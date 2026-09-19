@echo off
REM Genera el .exe detectando Python e instalando lo necesario para el build.
cd /d "%~dp0\.."
echo ============================================================
echo   Los Pocitos Azufrados - Generador de EXE
echo ============================================================
echo.

:: Detectar Python - primero ruta directa, luego PATH
set PYTHON_EXE=
if exist "C:\Users\julianr\AppData\Local\Python\bin\python.exe" (
    set PYTHON_EXE=C:\Users\julianr\AppData\Local\Python\bin\python.exe
    goto python_ok
)
if exist "C:\Python313\python.exe" (
    set PYTHON_EXE=C:\Python313\python.exe
    goto python_ok
)
if exist "C:\Python312\python.exe" (
    set PYTHON_EXE=C:\Python312\python.exe
    goto python_ok
)
if exist "C:\Python311\python.exe" (
    set PYTHON_EXE=C:\Python311\python.exe
    goto python_ok
)
:: Intentar python en PATH (excluye el stub de Windows Store)
for /f "delims=" %%i in ('where python 2^>nul') do (
    echo %%i | findstr /i "WindowsApps" >/dev/null
    if errorlevel 1 (
        if not defined PYTHON_EXE set PYTHON_EXE=%%i
    )
)

if not defined PYTHON_EXE (
    echo ERROR: Python no encontrado.
    echo Instala Python 3.9+ desde https://www.python.org/downloads/
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

:python_ok
echo Python encontrado: %PYTHON_EXE%
%PYTHON_EXE% --version

:: Instalar PyInstaller si no esta
%PYTHON_EXE% -m pip show pyinstaller >/dev/null 2>&1
if errorlevel 1 (
    echo Instalando PyInstaller...
    %PYTHON_EXE% -m pip install pyinstaller
)

:: Instalar Pillow para convertir logo PNG -> ICO
%PYTHON_EXE% -m pip show Pillow >/dev/null 2>&1
if errorlevel 1 (
    echo Instalando Pillow...
    %PYTHON_EXE% -m pip install Pillow
)

:: Convertir logo PNG a ICO
echo Convirtiendo logo a .ico...
%PYTHON_EXE% -c "from PIL import Image; img = Image.open('logo-los-pocitos-azufrados.png'); img.save('logo-los-pocitos-azufrados.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]); print('Logo .ico creado.')" 2>/dev/null
if errorlevel 1 (
    echo AVISO: No se pudo convertir el logo. El .exe usara icono generico.
)

:: Instalar dependencias del proyecto
echo.
echo Instalando dependencias del proyecto...
%PYTHON_EXE% -m pip install -r requirements.txt

:: Limpiar builds anteriores
echo.
echo Limpiando builds anteriores...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

:: Verificar que existe el .spec
if not exist pocitos.spec (
    echo ERROR: No se encontro pocitos.spec en la raiz del proyecto.
    pause
    exit /b 1
)

:: Construir el .exe
echo.
echo Construyendo el ejecutable...
echo (Esto puede tomar 2-5 minutos)
echo.
%PYTHON_EXE% -m PyInstaller pocitos.spec --clean

if errorlevel 1 (
    echo.
    echo ERROR: La construccion fallo. Revisa los mensajes arriba.
    pause
    exit /b 1
)

:: Crear carpetas necesarias dentro del dist
if not exist "dist\PocitosAzufrados\data" mkdir "dist\PocitosAzufrados\data"
if not exist "dist\PocitosAzufrados\data\recibos" mkdir "dist\PocitosAzufrados\data\recibos"
if not exist "dist\PocitosAzufrados\logs" mkdir "dist\PocitosAzufrados\logs"

:: Copiar scripts de inicio al dist
copy INICIAR.bat "dist\PocitosAzufrados\INICIAR.bat" >/dev/null
copy INSTALAR.bat "dist\PocitosAzufrados\INSTALAR.bat" >/dev/null 2>&1

echo.
echo ============================================================
echo   BUILD EXITOSO
echo ============================================================
echo.
echo El sistema listo para distribuir esta en:
echo   dist\PocitosAzufrados\
echo.
echo PASOS PARA INSTALAR EN EL CLIENTE:
echo   1. Copiar la carpeta dist\PocitosAzufrados\ al PC del cliente
echo   2. El cliente ejecuta: PocitosAzufrados.exe  (primera vez)
echo      O doble clic en INICIAR.bat
echo   3. La primera vez creara la base de datos automaticamente
echo.
pause
