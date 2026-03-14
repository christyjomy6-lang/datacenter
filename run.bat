@echo off
title Data Center Dashboard
color 0A
echo.
echo  ██████╗  █████╗ ████████╗ █████╗      ██████╗███████╗███╗   ██╗████████╗███████╗██████╗ 
echo  ██╔══██╗██╔══██╗╚══██╔══╝██╔══██╗    ██╔════╝██╔════╝████╗  ██║╚══██╔══╝██╔════╝██╔══██╗
echo  ██║  ██║███████║   ██║   ███████║    ██║     █████╗  ██╔██╗ ██║   ██║   █████╗  ██████╔╝
echo  ██║  ██║██╔══██║   ██║   ██╔══██║    ██║     ██╔══╝  ██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗
echo  ██████╔╝██║  ██║   ██║   ██║  ██║    ╚██████╗███████╗██║ ╚████║   ██║   ███████╗██║  ██║
echo  ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝     ╚═════╝╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝
echo.
echo  Checking dependencies...
pip install -r requirements.txt --quiet
echo.
echo  Launching dashboard at http://localhost:8501
echo.
streamlit run dashboard.py --server.headless false --browser.gatherUsageStats false
pause
