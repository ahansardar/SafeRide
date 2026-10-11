# SafeRide Android architecture

## Usage

The operator pairs both HC-05 modules in Android settings, selects or auto-identifies the helmet and vehicle modules, then presses **Connect both + open dashboard**. The app opens two Bluetooth Classic SPP sockets. It reads helmet frames, logs and parses them, forwards the unchanged safety frame to the vehicle, reads the vehicle decision, and updates the dashboard.

## Chosen design

Android owns the two wireless connections and the byte bridge. The helmet Arduino owns sensing. The vehicle Arduino owns the final relay decision and link timeout. The UI never calculates an engine-unlock result and never manufactures telemetry.

```text
helmet sensors
  -> helmet Arduino
  -> helmet HC-05
  -> Android BluetoothTransport
  -> vehicle HC-05
  -> vehicle Arduino interlock
  -> Android BluetoothTransport
  -> SafeRideState
  -> tablet dashboard and session log
```

## Types and ownership

- `Telemetry` parses the existing `H/A/D/M/ENGINE/LINK` contract and provides the exact helmet frame forwarded to the vehicle.
- `BluetoothTransport` owns paired-device discovery, role probing, two RFCOMM sockets, forwarding, disconnect, and reconnect.
- `SafeRideViewModel` owns screen state and converts transport events into immutable `SafeRideState` values.
- `PreferencesRepository` stores the selected helmet and vehicle MAC addresses.
- `SessionLog` owns the append-only session file and Storage Access Framework export.
- Compose screens only render state and send operator intents to the view model.

## Alternatives considered

One HC-05 link was rejected because the Android app could not observe both the helmet source and the vehicle's authoritative decision. Pairing the two HC-05 modules directly was rejected because the exhibition modules operate as Bluetooth slaves and the tablet would lose its two-controller inspection path. A web wrapper was rejected because browser Bluetooth support does not provide reliable dual Bluetooth Classic SPP sockets on Android.

## Failure rules

- The app requires two different paired MAC addresses.
- A broken socket closes both links and starts a two-second reconnect loop.
- The vehicle firmware still locks its relay when forwarded helmet packets stop.
- Missing packets display `WAITING` or `OFFLINE`; they never become safe defaults.
- The app stores no Bluetooth PIN and opens the Android pairing settings for trust setup.
