package com.saferide.app.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class TelemetryTest {
    @Test
    fun parsesHelmetPacketAndClampsMq3() {
        val packet = parsePacket("H:1,A:0,D:1,M:1400")!!
        assertTrue(packet.helmetWorn)
        assertFalse(packet.alcoholDetected)
        assertTrue(packet.drowsy)
        assertEquals(1023, packet.mq3)
        assertNull(packet.engineUnlocked)
    }

    @Test
    fun parsesVehicleDecision() {
        val packet = parsePacket("H:1,A:0,D:0,M:220,ENGINE:1,LINK:1")!!
        assertTrue(packet.engineUnlocked == true)
        assertTrue(packet.linkAlive == true)
        assertEquals("All safety checks passed", engineReason(packet))
    }

    @Test
    fun rejectsNoiseAndClassifiesControllers() {
        assertNull(parsePacket("HC-05 ready"))
        assertEquals(ControllerRole.HELMET, classifySafeRideLine("H:1,A:0,D:0,M:100"))
        assertEquals(ControllerRole.VEHICLE, classifySafeRideLine("H:1,A:0,D:0,M:100,ENGINE:1,LINK:1"))
    }

    @Test
    fun forwardsOnlyCanonicalHelmetFrames() {
        assertEquals("H:1,A:0,D:0,M:218", forwardableHelmetPacket("H:1,A:0,D:0,M:218"))
        assertNull(forwardableHelmetPacket("DEVICE:HELMET,FIRMWARE:3.1"))
        assertNull(forwardableHelmetPacket("H:1,A:0,D:0,M:218,ENGINE:1,LINK:1"))
    }

    @Test
    fun engineReasonMatchesDesktopPriority() {
        assertEquals("Helmet link offline", engineReason(Telemetry(linkAlive = false)))
        assertEquals("Helmet not detected", engineReason(Telemetry(linkAlive = true)))
        assertEquals("Alcohol detected", engineReason(Telemetry(true, true, false, 600, false, true)))
        assertEquals("Drowsiness detected", engineReason(Telemetry(true, false, true, 200, false, true)))
    }
}
