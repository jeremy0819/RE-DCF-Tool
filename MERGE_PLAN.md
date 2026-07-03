# RE-DCF-Tool 側：合併計畫角色定位文件

> **文件性質**：交接簡報（Handoff Briefing），供**另一個全新 session** 讀取後接手合併規劃。
> **寫作方**：RE-DCF-Tool（坪效分析／都更前期評估工具）session
> **對照方**：Urban-Renewal（都更儀表板）應有一份對等文件，由該側 session 另外產出
> **用途**：使用者會把這份文件＋Urban-Renewal 那份文件一起餵給新 session，讓新 session
>   在**不用重跑兩邊全部歷史對話**的情況下，直接進入「怎麼合併」的實質討論。
> **日期**：2026-07　**現況版本**：RE-DCF-Tool v4.9（Core Engine v0.2.0，合約 schema v1.1）

---

## 給新 session 的一句話摘要

RE-DCF-Tool 在合併後的系統裡，角色是**唯一計算引擎（Single Source of Truth）**——
不是被合併掉的一方，而是**兩個 repo 共同依賴的計算核心**。合併的正確理解不是「兩個
app 揉成一個」，而是「Urban-Renewal 這個消費端，要用什麼方式呼叫 RE-DCF 這個計算核心」。
這個定位已經跟 Urban-Renewal 側書面對齊兩輪（見下方「已對齊事項」），不是我方單方面主張。

---

## 一、我是誰（現況，供新 session 快速建立心智模型）

| 項目 | 內容 |
|---|---|
| Repo | `jeremy0819/RE-DCF-Tool` |
| 開發分支 | `claude/claude-md-docs-ls9Bu` → merge no-ff → `main`（Streamlit Cloud 自動部署） |
| 部署 URL | `https://re-dcf-tool-ovmbnrh45ew2khaklhhn3t.streamlit.app` |
| UI 版本 | v4.9 |
| Core Engine 版本 | `core/_version.py::CORE_VERSION = "0.2.0"`（**獨立於 UI 版本**，見下方說明） |
| 對外合約版本 | `schema_version = "1.1"`（`schemas/project_schema.json`） |
| 黃金測試 | `python test_golden.py`，7 案全 PASS（容積 4 案 + L6 財務 2 真實案 + JSON 合約） |
| 技術棧 | Python 3、Streamlit（UI-only）、Plotly、Pandas、jsonschema |

**架構**：計算公式全部在 `core/` package，`app.py` 純 UI／Demo，零計算邏輯。內部 domain
函式用中文（`calc_容積查核`），對外 JSON 合約用英文 key（`allow_floor_area`），分界點在
`core/contract.py`。詳見 `ROADMAP.md`（含完整目標架構樹狀圖）與 `CLAUDE.md`（函式目錄、
六大踩坑點、法規依據）。

**兩個真實案例已完成校準**（`core/templates.py` 的「安和段」「竹蓮段」範本）：
- **安民街(安和段)**：都更、全案管理模式、權變審議版數據 —— 共負比 55.3%、報酬率 81%
- **竹蓮段**：危老、合建模式、實際在建發包數據 —— 共負比 64.8%、ROI 54%

這兩案是目前**唯一有真實數字背書**的案例，其餘（龜山段、中正段）是較早期的示範資料，
數字未必經得起真實案比對。新 session 若要做任何「這樣算對不對」的判斷，優先信這兩案。

---

## 二、我在合併計畫中的角色

### 2.1 唯一計算來源（Single Source of Truth）
所有容積、坪效、共同負擔、更新前估值公式只在 `core/` 實作一次。任何消費端（Urban-Renewal
儀表板、未來的 Simulator、AI Copilot、CRM）**不得重新實作或重算這些公式**。這不是客氣話，
是這次合併唯一不能退讓的原則——理由見下方「三、我的邊界」。

### 2.2 對外合約的擁有者與版本守門人
`schemas/project_schema.json` 由我方定義、維護、決定何時升版。目前 schema_version 1.1
的 `owners[]` 9 個欄位規格，是 Urban-Renewal 提出、我方採納訂進 schema 的——這示範了正確
的協作模式：**消費端提需求，Core 端決定怎麼落進合約**，不是消費端自己土法煉鋼算。

### 2.3 統一健檢／判斷邏輯的提供者
v1.1 新增的 `result.warnings[]` 是這個角色的具體實作：銷坪比是否正常、容積是否超出、
共負比是否在合理區間、增值倍率是否偏低——這些「好不好」的判斷全部由 Core 產生，
消費端只讀 `warnings[].code`／`level` 顯示紅黃燈，**不自己重判門檻**。這避免了兩邊各自
寫一套規則、規則不一致的問題。

### 2.4 品質守門（回歸測試 + 真實案校準）
`test_golden.py` 是任何變更（不管是我方自己改，還是為了配合合併而改）的硬門檻。
本次會話過程中，光靠這道測試**不夠**——曾經因為只跑 golden test、沒有真的開瀏覽器操作，
放過 3 個會讓 UI 整頁崩潰的 regression（詳見 CHANGELOG v4.8 修正紀錄）。**合併計畫如果
牽涉到 UI 或跨 repo 呼叫，光看單元測試綠燈不夠，一定要有真實操作驗證這一關。**

### 2.5 我明確「不」擁有的角色
不是專案管理、不是 Dashboard、不是 CRM、不是 GIS、不是 AI 對話介面。這些如果合併後要做，
應該是 Urban-Renewal 那一側的範疇，或是未來第三個 repo，**不會塞進 RE-DCF 裡**。

---

## 三、我的邊界（合併時請新 session 守住這條線）

```
RE-DCF 負責：容積 / 坪效 / 法規檢核 / 共同負擔 / 財務模型 / 權利變換(進行中) / 現金流(規劃中) / 更新前估價
RE-DCF 不負責：UI / Project List / Login / 地圖 / AI 對話 / CRM / 甘特圖
```

合併規劃如果出現「乾脆把兩邊的計算邏輯都搬到同一個檔案裡比較快」這種提案，這是**要優先
反對的方向**——目前兩邊已經用 JSON 合約分離得很乾淨，合併不應該讓這條線模糊掉。

---

## 四、與 Urban-Renewal 已對齊事項（合併前的既有基礎，別重談）

這不是從零開始的合併，過去已經有兩輪書面往來，新 session 不需要重新協商以下已定案的部分：

| 事項 | 狀態 | 文件出處 |
|---|---|---|
| 純 JSON 檔案交換（非共用 package） | ✅ 雙方確認，因 Urban-Renewal 是零依賴純前端靜態站 | Urban-Renewal 回覆備忘錄 Q1 |
| Phase 1 單向對接（Core 匯出 → Dashboard 匯入顯示） | ✅ **雙方已實作上線**，`evaluator.html`「🔗 對接 RE-DCF Core」 | 同上 |
| owners[] 9 欄位規格 | ✅ 規格由 Urban-Renewal 提出，我方採納進 schema 1.1 | `RE-DCF回覆_介面對齊v1.1.md` |
| warnings[] 統一健檢 | ✅ 已實作，Core 算、消費端只讀 | 同上 |
| Phase 2（雙向：Dashboard 權利人資料 → 回算權利變換）啟動條件 | 🟡 已有共識：待 V4 產品線穩定＋owners UI 就緒＋FastAPI | 同上 |
| Schema 破壞性變更需先知會 | ✅ 雙方協議 | 同上 |

**這四份文件是合併規劃的既有基礎，建議新 session 開場就讀過**：
1. `ROADMAP.md`（本 repo）— 我方目標架構、v5–v7 路徑
2. `CHANGELOG.md`（本 repo）— 逐版變更含技術細節
3. Urban-Renewal 提供的介面對齊回覆備忘錄
4. `schemas/examples/RE-DCF回覆_介面對齊v1.1.md`（本 repo）— 我方對上述備忘錄的逐條回覆

---

## 五、我這邊尚未就緒、會卡住合併深化的部分

誠實列出，避免新 session 誤以為「兩邊都準備好了，可以直接做深度整合」：

| 缺口 | 影響 | 對應 ROADMAP 版本 |
|---|---|---|
| **無真實地主清冊** | `owners[]` 目前永遠輸出空陣列或合成範例；任何依賴逐戶分回的合併功能（Urban-Renewal 已做好的「逐戶分回表」「同意率視覺化」）目前接不到真資料 | v5，需使用者提供 |
| **無 `calc_rights_exchange()`** | 權利變換（更新前價值→權值比例→分回）還沒實作，`owners[].return_value` 目前不會被填值 | v5 |
| **無 `calc_cashflow()`／IRR／NPV** | 只有單期報酬率，沒有分期現金流；Urban-Renewal 若要做資金時程相關功能，Core 端還生不出這個數字 | v6 |
| **無 FastAPI／對外服務** | Phase 2 雙向資料流需要的呼叫端點還不存在，現在只能靠檔案匯出匯入 | v7 |
| **`law_db.py` 未分縣市** | 現在的容積獎勵/免計規則是「一般性版本」，沒有依縣市差異化 | v6 |

**結論**：目前的合併只能停在「Phase 1 單向 JSON 交換」這個深度，這已經是雙方實作上線的
現況。任何更深的整合（雙向、即時 API、逐戶真實分回）都卡在上表，不是合併規劃本身能解決的，
是要先把 v5/v6/v7 做完。**新 session 如果要規劃合併時程，這張表就是甘特圖的依賴關係。**

---

## 六、我對合併架構的立場（供新 session 參考，非最終定論）

延續 `ROADMAP.md` 已寫的判斷，我方傾向：

1. **維持兩個獨立 repo**，不要因為要合併就變成 monorepo。理由：Urban-Renewal 是零依賴純
   前端靜態站，RE-DCF 是 Python 計算引擎，技術棧完全不同，硬塞進同一個 repo 只會讓兩邊的
   建置/部署流程互相干擾。
2. **合約先於程式碼**：目前用 JSON Schema + 版本號（1.0→1.1）管理相容性，這個模式已經
   跑通一輪、雙方都能接受，合併規劃應該延續這個模式，而不是換一套機制。
3. **深度整合（Phase 2 雙向）要等 Core 穩定**：這不是保守，是有過教訓——這次會話中光是
   把「允建坪」換成「總樓地板面積」當營造基準，就讓共負比從錯誤的 38% 校準到正確的 55%。
   如果 Phase 2 在公式還會這樣大改的階段就上線，Urban-Renewal 那邊會一直被破壞性變更打到。

**但這些是我方立場，不是雙方已經拍板的決議**——新 session 的任務之一，應該是把這份文件
和 Urban-Renewal 那份文件放在一起看，找出兩邊立場**不一致**的地方（如果有的話），那才是
真正需要「合併規劃」討論的內容，而不是重複已經對齊的部分。

---

## 七、給新 session 的建議起手式

1. 讀完這份文件 + Urban-Renewal 對等文件。
2. **先做差異比對**：兩份文件對「合併」的想像是否一致？（例如：Urban-Renewal 是否也認為
   應該維持兩個 repo？他們對 Phase 2 時程的預期跟本文件第五節的卡點表對得上嗎？）
3. 差異比對完，才進入實質規劃：時程表、誰先做 owners UI、`calc_rights_exchange()` 的
   輸出格式要不要先跟 Urban-Renewal 對一版草稿再實作（避免像 schema 1.1 那樣事後改）。
4. 任何規劃結論，比照本 repo 慣例寫回 `ROADMAP.md`／`CHANGELOG.md`，不要只留在對話裡。

---

*版本 1.0｜2026-07｜RE-DCF-Tool 側合併計畫角色定位文件。*
