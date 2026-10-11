import os
from pathlib import Path
import tempfile
import unittest

from device_config import SafeRideConfig, save_config, load_config
from firmware_builder import render_firmware


class DeviceConfigTests(unittest.TestCase):
    def test_rejects_serial_pins(self):
        config = SafeRideConfig()
        config.helmet.helmet_ir_pin = 1
        with self.assertRaisesRegex(ValueError, "reserved for USB"):
            config.validate()

    def test_rejects_duplicate_pins(self):
        config = SafeRideConfig()
        config.vehicle.led_pin = config.vehicle.relay_pin
        with self.assertRaisesRegex(ValueError, "cannot both use"):
            config.validate()

    def test_hc05_uses_fixed_hardware_serial_pins(self):
        config = SafeRideConfig()
        config.helmet.bluetooth_rx_pin = 10
        with self.assertRaisesRegex(ValueError, "RX D0 and TX D1"):
            config.validate()

    def test_migrates_old_software_serial_configuration(self):
        config = SafeRideConfig.from_dict({
            "helmet": {"bluetooth_rx_pin": 10, "bluetooth_tx_pin": 11, "alcohol_threshold": 525},
            "vehicle": {"bluetooth_rx_pin": 10, "bluetooth_tx_pin": 11, "link_timeout_ms": 2500},
        })
        self.assertEqual((config.helmet.bluetooth_rx_pin, config.helmet.bluetooth_tx_pin), (0, 1))
        self.assertEqual((config.vehicle.bluetooth_rx_pin, config.vehicle.bluetooth_tx_pin), (0, 1))
        self.assertEqual(config.helmet.alcohol_threshold, 525)
        self.assertEqual(config.vehicle.link_timeout_ms, 2500)

    def test_board_pin_limits(self):
        config = SafeRideConfig()
        config.helmet.board = "uno"
        config.helmet.alcohol_pin = "A7"
        with self.assertRaisesRegex(ValueError, "maximum is A5"):
            config.validate()

    def test_persists_valid_config(self):
        with tempfile.TemporaryDirectory() as folder:
            old = os.environ.get("SAFERIDE_CONFIG_PATH")
            os.environ["SAFERIDE_CONFIG_PATH"] = str(Path(folder) / "config.json")
            try:
                config = SafeRideConfig()
                config.helmet.alcohol_threshold = 512
                save_config(config)
                self.assertEqual(load_config().helmet.alcohol_threshold, 512)
            finally:
                if old is None:
                    os.environ.pop("SAFERIDE_CONFIG_PATH", None)
                else:
                    os.environ["SAFERIDE_CONFIG_PATH"] = old

    def test_renders_selected_constants(self):
        config = SafeRideConfig()
        config.helmet.alcohol_pin = "A2"
        config.helmet.alcohol_threshold = 515
        config.vehicle.relay_pin = 9
        config.vehicle.relay_active_high = False
        with tempfile.TemporaryDirectory() as folder:
            helmet, vehicle = render_firmware(config, Path(folder))
            helmet_text = (helmet / "helmet.ino").read_text(encoding="utf-8")
            vehicle_text = (vehicle / "vehicle.ino").read_text(encoding="utf-8")
            self.assertIn("const uint8_t ALCOHOL_PIN = A2;", helmet_text)
            self.assertIn("const int ALCOHOL_THRESHOLD = 515;", helmet_text)
            self.assertIn("const uint8_t RELAY_PIN = 9;", vehicle_text)
            self.assertIn("const bool RELAY_ACTIVE_HIGH = false;", vehicle_text)

    def test_renders_bluetooth_firmware_on_hardware_serial(self):
        config = SafeRideConfig()
        with tempfile.TemporaryDirectory() as folder:
            helmet, vehicle = render_firmware(config, Path(folder), "bluetooth")
            helmet_text = (helmet / "helmet.ino").read_text(encoding="utf-8")
            vehicle_text = (vehicle / "vehicle.ino").read_text(encoding="utf-8")
            self.assertIn("const bool BLUETOOTH_MODE = true;", helmet_text)
            self.assertIn("const bool BLUETOOTH_MODE = true;", vehicle_text)
            self.assertNotIn("SoftwareSerial", helmet_text)
            self.assertNotIn("SoftwareSerial", vehicle_text)
            self.assertIn('Serial.print("DEVICE:HELMET', helmet_text)
            self.assertIn('Serial.print("DEVICE:VEHICLE', vehicle_text)


if __name__ == "__main__":
    unittest.main()

