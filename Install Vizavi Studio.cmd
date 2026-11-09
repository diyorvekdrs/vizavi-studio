@echo off
rem Vizavi Studio installer - double-click me.
if not exist "%~dp0app\setup\install.ps1" goto noextract
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\setup\install.ps1" -Source "%~dp0app"
if errorlevel 1 pause
exit /b
:noextract
echo.
echo   Please extract the zip first:
echo   right-click the zip, choose "Extract All...", open the extracted folder
echo   and double-click "Install Vizavi Studio" there.
echo.
pause
