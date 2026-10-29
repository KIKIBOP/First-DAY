@echo off
setlocal
cd /d "%~dp0\.."
py -3 -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
py -3 -m PyInstaller --noconfirm --clean --onefile --console --name MediaCollectorHost --distpath dist --workpath build --specpath build --paths native-host --collect-all PIL native-host\main.py
if errorlevel 1 exit /b 1
echo Build complete. Distribute the full project folder including dist\MediaCollectorHost.exe.
pause
