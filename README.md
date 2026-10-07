# SafeRide

A native Windows exhibition dashboard for a two-Arduino smart helmet prototype. The app selects the two COM ports, uploads the matching firmware, relays helmet telemetry to the vehicle over USB, and shows the safety state in real time.

## Zero-install portable EXE

Download `SafeRide-Portable-x64.exe` from the public GitHub release, copy it to any writable folder or USB drive, and run it. It needs no installation, administrator rights, Python, Arduino IDE or internet connection for normal operation. The first launch can take longer because the single EXE unpacks its bundled Arduino tools to a temporary folder.

Windows SmartScreen may warn because the SafeRide executable is not code-signed. Verify the adjacent `SafeRide-Portable-x64.sha256.txt` file before running it. The portable package contains the Arduino/FTDI driver files and the official Microsoft-signed WCH 4.0 installer for CH340/CH341 clone boards. Open **USB drivers** on the setup screen only when a connected board does not appear as a COM port; Windows requests administrator approval for that optional driver operation.

Build and verify the portable EXE locally:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build-portable.ps1
powershell -ExecutionPolicy Bypass -File .\tools\verify-portable.ps1
```

## Automatic updates

SafeRide checks the public `ahansardar/SafeRide` GitHub Releases feed after startup. **Check update** runs the same check on demand. When a newer semantic version is available, SafeRide downloads the package that matches the running mode and verifies its SHA-256 checksum. The installed build starts the verified installer. The portable build stages the new EXE beside the running file, closes, replaces itself and relaunches from the same path. SafeRide asks before both the download and replacement. No GitHub account or token is required.

To publish a future version, update `APP_VERSION` in `version.py`, commit and push the source, then run the **Build public SafeRide release** workflow from GitHub Actions. The workflow rejects a version that does not match the source, builds and verifies both Windows packages, and attaches each package with its checksum to the public release.

## Exhibition flow

1. Connect both Arduinos by USB.
2. Run `SafeRide.exe`.
3. Select the helmet and vehicle COM ports.
4. Click **Flash firmware & launch**.
5. The app uploads both sketches and opens the live dashboard.

Use **Configure** before flashing to change the board profile, pin assignments, MQ-3 threshold, drowsiness time, packet intervals, sensor polarity, link timeout, or relay polarity. SafeRide validates the settings, saves them under `%APPDATA%\SafeRide\config.json`, and generates matching firmware for that flash.

Use **Export logs** from the setup screen, configuration wizard, driver assistant, or live dashboard—or press `Ctrl+Shift+S`. The exported text file contains the complete session timeline: port discovery, configuration, firmware compilation/upload output, raw helmet and vehicle packets, safety-state transitions, update activity and errors. SafeRide also writes the active session log continuously under `%LOCALAPPDATA%\SafeRide\logs`.

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

The build script downloads the official Arduino CLI, installs the AVR board package into a portable folder, runs the test suite, compiles both sketches, and creates the installed app plus the single-file portable EXE. Use `-Target Installed` or `-Target Portable` to build only one form.

## Build the offline installer

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build-installer.ps1
```

This creates `release\SafeRide-Setup-x64.exe`. The installer includes Python, pySerial, Arduino CLI, the AVR compiler, board definitions, firmware, signed USB driver packages and the dashboard. The target computer does not need Python, Arduino IDE, internet access or administrator rights for SafeRide itself. It requires 64-bit Windows 10 version 1809 or newer.

Windows normally installs drivers automatically. If it does not, SafeRide can launch the bundled Arduino/FTDI packages or the checksum-pinned official WCH CH340/CH341 installer from its **USB drivers** assistant.

