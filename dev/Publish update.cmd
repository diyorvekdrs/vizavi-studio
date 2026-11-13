@echo off
rem Publishes the current code as a new Vizavi Studio version for everyone (needs git + GitHub CLI, logged in).
cd /d "%~dp0.."
echo.
echo   Publish a new Vizavi Studio version
echo   -----------------------------------
set /p NOTES=  What's new (one line, shown to your friends): 
set KIND=patch
set /p KIND=  Version step [patch / minor / major] (Enter = patch): 
py -3 "%~dp0publish_update.py" %KIND% --notes "%NOTES%"
echo.
pause
