param([switch]$Production)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
python -m nuitka --version
if ($LASTEXITCODE -ne 0) { throw 'Install and review Nuitka in the build environment first.' }
if ($Production) {
    python scripts/check_release_readiness.py --production
    if ($LASTEXITCODE -ne 0) { throw 'Production readiness preflight failed' }
}
python scripts/build_native.py
if ($LASTEXITCODE -ne 0) { throw 'Native build failed' }
python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
python -m nuitka --standalone --enable-plugin=pyside6 --windows-console-mode=disable --windows-icon-from-ico=assets/rainymine.ico --output-dir=dist-nuitka --output-filename=Rainymine.exe --include-package=vtkmodules --include-package=pyarrow --include-package=shapely --include-module=rainymine_core --include-data-dir=assets=assets --include-data-dir=examples=examples main.py
if ($LASTEXITCODE -ne 0) { throw 'Nuitka build failed' }
$target = 'dist-nuitka\main.dist\Rainymine.exe'
& "$PSScriptRoot\sign_windows.ps1" -Path $target -Required:$Production
Write-Host "Nuitka binary ready for separate Windows packaging/smoke validation: $target"
Write-Host 'Native compilation does not make reverse engineering or licence bypass impossible.'
