from __future__ import annotations

from dataclasses import dataclass
import re


FIELD_RE = re.compile(r"(?:^|,)(H|A|D|M|ENGINE|LINK|BT):(-?\d+)")


@dataclass
class Telemetry:
    helmet: bool = False
    alcohol: bool = False
    drowsy: bool = False
    mq3: int = 0
    engine: bool | None = None
    link: bool | None = None

    def helmet_packet(self) -> str:
        return f"H:{int(self.helmet)},A:{int(self.alcohol)},D:{int(self.drowsy)},M:{self.mq3}"


def parse_packet(line: str) -> Telemetry | None:
    fields = {name: int(value) for name, value in FIELD_RE.findall(line.strip())}
    if not {"H", "A", "D", "M"}.issubset(fields):
        return None
    return Telemetry(
        helmet=fields["H"] == 1,
        alcohol=fields["A"] == 1,
        drowsy=fields["D"] == 1,
        mq3=max(0, min(1023, fields["M"])),
        engine=fields.get("ENGINE") == 1 if "ENGINE" in fields else None,
        link=(fields.get("LINK", fields.get("BT")) == 1) if ("LINK" in fields or "BT" in fields) else None,
    )


def engine_reason(data: Telemetry) -> str:
    if data.link is False:
        return "Helmet link offline"
    if not data.helmet:
        return "Helmet not detected"
    if data.alcohol:
        return "Alcohol detected"
    if data.drowsy:
        return "Drowsiness detected"
    return "All safety checks passed"

