#!/usr/bin/env python3
"""Check profile artwork in the checkout and, optionally, on the public profile."""
import argparse
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
import json
import os
from pathlib import Path
import re
from statistics import median
from struct import unpack
import time
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

PROFILE = "https://github.com/EndeavorEverlasting"
REPO = "EndeavorEverlasting/EndeavorEverlasting"
BANNER = "assets/hero.svg"
OPENING = "assets/stitch-descent.gif"
CONTINUATION = "assets/stitch-resume.gif"
PULSE = "assets/stitch-pulse.gif"
MOTION = {OPENING: 0.39, CONTINUATION: 0.30, PULSE: 0.27}
ASSETS = (BANNER, *(path for gif in MOTION for path in (gif, gif.removesuffix(".gif") + ".png")))
MILESTONES = (
    "Threading complexity into stability",
    "I'm the builder behind",
    "I care about what happens",
    "Selected work",
    "Building in public where practical.",
)
REDUCED_MOTION = "(prefers-reduced-motion: reduce)"
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}
MAX_GIF_BYTES = 250_000
FRAME_COUNT = 21
FRAME_MS = 130
LOOP_APPLICATIONS = (b"NETSCAPE2.0", b"ANIMEXTS1.0")
ARTWORK_REVIEW = "assets/profile-artwork-review.json"
RENDERER = "scripts/render_profile_motion.py"
ARTWORK_CRITERIA = ("cosmic_density", "dark_voids", "luminous_clusters",
                    "vertical_continuity", "phone_legibility", "fibonacci_structure",
                    "handoff_ontology", "continuous_motion", "palette", "pinned_handoff")


class ProfileCheckError(ValueError):
    """A profile artifact or its placement did not match the checked-out release."""


def require(condition, message):
    if not condition:
        raise ProfileCheckError(message)


class ProfileImages(HTMLParser):
    def __init__(self, source, live):
        super().__init__()
        self.live = live
        self.articles = []
        self.hidden_elements = []
        self.images = []
        self.pictures = []
        self.body_text = []
        self.picture = None
        self.positions = {text: [] for text in MILESTONES}
        self.feed(source)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "article":
            self.articles.append("markdown-body" in (attrs.get("class") or "").split())
        if self.hidden_elements:
            if tag == self.hidden_elements[-1]:
                self.hidden_elements.append(tag)
            return
        style = re.sub(r"\s+", "", (attrs.get("style") or "").lower())
        hidden = ("hidden" in attrs or tag in ("code", "template") or
                  (tag == "details" and "open" not in attrs) or
                  "display:none" in style or "visibility:hidden" in style)
        if hidden:
            if tag not in VOID_TAGS:
                self.hidden_elements.append(tag)
            return
        if self.live and not any(self.articles):
            return
        if tag == "picture":
            self.picture = []
            self.pictures.append(self.picture)
        elif tag == "source" and self.picture is not None:
            self.picture.append((self.getpos(), attrs))
        elif tag == "img":
            self.images.append((self.getpos(), attrs, self.picture))

    def handle_data(self, data):
        if not self.live or self.hidden_elements or not any(self.articles):
            return
        visible = data.strip()
        if visible:
            self.body_text.append((self.getpos(), visible))
        for text in MILESTONES:
            if visible.startswith(text):
                self.positions[text].append(self.getpos())

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.hidden_elements and tag == self.hidden_elements[-1]:
            self.hidden_elements.pop()
        elif tag == "picture" and not self.hidden_elements:
            self.picture = None
        if tag == "article" and self.articles:
            self.articles.pop()


def asset_url(src, path, live):
    url = urlsplit(urljoin(PROFILE, src))
    github_raw = url.netloc == "github.com" and url.path == f"/{REPO}/raw/main/{path}"
    direct_raw = url.netloc == "raw.githubusercontent.com" and url.path in (
        f"/{REPO}/main/{path}", f"/{REPO}/refs/heads/main/{path}")
    require((not live and src == path) or (url.scheme == "https" and (github_raw or direct_raw)),
            f"{path} must point to the profile repository's main-branch asset.")
    return src


def checked_images(source, *, live=False):
    if not live:
        source = re.sub(r"(?s)<!--.*?-->", "", source)
        source = re.sub(r"(?ms)^ {0,3}(\x60{3,}|~{3,})[^\n]*\n.*?^ {0,3}\1[ \t]*$", "", source)
        source = re.sub(r"(?<!\x60)(\x60+)(?!\x60).*?(?<!\x60)\1(?!\x60)", "", source)
    page = ProfileImages(source, live)
    if not live:
        markers = (f"# {MILESTONES[0]}", MILESTONES[1], MILESTONES[2],
                   f"### {MILESTONES[3]}", f"<sub>{MILESTONES[4]}")
        for text, marker in zip(MILESTONES, markers):
            page.positions[text] = [(i, 0) for i, line in enumerate(source.splitlines(), 1)
                                    if line.startswith(marker)]

    require(len(page.images) == len(MOTION) + 1 and len(page.pictures) == len(MOTION),
            "The profile needs one banner and three motion pictures.")
    banner_position, banner, banner_sources = page.images[0]
    banner_src = asset_url(banner.get("src") or "", BANNER, live)
    banner_alt = (banner.get("alt") or "").strip()
    require(banner_sources is None and banner.get("width") == "100%" and
            "height" not in banner and banner_alt and "hidden" not in banner,
            "The top banner must be visible and fill the README width.")
    images = {BANNER: (banner_src, banner_alt)}
    positions = {}
    for (position, attrs, sources), path in zip(page.images[1:], MOTION):
        src = asset_url(attrs.get("src") or "", path, live)
        require(attrs.get("width") == "100%" and "height" not in attrs,
                f"{path} must fill the README width with its natural aspect ratio.")
        alt = (attrs.get("alt") or "").strip()
        require(alt and "hidden" not in attrs, f"{path} must be visible and have alternative text.")
        require(sources and len(sources) == 1 and sources[0][0] < position,
                f"{path} must have one still source before its animated image.")
        fallback = sources[0][1]
        require(fallback.get("media") == REDUCED_MOTION,
                f"{path} must honor the visitor's reduced-motion preference.")
        still = path.removesuffix(".gif") + ".png"
        images[path] = (src, alt)
        images[still] = (asset_url(fallback.get("srcset") or "", still, live), None)
        positions[path] = position

    require(all(len(page.positions[text]) == 1 for text in MILESTONES),
            "Profile headline, introduction, Selected work and closing copy must remain visible.")
    headline, first, second, work, closing = (page.positions[text][0] for text in MILESTONES)
    require(banner_position < positions[OPENING] < headline < first <
            positions[CONTINUATION] < second < work < closing < positions[PULSE],
            "Place the banner, opener, intro, continuation, body and pulse in reading order.")
    if live:
        # Readable copy after the footer would break the visual bookend.
        article_text = [position for position, _ in page.body_text]
        require(not article_text or max(article_text) < positions[PULSE],
                "The pulsing artwork must be the last visible README content.")
    else:
        tail = re.split(r"</picture>", source, flags=re.I)[-1]
        require(not tail.strip(), "The pulsing artwork must be the last README content.")
    return images


def gif_timing(content):
    """Inspect GIF block framing and timing without image-library dependencies."""
    require(len(content) <= MAX_GIF_BYTES, "Profile GIF exceeds its 250 kB budget.")
    stream = BytesIO(content)

    def take(count):
        block = stream.read(count)
        require(len(block) == count, "Profile GIF is truncated.")
        return block

    def skip_sub_blocks():
        while count := take(1)[0]:
            take(count)

    require(take(6) in (b"GIF87a", b"GIF89a"), "Profile GIF is not a GIF.")
    width, height, flags = unpack("<HHB", take(5))
    require(width > 0 and height > 0, "Profile GIF has invalid dimensions.")
    take(2)
    if flags & 128:
        take(3 * (2 << (flags & 7)))

    frames = duration = delay = 0
    loop_seen = False
    while (block := take(1)) != b";":
        if block == b",":
            flags = take(9)[-1]
            if flags & 128:
                take(3 * (2 << (flags & 7)))
            require(2 <= take(1)[0] <= 8, "Profile GIF has an invalid LZW code size.")
            skip_sub_blocks()
            require(delay >= 20, "Profile GIF requires explicit browser-safe frame delays.")
            require(delay == FRAME_MS, "Profile GIF must keep a uniform Fibonacci frame delay.")
            frames += 1
            duration += delay
            delay = 0
        elif block == b"!":
            extension = take(1)
            if extension == b"\xf9":
                require(take(1) == b"\x04", "Invalid GIF frame timing block.")
                delay = int.from_bytes(take(4)[1:3], "little") * 10
                require(take(1) == b"\0", "Invalid GIF frame timing terminator.")
            elif extension == b"\xff":
                application = take(take(1)[0])
                if application in LOOP_APPLICATIONS:
                    require(not loop_seen and frames == 0,
                            "Profile GIF requires exactly one loop declaration before the frames.")
                    require(take(5) == b"\x03\x01\x00\x00\x00",
                            "Profile GIF must repeat indefinitely.")
                    loop_seen = True
                else:
                    skip_sub_blocks()
            else:
                skip_sub_blocks()
        else:
            raise ProfileCheckError("Profile GIF contains an invalid GIF block.")
    require(loop_seen, "Profile GIF must repeat indefinitely.")
    require(frames == FRAME_COUNT, "Profile GIF must contain the complete 21-frame cycle.")
    return frames, duration


def read_url(url):
    request = Request(url, headers={"User-Agent": "ProfileVisualVerification/1.0",
                                   "Cache-Control": "no-cache"})
    with urlopen(request, timeout=12) as response:
        return response.read()


def check_artwork(asset_bytes):
    require(sum(len(asset_bytes[path]) for path in MOTION) <= MAX_GIF_BYTES,
            "The three GIFs together exceed the 250 kB budget.")
    for path, minimum_aspect in MOTION.items():
        animation = asset_bytes[path]
        frames, duration = gif_timing(animation)
        width, height = unpack("<HH", animation[6:10])
        require(height / width >= minimum_aspect,
                f"{path} returns to a thin strip at phone widths.")
        still = asset_bytes[path.removesuffix(".gif") + ".png"]
        require(still[:16] == b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" and
                len(still) >= 24 and unpack(">II", still[16:24]) == (width, height),
                f"{path} needs a PNG still with the same dimensions.")
        print(f"PASS {path}: {width}×{height}, {frames} frames, {duration} ms, "
              f"{len(animation)} bytes, infinite loop", flush=True)


def check_cosmic_density(image, path):
    """Catch sparse line-art silhouettes and flatter fields at reading size."""
    levels = image.histogram()
    pixels = image.width * image.height
    darkness = sum(levels[:31]) / pixels
    filaments = sum(levels[31:105]) / pixels
    cores = sum(levels[170:]) / pixels
    require(0.19 <= darkness <= 0.62 and filaments >= 0.32 and 0.006 <= cores <= 0.12,
            f"{path} must retain dark voids, diffuse filament density and compact luminous cores.")


def check_footer_handoff(changes):
    """Both outgoing pulses must reach the bottom in downward order."""
    width, height = changes[0].size
    bands = [round(height*fraction) for fraction in (1/2, 2/3, 5/6, 1)]
    for left, right in ((width//6, width//2), (width//2, 5*width//6)):
        peaks = []
        for top, bottom in zip(bands, bands[1:]):
            energy = [sum(max(0, value-12) for value in frame.crop(
                (left, top, right, bottom)).tobytes()) for frame in changes]
            peaks.append(max(range(len(energy)), key=energy.__getitem__))
            require(max(energy) >= 50, "Both footer branches must visibly pulse near the lower edge.")
        steps = [(end-start) % len(changes) for start, end in zip(peaks, peaks[1:])]
        require(all(0 < step <= len(changes)//3 for step in steps),
                "Both footer branches must pulse downward toward the pinned projects.")


def check_motion_pixels(asset_bytes):
    """Measure the actual GIF frames after browser-like phone-scale resampling."""
    from PIL import Image, ImageChops, ImageSequence

    def motion_size(frame):
        return frame.convert("L").resize(
            (255, round(frame.height / frame.width * 255)), Image.Resampling.LANCZOS
        )

    for path in MOTION:
        with Image.open(BytesIO(asset_bytes[path])) as gif:
            frames = [motion_size(frame) for frame in ImageSequence.Iterator(gif)]
        require(len(frames) == FRAME_COUNT, f"{path} has an incomplete decoded cycle.")
        check_cosmic_density(frames[0], path)
        still = path.removesuffix(".gif") + ".png"
        with Image.open(BytesIO(asset_bytes[still])) as image:
            check_cosmic_density(motion_size(image), still)
        deltas = []
        for first, second in zip(frames, frames[1:] + frames[:1]):
            changes = ImageChops.difference(first, second).histogram()
            deltas.append(sum(level*count for level, count in enumerate(changes)))
        typical = median(deltas[:-1])
        minimum = 900 if path == PULSE else 1600
        require(typical >= minimum, f"{path} has no legible motion at phone width.")
        require(0 < deltas[-1] <= typical * 2,
                f"{path} visibly jumps or holds at the repeat seam.")
        # Subtract the stationary dust using the darkest observed local value.
        floor = frames[0]
        for frame in frames[1:]:
            floor = ImageChops.darker(floor, frame)
        changes = [ImageChops.subtract(frame, floor) for frame in frames]
        if path == PULSE:
            check_footer_handoff(changes)
        else:
            middle = (0, round(frames[0].height*0.28), 255, round(frames[0].height*0.68))
            centers = []
            for change in changes:
                band = change.crop(middle)
                pixels = band.tobytes()
                rows = [sum(max(0, value-16) for value in pixels[i:i+255])
                        for i in range(0, len(pixels), 255)]
                centers.append(sum(i*weight for i, weight in enumerate(rows))/sum(rows)
                               if sum(rows) > 240 else None)
            advances = [b-a for a, b in zip(centers, centers[1:] + centers[:1])
                        if a is not None and b is not None and abs(b-a) <= 12]
            require(sum(advance > 1 for advance in advances) >= 3 and
                    sum(advance > 1 for advance in advances) > sum(advance < -1 for advance in advances),
                    f"{path} must show light traveling down the branches.")


def check_review(review, release_bytes):
    """Keep visual inspection tied to the exact renderer and delivered pixels."""
    require(isinstance(review, dict) and review.get("version") == 1,
            "Use the visual review record described in assets/profile-artwork.md.")
    notes = review.get("observations")
    require(isinstance(notes, dict) and set(notes) == set(ARTWORK_CRITERIA) and
            all(isinstance(note, str) and note.strip() for note in notes.values()),
            "Record every visual observation in " + ARTWORK_REVIEW + ".")
    digests = review.get("sha256")
    require(isinstance(digests, dict) and set(digests) == set(release_bytes),
            "The visual review must cover the banner, all six animated or still files and the renderer.")
    for path, content in release_bytes.items():
        require(digests[path] == sha256(content).hexdigest(),
                f"{path} differs from the reviewed version. See assets/profile-artwork.md.")


def verify_public(expected_images, asset_bytes):
    actual = checked_images(read_url(PROFILE).decode("utf-8"), live=True)
    for path, (src, alt) in actual.items():
        require(alt == expected_images[path][1], f"Public {path} alternative text is stale.")
        require(read_url(urljoin(PROFILE, src)) == asset_bytes[path],
                f"Public {path} bytes differ from this checkout.")


def verify_archived_public(blocks, name, archive_files):
    from profile_release import archive_prefix

    actual = ProfileImages(read_url(PROFILE).decode("utf-8"), True)
    expected = [(slot, ProfileImages(block, False).images[0])
                for slot, group in blocks.items() for block in group]
    require(len(actual.images) == len(expected), "Public profile has the wrong archived layout.")
    for (slot, (_, artwork, stills)), (position, image, sources) in zip(expected, actual.images):
        require(image.get("alt") == artwork.get("alt") and image.get("width") == "100%"
                and "height" not in image and "hidden" not in image, "Archived artwork presentation changed.")
        require(len(sources or []) == len(stills or []), "Archived reduced-motion sources changed.")
        files = [(image.get("src"), artwork["src"])]
        for (_, actual_source), (_, source) in zip(sources or [], stills or []):
            require(actual_source.get("media") == source.get("media"), "Archived media query changed.")
            files.append((actual_source.get("srcset"), source["srcset"]))
        if slot in ("after_intro", "before_work"):
            marker = MILESTONES[2] if slot == "after_intro" else MILESTONES[3]
            next_section = actual.positions[marker]
            require(len(next_section) == 1 and position < next_section[0] and
                    not any(position < p < next_section[0] for p, _ in actual.body_text),
                    "Public archived artwork moved away from its text break.")
        else:
            valid = (all(position < p for p, _ in actual.body_text) if slot == "top"
                     else all(p < position for p, _ in actual.body_text))
            require(valid, "Public archived artwork moved away from the page edge.")
        prefix = archive_prefix(name)
        for src, expected_path in files:
            url = asset_url(src or "", expected_path, True)
            content_path = expected_path.removeprefix(prefix + "/")
            require(read_url(urljoin(PROFILE, url)) == archive_files[content_path],
                    f"Public {expected_path} differs from the archived release.")


def main():
    from profile_release import current_version

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Also verify the public GitHub profile.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        selected, blocks, files = current_version(root, os.getenv("PROFILE_RELEASE_BASE") or None)
        if not selected["archive"]:
            expected = checked_images((root / "README.md").read_text(encoding="utf-8"))
            asset_bytes = {path: (root / path).read_bytes() for path in ASSETS}
            check_artwork(asset_bytes)
            check_motion_pixels(asset_bytes)
            review = json.loads((root / ARTWORK_REVIEW).read_text(encoding="utf-8"))
            check_review(review, {**asset_bytes, RENDERER: (root / RENDERER).read_bytes()})
        else:
            asset_bytes = {path: data for path, data in files.items() if path != "README.md"}
        print(f"PASS active profile version: {selected['id']}")
        if args.live:
            for attempt in range(3):
                try:
                    if selected["archive"]:
                        verify_archived_public(blocks, selected["id"], files)
                    else:
                        verify_public(expected, asset_bytes)
                    break
                except (ValueError, OSError) as error:
                    if attempt == 2:
                        raise
                    print(f"Public profile check attempt {attempt + 1}: {error}", flush=True)
                    time.sleep(4)
            print(f"PASS public profile: {PROFILE}")
            for path, content in asset_bytes.items():
                print(f"{path} SHA-256 {sha256(content).hexdigest()}")
    except (ValueError, OSError) as error:
        parser.exit(1, f"FAIL: {error}\n")


if __name__ == "__main__":
    main()
