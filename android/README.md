# SafeRide Android

Tablet-first Android dashboard for the SafeRide helmet and vehicle controllers. It uses Bluetooth Classic SPP only. There is no demo-data path.

## Build

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build-android.ps1
```

The script keeps Gradle state and build outputs on `F:` under this repository. It uses the installed Android SDK only as a compiler toolchain. The APK is written to `release\SafeRide-Android.apk`. The public release build uses the repository's private GitHub signing secrets so later APKs keep the same Android signing identity.

The app checks the public SafeRide GitHub release feed at startup and from the Hardware screen. When a newer signed APK is present, it opens the public release download page for the operator to approve the Android package update.

## First connection

1. Flash both Arduinos once with SafeRide Bluetooth firmware from the Windows app.
2. Remove both USB cables.
3. Wire each HC-05 directly: TXD to D0/RX, RXD to D1/TX, VCC to 5V, GND to GND, and leave EN/KEY disconnected.
4. Power both boards externally.
5. Pair both HC-05 modules in Android Bluetooth settings. The usual PIN is `1234`; some modules use `0000`.
6. Open SafeRide, grant Nearby devices access, and press **Rescan**.
7. Select the helmet and vehicle modules, or press **Auto identify**.
8. Press **Connect both + open dashboard**.

The app remembers both assignments. **Export logs** is present in the top bar on every screen.
