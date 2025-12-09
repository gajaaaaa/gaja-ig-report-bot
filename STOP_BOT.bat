@echo off
echo Stopping Instagram Report Bot...
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM pythonw.exe /T >nul 2>&1
echo Bot stopped!
pause

