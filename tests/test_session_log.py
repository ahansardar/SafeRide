from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from session_log import SessionLog


class SessionLogTests(unittest.TestCase):
    def test_exports_setup_raw_state_and_error_entries(self):
        started = datetime(2026, 10, 7, 6, 30, tzinfo=timezone.utc)
        event_time = datetime(2026, 10, 7, 6, 31, 2, 125000, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            log = SessionLog("3.3.0", root=root / "sessions", started_at=started)
            log.append("setup", "Found 2 serial ports.", event_time)
            log.append("raw-helmet", "H:1,A:0,D:0,M:187", event_time)
            log.append("state", "ENGINE UNLOCKED", event_time)
            log.append("error", "line one\nline two", event_time)
            exported = log.export(root / "SafeRide Logs.txt")
            log.close()

            text = exported.read_text(encoding="utf-8")
            self.assertIn("Version: 3.3.0", text)
            self.assertIn("SETUP\tFound 2 serial ports.", text)
            self.assertIn("RAW-HELMET\tH:1,A:0,D:0,M:187", text)
            self.assertIn("STATE\tENGINE UNLOCKED", text)
            self.assertIn("ERROR\tline one\\nline two", text)


if __name__ == "__main__":
    unittest.main()
