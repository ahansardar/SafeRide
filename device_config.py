from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import re


@dataclass(frozen=True)
class BoardProfile:
    key: str
    label: str
    fqbn: str | None
    max_digital_pin: int
    max_analog_pin: int


BOARD_PROFILES = {
    "auto": BoardProfile("auto", "Auto detect (Uno / Nano / Mega)", None, 13, 5),
    "uno": BoardProfile("uno", "Arduino Uno / compatible", "arduino:avr:uno", 13, 5),
    "nano": BoardProfile("nano", "Arduino Nano (new bootloader)", "arduino:avr:nano:cpu=atmega328", 13, 7),
    "nano_old": BoardProfile("nano_old", "Arduino Nano (old bootloader)", "arduino:avr:nano:cpu=atmega328old", 13, 7),
    "mega": BoardProfile("mega", "Arduino Mega 2560", "arduino:avr:mega", 53, 15),
}


@dataclass
class HelmetConfig:
    board: str = "auto"
    alcohol_pin: str = "A0"
    helmet_ir_pin: int = 2
    eye_ir_pin: int = 3
    led_pin: int = 7
    buzzer_pin: int = 8
    bluetooth_rx_pin: int = 0
    bluetooth_tx_pin: int = 1
    alcohol_threshold: int = 400
    drowsy_limit_ms: int = 3000
    send_interval_ms: int = 250
    helmet_active_low: bool = True
    eye_active_low: bool = True


@dataclass
class VehicleConfig:
    board: str = "auto"
    relay_pin: int = 4
    led_pin: int = 5
    buzzer_pin: int = 6
    bluetooth_rx_pin: int = 0
    bluetooth_tx_pin: int = 1
    link_timeout_ms: int = 2000
    send_interval_ms: int = 250
    relay_active_high: bool = True


@dataclass
class SafeRideConfig:
    version: int = 1
    helmet: HelmetConfig = field(default_factory=HelmetConfig)
    vehicle: VehicleConfig = field(default_factory=VehicleConfig)

    def validate(self) -> None:
        _validate_board(self.helmet.board, "helmet")
        _validate_board(self.vehicle.board, "vehicle")
        _validate_analog(self.helmet.alcohol_pin, self.helmet.board, "MQ-3 alcohol pin")
        _validate_digital_group(
            {
                "helmet IR": self.helmet.helmet_ir_pin,
                "eye IR": self.helmet.eye_ir_pin,
                "helmet LED": self.helmet.led_pin,
                "helmet buzzer": self.helmet.buzzer_pin,
            },
            self.helmet.board,
        )
        _validate_digital_group(
            {
                "relay": self.vehicle.relay_pin,
                "vehicle LED": self.vehicle.led_pin,
                "vehicle buzzer": self.vehicle.buzzer_pin,
            },
            self.vehicle.board,
        )
        _validate_hardware_serial(self.helmet.bluetooth_rx_pin, self.helmet.bluetooth_tx_pin, "helmet")
        _validate_hardware_serial(self.vehicle.bluetooth_rx_pin, self.vehicle.bluetooth_tx_pin, "vehicle")
        _range(self.helmet.alcohol_threshold, 0, 1023, "Alcohol threshold")
        _range(self.helmet.drowsy_limit_ms, 250, 30000, "Drowsiness time")
        _range(self.helmet.send_interval_ms, 100, 2000, "Helmet send interval")
        _range(self.vehicle.link_timeout_ms, 500, 30000, "Link timeout")
        _range(self.vehicle.send_interval_ms, 100, 2000, "Vehicle send interval")

    @classmethod
    def from_dict(cls, raw: dict) -> "SafeRideConfig":
        helmet_values = dict(raw.get("helmet", {}))
        vehicle_values = dict(raw.get("vehicle", {}))
        # SafeRide 3.4.0 stored editable SoftwareSerial pins here. Bluetooth now
        # uses the fixed hardware UART, so migrate old configurations without
        # discarding the user's sensor pins or thresholds.
        helmet_values["bluetooth_rx_pin"] = 0
        helmet_values["bluetooth_tx_pin"] = 1
        vehicle_values["bluetooth_rx_pin"] = 0
        vehicle_values["bluetooth_tx_pin"] = 1
        config = cls(
            version=int(raw.get("version", 1)),
            helmet=HelmetConfig(**helmet_values),
            vehicle=VehicleConfig(**vehicle_values),
        )
        config.validate()
        return config

    def to_dict(self) -> dict:
        return asdict(self)


def _validate_board(key: str, owner: str) -> None:
    if key not in BOARD_PROFILES:
        raise ValueError(f"Unsupported {owner} board profile: {key}")


def _validate_analog(value: str, board_key: str, name: str) -> None:
    match = re.fullmatch(r"A(\d{1,2})", value.strip().upper())
    if not match:
        raise ValueError(f"{name} must look like A0, A1, or another analog pin")
    pin = int(match.group(1))
    maximum = BOARD_PROFILES[board_key].max_analog_pin
    if pin > maximum:
        raise ValueError(f"{name} {value} is not available on {BOARD_PROFILES[board_key].label}; maximum is A{maximum}")


def _validate_digital_group(values: dict[str, int], board_key: str) -> None:
    maximum = BOARD_PROFILES[board_key].max_digital_pin
    used: dict[int, str] = {}
    for name, pin in values.items():
        if pin < 2 or pin > maximum:
            raise ValueError(f"{name} pin D{pin} must be between D2 and D{maximum}; D0 and D1 are reserved for USB upload serial")
        if pin in used:
            raise ValueError(f"{name} and {used[pin]} cannot both use D{pin}")
        used[pin] = name


def _validate_hardware_serial(rx_pin: int, tx_pin: int, owner: str) -> None:
    if (rx_pin, tx_pin) != (0, 1):
        raise ValueError(f"{owner.capitalize()} HC-05 must use hardware serial pins RX D0 and TX D1")


def _range(value: int, minimum: int, maximum: int, name: str) -> None:
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")


def config_path() -> Path:
    override = os.environ.get("SAFERIDE_CONFIG_PATH")
    if override:
        return Path(override)
    base = Path(os.environ.get("APPDATA", Path.home()))
    return base / "SafeRide" / "config.json"


def load_config() -> SafeRideConfig:
    path = config_path()
    if not path.exists():
        return SafeRideConfig()
    try:
        return SafeRideConfig.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return SafeRideConfig()


def save_config(config: SafeRideConfig) -> Path:
    config.validate()
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")
    temporary.replace(path)
    return path

