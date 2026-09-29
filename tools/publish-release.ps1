param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version,
    [string]$Notes = "SafeRide Windows installer with public GitHub release updates.",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot "assert-release-version.ps1") -Version $Version

if (-not $SkipBuild) {
    & (Join-Path $PSScriptRoot "build-installer.ps1")
}

$installer = Join-Path $projectRoot "release\SafeRide-Setup-x64.exe"
$checksum = Join-Path $projectRoot "release\SafeRide-Setup-x64.sha256.txt"
if (-not (Test-Path -LiteralPath $installer) -or -not (Test-Path -LiteralPath $checksum)) {
    throw "Build the installer and checksum before publishing."
}

$status = git -C $projectRoot status --porcelain
if ($status) {
    throw "Commit and push the source before publishing a release."
}

$remote = git -C $projectRoot remote get-url origin
if ($remote -notmatch 'github\.com[:/]ahansardar/SafeRide(?:\.git)?$') {
    throw "The origin remote is not ahansardar/SafeRide: $remote"
}

gh release create "v$Version" $installer $checksum `
    --repo "ahansardar/SafeRide" `
    --target "main" `
    --title "SafeRide $Version" `
    --notes $Notes

if ($LASTEXITCODE -ne 0) {
    throw "GitHub release publishing failed."
}
