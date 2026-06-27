# -*- coding: utf-8 -*-
"""
core/contract.py — Project JSON 合約（對外唯一資料介面）
=====================================================
Urban Renewal Core Engine ── Single Source of Truth 的「對外合約」。

設計原則（vNext 決策）：
  - 內部 domain 函式用中文（calc_容積查核），貼合領域思考。
  - 對外 JSON 的 key 用英文（allow_floor_area），作為跨 App 合約。
  - Dashboard / Simulator / AI Copilot 一律消費此 JSON，不得自行重算公式。

資料流：
  Input(中文 dict) → core.calc_*(中文 dict) → build_project_json() → 英文 JSON → 消費端

Schema 定義見 schemas/project_schema.json，build_project_json() 的輸出須通過該 schema 驗證。
"""

SCHEMA_VERSION = "1.0"


def build_result_json(容: dict, 坪: dict, 投: dict = None, 前: dict = None) -> dict:
    """把各 calc 層的中文輸出，映射成英文 key 的 result 區塊（對外合約）。

    參數：
      容 = calc_容積查核 輸出
      坪 = calc_坪效 輸出
      投 = calc_投報全案 輸出（可選；無投報參數時為 None）
      前 = calc_更新前價值 輸出（可選；無更新前估值時為 None）
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
    return result


def build_project_json(P: dict, 容: dict, 坪: dict, 投: dict = None,
                       前: dict = None, 案件類型: str = "都更",
                       獎勵拆解: dict = None) -> dict:
    """組出完整 Project JSON（合約格式），供 Dashboard / Simulator / AI 消費。

    P = L1 輸入參數 dict（範本參數 同結構）。其餘為各 calc 層輸出。
    回傳結構對齊 schemas/project_schema.json。
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
        "finance": {
            "residential_price":  P.get("住宅單價", 0.0),
            "shop_area":          P.get("店舖坪數", 0.0),
            "shop_price":         P.get("店舖單價", 0.0),
            "parking_count":      P.get("車位數", 0),
            "parking_price":      P.get("車位單價", 0.0),
            "construction_price": P.get("營造單價", 0.0),
        },
        "result": build_result_json(容, 坪, 投, 前),
    }
