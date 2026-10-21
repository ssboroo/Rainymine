$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
python -m PyInstaller --noconfirm --clean --windowed --onedir --name Rainymine --icon assets\rainymine.ico --collect-all vtkmodules --collect-data pyproj --collect-data ezdxf --hidden-import vtkmodules.qt.QVTKRenderWindowInteractor --hidden-import pyodbc --collect-submodules scipy.optimize --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module PySide2 --add-data "examples;examples" --add-data "assets;assets" main.py
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed' }
Copy-Item README.md dist\Rainymine\README.md
Copy-Item assets\AI-NOTICES.txt dist\Rainymine\AI-NOTICES.txt
Copy-Item assets\QWEN_MODEL_LICENSE.txt dist\Rainymine\QWEN_MODEL_LICENSE.txt
Copy-Item assets\LLAMA_CPP_LICENSE.txt dist\Rainymine\LLAMA_CPP_LICENSE.txt
New-Item -ItemType Directory -Path dist\Rainymine\ai -Force | Out-Null
Copy-Item ai\runtime dist\Rainymine\ai\runtime -Recurse -Force
# Reuse the MSVC redistributable DLLs already collected with Python/Qt.
foreach ($crtName in @('vcruntime140.dll','vcruntime140_1.dll','msvcp140.dll','concrt140.dll')) {
    $crt = Get-ChildItem dist\Rainymine\_internal -Recurse -Filter $crtName | Select-Object -First 1
    if ($crt) { Copy-Item $crt.FullName dist\Rainymine\ai\runtime\$crtName -Force }
}
Copy-Item Rainymine-Software.bat dist\Rainymine\Rainymine-Software.bat
if (Test-Path software-rendering) { Copy-Item software-rendering dist\Rainymine\software-rendering -Recurse -Force }
Copy-Item examples dist\Rainymine\examples -Recurse -Force
$proc = Start-Process -FilePath '.\dist\Rainymine\Rainymine.exe' -ArgumentList '--smoke' -PassThru
if (-not $proc.WaitForExit(180000)) { $proc.Kill(); throw 'Packaged app smoke test timed out' }
if ($proc.ExitCode -ne 0) { throw "Packaged app smoke test failed: $($proc.ExitCode)" }
Compress-Archive -Path dist\Rainymine -DestinationPath dist\Rainymine-0.5.0-Windows-x64.zip -Force
Write-Host 'Portable package ready: dist\Rainymine-0.5.0-Windows-x64.zip'

if (Test-Path ai\models) {
    Copy-Item ai\models dist\Rainymine\ai\models -Recurse -Force
    Compress-Archive -Path dist\Rainymine -DestinationPath dist\Rainymine-0.5.0-AI-Offline-x64.zip -CompressionLevel Fastest -Force
    Remove-Item dist\Rainymine\ai\models -Recurse -Force
    Write-Host 'Full offline AI portable package ready.'
}
