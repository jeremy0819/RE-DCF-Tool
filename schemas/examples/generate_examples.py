# -*- coding: utf-8 -*-
"""
schemas/examples/generate_examples.py — 產生 Core 合約範例 JSON（供消費端壓測）
=====================================================
執行：python schemas/examples/generate_examples.py
輸出：schemas/examples/*.json（4 個範例，涵蓋都更/危老、全案管理/合建模式、
      各種 warnings 組合、owners[] 有/無資料）

⚠️ 去識別化聲明（合併前置 P0-1）：全部輸入來自 core/templates.py 的**合成案例**
   （案名為代號、數值為虛構擾動值），非任何真實案件原始數據之匯出。
   範例的用途是讓消費端壓測「格式與 warnings 觸發」，不是提供真實數字。
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
                       P.get("建物單價", 0.0), int(P.get("屋齡", 45)))
          if P.get("地價", 0) > 0 else None)
    return P, 容, 坪, 投, 前


def _寫(檔名, proj):
    path = os.path.join(OUT_DIR, 檔名)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(proj, f, ensure_ascii=False, indent=2)
    print(f"  ✅ {檔名}")


def main():
    print("產生 Core 合約範例（schema v1.1，全部合成資料）...")

    # 1. 案例D：危老＋合建，三重 warning（EFFICIENCY + VOLUME + SHARED_COST_HIGH）
    鍵 = "案例D（危老・合建）"
    P, 容, 坪, 投, 前 = _算(鍵)
    proj = build_project_json(P, 容, 坪, 投, 前,
                              案件類型=範本案件類型[鍵], 獎勵拆解=範本獎勵拆解[鍵],
                              投報模式=範本模式[鍵], owners=[], computed_at=COMPUTED_AT)
    _寫("合成案例D_危老合建.json", proj)

    # 2. 案例A：都更＋全案管理，容積剛好打滿的邊界（VOLUME 極小負值 + SHARED_COST_HIGH）
    鍵 = "案例A（都更・全案管理）"
    P, 容, 坪, 投, 前 = _算(鍵)
    proj = build_project_json(P, 容, 坪, 投, 前,
                              案件類型=範本案件類型[鍵], 獎勵拆解=範本獎勵拆解[鍵],
                              投報模式=範本模式[鍵], owners=[], computed_at=COMPUTED_AT)
    _寫("合成案例A_都更全案管理.json", proj)

    # 3. 案例C：都更＋防災，三 warning 組合（EFFICIENCY + VOLUME + SHARED_COST_LOW）
    鍵 = "案例C（防災都更）"
    P, 容, 坪, 投, 前 = _算(鍵)
    proj = build_project_json(P, 容, 坪, 投, 前,
                              案件類型=範本案件類型[鍵], 獎勵拆解=範本獎勵拆解[鍵],
                              投報模式=範本模式[鍵], owners=[], computed_at=COMPUTED_AT)
    _寫("合成案例C_防災都更_容積超出.json", proj)

    # 4. 案例D + owners[]：48 戶等比分配合成清冊（Σ 自檢乾淨通過；三種 consent 狀態）
    鍵 = "案例D（危老・合建）"
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
    P合成["案件名稱"] = "案例D（owners 示範）"
    proj = build_project_json(P合成, 容, 坪, 投, 前,
                              案件類型=範本案件類型[鍵], 獎勵拆解=範本獎勵拆解[鍵],
                              投報模式=範本模式[鍵], owners=owners, computed_at=COMPUTED_AT)
    _寫("合成案例D_owners示範.json", proj)

    print(f"\n完成，共 4 個範例檔於 {OUT_DIR}")


if __name__ == "__main__":
    main()
