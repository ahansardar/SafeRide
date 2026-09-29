param(
    [string]$ArduinoCliVersion = "1.5.1"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$toolRoot = Join-Path $projectRoot "tools"
$cliPath = Join-Path $toolRoot "arduino-cli.exe"
$arduinoData = Join-Path $toolRoot "arduino-data"
$arduinoDownloads = Join-Path $arduinoData "staging"
$arduinoSketchbook = Join-Path $toolRoot "arduino-sketchbook"
$downloadZip = Join-Path $env:TEMP "arduino-cli-$ArduinoCliVersion-windows.zip"

Write-Host "[1/6] Preparing Python build tools"
python -m pip install -r (Join-Path $projectRoot "requirements.txt")
python (Join-Path $toolRoot "create_icon.py")

if (-not (Test-Path -LiteralPath $cliPath)) {
    Write-Host "[2/6] Downloading Arduino CLI $ArduinoCliVersion"
    $downloadUrl = "https://github.com/arduino/arduino-cli/releases/download/v$ArduinoCliVersion/arduino-cli_${ArduinoCliVersion}_Windows_64bit.zip"
    Invoke-WebRequest -Uri $downloadUrl -OutFile $downloadZip
    $extractRoot = Join-Path $env:TEMP "saferide-arduino-cli-$ArduinoCliVersion"
    if (Test-Path -LiteralPath $extractRoot) {
        Remove-Item -LiteralPath $extractRoot -Recurse -Force
    }
    Expand-Archive -LiteralPath $downloadZip -DestinationPath $extractRoot -Force
    Copy-Item -LiteralPath (Join-Path $extractRoot "arduino-cli.exe") -Destination $cliPath -Force
} else {
    Write-Host "[2/6] Arduino CLI already present"
}

New-Item -ItemType Directory -Force -Path $arduinoData, $arduinoDownloads, $arduinoSketchbook | Out-Null
$env:ARDUINO_DIRECTORIES_DATA = $arduinoData
$env:ARDUINO_DIRECTORIES_DOWNLOADS = $arduinoDownloads
$env:ARDUINO_DIRECTORIES_USER = $arduinoSketchbook

Write-Host "[3/6] Installing the portable Arduino AVR platform"
& $cliPath core update-index
& $cliPath core install arduino:avr

Write-Host "[4/6] Running parser and safety-decision tests"
Push-Location $projectRoot
try {
    python -m unittest discover -s tests -v

    Write-Host "[5/6] Compiling both bundled firmware sketches"
    & $cliPath compile --fqbn arduino:avr:uno (Join-Path $projectRoot "firmware\helmet")
    & $cliPath compile --fqbn arduino:avr:uno (Join-Path $projectRoot "firmware\vehicle")

    Write-Host "[6/6] Building the Windows application"
    python -m PyInstaller --noconfirm --clean --windowed --onedir `
        --name SafeRide `
        --icon "assets\saferide.ico" `
        --hidden-import serial.tools.list_ports_windows `
        --add-data "firmware;firmware" `
        --add-binary "tools\arduino-cli.exe;tools" `
        --add-data "tools\arduino-data;tools\arduino-data" `
        --add-data "THIRD_PARTY_NOTICES.md;." `
        app.py
} finally {
    Pop-Location
}

$exePath = Join-Path $projectRoot "dist\SafeRide\SafeRide.exe"
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "Build finished without creating $exePath"
}

Write-Host ""
Write-Host "Build complete: $exePath" -ForegroundColor Green

