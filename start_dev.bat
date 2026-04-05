@echo off
setlocal
REM Sempre roda a partir da pasta do repositório (evita .venv errado e uvicorn no cwd errado).
cd /d "%~dp0"

echo === Kindlemake Dev Server ===
echo.

start "API Backend" cmd /k ".venv\Scripts\uvicorn ldm_kindler.api:app --reload --host 127.0.0.1 --port 8000"
echo [OK] Backend: http://127.0.0.1:8000

timeout /t 2 >nul

start "Vue Frontend" powershell -NoExit -Command "Set-Location -LiteralPath '%~dp0frontend'; npm run dev"
echo [OK] Frontend: http://127.0.0.1:5173  (proxy /api -^> 127.0.0.1:8000)

echo.
echo Abra o frontend em 127.0.0.1 (nao apenas "localhost") se tiver erro de proxy.
pause >nul
