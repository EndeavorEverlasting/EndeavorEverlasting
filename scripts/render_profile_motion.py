#!/usr/bin/env python3
"""Regenerate the two profile GIFs and their matching stills with Pillow."""
from math import cos, pi, sin
from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parents[1] / "assets"
WIDTH = 640
TEAL = "#319c9e"
COPPER = "#cb754e"
TEAL_LIGHT = "#7cdbcf"
COPPER_LIGHT = "#ffb080"
ETCH = "#5b788b"
ETCH_FAINT = "#405865"
FRAMES = 48

# Consecutive cubic Béziers share an endpoint. The four exits of the opening
# illustration line up vertically with the four entrances of the interlude.
OPENING = (
    ((16, 36), (140, 32, 170, 50, 242, 87), (292, 114, 350, 105, 417, 87), (495, 65, 562, 82, 624, 82)),
    ((28, 76), (130, 72, 182, 116, 252, 116), (293, 116, 342, 86, 411, 94), (487, 103, 552, 97, 624, 97)),
    ((28, 144), (130, 148, 182, 104, 252, 104), (293, 104, 342, 134, 411, 126), (487, 117, 552, 123, 624, 123)),
    ((16, 184), (140, 188, 170, 170, 242, 133), (292, 106, 350, 115, 417, 133), (495, 155, 562, 138, 624, 138)),
)
CONTINUATION = (
    ((16, 56), (108, 56, 153, 56, 218, 69), (273, 79, 358, 72, 420, 48), (487, 21, 551, 24, 624, 24)),
    ((16, 71), (108, 71, 170, 76, 219, 82), (278, 88, 344, 88, 426, 72), (503, 57, 549, 57, 604, 57)),
    ((16, 97), (108, 97, 170, 92, 219, 86), (278, 80, 344, 80, 426, 96), (503, 111, 549, 111, 604, 111)),
    ((16, 112), (108, 112, 153, 112, 218, 99), (273, 89, 358, 96, 420, 120), (487, 147, 551, 144, 624, 144)),
)


def curve_points(curve):
    points = [curve[0]]
    x0, y0 = curve[0]
    for x1, y1, x2, y2, x3, y3 in curve[1:]:
        for step in range(1, 65):
            t = step / 64
            s = 1 - t
            points.append((
                s**3 * x0 + 3 * s**2 * t * x1 + 3 * s * t**2 * x2 + t**3 * x3,
                s**3 * y0 + 3 * s**2 * t * y1 + 3 * s * t**2 * y2 + t**3 * y3,
            ))
        x0, y0 = x3, y3
    return points


def terminal(draw, point, color, filled=False, radius=6):
    x, y = point
    draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                 fill=color if filled else None, outline=color, width=2)


def opening_engraving(draw, center):
    x, y = center
    for radius, start, stop in ((63, 202, 325), (63, 16, 145), (81, 130, 287), (81, 317, 391)):
        draw.arc((x - radius, y - radius, x + radius, y + radius), start, stop, fill=ETCH, width=1)
    # A golden spiral echoes the original First Stitch engraving.
    spiral = []
    for step in range(160):
        angle = step * 3 * pi / 159
        radius = 6 * ((1 + 5**0.5) / 2) ** (2 * angle / pi)
        spiral.append((x + radius * cos(angle - 1.2), y + radius * sin(angle - 1.2)))
    draw.line(spiral, fill=ETCH_FAINT, width=1)


def render_frame(height, curves, frame, opening):
    image = Image.new("RGBA", (WIDTH, height))
    draw = ImageDraw.Draw(image)
    y = height // 2
    center = (320, y)
    phase = frame / (FRAMES - 1)
    for offset in range(52, 600, 20):
        if abs(offset - 320) > 46:
            draw.line(((offset, y - 2), (offset, y + 2)), fill=ETCH_FAINT, width=1)
    if opening:
        opening_engraving(draw, center)

    for index, points in enumerate(curves):
        color, light = (TEAL, TEAL_LIGHT) if index < 2 else (COPPER, COPPER_LIGHT)
        draw.line(points, fill=color, width=4)
        travel = phase * 1.38 - 0.11 * (index % 2) - (0 if opening else 0.22)
        head = round(travel * (len(points) - 1))
        tail = head - 23
        pulse = points[max(0, tail):min(len(points), max(0, head))]
        if len(pulse) > 1:
            draw.line(pulse, fill=light, width=5)
        if 0 <= head < len(points):
            terminal(draw, points[head], light, filled=True, radius=4)
        terminal(draw, points[0], light if opening else color, filled=not opening,
                 radius=7 if opening else 3)
        terminal(draw, points[-1], color if opening else light, filled=opening,
                 radius=3 if opening else 7)

    # Give the hourglass its own clear negative space where strands cross.
    radius = 27 if opening else 19
    x = center[0]
    draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                 fill=(0, 0, 0, 0), outline=TEAL, width=3)
    half_width = 10 if opening else 7
    half_height = 13 if opening else 9
    for dy, color, light in ((-half_height, TEAL, TEAL_LIGHT), (half_height, COPPER, COPPER_LIGHT)):
        glow = 0.37 < phase < 0.48 if opening else 0.50 < phase < 0.61
        draw.line(((x - half_width, y + dy), (x + half_width, y + dy)), fill=color, width=3)
        draw.line(((x - half_width + 2, y + dy), (x, y), (x + half_width - 2, y + dy)),
                  fill=light if glow else color, width=3)
    return image


def render(name, height, shape, *, opening):
    curves = [curve_points(curve) for curve in shape]
    frames = [render_frame(height, curves, frame, opening) for frame in range(FRAMES)]
    durations = [70] * FRAMES
    durations[0] = 140
    durations[-1] = 360
    frames[0].save(ASSETS / f"{name}.gif", save_all=True, append_images=frames[1:],
                   duration=durations, disposal=2)
    frames[-1].save(ASSETS / f"{name}.png", optimize=True)


if __name__ == "__main__":
    render("stitch-opening", 220, OPENING, opening=True)
    render("stitch-continuation", 168, CONTINUATION, opening=False)
