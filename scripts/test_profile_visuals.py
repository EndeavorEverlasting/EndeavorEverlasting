"""Regression cases for the profile rollout verification."""
from pathlib import Path
import unittest
from unittest.mock import patch

from verify_profile_visuals import (
    ASSETS, GIF, HERO, PROFILE, REPO, ProfileCheckError, checked_images,
    gif_timing, verify_public,
)

ROOT = Path(__file__).resolve().parents[1]


class ProfileVisualTests(unittest.TestCase):
    def setUp(self):
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.expected = checked_images(self.readme)
        self.assets = {path: (ROOT / path).read_bytes() for path in ASSETS}
        self.urls = {path: f"{PROFILE}/EndeavorEverlasting/raw/main/{path}" for path in ASSETS}
        self.banner = self.image(HERO)
        self.motion = self.image(GIF)
        self.live = (f'<article class="markdown-body">{self.banner}'
                     f'<p><strong>Explore:</strong></p>{self.motion}'
                     '<a id="user-content-selected-work"></a></article>')

    def image(self, path):
        return f'<img src="/{REPO}/raw/main/{path}" width="100%" alt="{self.expected[path][1]}">'

    def test_current_checkout(self):
        frames, duration = gif_timing(self.assets[GIF])
        self.assertGreater(frames, 1)
        self.assertLess(duration, 5000)

    def test_local_readme_stale_or_commented(self):
        tag = next(line for line in self.readme.splitlines() if f'src="{GIF}"' in line)
        for replacement in ("", f"<!-- {tag} -->", f"\x60{tag}\x60", f"\x60\x60\x60html\n{tag}\n\x60\x60\x60",
                            tag.replace('width="100%"', 'width="50%"')):
            with self.subTest(replacement=replacement), self.assertRaises(ProfileCheckError):
                checked_images(self.readme.replace(tag, replacement))

    def test_public_missing_or_misplaced_gif(self):
        for html in (self.live.replace(self.motion, ""),
                     self.live.replace(self.motion, "") + self.motion,
                     self.live.replace(self.motion, "") + "<!--" + self.motion + "-->",
                     self.live.replace(self.motion, "").replace(self.banner, self.banner + self.motion)):
            with self.subTest(html=html), self.assertRaises(ProfileCheckError):
                checked_images(html, live=True)

    def test_hidden_motion(self):
        for opening, closing in (("<details>", "</details>"),
                                 ('<div hidden><div></div>', '</div>'),
                                 ('<span style="display: none">', "</span>")):
            actual = self.live.replace(self.motion, opening + self.motion + closing)
            with self.subTest(opening=opening), self.assertRaises(ProfileCheckError):
                checked_images(actual, live=True)
        visible = self.live.replace(self.motion, "<details open>" + self.motion + "</details>")
        checked_images(visible, live=True)

    def test_public_wrong_branch_or_alt(self):
        for broken in (self.motion.replace("/raw/main/", "/raw/review/"),
                       self.motion.replace(self.expected[GIF][1], ""),
                       self.motion + self.motion):
            with self.subTest(image=broken), self.assertRaises(ProfileCheckError):
                checked_images(self.live.replace(self.motion, broken), live=True)

    def test_versioned_banner_raw_url(self):
        direct = f"https://raw.githubusercontent.com/{REPO}/refs/heads/main/{HERO}?v=abcd"
        actual = self.live.replace(f"/{REPO}/raw/main/{HERO}", direct)
        self.assertEqual(checked_images(actual, live=True)[HERO][0], direct)

    def test_public_served_bytes_must_match_checkout(self):
        responses = {PROFILE: self.live.encode(), **{self.urls[p]: self.assets[p] for p in ASSETS}}
        with patch("verify_profile_visuals.read_url", side_effect=responses.__getitem__):
            verify_public(self.expected, self.assets)
            checkout_crlf = dict(self.assets, **{HERO: self.assets[HERO].replace(b"\n", b"\r\n")})
            verify_public(self.expected, checkout_crlf)
            responses[self.urls[GIF]] = b"older GIF bytes"
            with self.assertRaisesRegex(ProfileCheckError, "bytes differ"):
                verify_public(self.expected, self.assets)

    def test_bad_motion_bytes(self):
        gif = self.assets[GIF]
        start_of_blocks = 13 + 3 * (2 << (gif[10] & 7))
        loop = b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
        still = bytes.fromhex(
            "47494638396101000100800000000000ffffff21f90400020000002c00000000010001000002024401003b"
        )
        broken_lzw = still.replace(b"\x00\x02\x02\x44", b"\x00\xff\x02\x44")
        self.assertNotEqual(still, broken_lzw)
        for content, message in ((still, "must animate"),
                                 (broken_lzw, "invalid LZW"),
                                 (gif[:-1], "truncated"),
                                 (gif[:start_of_blocks] + loop + gif[start_of_blocks:], "play once"),
                                 (bytes(250_001), "250 kB budget")):
            with self.subTest(message=message), self.assertRaisesRegex(ProfileCheckError, message):
                gif_timing(content)


if __name__ == "__main__":
    unittest.main()
