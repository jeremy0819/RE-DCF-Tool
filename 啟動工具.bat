@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   RE-DCF-Tool  正在啟動...
echo   稍候瀏覽器會自動打開 http://localhost:8501
echo   要關閉：直接關掉這個黑色視窗，或按 Ctrl+C
echo ============================================
python -m streamlit run app.py
echo.
echo (若出現紅字錯誤，把訊息截圖給我)
pause
