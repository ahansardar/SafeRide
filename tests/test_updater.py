from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
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

    def test_public_portable_release_discovery_and_verified_download(self):
        package = b"MZ real portable bytes"
        checksum = f"{hashlib.sha256(package).hexdigest()}  SafeRide-Portable-x64.exe\n".encode("ascii")
        release_payload = {
            "tag_name": "v3.4.0",
            "body": "Update test",
            "assets": [
                {"name": "SafeRide-Portable-x64.exe", "url": "https://api.test/package", "size": len(package)},
                {"name": "SafeRide-Portable-x64.sha256.txt", "url": "https://api.test/checksum", "size": len(checksum)},
            ],
        }
        api_url = "https://api.github.com/repos/ahansardar/SafeRide/releases/latest"
        opener = FakeOpener({
            api_url: json.dumps(release_payload).encode("utf-8"),
            "https://api.test/package": package,
            "https://api.test/checksum": checksum,
        })
        with tempfile.TemporaryDirectory() as folder:
            updater = GitHubUpdater(opener=opener, update_dir=Path(folder), portable_mode=True)
            release = updater.latest_release()
            path = updater.download_update(release)
            self.assertEqual(path.name, "SafeRide-Portable-x64-v3.4.0.exe")
            self.assertEqual(path.read_bytes(), package)
        for request, timeout in opener.requests:
            self.assertIsNone(request.get_header("Authorization"))
            self.assertEqual(timeout, 30)

    def test_current_legacy_release_does_not_break_portable_check(self):
        payload = {
            "tag_name": "v3.2.0",
            "assets": [
                {"name": "SafeRide-Setup-x64.exe", "url": "https://api.test/installer", "size": 1},
                {"name": "SafeRide-Setup-x64.sha256.txt", "url": "https://api.test/checksum", "size": 1},
            ],
        }
        api_url = "https://api.github.com/repos/ahansardar/SafeRide/releases/latest"
        updater = GitHubUpdater(
            opener=FakeOpener({api_url: json.dumps(payload).encode("utf-8")}),
            portable_mode=True,
            current_version="3.3.0",
        )
        release = updater.latest_release()
        self.assertIsNone(release.package)
        self.assertIsNone(release.checksum)

    def test_new_release_without_portable_asset_is_rejected(self):
        payload = {"tag_name": "v3.4.0", "assets": []}
        api_url = "https://api.github.com/repos/ahansardar/SafeRide/releases/latest"
        updater = GitHubUpdater(
            opener=FakeOpener({api_url: json.dumps(payload).encode("utf-8")}),
            portable_mode=True,
            current_version="3.3.0",
        )
        with self.assertRaisesRegex(UpdateError, "portable EXE"):
            updater.latest_release()

    def test_checksum_mismatch_never_promotes_installer(self):
        installer = ReleaseAsset("SafeRide-Setup-x64.exe", "https://api.test/installer", 3)
        checksum_bytes = ("0" * 64 + "  SafeRide-Setup-x64.exe\n").encode("ascii")
        checksum = ReleaseAsset("SafeRide-Setup-x64.sha256.txt", "https://api.test/checksum", len(checksum_bytes))
        release = ReleaseInfo("9.0.0", "v9.0.0", "", installer, checksum, "installer")
        opener = FakeOpener({"https://api.test/installer": b"bad", "https://api.test/checksum": checksum_bytes})
        with tempfile.TemporaryDirectory() as folder:
            updater = GitHubUpdater(opener=opener, update_dir=Path(folder), portable_mode=False)
            with self.assertRaisesRegex(UpdateError, "SHA-256"):
                updater.download_update(release)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_portable_update_plan_stages_next_to_running_exe(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "Safe Ride.exe"
            downloaded = root / "downloaded.exe"
            target.write_bytes(b"MZ old")
            downloaded.write_bytes(b"MZ new")
            updater = GitHubUpdater(update_dir=root / "updates", portable_mode=True)
            plan = updater.prepare_portable_update(downloaded, target, process_id=12345)
            self.assertEqual(plan.staged_executable, root / "Safe Ride.exe.next")
            self.assertEqual(plan.staged_executable.read_bytes(), b"MZ new")
            self.assertEqual(plan.target_executable, target.resolve())
            self.assertIn(str(target.resolve()), plan.command)
            self.assertIn("12345", plan.command)
            self.assertIn("Start-Process -FilePath $Target", plan.script.read_text(encoding="utf-8-sig"))

    @unittest.skipUnless(os.name == "nt", "Portable replacement uses Windows PowerShell")
    def test_portable_update_helper_replaces_target_and_cleans_up(self):
        system32 = Path(os.environ["SystemRoot"]) / "System32"
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "SafeRide Test.exe"
            downloaded = root / "downloaded.exe"
            shutil.copy2(system32 / "where.exe", target)
            shutil.copy2(system32 / "whoami.exe", downloaded)
            expected = hashlib.sha256(downloaded.read_bytes()).hexdigest()

            updater = GitHubUpdater(update_dir=root / "updates", portable_mode=True)
            plan = updater.prepare_portable_update(downloaded, target, process_id=999999)
            completed = subprocess.run(
                list(plan.command),
                cwd=root,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=30,
                check=False,
            )

            self.assertEqual(completed.returncode, 0)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), expected)
            self.assertFalse(target.with_name(f"{target.name}.previous").exists())
            self.assertFalse(plan.staged_executable.exists())
            self.assertFalse(plan.script.exists())
            for _ in range(50):
                try:
                    target.unlink()
                    break
                except PermissionError:
                    time.sleep(0.1)
            else:
                self.fail("The relaunched test executable did not exit in time")


if __name__ == "__main__":
    unittest.main()
