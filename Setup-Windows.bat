@echo off
cd /d "%~dp0"
py -3.12 -m venv .venv
if errorlevel 1 py -3.11 -m venv .venv
if not exist ".venv\Scripts\python.exe" (
 echo Python 3.11 or 3.12 is required for source setup.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
 pause
 exit /b 1
)
echo Setup complete. Use Start-Windows.bat. Internet is not needed after setup.
pause
