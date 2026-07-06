#!/usr/bin/env bash
# 真實案件段名檢查（資料紀律紅線）。PASS=exit 0，FAIL=exit 1。
# 唯一允許含這些字串的檔案：本腳本、歷史乾淨度報告.md（稽核紀錄，僅 RE-DCF/docs 保存）。
# 用法：在 repo 根目錄執行  bash check_no_real_names.sh
set -u
FAIL=0
if grep -rnE "竹蓮|安和|安民|中正|龜山" \
     --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=node_modules \
     --exclude=check_no_real_names.sh --exclude=歷史乾淨度報告.md . ; then
  FAIL=1
fi
if find . -path ./.git -prune -o -print | grep -E "竹蓮|安和|安民|中正|龜山" ; then
  FAIL=1
fi
if [ "$FAIL" -eq 1 ]; then
  echo "FAIL：發現疑似真實段名（上列命中處需去識別化）"; exit 1
else
  echo "PASS：零命中"; exit 0
fi
