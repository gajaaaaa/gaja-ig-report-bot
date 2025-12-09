@echo off
echo ========================================
echo Instagram Report Bot - Startup Script
echo ========================================
echo.

REM Activate virtual environment
echo [1/3] Activating virtual environment...
call venv\Scripts\activate.bat

REM Update dependencies
echo.
echo [2/3] Installing/Updating dependencies...
pip install -r requirements.txt --upgrade

REM Run the bot
echo.
echo [3/3] Starting the bot...
echo.
echo Bot is starting... Check bot.log for logs.
echo Press Ctrl+C to stop the bot.
echo.
python main.py

pause

