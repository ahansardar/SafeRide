param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$versionFile = Join-Path $projectRoot "version.py"
$match = Select-String -LiteralPath $versionFile -Pattern '^APP_VERSION\s*=\s*"(\d+\.\d+\.\d+)"$'
if (-not $match) {
    throw "Could not read APP_VERSION from $versionFile"
}
$sourceVersion = $match.Matches[0].Groups[1].Value
if ($sourceVersion -ne $Version) {
    throw "Release version $Version does not match version.py ($sourceVersion)."
}
Write-Host "Release version verified: $Version" -ForegroundColor Green
