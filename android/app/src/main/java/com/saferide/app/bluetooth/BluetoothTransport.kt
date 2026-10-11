package com.saferide.app.bluetooth

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothSocket
import android.content.Context
import android.os.SystemClock
import com.saferide.app.data.SessionLog
import com.saferide.app.model.BluetoothDeviceInfo
import com.saferide.app.model.ConnectionPhase
import com.saferide.app.model.ControllerRole
import com.saferide.app.model.classifySafeRideLine
import com.saferide.app.model.forwardableHelmetPacket
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.IOException
import java.nio.charset.StandardCharsets
import java.util.UUID

class BluetoothTransport(
    context: Context,
    private val sessionLog: SessionLog,
    private val onPhase: (ConnectionPhase, String) -> Unit,
    private val onHelmetLine: (String) -> Unit,
    private val onVehicleLine: (String) -> Unit,
) {
    private val adapter: BluetoothAdapter? =
        context.getSystemService(BluetoothManager::class.java)?.adapter
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val socketLock = Any()
    private var helmetSocket: BluetoothSocket? = null
    private var vehicleSocket: BluetoothSocket? = null
    private var connectionJob: Job? = null
    @Volatile private var desiredConnection = false

    val bluetoothAvailable: Boolean get() = adapter != null
    val bluetoothEnabled: Boolean
        @SuppressLint("MissingPermission")
        get() = runCatching { adapter?.isEnabled == true }.getOrDefault(false)

    @SuppressLint("MissingPermission")
    fun bondedDevices(): List<BluetoothDeviceInfo> = adapter?.bondedDevices
        .orEmpty()
        .map { BluetoothDeviceInfo(it.name.orEmpty(), it.address) }
        .sortedWith(compareBy({ it.displayName.lowercase() }, { it.address }))

    @SuppressLint("MissingPermission")
    suspend fun probeRole(device: BluetoothDeviceInfo, timeoutMillis: Long = 3200): ControllerRole? =
        withContext(Dispatchers.IO) {
            val remote = adapter?.getRemoteDevice(device.address) ?: return@withContext null
            var socket: BluetoothSocket? = null
            try {
                socket = createSocket(remote)
                socket.connect()
                sessionLog.append("bluetooth", "Probing ${device.displayName} ${device.address}")
                val input = socket.inputStream
                val pending = StringBuilder()
                val buffer = ByteArray(256)
                val deadline = SystemClock.elapsedRealtime() + timeoutMillis
                while (SystemClock.elapsedRealtime() < deadline) {
                    val available = input.available()
                    if (available == 0) {
                        SystemClock.sleep(35)
                        continue
                    }
                    val count = input.read(buffer, 0, minOf(buffer.size, available))
                    if (count <= 0) break
                    pending.append(String(buffer, 0, count, StandardCharsets.US_ASCII))
                    var newline = pending.indexOf("\n")
                    while (newline >= 0) {
                        val line = pending.substring(0, newline).trim()
                        pending.delete(0, newline + 1)
                        classifySafeRideLine(line)?.let { role ->
                            sessionLog.append("bluetooth", "Identified ${device.address} as $role")
                            return@withContext role
                        }
                        newline = pending.indexOf("\n")
                    }
                }
                null
            } catch (error: IOException) {
                sessionLog.append("error", "Probe ${device.address}: ${error.message}")
                null
            } finally {
                runCatching { socket?.close() }
            }
        }

    fun connect(helmetAddress: String, vehicleAddress: String) {
        require(helmetAddress.isNotBlank() && vehicleAddress.isNotBlank())
        require(helmetAddress != vehicleAddress)
        desiredConnection = true
        connectionJob?.cancel()
        closeSockets()
        connectionJob = scope.launch { connectionLoop(helmetAddress, vehicleAddress) }
    }

    suspend fun disconnect() {
        desiredConnection = false
        closeSockets()
        connectionJob?.cancelAndJoin()
        connectionJob = null
        onPhase(ConnectionPhase.DISCONNECTED, "Bluetooth bridge stopped")
        sessionLog.append("connection", "Disconnected both HC-05 modules")
    }

    fun close() {
        desiredConnection = false
        closeSockets()
        connectionJob?.cancel()
    }

    @SuppressLint("MissingPermission")
    private suspend fun connectionLoop(helmetAddress: String, vehicleAddress: String) {
        var firstAttempt = true
        while (currentCoroutineContext().isActive && desiredConnection) {
            onPhase(
                if (firstAttempt) ConnectionPhase.CONNECTING else ConnectionPhase.RECONNECTING,
                if (firstAttempt) "Opening both HC-05 links" else "Link lost. Retrying in 2 seconds",
            )
            if (!firstAttempt) delay(2000)
            firstAttempt = false
            if (!desiredConnection) break
            try {
                val helmet = createSocket(adapter?.getRemoteDevice(helmetAddress) ?: error("Bluetooth unavailable"))
                helmet.connect()
                synchronized(socketLock) { helmetSocket = helmet }
                onPhase(ConnectionPhase.CONNECTING, "Helmet connected. Opening vehicle link")

                val vehicle = createSocket(adapter.getRemoteDevice(vehicleAddress))
                vehicle.connect()
                synchronized(socketLock) { vehicleSocket = vehicle }
                sessionLog.append("connection", "Bridge active $helmetAddress -> $vehicleAddress")
                onPhase(ConnectionPhase.CONNECTED, "Dual HC-05 bridge active")
                runBridge(helmet, vehicle)
            } catch (error: Exception) {
                if (desiredConnection) {
                    sessionLog.append("error", "Bluetooth bridge: ${error.message ?: error.javaClass.simpleName}")
                }
            } finally {
                closeSockets()
            }
        }
    }

    private suspend fun runBridge(helmet: BluetoothSocket, vehicle: BluetoothSocket) {
        coroutineScope {
            val failure = Channel<Throwable>(capacity = 2)
            val helmetReader = launch {
                try {
                    readLines(helmet) { line ->
                        onHelmetLine(line)
                        forwardableHelmetPacket(line)?.let { packet ->
                            synchronized(vehicle.outputStream) {
                                vehicle.outputStream.write((packet + "\n").toByteArray(StandardCharsets.US_ASCII))
                                vehicle.outputStream.flush()
                            }
                        }
                    }
                } catch (error: Throwable) {
                    failure.trySend(error)
                }
            }
            val vehicleReader = launch {
                try {
                    readLines(vehicle, onVehicleLine)
                } catch (error: Throwable) {
                    failure.trySend(error)
                }
            }
            val error = failure.receive()
            closeSockets()
            helmetReader.cancel()
            vehicleReader.cancel()
            throw IOException("Serial stream ended: ${error.message}", error)
        }
    }

    private fun readLines(socket: BluetoothSocket, consume: (String) -> Unit) {
        val input = socket.inputStream
        val buffer = ByteArray(512)
        val pending = StringBuilder()
        while (desiredConnection && socket.isConnected) {
            val count = input.read(buffer)
            if (count < 0) throw IOException("Remote module closed the stream")
            pending.append(String(buffer, 0, count, StandardCharsets.US_ASCII))
            var newline = pending.indexOf("\n")
            while (newline >= 0) {
                val line = pending.substring(0, newline).trim()
                pending.delete(0, newline + 1)
                if (line.isNotEmpty()) consume(line)
                newline = pending.indexOf("\n")
            }
            if (pending.length > 1024) pending.delete(0, pending.length - 512)
        }
    }

    @SuppressLint("MissingPermission")
    private fun createSocket(device: BluetoothDevice): BluetoothSocket =
        device.createRfcommSocketToServiceRecord(SPP_UUID)

    private fun closeSockets() {
        synchronized(socketLock) {
            runCatching { helmetSocket?.close() }
            runCatching { vehicleSocket?.close() }
            helmetSocket = null
            vehicleSocket = null
        }
    }

    companion object {
        private val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
    }
}
