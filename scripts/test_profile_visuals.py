"""Regression cases for the profile rollout verification."""
from pathlib import Path
import unittest
from unittest.mock import patch

from render_profile_motion import (
    CONTINUATION as CONTINUATION_CURVES, OPENING as OPENING_CURVES, verify_thread_direction,
)
from verify_profile_visuals import (
    ASSETS, CONTINUATION, MILESTONES, OPENING, PROFILE, REDUCED_MOTION, REPO,
    ProfileCheckError, check_artwork, checked_images, gif_timing, verify_public,
)

ROOT = Path(__file__).resolve().parents[1]


class ProfileVisualTests(unittest.TestCase):
    def setUp(self):
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.expected = checked_images(self.readme)
        self.assets = {path: (ROOT / path).read_bytes() for path in ASSETS}
        self.urls = {path: f"/{REPO}/raw/main/{path}" for path in ASSETS}
        self.opening = self.picture(OPENING)
        self.continuation = self.picture(CONTINUATION)
        headline, first, second, work = MILESTONES
        self.live = (
            f'<article class="markdown-body">{self.opening}<h1>{headline}</h1>'
            f'<p>{first}</p>{self.continuation}<p>{second}</p><h3>{work}</h3></article>'
        )

    def picture(self, path):
        still = path.removesuffix(".gif") + ".png"
        return (
            f'<picture><source srcset="{self.urls[still]}" media="{REDUCED_MOTION}">'
            f'<img src="{self.urls[path]}" width="100%" alt="{self.expected[path][1]}"></picture>'
        )

    def test_current_checkout(self):
        check_artwork(self.assets)

    def test_local_readme_missing_inert_or_narrow_gif(self):
        tag = next(line for line in self.readme.splitlines() if f'src="{CONTINUATION}"' in line)
        for replacement in ("", f"<!-- {tag} -->", f"`{tag}`", f"```html\n{tag}\n```",
                            tag.replace('width="100%"', 'width="50%"')):
            with self.subTest(replacement=replacement), self.assertRaises(ProfileCheckError):
                checked_images(self.readme.replace(tag, replacement))

    def test_public_motion_must_break_up_copy(self):
        without_continuation = self.live.replace(self.continuation, "")
        bad_placement = (
            without_continuation,
            without_continuation + self.continuation,
            without_continuation.replace(self.opening, self.opening + self.continuation),
            self.live.replace(self.opening, "").replace("</h1>", "</h1>" + self.opening),
        )
        for html in bad_placement:
            with self.subTest(html=html), self.assertRaises(ProfileCheckError):
                checked_images(html, live=True)

    def test_hidden_motion(self):
        for opening, closing in (("<details>", "</details>"),
                                 ('<div hidden><div></div>', '</div>'),
                                 ('<span style="display: none">', "</span>")):
            actual = self.live.replace(self.continuation, opening + self.continuation + closing)
            with self.subTest(opening=opening), self.assertRaises(ProfileCheckError):
                checked_images(actual, live=True)
        visible = self.live.replace(self.continuation, "<details open>" + self.continuation + "</details>")
        checked_images(visible, live=True)

    def test_public_wrong_branch_or_alt(self):
        for broken in (self.continuation.replace("/raw/main/", "/raw/review/"),
                       self.continuation.replace(self.expected[CONTINUATION][1], ""),
                       self.continuation + self.continuation):
            with self.subTest(image=broken), self.assertRaises(ProfileCheckError):
                checked_images(self.live.replace(self.continuation, broken), live=True)

    def test_public_reduced_motion_requires_matching_still(self):
        for broken in (self.continuation.replace(REDUCED_MOTION, "(max-width: 600px)"),
                       self.continuation.replace("stitch-resume.png", "stitch-descent.png")):
            with self.subTest(image=broken), self.assertRaises(ProfileCheckError):
                checked_images(self.live.replace(self.continuation, broken), live=True)

    def test_direct_raw_url(self):
        direct = f"https://raw.githubusercontent.com/{REPO}/refs/heads/main/{OPENING}?v=abcd"
        actual = self.live.replace(self.urls[OPENING], direct)
        self.assertEqual(checked_images(actual, live=True)[OPENING][0], direct)

    def test_public_served_bytes_must_match_checkout(self):
        responses = {PROFILE: self.live.encode(),
                     **{f"https://github.com{self.urls[p]}": self.assets[p] for p in ASSETS}}
        with patch("verify_profile_visuals.read_url", side_effect=responses.__getitem__):
            verify_public(self.expected, self.assets)
            responses[f"https://github.com{self.urls[CONTINUATION]}"] = b"older GIF bytes"
            with self.assertRaisesRegex(ProfileCheckError, "bytes differ"):
                verify_public(self.expected, self.assets)

    def test_phone_aspect_floor_and_matching_still_dimensions(self):
        gif = self.assets[OPENING]
        thin = gif[:8] + (110).to_bytes(2, "little") + gif[10:]
        with self.assertRaisesRegex(ProfileCheckError, "thin strip"):
            check_artwork({**self.assets, OPENING: thin})
        opening_still = OPENING.replace(".gif", ".png")
        wrong_still = self.assets[CONTINUATION.replace(".gif", ".png")]
        with self.assertRaisesRegex(ProfileCheckError, "same dimensions"):
            check_artwork({**self.assets, opening_still: wrong_still})

    def test_threads_descend_and_match_across_the_copy(self):
        verify_thread_direction(OPENING_CURVES, CONTINUATION_CURVES)
        opening_sideways = (((10, 90), (40, 90, 60, 90, 100, 90)), *OPENING_CURVES[1:])
        with self.assertRaisesRegex(ValueError, "top to the bottom"):
            verify_thread_direction(opening_sideways, CONTINUATION_CURVES)
        start, *remaining = CONTINUATION_CURVES[0]
        shifted = (((start[0] + 10, start[1]), *remaining), *CONTINUATION_CURVES[1:])
        with self.assertRaisesRegex(ValueError, "endpoints must align"):
            verify_thread_direction(OPENING_CURVES, shifted)

    def test_bad_motion_bytes(self):
        gif = self.assets[OPENING]
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
