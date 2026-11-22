#!/usr/bin/env python3
"""Dependency-free GitHub profile banner geometry and copy contract."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from render_profile_motion import BANNER_EXIT_X

root_dir = Path(__file__).resolve().parents[1]
svg_path = root_dir / "assets" / "hero.svg"
readme_path = root_dir / "README.md"
svg = svg_path.read_text(encoding="utf-8")
readme = readme_path.read_text(encoding="utf-8")
root = ET.fromstring(svg)
ns = "{http://www.w3.org/2000/svg}"

def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)

assert_true(root.attrib.get("viewBox") == "0 0 1200 390", "Banner must retain the 1200x390 viewBox")
assert_true(root.attrib.get("preserveAspectRatio") == "xMidYMid meet", "Aspect ratio must scale proportionally")
assert_true(root.attrib.get("width") == "1200" and root.attrib.get("height") == "390", "Intrinsic dimensions changed")
for svg_id in ("hourglass-badge", "flow-diagram", "needle-hub", "upper-thread", "lower-thread"):
    assert_true(root.find(f".//*[@id='{svg_id}']") is not None, f"Missing SVG element: {svg_id}")

texts = ["".join(el.itertext()).strip() for el in root.findall(f".//{ns}text")]
for label in ("THREADING COMPLEXITY", "INTO STABILITY", "Turning everyday friction into durable systems."):
    assert_true(texts.count(label) == 1, f"Headline/subhead missing or duplicated: {label}")
assert_true("Make complexity repeatable" not in svg and "hold up" not in svg, "Stale brand wording")

# The existing banner and new panels share the same true quarter-circle geometry.
spiral = root.find(".//*[@id='fibonacci-spiral']")
arcs = re.findall(r"A\s+(\d+)\s+(\d+)", spiral.get("d", "") if spiral is not None else "")
assert_true(arcs == [(str(r), str(r)) for r in (13, 21, 34, 55, 89)],
            "Banner spiral must retain exact Fibonacci quarter-circle radii")
flow = root.find(".//*[@id='flow-diagram']")
assert_true(flow.get("aria-label") == "Fragmented handoffs stitched into one repeatable workflow",
            "Banner must retain the fragmented-to-repeatable workflow semantics")

# The banner output lands at the entry point of the same world-coordinate field.
handoff = root.find(".//*[@id='cosmic-web-handoff']")
assert_true(handoff is not None and handoff.get("data-exit-x") == str(BANNER_EXIT_X),
            "The banner output must align with the opening cosmic field")
feed = handoff.find(".//*[@id='cosmic-feed']")
endpoint = re.search(r"(\d+)\s+(\d+)\s*$", feed.get("d", "") if feed is not None else "")
assert_true(endpoint is not None and int(endpoint.group(1)) == BANNER_EXIT_X and
            int(endpoint.group(2)) >= 390,
            "The visible glow must reach the opening field from the bottom of the banner")

# Profile copy reflows as text alongside the banner artwork.
assert_true("# Threading complexity into stability" in readme, "Profile headline must be readable text")
assert_true("Turning everyday friction into durable systems." in readme, "Profile subhead is missing")
assert_true("AgentSwitchboard" not in readme, "Retired project is still promoted")

# Opaque teal and coral branch strokes start in the right-hand diagram zone.
# These guards are conservative, not a claim of pixel-exact text bounds.
for name in ("upper-thread", "lower-thread"):
    path = root.find(f".//*[@id='{name}']")
    move = re.search(r"^M\s*([0-9.]+)\s+([0-9.]+)", path.attrib.get("d", "")) if path is not None else None
    assert_true(move is not None and float(move.group(1)) >= 800, f"{name} crosses protected copy zone")

print("PASS: profile banner viewBox, icons, profile wording, and branch-zone guards")
