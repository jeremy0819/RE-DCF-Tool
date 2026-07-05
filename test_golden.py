# -*- coding: utf-8 -*-
"""
黃金迴歸測試 v4（合成案例）：驗證四案容積層 + L6 財務層 + JSON 合約。
執行：pytest　（或 python test_golden.py）

⚠️ 去識別化聲明（合併前置 P0-1）：本檔全部期望值來自 core/templates.py 的**合成案例**
（虛構輸入 → 決定性輸出），為純迴歸鎖定。費率／公式曾以真實案件私下校準（誤差 ±5% 內），
校準紀錄不進版控；本測試保護的是「公式不被改壞」，不是「數字等於某真實案」。
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

from calc_engine import (calc_容積查核, calc_坪效, calc_投報全案,   # noqa: E402
                         calc_更新前價值, build_project_json,
                         範本參數, 範本樓層表, 範本案件類型, 範本獎勵拆解,
                         範本模式, 財務率預設)


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


def _建p(P):
    """由範本參數建 L6 成本率字典：財務率預設 → 售價/單價 → 各案財務覆寫。"""
    p = {**財務率預設,
         **{k: P[k] for k in ("住宅單價", "店舖坪數", "店舖單價", "車位數", "車位單價",
                              "營造單價", "戶數", "權變戶數") if k in P},
         "土地成本": P.get("土融土地成本", 0.0)}
    p.update(P.get("財務覆寫", {}))
    return p


def 測試投報鎖定(鍵, 期望共負, 期望共負比, 期望報酬率):
    """跑合成案完整 pipeline，鎖定 L6 輸出（純迴歸；共負容差 0.5%、比率 ±0.005）。"""
    P = dict(範本參數[鍵])
    容 = calc_容積查核(P, 範本樓層表(鍵).to_dict("records"))
    坪 = calc_坪效(容["允建容積"], 容["陽台免計面積"], P["公設比"])
    投 = calc_投報全案(坪["銷售坪數"], 容["總樓地板面積"] / 3.3058, _建p(P), 範本模式[鍵])
    共負ok = abs(投["共同負擔"] / 期望共負 - 1) <= 0.005
    比ok = abs(投["共負比"] - 期望共負比) <= 0.005
    報酬ok = abs(投["報酬率"] - 期望報酬率) <= 0.005
    print(f"\n=== {鍵} L6（{範本模式[鍵]}）鎖定 ===")
    print(f"  {'✅' if 共負ok else '❌'} 共負 {投['共同負擔']:,.0f}（鎖 {期望共負:,.0f}）"
          f"　{'✅' if 比ok else '❌'} 共負比 {投['共負比']:.2%}（鎖 {期望共負比:.2%}）"
          f"　{'✅' if 報酬ok else '❌'} 報酬率 {投['報酬率']:.2%}（鎖 {期望報酬率:.2%}）")
    return 共負ok and 比ok and 報酬ok


def 測試合約():
    """vNext：驗證 Project JSON 合約（英文 key）— 案例C 完整 pipeline → schema 驗證。

    確保「內部中文 calc → 對外英文合約」映射正確，且通過 schemas/project_schema.json。
    這是 Dashboard / Simulator / AI 消費的唯一資料格式，必須鎖回歸。
    """
    鍵 = "案例C（防災都更）"
    P = dict(範本參數[鍵])
    records = 範本樓層表(鍵).to_dict("records")
    容 = calc_容積查核(P, records)
    坪 = calc_坪效(容["允建容積"], 容["陽台免計面積"], P["公設比"])
    p = _建p(P)
    投 = calc_投報全案(坪["銷售坪數"], 容["總樓地板面積"] / 3.3058, p, 範本模式[鍵])
    前 = calc_更新前價值(P["基地面積"], 52.0, 既有建物面積=2000.0, 建物單價=10.0, 屋齡=40)

    # owners：一組故意持分加總偏離 1（0.9）的測資，驗證一致性自檢會抓到
    owners_bad = [
        {"owner_id": "T01", "land_share": 0.5, "pre_building_area_sqm": 0,
         "pre_value": 1000.0, "consent": "agreed"},
        {"owner_id": "T02", "land_share": 0.4, "pre_building_area_sqm": 0,
         "pre_value": 1000.0, "consent": "pending"},
    ]

    proj = build_project_json(P, 容, 坪, 投, 前,
                              案件類型=範本案件類型[鍵], 獎勵拆解=範本獎勵拆解[鍵],
                              投報模式=範本模式[鍵], owners=owners_bad,
                              computed_at="2026-07-01T00:00:00+00:00")
    r = proj["result"]
    碼集 = {w["code"] for w in r["warnings"]}

    print("\n=== vNext Project JSON 合約（schema v1.1） ===")
    檢查 = [
        ("schema_version=1.1", proj["schema_version"] == "1.1"),
        ("renewal_type=urban_renewal", proj["project"]["renewal_type"] == "urban_renewal"),
        ("allow_floor_area≈4017.60", 近似(r["allow_floor_area"], 4017.60, 0.5)),
        ("used_floor_area≈4049.52", 近似(r["used_floor_area"], 4049.52, 0.5)),
        ("efficiency_ratio≈1.691", 近似(r["efficiency_ratio"], 1.691, 0.02)),
        ("shared_cost_ratio 合理(0–1)", 0 < r["shared_cost_ratio"] < 1),
        ("pre_renewal_value 存在", "pre_renewal_value" in r),
        ("value_multiple 存在", "value_multiple" in r),
        # v1.1 欄位
        ("computed_at 原樣傳遞", r["computed_at"] == "2026-07-01T00:00:00+00:00"),
        ("core_version 存在", isinstance(r.get("core_version"), str) and len(r["core_version"]) > 0),
        # warnings：案例C 容積餘量為負（-31.92）必須抓到 VOLUME_EXCEEDED
        ("warnings 含 VOLUME_EXCEEDED", "VOLUME_EXCEEDED" in 碼集),
        # owners_bad 的 land_share 合計=0.9（偏離1超過3%容差）必須抓到
        ("warnings 含 OWNERS_SHARE_MISMATCH", "OWNERS_SHARE_MISMATCH" in 碼集),
        ("owners 陣列原樣輸出 2 筆", len(proj["owners"]) == 2),
    ]
    合約過 = all(ok for _, ok in 檢查)
    for 名, ok in 檢查:
        print(f"  {'✅' if ok else '❌'} {名}")

    # 若有 jsonschema，做真正的 schema 驗證（無則跳過、不擋測試）
    try:
        import json
        import jsonschema
        with open("schemas/project_schema.json", encoding="utf-8") as f:
            schema = json.load(f)
        jsonschema.validate(proj, schema)
        print("  ✅ jsonschema 驗證通過（schemas/project_schema.json）")
    except ModuleNotFoundError:
        print("  ⚠️ 未安裝 jsonschema，略過 schema 驗證（pip install jsonschema 可啟用）")
    except Exception as e:
        print(f"  ❌ schema 驗證失敗：{e}")
        合約過 = False

    return 合約過


def main():
    結果 = []

    過, _ = 跑("案例A（都更・全案管理）", {"基準容積FA": 4480.00, "允建容積": 7616.00,
                                    "安全梯上限": 1142.40, "陽台免計面積": 649.00,
                                    "計入容積_修正後": 7616.20, "容積餘量": -0.20})
    結果.append(("案例A", 過))

    過, _ = 跑("案例B（危老）", {"允建容積": 4177.92, "梯廳超出": 30.80,
                            "計入容積_修正後": 4210.80, "容積餘量": -32.88})
    結果.append(("案例B", 過))

    過, C = 跑("案例C（防災都更）", {"基準容積FA": 2160.00, "允建容積": 4017.60,
                               "安全梯上限": 602.64, "陽台超出": 29.40, "梯廳超出": 2.12,
                               "計入容積_修正後": 4049.52, "容積餘量": -31.92})
    結果.append(("案例C", 過))

    過, _ = 跑("案例D（危老・合建）", {"基準容積FA": 3600.00, "允建容積": 6120.00,
                                "安全梯上限": 918.00, "陽台免計面積": 693.00,
                                "計入容積_修正後": 6157.50, "容積餘量": -37.50})
    結果.append(("案例D", 過))

    # L6 純迴歸鎖定（合成案例；防財務層被改壞）
    結果.append(("案例D投報", 測試投報鎖定("案例D（危老・合建）", 149230, 0.6600, 0.5150)))
    結果.append(("案例A投報", 測試投報鎖定("案例A（都更・全案管理）", 151252, 0.5592, 0.7882)))

    # vNext：Project JSON 合約（英文 key + schema 驗證）
    結果.append(("JSON合約", 測試合約()))

    print("\n" + "=" * 42)
    for 名, 過 in 結果:
        print(f"  {'✅ PASS' if 過 else '❌ FAIL'}  {名}")

    # 銷坪比（案例C，含雙重超出）
    坪 = calc_坪效(C["允建容積"], C["陽台免計面積"], 0.33, 外皮係數=1.0)
    print(f"\n  案例C銷坪比（外皮1.0）= {坪['銷坪比']:.3f}")
    print(f"  案例C安全梯總量 = {C['安全梯總量']:.2f}（上限 {C['安全梯上限']:.2f}）")

    assert all(過 for _, 過 in 結果), "有案例未通過！"
    print("\n  🎉 全部 PASS")


def test_golden():
    """pytest 進入點（P1-2 一鍵化）：pytest 直接收集此函式。"""
    main()


if __name__ == "__main__":
    main()
