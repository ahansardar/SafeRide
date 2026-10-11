import os
from pathlib import Path
import tempfile
import unittest

from connection_settings import (
    BLUETOOTH_MODE,
    ConnectionPreferences,
    bluetooth_ports,
    classify_saferide_line,
    load_connection_preferences,
    probe_saferide_port,
    save_connection_preferences,
)


class FakePortInfo:
    def __init__(self, device: str, description: str, hwid: str = ""):
        self.device = device
        self.description = description
        self.hwid = hwid


class FakeSerial:
    def __init__(self, lines: list[bytes]):
        self.lines = list(lines)
        self.closed = False

    def readline(self) -> bytes:
        return self.lines.pop(0) if self.lines else b""

    def close(self) -> None:
        self.closed = True


class ConnectionSettingsTests(unittest.TestCase):
    def test_detects_windows_bluetooth_serial_ports(self):
        ports = [
            FakePortInfo("COM3", "USB-SERIAL CH340"),
            FakePortInfo("COM8", "Standard Serial over Bluetooth link"),
            FakePortInfo("COM9", "Communications Port", "BTHENUM\\{00001101}"),
        ]
        self.assertEqual([port.device for port in bluetooth_ports(ports)], ["COM8", "COM9"])

    def test_classifies_live_helmet_and_vehicle_packets(self):
        self.assertEqual(classify_saferide_line("H:1,A:0,D:0,M:213"), "helmet")
        self.assertEqual(
            classify_saferide_line("H:1,A:0,D:0,M:213,ENGINE:1,LINK:1"),
            "vehicle",
        )
        self.assertIsNone(classify_saferide_line("noise"))

    def test_probe_identifies_controller_and_closes_port(self):
        fake = FakeSerial([b"noise\n", b"H:1,A:0,D:0,M:210\n"])
        role = probe_saferide_port(
            "COM8",
            timeout_seconds=0.1,
            serial_factory=lambda *_args, **_kwargs: fake,
        )
        self.assertEqual(role, "helmet")
        self.assertTrue(fake.closed)

    def test_persists_mode_and_paired_ports(self):
        with tempfile.TemporaryDirectory() as folder:
            old = os.environ.get("SAFERIDE_CONNECTIONS_PATH")
            os.environ["SAFERIDE_CONNECTIONS_PATH"] = str(Path(folder) / "connections.json")
            try:
                preferences = ConnectionPreferences(
                    mode=BLUETOOTH_MODE,
                    helmet_bluetooth_port="COM8",
                    vehicle_bluetooth_port="COM9",
                )
                save_connection_preferences(preferences)
                self.assertEqual(load_connection_preferences(), preferences)
            finally:
                if old is None:
                    os.environ.pop("SAFERIDE_CONNECTIONS_PATH", None)
                else:
                    os.environ["SAFERIDE_CONNECTIONS_PATH"] = old


if __name__ == "__main__":
    unittest.main()
