package com.saferide.app.data

import android.content.Context
import android.net.Uri
import com.saferide.app.BuildConfig
import java.io.File
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter

class SessionLog(private val context: Context) {
    private val startedAt = OffsetDateTime.now()
    private val lock = Any()
    val file: File

    init {
        val directory = File(context.filesDir, "logs").apply { mkdirs() }
        val stamp = startedAt.format(DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss"))
        file = File(directory, "SafeRide-Android-$stamp.log")
        file.writeText(
            "SafeRide Android session log\n" +
                "Version: ${BuildConfig.VERSION_NAME}\n" +
                "Started: ${startedAt.format(DateTimeFormatter.ISO_OFFSET_DATE_TIME)}\n" +
                "Time\tCategory\tMessage\n",
        )
    }

    fun append(category: String, message: Any?) {
        val clean = message.toString().replace("\r", "").replace("\n", "\\n")
        val line = "${OffsetDateTime.now().format(DateTimeFormatter.ISO_OFFSET_DATE_TIME)}\t${category.uppercase()}\t$clean\n"
        synchronized(lock) { file.appendText(line) }
    }

    fun export(destination: Uri) {
        synchronized(lock) {
            context.contentResolver.openOutputStream(destination, "wt")?.use { output ->
                file.inputStream().use { input -> input.copyTo(output) }
            } ?: error("Android could not open the selected export file")
        }
    }

    fun readTail(maxLines: Int = 300): List<String> = synchronized(lock) {
        file.readLines().takeLast(maxLines)
    }
}
