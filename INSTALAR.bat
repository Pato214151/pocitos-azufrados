@echo off
echo ============================================
echo   CLUB LOS POCITOS AZUFRADOS
echo   Instalacion del Sistema POS
echo ============================================
echo.

:: Buscar Python en rutas comunes
set PYTHON_EXE=
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe
if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"  set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python39\python.exe
if exist "C:\Python312\python.exe" set PYTHON_EXE=C:\Python312\python.exe
if exist "C:\Python311\python.exe" set PYTHON_EXE=C:\Python311\python.exe
if exist "C:\Python310\python.exe" set PYTHON_EXE=C:\Python310\python.exe

if "%PYTHON_EXE%"=="" (
    python --version >nul 2>&1
    if not errorlevel 1 set PYTHON_EXE=python
)

echo [1/3] Verificando Python...
if "%PYTHON_EXE%"=="" (
    echo.
    echo ERROR: Python no esta instalado.
    echo.
    echo Descarga Python 3.10 o superior desde:
    echo   https://python.org/downloads
    echo.
    echo MUY IMPORTANTE: Al instalar, marca la casilla
    echo   "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
"%PYTHON_EXE%" --version
echo Python encontrado OK.
echo.

echo [2/3] Instalando dependencias...
"%PYTHON_EXE%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR al instalar dependencias.
    echo Verifica tu conexion a internet e intenta de nuevo.
    pause
    exit /b 1
)
echo Dependencias instaladas OK.
echo.

echo [3/3] Configurando base de datos...
"%PYTHON_EXE%" setup.py
if errorlevel 1 (
    echo.
    echo ERROR en la configuracion de la base de datos.
    pause
    exit /b 1
)
echo Base de datos lista.
echo.

echo ============================================
echo   INSTALACION COMPLETADA
echo   Ejecute INICIAR.bat para abrir el sistema
echo ============================================
echo.
pause
