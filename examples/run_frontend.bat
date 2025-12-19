@echo off
REM 啟動 Streamlit 前端應用程式

echo ========================================
echo 啟動 Streamlit 前端應用程式
echo ========================================
echo.

REM 切換到前端目錄
cd /d "%~dp0frontend"

REM 啟動 Streamlit
streamlit run app.py

pause
