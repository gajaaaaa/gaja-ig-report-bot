Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Instagram Report Bot - Startup Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Activate virtual environment
Write-Host "[1/3] Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Update dependencies
Write-Host ""
Write-Host "[2/3] Installing/Updating dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt --upgrade

# Run the bot
Write-Host ""
Write-Host "[3/3] Starting the bot..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Bot is starting... Check bot.log for logs." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the bot." -ForegroundColor Green
Write-Host ""
python main.py

