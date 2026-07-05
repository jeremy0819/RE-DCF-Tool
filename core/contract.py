# -*- coding: utf-8 -*-
"""
core/contract.py — Project JSON 合約（對外唯一資料介面）
=====================================================
Urban Renewal Core Engine ── Single Source of Truth 的「對外合約」。

設計原則（vNext 決策）：
  - 內部 domain 函式用中文（calc_容積查核），貼合領域思考。
  - 對外 JSON 的 key 用英文（allow_floor_area），作為跨 App 合約。
  - Dashboard / Simulator / AI Copilot 一律消費此 JSON，不得自行重算公式，
    包含健檢判斷——一律讀 result.warnings，不自行重判門檻（v1.1 起）。

資料流：
  Input(中文 dict) → core.calc_*(中文 dict) → build_project_json() → 英文 JSON → 消費端

Schema 定義見 schemas/project_schema.json，build_project_json() 的輸出須通過該 schema 驗證。

v1.1（2026-07，回應 Urban-Renewal 介面對齊回覆）新增：
  - result.warnings[]：Core 端統一健檢判斷（銷坪比／容積超出／共負區間／增值倍率），
    消費端只讀不重判，避免兩端邏輯分歧。
  - result.computed_at / result.core_version：可追溯是哪個時間點、哪版公式算出的結果。
  - owners[]：地主清冊（權利事實欄位），規格由 Urban-Renewal 提出、雙方對齊。
"""

from datetime import datetime, timezone

from core.law_db import COMMON_BURDEN_RANGES
from core._version import CORE_VERSION

SCHEMA_VERSION = "1.1"

# 銷坪比合理帶（住宅正常 1.58–1.68，見 CLAUDE.md L4.5）
EFFICIENCY_LOW, EFFICIENCY_HIGH = 1.58, 1.68

# 投報模式 → 共負合理區間表（law_db.COMMON_BURDEN_RANGES）之對應
_模式對照 = {"全案管理": "都更全案管理", "合建": "都更合建", "買賣": "都更合建"}


def _共負區間(案件類型: str, 投報模式: str) -> dict:
    """危老案優先採「危老重建」區間；都更案依投報模式對應全案管理／合建區間。"""
    if 案件類型 == "危老":
        return COMMON_BURDEN_RANGES["危老重建"]
    return COMMON_BURDEN_RANGES[_模式對照.get(投報模式, "都更全案管理")]


# ===========================================================================
# 健檢 warnings[]（Core 統一判斷，消費端只讀不重判 —— Urban-Renewal 對齊回覆建議#2）
# ===========================================================================
def _build_warnings(容: dict, 坪: dict, 投: dict = None, 前: dict = None,
                    案件類型: str = "都更", 投報模式: str = "全案管理") -> list:
    warnings = []

    銷坪比 = 坪.get("銷坪比", 0.0)
    if not (EFFICIENCY_LOW <= 銷坪比 <= EFFICIENCY_HIGH):
        warnings.append({
            "code": "EFFICIENCY_OUT_OF_BAND", "level": "warn",
            "message": f"銷坪比 {銷坪比:.3f} 不在正常帶 {EFFICIENCY_LOW}–{EFFICIENCY_HIGH}",
            "field": "efficiency_ratio",
        })

    if 容.get("容積餘量", 0) < 0:
        warnings.append({
            "code": "VOLUME_EXCEEDED", "level": "error",
            "message": f"容積超出允建 {abs(容['容積餘量']):.2f} m²，需調整設計",
            "field": "remaining_floor_area",
        })

    if 投 is not None:
        區間 = _共負區間(案件類型, 投報模式)
        共負比 = 投.get("共負比", 0.0)
        if 共負比 > 區間["warn"]:
            warnings.append({
                "code": "SHARED_COST_HIGH", "level": "error",
                "message": f"共負比 {共負比:.1%} 超過警示線 {區間['warn']:.0%}，地主接受度明顯降低",
                "field": "shared_cost_ratio",
            })
        elif 共負比 > 區間["high"]:
            warnings.append({
                "code": "SHARED_COST_HIGH", "level": "warn",
                "message": f"共負比 {共負比:.1%} 高於合理區間上限 {區間['high']:.0%}",
                "field": "shared_cost_ratio",
            })
        elif 共負比 < 區間["low"]:
            warnings.append({
                "code": "SHARED_COST_LOW", "level": "info",
                "message": f"共負比 {共負比:.1%} 低於合理區間下限 {區間['low']:.0%}，建議覆核參數",
                "field": "shared_cost_ratio",
            })

    if 前 is not None and 投 is not None and 前.get("更新前總值", 0) > 0:
        倍率 = 投["地主分回價值"] / 前["更新前總值"]
        if 倍率 < 1.0:
            warnings.append({
                "code": "VALUE_MULTIPLE_LOW", "level": "warn",
                "message": f"增值倍率 {倍率:.2f}× 小於 1，地主更新後市值低於更新前估值",
                "field": "value_multiple",
            })

    return warnings


# ===========================================================================
# owners[]（地主清冊，權利事實欄位；規格對齊 Urban-Renewal 介面回覆 Q2）
# ===========================================================================
def _validate_owners(owners: list, pre_renewal_value: float) -> list:
    """一致性自檢：Σ land_share ≈ 1、Σ pre_value ≈ result.pre_renewal_value。
    容差 3%。owners 為空時不檢查（consumer 端已約定：空陣列＝『總量可信、逐戶不可算』）。
    """
    if not owners:
        return []
    warnings = []
    Σ持分 = sum(o.get("land_share", 0.0) for o in owners)
    if abs(Σ持分 - 1.0) > 0.03:
        warnings.append({
            "code": "OWNERS_SHARE_MISMATCH", "level": "warn",
            "message": f"Σ land_share = {Σ持分:.3f}，偏離 1.0（容差 3%）",
            "field": "owners",
        })
    if pre_renewal_value > 0:
        Σ權值 = sum(o.get("pre_value", 0.0) for o in owners)
        差 = abs(Σ權值 - pre_renewal_value) / pre_renewal_value
        if 差 > 0.03:
            warnings.append({
                "code": "OWNERS_VALUE_MISMATCH", "level": "warn",
                "message": f"Σ pre_value = {Σ權值:,.0f}，與 result.pre_renewal_value "
                           f"{pre_renewal_value:,.0f} 偏離 {差:.1%}（容差 3%）",
                "field": "owners",
            })
    return warnings


def build_result_json(容: dict, 坪: dict, 投: dict = None, 前: dict = None,
                      案件類型: str = "都更", 投報模式: str = "全案管理",
                      owners: list = None, computed_at: str = None) -> dict:
    """把各 calc 層的中文輸出，映射成英文 key 的 result 區塊（對外合約）。

    參數：
      容 = calc_容積查核 輸出
      坪 = calc_坪效 輸出
      投 = calc_投報全案 輸出（可選；無投報參數時為 None）
      前 = calc_更新前價值 輸出（可選；無更新前估值時為 None）
      案件類型/投報模式：供 warnings[] 的共負區間判斷選對照表
      owners：地主清冊（可選），供一致性自檢附加 warnings
      computed_at：ISO 8601 時間字串；None 時取當下 UTC 時間（供測試傳入固定值）
    """
    result = {
        # ── 容積（L2–L4）──
        "baseline_far":          round(容["基準容積FA"], 2),
        "allow_floor_area":      round(容["允建容積"], 2),
        "used_floor_area":       round(容["計入容積_修正後"], 2),
        "remaining_floor_area":  round(容["容積餘量"], 2),
        "stair_exempt_cap":      round(容["安全梯上限"], 2),
        "balcony_exempt_area":   round(容["陽台免計面積"], 2),
        # ── 坪效（L4.5）──
        "saleable_area":         round(坪["銷售坪數"], 2),
        "efficiency_ratio":      round(坪["銷坪比"], 3),
    }
    # ── 財務投報（L6，可選）──
    if 投 is not None:
        result.update({
            "total_sales":        round(投["總銷"], 0),
            "shared_cost":        round(投["共同負擔"], 0),
            "shared_cost_ratio":  round(投["共負比"], 4),
            "owner_return_value": round(投["地主分回價值"], 0),
            "owner_return_ratio": round(投["地主分回比"], 4),
            "return_rate":        round(投["報酬率"], 4),
        })
    # ── 更新前估值（L7，可選）──
    if 前 is not None:
        result["pre_renewal_value"] = round(前["更新前總值"], 0)
        if 投 is not None and 前["更新前總值"] > 0:
            result["value_multiple"] = round(投["地主分回價值"] / 前["更新前總值"], 2)

    warnings = _build_warnings(容, 坪, 投, 前, 案件類型, 投報模式)
    warnings += _validate_owners(owners or [], result.get("pre_renewal_value", 0.0))
    result["warnings"] = warnings

    result["computed_at"] = computed_at or datetime.now(timezone.utc).isoformat()
    result["core_version"] = CORE_VERSION

    return result


def build_project_json(P: dict, 容: dict, 坪: dict, 投: dict = None,
                       前: dict = None, 案件類型: str = "都更",
                       獎勵拆解: dict = None, 投報模式: str = "全案管理",
                       owners: list = None, computed_at: str = None) -> dict:
    """組出完整 Project JSON（合約格式），供 Dashboard / Simulator / AI 消費。

    P = L1 輸入參數 dict（範本參數 同結構）。其餘為各 calc 層輸出。
    owners：地主清冊 list[dict]（英文 key，規格見 schemas/project_schema.json）。
            無資料時傳 None／[]，消費端已約定空陣列的語意（僅顯示總量）。
    回傳結構對齊 schemas/project_schema.json（schema_version 1.1）。
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "project": {
            "name":         P.get("案件名稱", ""),
            "renewal_type": "urban_renewal" if 案件類型 == "都更" else "danger_building",
        },
        "land": {
            "site_area_sqm":     P.get("基地面積", 0.0),
            "plaza_area_sqm":    P.get("人行廣場", 0.0),
            "far":               P.get("容積率", 0.0),
            "bonus_ratio":       P.get("獎勵率", 0.0),
            "bonus_breakdown":   dict(獎勵拆解) if 獎勵拆解 else {},
            "tdr_transfer_sqm":  P.get("容積移轉", 0.0),
        },
        "building": {
            "public_ratio":          P.get("公設比", 0.0),
            "stair_hall_exempt_pct": P.get("梯廳免計基準", 0),
            "balcony_exempt_pct":    P.get("陽台免計基準", 0),
            "unit_count":            P.get("戶數", 0),
        },
        "owners": list(owners) if owners else [],
        "finance": {
            "residential_price":  P.get("住宅單價", 0.0),
            "shop_area":          P.get("店舖坪數", 0.0),
            "shop_price":         P.get("店舖單價", 0.0),
            "parking_count":      P.get("車位數", 0),
            "parking_price":      P.get("車位單價", 0.0),
            "construction_price": P.get("營造單價", 0.0),
        },
        "result": build_result_json(容, 坪, 投, 前, 案件類型, 投報模式, owners, computed_at),
    }
