# -*- coding: utf-8 -*-
"""
schemas/examples/generate_examples.py — 產生 Core 合約範例 JSON（供消費端壓測）
=====================================================
執行：python schemas/examples/generate_examples.py
輸出：schemas/examples/*.json（4 個範例，涵蓋都更/危老、三種投報模式、
      容積合規/超出、owners[] 有/無資料）

⚠️ 案件參數為 core/templates.py 已公開之範本資料（非真實案件 Excel 原始值，
   投報參數已依真實案例校準但案名/地號皆為範本代稱）；owners[] 除非明確標註
   「合成範例」，否則為空陣列。符合 CLAUDE.md：不含真實案件資料，可進版控。
"""

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import (
    calc_容積查核, calc_坪效, calc_更新前價值, calc_投報全案,
    build_project_json, 平方米換坪, 財務率預設,
    範本參數, 範本樓層表, 範本案件類型, 範本獎勵拆解, 範本模式,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
COMPUTED_AT = "2026-07-01T00:00:00+00:00"  # 固定值，範例檔可重現、不隨產生時間漂移


def _算(鍵):
    P = dict(範本參數[鍵])
    容 = calc_容積查核(P, 範本樓層表(鍵).to_dict("records"))
    坪 = calc_坪效(容["允建容積"], 容["陽台免計面積"], P["公設比"])
    p = {**財務率預設,
         **{k: P[k] for k in ("住宅單價", "店舖坪數", "店舖單價", "車位數", "車位單價",
                              "營造單價", "戶數", "權變戶數") if k in P},
         "土地成本": P.get("土融土地成本", 0.0)}
    p.update(P.get("財務覆寫", {}))
    投 = calc_投報全案(坪["銷售坪數"], 容["總樓地板面積"] / 平方米換坪, p, 範本模式[鍵])
    前 = (calc_更新前價值(P["基地面積"], P["地價"], P.get("既有建物面積", 0.0),
                       P.get("建物單價", 0.0), int(P.get("屋齡", 40)))
          if P.get("地價", 0) > 0 else None)
    return P, 容, 坪, 投, 前


def _寫(檔名, proj):
    path = os.path.join(OUT_DIR, 檔名)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(proj, f, ensure_ascii=False, indent=2)
    print(f"  ✅ {檔名}")


def main():
    print("產生 Core 合約範例（schema v1.1）...")

    # 1. 竹蓮段：危老＋合建模式，容積超出（VOLUME_EXCEEDED）、共負比超警示線（SHARED_COST_HIGH）
    鍵 = "竹蓮段（危老重建）"
    P, 容, 坪, 投, 前 = _算(鍵)
    proj = build_project_json(P, 容, 坪, 投, 前,
                              案件類型=範本案件類型[鍵], 獎勵拆解=範本獎勵拆解[鍵],
                              投報模式=範本模式[鍵], owners=[], computed_at=COMPUTED_AT)
    _寫("竹蓮段_危老合建.json", proj)

    # 2. 安和段（安民街）：都更＋全案管理模式，容積合規（無 VOLUME_EXCEEDED）
    鍵 = "安和段（都市更新）"
    P, 容, 坪, 投, 前 = _算(鍵)
    proj = build_project_json(P, 容, 坪, 投, 前,
                              案件類型=範本案件類型[鍵], 獎勵拆解=範本獎勵拆解[鍵],
                              投報模式=範本模式[鍵], owners=[], computed_at=COMPUTED_AT)
    _寫("安和段_都更全案管理.json", proj)

    # 3. 中正段：都更＋防災，容積超出＋銷坪比超帶（雙重 warning，測消費端多筆 warnings 顯示）
    鍵 = "中正段（防災都更）"
    P, 容, 坪, 投, 前 = _算(鍵)
    proj = build_project_json(P, 容, 坪, 投, 前,
                              案件類型=範本案件類型[鍵], 獎勵拆解=範本獎勵拆解[鍵],
                              投報模式=範本模式[鍵], owners=[], computed_at=COMPUTED_AT)
    _寫("中正段_都更防災_容積超出.json", proj)

    # 4. 合成範例：owners[] 有資料（48 戶，持分/更新前價值依竹蓮段 pre_renewal_value 等比分配）
    #    ⚠️ owners 為示範用合成資料，非真實地主清冊；持分刻意含一筆不同意戶示範 consent 欄位。
    鍵 = "竹蓮段（危老重建）"
    P, 容, 坪, 投, 前 = _算(鍵)
    戶數 = int(P["戶數"])
    更新前總值 = 前["更新前總值"] if 前 else 0.0
    owners = []
    consents = ["agreed"] * 34 + ["pending"] * 10 + ["opposed"] * 4  # 示意同意率 ~71%
    for i in range(戶數):
        owners.append({
            "owner_id": f"W{i + 1:02d}",
            "land_share": round(1.0 / 戶數, 6),
            "pre_building_area_sqm": round(前["建物坪"] * 平方米換坪 / 戶數, 2) if 前 else 0.0,
            "pre_value": round(更新前總值 / 戶數, 2),
            "consent": consents[i % len(consents)],
            "min_unit_eligible": True,
        })
    P合成 = dict(P)
    P合成["案件名稱"] = "（合成範例）owners 示範"
    proj = build_project_json(P合成, 容, 坪, 投, 前,
                              案件類型=範本案件類型[鍵], 獎勵拆解=範本獎勵拆解[鍵],
                              投報模式=範本模式[鍵], owners=owners, computed_at=COMPUTED_AT)
    _寫("合成範例_owners示範.json", proj)

    print(f"\n完成，共 4 個範例檔於 {OUT_DIR}")


if __name__ == "__main__":
    main()
