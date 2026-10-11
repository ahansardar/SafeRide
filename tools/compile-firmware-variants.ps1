param(
    [string]$ArduinoCli = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $ArduinoCli) {
    $ArduinoCli = Join-Path $PSScriptRoot "arduino-cli.exe"
}
$resolvedCli = (Resolve-Path -LiteralPath $ArduinoCli).Path
$variantRoot = Join-Path $env:TEMP ("saferide-firmware-variants-" + [Guid]::NewGuid().ToString("N"))
$safeTempRoot = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
$resolvedVariantRoot = [System.IO.Path]::GetFullPath($variantRoot)
if (-not $resolvedVariantRoot.StartsWith($safeTempRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
    -not ([System.IO.Path]::GetFileName($resolvedVariantRoot)).StartsWith("saferide-firmware-variants-")) {
    throw "Refusing to use unsafe firmware variant path: $resolvedVariantRoot"
}

try {
    Write-Host "Compiling USB helmet and vehicle firmware"
    & $resolvedCli compile --fqbn arduino:avr:uno (Join-Path $projectRoot "firmware\helmet")
    if ($LASTEXITCODE -ne 0) { throw "USB helmet firmware compilation failed." }
    & $resolvedCli compile --fqbn arduino:avr:uno (Join-Path $projectRoot "firmware\vehicle")
    if ($LASTEXITCODE -ne 0) { throw "USB vehicle firmware compilation failed." }

    Write-Host "Rendering and compiling HC-05 helmet and vehicle firmware"
    python (Join-Path $PSScriptRoot "render-firmware-variant.py") bluetooth $resolvedVariantRoot
    if ($LASTEXITCODE -ne 0) { throw "Bluetooth firmware rendering failed." }
    & $resolvedCli compile --fqbn arduino:avr:uno (Join-Path $resolvedVariantRoot "helmet")
    if ($LASTEXITCODE -ne 0) { throw "Bluetooth helmet firmware compilation failed." }
    & $resolvedCli compile --fqbn arduino:avr:uno (Join-Path $resolvedVariantRoot "vehicle")
    if ($LASTEXITCODE -ne 0) { throw "Bluetooth vehicle firmware compilation failed." }
} finally {
    if (Test-Path -LiteralPath $resolvedVariantRoot) {
        Remove-Item -LiteralPath $resolvedVariantRoot -Recurse -Force
    }
}

Write-Host "SAFERIDE_FIRMWARE_VARIANTS_OK" -ForegroundColor Green
