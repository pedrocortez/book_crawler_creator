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
echo =============== Fonte de conteudo ===============
echo  [1] LOM (Lorde dos Misterios) - presets de livros 1 a 10
echo  [2] URL customizada - informar URL, titulo e autor
echo  [S] Sair
echo ================================================
set /p SRC=Escolha a fonte: 
if /I "%SRC%"=="1" goto lom_menu
if /I "%SRC%"=="2" goto custom_mode
if /I "%SRC%"=="S" goto end
echo Opcao invalida.
goto main

:lom_menu
echo.
echo ================== Gerar EPUB: Lorde dos Misterios ==================
echo  [1] Livro 01  Clown (1-65)
echo  [2] Livro 02  Magician (66-141)
echo  [3] Livro 03  Seer (142-222)
echo  [4] Livro 04  Hero (223-322)
echo  [5] Livro 05  Bizarro Sorcerer (323-390)
echo  [6] Livro 06 Hanged Man (391-533)
echo  [7] Livro 07 Fool (534-680)
echo  [8] Livro 08 Resonance (681-849)
echo  [9] Livro 09 Mystery Pryer (850-1029)
echo  [10] Livro 10 Apocalypse (1030-1394)
echo  [C] Custom (inserir faixa ex.: 441-480)
echo  [A] Todos (1 a 10)
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
if /I "%choice%"=="9" set RANGE=850-1029& goto run_lom
if /I "%choice%"=="10" set RANGE=1030-1394& goto run_lom
if /I "%choice%"=="A" goto run_all_lom
if /I "%choice%"=="C" goto custom_range_lom
if /I "%choice%"=="V" goto main

echo Opcao invalida.
goto lom_menu

:run_lom
echo [INFO] Gerando faixa !RANGE! (LOM)...
.\.venv\Scripts\python.exe -m ldm_kindler.cli --range-str !RANGE! --out .\build --min-delay 2 --max-delay 5 --max-retries 4
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
for %%R in (1-65 66-141 142-222 223-322 323-390 391-533 534-680 681-849 850-1029 1030-1394) do (
  echo [INFO] Gerando faixa %%R (LOM)...
  .\.venv\Scripts\python.exe -m ldm_kindler.cli --range-str %%R --out .\build --min-delay 2 --max-delay 5 --max-retries 4
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
  goto main
)
set /p SERIES=Titulo da serie (ex.: Minha Serie): 
if "%SERIES%"=="" set SERIES=Serie
set /p AUTHOR=Autor (ex.: Autor Desconhecido): 
if "%AUTHOR%"=="" set AUTHOR=Autor Desconhecido
set /p RANGE=Faixa de capitulos (ex.: 1-50): 
if "%RANGE%"=="" (
  echo Faixa invalida.
  goto main
)
echo [INFO] Gerando faixa %RANGE% (Custom)...
.\.venv\Scripts\python.exe -m ldm_kindler.cli --range-str %RANGE% --url-template "%URLT%" --series-title "%SERIES" --author "%AUTHOR%" --out .\build --min-delay 2 --max-delay 5 --max-retries 4
if %ERRORLEVEL% neq 0 (
  echo [ERRO] Falha ao processar %RANGE%.
  goto end
)
echo [OK] Concluido. Verifique .\build\
goto end

:end
echo.
endlocal
exit /b 0
