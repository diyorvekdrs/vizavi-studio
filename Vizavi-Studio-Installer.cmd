@echo off
rem Vizavi Studio - quick installer. Double-click me: I download the newest version from GitHub and install it.
title Vizavi Studio - quick install
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/diyorvekdrs/vizavi-studio/main/get.ps1 | iex"
if errorlevel 1 pause
