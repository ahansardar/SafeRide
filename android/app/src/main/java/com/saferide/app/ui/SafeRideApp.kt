package com.saferide.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ListAlt
import androidx.compose.material.icons.filled.Bluetooth
import androidx.compose.material.icons.filled.BluetoothConnected
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.LinkOff
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Speed
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.saferide.app.R
import com.saferide.app.BuildConfig
import com.saferide.app.model.BluetoothDeviceInfo
import com.saferide.app.model.ConnectionPhase
import com.saferide.app.model.ControllerRole
import com.saferide.app.model.RawPacket
import com.saferide.app.model.SafeRideState
import com.saferide.app.model.engineReason
import com.saferide.app.ui.theme.Amber
import com.saferide.app.ui.theme.Blue
import com.saferide.app.ui.theme.Canvas as CanvasColor
import com.saferide.app.ui.theme.Console
import com.saferide.app.ui.theme.Green
import com.saferide.app.ui.theme.Line
import com.saferide.app.ui.theme.Muted
import com.saferide.app.ui.theme.Navy
import com.saferide.app.ui.theme.Panel
import com.saferide.app.ui.theme.PanelSoft
import com.saferide.app.ui.theme.Red
import com.saferide.app.ui.theme.Text
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private enum class AppPage(val label: String, val icon: ImageVector) {
    CONNECT("Connect", Icons.Default.Bluetooth),
    DASHBOARD("Dashboard", Icons.Default.Dashboard),
    LOGS("Live logs", Icons.AutoMirrored.Filled.ListAlt),
    HARDWARE("Hardware", Icons.Default.Build),
}

@Composable
fun SafeRideApp(
    state: SafeRideState,
    onRequestPermission: () -> Unit,
    onOpenBluetoothSettings: () -> Unit,
    onRefresh: () -> Unit,
    onSelectDevice: (ControllerRole, String) -> Unit,
    onAutoIdentify: () -> Unit,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
    onExport: () -> Unit,
    onCheckUpdate: () -> Unit,
    onOpenUpdate: (String) -> Unit,
) {
    var page by rememberSaveable { mutableStateOf(AppPage.CONNECT) }
    LaunchedEffect(state.phase) {
        if (state.phase == ConnectionPhase.CONNECTED) page = AppPage.DASHBOARD
    }
    Scaffold(
        containerColor = CanvasColor,
        topBar = { SafeRideHeader(state, onExport) },
        bottomBar = {
            BoxWithConstraints {
                if (maxWidth < 840.dp) CompactNavigation(page, onPage = { page = it })
            }
        },
    ) { padding ->
        BoxWithConstraints(
            modifier = Modifier.fillMaxSize().padding(padding),
        ) {
            val wide = maxWidth >= 840.dp
            Row(Modifier.fillMaxSize()) {
                if (wide) {
                    TabletNavigation(page, onPage = { page = it })
                    HorizontalDivider(Modifier.fillMaxHeight().width(1.dp), color = Line)
                }
                Box(Modifier.fillMaxSize().padding(if (wide) 24.dp else 14.dp)) {
                    when (page) {
                        AppPage.CONNECT -> ConnectionPage(
                            state, wide, onRequestPermission, onOpenBluetoothSettings,
                            onRefresh, onSelectDevice, onAutoIdentify, onConnect, onDisconnect,
                        )
                        AppPage.DASHBOARD -> DashboardPage(state, wide, onDisconnect)
                        AppPage.LOGS -> LogsPage(state)
                        AppPage.HARDWARE -> HardwarePage(state, wide, onCheckUpdate, onOpenUpdate)
                    }
                }
            }
        }
    }
}

@Composable
private fun SafeRideHeader(state: SafeRideState, onExport: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().background(Navy).statusBarsPadding().height(72.dp).padding(horizontal = 20.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            painter = painterResource(R.drawable.ic_saferide),
            contentDescription = null,
            tint = Color.Unspecified,
            modifier = Modifier.size(46.dp),
        )
        Spacer(Modifier.width(12.dp))
        Column {
            Text("SAFERIDE", color = Color.White, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp, fontSize = 19.sp)
            Text("SMART HELMET CONTROL  /  ANDROID TABLET", color = Color(0xFF94A3B8), fontFamily = FontFamily.Monospace, fontSize = 10.sp)
        }
        Spacer(Modifier.weight(1f))
        ConnectionBadge(state.phase)
        Spacer(Modifier.width(10.dp))
        Button(
            onClick = onExport,
            colors = ButtonDefaults.buttonColors(containerColor = Color.White, contentColor = Navy),
            shape = RoundedCornerShape(5.dp),
        ) {
            Icon(Icons.Default.Download, null, Modifier.size(18.dp))
            Spacer(Modifier.width(8.dp))
            Text("EXPORT LOGS", fontWeight = FontWeight.Bold, fontSize = 12.sp)
        }
    }
}

@Composable
private fun ConnectionBadge(phase: ConnectionPhase) {
    val connected = phase == ConnectionPhase.CONNECTED
    Row(
        Modifier.clip(RoundedCornerShape(50)).background(if (connected) Color(0xFF14532D) else Color(0xFF1E293B))
            .padding(horizontal = 12.dp, vertical = 7.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            if (connected) Icons.Default.BluetoothConnected else Icons.Default.LinkOff,
            null,
            tint = if (connected) Color(0xFF86EFAC) else Color(0xFF94A3B8),
            modifier = Modifier.size(16.dp),
        )
        Spacer(Modifier.width(7.dp))
        Text(
            if (connected) "LIVE" else phase.name.replace('_', ' '),
            color = Color.White,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            fontSize = 10.sp,
        )
    }
}

@Composable
private fun TabletNavigation(selected: AppPage, onPage: (AppPage) -> Unit) {
    Column(
        Modifier.width(218.dp).fillMaxHeight().background(Panel).padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text("CONTROL CENTER", color = Muted, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 10.sp, modifier = Modifier.padding(10.dp))
        AppPage.entries.forEach { page -> NavigationItem(page, page == selected, onPage) }
        Spacer(Modifier.weight(1f))
        Text("BLUETOOTH CLASSIC / SPP", color = Muted, fontFamily = FontFamily.Monospace, fontSize = 9.sp, modifier = Modifier.padding(10.dp))
        Text("VERSION ${BuildConfig.VERSION_NAME}", color = Muted, fontFamily = FontFamily.Monospace, fontSize = 9.sp, modifier = Modifier.padding(horizontal = 10.dp))
        Text("REAL DATA ONLY", color = Green, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 10.sp, modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp))
    }
}

@Composable
private fun NavigationItem(page: AppPage, selected: Boolean, onPage: (AppPage) -> Unit) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(6.dp))
            .background(if (selected) Color(0xFFDBEAFE) else Color.Transparent)
            .clickable { onPage(page) }.padding(horizontal = 12.dp, vertical = 13.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(page.icon, null, tint = if (selected) Blue else Muted, modifier = Modifier.size(20.dp))
        Spacer(Modifier.width(12.dp))
        Text(page.label, color = if (selected) Blue else Text, fontWeight = FontWeight.Bold, fontSize = 14.sp)
    }
}

@Composable
private fun CompactNavigation(selected: AppPage, onPage: (AppPage) -> Unit) {
    Row(Modifier.fillMaxWidth().height(66.dp).background(Panel).border(1.dp, Line)) {
        AppPage.entries.forEach { page ->
            Column(
                Modifier.weight(1f).fillMaxHeight().clickable { onPage(page) },
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Icon(page.icon, null, tint = if (page == selected) Blue else Muted, modifier = Modifier.size(21.dp))
                Text(page.label, color = if (page == selected) Blue else Muted, fontSize = 10.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
private fun ConnectionPage(
    state: SafeRideState,
    wide: Boolean,
    onRequestPermission: () -> Unit,
    onOpenBluetoothSettings: () -> Unit,
    onRefresh: () -> Unit,
    onSelectDevice: (ControllerRole, String) -> Unit,
    onAutoIdentify: () -> Unit,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        PageTitle("Bluetooth setup", "Pair once, identify both controllers, then start the real dual-link bridge.")
        StatusStrip(state)
        Spacer(Modifier.height(14.dp))
        if (!state.permissionGranted) {
            ActionNotice("Nearby devices permission is required", "SafeRide uses it only to list and connect to paired HC-05 modules.", onRequestPermission, "ALLOW ACCESS")
        } else if (!state.bluetoothEnabled) {
            ActionNotice("Bluetooth is turned off", "Turn it on, pair both HC-05 modules, then return and rescan.", onOpenBluetoothSettings, "OPEN BLUETOOTH")
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            DeviceSelector(
                role = ControllerRole.HELMET,
                devices = state.pairedDevices,
                selectedAddress = state.helmetAddress,
                onSelect = onSelectDevice,
                modifier = Modifier.weight(1f),
            )
            if (wide) {
                DeviceSelector(
                    role = ControllerRole.VEHICLE,
                    devices = state.pairedDevices,
                    selectedAddress = state.vehicleAddress,
                    onSelect = onSelectDevice,
                    modifier = Modifier.weight(1f),
                )
            }
        }
        if (!wide) {
            Spacer(Modifier.height(12.dp))
            DeviceSelector(
                role = ControllerRole.VEHICLE,
                devices = state.pairedDevices,
                selectedAddress = state.vehicleAddress,
                onSelect = onSelectDevice,
                modifier = Modifier.fillMaxWidth(),
            )
        }
        Spacer(Modifier.height(14.dp))
        Card(
            colors = CardDefaults.cardColors(containerColor = Panel),
            shape = RoundedCornerShape(7.dp),
            modifier = Modifier.fillMaxWidth().border(1.dp, Line, RoundedCornerShape(7.dp)),
        ) {
            Row(
                Modifier.fillMaxWidth().padding(16.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                FilledTonalButton(onClick = onOpenBluetoothSettings, shape = RoundedCornerShape(5.dp)) {
                    Icon(Icons.Default.Settings, null, Modifier.size(18.dp)); Spacer(Modifier.width(7.dp)); Text("PAIR DEVICES")
                }
                FilledTonalButton(onClick = onRefresh, shape = RoundedCornerShape(5.dp)) {
                    Icon(Icons.Default.Refresh, null, Modifier.size(18.dp)); Spacer(Modifier.width(7.dp)); Text("RESCAN")
                }
                FilledTonalButton(
                    onClick = onAutoIdentify,
                    enabled = state.pairedDevices.isNotEmpty() && state.phase != ConnectionPhase.IDENTIFYING,
                    shape = RoundedCornerShape(5.dp),
                ) {
                    Icon(Icons.Default.Security, null, Modifier.size(18.dp)); Spacer(Modifier.width(7.dp)); Text("AUTO IDENTIFY")
                }
                Spacer(Modifier.weight(1f))
                if (state.phase == ConnectionPhase.CONNECTED || state.phase == ConnectionPhase.CONNECTING || state.phase == ConnectionPhase.RECONNECTING) {
                    TextButton(onClick = onDisconnect) { Text("DISCONNECT", color = Red, fontWeight = FontWeight.Bold) }
                } else {
                    Button(onClick = onConnect, enabled = state.canConnect, shape = RoundedCornerShape(5.dp)) {
                        Icon(Icons.Default.BluetoothConnected, null, Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)); Text("CONNECT BOTH + OPEN DASHBOARD", fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
        Spacer(Modifier.height(14.dp))
        ConnectionSequence(wide)
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun DeviceSelector(
    role: ControllerRole,
    devices: List<BluetoothDeviceInfo>,
    selectedAddress: String,
    onSelect: (ControllerRole, String) -> Unit,
    modifier: Modifier,
) {
    Card(
        modifier = modifier.border(1.dp, Line, RoundedCornerShape(7.dp)),
        colors = CardDefaults.cardColors(containerColor = Panel),
        shape = RoundedCornerShape(7.dp),
    ) {
        Column(Modifier.padding(16.dp)) {
            Text("${if (role == ControllerRole.HELMET) "01" else "02"}  ${role.name} HC-05", color = Text, fontWeight = FontWeight.Black, fontSize = 16.sp)
            Text(
                if (role == ControllerRole.HELMET) "Source: H, A, D and MQ-3" else "Authority: ENGINE and LINK",
                color = Muted, fontFamily = FontFamily.Monospace, fontSize = 10.sp,
            )
            Spacer(Modifier.height(10.dp))
            if (devices.isEmpty()) {
                Text("No paired modules found", color = Muted, modifier = Modifier.padding(vertical = 18.dp))
            } else {
                devices.forEach { device ->
                    val selected = device.address == selectedAddress
                    Row(
                        Modifier.fillMaxWidth().clip(RoundedCornerShape(5.dp))
                            .background(if (selected) Color(0xFFEFF6FF) else PanelSoft)
                            .clickable { onSelect(role, device.address) }
                            .padding(horizontal = 8.dp, vertical = 7.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        RadioButton(selected = selected, onClick = { onSelect(role, device.address) })
                        Column(Modifier.weight(1f)) {
                            Text(device.displayName, color = Text, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            Text(device.address, color = Muted, fontFamily = FontFamily.Monospace, fontSize = 10.sp)
                        }
                    }
                    Spacer(Modifier.height(5.dp))
                }
            }
        }
    }
}

@Composable
private fun StatusStrip(state: SafeRideState) {
    val color = when (state.phase) {
        ConnectionPhase.CONNECTED -> Green
        ConnectionPhase.ERROR -> Red
        ConnectionPhase.BLUETOOTH_OFF, ConnectionPhase.PERMISSION_REQUIRED -> Amber
        else -> Blue
    }
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(5.dp)).background(color.copy(alpha = 0.09f))
            .border(1.dp, color.copy(alpha = 0.35f), RoundedCornerShape(5.dp)).padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(if (state.phase == ConnectionPhase.ERROR) Icons.Default.Error else Icons.Default.Bluetooth, null, tint = color)
        Spacer(Modifier.width(10.dp))
        Column {
            Text(state.phase.name.replace('_', ' '), color = color, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace, fontSize = 11.sp)
            Text(state.phaseDetail, color = Text, fontSize = 13.sp)
        }
    }
}

@Composable
private fun ActionNotice(title: String, detail: String, action: () -> Unit, actionLabel: String) {
    Row(
        Modifier.fillMaxWidth().padding(bottom = 14.dp).background(Color(0xFFFFF7ED), RoundedCornerShape(6.dp))
            .border(1.dp, Color(0xFFFDBA74), RoundedCornerShape(6.dp)).padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, color = Color(0xFF9A3412), fontWeight = FontWeight.Bold)
            Text(detail, color = Color(0xFF7C2D12), fontSize = 12.sp)
        }
        Button(onClick = action, colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF9A3412)), shape = RoundedCornerShape(5.dp)) {
            Text(actionLabel, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun ConnectionSequence(wide: Boolean) {
    Card(
        colors = CardDefaults.cardColors(containerColor = Navy),
        shape = RoundedCornerShape(7.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(Modifier.padding(18.dp)) {
            Text("LIVE DATA ROUTE", color = Color.White, fontWeight = FontWeight.Black, fontSize = 15.sp)
            Text("The tablet replaces the Windows serial bridge. The vehicle Arduino still owns the relay decision.", color = Color(0xFFCBD5E1), fontSize = 12.sp)
            Spacer(Modifier.height(16.dp))
            val steps = listOf(
                "HELMET HC-05" to "Reads H / A / D / M",
                "ANDROID TABLET" to "Validates, logs and forwards",
                "VEHICLE HC-05" to "Returns ENGINE / LINK",
                "LIVE DASHBOARD" to "Shows the real decision",
            )
            if (wide) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    steps.forEachIndexed { index, item -> SequenceStep(index + 1, item.first, item.second, Modifier.weight(1f)) }
                }
            } else {
                steps.forEachIndexed { index, item ->
                    SequenceStep(index + 1, item.first, item.second, Modifier.fillMaxWidth())
                    Spacer(Modifier.height(7.dp))
                }
            }
        }
    }
}

@Composable
private fun SequenceStep(number: Int, title: String, detail: String, modifier: Modifier) {
    Row(modifier.background(Color(0xFF1E293B), RoundedCornerShape(5.dp)).padding(11.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(28.dp).background(Blue, RoundedCornerShape(4.dp)), contentAlignment = Alignment.Center) {
            Text(number.toString(), color = Color.White, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace)
        }
        Spacer(Modifier.width(9.dp))
        Column {
            Text(title, color = Color.White, fontWeight = FontWeight.Bold, fontSize = 11.sp)
            Text(detail, color = Color(0xFF94A3B8), fontSize = 9.sp)
        }
    }
}

@Composable
private fun DashboardPage(state: SafeRideState, wide: Boolean, onDisconnect: () -> Unit) {
    val helmet = state.helmetTelemetry
    val vehicle = state.vehicleTelemetry
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
            PageTitle("Live safety dashboard", "Every value below comes from the two connected controllers.", Modifier.weight(1f))
            if (state.phase == ConnectionPhase.CONNECTED) {
                TextButton(onClick = onDisconnect) { Text("DISCONNECT", color = Red, fontWeight = FontWeight.Bold) }
            }
        }
        StatusStrip(state)
        Spacer(Modifier.height(14.dp))
        if (wide) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                StatusMetric("HELMET", if (helmet == null) "WAITING" else if (helmet.helmetWorn) "WORN" else "NOT WORN", helmet?.helmetWorn == true, helmet == null, Modifier.weight(1f))
                StatusMetric("ALCOHOL", if (helmet == null) "WAITING" else if (helmet.alcoholDetected) "DETECTED" else "CLEAR", helmet?.alcoholDetected == false, helmet == null, Modifier.weight(1f))
                StatusMetric("ALERTNESS", if (helmet == null) "WAITING" else if (helmet.drowsy) "DROWSY" else "ALERT", helmet?.drowsy == false, helmet == null, Modifier.weight(1f))
                StatusMetric("ENGINE", if (vehicle == null) "WAITING" else if (vehicle.engineUnlocked == true) "UNLOCKED" else "LOCKED", vehicle?.engineUnlocked == true, vehicle == null, Modifier.weight(1f))
            }
        } else {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                StatusMetric("HELMET", if (helmet == null) "WAITING" else if (helmet.helmetWorn) "WORN" else "NOT WORN", helmet?.helmetWorn == true, helmet == null, Modifier.weight(1f))
                StatusMetric("ENGINE", if (vehicle == null) "WAITING" else if (vehicle.engineUnlocked == true) "UNLOCKED" else "LOCKED", vehicle?.engineUnlocked == true, vehicle == null, Modifier.weight(1f))
            }
            Spacer(Modifier.height(10.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                StatusMetric("ALCOHOL", if (helmet == null) "WAITING" else if (helmet.alcoholDetected) "DETECTED" else "CLEAR", helmet?.alcoholDetected == false, helmet == null, Modifier.weight(1f))
                StatusMetric("ALERTNESS", if (helmet == null) "WAITING" else if (helmet.drowsy) "DROWSY" else "ALERT", helmet?.drowsy == false, helmet == null, Modifier.weight(1f))
            }
        }
        Spacer(Modifier.height(14.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            TelemetryChart(state.mq3History, Modifier.weight(if (wide) 1.65f else 1f))
            if (wide) DecisionCard(state, Modifier.weight(1f))
        }
        if (!wide) {
            Spacer(Modifier.height(14.dp))
            DecisionCard(state, Modifier.fillMaxWidth())
        }
        Spacer(Modifier.height(14.dp))
        RawPacketPanel(state.rawPackets.takeLast(18), Modifier.fillMaxWidth().height(260.dp))
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun StatusMetric(label: String, value: String, ok: Boolean, waiting: Boolean, modifier: Modifier) {
    val color = if (waiting) Muted else if (ok) Green else Red
    Card(
        modifier.border(1.dp, Line, RoundedCornerShape(7.dp)),
        colors = CardDefaults.cardColors(containerColor = Panel),
        shape = RoundedCornerShape(7.dp),
    ) {
        Column(Modifier.padding(15.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(9.dp).background(color, RoundedCornerShape(50)))
                Spacer(Modifier.width(8.dp))
                Text(label, color = Muted, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 10.sp)
            }
            Spacer(Modifier.height(12.dp))
            Text(value, color = Text, fontWeight = FontWeight.Black, fontSize = 20.sp, maxLines = 1)
            Text(if (waiting) "No live packet yet" else if (ok) "Safety check passed" else "Interlock active", color = color, fontSize = 11.sp)
        }
    }
}

@Composable
private fun TelemetryChart(history: List<Int>, modifier: Modifier) {
    Card(modifier.border(1.dp, Line, RoundedCornerShape(7.dp)), colors = CardDefaults.cardColors(containerColor = Panel), shape = RoundedCornerShape(7.dp)) {
        Column(Modifier.padding(16.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column {
                    Text("MQ-3 LIVE SIGNAL", color = Text, fontWeight = FontWeight.Black, fontSize = 14.sp)
                    Text("REAL ADC VALUES  /  0–1023", color = Muted, fontFamily = FontFamily.Monospace, fontSize = 9.sp)
                }
                Spacer(Modifier.weight(1f))
                Text(history.lastOrNull()?.toString() ?: "---", color = Blue, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Black, fontSize = 24.sp)
            }
            Spacer(Modifier.height(12.dp))
            Box(Modifier.fillMaxWidth().height(220.dp).background(PanelSoft, RoundedCornerShape(5.dp)).padding(8.dp)) {
                if (history.size < 2) {
                    Text("Waiting for helmet telemetry", color = Muted, modifier = Modifier.align(Alignment.Center))
                } else {
                    Canvas(Modifier.fillMaxSize()) {
                        repeat(5) { index ->
                            val y = size.height * index / 4f
                            drawLine(Line, start = androidx.compose.ui.geometry.Offset(0f, y), end = androidx.compose.ui.geometry.Offset(size.width, y), strokeWidth = 1f)
                        }
                        val path = Path()
                        history.forEachIndexed { index, value ->
                            val x = size.width * index / (history.size - 1).coerceAtLeast(1)
                            val y = size.height * (1f - value / 1023f)
                            if (index == 0) path.moveTo(x, y) else path.lineTo(x, y)
                        }
                        drawPath(path, Blue, style = androidx.compose.ui.graphics.drawscope.Stroke(width = 4f, cap = StrokeCap.Round))
                    }
                }
            }
        }
    }
}

@Composable
private fun DecisionCard(state: SafeRideState, modifier: Modifier) {
    val vehicle = state.vehicleTelemetry
    val waiting = vehicle == null
    val unlocked = vehicle?.engineUnlocked == true
    val color = if (waiting) Muted else if (unlocked) Green else Red
    Card(modifier.border(1.dp, color.copy(alpha = 0.45f), RoundedCornerShape(7.dp)), colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.06f)), shape = RoundedCornerShape(7.dp)) {
        Column(Modifier.padding(18.dp)) {
            Text("VEHICLE INTERLOCK", color = Muted, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 10.sp)
            Spacer(Modifier.height(12.dp))
            Icon(if (waiting) Icons.Default.Speed else if (unlocked) Icons.Default.CheckCircle else Icons.Default.Security, null, tint = color, modifier = Modifier.size(38.dp))
            Spacer(Modifier.height(10.dp))
            Text(if (waiting) "WAITING FOR VEHICLE" else if (unlocked) "ENGINE UNLOCKED" else "ENGINE LOCKED", color = color, fontWeight = FontWeight.Black, fontSize = 22.sp)
            Text(engineReason(vehicle), color = Text, fontSize = 13.sp, modifier = Modifier.padding(top = 5.dp))
            HorizontalDivider(Modifier.padding(vertical = 14.dp), color = Line)
            Text("LINK  ${if (waiting) "WAITING" else if (state.linkAlive) "ALIVE" else "OFFLINE"}", color = if (waiting) Muted else if (state.linkAlive) Green else Red, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
            Text("PACKETS  ${state.packetsReceived}", color = Muted, fontFamily = FontFamily.Monospace, fontSize = 11.sp, modifier = Modifier.padding(top = 6.dp))
        }
    }
}

@Composable
private fun RawPacketPanel(packets: List<RawPacket>, modifier: Modifier) {
    val listState = rememberLazyListState()
    LaunchedEffect(packets.size) {
        if (packets.isNotEmpty()) listState.scrollToItem(packets.lastIndex)
    }
    Card(modifier, colors = CardDefaults.cardColors(containerColor = Console), shape = RoundedCornerShape(7.dp)) {
        Column(Modifier.padding(14.dp)) {
            Row(Modifier.fillMaxWidth()) {
                Text("RAW SERIAL MONITOR", color = Color.White, fontWeight = FontWeight.Black, fontSize = 13.sp)
                Spacer(Modifier.weight(1f))
                Text("${packets.size} VISIBLE", color = Color(0xFF60A5FA), fontFamily = FontFamily.Monospace, fontSize = 9.sp)
            }
            Spacer(Modifier.height(8.dp))
            LazyColumn(state = listState, modifier = Modifier.fillMaxSize(), contentPadding = PaddingValues(vertical = 4.dp)) {
                items(packets) { packet -> RawLine(packet) }
            }
        }
    }
}

@Composable
private fun RawLine(packet: RawPacket) {
    val time = Instant.ofEpochMilli(packet.timestampMillis).atZone(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("HH:mm:ss.SSS"))
    Row(Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
        Text(time, color = Color(0xFF64748B), fontFamily = FontFamily.Monospace, fontSize = 10.sp, modifier = Modifier.width(92.dp))
        Text(packet.source.name.padEnd(8), color = if (packet.source == ControllerRole.HELMET) Color(0xFF60A5FA) else Color(0xFF4ADE80), fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 10.sp, modifier = Modifier.width(70.dp))
        Text(packet.line, color = Color(0xFFCBD5E1), fontFamily = FontFamily.Monospace, fontSize = 10.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
private fun LogsPage(state: SafeRideState) {
    Column(Modifier.fillMaxSize()) {
        PageTitle("Live packet log", "Helmet and vehicle frames are timestamped before parsing. Export includes the full session.")
        StatusStrip(state)
        Spacer(Modifier.height(14.dp))
        RawPacketPanel(state.rawPackets, Modifier.fillMaxSize())
    }
}

@Composable
private fun HardwarePage(state: SafeRideState, wide: Boolean, onCheckUpdate: () -> Unit, onOpenUpdate: (String) -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        PageTitle("Hardware and protocol", "The Android build is Bluetooth-only. Flash both boards once with the SafeRide desktop app.")
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            WiringCard("HELMET HC-05", listOf("VCC  →  5V", "GND  →  GND", "TXD  →  D0 / RX", "RXD  →  D1 / TX", "EN/KEY  not connected"), Modifier.weight(1f))
            if (wide) WiringCard("VEHICLE HC-05", listOf("VCC  →  5V", "GND  →  GND", "TXD  →  D0 / RX", "RXD  →  D1 / TX", "EN/KEY  not connected"), Modifier.weight(1f))
        }
        if (!wide) {
            Spacer(Modifier.height(12.dp))
            WiringCard("VEHICLE HC-05", listOf("VCC  →  5V", "GND  →  GND", "TXD  →  D0 / RX", "RXD  →  D1 / TX", "EN/KEY  not connected"), Modifier.fillMaxWidth())
        }
        Spacer(Modifier.height(14.dp))
        Card(Modifier.fillMaxWidth().border(1.dp, Line, RoundedCornerShape(7.dp)), colors = CardDefaults.cardColors(containerColor = Panel), shape = RoundedCornerShape(7.dp)) {
            Column(Modifier.padding(18.dp)) {
                Text("SERIAL CONTRACT", color = Text, fontWeight = FontWeight.Black, fontSize = 15.sp)
                Spacer(Modifier.height(10.dp))
                ProtocolLine("HELMET → TABLET", "H:1,A:0,D:0,M:218")
                ProtocolLine("TABLET → VEHICLE", "H:1,A:0,D:0,M:218")
                ProtocolLine("VEHICLE → TABLET", "H:1,A:0,D:0,M:218,ENGINE:1,LINK:1")
                HorizontalDivider(Modifier.padding(vertical = 14.dp), color = Line)
                Text("9600 baud  /  Bluetooth Classic SPP  /  two simultaneous links", color = Blue, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
                Text("Direct D0/D1 connection with no divider, matching the current SafeRide firmware profile.", color = Muted, fontSize = 12.sp, modifier = Modifier.padding(top = 7.dp))
            }
        }
        Spacer(Modifier.height(14.dp))
        Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF7ED)), shape = RoundedCornerShape(7.dp)) {
            Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Error, null, tint = Amber)
                Spacer(Modifier.width(10.dp))
                Text("Disconnect both HC-05 modules from D0/D1 whenever USB firmware is uploaded. Reconnect them only after both USB cables are removed.", color = Color(0xFF7C2D12), fontWeight = FontWeight.Bold)
            }
        }
        Spacer(Modifier.height(14.dp))
        Card(Modifier.fillMaxWidth().border(1.dp, Line, RoundedCornerShape(7.dp)), colors = CardDefaults.cardColors(containerColor = Panel), shape = RoundedCornerShape(7.dp)) {
            Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Download, null, tint = Blue, modifier = Modifier.size(30.dp))
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text("APP UPDATES", color = Text, fontWeight = FontWeight.Black, fontSize = 14.sp)
                    Text(state.updateMessage, color = Muted, fontSize = 12.sp)
                }
                if (state.updateUrl != null) {
                    Button(onClick = { onOpenUpdate(state.updateUrl) }, shape = RoundedCornerShape(5.dp)) {
                        Text("DOWNLOAD ${state.updateVersion}", fontWeight = FontWeight.Bold)
                    }
                } else {
                    FilledTonalButton(onClick = onCheckUpdate, enabled = !state.updateChecking, shape = RoundedCornerShape(5.dp)) {
                        Icon(Icons.Default.Refresh, null, Modifier.size(18.dp)); Spacer(Modifier.width(7.dp)); Text(if (state.updateChecking) "CHECKING" else "CHECK UPDATE")
                    }
                }
            }
        }
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun WiringCard(title: String, lines: List<String>, modifier: Modifier) {
    Card(modifier.border(1.dp, Line, RoundedCornerShape(7.dp)), colors = CardDefaults.cardColors(containerColor = Panel), shape = RoundedCornerShape(7.dp)) {
        Column(Modifier.padding(18.dp)) {
            Text(title, color = Text, fontWeight = FontWeight.Black, fontSize = 15.sp)
            Text("DIRECT UART / NO DIVIDER", color = Blue, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 10.sp)
            Spacer(Modifier.height(12.dp))
            lines.forEach { Text(it, color = Muted, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.padding(vertical = 3.dp)) }
        }
    }
}

@Composable
private fun ProtocolLine(label: String, value: String) {
    Row(Modifier.fillMaxWidth().background(PanelSoft, RoundedCornerShape(4.dp)).padding(10.dp)) {
        Text(label, color = Muted, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 10.sp, modifier = Modifier.width(154.dp))
        Text(value, color = Text, fontFamily = FontFamily.Monospace, fontSize = 11.sp)
    }
    Spacer(Modifier.height(6.dp))
}

@Composable
private fun PageTitle(title: String, subtitle: String, modifier: Modifier = Modifier) {
    Column(modifier.padding(bottom = 14.dp)) {
        Text(title, color = Text, fontWeight = FontWeight.Black, fontSize = 25.sp)
        Text(subtitle, color = Muted, fontSize = 13.sp)
    }
}
