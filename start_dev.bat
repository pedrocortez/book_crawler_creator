@echo off
echo === Kindlemake Dev Server ===
echo.

start "API Backend" cmd /k ".venv\Scripts\uvicorn ldm_kindler.api:app --reload --port 8000"
echo [OK] Backend iniciando em http://localhost:8000

timeout /t 2 >nul

start "Vue Frontend" cmd /k "cd frontend && npm run dev"
echo [OK] Frontend iniciando em http://localhost:5173

echo.
echo Ambos os servidores iniciados. Pressione qualquer tecla para fechar este janela.
pause >nul
