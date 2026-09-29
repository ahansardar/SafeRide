from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from typing import BinaryIO, Callable
import urllib.error
import urllib.request

from version import APP_VERSION, CHECKSUM_ASSET, GITHUB_OWNER, GITHUB_REPOSITORY, INSTALLER_ASSET


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
    installer: ReleaseAsset
    checksum: ReleaseAsset


def version_tuple(value: str) -> tuple[int, int, int]:
    match = _VERSION_PATTERN.fullmatch(value.strip())
    if not match:
        raise UpdateError(f"Unsupported release version: {value}")
    return tuple(int(part) for part in match.groups())


def is_newer_version(candidate: str, current: str = APP_VERSION) -> bool:
    return version_tuple(candidate) > version_tuple(current)


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
    ) -> None:
        self._opener = opener
        self._update_dir = update_dir or (_state_root() / "updates")

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
        if INSTALLER_ASSET not in assets or CHECKSUM_ASSET not in assets:
            raise UpdateError("The latest release is missing the installer or checksum asset.")

        def release_asset(name: str) -> ReleaseAsset:
            item = assets[name]
            return ReleaseAsset(name, str(item["url"]), int(item["size"]))

        return ReleaseInfo(
            version=tag.removeprefix("v"),
            tag=tag,
            notes=str(payload.get("body") or "No release notes were provided."),
            installer=release_asset(INSTALLER_ASSET),
            checksum=release_asset(CHECKSUM_ASSET),
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
        checksum_text = self._download_bytes(release.checksum, 4096).decode("ascii", errors="strict")
        expected = checksum_text.strip().split()[0].lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise UpdateError("The release checksum file is invalid.")

        self._update_dir.mkdir(parents=True, exist_ok=True)
        destination = self._update_dir / f"SafeRide-Setup-x64-v{release.version}.exe"
        temporary = destination.with_suffix(".part")
        request = urllib.request.Request(
            release.installer.api_url, headers=self._headers("application/octet-stream")
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
                        progress(received, release.installer.size)
            if release.installer.size and received != release.installer.size:
                raise UpdateError("The downloaded installer is incomplete.")
            if digest.hexdigest().lower() != expected:
                raise UpdateError("The downloaded installer failed SHA-256 verification.")
            temporary.replace(destination)
            return destination
        except (OSError, UnicodeError) as exc:
            raise UpdateError(f"Could not save the update: {exc}") from exc
        finally:
            temporary.unlink(missing_ok=True)
