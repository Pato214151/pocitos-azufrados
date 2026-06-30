@echo off
title Cocina Web - Los Pocitos Azufrados
echo.
echo  Iniciando servidor de cocina para celular/tablet...
echo  (Este es un servidor local, no necesita internet)
echo.
cd /d "%~dp0"
python cocina_web\app.py
pause
