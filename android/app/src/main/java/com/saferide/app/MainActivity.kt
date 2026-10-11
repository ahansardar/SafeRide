package com.saferide.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.WindowManager
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.core.content.ContextCompat
import androidx.core.net.toUri
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.saferide.app.ui.SafeRideApp
import com.saferide.app.ui.SafeRideViewModel
import com.saferide.app.ui.theme.SafeRideTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContent {
            SafeRideTheme {
                val model: SafeRideViewModel = viewModel()
                val state by model.state.collectAsStateWithLifecycle()
                val permission = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                    Manifest.permission.BLUETOOTH_CONNECT
                } else null
                val permissionLauncher = rememberLauncherForActivityResult(
                    ActivityResultContracts.RequestPermission(),
                    model::updatePermission,
                )
                val exportLauncher = rememberLauncherForActivityResult(
                    ActivityResultContracts.CreateDocument("text/plain"),
                ) { uri ->
                    if (uri != null) {
                        model.exportLogs(uri) { result ->
                            Toast.makeText(
                                this,
                                result.fold(
                                    onSuccess = { "SafeRide log exported" },
                                    onFailure = { "Export failed: ${it.message}" },
                                ),
                                Toast.LENGTH_LONG,
                            ).show()
                        }
                    }
                }
                val requestPermission = remember(permission) {
                    {
                        if (permission == null) model.updatePermission(true)
                        else permissionLauncher.launch(permission)
                    }
                }
                LaunchedEffect(permission) {
                    val granted = permission == null || ContextCompat.checkSelfPermission(
                        this@MainActivity,
                        permission,
                    ) == PackageManager.PERMISSION_GRANTED
                    model.updatePermission(granted)
                }
                SafeRideApp(
                    state = state,
                    onRequestPermission = requestPermission,
                    onOpenBluetoothSettings = {
                        startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS))
                    },
                    onRefresh = model::refreshDevices,
                    onSelectDevice = model::selectDevice,
                    onAutoIdentify = model::autoIdentify,
                    onConnect = model::connect,
                    onDisconnect = model::disconnect,
                    onExport = {
                        exportLauncher.launch("SafeRide-session-${System.currentTimeMillis()}.txt")
                    },
                    onCheckUpdate = model::checkForUpdates,
                    onOpenUpdate = { url -> startActivity(Intent(Intent.ACTION_VIEW, url.toUri())) },
                )
            }
        }
    }

    override fun onResume() {
        super.onResume()
        // The composable refreshes after permission changes. Bluetooth settings
        // returns are also reflected when the user taps Rescan.
    }
}
