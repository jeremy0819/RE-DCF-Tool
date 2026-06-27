# RE-DCF Core — vNext Roadmap

> 定位：RE-DCF 不再只是「坪效工具」，而是 **Urban Renewal Core Engine** ——
> 所有都市更新系統（Dashboard / Simulator / AI Copilot / CRM / GIS）唯一可信的計算來源。
> 任何消費端**不得重新實作公式**，一律呼叫 Core，共享同一套 Domain Model、法規資料與測試。

---

## 開發原則（拍板，不可違反）

1. **所有公式只有一份**（Single Source of Truth）—— 實作在 `core/`。
2. **UI 與計算完全分離** —— `app.py` 僅 Demo，零計算邏輯。
3. **法規資料化，不寫死** —— 引用 `law_db.py` / 未來 `regulation/`。
4. **Domain Model 優先於 AI；Knowledge 優先於 Prompt；Core 優先於 Dashboard**。
5. **每新增公式，必須新增測試**（修改前必須 `python test_golden.py` 全 PASS）。
6. **RE-DCF 永遠保持獨立 Repository**。

### 命名慣例（vNext 決策，2026-06）

- **內部 domain 函式 / 變數 → 中文混用**（`calc_容積查核`、`calc_更新前價值`），貼合領域思考，符合 CLAUDE.md。
- **對外 JSON 合約 key → 英文**（`allow_floor_area`、`shared_cost_ratio`），給 Dashboard / AI 工程師消費。
- 分界點：`core/contract.py`（中文 calc 輸出 → 英文 key 映射）。

---

## 目標架構

```
re-dcf-core/
├── core/                  # 計算核心（唯一公式來源）
│   ├── capacity.py        # ✅ 容積查核 + 獎勵驗核（L2–L4）
│   ├── efficiency.py      # ✅ 銷售坪效 + 開發評效（L4.5–L5）
│   ├── finance.py         # ✅ 都更全案投報六大共負（L6）
│   ├── valuation.py       # 🟡 更新前估價（L7，基礎版，待校準）
│   ├── contract.py        # ✅ 對外 Project JSON 合約
│   ├── templates.py       # ✅ 範本案件種子（demo/測試）
│   ├── io.py              # ✅ Excel/CSV 解析 + Markdown 報告
│   ├── rights.py          # ❌ 權利變換（P1）
│   └── cashflow.py        # ❌ 現金流 / IRR / NPV（P1）
├── schemas/
│   └── project_schema.json # ✅ 對外合約 JSON Schema（draft-07）
├── law_db.py              # ✅ 法規庫（→ 未來 regulation/ 分縣市）
├── models/                # ❌ Domain Model（project/building/owner，P0 後續）
├── knowledge/             # ❌ 法規知識庫（AI 引用，P2）
├── app.py                 # ✅ Streamlit Demo（UI only）
└── test_golden.py         # ✅ 黃金 + 合約迴歸測試
```

✅ 已完成　🟡 雛形　❌ 未開始

---

## Roadmap

### P0 — Repository 重構（進行中）
- [x] Core 模組拆分：`calc_engine.py` → `core/`（capacity/efficiency/finance/valuation）
- [x] `calc_engine.py` 降為相容 shim（既有 import 不破）
- [x] Project JSON Schema（`schemas/project_schema.json` + `core/contract.py`）
- [x] 合約迴歸測試（`test_golden.py` 新增 JSON 合約驗證）
- [ ] `models/`：Domain Model 類別（project / building / owner）
- [ ] `knowledge/`：法規知識庫骨架

### P1 — Domain Model 補完（需安和段真實數據校準）
- [ ] `calc_更新前價值()` 補路寬 / 使用分區 / 建物型態係數
- [ ] `calc_rights_exchange()` 權利變換：更新前價值 → 權值比例 → 分回
- [ ] `calc_compensation()` 找補金
- [ ] `calc_irr()` / `calc_npv()` / `calc_cashflow()`
- [ ] L7 增值倍率合理區間防呆（>3× 黃燈 / >5× 紅燈）

### P2 — 法規 / 獎勵 / 財務引擎
- [ ] `regulation/` 分縣市（taipei / newtaipei / taoyuan…），每條含條文/上限/來源/更新日期
- [ ] Bonus Engine（獎勵自動累加 + 合法檢查，已有 `check_bonus_limit` 雛形）
- [ ] Loan Engine / Sensitivity / Monte Carlo（後期）

### P3 — 對外介面（Core 穩定後才做）
- [ ] Python Package（pip：`redcf-core`）
- [ ] JSON API / CLI
- [ ] FastAPI

---

## 與 Urban Dashboard 的關係

```
urban-dashboard/  →  Project JSON  →  re-dcf-core/  →  Result JSON  →  Dashboard
```

- 兩者**不同 Repository**。Dashboard **不能自行計算**，只能呼叫 RE-DCF。
- 結合分三階段：A 匯出/匯入 JSON（已具備合約）→ B Core 套件化 → C 雙向資料流。
- ⚠️ 在 Dashboard 真正消費前，**不提早拆多 repo**（避免同步成本）；先在本 repo 內 import-ready。
