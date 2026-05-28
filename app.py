# -*- coding: utf-8 -*-
"""
RE-DCF-Tool — 都更/危老前期評估工具（v3 逐層表格版）
====================================================
永盛開發建設「建築坪效與前期評估」Excel 財務模型的程式化版本。
執行：streamlit run app.py

v3 重大更新（依建築師/都更財務團隊回饋）：
  1.【準確】以「完整逐層表格」取代單一標準層——每層實填，可勾選排除（B1F 防空避難，踩坑5）。
  2.【即時】支援 Excel/CSV 一鍵匯入面積表，自動填表。
  3.【UIUX】結論橫幅 + KPI 卡 + 容積量表 + 逐層著色表 + 一頁報告匯出。

承襲 v2 的正確核心：陽台/梯廳超出皆「逐層」判斷（每層 vs 該層樓板×免計%），
已對齊安和/龜山/中正三案圖說。
"""

import io
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
      陽台1/8投影 = Σ 各層 max(0, 陽台 − 樓板 × 1/8)  ＿ 另一法則
      安全梯   = 允建容積 × 15%（總量，踩坑6）
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
    陽台1_8超出 = sum(max(0.0, 安全取(f, "陽台") - 安全取(f, "樓板") * 0.125) for f in 啟用層)  # 1/8 = 0.125
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
    """銷坪比 = (允建容積 + 陽台免計) / (1−公設比) / 允建容積（知識庫 §1 權威公式）。"""
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
# 範本（參數 + 逐層表格）：來源＝知識庫 + 中正段面積表查核報告
# ===========================================================================
範本參數 = {
    "安和段（都市更新）": dict(案件名稱="安和段", 基地面積=1632.04, 人行廣場=0.0, 容積率=2.80,
                         獎勵率=0.50, 容積移轉=913.94, 公設比=0.34,
                         梯廳免計基準=5, 陽台免計基準=10, 面積表計入容積=0.0),
    "龜山半嶺段（危老）": dict(案件名稱="龜山半嶺段", 基地面積=971.62, 人行廣場=0.0, 容積率=3.20,
                         獎勵率=0.365, 容積移轉=0.0, 公設比=0.34,
                         梯廳免計基準=8, 陽台免計基準=10, 面積表計入容積=4243.80),
    "中正段（防災都更）": dict(案件名稱="中正段", 基地面積=983.00, 人行廣場=0.0, 容積率=2.25,
                         獎勵率=0.88407, 容積移轉=0.0, 公設比=0.33,
                         梯廳免計基準=8, 陽台免計基準=10, 面積表計入容積=4167.00),
}


def 範本樓層表(鍵: str) -> pd.DataFrame:
    rows = []
    if 鍵 == "中正段（防災都更）":
        rows.append(dict(啟用=True, 樓層="1F", 樓板=340.56, 計容積=0.0, 梯廳=29.89, 安全梯=41.67, 陽台=21.20))
        for i in range(2, 16):  # 2F–15F
            rows.append(dict(啟用=True, 樓層=f"{i}F", 樓板=338.51, 計容積=0.0, 梯廳=14.84, 安全梯=41.67, 陽台=35.93))
    elif 鍵 == "龜山半嶺段（危老）":
        for i in range(2, 16):  # 2F–15F（14 層）
            rows.append(dict(啟用=True, 樓層=f"{i}F", 樓板=366.15, 計容積=0.0, 梯廳=31.61, 安全梯=0.0, 陽台=21.0))
    else:  # 安和段：無逐層資料，給空白模板
        for i in range(1, 22):  # 1F–21F
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


def 產生報告(案件名稱, 參數, 容, 坪, 評) -> str:
    結論 = ("超出允建容積，需調整" if 容["容積餘量"] < 0
            else "規劃精準、合規" if 容["容積餘量"] <= 2 else "合規（容積未充分利用）")
    return f"""# {案件名稱} 前期評估報告（RE-DCF-Tool v3）

## 結論：{結論}（容積餘量 {容['容積餘量']:.2f} m²）

## 容積帳
- 基準容積 FA：{容['基準容積FA']:.2f} m²
- 允建容積：{容['允建容積']:.2f} m²
- 計入容積（圖說）：{容['計入容積_圖說']:.2f} m²
- 梯廳超出（逐層 {參數['梯廳免計基準']}%）：{容['梯廳超出']:.2f} m²
- 陽台超出（逐層 {參數['陽台免計基準']}%）：{容['陽台超出']:.2f} m²
- 陽台超出（1/8 投影法）：{容['陽台1_8超出']:.2f} m²
- 安全梯：{容['安全梯總量']:.2f} / 上限 {容['安全梯上限']:.2f} m²
- 計入容積（修正後）：{容['計入容積_修正後']:.2f} m²
- **容積餘量：{容['容積餘量']:.2f} m²**

## 銷售坪效
- 銷售坪數：{坪['銷售坪數']:.2f} 坪
- 銷坪比：{坪['銷坪比']:.3f}（正常 1.58–1.68）

## 開發評效
- 總銷售收入：{評['總銷售收入']:,.0f} 萬
- 總開發成本：{評['總開發成本']:,.0f} 萬
- 開發評效：{評['開發評效']:.2f}（>5 優良 / 2–5 可行 / <2 偏低）

---
*RE-DCF-Tool v3｜圖說為真實依據｜逐層 §162 查核*
"""


# ===========================================================================
# 畫面層
# ===========================================================================
def 載入樓層表(df, 參數=None):
    st.session_state.floors_df = df.reset_index(drop=True)
    st.session_state.pop("floor_editor", None)
    if 參數:
        st.session_state.params = 參數
    st.rerun()


def main():
    st.set_page_config(page_title="RE-DCF-Tool 前期評估", page_icon="🏗️", layout="wide")
    st.markdown("## 🏗️ RE-DCF-Tool — 都更/危老前期評估工具　<span style='font-size:14px;color:#888'>v3 逐層表格版</span>",
                unsafe_allow_html=True)

    # 部署連結 & 說明
    部署url = "https://re-dcf-tool-ovmbnrh45ew2khaklhhn3t.streamlit.app"
    col1, col2 = st.columns([3, 1])
    with col2:
        st.markdown(f"<span style='font-size:12px;color:#666'>📱 [分享連結]({部署url})</span>",
                    unsafe_allow_html=True)

    if "floors_df" not in st.session_state:
        st.session_state.floors_df = 範本樓層表("中正段（防災都更）")
    if "params" not in st.session_state:
        st.session_state.params = dict(範本參數["中正段（防災都更）"])

    # ---------------- Sidebar：案件參數 + 成本 ----------------
    with st.sidebar:
        st.header("ℹ️ 工具資訊")
        st.markdown(f"""
**RE-DCF-Tool v3**
永盛開發建設內部工具

📍 **部署位置**：
🔗 [點此分享給同事]({部署url})

**本機執行**：
```
streamlit run app.py
```

**黃金測試**：
```
python test_golden.py
```

📚 **相關資源**：
- [GitHub Repo](https://github.com/jeremy0819/RE-DCF-Tool)
- 【踩坑5】B1F 防空避難室排除 §117
- 【踩坑6】安全梯總量 ≤ 允建×15%
- 【踩坑2】梯廳/陽台超出逐層補計
        """)
        st.divider()
        st.header("📥 案件參數")
        範本選擇 = st.selectbox("範本", list(範本參數.keys()))
        if st.button("📂 載入此範本（含逐層表）", use_container_width=True):
            載入樓層表(範本樓層表(範本選擇), dict(範本參數[範本選擇]))

        P = st.session_state.params
        P["案件名稱"] = st.text_input("案件名稱", P.get("案件名稱", "新案"))
        P["基地面積"] = st.number_input("基地面積（使照，非謄本）m²", value=float(P.get("基地面積", 1000.0)),
                                      step=1.0, help="踩坑3：用謄本面積會高估免計上限、掩蓋超出。")
        P["人行廣場"] = st.number_input("人行廣場/捐地 m²", value=float(P.get("人行廣場", 0.0)), step=1.0)
        P["容積率"] = st.number_input("容積率（225%→2.25）", value=float(P.get("容積率", 2.25)), step=0.01, format="%.4f")
        P["獎勵率"] = st.number_input("獎勵率（防災都更如 0.884）", value=float(P.get("獎勵率", 0.50)), step=0.001, format="%.5f")
        P["容積移轉"] = st.number_input("容積移轉 m²", value=float(P.get("容積移轉", 0.0)), step=1.0)
        P["面積表計入容積"] = st.number_input("面積表「計入容積合計」m²（0=由逐層加總）",
                                          value=float(P.get("面積表計入容積", 0.0)), step=1.0,
                                          help="圖說為真：直接採建築師面積表彙總值，工具只負責補計超出。")
        st.markdown("**免計基準（§162，逐層；待建築師確認）**")
        P["梯廳免計基準"] = st.selectbox("梯廳免計 %", [5, 8], index=[5, 8].index(int(P.get("梯廳免計基準", 8))))
        P["陽台免計基準"] = st.selectbox("陽台免計 %", [10, 15], index=[10, 15].index(int(P.get("陽台免計基準", 10))))
        st.markdown("**控制變數**")
        P["公設比"] = st.number_input("公設比（先鎖定）", value=float(P.get("公設比", 0.33)), step=0.01, format="%.2f")
        外皮係數 = st.number_input("外皮係數", value=1.01, step=0.01, format="%.2f")

        st.markdown("---")
        st.markdown("**💰 成本假設（可編輯）**")
        售價 = st.number_input("售價（萬/坪）", value=80.0, step=1.0)
        土地成本 = st.number_input("土地成本（萬）", value=50000.0, step=1000.0)
        營造單價 = st.number_input("營造單價（萬/坪）", value=18.0, step=0.5)
        管銷費率 = st.number_input("管銷費率", value=0.05, step=0.01, format="%.2f")
        建融成數 = st.number_input("建融成數", value=0.50, step=0.05, format="%.2f")
        利率 = st.number_input("利率（年）", value=0.03, step=0.005, format="%.3f")
        年期 = st.number_input("建融年期", value=2.0, step=0.5)
        稅費率 = st.number_input("稅費雜支率", value=0.03, step=0.01, format="%.2f")

    # ---------------- 逐層表格編輯（即時更新） ----------------
    st.markdown("### 🏢 逐層明細（圖說為真實依據）")
    cimp1, cimp2 = st.columns([3, 2])
    with cimp1:
        上傳 = st.file_uploader("📤 匯入面積表（Excel/CSV）→ 自動填表", type=["xlsx", "xls", "csv"],
                              help="欄位可含：樓層/樓板/計容積/梯廳/安全梯/陽台。對不上的留空，可在下表手動補。")
        if 上傳 is not None and st.button("✅ 套用上傳的面積表"):
            try:
                df_up = 解析上傳(上傳)
                # 修正(盲審#3)：上傳含真實逐層計容積時，改用逐層加總，避免被範本舊彙總值覆蓋
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
        st.caption("取消「啟用」勾選＝排除該層（如 B1F 防空避難室 §117，踩坑5）")

    edited = st.data_editor(
        st.session_state.floors_df, key="floor_editor", num_rows="dynamic",
        use_container_width=True, height=300,
        column_config={
            "啟用": st.column_config.CheckboxColumn("計入", help="取消＝排除該層"),
            "樓層": st.column_config.TextColumn("樓層"),
            "樓板": st.column_config.NumberColumn("樓板 m²", format="%.2f"),
            "計容積": st.column_config.NumberColumn("計容積 m²", format="%.2f"),
            "梯廳": st.column_config.NumberColumn("梯廳 m²", format="%.2f"),
            "安全梯": st.column_config.NumberColumn("安全梯 m²", format="%.2f"),
            "陽台": st.column_config.NumberColumn("陽台 m²", format="%.2f"),
        })
    樓層records = edited.to_dict("records")

    # ---------------- 計算 ----------------
    容 = calc_容積查核(P, 樓層records)
    坪 = calc_坪效(容["允建容積"], 容["陽台免計面積"], P["公設比"], 外皮係數)
    成本 = dict(售價=售價, 土地成本=土地成本, 營造單價=營造單價, 營造坪數=坪["銷售坪數"],
              管銷費率=管銷費率, 建融成數=建融成數, 利率=利率, 年期=年期, 稅費率=稅費率)
    評 = calc_開發評效(坪["銷售坪數"], 成本)

    # ---------------- 結論橫幅 ----------------
    餘量 = 容["容積餘量"]
    if 餘量 < 0:
        st.error(f"### ❌ 結論：超出允建容積 {abs(餘量):.2f} m²，需調整設計")
    elif 餘量 <= 2:
        st.success(f"### ✅ 結論：規劃精準、合規（容積餘量 {餘量:.2f} m²）")
    elif 餘量 <= 5:
        st.success(f"### ✅ 結論：合規（容積餘量 {餘量:.2f} m²）")
    else:
        st.warning(f"### ⚠️ 結論：合規但容積未充分利用（餘量 {餘量:.2f} m²）")

    # ---------------- KPI 卡 ----------------
    k = st.columns(5)
    k[0].metric("允建容積", f"{容['允建容積']:.0f}", help="FA×(1+獎勵)+容移")
    k[1].metric("計入容積(修正)", f"{容['計入容積_修正後']:.0f}", f"{餘量:+.1f}")
    k[2].metric("梯廳/陽台超出", f"{容['梯廳超出']+容['陽台超出']:.1f}", help=f"梯廳{容['梯廳超出']:.1f}+陽台{容['陽台超出']:.1f}")
    k[3].metric("銷售坪數", f"{坪['銷售坪數']:.0f} 坪")
    k[4].metric("開發評效", f"{評['開發評效']:.2f}")

    # ---------------- Tabs ----------------
    t1, t2, t3, t4, t5 = st.tabs(["① 容積量表", "② 三項免計", "③ 銷售坪效", "④ 開發評效＋敏感度", "⑤ 報告匯出"])

    with t1:
        上限 = max(容["允建容積"] * 1.1, 容["計入容積_修正後"])
        g = go.Figure(go.Indicator(
            mode="gauge+number+delta", value=容["計入容積_修正後"],
            delta={"reference": 容["允建容積"], "increasing": {"color": "#E24B4A"}},
            title={"text": "計入容積(修正後) vs 允建容積"},
            gauge={"axis": {"range": [0, 上限]},
                   "bar": {"color": "#534AB7"},
                   "threshold": {"line": {"color": "#E24B4A", "width": 4}, "value": 容["允建容積"]},
                   "steps": [{"range": [0, 容["允建容積"]], "color": "#EAF3DC"},
                             {"range": [容["允建容積"], 上限], "color": "#FCEAEA"}]}))
        g.update_layout(height=320, margin=dict(t=60, b=10))
        st.plotly_chart(g, use_container_width=True)
        來源 = (f"面積表彙總值 {P['面積表計入容積']:.0f}" if P.get("面積表計入容積", 0) > 0
                else "逐層計容積加總")
        st.caption(f"紅線＝允建容積上限 {容['允建容積']:.0f} m²，紫柱超過＝超出需調整。"
                   f"　計入容積(圖說)來源：**{來源}** = {容['計入容積_圖說']:.0f} m²")

    with t2:
        st.markdown(f"**逐層查核（梯廳基準 {P['梯廳免計基準']}%、陽台基準 {P['陽台免計基準']}% 或 1/8 投影）**")
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
            審.append({"樓層": f.get("樓層"), "梯廳超出": round(梯超, 2),
                       "陽台超出(10%)": round(陽超, 2), "陽台超出(1/8)": round(陽1_8超, 2),
                       "狀態": "❌ 超出" if (梯超 + 陽超) > 0.01 else "✅"})
        審df = pd.DataFrame(審)
        st.dataframe(審df, use_container_width=True, hide_index=True)
        c = st.columns(4)
        c[0].metric("梯廳超出合計", f"{容['梯廳超出']:.2f} m²")
        c[1].metric("陽台超出(10%)", f"{容['陽台超出']:.2f} m²")
        c[2].metric("陽台超出(1/8)", f"{容['陽台1_8超出']:.2f} m²")
        安差 = 容["安全梯總量"] - 容["安全梯上限"]
        c[3].metric("安全梯", f"{容['安全梯總量']:.1f}/{容['安全梯上限']:.1f}",
                    f"{安差:+.1f}", delta_color="inverse")
        if 容["梯廳超出"] + 容["陽台超出"] > 0:
            st.warning("⚠️ 超出部分依 §162 必須補計入容積（踩坑2）。逐層法為正解，勿用 FA×% 總量法。")
        if 容["陽台1_8超出"] > 0:
            st.info(f"💡 陽台 1/8 投影法超出 {容['陽台1_8超出']:.2f} m²（與 {P['陽台免計基準']}% 法併列審查）")

    with t3:
        c = st.columns(3)
        c[0].metric("室內坪", f"{坪['室內坪']:.1f}")
        c[1].metric("銷售坪數", f"{坪['銷售坪數']:.1f}")
        c[2].metric("銷坪比", f"{坪['銷坪比']:.3f}")
        陽台率 = 容["陽台免計面積"] / 容["允建容積"] if 容["允建容積"] else 0
        st.caption(f"陽台免計率 {陽台率:.1%}｜快算 (1+陽台率)/(1−公設比) ≈ {(1+陽台率)/(1-P['公設比']):.3f}")
        if 坪["銷坪比"] == 0:
            st.info("資料不足，無法計算銷坪比。")
        elif 1.58 <= 坪["銷坪比"] <= 1.68:
            st.success(f"✅ 銷坪比 {坪['銷坪比']:.3f} 落在住宅正常區間 1.58–1.68")
        else:
            st.warning(f"⚠️ 銷坪比 {坪['銷坪比']:.3f} 超出 1.58–1.68，請檢查陽台或公設比。")

    with t4:
        c = st.columns(3)
        c[0].metric("總銷售收入", f"{評['總銷售收入']:,.0f} 萬")
        c[1].metric("總開發成本", f"{評['總開發成本']:,.0f} 萬")
        c[2].metric("開發評效", f"{評['開發評效']:.2f}")
        瀑布 = go.Figure(go.Waterfall(
            orientation="v", measure=["relative", "relative", "relative", "relative", "total"],
            x=["土地", "營造", "管銷", "建融+稅費", "總成本"],
            y=[土地成本, 評["營造成本"], 評["管銷費"], 評["建融利息"] + 評["稅費雜支"], 評["總開發成本"]],
            textposition="outside"))
        瀑布.update_layout(title="開發成本拆解（萬元）", height=360)
        st.plotly_chart(瀑布, use_container_width=True)
        # 敏感度
        公設清單 = [round(P["公設比"] - 0.02 + 0.01 * i, 2) for i in range(5)]
        售價清單 = [round(售價 - 10 + 5 * i, 0) for i in range(5)]
        矩陣 = [[round(calc_開發評效(
            calc_坪效(容["允建容積"], 容["陽台免計面積"], c, 外皮係數)["銷售坪數"],
            dict(成本, 營造坪數=calc_坪效(容["允建容積"], 容["陽台免計面積"], c, 外皮係數)["銷售坪數"], 售價=p)
        )["開發評效"], 2) for p in 售價清單] for c in 公設清單]
        heat = go.Figure(go.Heatmap(z=矩陣, x=[f"{p:.0f}萬" for p in 售價清單],
                                    y=[f"公設{c:.0%}" for c in 公設清單],
                                    colorscale="RdYlGn", text=矩陣, texttemplate="%{text}"))
        heat.update_layout(title="開發評效敏感度（公設比×售價）", height=340)
        st.plotly_chart(heat, use_container_width=True)

    with t5:
        報告 = 產生報告(P["案件名稱"], P, 容, 坪, 評)
        st.markdown(報告)
        st.download_button("⬇️ 下載報告(Markdown)", 報告.encode("utf-8"),
                           f"{P['案件名稱']}_前期評估報告.md", "text/markdown")
        st.download_button("⬇️ 下載逐層表(CSV)",
                           edited.to_csv(index=False).encode("utf-8-sig"),
                           f"{P['案件名稱']}_逐層表.csv", "text/csv")


if __name__ == "__main__":
    main()
