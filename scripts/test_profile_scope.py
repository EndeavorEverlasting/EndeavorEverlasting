"""Regression cases for the pre-commit and CI profile scope gate."""
import unittest

from verify_profile_scope import LEGACY_NEXUS, NEXUS_ALT, REPOSITORIES_URL
from verify_profile_scope import ProfileScopeError, verify_changes


class ProfileScopeTests(unittest.TestCase):
    def test_allows_artwork_and_its_readme_slots(self):
        base = "# About\n\nProfile paragraph.\n"
        changed = ('''<p align="center">
  <img src="assets/hero.svg" width="100%" alt="Banner" />
</p>

''' + base + '''
<picture>
  <source media="(prefers-reduced-motion: reduce)" srcset="assets/stitch-pulse.png" />
  <img src="assets/stitch-pulse.gif" width="100%" alt="Pulse" />
</picture>
''')
        verify_changes({"README.md", "assets/stitch-pulse.gif"}, base, changed)
        verify_changes({"README.md"}, base, base.replace("paragraph", "introduction"))

    def test_rejects_unrelated_edits(self):
        for paths in ({"src/company_data.json"}, {"assets/stitch-pulse.gif", "assets/random.gif"}):
            with self.subTest(paths=paths), self.assertRaisesRegex(ProfileScopeError, "Unrelated paths"):
                verify_changes(paths)
        with self.assertRaisesRegex(ProfileScopeError, "separate changes"):
            verify_changes({"assets/stitch-pulse.gif", "AGENTS.md"})
        with self.assertRaisesRegex(ProfileScopeError, "approved media"):
            verify_changes({"README.md", "assets/stitch-pulse.gif"}, "# About", "# Changed heading")

    def test_protects_the_readme(self):
        with self.assertRaisesRegex(ProfileScopeError, "remain present"):
            verify_changes({"README.md"}, "# About", "")

    def test_only_the_exact_legacy_invitation_can_move_into_reviewed_art(self):
        before = f"# About\n\nUnrelated copy.\n\n{LEGACY_NEXUS}\n"
        block = f'''<a href="{REPOSITORIES_URL}">
<picture>
  <source media="(prefers-reduced-motion: reduce)" srcset="assets/stitch-pulse.png" />
  <img src="assets/stitch-pulse.gif" width="100%" alt="{NEXUS_ALT}" />
</picture>
</a>
'''
        after = "# About\n\nUnrelated copy.\n\n" + block
        paths = {"README.md", "assets/stitch-pulse.gif"}
        verify_changes(paths, before, after)
        for wrong in (after.replace(REPOSITORIES_URL, "https://example.com"),
                      after.replace(NEXUS_ALT, "Explore."),
                      after.replace("Unrelated copy.", "Edited copy."),
                      after.replace("Unrelated copy.\n\n" + block, block + "\nUnrelated copy.\n")):
            with self.subTest(wrong=wrong), self.assertRaisesRegex(ProfileScopeError, "approved media"):
                verify_changes(paths, before, wrong)
