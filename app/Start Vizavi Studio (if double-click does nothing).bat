@echo off
rem Fallback launcher: the app's own Python first, then the Python launcher, then pythonw on PATH.
if exist "%~dp0.venv\Scripts\pythonw.exe" (start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0Vizavi Studio.pyw" %*& exit /b)
where pyw >nul 2>nul && (start "" pyw -3 "%~dp0Vizavi Studio.pyw" %*) || (start "" pythonw "%~dp0Vizavi Studio.pyw" %*)
