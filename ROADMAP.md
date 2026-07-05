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
- [x] L6 財務層真實案校準（兩件真實案，私有紀錄，v4.8）
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
- [ ] `calc_irr()` / `calc_npv()` / `calc_cashflow()`（在建實案有實際撥款進度可私下校準）
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

## 版本路徑（v5 – v7）

> 現況 v4.9（Core 合約 v1.1）。以下把 P1–P3 剩餘項目對應到版本號，依**相依順序**排列——
> 後面版本的工作大多卡在前面版本先做完（例如 IRR 需要 owners[] 先有真實分回數字才能校準）。

### v5 — Domain Model 補完（owners[] 真正可用）
> 對應 P1 + P0 剩餘的 `models/`。目標：owners[] 從「合成範例」變成能吃真實清冊、算出逐戶分回。

| 項目 | 說明 | 前置 |
|---|---|---|
| owners[] 輸入 UI | Step 5/6 新增地主清冊 CSV 匯入（比照現有逐層表模式） | 無，可立即做 |
| `models/`：Domain Model 類別 | project / building / owner，取代目前散落各處的 dict 傳遞 | 無，可與上一項並行 |
| `calc_更新前價值()` 補強 | 加路寬 / 使用分區 / 建物型態係數，目前是基礎版 | 無 |
| `calc_rights_exchange()` | 更新前價值 → 權值比例 → 分回，填 owners[].`return_value` | owners[] 輸入 UI |
| `calc_compensation()` | 找補金，填 owners[].`equalization` | `calc_rights_exchange()` |
| **黃金測試** | 用真實案（私有）校準逐戶分回；版控內先用合成資料鎖回歸 | 待使用者提供真實清冊，否則沿用合成範例 |

**卡點**：目前沒有任何一案的真實地主清冊（土地持分、逐戶更新前建物面積）。UI 和函式可以先用合成資料做完，但要「真的算對」需要你提供至少一案的真實清冊。

### v6 — 財務引擎深化 + 法規資料庫
> 對應 P1 剩餘的現金流模組 + P2。目標：從「單期報酬率」補到「分期現金流＋分縣市法規」。

| 項目 | 說明 | 前置 |
|---|---|---|
| `calc_cashflow()` | 分期現金流（規劃→基礎→結構→裝修→交屋），在建實案 Excel 之現金流量表／請款紀錄可私下校準 | 無，資料已在手（私有） |
| `calc_irr()` / `calc_npv()` | 建在 `calc_cashflow()` 的分期現金流之上 | `calc_cashflow()` |
| Loan Engine | 建融/土融改分期攤還排程，取代目前 D 貸款利息的單期簡化算法 | `calc_cashflow()` |
| Sensitivity 擴充 | 現有售價×營造雙軸熱力圖，擴充到 IRR/NPV 維度 | `calc_irr()`/`calc_npv()` |
| `regulation/` 分縣市 | 拆 `law_db.py` → `regulation/{taipei,newtaipei,taoyuan,...}/`，每條規則附條文/上限/來源/更新日期 | 無，可與財務引擎並行 |
| `knowledge/` 骨架 | 法規知識庫（都市更新/危老/估價/土地法/建築技術規則），供未來 AI 引用 | 無 |
| Monte Carlo | 售價/成本常態分佈模擬，在建實案 Excel 已有雛形分頁可參考 | `calc_irr()` |

**卡點**：在建實案的三張現金流分頁已讀過但還沒建模；`regulation/` 分縣市需要你確認除了目前默認值以外，還要建哪些縣市（目前只有一般性 §162／都更容獎／危老 §6，未分縣市差異）。

### v7 — 對外介面 + Urban-Renewal Phase 2
> 對應 P3。目標：Core 從「這個 repo 裡的 package」變成「任何人都能呼叫的服務」。

| 項目 | 說明 | 前置 |
|---|---|---|
| Python Package（`redcf-core`） | 把 `core/` 抽成獨立可 pip install 的套件，`app.py` 與其他消費端改用套件而非相對 import | v5+v6 的公式都要先穩定 |
| FastAPI | 對外 HTTP 端點，`POST /calc` 吃 Project JSON（不含 result）→ 回傳完整結果 | Python Package |
| JSON API / CLI | 命令列版本（`redcf-core calc case.json`），方便 CI/批次跑 | Python Package |
| **Urban-Renewal Phase 2** | 雙向資料流：他們的權利人真實資料 → 呼叫 FastAPI 端點 → 回算權利變換 | FastAPI + v5 的 `calc_rights_exchange()` |

**卡點**：這一步之前 ROADMAP 就寫「Core 穩定後才做」——實務上就是等 v5、v6 的公式都經過真實案驗證，不要在公式還會變動時就開對外服務，否則消費端會一直被破壞性變更打到。

---

## 不在 v5–v7 範圍內（明確排除）

- **商辦版**（NOI + Cap Rate + 持有期報酬）：CLAUDE.md 已註記「住宅工具上線後，複製架構做商辦版，另開對話處理」——這是平行的產品線，不是這條 roadmap 的延伸，不占用 v5–v7 的版本號。
- **AI Copilot**：ROADMAP 開發原則第 4 條「Domain Model 優先於 AI」——v5–v7 都是 Domain Model／Core，AI 層要等這些穩定才開始，且會是另一個 repo（消費 Core 的 JSON，不重算）。

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
