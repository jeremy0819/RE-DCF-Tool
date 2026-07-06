# 合併計畫 — RE-DCF 側角色說明

> **文件性質**：兩庫合併之 RE-DCF 側交接文件（P0-3），與 Urban-Renewal 側
> 《合併計畫-Urban-Renewal側角色說明.md》對讀。新 session 依這兩份開工，
> 不需回頭問基本問題。
> **日期**：2026-07　**基準點**：tag `v0.2.0-premerge`（UI v4.9／Core v0.2.0／schema v1.1）
> **配套**：《歷史乾淨度報告.md》（P0-2，含合併策略建議：**乾淨快照**）

---

## 定位一句話

RE-DCF 在合併後是**唯一計算引擎（Single Source of Truth）**——合併是「消費端與
計算核心住進同一棟樓」，不是「兩個 app 揉成一個」。預期搬家路徑：`core/` → 新庫
`core/redcf/`（core 已自含、零 UI 依賴，見 P1-1 驗證）。

---

## 一、資產清單（搬家清單）

### 計算核心 `core/`（唯一公式來源；自含，law_db 已內移）
| 模組 | 內容 | 狀態 |
|---|---|---|
| `capacity.py` | 容積查核＋獎勵驗核（L2–L4；§162 逐層） | ✅ 穩定，真實案驗證 |
| `efficiency.py` | 銷售坪效＋開發評效（L4.5–L5） | ✅ 穩定 |
| `finance.py` | 共同負擔／投報（L6；三模式：全案管理/合建/買賣） | ✅ 真實案校準 ±5%（私有紀錄） |
| `valuation.py` | 更新前估值（L7 基礎版） | 🟡 待補路寬/分區係數 |
| `contract.py` | 對外 JSON 合約（中文 calc → 英文 key）＋ warnings 健檢＋owners 自檢 | ✅ v1.1 |
| `law_db.py` | 法規庫（容獎上限/§162/共負區間） | ✅（未分縣市） |
| `templates.py` | 合成案例 A–D（去識別化種子） | ✅ |
| `io.py` | Excel/CSV 解析＋Markdown 報告 | ✅ |
| `_version.py` | `CORE_VERSION`（獨立於 UI 版號） | ✅ 0.2.0 ＝ tag 對齊 |

### 契約與測試
- `schemas/project_schema.json`：**對外唯一合約**（draft-07，v1.1，**已凍結**，
  hash 見乾淨度報告）。owners[] 規格由 Urban-Renewal 提出、雙方定案。
- `schemas/examples/`：4 個合成範例 JSON（各 warnings 組合）＋ `generate_examples.py`
  一鍵重產＋ `min_input.json`。
- `test_golden.py`：**pytest 一鍵**黃金測試（4 合成容積案＋2 個 L6 鎖定＋JSON 合約
  schema 驗證）。乾淨 clone → `pip install -r requirements.txt` → `pytest` 三步全綠。
- `min_example.py`：10 行最小可跑範例（P1-1 驗收件）。

### UI（Demo 性質）
- `app.py`：Streamlit，純 UI 零公式；Streamlit Cloud 以 `streamlit run app.py` 部署。
- `make_template.py` → `都更全案投報_對照範本.xlsx`：給建築師的 Excel 對照。

### 相容 shim（合併時可淘汰）
- `calc_engine.py`、root `law_db.py`：舊 import 路徑轉接。新庫若統一改
  `from core.redcf import …`，這兩個 shim 可刪（app.py import 需同步改）。

---

## 二、紅線（不可被合併破壞）

1. **公式只有一份**：任何消費端（含合併後同庫的靜態站）不得複製/重算 core 公式，
   **含 warnings 健檢門檻**。出現「把計算邏輯搬去前端比較快」的提案一律擋。
2. **合約凍結紀律**：合併期間 `project_schema.json` 位元組不變（hash 驗證）；
   變更需求記 backlog，合併完成後照「知會 → bump schema_version」流程。
3. **黃金測試是硬門檻**：任何搬家/改路徑後 `pytest` 必須全綠才算搬完。教訓：光看
   單元測試不夠——v4.8 曾有 golden 全綠但 UI 整頁崩潰的 regression，**牽涉 UI 的
   變更要真實開瀏覽器驗**。
4. **中文 domain／英文合約的分界**（`core/contract.py`）不可模糊：內部函式保持中文
   命名（CLAUDE.md 規範），對外 key 保持英文。
5. **真實案資料不進版控**：合成案例已去識別化；未來任何真實清冊/金額只進私有紀錄。

---

## 三、已知風險與立場

| 議題 | 我方立場 | 理由 |
|---|---|---|
| 合併策略 | **乾淨快照＋舊庫私有封存**（非 subtree） | git 歷史含真實案名/金額（見乾淨度報告），改寫歷史不如快照 |
| 部署 | 合併後仍需兩條部署線（Pages 靜態站＋Streamlit 計算工具） | 技術棧不同；Streamlit Cloud 進入點需指向新庫路徑，**合併當天要改部署設定** |
| 相對 import | `core/` 內部全用 `from core.xxx import`，搬到 `core/redcf/` 需整批改前綴（機械性，測試會抓） | 已知、可控 |
| 版本線 | 合併後 `CORE_VERSION` 延續（0.2.0 →），UI 版號（v4.9）可淘汰或歸零 | core_version 是消費端追溯依據，不可斷 |
| Phase 2（雙向/FastAPI） | 合併**不**順帶啟動 Phase 2 | 對方清單也明列「不是前置任務」；公式未穩定前開 API 會讓消費端一直被打到 |
| 舊 Streamlit URL | 舊部署顯示過真實案名，舊庫封存時應下架/覆蓋 | 見乾淨度報告殘留風險 #3 |

---

## 四、技術債清單（老實列）

| 債 | 影響 | 對應路線 |
|---|---|---|
| **owners 輸入 UI 未做** | Tab⑤ 匯出永遠 `owners: []`；對方做好的逐戶分回/同意率功能接不到真資料 | v5 |
| **`calc_rights_exchange()`／`calc_compensation()` 未做** | `owners[].return_value`/`equalization` 無函式填值 | v5 |
| **IRR／NPV／現金流未做** | 只有單期報酬率；資金時程功能 Core 端生不出數字 | v6 |
| **合約缺逐層樓板輸入** | 從合約 JSON 無法重算 result（§162 需逐層資料）；schema 2.0 候選 | 凍結期不動 |
| **law_db 未分縣市** | 目前為一般性規則，無縣市差異 | v6 |
| **UI 版號散落**（app.py 4 處字串） | 更版易漏；合併時建議一次抽常數 | 順手做 |
| **`calc_更新前價值` 為基礎版** | 缺路寬/分區/建物型態係數，估值精度有限 | v5 |
| **合成案例的真實性邊界** | 黃金測試現為「合成輸入迴歸鎖」；「等於真實案」的驗證只存在私有紀錄，新公式要再校準時需回私有資料 | 常態 |

---

## 給合併 session 的驗收指令（照對方清單流程）

```bash
git clone <本庫> && cd RE-DCF-Tool
pip install -r requirements.txt          # Python 3.11
pytest                                    # 全綠
python min_example.py                     # 出 result JSON
bash check_no_real_names.sh               # PASS（真實段名檢查，字串只存在腳本與乾淨度報告內）
sha256sum schemas/project_schema.json     # 對照乾淨度報告之凍結 hash
git tag -l v0.2.0-premerge                # 基準 tag 存在
```

*版本 1.0｜2026-07｜RE-DCF 側交接文件（取代先前 MERGE_PLAN.md）。*
