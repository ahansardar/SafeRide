from __future__ import annotations

import ctypes
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import subprocess

from uploader import resource_path


CH341_INSTALLER_SHA256 = "458c37bdafbe4ce3cd0baf728c232b4b765b36d7463956e9b94cdf099212cad1"


class DriverSupportError(RuntimeError):
    pass


@dataclass(frozen=True)
class DriverAssets:
    arduino_driver_root: Path | None
    ch341_installer: Path | None


def driver_assets() -> DriverAssets:
    avr_root = resource_path("tools", "arduino-data", "packages", "arduino", "hardware", "avr")
    driver_roots = sorted(
        (candidate / "drivers" for candidate in avr_root.glob("*") if (candidate / "drivers").is_dir()),
        reverse=True,
    )
    arduino_root = next(
        (candidate for candidate in driver_roots if any(candidate.rglob("*.inf"))),
        None,
    )
    ch341 = resource_path("drivers", "CH341SER.EXE")
    return DriverAssets(arduino_root, ch341 if ch341.is_file() else None)


def verify_ch341_installer(path: Path) -> None:
    if not path.is_file():
        raise DriverSupportError("The bundled CH340/CH341 installer is missing.")
    digest = hashlib.sha256(path.read_bytes()).hexdigest().lower()
    if digest != CH341_INSTALLER_SHA256:
        raise DriverSupportError("The bundled CH340/CH341 installer failed its integrity check.")


def _launch_elevated(executable: Path, arguments: list[str]) -> None:
    if os.name != "nt":
        raise DriverSupportError("USB driver installation is supported only on Windows.")
    parameters = subprocess.list2cmdline(arguments)
    shell_execute = ctypes.windll.shell32.ShellExecuteW
    shell_execute.restype = ctypes.c_void_p
    result = shell_execute(
        None,
        "runas",
        str(executable),
        parameters,
        str(executable.parent),
        1,
    )
    result_code = int(result or 0)
    if result_code <= 32:
        if result_code == 5:
            raise DriverSupportError("Administrator approval was cancelled or denied.")
        raise DriverSupportError(f"Windows could not start the driver installer (code {result_code}).")


def install_arduino_drivers(assets: DriverAssets | None = None) -> Path:
    selected = assets or driver_assets()
    if selected.arduino_driver_root is None:
        raise DriverSupportError("The bundled Arduino/FTDI driver packages are missing.")
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    pnputil = system_root / "System32" / "pnputil.exe"
    if not pnputil.is_file():
        raise DriverSupportError("Windows PnPUtil was not found.")
    inf_pattern = selected.arduino_driver_root / "*.inf"
    _launch_elevated(pnputil, ["/add-driver", str(inf_pattern), "/subdirs", "/install"])
    return selected.arduino_driver_root


def install_ch341_driver(assets: DriverAssets | None = None) -> Path:
    selected = assets or driver_assets()
    if selected.ch341_installer is None:
        raise DriverSupportError("The bundled CH340/CH341 installer is missing.")
    verify_ch341_installer(selected.ch341_installer)
    _launch_elevated(selected.ch341_installer, [])
    return selected.ch341_installer
