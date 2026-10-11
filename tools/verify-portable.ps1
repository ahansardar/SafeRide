param(
    [string]$Executable = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Executable) {
    $Executable = Join-Path $projectRoot "release\SafeRide-Portable-x64.exe"
}
$resolvedExe = (Resolve-Path -LiteralPath $Executable).Path
$resultFile = Join-Path $env:TEMP ("saferide-portable-smoke-" + [Guid]::NewGuid().ToString("N") + ".json")

try {
    $process = Start-Process -FilePath $resolvedExe `
        -ArgumentList @("--portable-smoke-test", $resultFile) `
        -WindowStyle Hidden `
        -Wait `
        -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Portable SafeRide smoke test exited with code $($process.ExitCode)."
    }
    if (-not (Test-Path -LiteralPath $resultFile)) {
        throw "Portable SafeRide did not write its smoke-test result."
    }
    $result = Get-Content -Raw -LiteralPath $resultFile | ConvertFrom-Json
    foreach ($field in @("ok", "portable_mode", "arduino_cli", "arduino_usb_drivers", "ch341_driver", "helmet_firmware", "vehicle_firmware", "bluetooth_firmware", "brand_icon")) {
        if (-not $result.$field) {
            throw "Portable SafeRide check failed: $field"
        }
    }
    Write-Host "PORTABLE_SAFERIDE_OK" -ForegroundColor Green
    Write-Host "Version: $($result.version)"
    Write-Host "Executable: $($result.executable)"
} finally {
    Remove-Item -LiteralPath $resultFile -Force -ErrorAction SilentlyContinue
}
