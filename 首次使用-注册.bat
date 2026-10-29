@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0register.ps1"
if errorlevel 1 echo Registration failed. Please read the message above.
pause
