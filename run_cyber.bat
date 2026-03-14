@echo off
title GOD-EYE — Data Center Ops
color 0B
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║   ░██████╗░░█████╗░██████╗░       ███████╗██╗░░░██╗███████╗  ║
echo  ║  ██╔════╝░██╔══██╗██╔══██╗      ██╔════╝╚██╗░██╔╝██╔════╝  ║
echo  ║  ██║░░██╗░██║░░██║██║░░██║█████╗█████╗░░░╚████╔╝░█████╗░░  ║
echo  ║  ██║░░╚██╗██║░░██║██║░░██║╚════╝██╔══╝░░░░╚██╔╝░░██╔══╝░░  ║
echo  ║  ╚██████╔╝╚█████╔╝██████╔╝      ███████╗░░░██║░░░███████╗  ║
echo  ║   ╚═════╝░░╚════╝░╚═════╝       ╚══════╝░░░╚═╝░░░╚══════╝  ║
echo  ╚══════════════════════════════════════════════════════╝
echo.
echo  [ Installing / verifying dependencies... ]
py -m pip install fastapi uvicorn psutil pandas numpy scikit-learn --quiet
echo.
echo  [ Launching GOD-EYE at http://localhost:8000 ]
echo.
start "" "http://localhost:8000"
py main.py
pause
