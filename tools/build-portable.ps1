param(
    [switch]$SkipAppBuild
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$builtExe = Join-Path $projectRoot "dist\SafeRide-Portable-x64.exe"

if (-not $SkipAppBuild) {
    & (Join-Path $PSScriptRoot "build.ps1") -Target Portable
}
if (-not (Test-Path -LiteralPath $builtExe)) {
    throw "Portable SafeRide build is missing: $builtExe"
}

$releaseDir = Join-Path $projectRoot "release"
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
$portableExe = Join-Path $releaseDir "SafeRide-Portable-x64.exe"
Copy-Item -LiteralPath $builtExe -Destination $portableExe -Force

$checksum = (Get-FileHash -LiteralPath $portableExe -Algorithm SHA256).Hash
$checksumFile = Join-Path $releaseDir "SafeRide-Portable-x64.sha256.txt"
[System.IO.File]::WriteAllText($checksumFile, "$checksum  SafeRide-Portable-x64.exe`r`n")

Write-Host "Portable EXE complete: $portableExe" -ForegroundColor Green
Write-Host "No installation or administrator rights are required." -ForegroundColor Green
Write-Host "SHA-256: $checksum" -ForegroundColor Green
