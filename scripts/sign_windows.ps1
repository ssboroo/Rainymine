param(
    [Parameter(Mandatory=$true)][string]$Path,
    [switch]$Required
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Signing target does not exist: $Path" }
$thumbprint = $env:RAINYMINE_SIGN_THUMBPRINT
if (-not $thumbprint) {
    if ($Required) { throw 'Production requires RAINYMINE_SIGN_THUMBPRINT and its certificate/private key in the Windows certificate store.' }
    Write-Host "Unsigned preview: $Path"
    exit 0
}
if ($thumbprint -notmatch '^[0-9a-fA-F]{40}$') { throw 'Invalid certificate thumbprint' }
$certificate = Get-Item "Cert:\CurrentUser\My\$thumbprint"
if (-not $certificate.HasPrivateKey -or $certificate.NotAfter -le (Get-Date) -or $certificate.NotBefore -gt (Get-Date)) { throw 'Signing certificate is unavailable, not yet valid or expired' }
$codeSigningOid = '1.3.6.1.5.5.7.3.3'
if (-not ($certificate.EnhancedKeyUsageList | Where-Object { $_.ObjectId.Value -eq $codeSigningOid -or [string]$_.ObjectId -eq $codeSigningOid })) { throw 'Certificate does not explicitly permit code signing' }
$tool = Get-Command signtool.exe -ErrorAction SilentlyContinue
if ($tool) { $signTool = $tool.Source }
else {
    $signTool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" | Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $signTool) { throw 'Windows SDK signtool.exe is required' }
& $signTool sign /sha1 $thumbprint /fd SHA256 /tr 'http://timestamp.digicert.com' /td SHA256 $Path
if ($LASTEXITCODE -ne 0) { throw 'Authenticode signing failed' }
& $signTool verify /pa /all $Path
if ($LASTEXITCODE -ne 0) { throw 'Authenticode trust verification failed' }
$signature = Get-AuthenticodeSignature -LiteralPath $Path
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -ne $thumbprint) { throw 'Signer identity mismatch' }
if (-not $signature.TimeStamperCertificate) { throw 'A trusted timestamp is required for signed release artifacts' }
Write-Host "Verified signed artifact: $Path"
