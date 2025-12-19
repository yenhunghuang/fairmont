@echo off
REM 啟動 FastAPI 後端伺服器

echo ========================================
echo 啟動 FastAPI 後端伺服器
echo ========================================
echo.

REM 切換到後端目錄
cd /d "%~dp0backend"

REM 啟動 uvicorn
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
