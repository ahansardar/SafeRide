from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from driver_support import CH341_INSTALLER_SHA256, DriverSupportError, verify_ch341_installer


class DriverSupportTests(unittest.TestCase):
    def test_bundled_ch341_installer_matches_pinned_hash(self):
        installer = Path(__file__).resolve().parents[1] / "drivers" / "CH341SER.EXE"
        self.assertTrue(installer.is_file())
        self.assertEqual(hashlib.sha256(installer.read_bytes()).hexdigest(), CH341_INSTALLER_SHA256)
        verify_ch341_installer(installer)

    def test_rejects_tampered_ch341_installer(self):
        with tempfile.TemporaryDirectory() as folder:
            installer = Path(folder) / "CH341SER.EXE"
            installer.write_bytes(b"MZ tampered")
            with self.assertRaisesRegex(DriverSupportError, "integrity"):
                verify_ch341_installer(installer)


if __name__ == "__main__":
    unittest.main()
