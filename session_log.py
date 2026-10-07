from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import shutil
import threading


def _log_root() -> Path:
    override = os.environ.get("SAFERIDE_LOG_DIR")
    if override:
        return Path(override)
    base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    return base / "SafeRide" / "logs"


class SessionLog:
    """Append-only session log that can be exported while SafeRide is running."""

    def __init__(self, app_version: str, root: Path | None = None, started_at: datetime | None = None) -> None:
        self.started_at = started_at or datetime.now().astimezone()
        self._lock = threading.Lock()
        log_root = root or _log_root()
        log_root.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%d-%H%M%S")
        self.path = log_root / f"SafeRide-session-{stamp}-{os.getpid()}.log"
        self._handle = self.path.open("a", encoding="utf-8", buffering=1)
        self._handle.write("SafeRide session log\n")
        self._handle.write(f"Version: {app_version}\n")
        self._handle.write(f"Started: {self.started_at.isoformat(timespec='seconds')}\n")
        self._handle.write("Time\tCategory\tMessage\n")

    @staticmethod
    def _single_line(message: object) -> str:
        return str(message).replace("\r", "").replace("\n", "\\n")

    def append(self, category: str, message: object, timestamp: datetime | None = None) -> None:
        moment = timestamp or datetime.now().astimezone()
        line = f"{moment.isoformat(timespec='milliseconds')}\t{category.upper()}\t{self._single_line(message)}\n"
        with self._lock:
            if not self._handle.closed:
                self._handle.write(line)

    def export(self, destination: Path) -> Path:
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._handle.flush()
            if destination == self.path.resolve():
                return destination
            temporary = destination.with_name(f"{destination.name}.tmp")
            try:
                shutil.copyfile(self.path, temporary)
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
        return destination

    def close(self) -> None:
        with self._lock:
            if not self._handle.closed:
                self._handle.flush()
                self._handle.close()
