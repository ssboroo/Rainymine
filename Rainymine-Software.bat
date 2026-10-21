@echo off
cd /d "%~dp0"
set RAINYMINE_SOFTWARE=1
set GALLIUM_DRIVER=llvmpipe
if exist Rainymine.exe (
 start "" Rainymine.exe
 exit /b
)
if exist .venv\Scripts\python.exe (
 .venv\Scripts\python.exe main.py
 if errorlevel 1 pause
 exit /b
)
echo Use this launcher from the complete portable or installed Rainymine folder.
pause
