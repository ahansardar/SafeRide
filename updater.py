from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import BinaryIO, Callable
import urllib.error
import urllib.request

from version import (
    APP_VERSION,
    GITHUB_OWNER,
    GITHUB_REPOSITORY,
    INSTALLER_ASSET,
    INSTALLER_CHECKSUM_ASSET,
    PORTABLE_ASSET,
    PORTABLE_CHECKSUM_ASSET,
)


API_VERSION = "2022-11-28"
USER_AGENT = f"SafeRide/{APP_VERSION}"
_VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    api_url: str
    size: int


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag: str
    notes: str
    package: ReleaseAsset | None
    checksum: ReleaseAsset | None
    package_kind: str


@dataclass(frozen=True)
class PortableUpdatePlan:
    script: Path
    staged_executable: Path
    target_executable: Path
    command: tuple[str, ...]


def version_tuple(value: str) -> tuple[int, int, int]:
    match = _VERSION_PATTERN.fullmatch(value.strip())
    if not match:
        raise UpdateError(f"Unsupported release version: {value}")
    return tuple(int(part) for part in match.groups())


def is_newer_version(candidate: str, current: str = APP_VERSION) -> bool:
    return version_tuple(candidate) > version_tuple(current)


def is_portable_runtime() -> bool:
    """Return True only for a PyInstaller one-file executable."""
    if not getattr(sys, "frozen", False) or not hasattr(sys, "_MEIPASS"):
        return False
    executable_dir = Path(sys.executable).resolve().parent
    bundle_dir = Path(str(sys._MEIPASS)).resolve()
    return executable_dir != bundle_dir


def _state_root() -> Path:
    override = os.environ.get("SAFERIDE_UPDATE_STATE_DIR")
    if override:
        return Path(override)
    base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    return base / "SafeRide"


class GitHubUpdater:
    def __init__(
        self,
        opener: Callable[..., BinaryIO] = urllib.request.urlopen,
        update_dir: Path | None = None,
        portable_mode: bool | None = None,
        current_version: str = APP_VERSION,
    ) -> None:
        self._opener = opener
        self._update_dir = update_dir or (_state_root() / "updates")
        self.portable_mode = is_portable_runtime() if portable_mode is None else portable_mode
        self.current_version = current_version

    @property
    def asset_names(self) -> tuple[str, str]:
        if self.portable_mode:
            return PORTABLE_ASSET, PORTABLE_CHECKSUM_ASSET
        return INSTALLER_ASSET, INSTALLER_CHECKSUM_ASSET

    @staticmethod
    def _headers(accept: str) -> dict[str, str]:
        return {
            "Accept": accept,
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": USER_AGENT,
        }

    def _open(self, request: urllib.request.Request):
        try:
            return self._opener(request, timeout=30)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise UpdateError("No public SafeRide release is available yet.") from exc
            raise UpdateError(f"GitHub update request failed with HTTP {exc.code}.") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise UpdateError(f"Could not reach GitHub: {exc}") from exc

    def latest_release(self) -> ReleaseInfo:
        url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPOSITORY}/releases/latest"
        request = urllib.request.Request(url, headers=self._headers("application/vnd.github+json"))
        with self._open(request) as response:
            try:
                payload = json.loads(response.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise UpdateError("GitHub returned an invalid release response.") from exc

        tag = str(payload.get("tag_name", ""))
        version_tuple(tag)
        assets = {str(item.get("name")): item for item in payload.get("assets", [])}
        package_name, checksum_name = self.asset_names
        package_available = package_name in assets and checksum_name in assets
        if not package_available and is_newer_version(tag, self.current_version):
            kind = "portable EXE" if self.portable_mode else "installer"
            raise UpdateError(f"The latest release is missing the {kind} or its checksum.")

        def release_asset(name: str) -> ReleaseAsset:
            item = assets[name]
            return ReleaseAsset(name, str(item["url"]), int(item["size"]))

        return ReleaseInfo(
            version=tag.removeprefix("v"),
            tag=tag,
            notes=str(payload.get("body") or "No release notes were provided."),
            package=release_asset(package_name) if package_available else None,
            checksum=release_asset(checksum_name) if package_available else None,
            package_kind="portable" if self.portable_mode else "installer",
        )

    def _download_bytes(self, asset: ReleaseAsset, maximum: int) -> bytes:
        request = urllib.request.Request(
            asset.api_url, headers=self._headers("application/octet-stream")
        )
        with self._open(request) as response:
            data = response.read(maximum + 1)
        if len(data) > maximum:
            raise UpdateError(f"Release asset {asset.name} is unexpectedly large.")
        if asset.size and len(data) != asset.size:
            raise UpdateError(f"Release asset {asset.name} was truncated.")
        return data

    def download_update(
        self,
        release: ReleaseInfo,
        progress: Callable[[int, int], None] | None = None,
    ) -> Path:
        if release.package is None or release.checksum is None:
            raise UpdateError("This release does not contain an update package for the running app.")
        checksum_text = self._download_bytes(release.checksum, 4096).decode("ascii", errors="strict")
        expected = checksum_text.strip().split()[0].lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise UpdateError("The release checksum file is invalid.")

        self._update_dir.mkdir(parents=True, exist_ok=True)
        package_path = Path(release.package.name)
        destination = self._update_dir / f"{package_path.stem}-v{release.version}{package_path.suffix}"
        temporary = destination.with_suffix(".part")
        request = urllib.request.Request(
            release.package.api_url, headers=self._headers("application/octet-stream")
        )
        digest = hashlib.sha256()
        received = 0
        try:
            with self._open(request) as response, temporary.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
                    if progress:
                        progress(received, release.package.size)
            if release.package.size and received != release.package.size:
                raise UpdateError("The downloaded update is incomplete.")
            if digest.hexdigest().lower() != expected:
                raise UpdateError("The downloaded update failed SHA-256 verification.")
            temporary.replace(destination)
            return destination
        except (OSError, UnicodeError) as exc:
            raise UpdateError(f"Could not save the update: {exc}") from exc
        finally:
            temporary.unlink(missing_ok=True)

    def prepare_portable_update(
        self,
        downloaded_executable: Path,
        target_executable: Path | None = None,
        process_id: int | None = None,
    ) -> PortableUpdatePlan:
        if not self.portable_mode:
            raise UpdateError("Portable replacement is unavailable in the installed build.")
        source = downloaded_executable.resolve()
        target = (target_executable or Path(sys.executable)).resolve()
        if not source.is_file():
            raise UpdateError("The verified portable update file is missing.")
        if target.suffix.lower() != ".exe":
            raise UpdateError("The running portable target is not a Windows executable.")

        staged = target.with_name(f"{target.name}.next")
        staging_temp = target.with_name(f"{target.name}.next.tmp")
        script = self._update_dir / "apply-portable-update.ps1"
        pid = process_id or os.getpid()
        powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if not powershell.exists():
            found = shutil.which("powershell.exe")
            if not found:
                raise UpdateError("Windows PowerShell is required to replace the portable EXE.")
            powershell = Path(found)

        script_text = r'''param(
    [Parameter(Mandatory = $true)][int]$ProcessId,
    [Parameter(Mandatory = $true)][string]$Staged,
    [Parameter(Mandatory = $true)][string]$Target
)
$ErrorActionPreference = "Stop"
$backup = "$Target.previous"
try {
    try { Wait-Process -Id $ProcessId -Timeout 90 -ErrorAction SilentlyContinue } catch {}
    while (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        Start-Sleep -Milliseconds 250
    }
    if (-not (Test-Path -LiteralPath $Staged)) { throw "The staged SafeRide update is missing." }
    if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force }
    if (Test-Path -LiteralPath $Target) { Move-Item -LiteralPath $Target -Destination $backup -Force }
    try {
        Move-Item -LiteralPath $Staged -Destination $Target -Force
        Start-Process -FilePath $Target -WorkingDirectory (Split-Path -Parent $Target)
    } catch {
        if (Test-Path -LiteralPath $Target) { Remove-Item -LiteralPath $Target -Force }
        if (Test-Path -LiteralPath $backup) { Move-Item -LiteralPath $backup -Destination $Target -Force }
        throw
    }
    if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue }
} finally {
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
}
'''
        try:
            self._update_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, staging_temp)
            os.replace(staging_temp, staged)
            script.write_text(script_text, encoding="utf-8-sig")
        except OSError as exc:
            staging_temp.unlink(missing_ok=True)
            staged.unlink(missing_ok=True)
            raise UpdateError(f"Could not stage the portable update beside SafeRide: {exc}") from exc

        command = (
            str(powershell),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            str(script),
            "-ProcessId",
            str(pid),
            "-Staged",
            str(staged),
            "-Target",
            str(target),
        )
        return PortableUpdatePlan(script, staged, target, command)

    @staticmethod
    def launch_portable_update(plan: PortableUpdatePlan) -> None:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            subprocess.Popen(
                list(plan.command),
                cwd=str(plan.target_executable.parent),
                creationflags=creationflags,
                close_fds=True,
            )
        except OSError as exc:
            plan.staged_executable.unlink(missing_ok=True)
            raise UpdateError(f"Could not start the portable updater: {exc}") from exc
