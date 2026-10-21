# Optional per-application software driver, never installed system-wide.
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
$archive = Join-Path $env:RUNNER_TEMP 'rainymine-mesa.7z'
$extract = Join-Path $env:RUNNER_TEMP 'rainymine-mesa'
Invoke-WebRequest -Uri 'https://github.com/pal1000/mesa-dist-win/releases/download/24.3.4/mesa3d-24.3.4-release-msvc.7z' -OutFile $archive
& 'C:\Program Files\7-Zip\7z.exe' x $archive "-o$extract" -y | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Mesa archive extraction failed' }
New-Item -ItemType Directory -Path software-rendering -Force | Out-Null
foreach ($dll in @('opengl32.dll','libglapi.dll','libgallium_wgl.dll')) {
  Copy-Item (Join-Path $extract "x64\$dll") software-rendering -Force
}
# Preserve all upstream notices and license files alongside the optional drivers.
Get-ChildItem $extract -Recurse -File | Where-Object { $_.Name -match '(?i)license|copying|notice|copyright' -or $_.Extension -eq '.txt' } | ForEach-Object {
  $relative = $_.FullName.Substring($extract.Length).TrimStart('\')
  $target = Join-Path 'software-rendering\notices' $relative
  New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force | Out-Null
  Copy-Item $_.FullName $target -Force
}
@'
Optional CPU OpenGL renderer: Mesa 24.3.4 / llvmpipe.
Upstream binary source: https://github.com/pal1000/mesa-dist-win/releases/tag/24.3.4
Mesa source and license: https://gitlab.freedesktop.org/mesa/mesa/-/tree/mesa-24.3.4
Use Rainymine-Software.bat to enable these per-application drivers.
These files do not replace any Windows system DLL.
'@ | Set-Content software-rendering\README.txt
