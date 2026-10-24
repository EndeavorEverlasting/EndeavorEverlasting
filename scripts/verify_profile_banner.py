#!/usr/bin/env python3
"""Dependency-free GitHub profile banner geometry and copy contract."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET

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

# GitHub README panels are often narrower than the intrinsic artwork. Responsive
# width and the fixed viewBox preserve a 40:13 layout at, e.g., 760x247 or 600x195.
assert_true('src="assets/hero.svg"' in readme, "README no longer uses the authored SVG")
assert_true('width="100%"' in readme, "README image must occupy available width responsively")
assert_true("AgentSwitchboard" not in readme, "Retired project is still promoted")

# Opaque teal and coral branch strokes start in the right-hand diagram zone.
# These guards are conservative, not a claim of pixel-exact text bounds.
for name in ("upper-thread", "lower-thread"):
    path = root.find(f".//*[@id='{name}']")
    move = re.search(r"^M\s*([0-9.]+)\s+([0-9.]+)", path.attrib.get("d", "")) if path is not None else None
    assert_true(move is not None and float(move.group(1)) >= 800, f"{name} crosses protected copy zone")

print("PASS: profile banner viewBox, responsive embed, icons, wording, and branch-zone guards")
