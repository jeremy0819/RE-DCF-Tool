# -*- coding: utf-8 -*-
"""law_db.py — 相容 shim（DEPRECATED）。實體已搬至 core/law_db.py（P1-1 可攜性：
core/ 自含、搬目錄不斷）。新程式請 from core.law_db import …"""
from core.law_db import *          # noqa: F401,F403
from core.law_db import BONUS_都更, BONUS_危老, EXEMPTION_162, COMMON_BURDEN_RANGES  # noqa: F401
