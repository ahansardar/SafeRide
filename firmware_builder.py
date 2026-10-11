from __future__ import annotations

from pathlib import Path
import re
import sys

from device_config import SafeRideConfig
from connection_settings import BLUETOOTH_MODE, TRANSPORT_MODES


def resource_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath(*parts)


def _replace_constant(source: str, c_type: str, name: str, value: str) -> str:
    pattern = rf"const {re.escape(c_type)} {re.escape(name)} = [^;]+;"
    updated, count = re.subn(pattern, f"const {c_type} {name} = {value};", source)
    if count != 1:
        raise RuntimeError(f"Firmware template constant {name} was not found exactly once")
    return updated


def render_firmware(config: SafeRideConfig, output_root: Path, transport_mode: str = "usb") -> tuple[Path, Path]:
    config.validate()
    if transport_mode not in TRANSPORT_MODES:
        raise ValueError(f"Unsupported firmware transport: {transport_mode}")
    helmet_source = resource_path("firmware", "helmet", "helmet.ino").read_text(encoding="utf-8")
    vehicle_source = resource_path("firmware", "vehicle", "vehicle.ino").read_text(encoding="utf-8")

    helmet_values = {
        ("uint8_t", "ALCOHOL_PIN"): config.helmet.alcohol_pin.upper(),
        ("uint8_t", "HELMET_IR_PIN"): str(config.helmet.helmet_ir_pin),
        ("uint8_t", "EYE_IR_PIN"): str(config.helmet.eye_ir_pin),
        ("uint8_t", "LED_PIN"): str(config.helmet.led_pin),
        ("uint8_t", "BUZZER_PIN"): str(config.helmet.buzzer_pin),
        ("int", "ALCOHOL_THRESHOLD"): str(config.helmet.alcohol_threshold),
        ("unsigned long", "DROWSY_LIMIT_MS"): str(config.helmet.drowsy_limit_ms),
        ("unsigned long", "SEND_INTERVAL_MS"): str(config.helmet.send_interval_ms),
        ("bool", "HELMET_ACTIVE_LOW"): str(config.helmet.helmet_active_low).lower(),
        ("bool", "EYE_ACTIVE_LOW"): str(config.helmet.eye_active_low).lower(),
        ("bool", "BLUETOOTH_MODE"): str(transport_mode == BLUETOOTH_MODE).lower(),
    }
    for (c_type, name), value in helmet_values.items():
        helmet_source = _replace_constant(helmet_source, c_type, name, value)

    vehicle_values = {
        ("uint8_t", "RELAY_PIN"): str(config.vehicle.relay_pin),
        ("uint8_t", "LED_PIN"): str(config.vehicle.led_pin),
        ("uint8_t", "BUZZER_PIN"): str(config.vehicle.buzzer_pin),
        ("unsigned long", "LINK_TIMEOUT_MS"): str(config.vehicle.link_timeout_ms),
        ("unsigned long", "SEND_INTERVAL_MS"): str(config.vehicle.send_interval_ms),
        ("bool", "RELAY_ACTIVE_HIGH"): str(config.vehicle.relay_active_high).lower(),
        ("bool", "BLUETOOTH_MODE"): str(transport_mode == BLUETOOTH_MODE).lower(),
    }
    for (c_type, name), value in vehicle_values.items():
        vehicle_source = _replace_constant(vehicle_source, c_type, name, value)

    helmet_dir = output_root / "helmet"
    vehicle_dir = output_root / "vehicle"
    helmet_dir.mkdir(parents=True, exist_ok=True)
    vehicle_dir.mkdir(parents=True, exist_ok=True)
    (helmet_dir / "helmet.ino").write_text(helmet_source, encoding="utf-8")
    (vehicle_dir / "vehicle.ino").write_text(vehicle_source, encoding="utf-8")
    return helmet_dir, vehicle_dir

