package com.saferide.app.model

private val fieldPattern = Regex("(?:^|,)(H|A|D|M|ENGINE|LINK|BT):(-?\\d+)")

data class Telemetry(
    val helmetWorn: Boolean = false,
    val alcoholDetected: Boolean = false,
    val drowsy: Boolean = false,
    val mq3: Int = 0,
    val engineUnlocked: Boolean? = null,
    val linkAlive: Boolean? = null,
) {
    fun helmetPacket(): String =
        "H:${helmetWorn.asInt()},A:${alcoholDetected.asInt()},D:${drowsy.asInt()},M:$mq3"
}

enum class ControllerRole { HELMET, VEHICLE }

enum class ConnectionPhase {
    PERMISSION_REQUIRED,
    BLUETOOTH_OFF,
    DISCONNECTED,
    IDENTIFYING,
    CONNECTING,
    CONNECTED,
    RECONNECTING,
    ERROR,
}

data class BluetoothDeviceInfo(
    val name: String,
    val address: String,
) {
    val displayName: String get() = if (name.isBlank()) "Unnamed HC-05" else name
}

data class RawPacket(
    val source: ControllerRole,
    val line: String,
    val timestampMillis: Long = System.currentTimeMillis(),
)

data class SafeRideState(
    val permissionGranted: Boolean = false,
    val bluetoothEnabled: Boolean = false,
    val phase: ConnectionPhase = ConnectionPhase.DISCONNECTED,
    val phaseDetail: String = "Select two paired HC-05 modules",
    val pairedDevices: List<BluetoothDeviceInfo> = emptyList(),
    val helmetAddress: String = "",
    val vehicleAddress: String = "",
    val helmetTelemetry: Telemetry? = null,
    val vehicleTelemetry: Telemetry? = null,
    val mq3History: List<Int> = emptyList(),
    val rawPackets: List<RawPacket> = emptyList(),
    val connectionStartedAtMillis: Long? = null,
    val packetsReceived: Long = 0,
    val updateChecking: Boolean = false,
    val updateMessage: String = "Updates are checked against the public SafeRide GitHub release.",
    val updateVersion: String? = null,
    val updateUrl: String? = null,
) {
    val helmetConnected: Boolean get() = phase == ConnectionPhase.CONNECTED && helmetTelemetry != null
    val vehicleConnected: Boolean get() = phase == ConnectionPhase.CONNECTED && vehicleTelemetry != null
    val engineUnlocked: Boolean get() = vehicleTelemetry?.engineUnlocked == true
    val linkAlive: Boolean get() = vehicleTelemetry?.linkAlive == true
    val canConnect: Boolean
        get() = permissionGranted && bluetoothEnabled && helmetAddress.isNotBlank() &&
            vehicleAddress.isNotBlank() && helmetAddress != vehicleAddress
}

fun parsePacket(line: String): Telemetry? {
    val fields = fieldPattern.findAll(line.trim()).associate { result ->
        result.groupValues[1] to result.groupValues[2].toInt()
    }
    if (!fields.keys.containsAll(listOf("H", "A", "D", "M"))) return null
    return Telemetry(
        helmetWorn = fields["H"] == 1,
        alcoholDetected = fields["A"] == 1,
        drowsy = fields["D"] == 1,
        mq3 = fields.getValue("M").coerceIn(0, 1023),
        engineUnlocked = fields["ENGINE"]?.let { it == 1 },
        linkAlive = (fields["LINK"] ?: fields["BT"])?.let { it == 1 },
    )
}

fun classifySafeRideLine(line: String): ControllerRole? {
    val clean = line.trim().uppercase()
    if ("DEVICE:HELMET" in clean) return ControllerRole.HELMET
    if ("DEVICE:VEHICLE" in clean) return ControllerRole.VEHICLE
    if (!clean.startsWith("H:") || ",M:" !in clean) return null
    return if (",ENGINE:" in clean || ",LINK:" in clean) ControllerRole.VEHICLE else ControllerRole.HELMET
}

fun forwardableHelmetPacket(line: String): String? = parsePacket(line)
    ?.takeIf { telemetry -> telemetry.engineUnlocked == null && telemetry.linkAlive == null }
    ?.helmetPacket()

fun engineReason(data: Telemetry?): String = when {
    data == null -> "Waiting for vehicle telemetry"
    data.linkAlive == false -> "Helmet link offline"
    !data.helmetWorn -> "Helmet not detected"
    data.alcoholDetected -> "Alcohol detected"
    data.drowsy -> "Drowsiness detected"
    else -> "All safety checks passed"
}

private fun Boolean.asInt(): Int = if (this) 1 else 0
