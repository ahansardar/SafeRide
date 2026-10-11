package com.saferide.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val Navy = Color(0xFF0F172A)
val Blue = Color(0xFF2563EB)
val BlueDark = Color(0xFF1D4ED8)
val Green = Color(0xFF15803D)
val Red = Color(0xFFDC2626)
val Amber = Color(0xFFD97706)
val Canvas = Color(0xFFF1F5F9)
val Panel = Color(0xFFFFFFFF)
val PanelSoft = Color(0xFFF8FAFC)
val Line = Color(0xFFCBD5E1)
val Text = Color(0xFF0F172A)
val Muted = Color(0xFF475569)
val Console = Color(0xFF020617)

private val colors = lightColorScheme(
    primary = Blue,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDBEAFE),
    onPrimaryContainer = Navy,
    secondary = Green,
    error = Red,
    background = Canvas,
    onBackground = Text,
    surface = Panel,
    onSurface = Text,
    surfaceVariant = PanelSoft,
    onSurfaceVariant = Muted,
    outline = Line,
)

@Composable
fun SafeRideTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = colors, content = content)
}
