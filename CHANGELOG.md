# Changelog — RE-DCF-Tool

依語意化版本紀錄重要變更。計算公式變更一律先 `python test_golden.py` 全 PASS。

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
- `test_golden.py` 新增「JSON 合約」測試（中正段 pipeline → jsonschema 驗證）。

**測試**：5 案全 PASS（安和 / 龜山 / 中正 / 中正投報 / JSON 合約）。

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
