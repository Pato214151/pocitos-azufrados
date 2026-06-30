@echo off
title Los Pocitos Azufrados

:: Intentar ejecutar el .exe empaquetado primero
if exist "PocitosAzufrados.exe" (
    start "" "PocitosAzufrados.exe"
    exit /b 0
)

:: Buscar Python en rutas comunes de instalacion
set PYTHON_EXE=
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe
if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"  set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python39\python.exe
if exist "C:\Python312\python.exe" set PYTHON_EXE=C:\Python312\python.exe
if exist "C:\Python311\python.exe" set PYTHON_EXE=C:\Python311\python.exe
if exist "C:\Python310\python.exe" set PYTHON_EXE=C:\Python310\python.exe

:: Si no se encontro en ruta fija, intentar desde PATH
if "%PYTHON_EXE%"=="" (
    python --version >nul 2>&1
    if not errorlevel 1 set PYTHON_EXE=python
)

if "%PYTHON_EXE%"=="" (
    echo.
    echo ERROR: No se encontro Python instalado.
    echo.
    echo Descarga Python desde: https://python.org/downloads
    echo Marca la opcion "Add Python to PATH" al instalar.
    echo.
    echo Luego ejecuta este archivo de nuevo.
    pause
    exit /b 1
)

echo Iniciando Los Pocitos Azufrados...
"%PYTHON_EXE%" main.py
if errorlevel 1 (
    echo.
    echo Error al iniciar. Ejecute INSTALAR.bat primero.
    pause
)
