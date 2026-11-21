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
HERO = "assets/hero.svg"
GIF = "assets/first-stitch.gif"
ASSETS = (HERO, GIF)
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
        self.strong = False
        self.explore = []
        self.selected_work = []
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
        if tag == "img":
            self.images.append((self.getpos(), attrs))
        elif tag == "strong":
            self.strong = True
        elif tag == "a" and attrs.get("id") == "user-content-selected-work":
            self.selected_work.append(self.getpos())

    def handle_data(self, data):
        if self.strong and data.strip() == "Explore:":
            self.explore.append(self.getpos())

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.hidden_elements and tag == self.hidden_elements[-1]:
            self.hidden_elements.pop()
        if tag == "strong":
            self.strong = False
        if tag == "article" and self.articles:
            self.articles.pop()


def checked_images(source, *, live=False):
    if not live:
        source = re.sub(r"(?ms)^ {0,3}(\x60{3,}|~{3,})[^\n]*\n.*?^ {0,3}\1[ \t]*$", "", source)
        source = re.sub(r"(?<!\x60)(\x60+)(?!\x60).*?(?<!\x60)\1(?!\x60)", "", source)
    page = ProfileImages(source, live)
    if not live:
        page.explore = [(i, 0) for i, line in enumerate(source.splitlines(), 1)
                        if line.startswith("**Explore:**")]
        page.selected_work = [(i, 0) for i, line in enumerate(source.splitlines(), 1)
                              if line == "### Selected work"]

    images = {}
    positions = {}
    for path in ASSETS:
        matches = [(position, attrs) for position, attrs in page.images
                   if urlsplit(attrs.get("src") or "").path.endswith("/" + path)
                   or (attrs.get("src") or "") == path]
        require(len(matches) == 1, f"Expected one {path} image in the profile README.")
        position, attrs = matches[0]
        src = attrs["src"]
        url = urlsplit(urljoin(PROFILE, src))
        github_raw = url.netloc == "github.com" and url.path == f"/{REPO}/raw/main/{path}"
        direct_raw = url.netloc == "raw.githubusercontent.com" and url.path in (
            f"/{REPO}/main/{path}", f"/{REPO}/refs/heads/main/{path}")
        require((not live and src == path) or (url.scheme == "https" and (github_raw or direct_raw)),
                f"{path} must point to the profile repository's main-branch asset.")
        require(attrs.get("width") == "100%" and "height" not in attrs,
                f"{path} must fill the README width with its natural aspect ratio.")
        require((attrs.get("alt") or "").strip() and "hidden" not in attrs,
                f"{path} must be visible and have alternative text.")
        positions[path] = position
        images[path] = (src, attrs["alt"])
    require(len(page.explore) == 1 and len(page.selected_work) == 1,
            "Profile README must contain Explore and Selected work.")
    require(positions[HERO] < page.explore[0] < positions[GIF] < page.selected_work[0],
            "Place First Stitch between Explore and Selected work, below the hero.")
    return images


def gif_timing(content):
    """Inspect GIF block framing and timing without image-library dependencies."""
    require(len(content) <= MAX_GIF_BYTES, "First Stitch exceeds its 250 kB budget.")
    stream = BytesIO(content)

    def take(count):
        block = stream.read(count)
        require(len(block) == count, "First Stitch is truncated.")
        return block

    def skip_sub_blocks():
        while count := take(1)[0]:
            take(count)

    require(take(6) in (b"GIF87a", b"GIF89a"), "First Stitch is not a GIF.")
    width, height, flags = unpack("<HHB", take(5))
    require(width > 0 and height > 0, "First Stitch has invalid dimensions.")
    take(2)
    if flags & 128:
        take(3 * (2 << (flags & 7)))

    frames = duration = delay = 0
    while (block := take(1)) != b";":
        if block == b",":
            flags = take(9)[-1]
            if flags & 128:
                take(3 * (2 << (flags & 7)))
            require(2 <= take(1)[0] <= 8, "First Stitch has an invalid LZW code size.")
            skip_sub_blocks()
            require(delay >= 20, "First Stitch requires explicit browser-safe frame delays.")
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
                        "First Stitch must play once without a loop extension.")
                skip_sub_blocks()
            else:
                skip_sub_blocks()
        else:
            raise ProfileCheckError("First Stitch contains an invalid GIF block.")
    require(frames > 1 and 0 < duration < 5000, "First Stitch must animate for under five seconds.")
    return frames, duration


def read_url(url):
    request = Request(url, headers={"User-Agent": "ProfileVisualVerification/1.0",
                                   "Cache-Control": "no-cache"})
    with urlopen(request, timeout=12) as response:
        return response.read()


def verify_public(expected_images, asset_bytes):
    actual = checked_images(read_url(PROFILE).decode("utf-8"), live=True)
    for path, (src, alt) in actual.items():
        require(alt == expected_images[path][1], f"Public {path} alternative text is stale.")
        served, expected = read_url(urljoin(PROFILE, src)), asset_bytes[path]
        if path == HERO:
            # Git may check out the SVG as CRLF on Windows. The GIF is binary.
            served = served.replace(b"\r\n", b"\n")
            expected = expected.replace(b"\r\n", b"\n")
        require(served == expected, f"Public {path} bytes differ from this checkout.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Also verify the public GitHub profile.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        expected = checked_images((root / "README.md").read_text(encoding="utf-8"))
        asset_bytes = {path: (root / path).read_bytes() for path in ASSETS}
        frames, duration = gif_timing(asset_bytes[GIF])
        print(f"PASS checkout: First Stitch, {frames} frames, {duration} ms, "
              f"{len(asset_bytes[GIF])} bytes, no loop", flush=True)
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
            digest = sha256(asset_bytes[GIF]).hexdigest()
            print(f"PASS public profile: {PROFILE}, First Stitch SHA-256 {digest}")
    except (ValueError, OSError) as error:
        parser.exit(1, f"FAIL: {error}\n")


if __name__ == "__main__":
    main()
