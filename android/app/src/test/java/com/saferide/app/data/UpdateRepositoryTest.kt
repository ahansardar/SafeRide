package com.saferide.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class UpdateRepositoryTest {
    private val repository = UpdateRepository()

    @Test
    fun comparesSemanticVersions() {
        assertTrue(repository.compareVersions("3.5.1", "3.5.0") > 0)
        assertTrue(repository.compareVersions("4.0.0", "3.99.99") > 0)
        assertEquals(0, repository.compareVersions("3.5.0", "3.5.0"))
    }
}
