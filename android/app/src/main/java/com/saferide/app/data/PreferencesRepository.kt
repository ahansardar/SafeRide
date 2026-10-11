package com.saferide.app.data

import android.content.Context
import androidx.core.content.edit

data class ControllerSelection(
    val helmetAddress: String = "",
    val vehicleAddress: String = "",
)

class PreferencesRepository(context: Context) {
    private val preferences = context.getSharedPreferences("saferide_connections", Context.MODE_PRIVATE)

    fun load(): ControllerSelection = ControllerSelection(
        helmetAddress = preferences.getString("helmet_address", "").orEmpty(),
        vehicleAddress = preferences.getString("vehicle_address", "").orEmpty(),
    )

    fun save(selection: ControllerSelection) {
        require(selection.helmetAddress != selection.vehicleAddress || selection.helmetAddress.isBlank()) {
            "Helmet and vehicle modules must be different"
        }
        preferences.edit {
            putString("helmet_address", selection.helmetAddress)
            putString("vehicle_address", selection.vehicleAddress)
        }
    }
}
