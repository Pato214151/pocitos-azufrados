@echo off
cd /d "%~dp0\.."
setlocal

:: ============================================================
:: deploy.bat - Actualiza solo el ejecutable y los archivos
:: internos SIN tocar la base de datos de produccion.
:: Usar despues de correr scripts\build.bat en el PC de desarrollo.
:: ============================================================

set ORIGEN=dist\PocitosAzufrados
set DESTINO=C:\Users\julianr\OneDrive\PocitosAzufrados

echo.
echo ====================================================
echo  DEPLOY - Los Pocitos Azufrados
echo  Origen : %ORIGEN%
echo  Destino: %DESTINO%
echo ====================================================
echo.

:: Verificar que el build existe
if not exist "%ORIGEN%\PocitosAzufrados.exe" (
    echo ERROR: No se encontro el build en %ORIGEN%
    echo Corre primero scripts\build.bat
    pause
    exit /b 1
)

:: Verificar que el destino existe
if not exist "%DESTINO%" (
    echo ERROR: No se encontro la carpeta destino:
    echo %DESTINO%
    echo Verifica la ruta de OneDrive
    pause
    exit /b 1
)

:: Cerrar el exe en el destino si esta abierto
echo Cerrando ejecutable si esta abierto...
taskkill /F /IM PocitosAzufrados.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:: Copiar solo el .exe
echo Copiando PocitosAzufrados.exe ...
copy /Y "%ORIGEN%\PocitosAzufrados.exe" "%DESTINO%\PocitosAzufrados.exe"
if errorlevel 1 (
    echo ERROR al copiar el .exe
    pause
    exit /b 1
)

:: Copiar _internal\ completo (librerias compiladas)
echo Copiando _internal\ ...
robocopy "%ORIGEN%\_internal" "%DESTINO%\_internal" /E /IS /IT /NFL /NDL /NJH /NJS
if errorlevel 8 (
    echo ERROR al copiar _internal
    pause
    exit /b 1
)

:: Copiar templates y static de cocina web (por si cambiaron)
echo Copiando cocina_web\ ...
robocopy "%ORIGEN%\_internal\cocina_web" "%DESTINO%\_internal\cocina_web" /E /IS /IT /NFL /NDL /NJH /NJS

echo.
echo ====================================================
echo  Listo! Solo se actualizo el codigo.
echo  La base de datos de produccion NO fue tocada.
echo ====================================================
echo.
pause
