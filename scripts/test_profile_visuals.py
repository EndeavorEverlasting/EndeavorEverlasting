"""Regression cases for the profile rollout verification."""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from render_profile_motion import (
    BANNER_EXIT_X, BANNER_WIDTH, ENTRY_X, FIBONACCI, FLOW, FOOTER_BRANCHES, FOOTER_FORK,
    FRAME_MS, FRAMES, NEBULAE, PANELS, WIDTH, topology,
)
from profile_release import archive_prefix, catalog
from verify_profile_scope import NEXUS_ALT, NEXUS_MEDIA, REPOSITORIES_URL
from verify_profile_visuals import (
    ARTWORK_REVIEW, ASSETS, BANNER, CONTINUATION, MILESTONES, OPENING, PROFILE, PULSE,
    REDUCED_MOTION, RENDERER, REPO,
    ProfileCheckError, check_artwork, check_bicolor_density, check_cosmic_density, check_motion_pixels,
    check_nexus_pixels, check_quality_floor, check_quality_measurements, check_review,
    checked_images, gif_timing, verify_public,
)

ROOT = Path(__file__).resolve().parents[1]


class ProfileVisualTests(unittest.TestCase):
    def setUp(self):
        releases = catalog(ROOT)
        latest = max(releases["versions"], key=lambda version: int(version[1:]))
        latest_readme = (ROOT / archive_prefix(latest) / "README.md").read_text(encoding="utf-8")
        self.nexus = bool(NEXUS_MEDIA.search(latest_readme))
        self.readme = (ROOT / archive_prefix("v09") / "README.md").read_text(encoding="utf-8")
        self.expected = checked_images(self.readme)
        self.assets = {path: (ROOT / path).read_bytes() for path in ASSETS}
        self.urls = {path: f"/{REPO}/raw/main/{path}" for path in ASSETS}
        self.opening = self.picture(OPENING)
        self.continuation = self.picture(CONTINUATION)
        self.pulse = self.picture(PULSE)
        self.banner = f'<img src="{self.urls[BANNER]}" width="100%" alt="{self.expected[BANNER][1]}">'
        headline, first, second, work, ending = MILESTONES
        self.live = (
            f'<article class="markdown-body">{self.banner}{self.opening}<h1>{headline}</h1>'
            f'<p>{first}</p>{self.continuation}<p>{second}</p><h3>{work}</h3>'
            f'<sub>{ending}</sub>{self.pulse}</article>'
        )

    def picture(self, path):
        still = path.removesuffix(".gif") + ".png"
        return (
            f'<picture><source srcset="{self.urls[still]}" media="{REDUCED_MOTION}">'
            f'<img src="{self.urls[path]}" width="100%" alt="{self.expected[path][1]}"></picture>'
        )

    def test_current_checkout(self):
        check_artwork(self.assets, nexus=self.nexus)
        check_motion_pixels(self.assets, nexus=self.nexus)

    def test_nexus_artwork_links_both_invitations_to_public_work(self):
        footer = self.pulse.replace(self.expected[PULSE][1], NEXUS_ALT)
        linked = f'<a href="{REPOSITORIES_URL}">{footer}</a>'
        live = self.live.replace(self.pulse, linked)
        checked_images(live, live=True, nexus=True)
        for wrong in (footer, linked.replace(REPOSITORIES_URL, "https://example.com"),
                      linked.replace("Build with me.", ""), linked + "<p>Explore</p>"):
            with self.subTest(wrong=wrong), self.assertRaises(ProfileCheckError):
                checked_images(live.replace(linked, wrong), live=True, nexus=True)

    def test_nexus_rejects_the_old_unlettered_poster(self):
        if not self.nexus:
            self.skipTest("The checkout has not captured its Nexus footer yet.")
        path = PULSE.replace(".gif", ".png")
        old_still = (ROOT / archive_prefix("v09") / path).read_bytes()
        with self.assertRaisesRegex(ProfileCheckError, "same Nexus text"):
            check_motion_pixels({**self.assets, path: old_still}, nexus=True)

    def test_nexus_rejects_subtle_flicker_without_a_visible_halo(self):
        if not self.nexus:
            self.skipTest("The checkout has not captured its Nexus footer yet.")
        from PIL import Image, ImageChops, ImageSequence

        def phone(frame):
            return frame.convert("RGB").resize((255, 75), Image.Resampling.LANCZOS).convert("L")

        with Image.open(BytesIO(self.assets[PULSE])) as gif:
            frames = [phone(frame) for frame in ImageSequence.Iterator(gif)]
        with Image.open(BytesIO(self.assets[PULSE.removesuffix(".gif") + ".png"])) as poster:
            still = phone(poster)
        floor = frames[0]
        for frame in frames[1:]:
            floor = ImageChops.darker(floor, frame)
        dimmed = [Image.blend(floor, frame, .35) for frame in frames]
        with self.assertRaisesRegex(ProfileCheckError, "Visible glow"):
            check_nexus_pixels(dimmed, still)

    def test_top_banner_and_bottom_pulse_are_bookends(self):
        for bad_markup in (
            self.live.replace(self.banner, ""),
            self.live.replace(self.opening, "").replace(self.pulse, self.opening + self.pulse),
            self.live.replace(self.pulse, "").replace(self.banner, self.banner + self.pulse),
            self.live.replace("</article>", "<p>Stray copy</p></article>"),
        ):
            with self.subTest(markup=bad_markup), self.assertRaises(ProfileCheckError):
                checked_images(bad_markup, live=True)

    def test_public_invitation_follows_the_footer_with_the_expected_link(self):
        invitation = (f'<p><strong>Explore projects.</strong> Start with the pins below. '
                      f'<a href="{REPOSITORIES_URL}">Browse all repositories</a></p>')
        live = self.live.replace("</article>", invitation + "</article>")
        checked_images(live, live=True, invitation=invitation)
        for bad in (
            self.live,
            self.live.replace(self.pulse, invitation + self.pulse),
            live.replace('<p><strong>Explore', '<p hidden><strong>Explore'),
            live.replace(REPOSITORIES_URL, "https://example.com/projects"),
            live.replace(f'<a href="{REPOSITORIES_URL}">Browse all repositories</a>',
                         f'Browse all repositories<a href="{REPOSITORIES_URL}"></a>'),
            live.replace("</article>", "<p>Extra copy</p></article>"),
        ):
            with self.subTest(markup=bad), self.assertRaisesRegex(ProfileCheckError, "invitation"):
                checked_images(bad, live=True, invitation=invitation)

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

    def test_shared_field_crosses_both_readme_seams(self):
        seams = (0, PANELS[0][1], PANELS[0][1] + PANELS[1][1])
        edges = [strand for strand in topology() if strand.flow]
        routes = (FLOW, *FOOTER_BRANCHES)
        self.assertEqual([(edge.start, edge.end) for edge in edges],
                         [edge for route in routes for edge in zip(route, route[1:])])
        self.assertTrue(all(edge.end[1] > edge.start[1] for edge in edges))
        self.assertEqual(FLOW[0][0], ENTRY_X)
        self.assertAlmostEqual(ENTRY_X / WIDTH, BANNER_EXIT_X / BANNER_WIDTH, places=3)
        self.assertEqual(FLOW[-1], FOOTER_FORK)
        self.assertTrue(all(route[0] == FOOTER_FORK for route in FOOTER_BRANCHES))
        left, right = (route[-2][0] / WIDTH for route in FOOTER_BRANCHES)
        self.assertAlmostEqual(left, 0.25, delta=0.03)
        self.assertAlmostEqual(right, 0.75, delta=0.03)
        for seam in seams:
            self.assertEqual(sum(edge.start[1] < seam < edge.end[1] for edge in edges), 1)

    def test_growth_connects_neighboring_clouds(self):
        degree = Counter(point for edge in topology() for point in (edge.start, edge.end))
        self.assertEqual(set(degree), set(FLOW + NEBULAE).union(*FOOTER_BRANCHES))
        self.assertTrue(all(degree[cloud] >= 3 for cloud in NEBULAE))
        self.assertGreaterEqual(sum(value >= 4 for value in degree.values()), 20)

    def test_fibonacci_cadence(self):
        self.assertTrue(all(a + b == c for a, b, c in zip(FIBONACCI, FIBONACCI[1:], FIBONACCI[2:])))
        self.assertEqual((FRAME_MS, FRAMES), (130, 21))

    def test_sparse_line_art_and_uniform_fog_fail_density_check(self):
        from PIL import Image, ImageDraw

        thin = Image.new("L", (255, 100), 13)
        ImageDraw.Draw(thin).line((13, 0, 237, 99), fill=203, width=11)
        uniform = Image.new("L", (255, 100), 74)
        for sample in (thin, uniform):
            with self.assertRaisesRegex(ProfileCheckError, "diffuse filament density"):
                check_cosmic_density(sample, "fixture")

    def test_reverse_flow_fails_decoded_motion_check(self):
        from PIL import Image, ImageSequence

        with Image.open(BytesIO(self.assets[CONTINUATION])) as animation:
            frames = [frame.convert("RGB") for frame in ImageSequence.Iterator(animation)]
        frames.reverse()
        reversed_gif = BytesIO()
        frames[0].save(reversed_gif, format="GIF", save_all=True, append_images=frames[1:],
                       duration=FRAME_MS, loop=0)
        with self.assertRaisesRegex(ProfileCheckError, "traveling down"):
            check_motion_pixels({**self.assets, CONTINUATION: reversed_gif.getvalue()})

    def test_old_stationary_footer_fails_decoded_motion_check(self):
        stationary = (ROOT / archive_prefix("v07") / PULSE).read_bytes()
        still = PULSE.removesuffix(".gif") + ".png"
        legacy_still = (ROOT / archive_prefix("v09") / still).read_bytes()
        with self.assertRaisesRegex(ProfileCheckError, "footer branches"):
            check_motion_pixels({**self.assets, PULSE: stationary, still: legacy_still})

    def test_previous_sparse_accent_fails_bicolor_density(self):
        from PIL import Image

        still = ROOT / archive_prefix("v08") / OPENING.replace(".gif", ".png")
        with Image.open(still) as art:
            phone = art.convert("RGB").resize((255, 112), Image.Resampling.LANCZOS)
        with self.assertRaisesRegex(ProfileCheckError, "orange dust and orange knots"):
            check_bicolor_density(phone, OPENING)

    def test_review_protects_assets_and_renderer(self):
        review = json.loads((ROOT / ARTWORK_REVIEW).read_text(encoding="utf-8"))
        release = {**self.assets, RENDERER: (ROOT / RENDERER).read_bytes()}
        check_review(review, release)
        # This alteration leaves GIF layout and block timing valid.
        gif = bytearray(release[OPENING])
        gif[13] ^= 1
        check_artwork({**self.assets, OPENING: bytes(gif)}, nexus=self.nexus)
        for path, changed in ((OPENING, bytes(gif)), (RENDERER, b"flat line renderer")):
            with self.subTest(path=path), self.assertRaisesRegex(ProfileCheckError, "reviewed version"):
                check_review(review, {**release, path: changed})
        notes = dict(review["observations"])
        notes.pop("cosmic_density")
        with self.assertRaisesRegex(ProfileCheckError, "every visual observation"):
            check_review({**review, "observations": notes}, release)

    def test_v11_baseline_accepts_reference_and_catches_older_valid_art(self):
        criteria = json.loads((ROOT / ARTWORK_REVIEW).read_text())["quality_floor"]["criteria"]
        for version in ("v11", "v10"):
            archive = ROOT / archive_prefix(version)
            assets = {path: (archive / path).read_bytes() for path in ASSETS}
            check_artwork(assets, nexus=True, report=False)
            actual = check_motion_pixels(assets, nexus=True)
            if version == "v11":
                check_quality_floor(ROOT, assets, actual)
            else:
                with self.assertRaisesRegex(ProfileCheckError, "cosmic_density.*continuation"):
                    check_quality_measurements(criteria, actual)

    def test_quality_gate_rejects_dim_glow_even_with_a_motion_improvement(self):
        floor = json.loads((ROOT / ARTWORK_REVIEW).read_text())["quality_floor"]["criteria"]
        actual = {name: rule["v11"] for criterion in floor.values()
                  for name, rule in criterion["measurements"].items()}
        actual["opening.frame_delta_median"] *= 1.15
        actual["nexus.halo_pixels_min"] -= 1
        with self.assertRaisesRegex(ProfileCheckError, "nexus.halo_pixels_min"):
            check_quality_measurements(floor, actual)

    def test_new_artwork_requires_inspected_hashes_and_a_visible_improvement(self):
        review = json.loads((ROOT / ARTWORK_REVIEW).read_text())
        criteria = review["quality_floor"]["criteria"]
        actual = {name: rule["v11"] for criterion in criteria.values()
                  for name, rule in criterion["measurements"].items()}
        archive = ROOT / archive_prefix("v11")
        assets = {path: (archive / path).read_bytes() for path in ASSETS}
        assets[BANNER] += b"\n"
        evidence = {
            "baseline": "v11",
            "sha256": {path: sha256(content).hexdigest() for path, content in assets.items()},
            "criteria": {name: {"score": 1, "evidence": "test evidence"} for name in criteria},
        }
        for change, message in (("stale", "exact delivered"), ("parity", "one visible improvement"),
                                ("regression", "matches or improves"), ("improved", None)):
            candidate = deepcopy(evidence)
            if change == "stale":
                candidate["sha256"][BANNER] = "0" * 64
            if change in ("regression", "improved"):
                candidate["criteria"]["luminous_clusters"]["score"] = 0 if change == "regression" else 2
            with self.subTest(change=change), patch.object(Path, "read_text", return_value=json.dumps({
                **review, "candidate_evaluation": candidate,
            })):
                if message:
                    with self.assertRaisesRegex(ProfileCheckError, message):
                        check_quality_floor(ROOT, assets, actual)
                else:
                    check_quality_floor(ROOT, assets, actual)

    def test_restored_release_uses_its_archived_assessment(self):
        review = json.loads((ROOT / ARTWORK_REVIEW).read_text())
        criteria = review["quality_floor"]["criteria"]
        actual = {name: rule["v11"] for criterion in criteria.values()
                  for name, rule in criterion["measurements"].items()}
        archive = ROOT / archive_prefix("v11")
        assets = {path: (archive / path).read_bytes() for path in ASSETS}
        assets[BANNER] += b"\n"
        assessments = {name: {"score": 1, "evidence": "test evidence"} for name in criteria}
        assessments["luminous_clusters"]["score"] = 2
        evidence = {"baseline": "v11", "criteria": assessments,
                    "sha256": {path: sha256(content).hexdigest() for path, content in assets.items()}}
        versions = {**catalog(ROOT)["versions"], "v12": {"quality_evaluation": evidence}}
        with patch.object(Path, "read_text", return_value=json.dumps({
            **review, "candidate_evaluation": {"baseline": "another release"},
        })), patch("profile_release.catalog", return_value={"versions": versions}):
            self.assertEqual(check_quality_floor(ROOT, assets, actual, "v12"), evidence)

    def test_bad_motion_bytes(self):
        gif = self.assets[OPENING]
        start_of_blocks = 13 + 3 * (2 << (gif[10] & 7))
        loop = b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
        still = bytes.fromhex(
            "47494638396101000100800000000000ffffff21f90400020000002c00000000010001000002024401003b"
        )
        broken_lzw = still.replace(b"\x00\x02\x02\x44", b"\x00\xff\x02\x44")
        self.assertNotEqual(still, broken_lzw)
        no_loop = gif.replace(loop, b"", 1)
        finite = gif.replace(loop, loop[:-3] + b"\x02\x00\x00", 1)
        for content, message in ((still, "uniform Fibonacci frame delay"),
                                 (broken_lzw, "invalid LZW"),
                                 (gif[:-1], "truncated"),
                                 (gif[:start_of_blocks] + loop + gif[start_of_blocks:], "exactly one loop"),
                                 (no_loop, "repeat indefinitely"),
                                 (finite, "repeat indefinitely"),
                                 (bytes(250_001), "250 kB budget")):
            with self.subTest(message=message), self.assertRaisesRegex(ProfileCheckError, message):
                gif_timing(content)


if __name__ == "__main__":
    unittest.main()
