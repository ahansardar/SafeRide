param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version,
    [string]$Notes = "SafeRide Windows installer and zero-install portable EXE with public GitHub release updates.",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot "assert-release-version.ps1") -Version $Version

if (-not $SkipBuild) {
    & (Join-Path $PSScriptRoot "build.ps1") -Target All
    & (Join-Path $PSScriptRoot "build-installer.ps1") -SkipAppBuild
    & (Join-Path $PSScriptRoot "build-portable.ps1") -SkipAppBuild
    & (Join-Path $PSScriptRoot "verify-portable.ps1")
}

$installer = Join-Path $projectRoot "release\SafeRide-Setup-x64.exe"
$installerChecksum = Join-Path $projectRoot "release\SafeRide-Setup-x64.sha256.txt"
$portable = Join-Path $projectRoot "release\SafeRide-Portable-x64.exe"
$portableChecksum = Join-Path $projectRoot "release\SafeRide-Portable-x64.sha256.txt"
$assets = @($installer, $installerChecksum, $portable, $portableChecksum)
if ($assets.Where({ -not (Test-Path -LiteralPath $_) })) {
    throw "Build both Windows packages and checksums before publishing."
}

$status = git -C $projectRoot status --porcelain
if ($status) {
    throw "Commit and push the source before publishing a release."
}

$remote = git -C $projectRoot remote get-url origin
if ($remote -notmatch 'github\.com[:/]ahansardar/SafeRide(?:\.git)?$') {
    throw "The origin remote is not ahansardar/SafeRide: $remote"
}

gh release create "v$Version" $installer $installerChecksum $portable $portableChecksum `
    --repo "ahansardar/SafeRide" `
    --target "main" `
    --title "SafeRide $Version" `
    --notes $Notes

if ($LASTEXITCODE -ne 0) {
    throw "GitHub release publishing failed."
}
