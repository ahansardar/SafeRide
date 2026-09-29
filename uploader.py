from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Callable

from device_config import BOARD_PROFILES


LogFn = Callable[[str], None]


def resource_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath(*parts)


def arduino_cli_path() -> Path | None:
    bundled = resource_path("tools", "arduino-cli.exe")
    if bundled.exists():
        return bundled
    from shutil import which
    found = which("arduino-cli")
    return Path(found) if found else None


def portable_config_path() -> Path | None:
    config = resource_path("tools", "arduino-cli.yaml")
    return config if config.exists() else None


def candidate_boards(port_description: str = "", board_profile: str = "auto", vid: int | None = None, pid: int | None = None) -> list[str]:
    profile = BOARD_PROFILES.get(board_profile)
    if profile is None:
        raise ValueError(f"Unknown board profile: {board_profile}")
    if profile.fqbn:
        return [profile.fqbn]
    text = port_description.lower()
    known_usb = (vid, pid)
    if "mega" in text or known_usb in {(0x2341, 0x0042), (0x2341, 0x0010), (0x2A03, 0x0042), (0x2A03, 0x0010)}:
        return ["arduino:avr:mega", "arduino:avr:uno"]
    if "nano" in text:
        return [
            "arduino:avr:nano:cpu=atmega328old",
            "arduino:avr:nano:cpu=atmega328",
            "arduino:avr:uno",
        ]
    return [
        "arduino:avr:uno",
        "arduino:avr:nano:cpu=atmega328old",
        "arduino:avr:nano:cpu=atmega328",
        "arduino:avr:mega",
    ]


def _run(command: list[str], log: LogFn) -> tuple[bool, str]:
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    environment = os.environ.copy()
    data_dir = resource_path("tools", "arduino-data")
    environment["ARDUINO_DIRECTORIES_DATA"] = str(data_dir)
    environment["ARDUINO_DIRECTORIES_DOWNLOADS"] = str(data_dir / "staging")
    environment["ARDUINO_DIRECTORIES_USER"] = str(resource_path("tools", "arduino-sketchbook"))
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        creationflags=creationflags,
        env=environment,
    )
    output_lines: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        clean = line.rstrip()
        output_lines.append(clean)
        if clean:
            log(clean)
    return proc.wait() == 0, "\n".join(output_lines)


def upload_sketch(
    port: str,
    sketch_name: str,
    log: LogFn,
    port_description: str = "",
    board_profile: str = "auto",
    vid: int | None = None,
    pid: int | None = None,
    sketch_path: Path | None = None,
) -> str:
    cli = arduino_cli_path()
    if not cli:
        raise RuntimeError("Arduino CLI is missing. Run tools\\build.ps1 to create the complete app bundle.")

    sketch = sketch_path or resource_path("firmware", sketch_name)
    if not sketch.exists():
        raise RuntimeError(f"Bundled firmware was not found: {sketch_name}")

    base = [str(cli)]
    failures: list[str] = []
    for fqbn in candidate_boards(port_description, board_profile, vid, pid):
        short_name = fqbn.replace("arduino:avr:", "")
        log(f"Trying {short_name} on {port}...")
        with tempfile.TemporaryDirectory(prefix="saferide-build-") as build_dir:
            compile_cmd = base + [
                "compile", "--fqbn", fqbn,
                "--build-path", build_dir,
                str(sketch),
            ]
            compiled, compile_output = _run(compile_cmd, log)
            if not compiled:
                failures.append(f"{short_name}: compile failed")
                continue

            upload_cmd = base + [
                "upload", "--fqbn", fqbn,
                "--port", port,
                "--input-dir", build_dir,
                str(sketch),
            ]
            uploaded, upload_output = _run(upload_cmd, log)
            if uploaded:
                log(f"Upload complete: {short_name} on {port}")
                return fqbn
            last_line = upload_output.splitlines()[-1] if upload_output.splitlines() else "upload failed"
            failures.append(f"{short_name}: {last_line}")

    raise RuntimeError("No compatible Uno/Nano profile uploaded successfully. " + " | ".join(failures))

