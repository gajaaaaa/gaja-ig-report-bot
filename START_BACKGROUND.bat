@echo off
echo ========================================
echo Instagram Report Bot - Background Mode
echo ========================================
echo.
echo Bot will run in background...
echo Check bot.log for logs.
echo.

REM Activate virtual environment
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    python -m venv venv
    call venv\Scripts\activate.bat
)

REM Install dependencies
pip install -r requirements.txt --upgrade >nul 2>&1

REM Run bot in background using pythonw (no window)
start /B pythonw main.py

echo Bot started in background!
echo.
echo To stop the bot, use Task Manager or:
echo taskkill /F /IM pythonw.exe
echo.
pause

