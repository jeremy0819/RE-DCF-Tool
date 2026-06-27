# -*- coding: utf-8 -*-
"""
calc_engine.py — 相容層（DEPRECATED shim）
=====================================================
⚠️ 實際計算實作已於 vNext 搬遷至 core/ package（Urban Renewal Core Engine）。
本檔僅保留 re-export，讓既有 import（app.py / test_golden.py）不需修改。

新程式請直接：
    from core import calc_容積查核, calc_坪效, build_project_json, ...

模組對照：
    容積      → core/capacity.py
    坪效/評效 → core/efficiency.py
    投報      → core/finance.py
    更新前    → core/valuation.py
    合約      → core/contract.py
    範本      → core/templates.py
    I/O       → core/io.py
"""

# 整批 re-export core 公開介面（__all__ 控制範圍）
from core import *           # noqa: F401,F403
from core import __all__     # noqa: F401
