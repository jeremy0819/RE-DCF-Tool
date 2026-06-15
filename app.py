# -*- coding: utf-8 -*-
"""
RE-DCF-Tool — 都更/危老前期評估工具（v4.2 設計感升級版）
==============================================================
永盛開發建設「建築坪效與前期評估」Excel 財務模型的程式化版本。
執行：streamlit run app.py

v4.2 更新（創意設計 × 專業質感，計算層不動）：
  1.【字體】導入 Noto Sans TC + Space Grotesk（數字等寬對齊 tabular-nums）。
  2.【Hero】Header 改深靛藍「藍圖網格」橫幅（建築製圖意象）+ 版本徽章。
  3.【流程帶】新增 L2→L6 計算流程帶 _pipeline()，六層架構即時數值串接。
  4.【KPI】卡片頂部狀態色 accent 條 + 迷你進度條（容積使用率/銷坪比定位/投報），hover 浮起。
  5.【區塊標題】_section() 紫色側標，統一各 Tab 小節層級。
  6.【背景】淡靛放射漸層底 + 卡片陰影層次 + 頁尾資訊列。
  7.【圖表】Plotly 字體/品牌色同步（#534AB7 / #1E1B4B）。

v4.1 更新（UI 精化 + 方法論蒸餾）：
  1.【UI】全局 CSS 升級：漸層 Tab、卡片陰影、專業字重、Grid 排版。
  2.【UI】Header 改紫色漸層橫幅（HTML），案件名稱內嵌。
  3.【UI】結論橫幅改 HTML styled div（顏色更精確）。
  4.【UI】KPI 卡改 HTML 自製（可依狀態染色，值/注釋分層排版）。
  5.【UI】統一 Plotly 佈局函式 _fig_layout()，圖表風格一致。
  6.【參數】新增 L6 土融土地成本輸入（原本鎖定 0，都更全案投報可覆寫）。
  7.【功能】Tab ② 坪效新增「公設比反推驗算」（方法論 §6 第一項）。
  8.【功能】Tab ④ 都更投報新增「費率基數一覽」摺疊表（方法論 §4③）。

核心計算承襲 v3：陽台/梯廳超出皆「逐層」判斷（§162），
已對齊安和/龜山/中正三案圖說。黃金測試：python test_golden.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# 常數
# ---------------------------------------------------------------------------
平方米換坪 = 3.3058
安全梯免計率 = 0.15
樓層欄位 = ["啟用", "樓層", "樓板", "計容積", "梯廳", "安全梯", "陽台"]


# ===========================================================================
# 計算層（純函式，無 Streamlit，方便測試）
# ===========================================================================
def calc_容積查核(參數: dict, 樓層records: list) -> dict:
    """
    逐層容積查核。樓層records = [{啟用,樓層,樓板,計容積,梯廳,安全梯,陽台}, ...]

    §162（全部逐層）：
      梯廳超出 = Σ 各層 max(0, 梯廳 − 樓板 × 梯廳免計%)
      陽台超出 = Σ 各層 max(0, 陽台 − 樓板 × 陽台免計%)
      陽台1/8投影 = Σ 各層 max(0, 陽台 − 樓板 × 1/8)  ── 另一法則，並列審查
      安全梯   = 允建容積 × 15%（總量上限，踩坑6）
    只計入「啟用」的樓層（取消勾選 = 排除，如 B1F 防空避難室 §117，踩坑5）。
    """
    基地使用面積 = 參數["基地面積"] - 參數["人行廣場"]
    基準容積FA = 基地使用面積 * 參數["容積率"]
    允建容積 = 基準容積FA * (1 + 參數["獎勵率"]) + 參數["容積移轉"]

    梯廳基準 = 參數["梯廳免計基準"] / 100.0
    陽台基準 = 參數["陽台免計基準"] / 100.0

    啟用層 = [f for f in 樓層records if f.get("啟用", True)]

    def 安全取(f, k):
        try:
            return float(f.get(k) or 0)
        except (TypeError, ValueError):
            return 0.0

    梯廳超出 = sum(max(0.0, 安全取(f, "梯廳") - 安全取(f, "樓板") * 梯廳基準) for f in 啟用層)
    陽台超出 = sum(max(0.0, 安全取(f, "陽台") - 安全取(f, "樓板") * 陽台基準) for f in 啟用層)
    陽台1_8超出 = sum(max(0.0, 安全取(f, "陽台") - 安全取(f, "樓板") * 0.125) for f in 啟用層)
    安全梯總量 = sum(安全取(f, "安全梯") for f in 啟用層)
    陽台總量 = sum(安全取(f, "陽台") for f in 啟用層)
    陽台免計面積 = 陽台總量 - 陽台超出

    安全梯上限 = 允建容積 * 安全梯免計率

    # 計入容積（圖說）：優先採面積表彙總值（圖說為真）；否則由逐層計容積加總
    if 參數.get("面積表計入容積", 0) and 參數["面積表計入容積"] > 0:
        計入容積_圖說 = 參數["面積表計入容積"]
    else:
        計入容積_圖說 = sum(安全取(f, "計容積") for f in 啟用層)

    計入容積_修正後 = 計入容積_圖說 + 梯廳超出 + 陽台超出
    容積餘量 = 允建容積 - 計入容積_修正後

    return {
        "基準容積FA": 基準容積FA, "允建容積": 允建容積,
        "梯廳超出": 梯廳超出, "陽台超出": 陽台超出, "陽台1_8超出": 陽台1_8超出,
        "安全梯上限": 安全梯上限, "安全梯總量": 安全梯總量,
        "陽台總量": 陽台總量, "陽台免計面積": 陽台免計面積,
        "計入容積_圖說": 計入容積_圖說, "計入容積_修正後": 計入容積_修正後,
        "容積餘量": 容積餘量, "啟用層數": len(啟用層),
    }


def calc_坪效(允建容積, 陽台免計面積, 公設比, 外皮係數=1.01) -> dict:
    """
    銷售坪數 = [(允建容積 + 陽台免計) × 外皮係數 / 3.3058] / (1 − 公設比)
    銷坪比   = 銷售坪數 / 允建容積坪　（住宅正常範圍 1.58–1.68）
    """
    可賣面積 = (允建容積 + 陽台免計面積) * 外皮係數
    室內坪 = 可賣面積 / 平方米換坪
    銷售坪數 = 室內坪 / (1 - 公設比) if 公設比 < 1 else 0
    允建容積坪 = 允建容積 / 平方米換坪
    銷坪比 = 銷售坪數 / 允建容積坪 if 允建容積坪 else 0.0
    return {"室內坪": 室內坪, "銷售坪數": 銷售坪數, "允建容積坪": 允建容積坪, "銷坪比": 銷坪比}


def calc_開發評效(銷售坪數, 成本: dict) -> dict:
    """開發評效 = 總銷 ÷ 總成本（>5 優良 / 2–5 可行 / <2 偏低，永盛內部定義）。"""
    總銷售收入 = 銷售坪數 * 成本["售價"]
    營造成本 = 成本["營造單價"] * 成本["營造坪數"]
    管銷費 = 總銷售收入 * 成本["管銷費率"]
    建融利息 = (成本["土地成本"] + 營造成本) * 成本["建融成數"] * 成本["利率"] * 成本["年期"]
    稅費雜支 = 總銷售收入 * 成本["稅費率"]
    總開發成本 = 成本["土地成本"] + 營造成本 + 管銷費 + 建融利息 + 稅費雜支
    開發評效 = 總銷售收入 / 總開發成本 if 總開發成本 else 0.0
    return {"總銷售收入": 總銷售收入, "營造成本": 營造成本, "管銷費": 管銷費,
            "建融利息": 建融利息, "稅費雜支": 稅費雜支,
            "總開發成本": 總開發成本, "開發評效": 開發評效}


# ===========================================================================
# L6 都更全案投報層：總銷 → 共同負擔六大科目 → 分回 → 報酬率 → 敏感度
# 法源：都市更新權利變換實施辦法「費用負擔」六類（工程/權變/利息/稅捐/管理/其他）。
# 參數基準：安和段估價師級共負試算（2025 送審版）。純函式、無 Streamlit，可被測試引用。
# 對應建築師 Excel 的「坪效及獲利分析」分頁，供開啟舊表逐格對照。
# ===========================================================================
def calc_總銷(銷售坪數, 住宅單價, 店舖坪數=0.0, 店舖單價=0.0, 車位數=0, 車位單價=0.0) -> dict:
    """總銷 = 住宅 + 店舖 + 車位。住宅坪數 = 銷售坪數 − 店舖坪數（店舖由住宅坪切出）。"""
    住宅坪數 = max(0.0, 銷售坪數 - 店舖坪數)
    住宅銷售 = 住宅坪數 * 住宅單價
    店舖銷售 = 店舖坪數 * 店舖單價
    房地總銷 = 住宅銷售 + 店舖銷售
    車位銷售 = 車位數 * 車位單價
    總銷 = 房地總銷 + 車位銷售
    房地坪 = 住宅坪數 + 店舖坪數
    平均單價 = 房地總銷 / 房地坪 if 房地坪 else 0.0
    return {"住宅坪數": 住宅坪數, "住宅銷售": 住宅銷售, "店舖銷售": 店舖銷售,
            "房地總銷": 房地總銷, "車位銷售": 車位銷售, "總銷": 總銷, "平均單價": 平均單價}


def calc_共同負擔(總銷, 房地總銷, 營造坪數, p: dict) -> dict:
    """
    都更權利變換『共同負擔』六大科目（都市更新權利變換實施辦法 — 費用負擔）：
      A 工程費用 = 營造成本 + 設計監造 + 工程管理
      B 管維費用 = 申請容積獎勵後續管理維護（綠建築/無障礙/耐震/智慧）
      C 權變費用 = 估價/規劃/測量/鑑定（權變作業）+ 拆遷補償 + 租金補償(安置)
      D 貸款利息 = 土融利息 + 建融利息
      E 稅　　捐 = 營業稅 + 印花稅
      F 管理費用 = 實施者（全案管理）服務費
    p：成本率/單價字典（預設見「財務率預設」＋各案範本），全部從輸入推導、不寫死結果。
    費率基數（方法論 §4③）：代銷/稅 → 總銷；設計/工管 → 營造；管維 → 工程A。
    """
    營造成本 = p["營造單價"] * 營造坪數
    設計監造 = 營造成本 * p["設計監造率"]
    工程管理 = 營造成本 * p["工程管理率"]
    A工程費用 = 營造成本 + 設計監造 + 工程管理

    B管維費用 = A工程費用 * p["管維率"]

    權變作業 = 房地總銷 * p["權變作業率"]
    拆遷補償 = p["戶數"] * p["拆補每戶"]
    租金補償 = p["戶數"] * p["月租金每戶"] * p["安置月數"]
    C權變費用 = 權變作業 + 拆遷補償 + 租金補償

    # D 貸款利息：土融（全案管理預設土地成本=0）+ 建融（以工程費A為計算基礎）
    土融利息 = p["土地成本"] * p["土融成數"] * p["土融利率"] * p["土融年期"]
    建融利息 = A工程費用 * p["建融成數"] * p["建融利率"] * p["建融年期"] * p["現金流係數"]
    D貸款利息 = 土融利息 + 建融利息

    營業稅 = 房地總銷 * p["營業稅率"]
    印花稅 = 總銷 * p["印花稅率"]
    E稅捐 = 營業稅 + 印花稅

    F管理費用 = 總銷 * p["管理費率"]

    共同負擔 = A工程費用 + B管維費用 + C權變費用 + D貸款利息 + E稅捐 + F管理費用
    return {"A工程費用": A工程費用, "B管維費用": B管維費用, "C權變費用": C權變費用,
            "D貸款利息": D貸款利息, "E稅捐": E稅捐, "F管理費用": F管理費用,
            "共同負擔": 共同負擔,
            "_明細": {"營造成本": 營造成本, "設計監造": 設計監造, "工程管理": 工程管理,
                     "權變作業": 權變作業, "拆遷補償": 拆遷補償, "租金補償": 租金補償,
                     "土融利息": 土融利息, "建融利息": 建融利息,
                     "營業稅": 營業稅, "印花稅": 印花稅}}


def calc_分回(總銷, 共同負擔) -> dict:
    """
    全案管理／權利變換框架（地主分回近全部可建價值扣共負）：
      共同負擔比 = 共同負擔 ÷ 總銷
      地主分回價值 = 總銷 − 共同負擔
      報酬率（利潤/總成本） = 地主分回價值 ÷ 共同負擔
    """
    共負比 = 共同負擔 / 總銷 if 總銷 else 0.0
    地主分回價值 = 總銷 - 共同負擔
    地主分回比 = 地主分回價值 / 總銷 if 總銷 else 0.0
    報酬率 = 地主分回價值 / 共同負擔 if 共同負擔 else 0.0
    return {"共負比": 共負比, "地主分回價值": 地主分回價值,
            "地主分回比": 地主分回比, "報酬率": 報酬率}


def calc_投報全案(銷售坪數, 營造坪數, p: dict) -> dict:
    """串起 總銷 → 共負 → 分回，回傳一張都更全案投報總表（單位：萬元）。"""
    銷 = calc_總銷(銷售坪數, p["住宅單價"], p["店舖坪數"], p["店舖單價"], p["車位數"], p["車位單價"])
    負 = calc_共同負擔(銷["總銷"], 銷["房地總銷"], 營造坪數, p)
    分 = calc_分回(銷["總銷"], 負["共同負擔"])
    return {**銷, **負, **分}


def calc_投報敏感度(銷售坪數, 營造坪數, p: dict,
                售價變動=(-0.10, -0.05, 0.0, 0.05, 0.10),
                營造變動=(-0.10, -0.05, 0.0, 0.05, 0.10)) -> dict:
    """報酬率敏感度矩陣：列＝營造單價變動、欄＝住宅單價變動（其餘參數固定）。"""
    矩陣 = []
    for d營 in 營造變動:
        列 = []
        for d售 in 售價變動:
            pp = dict(p)
            pp["住宅單價"] = p["住宅單價"] * (1 + d售)
            pp["營造單價"] = p["營造單價"] * (1 + d營)
            列.append(calc_投報全案(銷售坪數, 營造坪數, pp)["報酬率"])
        矩陣.append(列)
    return {"矩陣": 矩陣, "售價變動": list(售價變動), "營造變動": list(營造變動)}


# ===========================================================================
# 範本（參數 + 逐層表格）：來源＝知識庫 + 中正段面積表查核報告
# ===========================================================================
# 都更全案投報——成本率預設（來源：安和段估價師級共負試算＋都市更新權利變換實施辦法六大科目）
# 各案範本可覆寫此處任一項；新案沿用此預設。比率為「萬元」制（單價萬/坪、金額萬元）。
財務率預設 = dict(
    設計監造率=0.05, 工程管理率=0.03, 管維率=0.01,
    權變作業率=0.015, 拆補每戶=90.0, 月租金每戶=2.0, 安置月數=42,
    # 土地融資：全案管理模式地主自持土地，土融利息通常為 0；合建/買賣案填入實際土地成本
    土地成本=0.0, 土融成數=0.70, 土融利率=0.03, 土融年期=4.0,
    建融成數=0.70, 建融利率=0.0325, 建融年期=3.0, 現金流係數=0.5,
    營業稅率=0.05, 印花稅率=0.001, 管理費率=0.05,
)

範本參數 = {
    # 容積欄位（基地面積…面積表計入容積）＝黃金測試鎖定值，勿改；其後為都更全案投報參數。
    "安和段（都市更新）": dict(案件名稱="安和段", 基地面積=1632.04, 人行廣場=0.0, 容積率=2.80,
                         獎勵率=0.50, 容積移轉=913.94, 公設比=0.34,
                         梯廳免計基準=5, 陽台免計基準=10, 面積表計入容積=0.0,
                         # 都更全案投報（新店行情；估價師事業計畫參數）
                         住宅單價=57.0, 店舖坪數=35.0, 店舖單價=80.0, 車位數=103, 車位單價=240.0,
                         營造單價=22.0, 戶數=111, 土融土地成本=0.0),
    "龜山半嶺段（危老）": dict(案件名稱="龜山半嶺段", 基地面積=971.62, 人行廣場=0.0, 容積率=3.20,
                         獎勵率=0.365, 容積移轉=0.0, 公設比=0.34,
                         梯廳免計基準=8, 陽台免計基準=10, 面積表計入容積=4243.80,
                         # 都更全案投報（桃園龜山行情；前期假設）
                         住宅單價=42.0, 店舖坪數=0.0, 店舖單價=0.0, 車位數=60, 車位單價=180.0,
                         營造單價=20.0, 戶數=40, 土融土地成本=0.0),
    "中正段（防災都更）": dict(案件名稱="中正段", 基地面積=983.00, 人行廣場=0.0, 容積率=2.25,
                         獎勵率=0.88407, 容積移轉=0.0, 公設比=0.33,
                         梯廳免計基準=8, 陽台免計基準=10, 面積表計入容積=4167.00,
                         # 都更全案投報（中正紀念堂第一排，4M 巷取保守；行情查證 2026-06）
                         住宅單價=130.0, 店舖坪數=66.0, 店舖單價=182.0, 車位數=49, 車位單價=250.0,
                         營造單價=24.0, 戶數=40, 土融土地成本=0.0),
}


def 範本樓層表(鍵: str) -> pd.DataFrame:
    rows = []
    if 鍵 == "中正段（防災都更）":
        rows.append(dict(啟用=True, 樓層="1F", 樓板=340.56, 計容積=0.0, 梯廳=29.89, 安全梯=41.67, 陽台=21.20))
        for i in range(2, 16):
            rows.append(dict(啟用=True, 樓層=f"{i}F", 樓板=338.51, 計容積=0.0, 梯廳=14.84, 安全梯=41.67, 陽台=35.93))
    elif 鍵 == "龜山半嶺段（危老）":
        for i in range(2, 16):
            rows.append(dict(啟用=True, 樓層=f"{i}F", 樓板=366.15, 計容積=0.0, 梯廳=31.61, 安全梯=0.0, 陽台=21.0))
    else:
        for i in range(1, 22):
            rows.append(dict(啟用=True, 樓層=f"{i}F", 樓板=0.0, 計容積=0.0, 梯廳=0.0, 安全梯=0.0, 陽台=0.0))
    return pd.DataFrame(rows, columns=樓層欄位)


def 解析上傳(file) -> pd.DataFrame:
    """讀 Excel/CSV，盡量對應到標準欄位。對不上的欄位留空，讓使用者在表中補。"""
    if file.name.lower().endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)
    別名 = {
        "樓層": ["樓層", "層", "floor", "Floor", "樓別"],
        "樓板": ["樓板", "樓地板", "樓板面積", "樓地板面積"],
        "計容積": ["計容積", "計入容積", "容積面積", "樓地板面積(容積)"],
        "梯廳": ["梯廳", "梯廳面積"],
        "安全梯": ["安全梯", "安全梯機電", "安全梯及機電", "機電"],
        "陽台": ["陽台", "陽臺", "陽台面積"],
    }
    out = pd.DataFrame()
    out["啟用"] = True
    cols = {str(c).strip(): c for c in df.columns}
    for 標準, 候選 in 別名.items():
        命中 = next((cols[a] for a in 候選 if a in cols), None)
        out[標準] = df[命中] if 命中 else (range(1, len(df) + 1) if 標準 == "樓層" else 0.0)
    out = out[["啟用", "樓層", "樓板", "計容積", "梯廳", "安全梯", "陽台"]]
    for c in ["樓板", "計容積", "梯廳", "安全梯", "陽台"]:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)
    out["啟用"] = True
    out["樓層"] = out["樓層"].astype(str)
    if len(out) == 0:
        raise ValueError("檔案沒有任何資料列")
    return out


def 產生報告(案件名稱, 參數, 容, 坪, 評, 營造坪數, 投=None) -> str:
    結論 = ("超出允建容積，需調整" if 容["容積餘量"] < 0
            else "規劃精準、合規" if 容["容積餘量"] <= 2 else "合規（容積未充分利用）")
    評效等級 = "優良" if 評["開發評效"] > 5 else "可行" if 評["開發評效"] >= 2 else "偏低"
    都更全案段 = ""
    if 投:
        都更全案段 = f"""
## 都更全案投報 ── 開發商（共同負擔六大科目）
| 項目 | 金額（萬） |
|------|-----------|
| 總銷（住宅+店舖+車位） | {投['總銷']:,.0f} |
| A 工程費用 | {投['A工程費用']:,.0f} |
| B 管維費用 | {投['B管維費用']:,.0f} |
| C 權變費用（含拆補/租金補償） | {投['C權變費用']:,.0f} |
| D 貸款利息 | {投['D貸款利息']:,.0f} |
| E 稅捐 | {投['E稅捐']:,.0f} |
| F 管理費用 | {投['F管理費用']:,.0f} |
| **共同負擔合計** | **{投['共同負擔']:,.0f}（共負比 {投['共負比']:.1%}）** |
| **地主分回價值** | **{投['地主分回價值']:,.0f}（分回 {投['地主分回比']:.1%}）** |
| 報酬率（利潤/總成本） | {投['報酬率']:.1%} |

> 共同負擔科目依《都市更新權利變換實施辦法》費用負擔分類；參數基準＝安和段送審試算。
"""
    return f"""# {案件名稱} 前期評估報告（RE-DCF-Tool v4.2）

## 結論：{結論}（容積餘量 {容['容積餘量']:.2f} m²）

## 容積帳 ── 建管合規性
| 項目 | 數值 |
|------|------|
| 基地使用面積 | {參數['基地面積'] - 參數['人行廣場']:.2f} m² |
| 基準容積 FA | {容['基準容積FA']:.2f} m² |
| 獎勵後容積 | {容['基準容積FA'] * (1 + 參數['獎勵率']):.2f} m² |
| + 容積移轉 | {參數['容積移轉']:.2f} m² |
| **允建容積** | **{容['允建容積']:.2f} m²** |
| 計入容積（圖說） | {容['計入容積_圖說']:.2f} m² |
| + 梯廳超出補計（{參數['梯廳免計基準']}%逐層） | {容['梯廳超出']:.2f} m² |
| + 陽台超出補計（{參數['陽台免計基準']}%逐層） | {容['陽台超出']:.2f} m² |
| **計入容積（修正後）** | **{容['計入容積_修正後']:.2f} m²** |
| **容積餘量** | **{容['容積餘量']:+.2f} m²** |

### 三項免計（建築師查核）
- 安全梯：{容['安全梯總量']:.2f} m² ／ 上限 {容['安全梯上限']:.2f} m²（允建×15%）
- 陽台超出（1/8 投影法）：{容['陽台1_8超出']:.2f} m²

## 坪效分析 ── 開發商
| 步驟 | 坪數 |
|------|------|
| 允建容積坪 | {坪['允建容積坪']:.2f} 坪 |
| 室內坪（含陽台免計×外皮） | {坪['室內坪']:.2f} 坪 |
| 銷售坪數（÷(1−公設比)） | {坪['銷售坪數']:.2f} 坪 |
| 銷坪比 | {坪['銷坪比']:.3f}（住宅正常 1.58–1.68） |

## 財務評效 ── 開發商
| 項目 | 金額（萬） |
|------|-----------|
| 總銷售收入 | {評['總銷售收入']:,.0f} |
| 土地成本 | {評['總開發成本'] - 評['營造成本'] - 評['管銷費'] - 評['建融利息'] - 評['稅費雜支']:,.0f} |
| 營造成本（{營造坪數:.0f} 坪） | {評['營造成本']:,.0f} |
| 管銷費 | {評['管銷費']:,.0f} |
| 建融利息 | {評['建融利息']:,.0f} |
| 稅費雜支 | {評['稅費雜支']:,.0f} |
| 總開發成本 | {評['總開發成本']:,.0f} |
| **開發評效** | **{評['開發評效']:.2f}（{評效等級}）** |
{都更全案段}
---
*RE-DCF-Tool v4.2｜圖說為真實依據｜逐層 §162 查核｜都更全案投報＝權利變換六大共負*
"""


# ===========================================================================
# 畫面層 — 輔助函式
# ===========================================================================
def 載入樓層表(df, 參數=None):
    st.session_state.floors_df = df.reset_index(drop=True)
    st.session_state.pop("floor_editor", None)
    if 參數:
        st.session_state.params = 參數
    st.rerun()


def _kpi(label, value, note="", note_color="#64748B", accent="#534AB7", bar=None):
    """HTML KPI 卡片 v2：頂部 accent 色條 + 大數字（等寬數字字體）+ 狀態注釋 + 迷你進度條。

    bar：0–1 之間的比例（如容積使用率），None = 不顯示進度條。
    accent：卡片頂條與進度條顏色，依狀態傳入紅/黃/綠/品牌紫。
    """
    bar_html = ""
    if bar is not None:
        p = max(0.0, min(1.0, bar))
        bar_html = (
            f'<div style="margin-top:10px;height:4px;border-radius:2px;background:#EEF0F7;'
            f'overflow:hidden"><div style="width:{p * 100:.0f}%;height:100%;border-radius:2px;'
            f'background:linear-gradient(90deg,{accent},{accent}99)"></div></div>')
    note_html = (f'<div style="font-size:12px;color:{note_color};margin-top:6px;'
                 f'line-height:1.45">{note}</div>') if note else ""
    return (
        f'<div class="kpi-card" style="position:relative;background:#fff;border:1px solid #E7E9F2;'
        f'border-radius:14px;padding:18px 20px 16px;height:100%;min-height:96px;overflow:hidden;'
        f'box-shadow:0 1px 2px rgba(15,23,42,0.04),0 8px 24px -18px rgba(15,23,42,0.25);">'
        f'<div style="position:absolute;top:0;left:0;right:0;height:3px;'
        f'background:linear-gradient(90deg,{accent},{accent}44)"></div>'
        f'<div style="font-size:10.5px;font-weight:700;color:#8A91A8;text-transform:uppercase;'
        f'letter-spacing:1px;margin-bottom:8px">{label}</div>'
        f'<div style="font-family:\'Space Grotesk\',\'Noto Sans TC\',sans-serif;font-size:24px;'
        f'font-weight:700;color:#0F172A;line-height:1.1;'
        f'font-variant-numeric:tabular-nums">{value}</div>'
        f'{note_html}{bar_html}</div>'
    )


def _banner(餘量):
    """HTML 結論橫幅 v2：圓形狀態圖示 + 主訊息 + 右側「L4 容積帳」層級膠囊。"""
    if 餘量 < 0:
        bg, lb, tc, icon = "#FEF2F2", "#DC2626", "#991B1B", "✕"
        msg = f"容積超出 {abs(餘量):.2f} m²，需調整設計"
    elif 餘量 <= 2:
        bg, lb, tc, icon = "#F0FDF4", "#16A34A", "#166534", "✓"
        msg = f"規劃精準、合規（容積餘量 {餘量:.2f} m²）"
    elif 餘量 <= 5:
        bg, lb, tc, icon = "#F0FDF4", "#16A34A", "#166534", "✓"
        msg = f"合規（容積餘量 {餘量:.2f} m²）"
    else:
        bg, lb, tc, icon = "#FFFBEB", "#D97706", "#92400E", "!"
        msg = f"合規但容積未充分利用（餘量 {餘量:.2f} m²）"
    return (
        f'<div style="background:{bg};border:1px solid {lb}22;'
        f'border-left:5px solid {lb};border-radius:12px;'
        f'padding:12px 18px;display:flex;align-items:center;gap:13px;margin:0.5rem 0 0.7rem;">'
        f'<span style="width:27px;height:27px;border-radius:50%;background:{lb};color:#fff;'
        f'display:inline-flex;align-items:center;justify-content:center;'
        f'font-size:14px;font-weight:800;flex-shrink:0">{icon}</span>'
        f'<span style="font-weight:700;color:{tc};font-size:14.5px">{msg}</span>'
        f'<span style="margin-left:auto;font-size:10.5px;font-weight:700;color:{lb};'
        f'border:1px solid {lb}55;border-radius:999px;padding:2px 11px;'
        f'letter-spacing:0.5px;white-space:nowrap">L4 容積帳</span>'
        f'</div>'
    )


def _section(title, sub=""):
    """區塊標題：品牌紫漸層側標 + 標題 + 灰色補充（取代散落的 st.markdown 粗體）。"""
    sub_html = (f'<span style="font-size:12px;color:#8A91A8;font-weight:400;'
                f'margin-left:10px">{sub}</span>') if sub else ""
    return (
        f'<div style="display:flex;align-items:center;margin:8px 0 8px">'
        f'<span style="width:4px;height:16px;border-radius:2px;'
        f'background:linear-gradient(180deg,#534AB7,#7C6FE0);margin-right:9px;'
        f'flex-shrink:0"></span>'
        f'<span style="font-size:14.5px;font-weight:700;color:#1E293B">{title}</span>'
        f'{sub_html}</div>'
    )


def _pipeline(容, 坪, 評效, 投):
    """L2→L6 計算流程帶：六層架構的即時數值串接成 pipeline chips，一眼看穿全案脈絡。"""
    免計超出 = 容["梯廳超出"] + 容["陽台超出"]
    steps = [
        ("L2", "允建容積", f"{容['允建容積']:,.0f} m²"),
        ("L3", "免計超出", f"{免計超出:.1f} m²"),
        ("L4", "容積餘量", f"{容['容積餘量']:+,.1f} m²"),
        ("L4.5", "銷售坪", f"{坪['銷售坪數']:,.0f} 坪"),
        ("L5", "開發評效", f"{評效:.2f}"),
        ("L6", "投報率", f"{投['報酬率']:.0%}"),
    ]
    箭頭 = '<span style="color:#C3C8DB;font-size:13px;margin:0 3px;flex-shrink:0">›</span>'
    chips = 箭頭.join(
        f'<span style="display:inline-flex;align-items:center;gap:7px;background:#fff;'
        f'border:1px solid #E7E9F2;border-radius:999px;padding:5px 13px 5px 6px;'
        f'white-space:nowrap;box-shadow:0 1px 2px rgba(15,23,42,0.04)">'
        f'<span style="background:linear-gradient(135deg,#534AB7,#7C6FE0);color:#fff;'
        f'font-size:10px;font-weight:700;border-radius:999px;padding:3px 8px;'
        f'letter-spacing:0.4px">{code}</span>'
        f'<span style="font-size:11.5px;color:#8A91A8">{name}</span>'
        f'<span style="font-size:12.5px;font-weight:700;color:#0F172A;'
        f'font-variant-numeric:tabular-nums">{val}</span>'
        f'</span>'
        for code, name, val in steps)
    return (f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:3px;'
            f'margin:2px 0 4px">{chips}</div>')


def _fig_layout(title="", height=380, margin_top=None):
    """統一 Plotly 佈局：字體/底色/留白/懸停，確保全站圖表風格一致。"""
    mt = margin_top if margin_top is not None else (50 if title else 20)
    base = dict(
        font=dict(family="Noto Sans TC, Space Grotesk, Arial, sans-serif",
                  size=12, color="#374151"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(248,250,252,0.6)",
        height=height,
        margin=dict(t=mt, b=20, l=10, r=10),
        hoverlabel=dict(bgcolor="white", bordercolor="#E7E9F2", font_size=12),
    )
    if title:
        base["title"] = dict(
            text=title,
            font=dict(size=14, color="#1E293B",
                      family="Noto Sans TC, Space Grotesk, Arial, sans-serif"),
            x=0, xanchor="left",
        )
    return base


# ===========================================================================
# 畫面層 — 主程式
# ===========================================================================
def main():
    st.set_page_config(page_title="RE-DCF-Tool 前期評估", page_icon="🏗️", layout="wide")

    # ── 全域 CSS ─────────────────────────────────────────────────────────────
    st.markdown("""
<style>
/* ── 字體（v4.2：Noto Sans TC 中文 + Space Grotesk 數字/英文）────── */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&family=Space+Grotesk:wght@500;600;700&display=swap');

html, body, [class*="st-"], .stMarkdown {
    font-family: 'Noto Sans TC', 'Space Grotesk', -apple-system, 'Segoe UI', sans-serif !important;
}

/* ── 全域：淡靛放射漸層底 ─────────────── */
.stApp {
    background:
        radial-gradient(ellipse 60% 40% at 85% -5%, rgba(83,74,183,0.08), transparent),
        radial-gradient(ellipse 50% 30% at 0% 100%, rgba(124,111,224,0.05), transparent),
        #F7F8FC;
}
.main .block-container { padding: 0.75rem 1.5rem 1rem !important; max-width: 1400px; }
#MainMenu, footer { visibility: hidden; }

/* ── KPI 卡 hover 浮起 ─────────────────── */
.kpi-card { transition: transform 0.18s ease, box-shadow 0.18s ease; }
.kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 2px 4px rgba(15,23,42,0.05), 0 14px 32px -16px rgba(83,74,183,0.35) !important;
}

/* ── Tab：白底膠囊條 + 漸層選中 ───────── */
.stTabs [data-baseweb="tab-list"] {
    background: #fff; border-radius: 13px;
    padding: 4px; gap: 2px; border: 1px solid #E7E9F2;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 9px; padding: 7px 20px;
    color: #6B7280; font-size: 13px; font-weight: 500;
    transition: color 0.15s ease;
}
.stTabs [data-baseweb="tab"]:hover { color: #534AB7; }
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg,#534AB7 0%,#6B62D0 100%) !important;
    color: #fff !important; font-weight: 600;
    box-shadow: 0 2px 10px rgba(83,74,183,0.32);
}

/* ── Expander ────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #E7E9F2 !important;
    border-radius: 11px !important;
    overflow: hidden; margin-bottom: 4px;
    background: #fff;
}
[data-testid="stExpander"] summary {
    background: #FBFBFE !important; padding: 10px 14px !important;
}
[data-testid="stExpander"] summary p {
    font-weight: 600 !important; color: #374151 !important; font-size: 13.5px !important;
}

/* ── Divider ─────────────────────────── */
hr { border: none !important; border-top: 1px solid #E7E9F2 !important; margin: 1rem 0 !important; }

/* ── Metric（Tab 內備援樣式）──────────── */
[data-testid="metric-container"] {
    background: #fff; border: 1px solid #E7E9F2; border-radius: 13px;
    padding: 15px 18px !important;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04), 0 8px 24px -18px rgba(15,23,42,0.22);
}
[data-testid="metric-container"] label {
    font-size: 10.5px !important; font-weight: 700 !important;
    color: #8A91A8 !important; text-transform: uppercase; letter-spacing: 0.8px;
}
[data-testid="stMetricValue"] {
    font-family: 'Space Grotesk', 'Noto Sans TC', sans-serif !important;
    font-size: 22px !important; font-weight: 700 !important; color: #0F172A !important;
    font-variant-numeric: tabular-nums;
}
[data-testid="stMetricDelta"] { font-size: 12px !important; }

/* ── DataFrame：表頭品牌淡紫 + 等寬數字 ── */
[data-testid="stDataFrameResizable"] th {
    background: #F4F3FB !important; color: #43398F !important;
    font-weight: 700 !important; border-bottom: 2px solid #E3E0F5 !important;
    font-size: 12px !important;
}
[data-testid="stDataFrameResizable"] td {
    font-size: 13px !important; color: #374151 !important;
    font-variant-numeric: tabular-nums;
}

/* ── Button ──────────────────────────── */
.stButton > button {
    border-radius: 9px !important; font-weight: 500 !important;
    border: 1px solid #D6D9E4 !important; color: #374151 !important; background: #fff !important;
    transition: all 0.15s ease;
}
.stButton > button:hover {
    background: #F6F5FC !important; border-color: #534AB7 !important; color: #534AB7 !important;
    box-shadow: 0 2px 8px rgba(83,74,183,0.15);
}

/* ── Caption ─────────────────────────── */
[data-testid="stCaptionContainer"] { color: #8A91A8 !important; font-size: 12px !important; }

/* ── Sidebar：白底 + 右緣陰影分界 ──────── */
section[data-testid="stSidebar"] {
    background: #fff;
    box-shadow: 1px 0 0 #E7E9F2, 4px 0 18px -12px rgba(15,23,42,0.12);
}
section[data-testid="stSidebar"] > div:first-child { padding-top: 0.75rem; }
section[data-testid="stSidebar"] [data-testid="stExpander"] { border-color: #ECEEF5 !important; }
</style>
""", unsafe_allow_html=True)

    # ── 初始化 ────────────────────────────────────────────────────────────────
    if "floors_df" not in st.session_state:
        st.session_state.floors_df = 範本樓層表("中正段（防災都更）")
    if "params" not in st.session_state:
        st.session_state.params = dict(範本參數["中正段（防災都更）"])

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 📋 案件設定")
        範本選擇 = st.selectbox("範本", list(範本參數.keys()), label_visibility="collapsed")
        if st.button("📂 載入此範本（含逐層表）", use_container_width=True):
            載入樓層表(範本樓層表(範本選擇), dict(範本參數[範本選擇]))

        P = st.session_state.params
        P["案件名稱"] = st.text_input("案件名稱", P.get("案件名稱", "新案"))
        st.divider()

        with st.expander("🏗️ 基地與容積", expanded=True):
            c1, c2 = st.columns(2)
            P["基地面積"] = c1.number_input(
                "基地面積 m²", value=float(P.get("基地面積", 1000.0)), step=1.0,
                help="使照面積（踩坑3：謄本面積會高估免計上限，掩蓋超容）")
            P["人行廣場"] = c2.number_input(
                "廣場捐地 m²", value=float(P.get("人行廣場", 0.0)), step=1.0)
            P["容積率"] = c1.number_input(
                "容積率", value=float(P.get("容積率", 2.25)), step=0.01, format="%.4f",
                help="225% → 輸入 2.25，住宅區通常 0.8–3.6")
            P["獎勵率"] = c2.number_input(
                "獎勵率", value=float(P.get("獎勵率", 0.50)), step=0.001, format="%.5f",
                help="防災都更最高 +88.4%（0.884），需與建築師面積表核對拆項")
            P["容積移轉"] = c1.number_input(
                "容積移轉 m²", value=float(P.get("容積移轉", 0.0)), step=1.0)
            P["面積表計入容積"] = c2.number_input(
                "面積表計入 m²", value=float(P.get("面積表計入容積", 0.0)), step=1.0,
                help="填建築師面積表彙總值（圖說為真）；0 = 由逐層加總")

        with st.expander("📋 免計基準"):
            c1, c2 = st.columns(2)
            P["梯廳免計基準"] = c1.selectbox(
                "梯廳免計 %（§162-1）", [5, 8],
                index=[5, 8].index(int(P.get("梯廳免計基準", 8))),
                help="逐層：各層樓板×%（非 FA 總量）；待建築師確認適用 5% 或 8%")
            P["陽台免計基準"] = c2.selectbox(
                "陽台免計 %（§162）", [10, 15],
                index=[10, 15].index(int(P.get("陽台免計基準", 10))),
                help="§162 一般為 10%；§162-3 特殊情況 15%，待建築師確認")
            P["公設比"] = c1.number_input(
                "公設比", value=float(P.get("公設比", 0.33)), step=0.01, format="%.2f",
                help="坪效 Tab 有反推公設比驗算（方法論 §6 第一項）")
            外皮係數 = c2.number_input("外皮係數", value=1.01, step=0.01, format="%.2f")

        with st.expander("💰 成本快篩（L5，開發評效用）"):
            c1, c2 = st.columns(2)
            售價 = c1.number_input("售價（萬/坪）", value=80.0, step=1.0)
            土地成本 = c2.number_input("土地成本（萬）", value=50000.0, step=1000.0)
            營造單價 = c1.number_input(
                "營造單價（萬/坪）", value=18.0, step=0.5,
                help="× 下方基準坪數 = 總營造成本；L6 另有獨立的都更營造單價")
            管銷費率 = c2.number_input("管銷費率", value=0.05, step=0.01, format="%.2f")
            建融成數 = c1.number_input("建融成數", value=0.50, step=0.05, format="%.2f")
            利率 = c2.number_input("利率（年）", value=0.03, step=0.005, format="%.3f")
            年期 = c1.number_input("建融年期", value=2.0, step=0.5)
            稅費率 = c2.number_input("稅費率", value=0.03, step=0.01, format="%.2f")
            營造坪基準 = st.radio(
                "營造坪數基準",
                ["銷售坪數（前期保守估算）", "允建容積坪（實務成本估算）"],
                help="誤用銷售坪會高估成本約 60%（方法論 §6 第六項）；實務依允建坪報估")

        with st.expander("🏘️ 都更全案投報（L6，總銷·共負·分回）"):
            st.caption("對應建築師 Excel「坪效及獲利分析」。費率基數：代銷/稅→總銷，設計/工管→營造，管維→工程A。")
            c1, c2 = st.columns(2)
            P["住宅單價"] = c1.number_input(
                "住宅單價（萬/坪）", value=float(P.get("住宅單價", 80.0)), step=1.0)
            P["店舖坪數"] = c2.number_input(
                "1F 店舖坪數", value=float(P.get("店舖坪數", 0.0)), step=1.0)
            P["店舖單價"] = c1.number_input(
                "店舖單價（萬/坪）", value=float(P.get("店舖單價", 0.0)), step=1.0,
                help="查核：店舖單價 ≈ 住宅 × 1.4（方法論 §4②）")
            P["車位數"] = c2.number_input("車位數", value=int(P.get("車位數", 0)), step=1)
            P["車位單價"] = c1.number_input(
                "車位單價（萬/位）", value=float(P.get("車位單價", 220.0)), step=10.0)
            P["營造單價"] = c2.number_input(
                "都更營造單價（萬/坪）", value=float(P.get("營造單價", 22.0)), step=0.5,
                help="含工程費A；基礎→結構→裝修各期，施工困難基地上調")
            P["戶數"] = c1.number_input("戶數", value=int(P.get("戶數", 0)), step=1)
            P["總營建坪"] = c2.number_input(
                "總營建坪", value=float(P.get("總營建坪", 0.0)), step=10.0,
                help="填圖說總樓地板坪（非銷售坪！方法論 §6 第六項）；0 = 允建坪×2 粗估")
            # L6 土融利息新增：全案管理模式通常填 0，合建/買賣案填入土地取得成本
            P["土融土地成本"] = c1.number_input(
                "土融土地成本（萬）", value=float(P.get("土融土地成本", 0.0)), step=1000.0,
                help="全案管理（地主自持）填 0；合建/買賣案填入土地取得成本，納入 D 土融利息計算")
            with st.expander("⚙️ 進階成本率（預設＝安和段送審值）"):
                cc1, cc2 = st.columns(2)
                P["管理費率"] = cc1.number_input(
                    "全案管理費率（基數：總銷）",
                    value=float(P.get("管理費率", 財務率預設["管理費率"])), step=0.005, format="%.3f")
                P["設計監造率"] = cc2.number_input(
                    "設計監造率（基數：營造費）",
                    value=float(P.get("設計監造率", 財務率預設["設計監造率"])), step=0.005, format="%.3f")
                P["工程管理率"] = cc1.number_input(
                    "工程管理率（基數：營造費）",
                    value=float(P.get("工程管理率", 財務率預設["工程管理率"])), step=0.005, format="%.3f")
                P["管維率"] = cc2.number_input(
                    "容獎管維率（基數：工程費A）",
                    value=float(P.get("管維率", 財務率預設["管維率"])), step=0.005, format="%.3f")
                P["權變作業率"] = cc1.number_input(
                    "權變作業率（基數：房地銷）",
                    value=float(P.get("權變作業率", 財務率預設["權變作業率"])), step=0.005, format="%.3f")
                P["營業稅率"] = cc2.number_input(
                    "營業稅率（基數：房地銷）",
                    value=float(P.get("營業稅率", 財務率預設["營業稅率"])), step=0.005, format="%.3f",
                    help="正式權變共負須 5%；前期試算有時簡化為 1%，注意版本別")
                P["拆補每戶"] = cc1.number_input(
                    "拆補每戶（萬）",
                    value=float(P.get("拆補每戶", 財務率預設["拆補每戶"])), step=5.0)
                P["月租金每戶"] = cc2.number_input(
                    "月租金每戶（萬）",
                    value=float(P.get("月租金每戶", 財務率預設["月租金每戶"])), step=0.5)
                P["安置月數"] = st.number_input(
                    "安置月數", value=int(P.get("安置月數", 財務率預設["安置月數"])), step=1)

    # ── Hero 標題橫幅（v4.2：深靛藍「藍圖網格」背景，建築製圖意象）───────────────
    st.markdown(f"""
<div style="position:relative;overflow:hidden;
background:linear-gradient(118deg,#1E1B4B 0%,#3B3486 52%,#534AB7 100%);
border-radius:16px;padding:1.25rem 1.6rem;margin-bottom:1rem;
box-shadow:0 6px 28px -8px rgba(30,27,75,0.45);">
  <div style="position:absolute;inset:0;
  background-image:linear-gradient(rgba(255,255,255,0.055) 1px,transparent 1px),
  linear-gradient(90deg,rgba(255,255,255,0.055) 1px,transparent 1px);
  background-size:26px 26px;pointer-events:none;"></div>
  <div style="position:absolute;right:-30px;top:-46px;width:190px;height:190px;
  border:1.5px dashed rgba(255,255,255,0.14);border-radius:50%;pointer-events:none;"></div>
  <div style="position:relative;display:flex;align-items:center;
  justify-content:space-between;gap:16px;flex-wrap:wrap;">
    <div>
      <div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">
        <span style="font-family:'Space Grotesk','Noto Sans TC',sans-serif;font-size:21px;
        font-weight:700;color:#fff;letter-spacing:-0.3px">🏗️ RE-DCF-Tool</span>
        <span style="font-size:12px;color:rgba(255,255,255,0.55);
        letter-spacing:2.5px;font-weight:600">PRE-DEVELOPMENT&nbsp;ANALYSIS</span>
      </div>
      <div style="font-size:13px;color:rgba(255,255,255,0.85);margin-top:5px;font-weight:400">
        都更／危老前期評估　<span style="color:rgba(255,255,255,0.4)">｜</span>
        　<span style="font-weight:700;color:#fff">{P['案件名稱']}</span>
      </div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <span style="background:rgba(255,255,255,0.13);border:1px solid rgba(255,255,255,0.28);
      backdrop-filter:blur(4px);border-radius:999px;padding:4px 14px;
      color:rgba(255,255,255,0.95);font-size:11.5px;font-weight:600;white-space:nowrap;">
        v4.2</span>
      <span style="background:rgba(255,255,255,0.13);border:1px solid rgba(255,255,255,0.28);
      backdrop-filter:blur(4px);border-radius:999px;padding:4px 14px;
      color:rgba(255,255,255,0.95);font-size:11.5px;font-weight:600;white-space:nowrap;">
        逐層 §162</span>
      <span style="background:rgba(255,255,255,0.13);border:1px solid rgba(255,255,255,0.28);
      backdrop-filter:blur(4px);border-radius:999px;padding:4px 14px;
      color:rgba(255,255,255,0.95);font-size:11.5px;font-weight:600;white-space:nowrap;">
        圖說為真</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── 上傳工具（折疊）──────────────────────────────────────────────────────
    with st.expander("📤 上傳面積表 / 下載空白範本", expanded=False):
        cimp1, cimp2 = st.columns([3, 2])
        with cimp1:
            上傳 = st.file_uploader(
                "匯入 Excel/CSV 面積表", type=["xlsx", "xls", "csv"],
                help="欄位：樓層/樓板/計容積/梯廳/安全梯/陽台，對不上的留空。")
            if 上傳 is not None and st.button("✅ 套用上傳的面積表"):
                try:
                    df_up = 解析上傳(上傳)
                    if df_up["計容積"].sum() > 0:
                        st.session_state.params["面積表計入容積"] = 0.0
                    載入樓層表(df_up)
                except Exception as e:
                    st.error(f"解析失敗：{e}")
        with cimp2:
            空白 = pd.DataFrame([dict(啟用=True, 樓層="1F", 樓板=0, 計容積=0, 梯廳=0, 安全梯=0, 陽台=0)])
            st.download_button("⬇️ 下載空白匯入範本(CSV)",
                               空白.to_csv(index=False).encode("utf-8-sig"),
                               "面積表匯入範本.csv", "text/csv", use_container_width=True)
            st.caption("取消「計入」勾選 = 排除該層（B1F 防空避難室 §117，踩坑5）")

    # ── 逐層明細（主畫面常駐）────────────────────────────────────────────────
    st.markdown(_section("逐層明細", "圖說為真實依據　·　取消「計入」勾選＝排除該層"),
                unsafe_allow_html=True)
    edited = st.data_editor(
        st.session_state.floors_df, key="floor_editor", num_rows="dynamic",
        use_container_width=True, height=240,
        column_config={
            "啟用": st.column_config.CheckboxColumn("計入"),
            "樓層": st.column_config.TextColumn("樓層"),
            "樓板": st.column_config.NumberColumn("樓板 m²", format="%.2f"),
            "計容積": st.column_config.NumberColumn("計容積 m²", format="%.2f"),
            "梯廳": st.column_config.NumberColumn("梯廳 m²", format="%.2f"),
            "安全梯": st.column_config.NumberColumn("安全梯 m²", format="%.2f"),
            "陽台": st.column_config.NumberColumn("陽台 m²", format="%.2f"),
        })
    樓層records = edited.to_dict("records")

    # ── 計算 ──────────────────────────────────────────────────────────────────
    容 = calc_容積查核(P, 樓層records)
    坪 = calc_坪效(容["允建容積"], 容["陽台免計面積"], P["公設比"], 外皮係數)

    _營造坪數 = (坪["允建容積坪"] if 營造坪基準 == "允建容積坪（實務成本估算）"
               else 坪["銷售坪數"])

    成本 = dict(售價=售價, 土地成本=土地成本, 營造單價=營造單價, 營造坪數=_營造坪數,
              管銷費率=管銷費率, 建融成數=建融成數, 利率=利率, 年期=年期, 稅費率=稅費率)
    評 = calc_開發評效(坪["銷售坪數"], 成本)

    # L6 投報：財務率預設 ← 各案覆寫；新增 土融土地成本 (v4.1)
    投報參數 = {**財務率預設,
              **{k: P[k] for k in ("住宅單價", "店舖坪數", "店舖單價", "車位數", "車位單價",
                                   "營造單價", "設計監造率", "工程管理率", "管維率", "權變作業率",
                                   "拆補每戶", "月租金每戶", "安置月數", "管理費率", "營業稅率", "戶數")
                 if k in P},
              "土地成本": float(P.get("土融土地成本", 0.0))}
    _總營建坪 = float(P.get("總營建坪", 0.0) or 0.0) or (坪["允建容積坪"] * 2.0)
    投 = calc_投報全案(坪["銷售坪數"], _總營建坪, 投報參數)

    # ── L2→L6 計算流程帶 + 結論橫幅（v4.2）────────────────────────────────────
    餘量 = 容["容積餘量"]
    免計超出 = 容["梯廳超出"] + 容["陽台超出"]
    評效 = 評["開發評效"]
    評效等級 = "優良" if 評效 > 5 else "可行" if 評效 >= 2 else "偏低"
    st.markdown(_pipeline(容, 坪, 評效, 投), unsafe_allow_html=True)
    st.markdown(_banner(餘量), unsafe_allow_html=True)

    # ── 4 欄 KPI（HTML 卡片：accent 色條 + 迷你進度條） ──────────────────────
    k = st.columns(4)
    with k[0]:
        使用率 = 容["計入容積_修正後"] / 容["允建容積"] if 容["允建容積"] else 0
        st.markdown(_kpi(
            "允建容積 m²",
            f"{容['允建容積']:,.0f}",
            f"FA {容['基準容積FA']:,.0f} × (1+{P['獎勵率']:.1%}) + 移轉 {P['容積移轉']:.0f}",
            accent="#534AB7"
        ), unsafe_allow_html=True)
    with k[1]:
        nc = "#DC2626" if 餘量 < 0 else ("#059669" if 餘量 <= 5 else "#D97706")
        st.markdown(_kpi(
            "計入容積 / 餘量",
            f"{容['計入容積_修正後']:,.0f}",
            f"餘量 {餘量:+.1f} m²（使用率 {使用率:.1%}）", nc,
            accent=nc, bar=使用率
        ), unsafe_allow_html=True)
    with k[2]:
        nc = "#059669" if 1.58 <= 坪["銷坪比"] <= 1.68 else "#D97706"
        st.markdown(_kpi(
            "銷售坪數 / 銷坪比",
            f"{坪['銷售坪數']:,.0f} 坪",
            f"銷坪比 {坪['銷坪比']:.3f}（正常 1.58–1.68）", nc,
            accent="#0D9488", bar=(坪["銷坪比"] - 1.40) / 0.40
        ), unsafe_allow_html=True)
    with k[3]:
        nc = "#059669" if 投["報酬率"] >= 1.5 else ("#D97706" if 投["報酬率"] >= 1.0 else "#DC2626")
        st.markdown(_kpi(
            "投報率 / 共負比",
            f"{投['報酬率']:.1%}",
            f"共負比 {投['共負比']:.1%}", nc,
            accent=nc, bar=min(投["報酬率"] / 2.0, 1.0)
        ), unsafe_allow_html=True)

    st.markdown("")

    # ── 5 個 Tab ──────────────────────────────────────────────────────────────
    t1, t2, t3, t4, t5 = st.tabs([
        "① 容積查核",
        "② 坪效分析",
        "③ 財務評效",
        "④ 都更全案投報",
        "⑤ 報告匯出",
    ])

    # ── Tab ①：容積查核（容積帳 + 逐層免計） ────────────────────────────────
    with t1:
        col_g, col_t = st.columns([1, 1])
        with col_g:
            上限 = max(容["允建容積"] * 1.1, 容["計入容積_修正後"])
            g = go.Figure(go.Indicator(
                mode="gauge+number+delta", value=容["計入容積_修正後"],
                delta={"reference": 容["允建容積"], "increasing": {"color": "#DC2626"}},
                title={"text": "計入容積(修正後) vs 允建容積 m²",
                       "font": {"size": 14, "color": "#1E293B",
                                "family": "Noto Sans TC, Space Grotesk, Arial"}},
                gauge={"axis": {"range": [0, 上限],
                                "tickfont": {"size": 11, "color": "#6B7280"}},
                       "bar": {"color": "#534AB7"},
                       "threshold": {"line": {"color": "#DC2626", "width": 3},
                                     "value": 容["允建容積"]},
                       "steps": [{"range": [0, 容["允建容積"]], "color": "#EAF3DC"},
                                 {"range": [容["允建容積"], 上限], "color": "#FEE2E2"}]}))
            g.update_layout(**_fig_layout(height=300, margin_top=60))
            st.plotly_chart(g, use_container_width=True)
            來源 = (f"面積表彙總值 {P['面積表計入容積']:.0f}" if P.get("面積表計入容積", 0) > 0
                    else "逐層計容積加總")
            st.caption(f"紅線＝允建容積上限　｜　計入容積(圖說)來源：**{來源}** = {容['計入容積_圖說']:.0f} m²")

        with col_t:
            st.markdown(_section("容積帳明細", "L2 容積 → L4 容積帳"), unsafe_allow_html=True)
            基地使用 = P["基地面積"] - P["人行廣場"]
            st.dataframe(pd.DataFrame([
                {"項目": "基地使用面積", "m²": f"{基地使用:.2f}",
                 "說明": f"{P['基地面積']:.0f} − 廣場 {P['人行廣場']:.0f}"},
                {"項目": "基準容積 FA", "m²": f"{容['基準容積FA']:.2f}",
                 "說明": f"× 容積率 {P['容積率']:.4f}"},
                {"項目": "獎勵後容積", "m²": f"{容['基準容積FA'] * (1 + P['獎勵率']):.2f}",
                 "說明": f"× (1 + {P['獎勵率']:.3f})"},
                {"項目": "+ 容積移轉", "m²": f"{P['容積移轉']:.2f}", "說明": "直接加計"},
                {"項目": "🔵 允建容積", "m²": f"{容['允建容積']:.2f}", "說明": ""},
                {"項目": "計入容積（圖說）", "m²": f"{容['計入容積_圖說']:.2f}", "說明": 來源},
                {"項目": "+ 梯廳超出補計", "m²": f"{容['梯廳超出']:.2f}",
                 "說明": f"逐層 {P['梯廳免計基準']}% 法"},
                {"項目": "+ 陽台超出補計", "m²": f"{容['陽台超出']:.2f}",
                 "說明": f"逐層 {P['陽台免計基準']}% 法"},
                {"項目": "🔴 計入容積（修正）", "m²": f"{容['計入容積_修正後']:.2f}", "說明": ""},
                {"項目": "容積餘量", "m²": f"{容['容積餘量']:+.2f}",
                 "說明": "正值=合規，負值=超出"},
            ]), use_container_width=True, hide_index=True)

        st.divider()

        st.markdown(_section(
            "逐層免計查核",
            f"梯廳基準 {P['梯廳免計基準']}%　·　陽台基準 {P['陽台免計基準']}% 或 1/8 投影　·　L3"),
            unsafe_allow_html=True)
        梯比 = P["梯廳免計基準"] / 100
        陽比 = P["陽台免計基準"] / 100
        審 = []
        for f in 樓層records:
            if not f.get("啟用", True):
                continue
            樓板 = float(f.get("樓板") or 0)
            梯超 = max(0, float(f.get("梯廳") or 0) - 樓板 * 梯比)
            陽超 = max(0, float(f.get("陽台") or 0) - 樓板 * 陽比)
            陽1_8超 = max(0, float(f.get("陽台") or 0) - 樓板 * 0.125)
            審.append({
                "樓層": f.get("樓層"),
                "梯廳超出": round(梯超, 2),
                f"陽台超出({P['陽台免計基準']}%)": round(陽超, 2),
                "陽台超出(1/8)": round(陽1_8超, 2),
                "狀態": "❌ 超出" if (梯超 + 陽超) > 0.01 else "✅",
            })
        st.dataframe(pd.DataFrame(審), use_container_width=True, hide_index=True)

        c = st.columns(4)
        c[0].metric("梯廳超出合計", f"{容['梯廳超出']:.2f} m²")
        c[1].metric(f"陽台超出({P['陽台免計基準']}%)", f"{容['陽台超出']:.2f} m²")
        c[2].metric("陽台超出(1/8)", f"{容['陽台1_8超出']:.2f} m²")
        安差 = 容["安全梯總量"] - 容["安全梯上限"]
        c[3].metric("安全梯 總/上限", f"{容['安全梯總量']:.1f}/{容['安全梯上限']:.1f}",
                    f"{安差:+.1f}", delta_color="inverse")

        if 免計超出 > 0:
            st.warning("⚠️ 超出部分依 §162 必須補計入容積（踩坑2）。逐層法為正解，勿用 FA×% 總量法。")
        if 容["陽台1_8超出"] > 0:
            st.info(f"💡 陽台 1/8 投影法超出 {容['陽台1_8超出']:.2f} m²（與 {P['陽台免計基準']}% 法併列審查）")
        if 容["安全梯總量"] > 容["安全梯上限"]:
            st.error(
                f"❌ 安全梯總量 {容['安全梯總量']:.1f} m² 超過上限 {容['安全梯上限']:.1f} m²"
                f"（允建×15%），超出 {abs(安差):.1f} m²")

    # ── Tab ②：坪效分析 ──────────────────────────────────────────────────────
    with t2:
        c = st.columns(4)
        c[0].metric("允建容積坪", f"{坪['允建容積坪']:.1f} 坪")
        c[1].metric("室內坪（含陽台免計）", f"{坪['室內坪']:.1f} 坪")
        c[2].metric("銷售坪數", f"{坪['銷售坪數']:.1f} 坪")
        c[3].metric("銷坪比", f"{坪['銷坪比']:.3f}")

        st.markdown(_section("銷售坪數推導步驟", "L4.5 銷售坪效"), unsafe_allow_html=True)
        陽台免計坪 = 容["陽台免計面積"] / 平方米換坪
        st.dataframe(pd.DataFrame([
            {"步驟": "① 允建容積", "m²": f"{容['允建容積']:.2f}", "坪": f"{坪['允建容積坪']:.2f}"},
            {"步驟": "② + 陽台免計面積", "m²": f"+{容['陽台免計面積']:.2f}", "坪": f"+{陽台免計坪:.2f}"},
            {"步驟": "③ × 外皮係數", "m²": f"× {外皮係數:.2f}", "坪": f"× {外皮係數:.2f}"},
            {"步驟": "④ = 可賣面積（室內）",
             "m²": f"{(容['允建容積']+容['陽台免計面積'])*外皮係數:.2f}",
             "坪": f"{坪['室內坪']:.2f}"},
            {"步驟": f"⑤ ÷ (1 − 公設比 {P['公設比']:.0%})", "m²": "—", "坪": f"÷ {1-P['公設比']:.2f}"},
            {"步驟": "⑥ = 銷售坪數", "m²": "—", "坪": f"{坪['銷售坪數']:.2f}"},
        ]), use_container_width=True, hide_index=True)

        陽台率 = 容["陽台免計面積"] / 容["允建容積"] if 容["允建容積"] else 0
        st.caption(
            f"陽台免計率 {陽台率:.1%}　｜　"
            f"快算公式：(1+陽台率)/(1−公設比) = {(1+陽台率)/(1-P['公設比']):.3f}")

        if 坪["銷坪比"] == 0:
            st.info("資料不足，無法計算銷坪比。")
        elif 1.58 <= 坪["銷坪比"] <= 1.68:
            st.success(f"✅ 銷坪比 {坪['銷坪比']:.3f} 落在住宅正常區間 1.58–1.68")
        else:
            st.warning(f"⚠️ 銷坪比 {坪['銷坪比']:.3f} 超出住宅正常區間 1.58–1.68，請確認陽台或公設比。")

        # ── 公設比反推驗算（方法論 §6 第一項：公設比顯示值≠公式實際值）────────
        st.markdown(_section("公設比反推驗算", "方法論 §6 查核項"), unsafe_allow_html=True)
        反推公設比 = 1 - 坪["室內坪"] / 坪["銷售坪數"] if 坪["銷售坪數"] > 0 else 0
        diff = abs(反推公設比 - P["公設比"])
        st.caption(
            f"反推公設比 = 1 − 室內坪 / 銷售坪 = 1 − {坪['室內坪']:.2f} / {坪['銷售坪數']:.2f}"
            f" = **{反推公設比:.2%}**　（設定值：{P['公設比']:.2%}，差 {diff:.2%}）")
        if diff > 0.005:
            st.warning(
                f"⚠️ 設定公設比 {P['公設比']:.2%} 與反推 {反推公設比:.2%} 差距 {diff:.2%}。"
                "Excel 常見問題：儲存格顯示值 ≠ 公式實際值，建議回頭確認公設比來源。")

    # ── Tab ③：財務評效 ──────────────────────────────────────────────────────
    with t3:
        c = st.columns(3)
        c[0].metric("總銷售收入", f"{評['總銷售收入']:,.0f} 萬")
        c[1].metric("總開發成本", f"{評['總開發成本']:,.0f} 萬")
        c[2].metric("開發評效", f"{評效:.2f}（{評效等級}）")

        if 營造坪基準 == "銷售坪數（前期保守估算）":
            st.info(
                f"💡 營造成本以**銷售坪數 {坪['銷售坪數']:.0f} 坪**計算（保守估算，成本偏高）。"
                f"實務上建築師依允建容積坪（{坪['允建容積坪']:.0f} 坪）報估，"
                f"差異比 {坪['銷坪比']:.2f}×。如需比較，請切換側邊欄基準。")

        瀑布 = go.Figure(go.Waterfall(
            orientation="v",
            measure=["relative", "relative", "relative", "relative", "relative", "total"],
            x=["土地", "營造", "管銷", "建融利息", "稅費雜支", "總成本"],
            y=[土地成本, 評["營造成本"], 評["管銷費"], 評["建融利息"], 評["稅費雜支"], 評["總開發成本"]],
            texttemplate="%{y:,.0f}", textposition="outside",
            connector={"line": {"color": "#D6D9E4"}},
            increasing={"marker": {"color": "#534AB7"}},
            decreasing={"marker": {"color": "#F43F5E"}},
            totals={"marker": {"color": "#1E1B4B"}}))
        瀑布.update_layout(**_fig_layout(
            title=f"開發成本拆解（萬）｜營造基準：{_營造坪數:.0f} 坪 × {營造單價:.1f} 萬/坪",
            height=380))
        st.plotly_chart(瀑布, use_container_width=True)

        st.markdown(_section("開發評效敏感度", "公設比 × 售價"), unsafe_allow_html=True)
        公設清單 = [round(P["公設比"] - 0.02 + 0.01 * i, 2) for i in range(5)]
        售價清單 = [round(售價 - 10 + 5 * i, 0) for i in range(5)]
        矩陣 = [[round(calc_開發評效(
            calc_坪效(容["允建容積"], 容["陽台免計面積"], cc, 外皮係數)["銷售坪數"],
            dict(成本,
                 營造坪數=(calc_坪效(容["允建容積"], 容["陽台免計面積"], cc, 外皮係數)["允建容積坪"]
                           if 營造坪基準 == "允建容積坪（實務成本估算）"
                           else calc_坪效(容["允建容積"], 容["陽台免計面積"], cc, 外皮係數)["銷售坪數"]),
                 售價=p)
        )["開發評效"], 2) for p in 售價清單] for cc in 公設清單]
        heat = go.Figure(go.Heatmap(
            z=矩陣, x=[f"{p:.0f}萬" for p in 售價清單],
            y=[f"公設{c:.0%}" for c in 公設清單],
            colorscale="RdYlGn", text=矩陣, texttemplate="%{text}",
            colorbar=dict(thickness=12, len=0.8)))
        heat.update_layout(**_fig_layout(height=300))
        st.plotly_chart(heat, use_container_width=True)

    # ── Tab ④：都更全案投報 ───────────────────────────────────────────────────
    with t4:
        st.caption(
            f"總銷 → 共同負擔六大科目（都市更新權利變換實施辦法）→ 地主分回。"
            f"　營造坪採 **{_總營建坪:.0f} 坪**"
            f"（{'圖說總樓地板' if float(P.get('總營建坪', 0) or 0) > 0 else '允建坪×2 估算'}）。")
        m = st.columns(5)
        m[0].metric("總銷", f"{投['總銷']:,.0f} 萬")
        m[1].metric("共同負擔", f"{投['共同負擔']:,.0f} 萬")
        m[2].metric("共負比", f"{投['共負比']:.1%}", help="共同負擔 ÷ 總銷")
        m[3].metric("地主分回", f"{投['地主分回比']:.1%}", f"{投['地主分回價值']:,.0f} 萬")
        m[4].metric("報酬率", f"{投['報酬率']:.1%}", help="利潤 ÷ 總成本")

        cc1, cc2 = st.columns([1, 1])
        with cc1:
            st.markdown(_section("總銷分析", "住宅＋店舖＋車位"), unsafe_allow_html=True)
            st.dataframe(pd.DataFrame([
                {"項目": "住宅", "量": f"{投['住宅坪數']:.0f} 坪",
                 "單價": f"{P['住宅單價']:.0f}", "金額(萬)": f"{投['住宅銷售']:,.0f}"},
                {"項目": "店舖", "量": f"{P['店舖坪數']:.0f} 坪",
                 "單價": f"{P['店舖單價']:.0f}", "金額(萬)": f"{投['店舖銷售']:,.0f}"},
                {"項目": "車位", "量": f"{P['車位數']:.0f} 位",
                 "單價": f"{P['車位單價']:.0f}", "金額(萬)": f"{投['車位銷售']:,.0f}"},
                {"項目": "總銷", "量": "",
                 "單價": f"均{投['平均單價']:.1f}", "金額(萬)": f"{投['總銷']:,.0f}"},
            ]), use_container_width=True, hide_index=True)
        with cc2:
            st.markdown(_section("共同負擔六大科目", "權利變換實施辦法"), unsafe_allow_html=True)
            st.dataframe(pd.DataFrame([
                {"科目": "A 工程費用", "金額(萬)": f"{投['A工程費用']:,.0f}",
                 "占總銷": f"{投['A工程費用']/投['總銷']:.1%}"},
                {"科目": "B 管維費用", "金額(萬)": f"{投['B管維費用']:,.0f}",
                 "占總銷": f"{投['B管維費用']/投['總銷']:.1%}"},
                {"科目": "C 權變費用", "金額(萬)": f"{投['C權變費用']:,.0f}",
                 "占總銷": f"{投['C權變費用']/投['總銷']:.1%}"},
                {"科目": "D 貸款利息", "金額(萬)": f"{投['D貸款利息']:,.0f}",
                 "占總銷": f"{投['D貸款利息']/投['總銷']:.1%}"},
                {"科目": "E 稅捐", "金額(萬)": f"{投['E稅捐']:,.0f}",
                 "占總銷": f"{投['E稅捐']/投['總銷']:.1%}"},
                {"科目": "F 管理費用", "金額(萬)": f"{投['F管理費用']:,.0f}",
                 "占總銷": f"{投['F管理費用']/投['總銷']:.1%}"},
                {"科目": "🔴 共同負擔", "金額(萬)": f"{投['共同負擔']:,.0f}",
                 "占總銷": f"{投['共負比']:.1%}"},
            ]), use_container_width=True, hide_index=True)

        wf = go.Figure(go.Waterfall(
            orientation="v", measure=["relative"] * 6 + ["total"],
            x=["A工程", "B管維", "C權變", "D利息", "E稅捐", "F管理", "共同負擔"],
            y=[投["A工程費用"], 投["B管維費用"], 投["C權變費用"], 投["D貸款利息"],
               投["E稅捐"], 投["F管理費用"], 投["共同負擔"]],
            texttemplate="%{y:,.0f}", textposition="outside",
            connector={"line": {"color": "#D6D9E4"}},
            increasing={"marker": {"color": "#534AB7"}},
            totals={"marker": {"color": "#1E1B4B"}}))
        wf.update_layout(**_fig_layout(title="共同負擔六大科目拆解（萬）", height=360))
        st.plotly_chart(wf, use_container_width=True)

        分回每戶 = 投["地主分回價值"] / P["戶數"] if P.get("戶數") else 0
        st.info(
            f"地主分回 **{投['地主分回價值']:,.0f} 萬**（占總銷 {投['地主分回比']:.1%}）"
            + (f"，{int(P['戶數'])} 戶平均 **{分回每戶:,.0f} 萬/戶**（依各戶權值估價，僅示意）"
               if P.get("戶數") else "")
            + "。共負比 > 65% 時留意地主接受度。")

        # ── 費率基數一覽（方法論 §4③：看清各費率的基數）────────────────────────
        with st.expander("📋 費率基數一覽（方法論 §4③ 查核項）", expanded=False):
            st.caption("各費率計算基數不同，誤用基數會造成嚴重誤算（方法論 §4③、§6）。")
            明細 = 投["_明細"]
            st.dataframe(pd.DataFrame([
                {"費率名稱": "設計監造", "費率基數": "A中的營造費",
                 "基數(萬)": f"{明細['營造成本']:,.0f}",
                 "費率": f"{P.get('設計監造率', 0.05):.1%}",
                 "金額(萬)": f"{明細['設計監造']:,.0f}"},
                {"費率名稱": "工程管理", "費率基數": "A中的營造費",
                 "基數(萬)": f"{明細['營造成本']:,.0f}",
                 "費率": f"{P.get('工程管理率', 0.03):.1%}",
                 "金額(萬)": f"{明細['工程管理']:,.0f}"},
                {"費率名稱": "B 容獎管維", "費率基數": "A 工程費用合計",
                 "基數(萬)": f"{投['A工程費用']:,.0f}",
                 "費率": f"{P.get('管維率', 0.01):.1%}",
                 "金額(萬)": f"{投['B管維費用']:,.0f}"},
                {"費率名稱": "C 權變作業", "費率基數": "房地總銷",
                 "基數(萬)": f"{投['房地總銷']:,.0f}",
                 "費率": f"{P.get('權變作業率', 0.015):.1%}",
                 "金額(萬)": f"{明細['權變作業']:,.0f}"},
                {"費率名稱": "E 營業稅", "費率基數": "房地總銷",
                 "基數(萬)": f"{投['房地總銷']:,.0f}",
                 "費率": f"{P.get('營業稅率', 0.05):.1%}",
                 "金額(萬)": f"{明細['營業稅']:,.0f}"},
                {"費率名稱": "E 印花稅", "費率基數": "總銷",
                 "基數(萬)": f"{投['總銷']:,.0f}",
                 "費率": f"{財務率預設['印花稅率']:.1%}",
                 "金額(萬)": f"{明細['印花稅']:,.0f}"},
                {"費率名稱": "F 全案管理費", "費率基數": "總銷",
                 "基數(萬)": f"{投['總銷']:,.0f}",
                 "費率": f"{P.get('管理費率', 0.05):.1%}",
                 "金額(萬)": f"{投['F管理費用']:,.0f}"},
            ]), use_container_width=True, hide_index=True)
            if P.get("土融土地成本", 0) > 0:
                st.caption(
                    f"土融利息（D）：土地成本 {P['土融土地成本']:,.0f}萬 × "
                    f"成數 {財務率預設['土融成數']:.0%} × 利率 {財務率預設['土融利率']:.1%} × "
                    f"年期 {財務率預設['土融年期']:.0f}年 = {明細['土融利息']:,.0f} 萬")

        st.markdown(_section("報酬率敏感度", "住宅售價 × 營造單價"), unsafe_allow_html=True)
        sens = calc_投報敏感度(坪["銷售坪數"], _總營建坪, 投報參數)
        z = [[round(v * 100, 0) for v in 列] for 列 in sens["矩陣"]]
        heat = go.Figure(go.Heatmap(
            z=z,
            x=[f"售{P['住宅單價'] * (1 + d):.0f}" for d in sens["售價變動"]],
            y=[f"營{P['營造單價'] * (1 + d):.1f}" for d in sens["營造變動"]],
            colorscale="RdYlGn", text=z, texttemplate="%{text}%",
            colorbar=dict(thickness=12, len=0.8)))
        heat.update_layout(**_fig_layout(height=320))
        st.plotly_chart(heat, use_container_width=True)
        st.caption("數值＝報酬率(%)。售價↑報酬↑、營造↑報酬↓。共負比 > 65%（分回 < 35%）時留意地主接受度。")

    # ── Tab ⑤：報告匯出 ──────────────────────────────────────────────────────
    with t5:
        報告 = 產生報告(P["案件名稱"], P, 容, 坪, 評, _營造坪數, 投)
        st.markdown(報告)
        st.download_button("⬇️ 下載報告(Markdown)", 報告.encode("utf-8"),
                           f"{P['案件名稱']}_前期評估報告.md", "text/markdown")
        st.download_button("⬇️ 下載逐層表(CSV)",
                           edited.to_csv(index=False).encode("utf-8-sig"),
                           f"{P['案件名稱']}_逐層表.csv", "text/csv")

    # ── 頁尾資訊列（v4.2）─────────────────────────────────────────────────────
    st.markdown(
        '<div style="margin-top:2rem;padding:13px 2px 4px;border-top:1px solid #E7E9F2;'
        'display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;'
        'font-size:11.5px;color:#9AA1B5">'
        '<span>🏗️ <b style="color:#6B7280">RE-DCF-Tool v4.2</b>　永盛開發建設 前期評估</span>'
        '<span>圖說為真　·　§162 逐層查核　·　都市更新權利變換實施辦法</span>'
        '</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
