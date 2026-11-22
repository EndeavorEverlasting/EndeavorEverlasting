#!/usr/bin/env python3
"""Render the profile artwork described in assets/profile-artwork.md."""
import argparse
from dataclasses import dataclass
from math import atan2, cos, pi, sin, tau
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"
WIDTH = 768
OPENING_HEIGHT = 384
CONTINUATION_HEIGHT = 304
PULSE_HEIGHT = 233
FIBONACCI = (1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233)
RING_RADII = FIBONACCI[-6:]
SPIRAL_RADII = FIBONACCI[5:11]
HANDOFF = tuple(WIDTH//2 + spacing for spacing in (-55, -21, 21, 55))
ENDPOINTS = (94, 250, 519, 675)
TEAL = (31, 157, 169)
AMBER = (194, 103, 50)
SCALE = 2
FRAMES = FIBONACCI[6]
FRAME_MS = FIBONACCI[5]*10
WAVE_PERIOD = 2*FIBONACCI[-2]
WAVE_WIDTH = FIBONACCI[5]
OPENING = (
    ((92, 13), (90, 69, 162, 75, 221, 118), (285, 165, 314, 206, 325, 264),
     (335, 308, 331, 348, HANDOFF[0], 371)),
    ((205, 13), (201, 65, 212, 99, 278, 144), (357, 195, 362, 221, 361, 281),
     (360, 322, 369, 350, HANDOFF[1], 371)),
    ((553, 13), (546, 67, 512, 105, 468, 133), (398, 179, 405, 222, 404, 280),
     (407, 322, 399, 352, HANDOFF[2], 371)),
    ((677, 13), (678, 65, 616, 89, 565, 113), (495, 145, 435, 203, 438, 259),
     (440, 304, 429, 355, HANDOFF[3], 371)),
)
CONTINUATION = (
    ((HANDOFF[0], 13), (334, 60, 345, 110, 297, 144), (261, 168, 208, 174, 149, 210),
     (119, 228, 98, 253, ENDPOINTS[0], 291)),
    ((HANDOFF[1], 13), (369, 61, 356, 119, 344, 157), (333, 195, 281, 208, 265, 236),
     (255, 254, 250, 270, ENDPOINTS[1], 291)),
    ((HANDOFF[2], 13), (399, 67, 400, 115, 422, 154), (446, 193, 480, 207, 499, 237),
     (509, 254, 519, 268, ENDPOINTS[2], 291)),
    ((HANDOFF[3], 13), (433, 69, 418, 103, 470, 145), (519, 185, 594, 190, 634, 222),
     (659, 241, 675, 262, ENDPOINTS[3], 291)),
)


# The bottom receives the spread endpoints and passes them behind the same
# durational centerpiece. They re-emerge in the Fibonacci handoff spacing.
PULSE = (
    ((ENDPOINTS[0], 13), (114, 65, 207, 68, 275, 90), (328, 112, 327, 163, HANDOFF[0], 220)),
    ((ENDPOINTS[1], 13), (261, 62, 329, 70, 346, 103), (366, 132, 353, 168, HANDOFF[1], 220)),
    ((ENDPOINTS[2], 13), (515, 60, 442, 69, 421, 104), (402, 135, 415, 172, HANDOFF[2], 220)),
    ((ENDPOINTS[3], 13), (652, 60, 551, 64, 493, 90), (441, 113, 441, 161, HANDOFF[3], 220)),
)


def verify_thread_direction(opening, continuation):
    for height, shape in ((OPENING_HEIGHT, opening), (CONTINUATION_HEIGHT, continuation)):
        for start, *segments in shape:
            vertical = [start[1], *(point for segment in segments for point in segment[1::2])]
            if vertical != sorted(vertical) or vertical[0] > 16 or vertical[-1] < height - 16:
                raise ValueError("Each profile thread must run from the top to the bottom.")
    if tuple(curve[-1][-2] for curve in opening) != tuple(curve[0][0] for curve in continuation):
        raise ValueError("Opening and continuation thread endpoints must align across the copy.")
    if tuple(curve[-1][-2] for curve in continuation) != tuple(curve[0][0] for curve in PULSE):
        raise ValueError("The footer must receive the continuation endpoints.")


def fibonacci_spiral(start, rotation):
    """Walk tangent quarter circles whose radii are successive Fibonacci numbers."""
    x, y = start
    points = [(x, y)]
    for index, radius in enumerate(SPIRAL_RADII):
        angle = rotation + index*pi/2
        center_x, center_y = x-radius*cos(angle), y-radius*sin(angle)
        for step in range(1, 65):
            theta = angle + step*pi/128
            points.append((center_x + radius*cos(theta), center_y + radius*sin(theta)))
        x, y = points[-1]
    return tuple(points)


@dataclass(frozen=True)
class Branch:
    points: tuple
    radii: tuple
    color: tuple
    depth: float
    signal: int | None = None


def sample_curve(start, segments):
    points = [start]
    x, y = start
    for x1, y1, x2, y2, x3, y3 in segments:
        for step in range(1, 65):
            t = step / 64
            s = 1 - t
            points.append((s**3*x + 3*s*s*t*x1 + 3*s*t*t*x2 + t**3*x3,
                           s**3*y + 3*s*s*t*y1 + 3*s*t*t*y2 + t**3*y3))
        x, y = x3, y3
    return tuple(points)


def taper(points, root, tip):
    last = len(points) - 1
    return tuple(tip + (root - tip) * (1 - i / last)**0.72 for i in range(len(points)))


def fork(start, previous, offset, length):
    x, y = start
    heading = atan2(y - previous[1], x - previous[0])
    dx, dy = cos(heading), sin(heading)
    return sample_curve(start, ((x + dx*22, y + min(dy*21, length*0.65), x + offset*0.72, y + length*0.45,
                                 x + offset, y + length),))


def dendrites(curves, height, opening):
    branches = []
    for index, curve in enumerate(curves):
        points = sample_curve(curve[0], curve[1:])
        color = TEAL if index % 2 == 0 else AMBER
        side = -1 if index < 2 else 1
        # Each trunk carries the same branch orders in different positions.
        # Junction cadence uses Fibonacci offsets in the subdivided curves.
        positions = (21, 34, 55, 89, 144)
        shift = (0, 13, 8, -5)[index] + (0 if opening else 34)
        for order, (attach, reach, length) in enumerate(zip(
                positions, (55, 89, 144, 89, 55), (55, 55, 89, 55, 34))):
            start = attach + shift
            if start >= len(points):
                continue
            x, y = points[start]
            target_x = max(17, min(WIDTH - 17, x + side*reach))
            length = min(length, height-y-21)
            if length < 21:
                continue
            fork_points = fork(points[start], points[start-1], target_x-x, length)
            fork_radii = taper(fork_points, (5, 5, 5, 3, 3)[order], 0.55)
            depth = 1.1 + index*0.42 - order*0.92
            branches.append(Branch(fork_points, fork_radii, color, depth))
            for attach, turn, reach in ((21, 1, 34), (34, -1, 21)):
                x, y = fork_points[attach]
                if height-y < 34:
                    continue
                twig = fork(fork_points[attach], fork_points[attach-1],
                            max(12, min(WIDTH-12, x + turn*side*reach))-x,
                            min(21 + 13*(turn == 1), height-y-6))
                branches.append(Branch(twig, taper(twig, fork_radii[attach]*0.68, 0.34),
                                       color, depth - 0.8))
        # Recessed filaments follow two larger orders at lower luminance.
        for i, reach in enumerate((233, 144)):
            start = (13, 55)[i] if opening else (55, 89)[i]
            dim = tuple(round(channel*0.62) for channel in color)
            x, y = points[start]
            endpoint_x = max(24, min(WIDTH - 24, x + side*reach))
            points_back = fork(points[start], points[start-1],
                               endpoint_x-x, min((144, 89)[i], height-y-21))
            branches.append(Branch(points_back, taper(points_back, 3, 0.52), dim, -13 - i*5))
        # These four handoff fibers have matching tip widths and color.
        radii = tuple(3 + (5 if opening else 3) * sin(pi*i/(len(points)-1))**0.8
                      for i in range(len(points)))
        branches.append(Branch(points, radii, color, 6 + index*1.35, index))
    return branches


class Scene:
    def __init__(self, height, treatment):
        import numpy as np

        self.np = np
        self.height = height
        self.treatment = treatment
        shape = (height*SCALE, WIDTH*SCALE)
        y, x = np.ogrid[:shape[0], :shape[1]]
        self.x = x / SCALE
        self.y = y / SCALE
        fog = np.exp(-((self.x-384)/286)**2 - ((self.y-height*0.46)/(height*0.68))**2)
        cool = np.exp(-((self.x-245)/185)**2 - ((self.y-height*0.46)/(height*0.43))**2)
        warm = np.exp(-((self.x-530)/186)**2 - ((self.y-height*0.42)/(height*0.38))**2)
        self.background = np.array([13., 17., 23.]) + (
            fog[..., None]*[1.3, 3.5, 6.] +
            cool[..., None]*[0.0, 5., 8.] +
            warm[..., None]*[7., 1.8, 0.])
        self.rgb = self.background.copy()
        self.depth = np.full(shape, -np.inf, dtype=np.float32)
        self.signal = np.full(shape, -1, dtype=np.int8)
        self.visibility = np.zeros(shape, dtype=np.float32)

    def shade(self, x, y, normal_x, normal_y, normal_z, mask, z, branch):
        np = self.np
        ix = (y, x)
        active = mask & (z >= self.depth[ix])
        if not active.any():
            return
        nx, ny, nz = normal_x[active], normal_y[active], normal_z[active]
        diffuse = np.maximum(0, -0.46*nx - 0.64*ny + 0.61*nz)
        reflection = np.maximum(0, -0.32*nx - 0.34*ny + 0.885*nz)
        rim = np.maximum(0, 0.75*nx + 0.25*ny + 0.44*nz)
        ambient, key, gloss, roughness = self.treatment
        color = np.array(branch.color)
        strength = ambient + key*diffuse + 0.22*rim
        highlight = ((reflection**roughness)*gloss + (reflection**8)*0.13)
        lit = color * strength[:, None] + highlight[:, None]*[177, 194, 191]
        mist = min(1, max(0.21, (branch.depth + 23)/26))
        self.rgb[ix][active] = self.background[ix][active]*(1-mist) + lit*mist
        self.depth[ix][active] = z[active]
        self.signal[ix][active] = -1 if branch.signal is None else branch.signal
        self.visibility[ix][active] = (0.35 + 0.65*nz)

    def sweep(self, branch):
        """Project the visible surface of a tapered swept sphere into the depth buffer."""
        np = self.np
        for (x0, y0), (x1, y1), r0, r1 in zip(
                branch.points, branch.points[1:], branch.radii, branch.radii[1:]):
            r = max(r0, r1)
            ys = slice(max(0, int((min(y0, y1)-r)*SCALE)),
                       min(self.height*SCALE, int((max(y0, y1)+r)*SCALE)+1))
            xs = slice(max(0, int((min(x0, x1)-r)*SCALE)),
                       min(WIDTH*SCALE, int((max(x0, x1)+r)*SCALE)+1))
            if ys.stop <= ys.start or xs.stop <= xs.start:
                continue
            px, py = self.x[:, xs]-x0, self.y[ys, :]-y0
            dx, dy = x1-x0, y1-y0
            t = np.clip((px*dx + py*dy) / max(dx*dx+dy*dy, 1e-8), 0, 1)
            radius = r0 + t*(r1-r0)
            nx, ny = (px-t*dx)/radius, (py-t*dy)/radius
            square = nx*nx + ny*ny
            nz = np.sqrt(np.maximum(0, 1-square))
            self.shade(xs, ys, nx, ny, nz, square < 1, branch.depth+radius*nz, branch)

    def inlay(self, center, is_footer):
        """Cut Fibonacci annuli into the substrate and seat the spiral between them."""
        np = self.np
        cx, cy = center
        x, y = self.x-cx, (self.y-cy) / 0.618
        radius, angle = np.hypot(x, y), np.arctan2(y, x)
        key = (np.cos(angle+2.35)*0.5+0.5)**2
        edge_tint = np.where((x < 0)[..., None], [13, 48, 54], [59, 35, 16])
        for ring in RING_RADII:
            width = 1.35 if ring < 144 else 1.9
            lip = np.exp(-((radius-ring)/width)**2)
            cut = np.exp(-((radius-ring+2.9)/(width*1.23))**2)
            self.rgb += lip[..., None] * (0.33+0.62*key[..., None]) * edge_tint
            self.rgb -= cut[..., None] * np.array([4.0, 7.0, 9.0])
        if not is_footer:
            for rotation, tint in ((0.42, (102, 68, 37)), (pi+0.42, (28, 81, 90))):
                spiral = fibonacci_spiral(center, rotation)
                # Set these below the branches so their occlusion reads as depth.
                self.sweep(Branch(spiral, taper(spiral, 1.05, 1.65), tint, -8))

    def stitch_bridge(self, center):
        """The confluence seats a tapered needle and three stitches between the rails."""
        x, y = center
        for step, span in zip((13, 34, 55), (89, 89, 55)):
            start = (x-span/2, y+step+8)
            finish = (x+span/2, y+step-8)
            cord = sample_curve(start, ((x-21, y+step+21, x+21, y+step-21, *finish),))
            self.sweep(Branch(cord, taper(cord, 1.65, 0.65), (115, 77, 52), 18))
        needle = sample_curve((x-34, y+55), ((x-13, y+51, x+21, y+34, x+55, y+21),))
        self.sweep(Branch(needle, taper(needle, 3, 0.3), (172, 135, 83), 20))

    def centerpiece(self, center, scale):
        np = self.np
        cx, cy = center
        # A concentric machined surround casts a soft contact shadow over the
        # fibers. Its recessed glass face reflects the two nearby materials.
        x, y = (self.x-cx)/scale, (self.y-cy)/scale
        radius = np.hypot(x, y)
        angle = np.arctan2(y, x)
        shade = 1 - 0.68*np.exp(-(np.maximum(radius-38, 0)/8)**2)
        self.rgb *= shade[..., None]
        inside = radius < 46
        face = np.clip(0.55 - 0.007*(x+y), 0, 1)
        reflected = (np.cos(angle+2.25)*0.5+0.5)**2
        metal = np.array([28., 35., 41.]) + reflected[..., None]*[85, 94, 101]
        ribbon = (radius > 41.7) & (radius < 44.2)
        metal += np.where((x < 0), 1., 0.)[..., None]*reflected[..., None]*[0, 20, 23]
        metal += np.where((x > 0), 1., 0.)[..., None]*(1-reflected[..., None])*[76, 34, 8]
        metal[ribbon] *= 1.38
        glass = np.array([8., 16., 23.]) + face[..., None]*[15, 22, 29]
        glass += np.exp(-((x+y+24)/13)**2)[..., None]*[13, 24, 31]
        stack = np.where((radius < 38.7)[..., None], glass, metal)
        stack[(radius >= 38.7) & (radius < 40.8)] *= 0.32
        self.rgb[inside] = stack[inside]
        self.depth[inside] = 45
        self.signal[inside] = -1
        self.visibility[inside] = 0
        # The two recessed glass bulbs have a transmitted light gradient and
        # a layer of amber material gathering in the lower chamber.
        bulb_width = 2.2 + 13.3*np.sin(np.minimum(np.abs(y)/19, 1.0)*pi/2)**1.42
        bulb = (np.abs(y) < 19) & (np.abs(x) <= bulb_width)
        light_through_glass = np.sqrt(np.maximum(0, 1 - (x/bulb_width)**2))
        upper = np.where(y < 0, 1., 0.)
        glass_tint = upper[..., None]*[5, 40, 49] + (1-upper[..., None])*[32, 18, 8]
        contents = (y > 17.5 - 8.5*np.exp(-(x/8)**2)) & bulb & (y > 0)
        self.rgb[bulb] += (light_through_glass[..., None]*glass_tint)[bulb]
        self.rgb[contents] += np.array([68, 36, 13])
        grain = (y > 0) & (y < 15) & (np.abs(x) < 0.55)
        self.rgb[grain] += np.array([94, 53, 18])
        # Curved glass sides and a narrow waist share the chamber silhouette.
        for sign, color in ((-1, TEAL), (1, AMBER)):
            near = (cx, cy)
            left = (cx-15.5*scale, cy+sign*19*scale)
            right = (cx+15.5*scale, cy+sign*19*scale)
            for point, turn in ((left, -1), (right, 1)):
                route = sample_curve(near, ((cx+turn*2*scale, cy+sign*7*scale,
                                             point[0], cy+sign*9*scale, *point),))
                self.sweep(Branch(route, (1.75*scale,)*len(route), color, 46))
            rail = tuple((left[0]+i*(right[0]-left[0])/24, left[1]) for i in range(25))
            self.sweep(Branch(rail, (2.15*scale,)*len(rail), color, 46))

    def frame(self, phase=None):
        from PIL import Image

        np = self.np
        light = np.zeros(self.depth.shape, dtype=np.float32)
        if phase is not None and self.height == PULSE_HEIGHT:
            x, y = self.x-WIDTH/2, self.y-self.height/2
            radius = np.hypot(x, y/0.618)
            breathing = (1 + cos(tau*phase))/2
            bezel_light = (1 + cos(tau*(phase-1/13)))/2
            rings = np.exp(-((radius-55)/1.65)**2) * bezel_light * (self.depth < 0)
            core = np.exp(-((x/21)**2 + (y/13)**2))
            boost = rings*0.27 + core*1.36*breathing
        elif phase is not None:
            offset = 0 if self.height == OPENING_HEIGHT else FIBONACCI[-2]
            for index in range(4):
                positions = self.signal == index
                head = phase*WAVE_PERIOD - index*FIBONACCI[4]
                distance = (head-self.y-offset+WAVE_PERIOD/2) % WAVE_PERIOD-WAVE_PERIOD/2
                falloff = np.exp(-(distance/WAVE_WIDTH)**2)
                light[positions] = np.broadcast_to(falloff, light.shape)[positions]
            boost = light * self.visibility
        else:
            boost = light
        rgb = np.clip(self.rgb + boost[..., None]*[63, 78, 75], 0, 255).astype(np.uint8)
        return Image.fromarray(rgb).resize((WIDTH, self.height), Image.Resampling.LANCZOS)


# Ambient strength, key strength, reflection strength and lobe exponent.
BRUSHED_ALLOY = (0.22, 0.89, 0.72, 19)


def build_scene(height, geometry, opening, treatment):
    scene = Scene(height, treatment)
    footer = height == PULSE_HEIGHT
    center = WIDTH/2, height/2
    scene.inlay(center, footer)
    for branch in dendrites(geometry, height, opening or footer):
        if footer:
            branch = Branch(branch.points, branch.radii,
                            tuple(round(channel*0.73) for channel in branch.color),
                            branch.depth, branch.signal)
        scene.sweep(branch)
    if opening:
        scene.stitch_bridge(center)
    scene.centerpiece(center, 1 if opening or footer else 0.73)
    return scene


def render(output, name, height, geometry, opening):
    from PIL import Image

    scene = build_scene(height, geometry, opening, BRUSHED_ALLOY)
    still = scene.frame()
    still.save(output / f"{name}.png", optimize=True)
    frames = [scene.frame(index/FRAMES) for index in range(FRAMES)]

    # A single palette keeps the still background byte-stable between frames.
    # Let the encoder delta-compress just the traveling light. Lanczos provides
    # stable silhouettes before quantization.
    contact = Image.new("RGB", (WIDTH, height*5))
    for index, frame in enumerate((still, frames[0], frames[5], frames[10], frames[15])):
        contact.paste(frame, (0, index*height))
    palette = contact.quantize(colors=96, method=Image.Quantize.MEDIANCUT)
    encoded = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    encoded[0].save(output / f"{name}.gif", save_all=True, append_images=encoded[1:],
                    duration=FRAME_MS, loop=0, disposal=1, optimize=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ASSETS)
    args = parser.parse_args()
    verify_thread_direction(OPENING, CONTINUATION)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, height, geometry, opening in (
        ("stitch-descent", OPENING_HEIGHT, OPENING, True),
        ("stitch-resume", CONTINUATION_HEIGHT, CONTINUATION, False),
        ("stitch-pulse", PULSE_HEIGHT, PULSE, False),
    ):
        render(args.output, name, height, geometry, opening)


if __name__ == "__main__":
    main()
