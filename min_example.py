# -*- coding: utf-8 -*-
"""P1-1 最小可跑範例：讀合成 JSON → core 計算 → 印出合約 result（10 行內）。"""
import json
from core import calc_容積查核, calc_坪效, build_project_json

案 = json.load(open("schemas/examples/min_input.json", encoding="utf-8"))
P, 樓層 = 案["參數"], 案["樓層"]
容 = calc_容積查核(P, 樓層)
坪 = calc_坪效(容["允建容積"], 容["陽台免計面積"], P["公設比"])
proj = build_project_json(P, 容, 坪, 案件類型=P["案件類型"])
print(json.dumps(proj["result"], ensure_ascii=False, indent=2))
