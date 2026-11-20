#!/usr/bin/env python3
"""Dependency-free GitHub profile banner geometry and copy contract."""
import argparse
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import re
import xml.etree.ElementTree as ET

root_dir = Path(__file__).resolve().parents[1]
svg_path = root_dir / "assets" / "hero.svg"
readme_path = root_dir / "README.md"
ns = "{http://www.w3.org/2000/svg}"
raw_banner_url = (
    "https://raw.githubusercontent.com/EndeavorEverlasting/EndeavorEverlasting/main/assets/hero.svg"
)


class BannerImageParser(HTMLParser):
    """Find real image tags that refer to the committed banner asset."""

    def __init__(self):
        super().__init__()
        self.banners = []

    def handle_starttag(self, tag, attributes):
        if tag == "img":
            attrs = dict(attributes)
            src = attrs.get("src") or ""
            if src.partition("?")[0] in ("assets/hero.svg", raw_banner_url):
                self.banners.append((attrs, self.getpos(), self.get_starttag_text()))


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def verify_banner_source(readme, svg_bytes, *, sync=False):
    """Tie the rendered URL to the artwork, independent of checkout line endings."""
    parser = BannerImageParser()
    parser.feed(readme)
    assert_true(len(parser.banners) == 1, "README must embed assets/hero.svg exactly once")
    attrs, (line, column), image_tag = parser.banners[0]
    assert_true(attrs.get("width") == "100%", "Banner must fill the README width responsively")
    assert_true((attrs.get("alt") or "").strip(), "Banner must have descriptive alt text")

    # Windows checkouts can use CRLF for the same GitHub asset.
    canonical_svg = svg_bytes.replace(b"\r\n", b"\n")
    # GitHub's relative raw-file redirect can discard the content fingerprint.
    expected = f"{raw_banner_url}?v={sha256(canonical_svg).hexdigest()[:16]}"
    if attrs["src"] == expected:
        return readme
    assert_true(sync, f"Stale banner URL; expected {expected}. Run python scripts/verify_profile_banner.py --sync")

    # Consume quoted values as complete attributes, including text that looks like src=.
    tokens = re.finditer(r'''\s+([^\s=<>/]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|[^\s"'=<>]+))?''', image_tag)
    sources = [token for token in tokens if token.group(1).lower() == "src"]
    assert_true(len(sources) == 1, "Banner must have exactly one src attribute")
    source = sources[0]
    value_group = 2 if source.group(2) is not None else 3
    assert_true(source.group(value_group) is not None, "Quote the banner src attribute before running --sync")
    start = sum(map(len, readme.splitlines(keepends=True)[:line - 1])) + column
    updated = readme[:start + source.start(value_group)] + expected + readme[start + source.end(value_group):]
    return verify_banner_source(updated, svg_bytes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync", action="store_true", help="Refresh the README banner cache key")
    args = parser.parse_args()

    svg_bytes = svg_path.read_bytes()
    svg = svg_bytes.decode("utf-8")
    readme = readme_path.read_bytes().decode("utf-8")
    root = ET.fromstring(svg)
    assert_true(root.attrib.get("viewBox") == "0 0 1200 390", "Banner must retain the 1200x390 viewBox")
    assert_true(root.attrib.get("preserveAspectRatio") == "xMidYMid meet", "Aspect ratio must scale proportionally")
    assert_true(root.attrib.get("width") == "1200" and root.attrib.get("height") == "390", "Intrinsic dimensions changed")
    for svg_id in ("hourglass-badge", "flow-diagram", "needle-hub", "upper-thread", "lower-thread"):
        assert_true(root.find(f".//*[@id='{svg_id}']") is not None, f"Missing SVG element: {svg_id}")

    texts = ["".join(el.itertext()).strip() for el in root.findall(f".//{ns}text")]
    for label in ("THREADING COMPLEXITY", "INTO STABILITY", "Turning everyday friction into durable systems."):
        assert_true(texts.count(label) == 1, f"Headline/subhead missing or duplicated: {label}")
    assert_true("Make complexity repeatable" not in svg and "hold up" not in svg, "Stale brand wording")

    # GitHub README panels are often narrower than the intrinsic artwork. Responsive
    # width and the fixed viewBox preserve a 40:13 layout at, e.g., 760x247 or 600x195.
    assert_true("AgentSwitchboard" not in readme, "Retired project is still promoted")

    # Opaque teal and coral branch strokes start in the right-hand diagram zone.
    # These guards are conservative, not a claim of pixel-exact text bounds.
    for name in ("upper-thread", "lower-thread"):
        path = root.find(f".//*[@id='{name}']")
        move = re.search(r"^M\s*([0-9.]+)\s+([0-9.]+)", path.attrib.get("d", "")) if path is not None else None
        assert_true(move is not None and float(move.group(1)) >= 800, f"{name} crosses protected copy zone")

    updated = verify_banner_source(readme, svg_bytes, sync=args.sync)
    if updated != readme:
        readme_path.write_bytes(updated.encode("utf-8"))
    print("PASS: profile banner geometry, wording, responsive embed, and content-derived cache key")


if __name__ == "__main__":
    main()
