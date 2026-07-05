# Changelog — RE-DCF-Tool

依語意化版本紀錄重要變更。計算公式變更一律先 `python test_golden.py` 全 PASS。

---

## v4.9 — 2026-07-01　Core 合約 v1.1（回應 Urban-Renewal 介面對齊回覆）

**背景**：Urban-Renewal（都更儀表板，純前端靜態站）完成 Phase 1 對接後回覆介面對齊備忘錄，
提出 owners[]／warnings[]／computed_at／core_version 四項規格建議。本版逐項落地。

**新增（合約 schema_version 1.0 → 1.1，向下相容，純新增欄位）**
- `core/contract.py`：新增 `_build_warnings()` 統一健檢判斷（Core 算、消費端只讀不重判）：
  `EFFICIENCY_OUT_OF_BAND`／`VOLUME_EXCEEDED`／`SHARED_COST_HIGH`／`SHARED_COST_LOW`／
  `VALUE_MULTIPLE_LOW`，共負門檻讀 `law_db.COMMON_BURDEN_RANGES`（依案件類型＋投報模式對照）。
- `owners[]`：地主清冊規格定案（`owner_id`／`land_share`／`pre_building_area_sqm`／
  `pre_value`／`consent`／`min_unit_eligible`／`return_value`／`equalization`／
  `selected_units`），規格由 Urban-Renewal 提出。新增 `_validate_owners()` 一致性自檢
  （Σ land_share≈1、Σ pre_value≈`result.pre_renewal_value`，容差 3%），偏離時附加
  `OWNERS_SHARE_MISMATCH`／`OWNERS_VALUE_MISMATCH` warning。
- `result.computed_at`（ISO 8601 UTC）／`result.core_version`：可追溯結果算於何時、哪版公式。
- `core/_version.py`：新增 `CORE_VERSION` 常數，獨立於 app.py 的 UI 版本號（不同軸線）。

**交付**
- `schemas/examples/`：4 個可重現的合約範例 JSON（危老合建／都更全案管理／都更防災+容積超出／
  含 owners 的合成範例），供 Urban-Renewal 壓測用；`generate_examples.py` 一鍵重產生。
- app.py Tab⑤ 新增 warnings 即時顯示（🔴/🟡/🔵），JSON 匯出時 `owners=[]`（尚無清冊輸入 UI，
  P1 待真實資料）。

**測試**：`test_golden.py` 新增 owners 一致性自檢測試（故意偏離 10% 持分，驗證抓到
`OWNERS_SHARE_MISMATCH`）與 `VOLUME_EXCEEDED` warning 斷言（合約測試案已知容積超出）。

**版本號 DRY 化**：app.py 散落 4 處的 `v4.x` 字串問題（見 v4.6 專案報告已知問題）尚未完全解決，
本版僅統一改字串內容，未來再抽成單一常數。

---

## v4.8 — 2026-06-28　L6 財務層真實案校準 + 三模式

**重構（財務層）**
- 營造基準由「允建坪」改為「總樓地板面積(含地下室)」（`calc_容積查核` 新增輸出）——
  修正舊法低估營造成本約一半的踩坑（B5F/B3F 地下室營造費原本全漏）。
- `calc_共同負擔` 新增 **三模式**（全案管理／合建／買賣）：土地成本、全案管理費、
  權變作業費依模式計入；新增科目代銷費、信託+公共基金；設計費率 5%→實際 ~1.4%。
- 拆補/租金補償基準改為「權變戶數」（既有地主），非總銷售戶數。

**資料（真實案）**
- 新增兩件真實案（危老在建合建案／都更權變審議案；案名與數字為私有校準紀錄）為 L6 校準基準。
- `範本模式` / `財務覆寫`：各案實際費率與模式。

**測試**：7 案 PASS。L6 校準結果——
兩案共負比／報酬率與實際值誤差均在 ±5% 內（校準明細私有，不進版控）。

**UI**：Step 4 新增投報模式切換；營造基準自動採總樓地板，移除手填粗估。

---

## v4.7 — 2026-06-27　vNext Sprint 1：Core Engine 化

**重構（架構）**
- 計算層由單一 `calc_engine.py` 拆分為 `core/` package（Urban Renewal Core Engine）：
  - `core/capacity.py`（容積 L2–L4）、`core/efficiency.py`（坪效 L4.5–L5）、
    `core/finance.py`（投報 L6）、`core/valuation.py`（更新前 L7）、
    `core/templates.py`（範本）、`core/io.py`（解析/報告）。
- `calc_engine.py` 降為**相容 shim**（`from core import *`），`app.py`、`test_golden.py` import 不變。

**新增（合約）**
- `core/contract.py` + `schemas/project_schema.json`：對外 Project JSON 合約。
  內部 domain 中文、對外 key 英文（`allow_floor_area`…），跨 App 唯一資料格式。
- `app.py` Tab ⑤ 新增「下載案件 JSON」+ 預覽。
- `test_golden.py` 新增「JSON 合約」測試（完整 pipeline → jsonschema 驗證）。

**測試**：5 案全 PASS（三容積案 + L6 投報 + JSON 合約）。

---

## v4.6 — 2026-06-23　P1 穩定現有資料
- Tab ④ 共同負擔比合理區間警示（依案件模式自動對照）。
- Step 5 更新前估值輸入 + `calc_更新前價值()`（L7 §56 基準）。
- 增值倍率指標（地主分回市值 ÷ 更新前總值）。

## v4.5 — 2026-06-22　P0 模組化
- 拆出 `calc_engine.py`（純計算）、`law_db.py`（法規庫）。
- 容積獎勵拆解 UI（都更 8 項 / 危老 6 項）+ `check_bonus_limit()` 法規上限驗證。
- 獎勵率由手動輸入改為各項自動累加。

## v4.4 — 2026-06-20
- 面積表匯入優化、§162 核對表、CLAUDE.md 建築師反饋協議。

## v4.1–v4.3 — 2026-06-10～06-17
- UI 重設計、藍圖 Hero、L2→L6 流程帶、步驟化引導、§162 欄位對照卡。
