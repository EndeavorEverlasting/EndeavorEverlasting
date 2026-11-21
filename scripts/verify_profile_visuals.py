#!/usr/bin/env python3
"""Check profile artwork in the checkout and, optionally, on the public profile."""
import argparse
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
import re
from struct import unpack
import time
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

PROFILE = "https://github.com/EndeavorEverlasting"
REPO = "EndeavorEverlasting/EndeavorEverlasting"
OPENING = "assets/stitch-opening.gif"
CONTINUATION = "assets/stitch-continuation.gif"
MOTION = {OPENING: 0.33, CONTINUATION: 0.25}
ASSETS = tuple(path for gif in MOTION for path in (gif, gif.removesuffix(".gif") + ".png"))
MILESTONES = (
    "Threading complexity into stability",
    "I'm the builder behind",
    "I care about what happens",
    "Selected work",
)
REDUCED_MOTION = "(prefers-reduced-motion: reduce)"
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}
MAX_GIF_BYTES = 250_000


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
        for text in MILESTONES:
            if data.strip().startswith(text):
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
        markers = (f"# {MILESTONES[0]}", MILESTONES[1], MILESTONES[2], f"### {MILESTONES[3]}")
        for text, marker in zip(MILESTONES, markers):
            page.positions[text] = [(i, 0) for i, line in enumerate(source.splitlines(), 1)
                                    if line.startswith(marker)]

    require(len(page.images) == len(MOTION) and len(page.pictures) == len(MOTION),
            "Each of the two profile illustrations must have one visible picture and image.")
    images = {}
    positions = {}
    for (position, attrs, sources), path in zip(page.images, MOTION):
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
            "Profile headline, two introduction paragraphs and Selected work must remain visible.")
    headline, first, second, work = (page.positions[text][0] for text in MILESTONES)
    require(positions[OPENING] < headline < first < positions[CONTINUATION] < second < work,
            "Place the opening first and the continuation between the introduction paragraphs.")
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
    while (block := take(1)) != b";":
        if block == b",":
            flags = take(9)[-1]
            if flags & 128:
                take(3 * (2 << (flags & 7)))
            require(2 <= take(1)[0] <= 8, "Profile GIF has an invalid LZW code size.")
            skip_sub_blocks()
            require(delay >= 20, "Profile GIF requires explicit browser-safe frame delays.")
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
                require(application not in (b"NETSCAPE2.0", b"ANIMEXTS1.0"),
                        "Profile GIF must play once without a loop extension.")
                skip_sub_blocks()
            else:
                skip_sub_blocks()
        else:
            raise ProfileCheckError("Profile GIF contains an invalid GIF block.")
    require(frames > 1 and 0 < duration < 5000, "Profile GIF must animate for under five seconds.")
    return frames, duration


def read_url(url):
    request = Request(url, headers={"User-Agent": "ProfileVisualVerification/1.0",
                                   "Cache-Control": "no-cache"})
    with urlopen(request, timeout=12) as response:
        return response.read()


def check_artwork(asset_bytes):
    require(sum(len(asset_bytes[path]) for path in MOTION) <= MAX_GIF_BYTES,
            "The two GIFs together exceed the 250 kB budget.")
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
              f"{len(animation)} bytes, no loop", flush=True)


def verify_public(expected_images, asset_bytes):
    actual = checked_images(read_url(PROFILE).decode("utf-8"), live=True)
    for path, (src, alt) in actual.items():
        require(alt == expected_images[path][1], f"Public {path} alternative text is stale.")
        require(read_url(urljoin(PROFILE, src)) == asset_bytes[path],
                f"Public {path} bytes differ from this checkout.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Also verify the public GitHub profile.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        expected = checked_images((root / "README.md").read_text(encoding="utf-8"))
        asset_bytes = {path: (root / path).read_bytes() for path in ASSETS}
        check_artwork(asset_bytes)
        if args.live:
            for attempt in range(3):
                try:
                    verify_public(expected, asset_bytes)
                    break
                except (ValueError, OSError) as error:
                    if attempt == 2:
                        raise
                    print(f"Public profile check attempt {attempt + 1}: {error}", flush=True)
                    time.sleep(4)
            print(f"PASS public profile: {PROFILE}")
            for path in ASSETS:
                print(f"{path} SHA-256 {sha256(asset_bytes[path]).hexdigest()}")
    except (ValueError, OSError) as error:
        parser.exit(1, f"FAIL: {error}\n")


if __name__ == "__main__":
    main()
