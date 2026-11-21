#!/usr/bin/env python3
"""Regenerate the two profile GIFs and their matching stills with Pillow."""
from math import cos, pi, sin
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"
WIDTH = 640
TEAL = "#319c9e"
COPPER = "#cb754e"
TEAL_LIGHT = "#7cdbcf"
COPPER_LIGHT = "#ffb080"
ETCH = "#5b788b"
ETCH_FAINT = "#405865"
FRAMES = 42

# The horizontal positions of the four exits match the four entrances below
# the copy. Each alternating-color strand travels from the top edge downward.
HANDOFF = (287, 306, 334, 353)
OPENING_HEIGHT = 260
CONTINUATION_HEIGHT = 200
OPENING = (
    ((162, 14), (164, 60, 243, 74, 264, 106), (275, 122, 288, 132, 294, 159), (295, 190, 287, 211, HANDOFF[0], 246)),
    ((250, 14), (248, 63, 281, 87, 304, 111), (329, 130, 319, 146, 305, 170), (299, 198, 306, 215, HANDOFF[1], 246)),
    ((390, 14), (392, 63, 359, 87, 336, 111), (311, 130, 321, 146, 335, 170), (341, 198, 334, 215, HANDOFF[2], 246)),
    ((478, 14), (476, 60, 397, 74, 376, 106), (365, 122, 352, 132, 346, 159), (345, 190, 353, 211, HANDOFF[3], 246)),
)
CONTINUATION = (
    ((HANDOFF[0], 14), (287, 34, 295, 66, 284, 95), (266, 118, 240, 123, 217, 145), (201, 164, 200, 172, 200, 186)),
    ((HANDOFF[1], 14), (306, 40, 314, 59, 316, 83), (320, 107, 315, 119, 300, 142), (285, 158, 275, 165, 275, 186)),
    ((HANDOFF[2], 14), (334, 40, 326, 59, 324, 83), (320, 107, 325, 119, 340, 142), (355, 158, 365, 165, 365, 186)),
    ((HANDOFF[3], 14), (353, 34, 345, 66, 356, 95), (374, 118, 400, 123, 423, 145), (439, 164, 440, 172, 440, 186)),
)


def verify_thread_direction(opening, continuation):
    for height, shape in ((OPENING_HEIGHT, opening), (CONTINUATION_HEIGHT, continuation)):
        for start, *segments in shape:
            vertical = [start[1], *(point for segment in segments for point in segment[1::2])]
            if vertical != sorted(vertical) or vertical[0] > 16 or vertical[-1] < height - 16:
                raise ValueError("Each profile thread must run from the top to the bottom.")
    if tuple(curve[-1][-2] for curve in opening) != tuple(curve[0][0] for curve in continuation):
        raise ValueError("Opening and continuation thread endpoints must align across the copy.")


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
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (WIDTH, height))
    draw = ImageDraw.Draw(image)
    y = height // 2
    center = (320, y)
    phase = frame / (FRAMES - 1)
    for offset in range(24, height - 20, 13):
        if abs(offset - y) > 32:
            draw.line(((317, offset), (323, offset)), fill=ETCH_FAINT, width=1)
    if opening:
        opening_engraving(draw, center)

    for index, points in enumerate(curves):
        color, light = (TEAL, TEAL_LIGHT) if index % 2 == 0 else (COPPER, COPPER_LIGHT)
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
    durations = [80] * FRAMES
    durations[0] = 140
    durations[-1] = 360
    frames[0].save(ASSETS / f"{name}.gif", save_all=True, append_images=frames[1:],
                   duration=durations, disposal=2)
    frames[-1].save(ASSETS / f"{name}.png", optimize=True)


if __name__ == "__main__":
    verify_thread_direction(OPENING, CONTINUATION)
    render("stitch-descent", OPENING_HEIGHT, OPENING, opening=True)
    render("stitch-resume", CONTINUATION_HEIGHT, CONTINUATION, opening=False)
