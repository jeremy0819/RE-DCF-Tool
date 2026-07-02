# -*- coding: utf-8 -*-
"""core/_version.py — Core Engine 自身版本（獨立於 app.py 的 UI 版本號）。

CORE_VERSION 隨計算公式 / 合約結構變更而動；app.py 的 UI 版本（v4.x）隨介面變更而動，
兩者是不同軸線，不強制同步。消費端（Urban-Renewal 等）用 core_version 判斷是哪一版
公式算出的結果，不需要關心 UI 版本。
"""

CORE_VERSION = "0.2.0"
