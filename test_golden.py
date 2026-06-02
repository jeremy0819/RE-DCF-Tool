# -*- coding: utf-8 -*-
"""
黃金測試 v3（逐層表格）：驗證三案核心數字。
來源：永盛開發_知識庫 + 中正段面積表查核報告。
執行：python test_golden.py
"""
import sys, types
# Windows 繁中主控台預設 cp950，印不出 emoji（✅❌🎉）會讓「其實有通過」的測試
# 噴 UnicodeEncodeError 假崩潰。先強制 stdout 走 UTF-8，讓直接 python test_golden.py 也能跑。
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass
# pandas 是真要用的（範本樓層表回傳 DataFrame）；只 stub UI 套件。
for 套件 in ["streamlit", "plotly", "plotly.graph_objects"]:
    if 套件 not in sys.modules:
        m = types.ModuleType(套件)
        sys.modules[套件] = m
# streamlit.column_config 屬性存取防呆
sys.modules["streamlit"].column_config = types.SimpleNamespace()

from app import calc_容積查核, calc_坪效, 範本參數, 範本樓層表   # noqa: E402


def 近似(a, b, 容差=0.5):
    return abs(a - b) <= 容差


def 跑(鍵, 期望: dict):
    參數 = dict(範本參數[鍵])
    records = 範本樓層表(鍵).to_dict("records")
    r = calc_容積查核(參數, records)
    print(f"\n=== {鍵} ===")
    全過 = True
    for 欄, 期 in 期望.items():
        實 = r[欄]
        ok = 近似(實, 期)
        全過 = 全過 and ok
        print(f"  {'✅' if ok else '❌'} {欄}: {實:.2f} / 期望 {期:.2f}")
    return 全過, r


def main():
    結果 = []

    過, _ = 跑("安和段（都市更新）", {"基準容積FA": 4569.71, "允建容積": 7768.51, "安全梯上限": 1165.28})
    結果.append(("安和段", 過))

    過, _ = 跑("龜山半嶺段（危老）", {"允建容積": 4244.04, "梯廳超出": 32.45,
                              "計入容積_修正後": 4276.25, "容積餘量": -32.21})
    結果.append(("龜山段", 過))

    過, 中 = 跑("中正段（防災都更）", {"基準容積FA": 2211.75, "允建容積": 4167.08, "安全梯上限": 625.06,
                                "陽台超出": 29.11, "梯廳超出": 2.65,
                                "計入容積_修正後": 4198.75, "容積餘量": -31.67})
    結果.append(("中正段", 過))

    print("\n" + "=" * 42)
    for 名, 過 in 結果:
        print(f"  {'✅ PASS' if 過 else '❌ FAIL'}  {名}")

    # 銷坪比（龜山，陽台全免計）
    坪 = calc_坪效(中["允建容積"], 中["陽台免計面積"], 0.33, 外皮係數=1.0)
    print(f"\n  中正銷坪比（修正後公式）= {坪['銷坪比']:.3f}")
    print(f"  中正安全梯總量 = {中['安全梯總量']:.2f}（期望 625.05）")

    assert all(過 for _, 過 in 結果), "有案例未通過！"
    print("\n  🎉 三案全部 PASS")


if __name__ == "__main__":
    main()
