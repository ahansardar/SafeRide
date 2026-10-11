param(
    [ValidateSet("Debug", "Release")]
    [string]$Variant = "Debug",
    [string]$AndroidSdk = "D:\sdk",
    [string]$JavaHome = "D:\Android Studio\jbr"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$androidRoot = Join-Path $projectRoot "android"
$gradleHome = Join-Path $projectRoot ".gradle-android"
$androidUserHome = Join-Path $projectRoot ".android-user"
$releaseRoot = Join-Path $projectRoot "release"

if (-not (Test-Path -LiteralPath (Join-Path $AndroidSdk "platform-tools"))) {
    throw "Android SDK not found at $AndroidSdk. Pass -AndroidSdk with the installed SDK path."
}
if (-not (Test-Path -LiteralPath (Join-Path $JavaHome "bin\java.exe"))) {
    throw "Android Studio JBR not found at $JavaHome. Pass -JavaHome with a Java 17+ JDK path."
}

$env:ANDROID_HOME = $AndroidSdk
$env:ANDROID_SDK_ROOT = $AndroidSdk
$env:ANDROID_USER_HOME = $androidUserHome
$env:GRADLE_USER_HOME = $gradleHome
$env:JAVA_HOME = $JavaHome

New-Item -ItemType Directory -Force -Path $gradleHome, $androidUserHome, $releaseRoot | Out-Null
$localProperties = Join-Path $androidRoot "local.properties"
$escapedSdk = $AndroidSdk.Replace("\", "\\").Replace(":", "\:")
Set-Content -LiteralPath $localProperties -Value "sdk.dir=$escapedSdk" -Encoding ASCII

Push-Location $androidRoot
try {
    & .\gradlew.bat --no-daemon testDebugUnitTest lintDebug
    if ($LASTEXITCODE -ne 0) { throw "SafeRide Android tests or lint checks failed." }

    $task = if ($Variant -eq "Release") { "assembleRelease" } else { "assembleDebug" }
    & .\gradlew.bat --no-daemon $task
    if ($LASTEXITCODE -ne 0) { throw "SafeRide Android $Variant build failed." }
} finally {
    Pop-Location
}

$variantLower = $Variant.ToLowerInvariant()
$sourceApk = Join-Path $androidRoot "app\build\outputs\apk\$variantLower\app-$variantLower.apk"
if (-not (Test-Path -LiteralPath $sourceApk)) {
    throw "Expected signed APK was not produced: $sourceApk"
}
$destination = Join-Path $releaseRoot "SafeRide-Android.apk"
Copy-Item -LiteralPath $sourceApk -Destination $destination -Force
$hash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
Set-Content -LiteralPath (Join-Path $releaseRoot "SafeRide-Android.sha256.txt") -Value "$hash  SafeRide-Android.apk" -Encoding ASCII

Write-Host "SAFERIDE_ANDROID_OK" -ForegroundColor Green
Write-Host "APK: $destination"
Write-Host "SHA-256: $hash"
