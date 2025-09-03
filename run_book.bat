@echo off
setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
  echo [INFO] Criando venv...
  py -m venv .venv
)

.\.venv\Scripts\python.exe -m pip --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
  echo [INFO] Atualizando pip/setuptools/wheel...
  .\.venv\Scripts\python.exe -m pip install -U pip setuptools wheel
)

.\.venv\Scripts\python.exe -c "import pkgutil,sys;req=['typer','requests','bs4','lxml','tenacity','PIL','ebooklib','readability_lxml','pytest'];missing=[r for r in req if not pkgutil.find_loader(r)];sys.exit(1 if missing else 0)" >nul 2>&1
if %ERRORLEVEL% neq 0 (
  echo [INFO] Instalando dependencias do requirements.txt...
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
)

:menu
echo.
echo ================== Gerar EPUB: Lorde dos Misterios ==================
echo  [1] Livro 01 – Clown (1-65)
echo  [2] Livro 02 – Magician (66-141)
echo  [3] Livro 03 – Seer (142-222)
echo  [4] Livro 04 – Hero (223-322)
echo  [5] Livro 05 – Bizarro Sorcerer (323-390)
echo  [6] Livro 06 – Hanged Man (391-533)
echo  [7] Livro 07 – Fool (534-680)
echo  [8] Livro 08 – Resonance (681-849)
echo  [9] Livro 09 – Mystery Pryer (850-1029)
echo  [10] Livro 10 – Apocalypse (1030-1394)
echo  [C] Custom (inserir faixa ex.: 441-480)
echo  [A] Todos (6 a 10)
echo  [S] Sair
echo =====================================================================
set /p choice=Escolha uma opcao: 

if /I "%choice%"=="1" set RANGE=1-65& set BOOK=01& set NAME=Clown& goto run
if /I "%choice%"=="2" set RANGE=66-141& set BOOK=02& set NAME=Magician& goto run
if /I "%choice%"=="3" set RANGE=142-222& set BOOK=03& set NAME=Seer& goto run
if /I "%choice%"=="4" set RANGE=223-322& set BOOK=04& set NAME=Hero& goto run
if /I "%choice%"=="5" set RANGE=323-390& set BOOK=05& set NAME=Bizarro_Sorcerer& goto run
if /I "%choice%"=="6" set RANGE=391-533& set BOOK=06& set NAME=Hanged_Man& goto run
if /I "%choice%"=="7" set RANGE=534-680& set BOOK=07& set NAME=Fool& goto run
if /I "%choice%"=="8" set RANGE=681-849& set BOOK=08& set NAME=Resonance& goto run
if /I "%choice%"=="9" set RANGE=850-1029& set BOOK=09& set NAME=Mystery_Pryer& goto run
if /I "%choice%"=="10" set RANGE=1030-1394& set BOOK=10& set NAME=Apocalypse& goto run
if /I "%choice%"=="A" goto run_all
if /I "%choice%"=="C" goto custom
if /I "%choice%"=="S" goto end

echo Opcao invalida.
goto menu

:run
echo [INFO] Gerando Livro !BOOK! (!RANGE!)...
.\.venv\Scripts\python.exe -m ldm_kindler.cli --range-str !RANGE! --out .\build --min-delay 2 --max-delay 5 --max-retries 4
if %ERRORLEVEL% neq 0 (
  echo [ERRO] Falha ao gerar o livro !BOOK! (!RANGE!).
  goto end
)
echo [OK] Concluido. Verifique .\build\

goto end

:: custom range
:custom
set /p RANGE=Informe a faixa (ex.: 441-480): 
if "%RANGE%"=="" (
  echo Faixa invalida.
  goto menu
)
echo [INFO] Gerando faixa personalizada %RANGE%...
.\.venv\Scripts\python.exe -m ldm_kindler.cli --range-str %RANGE% --out .\build --min-delay 2 --max-delay 5 --max-retries 4
if %ERRORLEVEL% neq 0 (
  echo [ERRO] Falha ao processar %RANGE%.
)
goto end

:run_all
for %%R in (1-65 66-141 142-222 223-322 323-390 391-533 534-680 681-849 850-1029 1030-1394) do (
  echo [INFO] Gerando faixa %%R...
  .\.venv\Scripts\python.exe -m ldm_kindler.cli --range-str %%R --out .\build --min-delay 2 --max-delay 5 --max-retries 4
  if !ERRORLEVEL! neq 0 (
    echo [ERRO] Falha ao processar %%R. Encerrando.
    goto end
  )
)
echo [OK] Todos concluidos. Verifique .\build\

goto end

:end
echo.
endlocal
exit /b 0
