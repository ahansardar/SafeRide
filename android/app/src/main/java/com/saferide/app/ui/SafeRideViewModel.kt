package com.saferide.app.ui

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.saferide.app.bluetooth.BluetoothTransport
import com.saferide.app.data.ControllerSelection
import com.saferide.app.data.PreferencesRepository
import com.saferide.app.data.SessionLog
import com.saferide.app.data.UpdateRepository
import com.saferide.app.BuildConfig
import com.saferide.app.model.ConnectionPhase
import com.saferide.app.model.ControllerRole
import com.saferide.app.model.RawPacket
import com.saferide.app.model.SafeRideState
import com.saferide.app.model.parsePacket
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class SafeRideViewModel(application: Application) : AndroidViewModel(application) {
    private val preferences = PreferencesRepository(application)
    private val sessionLog = SessionLog(application)
    private val updateRepository = UpdateRepository()
    private val saved = preferences.load()
    private val mutableState = MutableStateFlow(
        SafeRideState(
            helmetAddress = saved.helmetAddress,
            vehicleAddress = saved.vehicleAddress,
        ),
    )
    val state: StateFlow<SafeRideState> = mutableState.asStateFlow()

    private val transport = BluetoothTransport(
        context = application,
        sessionLog = sessionLog,
        onPhase = ::onPhase,
        onHelmetLine = ::onHelmetLine,
        onVehicleLine = ::onVehicleLine,
    )

    init {
        sessionLog.append("system", "SafeRide Android started; Bluetooth Classic SPP only")
        checkForUpdates()
    }

    fun updatePermission(granted: Boolean) {
        mutableState.value = mutableState.value.copy(permissionGranted = granted)
        if (granted) refreshDevices() else onPhase(
            ConnectionPhase.PERMISSION_REQUIRED,
            "Nearby devices permission is required for paired HC-05 modules",
        )
    }

    fun refreshDevices() {
        val enabled = transport.bluetoothEnabled
        if (!enabled) {
            mutableState.value = mutableState.value.copy(
                bluetoothEnabled = false,
                pairedDevices = emptyList(),
                phase = ConnectionPhase.BLUETOOTH_OFF,
                phaseDetail = "Turn on Bluetooth and pair both HC-05 modules",
            )
            return
        }
        runCatching { transport.bondedDevices() }
            .onSuccess { devices ->
                val addresses = devices.map { it.address }.toSet()
                val current = mutableState.value
                mutableState.value = current.copy(
                    bluetoothEnabled = true,
                    pairedDevices = devices,
                    helmetAddress = current.helmetAddress.takeIf(addresses::contains).orEmpty(),
                    vehicleAddress = current.vehicleAddress.takeIf(addresses::contains).orEmpty(),
                    phase = if (current.phase == ConnectionPhase.CONNECTED) current.phase else ConnectionPhase.DISCONNECTED,
                    phaseDetail = if (devices.isEmpty()) {
                        "No paired devices. Pair both HC-05 modules in Android settings"
                    } else {
                        "${devices.size} paired Bluetooth device${if (devices.size == 1) "" else "s"} found"
                    },
                )
                sessionLog.append("bluetooth", "Found ${devices.size} paired devices")
            }
            .onFailure { error ->
                onPhase(ConnectionPhase.ERROR, error.message ?: "Could not read paired devices")
            }
    }

    fun selectDevice(role: ControllerRole, address: String) {
        val current = mutableState.value
        val updated = when (role) {
            ControllerRole.HELMET -> current.copy(helmetAddress = address)
            ControllerRole.VEHICLE -> current.copy(vehicleAddress = address)
        }
        mutableState.value = updated
        if (updated.helmetAddress != updated.vehicleAddress || updated.helmetAddress.isBlank()) {
            preferences.save(ControllerSelection(updated.helmetAddress, updated.vehicleAddress))
        }
        sessionLog.append("configuration", "$role selected $address")
    }

    fun autoIdentify() {
        if (!mutableState.value.permissionGranted) return
        viewModelScope.launch {
            onPhase(ConnectionPhase.IDENTIFYING, "Reading live packets from paired modules")
            var helmet = ""
            var vehicle = ""
            for (device in mutableState.value.pairedDevices) {
                when (transport.probeRole(device)) {
                    ControllerRole.HELMET -> helmet = device.address
                    ControllerRole.VEHICLE -> vehicle = device.address
                    null -> Unit
                }
                if (helmet.isNotBlank() && vehicle.isNotBlank()) break
            }
            if (helmet.isNotBlank() && vehicle.isNotBlank()) {
                preferences.save(ControllerSelection(helmet, vehicle))
                mutableState.value = mutableState.value.copy(
                    helmetAddress = helmet,
                    vehicleAddress = vehicle,
                    phase = ConnectionPhase.DISCONNECTED,
                    phaseDetail = "Helmet and vehicle identified from live packets",
                )
            } else {
                onPhase(
                    ConnectionPhase.ERROR,
                    "Could not identify both modules. Power them on and select each paired device manually",
                )
            }
        }
    }

    fun connect() {
        val current = mutableState.value
        if (!current.canConnect) {
            onPhase(ConnectionPhase.ERROR, "Choose two different paired HC-05 modules")
            return
        }
        mutableState.value = current.copy(
            helmetTelemetry = null,
            vehicleTelemetry = null,
            mq3History = emptyList(),
            rawPackets = emptyList(),
            packetsReceived = 0,
            connectionStartedAtMillis = System.currentTimeMillis(),
        )
        transport.connect(current.helmetAddress, current.vehicleAddress)
    }

    fun disconnect() {
        viewModelScope.launch { transport.disconnect() }
    }

    fun exportLogs(uri: Uri, onComplete: (Result<Unit>) -> Unit) {
        viewModelScope.launch {
            val result = runCatching {
                withContext(Dispatchers.IO) { sessionLog.export(uri) }
                sessionLog.append("export", "Session log exported")
            }
            onComplete(result)
        }
    }

    fun checkForUpdates() {
        if (mutableState.value.updateChecking) return
        mutableState.update { it.copy(updateChecking = true, updateMessage = "Checking the public SafeRide release…") }
        viewModelScope.launch {
            runCatching { withContext(Dispatchers.IO) { updateRepository.latestUpdate() } }
                .onSuccess { update ->
                    mutableState.update { current ->
                        if (update == null) current.copy(
                            updateChecking = false,
                            updateMessage = "SafeRide ${BuildConfig.VERSION_NAME} is current.",
                            updateVersion = null,
                            updateUrl = null,
                        ) else current.copy(
                            updateChecking = false,
                            updateMessage = "SafeRide ${update.version} is ready to download.",
                            updateVersion = update.version,
                            updateUrl = update.releaseUrl,
                        )
                    }
                    sessionLog.append("update", update?.let { "Version ${it.version} available" } ?: "App is current")
                }
                .onFailure { error ->
                    mutableState.update { current ->
                        current.copy(updateChecking = false, updateMessage = "Update check unavailable: ${error.message}")
                    }
                    sessionLog.append("error", "Update check: ${error.message}")
                }
        }
    }

    private fun onPhase(phase: ConnectionPhase, detail: String) {
        mutableState.update { current ->
            current.copy(
                phase = phase,
                phaseDetail = detail,
                bluetoothEnabled = transport.bluetoothEnabled,
            )
        }
        sessionLog.append("connection", "$phase: $detail")
    }

    private fun onHelmetLine(line: String) {
        recordRaw(ControllerRole.HELMET, line)
        parsePacket(line)?.let { packet ->
            mutableState.update { current ->
                current.copy(
                    helmetTelemetry = packet,
                    mq3History = (current.mq3History + packet.mq3).takeLast(90),
                )
            }
        }
    }

    private fun onVehicleLine(line: String) {
        recordRaw(ControllerRole.VEHICLE, line)
        parsePacket(line)?.let { packet ->
            mutableState.update { current -> current.copy(vehicleTelemetry = packet) }
        }
    }

    private fun recordRaw(role: ControllerRole, line: String) {
        sessionLog.append("raw-${role.name.lowercase()}", line)
        mutableState.update { current ->
            current.copy(
                rawPackets = (current.rawPackets + RawPacket(role, line)).takeLast(160),
                packetsReceived = current.packetsReceived + 1,
            )
        }
    }

    override fun onCleared() {
        transport.close()
        sessionLog.append("system", "SafeRide Android closed")
        super.onCleared()
    }
}
