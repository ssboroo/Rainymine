param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ExpectedSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-fA-F0-9]{40}$')][string]$ExpectedSignerThumbprint,
    [switch]$Install
)
$ErrorActionPreference = 'Stop'
$file = Get-Item -LiteralPath $Installer
if ($file.Extension -ne '.exe') { throw 'Expected a Windows installer executable' }
if ((Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ne $ExpectedSha256) { throw 'Installer SHA256 mismatch' }
$signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -ne $ExpectedSignerThumbprint) { throw 'Installer signature or publisher identity mismatch' }
Write-Host 'Installer integrity and trusted signer verified.'
if ($Install) {
    $process = Start-Process -FilePath $file.FullName -PassThru -Wait
    if ($process.ExitCode -ne 0) { throw "Installer failed: $($process.ExitCode)" }
}
