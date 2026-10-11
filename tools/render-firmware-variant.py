from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from device_config import SafeRideConfig
from firmware_builder import render_firmware


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a default SafeRide firmware transport variant")
    parser.add_argument("mode", choices=("usb", "bluetooth"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    helmet, vehicle = render_firmware(SafeRideConfig(), args.output, args.mode)
    print(helmet)
    print(vehicle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
