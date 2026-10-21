@echo off
cd /d "%~dp0"
if exist "dist\Rainymine\Rainymine.exe" (
 start "" "dist\Rainymine\Rainymine.exe"
 exit /b
)
if not exist ".venv\Scripts\python.exe" (
 echo First run: install Python 3.11 or 3.12, then run Setup-Windows.bat.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
