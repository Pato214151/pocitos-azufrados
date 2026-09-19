@echo off
REM Genera el ejecutable con PyInstaller (pocitos.spec) y copia la carpeta data.
cd /d "%~dp0\.."
echo Cerrando ejecutable si esta abierto...
taskkill /F /IM PocitosAzufrados.exe >nul 2>&1
timeout /t 3 /nobreak >nul

echo Liberando carpeta dist (forzado)...
powershell -NoProfile -Command "Remove-Item -Path 'dist\PocitosAzufrados' -Recurse -Force -ErrorAction SilentlyContinue"
timeout /t 1 /nobreak >nul

echo Construyendo ejecutable...
python -m PyInstaller pocitos.spec --noconfirm
if errorlevel 1 (
    echo ERROR en el build
    pause
    exit /b 1
)
echo Copiando base de datos...
xcopy /E /I /Y "data" "dist\PocitosAzufrados\data"
echo.
echo Listo! El ejecutable esta en dist\PocitosAzufrados\
pause
