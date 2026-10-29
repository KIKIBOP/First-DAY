@echo off
setlocal
chcp 65001 >nul
"%~dp0runtime\python.exe" -I "%~dp0native-host\portable_check.py"
pause
