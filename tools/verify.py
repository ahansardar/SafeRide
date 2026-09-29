"""Repeatable release checks for the dashboard data path."""

from __future__ import annotations

from pathlib import Path
import ast
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    required = [
        ROOT / "app.py",
        ROOT / "core.py",
        ROOT / "uploader.py",
        ROOT / "device_config.py",
        ROOT / "firmware_builder.py",
        ROOT / "updater.py",
        ROOT / "version.py",
        ROOT / "firmware" / "helmet" / "helmet.ino",
        ROOT / "firmware" / "vehicle" / "vehicle.ino",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        print("Missing required files:")
        print("\n".join(missing))
        return 1

    for source in (
        ROOT / "app.py", ROOT / "core.py", ROOT / "uploader.py", ROOT / "device_config.py",
        ROOT / "firmware_builder.py", ROOT / "updater.py", ROOT / "version.py",
    ):
        ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        print(f"PASS Python syntax: {source.name}")

    helmet = (ROOT / "firmware" / "helmet" / "helmet.ino").read_text(encoding="utf-8")
    vehicle = (ROOT / "firmware" / "vehicle" / "vehicle.ino").read_text(encoding="utf-8")
    for field in ("H:", "A:", "D:", "M:"):
        if field not in helmet or field not in vehicle:
            print(f"FAIL telemetry field {field} missing from firmware")
            return 1
    for field in ("ENGINE:", "LINK:"):
        if field not in vehicle:
            print(f"FAIL vehicle field {field} missing")
            return 1
    print("PASS matching firmware packet contract")

    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

