from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Callable, Iterable, Protocol

import serial


USB_MODE = "usb"
BLUETOOTH_MODE = "bluetooth"
TRANSPORT_MODES = (USB_MODE, BLUETOOTH_MODE)


class PortLike(Protocol):
    device: str
    description: str
    hwid: str


@dataclass
class ConnectionPreferences:
    version: int = 1
    mode: str = USB_MODE
    helmet_bluetooth_port: str = ""
    vehicle_bluetooth_port: str = ""

    def validate(self) -> None:
        if self.mode not in TRANSPORT_MODES:
            raise ValueError(f"Unsupported connection mode: {self.mode}")
        if (
            self.helmet_bluetooth_port
            and self.helmet_bluetooth_port == self.vehicle_bluetooth_port
        ):
            raise ValueError("Helmet and vehicle Bluetooth ports must be different")

    @classmethod
    def from_dict(cls, raw: dict) -> "ConnectionPreferences":
        preferences = cls(
            version=int(raw.get("version", 1)),
            mode=str(raw.get("mode", USB_MODE)),
            helmet_bluetooth_port=str(raw.get("helmet_bluetooth_port", "")),
            vehicle_bluetooth_port=str(raw.get("vehicle_bluetooth_port", "")),
        )
        preferences.validate()
        return preferences

    def to_dict(self) -> dict:
        return asdict(self)


def preferences_path() -> Path:
    override = os.environ.get("SAFERIDE_CONNECTIONS_PATH")
    if override:
        return Path(override)
    base = Path(os.environ.get("APPDATA", Path.home()))
    return base / "SafeRide" / "connections.json"


def load_connection_preferences() -> ConnectionPreferences:
    path = preferences_path()
    if not path.exists():
        return ConnectionPreferences()
    try:
        return ConnectionPreferences.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return ConnectionPreferences()


def save_connection_preferences(preferences: ConnectionPreferences) -> Path:
    preferences.validate()
    path = preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(preferences.to_dict(), indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def is_bluetooth_port(port: PortLike) -> bool:
    identity = f"{port.device} {port.description} {port.hwid}".casefold()
    return any(token in identity for token in ("bluetooth", "bthenum", "bthmodem"))


def bluetooth_ports(ports: Iterable[PortLike]) -> list[PortLike]:
    return [port for port in ports if is_bluetooth_port(port)]


def open_windows_bluetooth_settings() -> None:
    if os.name != "nt":
        raise OSError("Bluetooth pairing is available only on Windows")
    os.startfile("ms-settings:bluetooth")  # type: ignore[attr-defined]


def classify_saferide_line(line: str) -> str | None:
    cleaned = line.strip().upper()
    if "DEVICE:HELMET" in cleaned:
        return "helmet"
    if "DEVICE:VEHICLE" in cleaned:
        return "vehicle"
    if cleaned.startswith("H:") and ",M:" in cleaned:
        return "vehicle" if ",ENGINE:" in cleaned or ",LINK:" in cleaned else "helmet"
    return None


def probe_saferide_port(
    device: str,
    timeout_seconds: float = 2.5,
    serial_factory: Callable[..., object] = serial.Serial,
) -> str | None:
    """Identify a Bluetooth-connected SafeRide controller from live packets."""
    port = serial_factory(device, 9600, timeout=0.25, write_timeout=0.5)
    try:
        import time

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            line = port.readline().decode("utf-8", errors="replace")
            role = classify_saferide_line(line)
            if role:
                return role
        return None
    finally:
        port.close()
