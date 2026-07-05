# RE-DCF Core ⇄ Urban-Renewal 介面對齊回覆（v1.1 落地通知）

> **文件性質**：兩專案之介面契約紀錄（Interface Agreement Memo）
> **對象**：Urban-Renewal（儀表板／試算／沙盤）
> **我方**：RE-DCF Core Engine 開發方
> **回覆對象**：貴方 2026-07「RE-DCF Core ⇄ Urban-Renewal 介面對齊回覆」
> **契約**：`schemas/project_schema.json`（**schema_version 1.0 → 1.1**）
> **日期**：2026-07　**狀態**：已實作上線（`main` 分支）

---

## TL;DR

先謝謝這份備忘錄——四個問題答得非常具體，Q2 的 owners[] 規格表可以直接照抄，我們幾乎沒改動。

| 貴方建議 | 我方狀態 |
|---|---|
| 建議#1 單位標註（saleable_area 混淆） | 暫緩，見下方說明 |
| 建議#2 `warnings[]` | ✅ **已實作**，本版核心交付 |
| 建議#3 `computed_at` + `core_version` | ✅ **已實作** |
| 建議#4 owners 空陣列語意明訂 | ✅ 沿用貴方定義（總量可信、逐戶不可算） |
| 需求#1　2–3 個 Tab⑤ 匯出檔壓測 | ✅ **已交付**，見下方 |
| 需求#2　owners[] 開始填資料 | 🟡 **契約已就緒，UI 未就緒**（見下方說明） |
| 需求#3　warnings[]／computed_at／core_version | ✅ **已實作** |
| 需求#4　schema 破壞性變更先知會 | ✅ 本次為**非破壞性**新增，仍主動知會 |

---

## 一、`warnings[]`（貴方建議#2）── 已實作，Core 統一判斷

`result.warnings` 現在會依下列規則自動產生，**判斷邏輯完全在 Core 端**，貴方不需要、也不應該再自己重判任何門檻：

```json
"warnings": [
  { "code": "EFFICIENCY_OUT_OF_BAND", "level": "warn",
    "message": "銷坪比 1.700 不在正常帶 1.58–1.68", "field": "efficiency_ratio" },
  { "code": "VOLUME_EXCEEDED", "level": "error",
    "message": "容積超出允建 37.70 m²，需調整設計", "field": "remaining_floor_area" },
  { "code": "SHARED_COST_HIGH", "level": "error",
    "message": "共負比 64.6% 超過警示線 60%，地主接受度明顯降低", "field": "shared_cost_ratio" }
]
```

**目前規則清單**（`core/contract.py::_build_warnings()`）：

| code | 觸發條件 | level |
|---|---|---|
| `EFFICIENCY_OUT_OF_BAND` | 銷坪比不在 1.58–1.68 | warn |
| `VOLUME_EXCEEDED` | 容積餘量 < 0 | error |
| `SHARED_COST_HIGH` | 共負比 > 合理區間上限 | warn；超過警示線則 error |
| `SHARED_COST_LOW` | 共負比 < 合理區間下限 | info |
| `VALUE_MULTIPLE_LOW` | 增值倍率 < 1.0 | warn |
| `OWNERS_SHARE_MISMATCH` | Σ land_share 偏離 1.0（容差 3%） | warn |
| `OWNERS_VALUE_MISMATCH` | Σ pre_value 偏離 result.pre_renewal_value（容差 3%） | warn |

共負比門檻讀 `law_db.COMMON_BURDEN_RANGES`，**會依 `project.renewal_type` 與投報模式（全案管理／合建／買賣）自動對照不同區間**——這正是我們兩案例校準後才確定的真實門檻（危老 25–45%／60% 警示；都更全案管理 30–50%／65% 警示），比通用值準。

> 這份清單會持續擴充（例如未來 §162 相關規則），**code 命名穩定、不重編**，貴方可以放心用 code 做條件判斷而非解析 message 文字。

---

## 二、`owners[]`（貴方建議 Q2）── 規格照抄，一致性自檢已加

您 Q2 的 5 個必要欄＋4 個選填欄，我們**原樣採用**，寫進 schema 的 `required`：

```
owner_id / land_share / pre_building_area_sqm / pre_value / consent   ← 必要
min_unit_eligible / return_value / equalization / selected_units      ← 選填
```

多做的一件事：**Σ 一致性自檢**內建進 Core，不用貴方自己算：

- `Σ land_share ≈ 1`（容差 3%）偏離 → `OWNERS_SHARE_MISMATCH`
- `Σ pre_value ≈ result.pre_renewal_value`（容差 3%）偏離 → `OWNERS_VALUE_MISMATCH`

**owners[] 目前狀態老實說**：契約（schema + 驗證邏輯）已完整就緒，但 **RE-DCF 這邊還沒有地主清冊的輸入介面**——目前 Tab⑤ 匯出永遠是 `owners: []`。原因不是技術問題，是我們手上沒有任何一個案子的真實逐戶清冊資料（土地持分、更新前建物面積都是需要建築師/地政士提供的原始資料，不是能從坪效表反推的）。

**附上一份合成範例**（`合成範例_owners示範.json`）讓貴方先用真資料結構開發：48 戶等比分配、含三種 `consent` 狀態，Σ 兩項自檢都乾淨通過，可以直接餵您的匯入功能測。**這不是真實案件資料**，純示範用途。

---

## 三、`computed_at` + `core_version`（貴方建議#3）── 已實作

```json
"result": {
  ...,
  "computed_at": "2026-07-01T08:42:00+00:00",
  "core_version": "0.2.0"
}
```

- `computed_at`：每次匯出當下的 UTC 時間戳，不是固定值。
- `core_version`：獨立於 app.py 的 UI 版本號（`v4.9` 是介面版本，`0.2.0` 是計算引擎版本）——**這是刻意的設計**：UI 改版不代表公式變了，公式變了 UI 可能沒動，兩條版本線分開追蹤更準確。之後如果 Core 拆成獨立套件（ROADMAP P3），`core_version` 就是那個套件的版號。

---

## 四、`schema_version` 升版通知（貴方需求#4）

**1.0 → 1.1**，純新增欄位（`warnings` / `computed_at` / `core_version` 進 `result.required`；`owners[].items` 補完屬性），**不刪不改既有欄位**，理論上您現有的驗證器不用改也能繼續吃 1.0 格式的舊檔案。但既然升版了還是照您說的規矩主動通知——**這次不算破壞性，但還是先講**。

下次如果有真正破壞性變更（例如改掉現有欄位語意），會先開 issue 討論再動。

---

## 五、單位標註建議（您的建議#1）── 暫緩，說明原因

您說得對，`used_floor_area`(㎡) 跟 `saleable_area`(坪) 混用容易誤讀。我們決定**暫不加 `_ping`/`_sqm` 後綴**，原因：

- 現有消費端（含我們自己的 app.py）已經依賴目前的 key 名稱，改名是破壞性變更。
- 折衷方案：schema 的 `description` 已經標明單位（`"銷售坪數"` 明確寫「坪」，`"容積..."` 明確寫「m²」），建議貴方匯入時**先讀 description 建一份本地映射表**，比我們大改 key 名風險低。
- 若貴方認為這件事優先度夠高，我們可以在下次破壞性版本（2.0）一併處理，屆時會提前討論。

---

## 六、交付物清單（回應您需求#1）

`schemas/examples/` 已提交進 repo，4 個可重現範例（固定 `computed_at`，內容不隨產生時間漂移）：

| 檔案 | 涵蓋情境 |
|---|---|
| `合成案例D_危老合建.json` | 危老＋合建模式；EFFICIENCY_OUT_OF_BAND + VOLUME_EXCEEDED + SHARED_COST_HIGH |
| `合成案例A_都更全案管理.json` | 都更＋全案管理；容積剛好打滿（VOLUME_EXCEEDED 邊界情況，容積餘量≈0 但為負） |
| `合成案例C_防災都更_容積超出.json` | 都更＋防災；三個 warning 同時觸發，測多筆顯示 |
| `合成範例_owners示範.json` | 含 48 戶合成 owners[]，Σ 自檢乾淨通過 |

可直接指到 repo 裡這幾個檔案做壓測，不用再等我們手動傳檔。`generate_examples.py` 可重跑，之後 Core 公式有變、需要重新出範例時直接執行即可。

---

## 七、我方接下來要做的事

### 立即可做（不需要貴方配合）
1. **地主清冊輸入 UI**：Step 5/6 新增 CSV 匯入（比照現有逐層表模式），格式對齊 owners[] 9 欄。做完就能解鎖您說的「逐戶分回表／同意率視覺化／沙盤劇本橋接」三項——目前卡住的唯一原因是輸入介面，不是計算邏輯。
2. **`calc_rights_exchange()`**（權利變換：更新前價值 → 權值比例 → 分回）：schema 已經有 owners[] 的 `return_value`／`equalization` 欄位在等這個函式填值。

### 需要真實地主清冊資料才能做（卡在我們自己這邊，不是您）
3. 上面兩項做完後，才有辦法把 owners[] 從「合成範例」換成真案件——這需要建築師/代書提供實際清冊，不是我們能憑空生的。

### 不會做（邊界，跟您一致）
- ❌ 不會要求貴方重算任何 Core 公式或健檢門檻。
- ❌ Phase 2（FastAPI／雙向回算）在地主清冊 UI 與 IRR/NPV 模組穩定前不會啟動。
- ❌ 不會把任何真實案件的姓名、地號、金額放進這個 repo 或範例檔。

---

*版本 1.1｜2026-07｜RE-DCF Core 側回覆。合約以 `schemas/project_schema.json` 為準（schema_version 1.1）。*
