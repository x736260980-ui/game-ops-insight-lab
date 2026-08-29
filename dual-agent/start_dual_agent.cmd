@echo off
chcp 65001 >nul
python -X utf8 "%~dp0launch_dual_agent.py"
set EXIT_CODE=%ERRORLEVEL%
echo.
pause
exit /b %EXIT_CODE%
