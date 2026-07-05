# -*- coding: utf-8 -*-
"""
RE-DCF-Tool — 都更/危老前期評估工具（v4.9 Core 合約 v1.1：warnings/owners/版本追溯）
==============================================================
永盛開發建設「建築坪效與前期評估」Excel 財務模型的程式化版本。
本檔僅為 UI（Demo）；所有計算公式來自 core/ package（Urban Renewal Core Engine）。
執行：streamlit run app.py

v4.9 更新（回應 Urban-Renewal 介面對齊回覆）：
  1.【warnings[]】Core 統一健檢判斷（銷坪比/容積超出/共負區間/增值倍率），
     消費端只讀不重判，兩端邏輯不再分歧。
  2.【owners[]】地主清冊欄位定案（owner_id/land_share/pre_value/consent…），
     含 Σ持分／Σ權值一致性自檢；UI 暫傳空陣列，待真實清冊資料建置輸入介面。
  3.【追溯】result 新增 computed_at（ISO 8601）與 core_version；
     schema_version 升級 1.0→1.1（純新增欄位，向下相容）。

v4.8 更新（L6 財務層重構）：
  1.【營造基準】改用「總樓地板面積(含地下室)」，修正舊「允建坪」低估營造約一半的踩坑。
  2.【三模式】全案管理／合建／買賣；土地成本、全案管理費、權變費依模式計入。
  3.【新科目】補代銷費、信託+公共基金；設計費率由假設 5% 修正為實際 ~1.4%。
  4.【真實校準】以兩件真實案（私有校準紀錄，去識別化不進版控）鎖 L6 黃金測試（±5%）。

v4.7 更新（vNext Sprint 1：Core 化）：
  1.【模組拆分】計算層搬入 core/（capacity/efficiency/finance/valuation）；
     calc_engine.py 降為相容 shim，app.py 與測試 import 不變。
  2.【JSON 合約】新增 core/contract.py + schemas/project_schema.json；
     內部 domain 用中文、對外 key 用英文（allow_floor_area…），跨 App 唯一資料格式。
  3.【匯出】Tab ⑤ 新增「下載案件 JSON」，供都更儀表板 / AI 消費，不得自行重算。

v4.6（P1 穩定現有資料）：共負合理區間警示、更新前估值、增值倍率。
v4.5（P0 模組化）：計算層 calc_engine.py、法規庫 law_db.py、獎勵拆解 8/6 項。
核心計算承襲 v3：陽台/梯廳超出皆「逐層」判斷（§162），黃金測試：python test_golden.py
"""

import json
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from calc_engine import (
    calc_容積查核, calc_坪效, calc_開發評效,
    calc_投報全案, calc_投報敏感度,
    calc_獎勵率合計, check_bonus_limit,
    calc_更新前價值, build_project_json, CORE_VERSION,
    平方米換坪, 樓層欄位,
    財務率預設, 範本參數, 範本樓層表, 範本案件類型, 範本獎勵拆解, 範本模式,
    解析上傳, 產生報告,
)
from law_db import BONUS_都更, BONUS_危老, COMMON_BURDEN_RANGES


# ===========================================================================
# 畫面層 — 輔助函式
# ===========================================================================
def 載入樓層表(df, 參數=None, 案件類型=None, 獎勵拆解=None, 投報模式=None):
    st.session_state.floors_df = df.reset_index(drop=True)
    st.session_state.pop("floor_editor", None)
    if 參數:
        參數 = dict(參數)
        # 展平「財務覆寫」為一般參數：讓 Step4 費率 widget 顯示範本實際值、且使用者可編輯
        # （否則 widget 顯示財務率預設、但最終計算被覆寫值蓋過，使用者改了也無效）
        參數.update(參數.pop("財務覆寫", {}))
        st.session_state.params = 參數
    if 案件類型 is not None:
        st.session_state.案件類型 = 案件類型
    if 獎勵拆解 is not None:
        st.session_state.獎勵拆解 = dict(獎勵拆解)
    if 投報模式 is not None:
        st.session_state.投報模式 = 投報模式
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
/* ── 字體（v4.3 fix：不覆蓋 Streamlit icon font，emoji fallback 加回）── */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&family=Space+Grotesk:wght@500;600;700&display=swap');

/* 只改文字內容，不動 Streamlit 元件 class（避免 icon 字型被蓋）*/
html, body {
    font-family: 'Noto Sans TC', 'Space Grotesk', -apple-system, 'Segoe UI',
                 'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji', sans-serif;
}
.stMarkdown p, .stMarkdown li, .stMarkdown td, .stMarkdown th,
.stText, [data-testid="stCaptionContainer"],
[data-testid="stExpander"] summary p {
    font-family: 'Noto Sans TC', 'Space Grotesk', -apple-system, 'Segoe UI',
                 'Apple Color Emoji', 'Segoe UI Emoji', sans-serif !important;
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
        st.session_state.floors_df = 範本樓層表("案例C（防災都更）")
    if "params" not in st.session_state:
        st.session_state.params = dict(範本參數["案例C（防災都更）"])
    if "案件類型" not in st.session_state:
        st.session_state.案件類型 = 範本案件類型["案例C（防災都更）"]
    if "獎勵拆解" not in st.session_state:
        st.session_state.獎勵拆解 = dict(範本獎勵拆解["案例C（防災都更）"])
    if "投報模式" not in st.session_state:
        st.session_state.投報模式 = 範本模式["案例C（防災都更）"]

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        # ── 操作步驟引導 ─────────────────────────────────────────────────────
        st.markdown("""
<div style="background:linear-gradient(135deg,#534AB7,#7C6FE0);
border-radius:11px;padding:10px 14px 8px;margin-bottom:10px">
<div style="color:#fff;font-size:13px;font-weight:700;margin-bottom:6px">
  使用步驟</div>
<div style="color:rgba(255,255,255,0.88);font-size:11.5px;line-height:1.9">
  <b>1</b>　載入範本或輸入案件資訊<br>
  <b>2</b>　確認容積與免計基準（§162）<br>
  <b>3</b>　逐層填入面積表或上傳 Excel<br>
  <b>4</b>　查看右側 Tab 查核結果</div>
</div>
""", unsafe_allow_html=True)

        st.markdown("**案件設定**")
        範本選擇 = st.selectbox("選擇範本", list(範本參數.keys()), label_visibility="collapsed")
        if st.button("載入此範本（含逐層面積表）", use_container_width=True):
            載入樓層表(
                範本樓層表(範本選擇),
                dict(範本參數[範本選擇]),
                案件類型=範本案件類型[範本選擇],
                獎勵拆解=dict(範本獎勵拆解[範本選擇]),
                投報模式=範本模式[範本選擇],
            )

        P = st.session_state.params
        P["案件名稱"] = st.text_input("案件名稱", P.get("案件名稱", "新案"))

        # 案件類型：決定容積獎勵拆解清單（都更 8 項 / 危老 6 項）
        新案件類型 = st.selectbox(
            "案件類型", ["都更", "危老"],
            index=["都更", "危老"].index(st.session_state.案件類型),
            help="都市更新（都更）或危老重建（危老），決定容積獎勵項目清單與法規依據"
        )
        if 新案件類型 != st.session_state.案件類型:
            st.session_state.案件類型 = 新案件類型
            st.session_state.獎勵拆解 = {}
        案件類型 = st.session_state.案件類型

        st.divider()

        # Step 1
        with st.expander("Step 1  基地資訊（L2 容積計算）", expanded=True):
            st.caption("FA = 基地使用面積 × 容積率　→　允建容積 = FA × (1+獎勵率) + 容積移轉")
            c1, c2 = st.columns(2)
            P["基地面積"] = c1.number_input(
                "基地面積 m²", value=float(P.get("基地面積", 1000.0)), step=1.0,
                help="⚠️ 用使照面積，不用謄本面積！謄本面積會高估免計上限、掩蓋超容（踩坑3）")
            P["人行廣場"] = c2.number_input(
                "廣場捐地 m²", value=float(P.get("人行廣場", 0.0)), step=1.0,
                help="扣除後才是有效基地面積")
            P["容積率"] = c1.number_input(
                "容積率", value=float(P.get("容積率", 2.25)), step=0.01, format="%.4f",
                help="住二 = 2.25，商業區 = 5.60，輸入小數（225% → 2.25）")
            P["容積移轉"] = c2.number_input(
                "容積移轉 m²", value=float(P.get("容積移轉", 0.0)), step=1.0,
                help="購買可移入的容積（單位 m²，直接加計）")
            P["面積表計入容積"] = c1.number_input(
                "圖說計入容積 m²", value=float(P.get("面積表計入容積", 0.0)), step=1.0,
                help="填建築師面積表彙總值（圖說為真實依據）；填 0 = 由逐層各欄加總")

            # ── 容積獎勵拆解（P0：各項法規上限 + 自動累加）────────────────────
            st.divider()
            items = BONUS_都更 if 案件類型 == "都更" else BONUS_危老
            獎勵拆解 = dict(st.session_state.get("獎勵拆解", {}))
            st.caption(
                f"{'都更獎勵（都市更新建築容積獎勵辦法）' if 案件類型 == '都更' else '危老獎勵（危老條例 §6）'}"
                "——各項填 0 表示不申請"
            )
            for item in items:
                獎勵拆解[item["key"]] = st.number_input(
                    f"{item['label']}（≤ {item['cap']:.0%}）",
                    value=float(獎勵拆解.get(item["key"], item["default"])),
                    min_value=0.0, step=0.01, format="%.4f",
                    key=f"bonus_{item['key']}_{案件類型}",
                    help=f"{item['article']}\n{item['note']}"
                )
            st.session_state.獎勵拆解 = 獎勵拆解

            # 法規查核：超出上限警示（條文引用）
            violations = check_bonus_limit(獎勵拆解, 案件類型)
            for v in violations:
                st.warning(
                    f"⚠️ **{v['項目']}** 設定 {v['設定值']} 超出法規上限 {v['上限']}"
                    f"（{v['條文']}）"
                )

            P["獎勵率"] = calc_獎勵率合計(獎勵拆解, 案件類型)
            st.caption(f"獎勵率合計：**{P['獎勵率']:.3%}**（各項自動加總）")

        # Step 2
        with st.expander("Step 2  §162 免計基準（L3 三項免計）"):
            st.caption("建築技術規則 §162：梯廳、安全梯、陽台三項可不計入容積，但各有上限。超出上限須補計入。")
            c1, c2 = st.columns(2)
            P["梯廳免計基準"] = c1.selectbox(
                "梯廳免計上限（§162-1）", [5, 8],
                index=[5, 8].index(int(P.get("梯廳免計基準", 8))),
                help="各層樓板面積 × %（逐層判斷，非 FA 總量）\n"
                     "§162-1：「不計入容積之梯廳，不得超過各層樓板面積 8%（附表）」\n"
                     "待建築師確認：適用 5% 或 8%？")
            P["陽台免計基準"] = c2.selectbox(
                "陽台免計上限（§162）", [10, 15],
                index=[10, 15].index(int(P.get("陽台免計基準", 10))),
                help="各層樓板面積 × %（逐層判斷）\n"
                     "§162：一般住宅 10%\n"
                     "§162-3：特殊情況可至 15%（待建築師確認條文依據）")
            st.caption("安全梯：允建容積 × 15% 為總量上限（§162-1），自動計算。")
            P["公設比"] = c1.number_input(
                "公設比（坪效用）", value=float(P.get("公設比", 0.33)), step=0.01, format="%.2f",
                help="影響銷售坪數計算：銷售坪 = 室內坪 ÷ (1 − 公設比)\n"
                     "Tab ② 有反推驗算，防止公設比填錯造成 10 倍誤差")
            外皮係數 = c2.number_input("外皮係數", value=1.01, step=0.01, format="%.2f",
                                     help="牆厚修正係數，一般取 1.01")

        # Step 3
        with st.expander("Step 3  財務快篩（L5 開發評效）"):
            st.caption("快速評估「總銷 ÷ 總成本」—— > 5 優良 / 2–5 可行 / < 2 偏低")
            c1, c2 = st.columns(2)
            售價 = c1.number_input("售價（萬/坪）", value=80.0, step=1.0)
            土地成本 = c2.number_input("土地成本（萬）", value=50000.0, step=1000.0)
            營造單價 = c1.number_input(
                "營造單價（萬/坪）", value=18.0, step=0.5,
                help="L5 快篩用；L6 都更全案投報有獨立的「都更營造單價」")
            管銷費率 = c2.number_input("管銷費率", value=0.05, step=0.01, format="%.2f")
            建融成數 = c1.number_input("建融成數", value=0.50, step=0.05, format="%.2f")
            利率 = c2.number_input("利率（年）", value=0.03, step=0.005, format="%.3f")
            年期 = c1.number_input("建融年期", value=2.0, step=0.5)
            稅費率 = c2.number_input("稅費率", value=0.03, step=0.01, format="%.2f")
            營造坪基準 = st.radio(
                "營造坪數基準",
                ["銷售坪數（前期保守估算）", "允建容積坪（實務成本估算）"],
                help="⚠️ 誤用銷售坪會高估成本約 60%（含公設）\n"
                     "建築師實務上依允建容積坪估算")

        # Step 4
        with st.expander("Step 4  都更全案投報（L6）"):
            st.caption("對應建築師 Excel「坪效及獲利分析」\n費率基數：代銷/稅 → 總銷，設計 → 營造費，管維 → 工程費A")
            _模式選項 = ["全案管理", "合建", "買賣"]
            投報模式 = st.radio(
                "投報模式", _模式選項, horizontal=True,
                index=_模式選項.index(st.session_state.投報模式),
                help="全案管理：地主自持土地，土地成本不計共負、另收全案管理費（權變）\n"
                     "合建／買賣：土地為成本計入總成本，不收全案管理費",
            )
            st.session_state.投報模式 = 投報模式
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
            P["權變戶數"] = c2.number_input(
                "權變戶數（拆補基準）", value=int(P.get("權變戶數", P.get("戶數", 0))),
                step=1, help="既有地主戶數（拆遷/租金補償基準），非總銷售戶數；合建分屋可填 0")
            P["土融土地成本"] = c1.number_input(
                "土地成本（萬）", value=float(P.get("土融土地成本", 0.0)), step=1000.0,
                help="全案管理（地主自持）填 0；合建/買賣填土地取得成本，計入共負 G 科目與土融利息")
            st.caption("💡 營造基準已自動採「總樓地板面積（含地下室）」= 逐層表加總，不需手填")
            with st.expander("⚙️ 進階成本率（預設＝實案校準值）"):
                cc1, cc2 = st.columns(2)
                P["管理費率"] = cc1.number_input(
                    "全案管理費率（基數：總銷）",
                    value=float(P.get("管理費率", 財務率預設["管理費率"])), step=0.005, format="%.3f")
                P["設計規劃率"] = cc2.number_input(
                    "設計規劃率（基數：營造費，含監造+管理）",
                    value=float(P.get("設計規劃率", 財務率預設["設計規劃率"])), step=0.002, format="%.3f",
                    help="實際案例校準約 1.3–1.4%（非舊估的 5–8%）")
                P["管維率"] = cc1.number_input(
                    "容獎管維率（基數：工程費A）",
                    value=float(P.get("管維率", 財務率預設["管維率"])), step=0.005, format="%.3f")
                P["權變作業率"] = cc2.number_input(
                    "權變作業率（基數：房地銷）",
                    value=float(P.get("權變作業率", 財務率預設["權變作業率"])), step=0.005, format="%.3f",
                    help="僅全案管理模式計入；合建/買賣不適用權變程序")
                P["營業稅率"] = cc1.number_input(
                    "營業稅率（基數：房地銷）",
                    value=float(P.get("營業稅率", 財務率預設["營業稅率"])), step=0.005, format="%.3f",
                    help="正式權變共負須 5%；前期試算有時簡化為 1–2%，注意版本別")
                P["代銷費率"] = cc2.number_input(
                    "代銷費率（基數：總銷）",
                    value=float(P.get("代銷費率", 財務率預設["代銷費率"])), step=0.005, format="%.3f")
                P["信託費率"] = cc1.number_input(
                    "信託+公共基金率（基數：總銷）",
                    value=float(P.get("信託費率", 財務率預設["信託費率"])), step=0.002, format="%.3f")
                P["拆補每戶"] = cc2.number_input(
                    "拆補每戶（萬）",
                    value=float(P.get("拆補每戶", 財務率預設["拆補每戶"])), step=5.0)
                P["月租金每戶"] = cc1.number_input(
                    "月租金每戶（萬）",
                    value=float(P.get("月租金每戶", 財務率預設["月租金每戶"])), step=0.5)
                P["安置月數"] = cc2.number_input(
                    "安置月數", value=int(P.get("安置月數", 財務率預設["安置月數"])), step=1)

        # Step 5 （P1）
        with st.expander("Step 5  更新前估值（L7 權利變換基準）"):
            st.caption(
                "更新前土地 + 建物現值 = 權利變換計算基礎（都更條例 §56）。\n"
                "填入後自動計算增值倍率與地主應分回估算。0 = 略過此試算。")
            c1, c2 = st.columns(2)
            P["地價"] = c1.number_input(
                "土地市值（萬/坪）", value=float(P.get("地價", 0.0)), step=10.0,
                help="建議：公告現值 × 1.2 倍 或 實際市場行情\n"
                     "0 = 不進行更新前估值試算")
            P["屋齡"] = c2.number_input(
                "既有建物屋齡（年）", value=int(P.get("屋齡", 40)), step=1,
                help="RC 造法定折舊率 2%/年；耐用年限 50 年後殘值為 0")
            P["既有建物面積"] = c1.number_input(
                "既有建物總面積 m²", value=float(P.get("既有建物面積", 0.0)), step=10.0,
                help="現有建物各層樓地板面積合計（謄本或現況丈量）")
            P["建物單價"] = c2.number_input(
                "建物單價（萬/坪）", value=float(P.get("建物單價", 10.0)), step=1.0,
                help="老屋折舊後單價，通常 5–15 萬/坪（RC 造）")
            st.caption(f"折舊率固定 2%/年（RC 造），殘值率 = max(0, 1 − 2% × 屋齡)")

    # ── Hero 標題橫幅 ─────────────────────────────────────────────────────────
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
        v4.9</span>
      <span style="background:rgba(255,255,255,0.13);border:1px solid rgba(255,255,255,0.28);
      backdrop-filter:blur(4px);border-radius:999px;padding:4px 14px;
      color:rgba(255,255,255,0.95);font-size:11.5px;font-weight:600;white-space:nowrap;">
        逐層 §162</span>
      <span style="background:rgba(255,255,255,0.13);border:1px solid rgba(255,255,255,0.28);
      backdrop-filter:blur(4px);border-radius:999px;padding:4px 14px;
      color:rgba(255,255,255,0.95);font-size:11.5px;font-weight:600;white-space:nowrap;">
        獎勵拆解</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── 上傳工具 ──────────────────────────────────────────────────────────────
    with st.expander("📤 匯入建築師面積表（Excel / CSV）", expanded=True):
        cimp1, cimp2 = st.columns([3, 2])
        with cimp1:
            st.caption(
                "支援建照/使照圖說格式 Excel 或 CSV。\n"
                "自動辨識欄名：樓層／樓地板／計入容積／梯廳／安全梯（機電）／陽台。\n"
                "欄名對不上時工具會留空，可在下方逐層表格手動補填。")
            上傳 = st.file_uploader(
                "拖曳或選取面積表檔案", type=["xlsx", "xls", "csv"],
                help="台灣建築師事務所常見欄位命名皆支援（含走廊梯廳、陽臺面積、防火梯等別名）")
            if 上傳 is not None and st.button("✅ 套用上傳的面積表"):
                try:
                    df_up = 解析上傳(上傳)
                    if df_up["計容積"].sum() > 0:
                        st.session_state.params["面積表計入容積"] = 0.0
                    載入樓層表(df_up)
                except Exception as e:
                    st.error(f"解析失敗：{e}")
        with cimp2:
            範本列 = [
                dict(啟用=False, 樓層="B1F（防空避難室§117）", 樓板=0, 計容積=0, 梯廳=0, 安全梯=0, 陽台=0),
                dict(啟用=True,  樓層="1F",  樓板=0, 計容積=0, 梯廳=0, 安全梯=0, 陽台=0),
                dict(啟用=True,  樓層="2F",  樓板=0, 計容積=0, 梯廳=0, 安全梯=0, 陽台=0),
                dict(啟用=True,  樓層="標準層（複製此列）", 樓板=0, 計容積=0, 梯廳=0, 安全梯=0, 陽台=0),
            ]
            st.download_button("⬇️ 下載面積表範本（含說明）",
                               pd.DataFrame(範本列).to_csv(index=False).encode("utf-8-sig"),
                               "建築師面積表匯入範本.csv", "text/csv", use_container_width=True)
            st.caption("B1F 防空避難室依 §117 預設不計入，請依圖說確認後再啟用")

    # ── §162 法規對照卡 ──────────────────────────────────────────────────────
    with st.expander("📐 建築技術規則 §162 三項免計——欄位對照", expanded=False):
        st.markdown("""
<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;margin:4px 0">

<div style="background:#F4F3FB;border-radius:10px;padding:10px 13px;border-left:3px solid #534AB7">
<div style="font-size:10px;font-weight:700;color:#534AB7;letter-spacing:0.8px;margin-bottom:4px">
梯廳　欄位 ▶ §162-1</div>
<div style="font-size:12.5px;color:#1E293B;font-weight:600;margin-bottom:4px">
免計上限：各層樓板 × 8%<br>（附表，或 5%）</div>
<div style="font-size:11.5px;color:#64748B;line-height:1.6">
逐層判斷，不得以 FA×8% 總量計算。超出部分<b>補計入</b>容積（踩坑2）。</div>
</div>

<div style="background:#FFF7ED;border-radius:10px;padding:10px 13px;border-left:3px solid #F59E0B">
<div style="font-size:10px;font-weight:700;color:#D97706;letter-spacing:0.8px;margin-bottom:4px">
安全梯　欄位 ▶ §162-1</div>
<div style="font-size:12.5px;color:#1E293B;font-weight:600;margin-bottom:4px">
免計上限：允建容積 × 15%<br>（總量上限）</div>
<div style="font-size:11.5px;color:#64748B;line-height:1.6">
安全梯＋機電設備合計上限。<b>基準是允建容積</b>，非 FA（踩坑6）。</div>
</div>

<div style="background:#F0FDF4;border-radius:10px;padding:10px 13px;border-left:3px solid #16A34A">
<div style="font-size:10px;font-weight:700;color:#16A34A;letter-spacing:0.8px;margin-bottom:4px">
陽台　欄位 ▶ §162 / §162-3</div>
<div style="font-size:12.5px;color:#1E293B;font-weight:600;margin-bottom:4px">
免計上限：各層樓板 × 10%<br>（§162-3 特殊案件 15%）</div>
<div style="font-size:11.5px;color:#64748B;line-height:1.6">
逐層判斷，超出補計入。亦可用 1/8 投影法（兩法並列，取較嚴者）。</div>
</div>

<div style="background:#FFF1F2;border-radius:10px;padding:10px 13px;border-left:3px solid #E11D48">
<div style="font-size:10px;font-weight:700;color:#E11D48;letter-spacing:0.8px;margin-bottom:4px">
B1F 防空避難室　▶ §117</div>
<div style="font-size:12.5px;color:#1E293B;font-weight:600;margin-bottom:4px">
依法設置者不計入<br>樓地板面積</div>
<div style="font-size:11.5px;color:#64748B;line-height:1.6">
在逐層表格<b>取消「計入」勾選</b>即可排除。依條文強制規定，非選項（踩坑5）。</div>
</div>

</div>
""", unsafe_allow_html=True)

    # ── 逐層明細（主畫面常駐）────────────────────────────────────────────────
    st.markdown(_section("逐層面積明細", "圖說為真實依據　·　B1F 請取消勾選排除（§117）"),
                unsafe_allow_html=True)
    edited = st.data_editor(
        st.session_state.floors_df, key="floor_editor", num_rows="dynamic",
        use_container_width=True, height=240,
        column_config={
            "啟用": st.column_config.CheckboxColumn(
                "計入", help="取消勾選＝排除此層（B1F 防空避難室依 §117 不計入，務必取消）"),
            "樓層": st.column_config.TextColumn("樓層"),
            "樓板": st.column_config.NumberColumn(
                "樓板 m²", format="%.2f",
                help="各層樓地板面積，是梯廳/陽台免計上限的計算基準（§162 逐層法）"),
            "計容積": st.column_config.NumberColumn(
                "計容積 m²", format="%.2f",
                help="圖說面積表的計入容積欄位（填 0 時由側欄「圖說計入容積」彙總值代替）"),
            "梯廳": st.column_config.NumberColumn(
                "梯廳 m²", format="%.2f",
                help="§162-1：免計上限＝各層樓板 × 8%（或 5%）\n超出部分會補計入容積"),
            "安全梯": st.column_config.NumberColumn(
                "安全梯 m²", format="%.2f",
                help="§162-1：總量上限＝允建容積 × 15%（注意：基準是允建容積，不是 FA）"),
            "陽台": st.column_config.NumberColumn(
                "陽台 m²", format="%.2f",
                help="§162：免計上限＝各層樓板 × 10%（§162-3 特殊 15%）\n超出部分補計入容積"),
        })
    樓層records = edited.to_dict("records")

    # ── 計算 ──────────────────────────────────────────────────────────────────
    容 = calc_容積查核(P, 樓層records)
    坪 = calc_坪效(容["允建容積"], 容["陽台免計面積"], P["公設比"], 外皮係數)

    _營造坪數 = (坪["允建容積坪"] if 營造坪基準 == "允建容積坪（實務成本估算）"
               else 坪["銷售坪數"])

    成本 = dict(售價=售價, 土地成本=土地成本, 營造單價=營造單價, 營造坪數=_營造坪數,
              管銷費率=管銷費率, 建融成數=建融成數, 利率=利率, 年期=年期, 稅費率=稅費率)
    from calc_engine import calc_開發評效
    評 = calc_開發評效(坪["銷售坪數"], 成本)

    # P1 更新前價值（有填地價才試算）
    前值 = (calc_更新前價值(
                P["基地面積"], P["地價"],
                P.get("既有建物面積", 0.0), P.get("建物單價", 10.0),
                int(P.get("屋齡", 40)))
            if P.get("地價", 0) > 0 else None)

    # L6 投報：財務率預設 ← 各案覆寫（財務覆寫已於載入樓層表()展平入 P，Step4 widget 可直接編輯）
    投報參數 = {**財務率預設,
              **{k: P[k] for k in ("住宅單價", "店舖坪數", "店舖單價", "車位數", "車位單價",
                                   "營造單價", "設計規劃率", "管維率",
                                   "權變作業率", "拆補每戶", "月租金每戶", "安置月數", "管理費率",
                                   "營業稅率", "代銷費率", "信託費率", "權變戶數", "戶數")
                 if k in P},
              "土地成本": float(P.get("土融土地成本", 0.0))}
    # 營造基準＝總樓地板面積(含地下室)；踩坑：用允建坪會低估營造成本約一半
    _總營建坪 = 容["總樓地板面積"] / 平方米換坪
    投 = calc_投報全案(坪["銷售坪數"], _總營建坪, 投報參數, 投報模式)

    # ── L2→L6 計算流程帶 + 結論橫幅 ────────────────────────────────────────
    餘量 = 容["容積餘量"]
    免計超出 = 容["梯廳超出"] + 容["陽台超出"]
    評效 = 評["開發評效"]
    評效等級 = "優良" if 評效 > 5 else "可行" if 評效 >= 2 else "偏低"
    st.markdown(_pipeline(容, 坪, 評效, 投), unsafe_allow_html=True)
    st.markdown(_banner(餘量), unsafe_allow_html=True)

    # ── 4 欄 KPI ──────────────────────────────────────────────────────────────
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

    # ── Tab ①：容積查核 ────────────────────────────────────────────────────
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

        # ── 三項免計核對表（建築師送件格式）──────────────────────────────────
        st.markdown(_section(
            "三項免計核對表",
            "對應建築師面積表 §162 查核欄　·　L3"),
            unsafe_allow_html=True)
        st.caption(
            "此格式對應建築師申請建照/使照時的「容積計算說明」，可與圖說面積表逐行核對。")
        梯廳免計合計 = sum(
            min(float(f.get("梯廳") or 0), float(f.get("樓板") or 0) * P["梯廳免計基準"] / 100)
            for f in 樓層records if f.get("啟用", True))
        陽台免計合計 = 容["陽台免計面積"]
        核對表 = pd.DataFrame([
            {"免計項目": "① 梯廳（§162-1）",
             "法規上限公式": f"各層樓板 × {P['梯廳免計基準']}%（逐層）",
             "免計上限合計 m²": f"{sum(float(f.get('樓板') or 0) * P['梯廳免計基準'] / 100 for f in 樓層records if f.get('啟用', True)):.2f}",
             "圖說實際 m²": f"{sum(float(f.get('梯廳') or 0) for f in 樓層records if f.get('啟用', True)):.2f}",
             "免計採認 m²": f"{梯廳免計合計:.2f}",
             "超出須補計 m²": f"{容['梯廳超出']:.2f}",
             "狀態": "❌ 超出" if 容["梯廳超出"] > 0.01 else "✅ 合規"},
            {"免計項目": "② 安全梯及機電（§162-1）",
             "法規上限公式": "允建容積 × 15%（總量）",
             "免計上限合計 m²": f"{容['安全梯上限']:.2f}",
             "圖說實際 m²": f"{容['安全梯總量']:.2f}",
             "免計採認 m²": f"{min(容['安全梯總量'], 容['安全梯上限']):.2f}",
             "超出須補計 m²": f"{max(0, 容['安全梯總量'] - 容['安全梯上限']):.2f}",
             "狀態": ("❌ 超出" if 容["安全梯總量"] > 容["安全梯上限"]
                     else "✅ 合規")},
            {"免計項目": f"③ 陽台（§162，{P['陽台免計基準']}% 法）",
             "法規上限公式": f"各層樓板 × {P['陽台免計基準']}%（逐層）",
             "免計上限合計 m²": f"{sum(float(f.get('樓板') or 0) * P['陽台免計基準'] / 100 for f in 樓層records if f.get('啟用', True)):.2f}",
             "圖說實際 m²": f"{容['陽台總量']:.2f}",
             "免計採認 m²": f"{陽台免計合計:.2f}",
             "超出須補計 m²": f"{容['陽台超出']:.2f}",
             "狀態": "❌ 超出" if 容["陽台超出"] > 0.01 else "✅ 合規"},
        ])
        st.dataframe(核對表, use_container_width=True, hide_index=True)
        超出合計 = 容["梯廳超出"] + 容["陽台超出"] + max(0, 容["安全梯總量"] - 容["安全梯上限"])
        if 超出合計 > 0.01:
            st.error(
                f"三項免計超出合計 **{超出合計:.2f} m²**，依 §162 須全數補計入容積（計入容積已自動加計）。"
                "建議回建築師確認圖說設計是否需調整。")
        else:
            st.success("三項免計全數在法規上限內，無須補計。")

        st.divider()

        st.markdown(_section(
            "逐層免計查核明細",
            f"梯廳基準 {P['梯廳免計基準']}%　·　陽台基準 {P['陽台免計基準']}% 或 1/8 投影"),
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

        # ── 公設比反推驗算 ──────────────────────────────────────────────────
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
            f"總銷 → 共同負擔科目（都市更新權利變換實施辦法）→ 地主分回。"
            f"　投報模式：**{投報模式}**"
            f"　營造坪採 **{_總營建坪:.0f} 坪**（圖說總樓地板，含地下室）。")
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
        _有土地科目 = 投.get("G土地成本", 0) > 0
        with cc2:
            st.markdown(_section(
                "共同負擔科目" + ("（含 G 土地）" if _有土地科目 else "六大科目"),
                "權利變換實施辦法"), unsafe_allow_html=True)
            _科目列 = [
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
            ]
            if _有土地科目:
                _科目列.append({"科目": "G 土地成本", "金額(萬)": f"{投['G土地成本']:,.0f}",
                              "占總銷": f"{投['G土地成本']/投['總銷']:.1%}"})
            _科目列.append({"科目": "🔴 共同負擔", "金額(萬)": f"{投['共同負擔']:,.0f}",
                          "占總銷": f"{投['共負比']:.1%}"})
            st.dataframe(pd.DataFrame(_科目列), use_container_width=True, hide_index=True)

        _wf_x = ["A工程", "B管維", "C權變", "D利息", "E稅捐", "F管理"]
        _wf_y = [投["A工程費用"], 投["B管維費用"], 投["C權變費用"], 投["D貸款利息"],
                 投["E稅捐"], 投["F管理費用"]]
        if _有土地科目:
            _wf_x.append("G土地")
            _wf_y.append(投["G土地成本"])
        _wf_x.append("共同負擔")
        _wf_y.append(投["共同負擔"])
        wf = go.Figure(go.Waterfall(
            orientation="v", measure=["relative"] * (len(_wf_x) - 1) + ["total"],
            x=_wf_x, y=_wf_y,
            texttemplate="%{y:,.0f}", textposition="outside",
            connector={"line": {"color": "#D6D9E4"}},
            increasing={"marker": {"color": "#534AB7"}},
            totals={"marker": {"color": "#1E1B4B"}}))
        wf.update_layout(**_fig_layout(title="共同負擔科目拆解（萬）", height=360))
        st.plotly_chart(wf, use_container_width=True)

        分回每戶 = 投["地主分回價值"] / P["戶數"] if P.get("戶數") else 0
        st.info(
            f"地主分回 **{投['地主分回價值']:,.0f} 萬**（占總銷 {投['地主分回比']:.1%}）"
            + (f"，{int(P['戶數'])} 戶平均 **{分回每戶:,.0f} 萬/戶**（依各戶權值估價，僅示意）"
               if P.get("戶數") else "")
            + "。共負比 > 65% 時留意地主接受度。")

        # ── 費率基數一覽 ──────────────────────────────────────────────────────
        with st.expander("📋 費率基數一覽（方法論 §4③ 查核項）", expanded=False):
            st.caption("各費率計算基數不同，誤用基數會造成嚴重誤算（方法論 §4③、§6）。")
            明細 = 投["_明細"]
            _費率列 = [
                {"費率名稱": "A 設計規劃", "費率基數": "A中的營造費（含監造+管理）",
                 "基數(萬)": f"{明細['營造成本']:,.0f}",
                 "費率": f"{P.get('設計規劃率', 財務率預設['設計規劃率']):.1%}",
                 "金額(萬)": f"{明細['設計規劃']:,.0f}"},
                {"費率名稱": "B 容獎管維", "費率基數": "A 工程費用合計",
                 "基數(萬)": f"{投['A工程費用']:,.0f}",
                 "費率": f"{P.get('管維率', 財務率預設['管維率']):.1%}",
                 "金額(萬)": f"{投['B管維費用']:,.0f}"},
                {"費率名稱": "C 權變作業", "費率基數": "房地總銷（僅全案管理適用）",
                 "基數(萬)": f"{投['房地總銷']:,.0f}",
                 "費率": f"{P.get('權變作業率', 財務率預設['權變作業率']):.1%}",
                 "金額(萬)": f"{明細['權變作業']:,.0f}"},
                {"費率名稱": "C 拆遷+租金補償", "費率基數": f"權變戶數 {int(P.get('權變戶數', P.get('戶數', 0)))} 戶",
                 "基數(萬)": "—",
                 "費率": "—",
                 "金額(萬)": f"{明細['拆遷補償'] + 明細['租金補償']:,.0f}"},
                {"費率名稱": "E 營業稅", "費率基數": "房地總銷",
                 "基數(萬)": f"{投['房地總銷']:,.0f}",
                 "費率": f"{P.get('營業稅率', 財務率預設['營業稅率']):.1%}",
                 "金額(萬)": f"{明細['營業稅']:,.0f}"},
                {"費率名稱": "E 印花稅", "費率基數": "總銷",
                 "基數(萬)": f"{投['總銷']:,.0f}",
                 "費率": f"{財務率預設['印花稅率']:.1%}",
                 "金額(萬)": f"{明細['印花稅']:,.0f}"},
                {"費率名稱": "F 全案管理費", "費率基數": "總銷（僅全案管理適用）",
                 "基數(萬)": f"{投['總銷']:,.0f}",
                 "費率": f"{P.get('管理費率', 財務率預設['管理費率']):.1%}",
                 "金額(萬)": f"{明細['全案管理費']:,.0f}"},
                {"費率名稱": "F 代銷費", "費率基數": "總銷",
                 "基數(萬)": f"{投['總銷']:,.0f}",
                 "費率": f"{P.get('代銷費率', 財務率預設['代銷費率']):.1%}",
                 "金額(萬)": f"{明細['代銷費']:,.0f}"},
                {"費率名稱": "F 信託+公共基金", "費率基數": "總銷",
                 "基數(萬)": f"{投['總銷']:,.0f}",
                 "費率": f"{P.get('信託費率', 財務率預設['信託費率']):.1%}",
                 "金額(萬)": f"{明細['信託公基金']:,.0f}"},
            ]
            st.dataframe(pd.DataFrame(_費率列), use_container_width=True, hide_index=True)
            if 投.get("G土地成本", 0) > 0:
                st.caption(
                    f"G 土地成本（{投報模式}）：{投['G土地成本']:,.0f} 萬，計入共同負擔　｜　"
                    f"土融利息（D）：× 成數 {財務率預設['土融成數']:.0%} × 利率 {財務率預設['土融利率']:.1%} × "
                    f"年期 {財務率預設['土融年期']:.0f}年 = {明細['土融利息']:,.0f} 萬")

        # ── P1 共同負擔比合理區間檢核 ────────────────────────────────────────
        st.markdown(_section("共同負擔比合理區間", "P1 穩定性查核　·　law_db.py"), unsafe_allow_html=True)
        _模式對應 = {"都更": "都更全案管理", "危老": "危老重建"}
        _模式預設 = _模式對應.get(案件類型, "都更全案管理")
        # 案件切換時重置比較模式（key 固定的 widget 不會自動跟著 index 參數更新，
        # 需在渲染前直接改 session_state[key]，否則沿用上一個案件的選擇，案件切換踩坑）
        if st.session_state.get("_共負模式_案件") != P.get("案件名稱"):
            st.session_state["共負模式"] = _模式預設
            st.session_state["_共負模式_案件"] = P.get("案件名稱")
        _模式 = st.selectbox(
            "比較模式",
            list(COMMON_BURDEN_RANGES.keys()),
            help="依案件性質選擇合理區間基準（法源：都市更新推動中心參考資料）",
            key="共負模式"
        )
        _範圍 = COMMON_BURDEN_RANGES[_模式]
        _共負比 = 投["共負比"]
        _共負low, _共負high, _共負warn = _範圍["low"], _範圍["high"], _範圍["warn"]
        _bar_pct = min(_共負比 / _共負warn, 1.0)
        st.markdown(
            f'<div style="background:#F8F9FB;border-radius:10px;padding:12px 16px;margin:4px 0">'
            f'<div style="display:flex;justify-content:space-between;margin-bottom:6px">'
            f'<span style="font-size:12px;color:#6B7280">合理：{_共負low:.0%}–{_共負high:.0%}</span>'
            f'<span style="font-size:12px;color:#6B7280">警示線：{_共負warn:.0%}</span>'
            f'<span style="font-size:13px;font-weight:700;color:#1E293B">本案：{_共負比:.1%}</span>'
            f'</div>'
            f'<div style="height:8px;border-radius:4px;background:#E5E7EB;overflow:hidden">'
            f'<div style="width:{_bar_pct*100:.0f}%;height:100%;border-radius:4px;'
            f'background:{"#DC2626" if _共負比>_共負warn else "#F59E0B" if _共負比>_共負high else "#16A34A"}">'
            f'</div></div></div>',
            unsafe_allow_html=True
        )
        if _共負比 > _共負warn:
            st.error(f"⚠️ 共負比 {_共負比:.1%} 超過警示線 {_共負warn:.0%}，地主接受度明顯降低。{_範圍['note']}")
        elif _共負比 > _共負high:
            st.warning(f"共負比 {_共負比:.1%} 偏高（合理區間上限 {_共負high:.0%}），建議重新檢視成本結構。")
        else:
            st.success(f"共負比 {_共負比:.1%} 在 {_模式} 合理區間 {_共負low:.0%}–{_共負high:.0%} 內。")

        # ── P1 更新前估值 + 增值倍率 ──────────────────────────────────────────
        if 前值 is not None:
            st.markdown(_section("更新前估值 × 增值倍率", "L7 都更條例 §56 權利變換基準"),
                        unsafe_allow_html=True)
            _增值倍率 = 投["地主分回價值"] / 前值["更新前總值"] if 前值["更新前總值"] > 0 else 0
            _c1, _c2, _c3 = st.columns(3)
            _c1.metric("更新前總值", f"{前值['更新前總值']:,.0f} 萬",
                       f"土地 {前值['土地現值']:,.0f} ＋ 建物 {前值['建物現值']:,.0f}")
            _c2.metric("地主分回市值（更新後）", f"{投['地主分回價值']:,.0f} 萬",
                       help="L6 總銷 − 共同負擔 = 地主分回市值")
            _c3.metric("增值倍率", f"{_增值倍率:.2f}×",
                       f"殘值率 {前值['建物殘值率']:.0%}（屋齡 {int(P.get('屋齡',40))} 年）")
            st.caption(
                f"建物殘值率 = 1 − 2% × {int(P.get('屋齡',40))} 年 = {前值['建物殘值率']:.0%}　｜　"
                f"土地 {前值['基地坪']:.1f} 坪 × {P['地價']:.0f} 萬 = {前值['土地現值']:,.0f} 萬　｜　"
                f"建物 {前值['建物坪']:.1f} 坪 × {P.get('建物單價',10):.0f} 萬 × {前值['建物殘值率']:.0%} = {前值['建物現值']:,.0f} 萬"
            )
            if _增值倍率 < 1.0:
                st.warning("增值倍率 < 1.0：地主更新後市值低於更新前估值，請確認地價或共負結構。")
            elif _增值倍率 >= 1.5:
                st.success(f"增值倍率 {_增值倍率:.2f}×，地主更新效益顯著（建議向地主說明此數字）。")

        st.markdown(_section("報酬率敏感度", "住宅售價 × 營造單價"), unsafe_allow_html=True)
        sens = calc_投報敏感度(坪["銷售坪數"], _總營建坪, 投報參數, 投報模式)
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

        # ── 案件 JSON 合約（RE-DCF Core 對外唯一資料格式，schema v1.1）──
        st.divider()
        st.markdown(f"**🔗 案件 JSON（Core 合約 v1.1｜core {CORE_VERSION}）**")
        st.caption("RE-DCF Core Engine 的對外標準格式（英文 key）。"
                   "供 都更儀表板 / Simulator / AI Copilot 消費——所有數值與健檢判斷"
                   "（result.warnings）只由 Core 計算，消費端不得自行重算或重判門檻。"
                   "Schema 見 schemas/project_schema.json。")
        案件JSON = build_project_json(
            P, 容, 坪, 投, 前值,
            案件類型=st.session_state.get("案件類型", "都更"),
            獎勵拆解=st.session_state.get("獎勵拆解", {}),
            投報模式=投報模式,
            owners=[],  # 地主清冊 UI 尚未建置（P1 待真實清冊資料），先輸出空陣列
        )
        st.download_button(
            "⬇️ 下載案件 JSON",
            json.dumps(案件JSON, ensure_ascii=False, indent=2).encode("utf-8"),
            f"{P['案件名稱']}_case.json", "application/json")
        if 案件JSON["result"]["warnings"]:
            for w in 案件JSON["result"]["warnings"]:
                _icon = {"error": "🔴", "warn": "🟡", "info": "🔵"}.get(w["level"], "•")
                st.caption(f"{_icon} `{w['code']}` {w['message']}")
        with st.expander("預覽 JSON 合約"):
            st.json(案件JSON)

    # ── 頁尾 ─────────────────────────────────────────────────────────────────
    _build = "2026-07-01"
    st.markdown(
        f'<div style="margin-top:2rem;padding:13px 2px 4px;border-top:1px solid #E7E9F2;'
        f'display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;'
        f'font-size:11.5px;color:#9AA1B5">'
        f'<span>🏗️ <b style="color:#6B7280">RE-DCF-Tool v4.9</b>　永盛開發建設 前期評估</span>'
        f'<span style="color:#C9CEDB">build {_build}　·　圖說為真　·　§162 逐層查核　·　都市更新權利變換實施辦法</span>'
        f'</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
