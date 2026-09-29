# SafeRide

A native Windows exhibition dashboard for a two-Arduino smart helmet prototype. The app selects the two COM ports, uploads the matching firmware, relays helmet telemetry to the vehicle over USB, and shows the safety state in real time.

## Automatic updates

SafeRide checks the public `ahansardar/SafeRide` GitHub Releases feed after startup. **Check update** runs the same check on demand. When a newer semantic version is available, SafeRide asks before downloading it, verifies the release installer against the published SHA-256 checksum, and asks again before starting the in-place upgrade. No GitHub account or token is required.

To publish a future version, update `APP_VERSION` in `version.py`, commit and push the source, then run the **Build public SafeRide release** workflow from GitHub Actions. The workflow rejects a version that does not match the source, builds the offline installer, and attaches both the installer and checksum to the public release.

## Exhibition flow

1. Connect both Arduinos by USB.
2. Run `SafeRide.exe`.
3. Select the helmet and vehicle COM ports.
4. Click **Flash firmware & launch**.
5. The app uploads both sketches and opens the live dashboard.

Use **Configure** before flashing to change the board profile, pin assignments, MQ-3 threshold, drowsiness time, packet intervals, sensor polarity, link timeout, or relay polarity. SafeRide validates the settings, saves them under `%APPDATA%\SafeRide\config.json`, and generates matching firmware for that flash.

Supported board profiles are Arduino Uno, Nano with either bootloader, and Mega 2560. Auto Detect tries compatible profiles in a safe order. D0 and D1 stay reserved for USB serial on every profile.

No HC-05 is required. The PC forwards the real helmet packet to the vehicle Arduino over the two USB connections. The dashboard calls this the Helmet to Vehicle Link; the vehicle still makes the final relay decision.

## Wiring

### Helmet Arduino

| Part | Arduino pin |
|---|---|
| MQ-3 AOUT | A0 |
| Helmet IR | D2 |
| Eye IR | D3 |
| Status LED | D7 |
| Buzzer | D8 |

### Vehicle Arduino

| Part | Arduino pin |
|---|---|
| Relay IN | D4 |
| Status LED | D5 |
| Buzzer | D6 |

## Development

```powershell
python -m pip install -r requirements.txt
python app.py
```

## Build the Windows app

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build.ps1
```

The build script downloads the official Arduino CLI, installs the AVR board package into a portable folder, runs the test suite, builds the application, and creates `dist\SafeRide\SafeRide.exe`.

## Build the offline installer

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build-installer.ps1
```

This creates `release\SafeRide-Setup-x64.exe`. The installer includes Python, pySerial, Arduino CLI, the AVR compiler, board definitions, firmware and the dashboard. The target computer does not need Python, Arduino IDE, internet access or administrator rights. It requires 64-bit Windows 10 version 1809 or newer.

Windows normally installs drivers automatically for genuine Arduino USB interfaces. CH340-based clone boards may still require their signed USB serial driver through Windows Update or the board vendor.

