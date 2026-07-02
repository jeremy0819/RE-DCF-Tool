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
- [x] L6 財務層真實案校準（竹蓮段/安民街，v4.8）
- [x] Core 合約 v1.1：`warnings[]` 統一健檢、`owners[]` 規格定案、
      `computed_at`/`core_version` 追溯（v4.9，回應 Urban-Renewal 對齊回覆）
- [ ] `models/`：Domain Model 類別（project / building / owner）
- [ ] `knowledge/`：法規知識庫骨架

### P1 — Domain Model 補完（需真實地主清冊資料）
- [ ] **owners[] 輸入 UI**：Step 5/6 新增地主清冊 CSV 匯入（比照逐層表模式），
      解鎖 Urban-Renewal 已實作的逐戶分回表／同意率視覺化／沙盤劇本橋接
- [ ] `calc_更新前價值()` 補路寬 / 使用分區 / 建物型態係數
- [ ] `calc_rights_exchange()` 權利變換：更新前價值 → 權值比例 → 分回（owners[] 逐戶）
- [ ] `calc_compensation()` 找補金（對應 owners[].equalization）
- [ ] `calc_irr()` / `calc_npv()` / `calc_cashflow()`（竹蓮段有實際撥款進度可校準）
- [x] L7 增值倍率合理區間防呆 → 已併入 v1.1 `VALUE_MULTIPLE_LOW` warning

### P2 — 法規 / 獎勵 / 財務引擎
- [ ] `regulation/` 分縣市（taipei / newtaipei / taoyuan…），每條含條文/上限/來源/更新日期
- [ ] Bonus Engine（獎勵自動累加 + 合法檢查，已有 `check_bonus_limit` 雛形）
- [ ] Loan Engine / Sensitivity / Monte Carlo（後期）

### P3 — 對外介面（Core 穩定後才做）
- [ ] Python Package（pip：`redcf-core`）
- [ ] JSON API / CLI
- [ ] FastAPI

---

## 與 Urban-Renewal Dashboard 的關係

```
Urban-Renewal/（純前端靜態站，evaluator.html）  ←  Project JSON  ←  RE-DCF Core
```

- 兩者**不同 Repository**，純 JSON 檔案交換（Urban-Renewal 無 build step / runtime，
  不共用 npm/pip package）。Dashboard **不重算任何 Core 公式**，含 warnings 健檢判斷。
- **狀態（2026-07）**：Phase 1 單向（Core 匯出 → Urban-Renewal 匯入顯示）**已雙方實作上線**。
  Urban-Renewal 的 `evaluator.html`「🔗 對接 RE-DCF Core」區塊已可讀取 Tab⑤ 匯出的 JSON。
- Phase 2（雙向：Urban-Renewal 權利人資料 → 回算 RE-DCF 權利變換）**待 V4 產品線穩定＋
  owners[] 輸入 UI 就緒**才啟動，需 Core 提供計算端點（FastAPI，對應 P3）。
- 契約版本紀律：schema 破壞性變更先知會 Urban-Renewal（bump `schema_version`）；
  v1.0→v1.1 為純新增欄位，未知會即可上線。
