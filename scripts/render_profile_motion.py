#!/usr/bin/env python3
"""Render the profile artwork described in assets/profile-artwork.md."""
import argparse
from dataclasses import dataclass
from math import atan2, cos, pi, sin
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"
WIDTH = 768
OPENING_HEIGHT = 384
CONTINUATION_HEIGHT = 304
HANDOFF = (340, 369, 399, 428)
TEAL = (31, 157, 169)
AMBER = (194, 103, 50)
SCALE = 2
FRAMES = 28
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
     (119, 228, 98, 253, 94, 291)),
    ((HANDOFF[1], 13), (369, 61, 356, 119, 344, 157), (333, 195, 281, 208, 265, 236),
     (255, 254, 250, 270, 250, 291)),
    ((HANDOFF[2], 13), (399, 67, 400, 115, 422, 154), (446, 193, 480, 207, 499, 237),
     (509, 254, 519, 268, 519, 291)),
    ((HANDOFF[3], 13), (433, 69, 418, 103, 470, 145), (519, 185, 594, 190, 634, 222),
     (659, 241, 675, 262, 675, 291)),
)


def verify_thread_direction(opening, continuation):
    for height, shape in ((OPENING_HEIGHT, opening), (CONTINUATION_HEIGHT, continuation)):
        for start, *segments in shape:
            vertical = [start[1], *(point for segment in segments for point in segment[1::2])]
            if vertical != sorted(vertical) or vertical[0] > 16 or vertical[-1] < height - 16:
                raise ValueError("Each profile thread must run from the top to the bottom.")
    if tuple(curve[-1][-2] for curve in opening) != tuple(curve[0][0] for curve in continuation):
        raise ValueError("Opening and continuation thread endpoints must align across the copy.")


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
    return sample_curve(start, ((x + dx*22, y + dy*22, x + offset*0.72, y + length*0.45,
                                 x + offset, y + length),))


def dendrites(curves, height, opening):
    branches = []
    for index, curve in enumerate(curves):
        points = sample_curve(curve[0], curve[1:])
        color = TEAL if index % 2 == 0 else AMBER
        side = -1 if index < 2 else 1
        # Outer silhouettes fork first. Smaller offshoots attach to their parent
        # immediately below the junction, with continuous tangent and radius.
        positions = (
            ((29, 65, 104), (40, 76, 111), (35, 78, 130), (26, 57, 93)) if opening else
            ((70, 97, 136), (91, 120, 151), (83, 106, 133), (64, 103, 144))
        )[index]
        for branch_index, start in enumerate(positions):
            reach = side * (121 - 18*branch_index + (index % 2)*15)
            length = 72 - 11*branch_index + (index % 3)*8
            fork_points = fork(points[start], points[start-1], reach, length)
            if any(x < 17 or x > WIDTH - 17 or y > height - 12 for x, y in fork_points):
                reach *= 0.57
                fork_points = fork(points[start], points[start-1], reach, length * 0.74)
            fork_radii = taper(fork_points, 3.8 - 0.42*branch_index, 0.65)
            depth = 1.1 + index*0.42 - branch_index*1.35
            branches.append(Branch(fork_points, fork_radii, color, depth))
            for attach, turn in ((19 + index + branch_index*2, 1), (41 - index*2, -1)):
                twig = fork(fork_points[attach], fork_points[attach-1],
                            turn*side*(36 - branch_index*3), 27 + 5*(turn == 1))
                branches.append(Branch(twig, taper(twig, fork_radii[attach]*0.68, 0.38),
                                       color, depth - 0.8))
        # Deep, dim filaments carry the same curvature behind the primary trunks.
        for i in (0, 1):
            start = 18 + i*43 if opening else 60 + i*34
            dim = tuple(round(channel*0.62) for channel in color)
            x, y = points[start]
            endpoint_x = max(24, min(WIDTH - 24, x + side*(165 - i*41)))
            reach = endpoint_x - x
            points_back = fork(points[start], points[start-1], reach, min(109 - i*15, height-y-14))
            branches.append(Branch(points_back, taper(points_back, 3.4, 0.52), dim, -12 - i*4))
        # These four handoff fibers have matching tip widths and color.
        radii = tuple(3.25 + (4.8 if opening else 4.0) * sin(pi*i/(len(points)-1))**0.8
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

    def centerpiece(self, opening):
        np = self.np
        cx, cy = WIDTH/2, self.height*(0.51 if opening else 0.49)
        scale = 1 if opening else 0.62
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
        if opening:
            # An engraved Fibonacci spiral sits behind the focal assembly.
            spiral = []
            for step in range(180):
                theta = step * 1.84*pi/179
                radius = 75 / (((1+5**0.5)/2)**(2*theta/pi))
                spiral.append((cx + radius*cos(theta-1.95), cy + radius*sin(theta-1.95)))
            self.sweep(Branch(tuple(spiral), (0.95,)*len(spiral), (130, 77, 34), -3))

    def frame(self, phase=None):
        from PIL import Image

        np = self.np
        light = np.zeros(self.depth.shape, dtype=np.float32)
        if phase is not None:
            for index in range(4):
                positions = self.signal == index
                head = (phase*1.21 - index%2*0.075 - 0.08) * self.height
                distance = head - self.y
                falloff = np.exp(-((distance-6)/14)**2)
                light[positions] = np.broadcast_to(falloff, light.shape)[positions]
        boost = light * self.visibility
        rgb = np.clip(self.rgb + boost[..., None]*[83, 101, 99], 0, 255).astype(np.uint8)
        return Image.fromarray(rgb).resize((WIDTH, self.height), Image.Resampling.LANCZOS)


# Ambient strength, key strength, reflection strength and lobe exponent.
BRUSHED_ALLOY = (0.22, 0.89, 0.72, 19)


def build_scene(height, geometry, opening, treatment):
    scene = Scene(height, treatment)
    for branch in dendrites(geometry, height, opening):
        scene.sweep(branch)
    scene.centerpiece(opening)
    return scene


def render(output, name, height, geometry, opening):
    from PIL import Image

    scene = build_scene(height, geometry, opening, BRUSHED_ALLOY)
    still = scene.frame()
    still.save(output / f"{name}.png", optimize=True)
    frames = [scene.frame(index/(FRAMES-1)) for index in range(FRAMES)]
    frames[-1] = still

    # A single palette keeps the still background byte-stable between frames.
    # Let the encoder delta-compress just the traveling light. Lanczos provides
    # stable silhouettes before quantization.
    contact = Image.new("RGB", (WIDTH, height*5))
    for index, frame in enumerate((still, frames[6], frames[12], frames[19], frames[25])):
        contact.paste(frame, (0, index*height))
    palette = contact.quantize(colors=144, method=Image.Quantize.MEDIANCUT)
    encoded = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    durations = [110]*FRAMES
    durations[0], durations[-1] = 140, 360
    encoded[0].save(output / f"{name}.gif", save_all=True, append_images=encoded[1:],
                    duration=durations, disposal=1, optimize=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ASSETS)
    args = parser.parse_args()
    verify_thread_direction(OPENING, CONTINUATION)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, height, geometry, opening in (
        ("stitch-descent", OPENING_HEIGHT, OPENING, True),
        ("stitch-resume", CONTINUATION_HEIGHT, CONTINUATION, False),
    ):
        render(args.output, name, height, geometry, opening)


if __name__ == "__main__":
    main()
