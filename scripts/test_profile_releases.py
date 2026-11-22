"""Exercise the real snapshot and rollback commands in an isolated Git checkout."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from profile_release import ARCHIVES, CATALOG, REPO, catalog, current_version, encode
from profile_release import git, read_archive, archive_layout, next_release_id, verify_live_checkout, ReleaseError
from verify_profile_scope import FOOTER_INVITATION, REPOSITORIES_URL, readme_copy
from verify_profile_visuals import PROFILE, ProfileCheckError, verify_archived_public

ROOT = Path(__file__).resolve().parents[1]


class ProfileReleaseTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for name in ("assets", "scripts"):
            shutil.copytree(ROOT / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(ROOT / "README.md", self.root / "README.md")
        profile = self.root / "README.md"
        # Carry a genuinely later, committed editorial edit through the restore.
        profile.write_text(profile.read_text().replace(
            "Turning everyday friction into durable systems.",
            "Turning everyday friction into durable systems. New editorial sentence."),
            encoding="utf-8")
        self.commit("Initialize rollback drill", init=True)

    def commit(self, message, init=False):
        if init:
            git(self.root, "init", "--quiet")
        git(self.root, "add", ".")
        git(self.root, "-c", "user.name=Regression", "-c", "user.email=regression@example.invalid",
            "commit", "-qm", message)
        return git(self.root, "rev-parse", "HEAD").decode().strip()

    def command(self, *args):
        return subprocess.run([sys.executable, "scripts/profile_release.py", *args],
                              cwd=self.root, capture_output=True, text=True)

    def test_full_verification_rejects_dirty_inputs_and_uses_the_base_guard(self):
        base = git(self.root, "rev-parse", "HEAD").decode().strip()
        extra = self.root / "unrelated.txt"
        extra.write_text("Outside the release.\n")
        result = self.command("verify", "--base", base)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("needs a clean checkout", result.stderr)

        guard = self.root / "scripts/verify_profile_scope.py"
        guard.write_text(guard.read_text().replace('    main()\n', '    pass\n'))
        self.commit("Propose a weaker scope guard and unrelated file")
        result = self.command("verify", "--base", base)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unrelated paths in this profile change: unrelated.txt", result.stderr)
        self.assertNotIn("PASS profile release checks", result.stdout)

    def test_every_version_restores_and_returns_to_original(self):
        data = catalog(self.root)
        original = data["active"]["id"]
        versions = [name for name in data["versions"] if name != original] + [original]
        readme = self.root / "README.md"
        prose = readme_copy(readme.read_text(encoding="utf-8"))
        for version in versions:
            with self.subTest(version=version):
                before = readme.read_bytes()
                preview = self.command("restore", version)
                self.assertEqual(preview.returncode, 0, preview.stderr)
                self.assertIn(f"/{version}/", preview.stdout)
                self.assertEqual(readme.read_bytes(), before)
                applied = self.command("restore", version, "--apply")
                self.assertEqual(applied.returncode, 0, applied.stderr)
                self.assertEqual(current_version(self.root)[0]["id"], version)
                self.assertEqual(readme_copy(readme.read_text(encoding="utf-8")), prose)
                self.assertEqual(set(git(self.root, "diff", "--name-only").decode().splitlines()),
                                 {"README.md", CATALOG})
                self.commit(f"Select {version}")

    def test_invitation_survives_rollbacks_with_and_without_a_footer(self):
        readme = self.root / "README.md"
        version = catalog(self.root)["active"]["id"]
        invitation = (f'<p><strong>Explore projects.</strong> Start with the pins below. '
                      f'<a href="{REPOSITORIES_URL}">Browse all repositories</a></p>')
        original = FOOTER_INVITATION.sub("", readme.read_text()).rstrip()
        readme.write_text(original + "\n\n" + invitation + "\n")
        prose = readme_copy(readme.read_text())
        self.commit("Add the repository invitation")
        for target in ("v02", "v08", version):
            with self.subTest(version=target):
                result = self.command("restore", target, "--apply")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(current_version(self.root)[0]["id"], target)
                text = readme.read_text()
                self.assertEqual(readme_copy(text), prose)
                self.assertTrue(text.endswith(invitation + "\n"))
                if target != "v02":
                    self.assertTrue(text.split(invitation)[0].rstrip().endswith("</picture>"))
                self.commit(f"Select {target}")

    def test_dirty_and_corrupt_inputs_fail_without_overwriting(self):
        readme = self.root / "README.md"
        edited = readme.read_bytes() + b"\nPending personal edit\n"
        readme.write_bytes(edited)
        failed = self.command("restore", "v02", "--apply")
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("pending README", failed.stderr)
        self.assertEqual(readme.read_bytes(), edited)
        snapshot = self.root / ARCHIVES / "v02" / "assets/first-stitch.gif"
        snapshot.write_bytes(b"corrupt")
        self.assertIn("checksum mismatch", self.command("check").stderr)
        self.assertEqual(readme.read_bytes(), edited)

    def test_capture_creates_the_next_version_and_keeps_old_archives(self):
        data = catalog(self.root)
        current = max(data["versions"], key=lambda version: int(version[1:]))
        next_version = f"v{int(current[1:]) + 1:02d}"
        # Modern capture is based on the reviewed working art, even if this PR
        # starts at an older selected version.
        source = self.root / ARCHIVES / current / "README.md"
        shutil.copyfile(source, self.root / "README.md")
        data["active"] = {"id": current, "archive": False}
        (self.root / CATALOG).write_bytes(encode(data))
        base = self.commit("Select the reviewed working art for capture")
        result = self.command("capture", next_version, "--title", "Future profile expression")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(current_version(self.root, base)[0], {"id": next_version, "archive": False})
        self.assertEqual((self.root / ARCHIVES / next_version / "README.md").read_bytes(),
                         source.read_bytes())
        self.assertIn("next version ID", self.command("capture", next_version, "--title", "Overwrite").stderr)

        served = json.loads(self.command("status", "--compare", next_version, "--json").stdout)["comparison"]
        self.assertEqual(served["changed_scenes"], {})
        self.assertEqual(served["media_url_scenes"], ["top", "after_intro", "bottom"])

        self.commit("Capture the reviewed working art")
        applied = self.command("restore", next_version, "--apply")
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(current_version(self.root, base)[0], {"id": next_version, "archive": True})
        self.assertIn(f"{ARCHIVES}/{next_version}/assets/", (self.root / "README.md").read_text())
        (self.root / "assets/stitch-pulse.gif").write_bytes(b"unreviewed")
        self.assertIn("Capture the changed artwork", self.command("check", "--base", base).stderr)

    def test_status_tracks_copy_scene_changes_and_default_artwork_independently(self):
        registry = catalog(self.root)
        version = registry["active"]["id"]
        base = git(self.root, "rev-parse", "HEAD").decode().strip()
        git(self.root, "remote", "add", "origin", f"{REPO}.git")
        git(self.root, "update-ref", "refs/remotes/origin/main", base)
        git(self.root, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        readme = self.root / "README.md"
        readme.write_text(readme.read_text().replace("New editorial sentence.", "New editorial revision."))
        copy = self.commit("Edit only the invitation context")
        report = json.loads(self.command("status", "--compare", "v02", "--json").stdout)
        self.assertEqual(report["artwork"]["registered_commit"], base)
        self.assertEqual(report["next_artwork_version"], next_release_id(registry["versions"]))
        self.assertEqual(report["editorial"]["last_commit"], copy)
        self.assertEqual(report["last_fetched_default"]["commit"], base)
        self.assertEqual(report["last_fetched_default"]["artwork"]["id"], version)
        self.assertIn(f"/tree/{base}/", report["artwork"]["archive_url"])
        git(self.root, "remote", "set-url", "origin", "https://github.com/example/profile-fork.git")
        fork = json.loads(self.command("status", "--json").stdout)
        self.assertFalse(fork["last_fetched_default"]["canonical_origin"])
        self.assertIsNone(fork["artwork"]["archive_url"])
        self.assertEqual(report["comparison"]["changed_scenes"]["bottom"]["removed"],
                         ["assets/stitch-pulse.gif", "assets/stitch-pulse.png"])
        self.assertIn("restore v02", report["comparison"]["preview_command"])
        self.assertIsNone(report["comparison"]["restore_blocker"])
        self.assertEqual(git(self.root, "status", "--porcelain"), b"")

        self.assertEqual(self.command("restore", "v02", "--apply").returncode, 0)
        pending = json.loads(self.command("status", "--json").stdout)
        self.assertTrue(pending["checkout"]["profile_changes_pending"])
        self.assertEqual(pending["artwork"]["id"], "v02")
        self.assertEqual(pending["last_fetched_default"]["artwork"]["id"], version)
        self.commit("Restore artwork only")
        restored = json.loads(self.command("status", "--json").stdout)
        self.assertFalse(restored["history"][-1]["editorial_changed"])
        self.assertTrue(restored["history"][-1]["artwork_selection_changed"])
        self.assertEqual(restored["editorial"]["last_commit"], copy)

        readme.write_text(readme.read_text().replace("I care about what happens", "How I think about what happens"))
        blocked = json.loads(self.command("status", "--compare", version, "--json").stdout)
        self.assertIn("Restore needs exactly one section", blocked["comparison"]["restore_blocker"])

    def test_shallow_status_does_not_invent_registration_or_editorial_provenance(self):
        with TemporaryDirectory() as directory:
            shallow = Path(directory)
            git(self.root, "clone", "--depth", "1", self.root.as_uri(), str(shallow))
            result = subprocess.run([sys.executable, "scripts/profile_release.py", "status", "--json"],
                                    cwd=shallow, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["history_is_shallow"])
            self.assertIsNone(report["artwork"]["registered_commit"])
            self.assertIsNone(report["editorial"]["last_commit"])
            self.assertEqual(report["history"], [])

    def test_live_status_rejects_pending_or_stale_checkout_before_render(self):
        with patch("profile_release.subprocess.run") as dispatch:
            with self.assertRaisesRegex(ReleaseError, "clean profile checkout"):
                verify_live_checkout(self.root, "a"*40, pending=True)
            dispatch.assert_not_called()
            dispatch.return_value = subprocess.CompletedProcess([], 0, "b"*40 + "\tHEAD\n", "")
            with self.assertRaisesRegex(ReleaseError, "current default HEAD"):
                verify_live_checkout(self.root, "a"*40, pending=False)
            self.assertEqual(dispatch.call_count, 1)
            dispatch.side_effect = [subprocess.CompletedProcess([], 0, f"{'a'*40}\tHEAD\n", ""),
                                    subprocess.CompletedProcess([], 0, "", ""),
                                    subprocess.CompletedProcess([], 0, f"{'b'*40}\tHEAD\n", "")]
            with self.assertRaisesRegex(ReleaseError, "changed during verification"):
                verify_live_checkout(self.root, "a"*40, pending=False)

        (self.root / "scripts/verify_profile_visuals.py").write_text(f"PROFILE = {PROFILE!r}\n")
        result = self.command("status", "--live")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("clean profile checkout", result.stderr)

    def test_published_catalog_rejects_skipping_the_next_version_id(self):
        base = git(self.root, "rev-parse", "HEAD").decode().strip()
        data = catalog(self.root)
        current = data["active"]["id"]
        next_id = next_release_id(data["versions"])
        skipped = f"v{int(next_id[1:]) + 1:02d}"
        shutil.copytree(self.root / ARCHIVES / current, self.root / ARCHIVES / skipped)
        data["versions"][skipped] = data["versions"][current]
        data["active"] = {"id": skipped, "archive": True}
        (self.root / CATALOG).write_bytes(encode(data))
        self.assertIn(f"Use the next version ID: {next_id}", self.command("check", "--base", base).stderr)

    def test_published_catalog_is_append_only(self):
        base = git(self.root, "rev-parse", "HEAD").decode().strip()
        data = catalog(self.root)
        data["versions"]["v01"]["title"] = "Overwrite a permanent name"
        (self.root / CATALOG).write_bytes(encode(data))
        self.assertIn("immutable", self.command("check", "--base", base).stderr)

    def test_live_legacy_art_rejects_move_and_wrong_bytes(self):
        entry = catalog(self.root)["versions"]["v02"]
        blocks, files = read_archive(self.root, "v02", entry)
        blocks = archive_layout(blocks, "v02")
        header, = blocks["top"]
        bridge, = blocks["before_work"]
        repo_path = REPO.removeprefix("https://github.com")
        prefix = f"{repo_path}/raw/main/"
        profile = (f'<article class="markdown-body">{header}<p>Intro</p><p>Explore:</p>'
                   f'{bridge}<h3>Selected work</h3><p>End</p></article>').replace(
                       'src="assets/', f'src="{prefix}assets/')
        urls = {PROFILE: profile.encode(), **{
            f"https://github.com{prefix}{ARCHIVES}/v02/{path}": data
            for path, data in files.items() if path != "README.md"
        }}
        with patch("verify_profile_visuals.read_url", side_effect=urls.__getitem__):
            verify_archived_public(blocks, "v02", files)
            invitation = (f'<p><strong>Explore projects.</strong> Start with the pins below. '
                          f'<a href="{REPOSITORIES_URL}">Browse all repositories</a></p>')
            with self.assertRaisesRegex(ProfileCheckError, "invitation"):
                verify_archived_public(blocks, "v02", files, invitation)
            urls[PROFILE] = profile.replace("</article>", invitation + "</article>").encode()
            verify_archived_public(blocks, "v02", files, invitation)
            urls[PROFILE] = profile.replace("<h3>Selected", "<p>Moved text</p><h3>Selected").encode()
            with self.assertRaisesRegex(ProfileCheckError, "text break"):
                verify_archived_public(blocks, "v02", files)
            urls[PROFILE] = profile.encode()
            urls[f"https://github.com{prefix}{ARCHIVES}/v02/assets/first-stitch.gif"] = b"stale"
            with self.assertRaisesRegex(ProfileCheckError, "differs"):
                verify_archived_public(blocks, "v02", files)
