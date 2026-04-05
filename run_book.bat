@echo off
setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

cd /d "%~dp0"

REM Venv
if not exist .venv\Scripts\python.exe (
  echo [INFO] Criando venv...
  py -m venv .venv
)

.\.venv\Scripts\python.exe -m pip --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
  echo [INFO] Atualizando pip/setuptools/wheel...
  .\.venv\Scripts\python.exe -m pip install -U pip setuptools wheel
)

.\.venv\Scripts\python.exe -c "import pkgutil,sys;req=['typer','requests','bs4','lxml','tenacity','PIL','ebooklib','readability_lxml','pytest','rich'];missing=[r for r in req if not pkgutil.find_loader(r)];sys.exit(1 if missing else 0)" >nul 2>&1
if %ERRORLEVEL% neq 0 (
  echo [INFO] Instalando dependencias do requirements.txt...
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
)

:main
echo.
goto custom_mode

:lom_menu
echo.
echo ================== Gerar: Lorde dos Misterios ==================
echo  [1] Livro 01  O Mago (1-185)
echo  [2] Livro 02  O Louco (186-381)
echo  [3] Livro 03  O Viajante (382-732)
echo  [4] Livro 04  O Imperador (733-789)
echo  [5] Livro 05  O Louco dos Ventos (790-961)
echo  [6] Livro 06  O Eremita (962-1145)
echo  [7] Livro 07  O Enforcado (1146-1353)
echo  [8] Livro 08  O Sol (1354-1436)
echo  [C] Custom (inserir faixa ex.: 441-480)
echo  [A] Todos (1 a 8)
echo  [V] Voltar
echo =====================================================================
set /p choice=Escolha uma opcao: 

if /I "%choice%"=="1" set RANGE=1-65& goto run_lom
if /I "%choice%"=="2" set RANGE=66-141& goto run_lom
if /I "%choice%"=="3" set RANGE=142-222& goto run_lom
if /I "%choice%"=="4" set RANGE=223-322& goto run_lom
if /I "%choice%"=="5" set RANGE=323-390& goto run_lom
if /I "%choice%"=="6" set RANGE=391-533& goto run_lom
if /I "%choice%"=="7" set RANGE=534-680& goto run_lom
if /I "%choice%"=="8" set RANGE=681-849& goto run_lom
if /I "%choice%"=="A" goto run_all_lom
if /I "%choice%"=="C" goto custom_range_lom
if /I "%choice%"=="V" goto main

echo Opcao invalida.
goto lom_menu

:run_lom
call :ask_format
echo [INFO] Gerando faixa !RANGE! (LOM) formato %FORMAT%...
.\.venv\Scripts\python.exe -m ldm_kindler.cli --range-str !RANGE! --out .\build --min-delay 2 --max-delay 5 --max-retries 4 %FMT_ARG%
if %ERRORLEVEL% neq 0 (
  echo [ERRO] Falha ao gerar LOM !RANGE!.
  goto end
)
echo [OK] Concluido. Verifique .\build\
goto end

:custom_range_lom
set /p RANGE=Informe a faixa (ex.: 441-480): 
if "%RANGE%"=="" (
  echo Faixa invalida.
  goto lom_menu
)
goto run_lom

:run_all_lom
call :ask_format
for %%R in (1-185 186-381 382-732 733-789 790-961 962-1145 1146-1353 1354-1436) do (
  echo [INFO] Gerando faixa %%R (LOM)...
  .\.venv\Scripts\python.exe -m ldm_kindler.cli --range-str %%R --out .\build --min-delay 2 --max-delay 5 --max-retries 4 %FMT_ARG%
  if !ERRORLEVEL! neq 0 (
    echo [ERRO] Falha ao processar %%R. Encerrando.
    goto end
  )
)
echo [OK] Todos concluidos. Verifique .\build\
goto end

:custom_mode
echo.
echo ============== Modo URL customizada ==============
set /p URLT=URL template (use {id}, ex.: https://site/obra/capitulo-{id}): 
if "%URLT%"=="" (
  echo URL invalida.
  goto end
)
set /p SERIES=Titulo da serie (ex.: Minha Serie): 
if "%SERIES%"=="" set SERIES=Serie
set /p AUTHOR=Autor (ex.: Autor Desconhecido): 
if "%AUTHOR%"=="" set AUTHOR=Autor Desconhecido
set /p COVER=URL da imagem de capa (opcional): 
set /p RANGE=Faixa de capitulos (ex.: 1-50): 
if "%RANGE%"=="" (
  echo Faixa invalida.
  goto end
)
echo [INFO] Gerando faixa %RANGE% (Custom)...
set COVER_ARG=
if not "%COVER%"=="" set COVER_ARG= --cover-url "%COVER%"
call :ask_format
.\.venv\Scripts\python.exe -m ldm_kindler.cli --range-str %RANGE% --url-template "%URLT%" --series-title "%SERIES%" --author "%AUTHOR%" %COVER_ARG% --out .\build --min-delay 2 --max-delay 5 --max-retries 4 %FMT_ARG%
if %ERRORLEVEL% neq 0 (
  echo [ERRO] Falha ao processar %RANGE%.
  goto end
)
echo [OK] Concluido. Verifique .\build\
goto end

:ask_format
echo.
echo ================= Formato de saida =================
echo  [1] EPUB (padrao)
echo  [2] TXT
echo ====================================================
set /p FMT=Escolha o formato: 
if /I "%FMT%"=="2" (
  set FORMAT=txt
) else (
  set FORMAT=epub
)
set FMT_ARG= --format %FORMAT%
goto :eof

:end
echo.
endlocal
exit /b 0
