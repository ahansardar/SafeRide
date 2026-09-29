from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from updater import GitHubUpdater, ReleaseAsset, ReleaseInfo, UpdateError, is_newer_version, version_tuple


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class FakeOpener:
    def __init__(self, responses: dict[str, bytes]):
        self.responses = responses
        self.requests = []

    def __call__(self, request, timeout=0):
        self.requests.append((request, timeout))
        return FakeResponse(self.responses[request.full_url])


class UpdaterTests(unittest.TestCase):
    def test_version_comparison(self):
        self.assertEqual(version_tuple("v3.2.0"), (3, 2, 0))
        self.assertTrue(is_newer_version("3.2.1", "3.2.0"))
        self.assertFalse(is_newer_version("v3.2.0", "3.2.0"))
        with self.assertRaises(UpdateError):
            version_tuple("release-next")

    def test_public_release_discovery_and_verified_download(self):
        installer = b"real installer bytes"
        checksum = f"{hashlib.sha256(installer).hexdigest()}  SafeRide-Setup-x64.exe\n".encode("ascii")
        release_payload = {
            "tag_name": "v3.3.0",
            "body": "Update test",
            "assets": [
                {"name": "SafeRide-Setup-x64.exe", "url": "https://api.test/installer", "size": len(installer)},
                {"name": "SafeRide-Setup-x64.sha256.txt", "url": "https://api.test/checksum", "size": len(checksum)},
            ],
        }
        api_url = "https://api.github.com/repos/ahansardar/SafeRide/releases/latest"
        opener = FakeOpener({
            api_url: json.dumps(release_payload).encode("utf-8"),
            "https://api.test/installer": installer,
            "https://api.test/checksum": checksum,
        })
        with tempfile.TemporaryDirectory() as folder:
            updater = GitHubUpdater(opener=opener, update_dir=Path(folder))
            release = updater.latest_release()
            path = updater.download_update(release)
            self.assertEqual(path.read_bytes(), installer)
        for request, timeout in opener.requests:
            self.assertIsNone(request.get_header("Authorization"))
            self.assertEqual(timeout, 30)

    def test_checksum_mismatch_never_promotes_installer(self):
        installer = ReleaseAsset("SafeRide-Setup-x64.exe", "https://api.test/installer", 3)
        checksum_bytes = ("0" * 64 + "  SafeRide-Setup-x64.exe\n").encode("ascii")
        checksum = ReleaseAsset("SafeRide-Setup-x64.sha256.txt", "https://api.test/checksum", len(checksum_bytes))
        release = ReleaseInfo("9.0.0", "v9.0.0", "", installer, checksum)
        opener = FakeOpener({"https://api.test/installer": b"bad", "https://api.test/checksum": checksum_bytes})
        with tempfile.TemporaryDirectory() as folder:
            updater = GitHubUpdater(opener=opener, update_dir=Path(folder))
            with self.assertRaisesRegex(UpdateError, "SHA-256"):
                updater.download_update(release)
            self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
