package com.saferide.app.data

import com.saferide.app.BuildConfig
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

data class AppUpdate(
    val version: String,
    val releaseUrl: String,
)

class UpdateRepository {
    fun latestUpdate(): AppUpdate? {
        val connection = URL("https://api.github.com/repos/ahansardar/SafeRide/releases/latest")
            .openConnection() as HttpURLConnection
        connection.connectTimeout = 12_000
        connection.readTimeout = 12_000
        connection.setRequestProperty("Accept", "application/vnd.github+json")
        connection.setRequestProperty("User-Agent", "SafeRide-Android/${BuildConfig.VERSION_NAME}")
        try {
            if (connection.responseCode !in 200..299) error("GitHub returned HTTP ${connection.responseCode}")
            val payload = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
            val version = payload.getString("tag_name").removePrefix("v")
            val assets = payload.getJSONArray("assets")
            val hasAndroidApk = (0 until assets.length()).any { index ->
                assets.getJSONObject(index).optString("name") == "SafeRide-Android.apk"
            }
            if (!hasAndroidApk || compareVersions(version, BuildConfig.VERSION_NAME) <= 0) return null
            return AppUpdate(version, payload.getString("html_url"))
        } finally {
            connection.disconnect()
        }
    }

    internal fun compareVersions(candidate: String, current: String): Int {
        fun parts(value: String): List<Int> = value.substringBefore('-').split('.').map { it.toIntOrNull() ?: 0 }
        val left = parts(candidate)
        val right = parts(current)
        return (0 until maxOf(left.size, right.size))
            .asSequence()
            .map { index -> (left.getOrElse(index) { 0 }).compareTo(right.getOrElse(index) { 0 }) }
            .firstOrNull { it != 0 } ?: 0
    }
}
