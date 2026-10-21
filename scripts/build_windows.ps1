$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
python -m PyInstaller --noconfirm --clean --windowed --onedir --name Rainymine --icon assets\rainymine.ico --collect-all vtkmodules --hidden-import vtkmodules.qt.QVTKRenderWindowInteractor --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module PySide2 --add-data "examples;examples" --add-data "assets;assets" main.py
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed' }
Copy-Item README.md dist\Rainymine\README.md
Copy-Item Rainymine-Software.bat dist\Rainymine\Rainymine-Software.bat
if (Test-Path software-rendering) { Copy-Item software-rendering dist\Rainymine\software-rendering -Recurse -Force }
Copy-Item examples dist\Rainymine\examples -Recurse -Force
$proc = Start-Process -FilePath '.\dist\Rainymine\Rainymine.exe' -ArgumentList '--smoke' -PassThru
if (-not $proc.WaitForExit(60000)) { $proc.Kill(); throw 'Packaged app smoke test timed out' }
if ($proc.ExitCode -ne 0) { throw "Packaged app smoke test failed: $($proc.ExitCode)" }
Compress-Archive -Path dist\Rainymine -DestinationPath dist\Rainymine-0.1.0-Windows-x64.zip -Force
Write-Host 'Portable package ready: dist\Rainymine-0.1.0-Windows-x64.zip'
