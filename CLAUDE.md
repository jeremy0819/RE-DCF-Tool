# RE-DCF-Tool — 都更/危老前期評估・計算核心（Session 索引）

> Urban Renewal OS 的**唯一計算引擎（SSOT）**：容積查核、坪效、共同負擔、投報、估值。
> Streamlit 只是 Demo UI；公式全部在 `core/` package。
> 本檔是索引（≤150 行）：內容在被指向的檔案裡。舊版 337 行完整檔備份於
> `docs/backups/CLAUDE-2026-07-06-v4.9.md`。

## 背景與 code style（一段講完）

開發者＝建築學碩士＋都更 PM，正在學 Python。程式碼要求：清晰、大量中文註解、變數可用中文、
可讀性優先。內部函式中文命名（`calc_容積查核`）、對外 JSON key 英文——分界＝`core/contract.py`。

## 常用指令

```bash
pip install -r requirements.txt   # Python 3.11，版本已釘死
streamlit run app.py              # Web UI（Demo）
pytest                            # 黃金測試——改公式必跑，不綠不 commit
python make_template.py           # 改 L6 後必重跑（同步 Excel 對照範本）
python min_example.py             # 最小可跑範例
```

## 紅線（違反任何一條＝停止並回報使用者）

1. 公式只存在 `core/`——app.py 與任何消費端一條公式都不准寫（含 warnings 門檻）
2. `schemas/project_schema.json` **v1.1 凍結**：位元組不可變（基準 sha256 見 `歷史乾淨度報告.md`）；
   變更需求記 backlog
3. 零真實案件資料進版控（含檔名、commit 訊息）。驗證：`bash check_no_real_names.sh` → PASS
   （檢查字串只允許存在於該腳本與《歷史乾淨度報告.md》內）
4. 黃金測試期望值與校準費率（`財務率預設`）＝使用者核准才能改
5. `pytest` 不綠不 commit

## 檔案地圖（要細節就 ls / grep，本表不維護行號）

```
core/          計算核心（capacity/efficiency/finance/valuation/contract/law_db/templates/io）
schemas/       project_schema.json（v1.1 凍結）＋ examples/（合成範例＋generate_examples.py）
app.py         Streamlit UI（零公式）      test_golden.py   黃金＋合約測試（pytest）
calc_engine.py / law_db.py（根目錄）       DEPRECATED shim，新程式一律 from core import …
make_template.py → 都更全案投報_對照範本.xlsx（給建築師的對照）
供py/          真實案件資料（.gitignore 排除，絕不 commit）
```

## 路由表

| 要做的事 | 讀哪份 |
|---|---|
| 改公式／查六層架構、L6 科目、費率、踩坑點、黃金測試期望值 | `docs/計算與法規.md` |
| 日常開發、git 流程、版本號、部署驗收、建築師反饋協議 | `docs/開發與部署.md` |
| 排優先序（權變/現金流/IRR 什麼時候做） | `ROADMAP.md`＋BUILDER `docs/architecture/ROADMAP.md` |
| 合併搬遷相關（本庫將以乾淨快照搬入 BUILDER） | `合併計畫-RE-DCF側角色說明.md`、`歷史乾淨度報告.md`、BUILDER `docs/architecture/MIGRATION_PLAN.md` |
| 派 subagent／驗收／判斷準則（全 OS 通用制度） | BUILDER repo `governance/`（未掛載則 add_repo `jeremy0819/BUILDER`） |
| 公式修正歷史教訓 | `REVIEW.md`、`CHANGELOG.md` |

## 分支與版控

- 分支以**當前 session 被指定者**為準（舊文件的 `claude/claude-md-docs-ls9Bu` 已過時）。
- 只 `git add <改過的檔>`；commit 前跑紅線 3 的檢查腳本＋`pytest`。

## 現況座標（2026-07）

Core v0.2.0（基準 commit `ea0fe9b`；⚠️ tag `v0.2.0-premerge` 尚未推上遠端，遠端替代 ref＝
分支 `premerge-v0.2.0`，正式 tag 待 repo 擁有者補推）／schema v1.1 凍結／合併前置 P0–P2 完成。
下一步＝依 BUILDER `MIGRATION_PLAN.md` 搬遷；搬遷前本庫**不加新功能**（「搬家不是改建」）。
