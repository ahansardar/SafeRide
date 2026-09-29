param(
    [switch]$SkipAppBuild
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$appExe = Join-Path $projectRoot "dist\SafeRide\SafeRide.exe"

if (-not $SkipAppBuild) {
    & (Join-Path $PSScriptRoot "build.ps1")
}
if (-not (Test-Path -LiteralPath $appExe)) {
    throw "SafeRide application build is missing: $appExe"
}

python (Join-Path $PSScriptRoot "create_icon.py")

$versionFile = Join-Path $projectRoot "version.py"
$versionMatch = Select-String -LiteralPath $versionFile -Pattern '^APP_VERSION\s*=\s*"(\d+\.\d+\.\d+)"$'
if (-not $versionMatch) {
    throw "Could not read APP_VERSION from $versionFile"
}
$appVersion = $versionMatch.Matches[0].Groups[1].Value

$compilerCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\InnoSetup6\ISCC.exe")
)
$compiler = $compilerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $compiler) {
    throw "Inno Setup 6 is required. Install JRSoftware.InnoSetup with winget, then rerun this script."
}

& $compiler "/DMyAppVersion=$appVersion" (Join-Path $projectRoot "installer\SafeRide.iss")
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compiler failed with exit code $LASTEXITCODE"
}

$installer = Join-Path $projectRoot "release\SafeRide-Setup-x64.exe"
if (-not (Test-Path -LiteralPath $installer)) {
    throw "Installer compiler did not create $installer"
}

$checksum = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash
$checksumFile = Join-Path $projectRoot "release\SafeRide-Setup-x64.sha256.txt"
[System.IO.File]::WriteAllText($checksumFile, "$checksum  SafeRide-Setup-x64.exe`r`n")

Write-Host "Installer complete: $installer" -ForegroundColor Green
Write-Host "Version: $appVersion" -ForegroundColor Green
Write-Host "SHA-256: $checksum" -ForegroundColor Green

