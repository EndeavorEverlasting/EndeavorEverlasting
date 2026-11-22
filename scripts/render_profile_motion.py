#!/usr/bin/env python3
"""Render one cosmic-web density field in three slices for the profile README."""
import argparse
from dataclasses import dataclass
from math import pi, tau
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"
WIDTH = 768
DELIVERY_WIDTH = 704
FIBONACCI = (1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233)
FRAMES = FIBONACCI[6]
FRAME_MS = FIBONACCI[5] * 10
NEXUS_FRAMES = FIBONACCI[7]
NEXUS_FRAME_MS = FIBONACCI[4] * 10
NEXUS_SIZE = (704, 207)
BACKGROUND = (13, 17, 23)
BANNER_EXIT_X = 958
BANNER_WIDTH = 1200
ENTRY_X = round(WIDTH * BANNER_EXIT_X / BANNER_WIDTH)
PANELS = (("stitch-descent", 336), ("stitch-resume", 280), ("stitch-pulse", 216))
HEIGHT = sum(height for _, height in PANELS)
FOOTER_FORK = (WIDTH // 2, 716)
FOOTER_BRANCHES = (
    (FOOTER_FORK, (325, 748), (248, 784), (204, 822), (196, 856)),
    (FOOTER_FORK, (449, 741), (514, 778), (561, 817), (579, 854)),
)
# The flow route is a chain of clouds from the banner output through both
# picture boundaries and into the two footer branches. No route is painted as a stroke.
FLOW = (
    (ENTRY_X, -25), (593, 34), (511, 96), (466, 143), (376, 186), (322, 253),
    (279, 311), (265, 351), (302, 394), (395, 439), (488, 493), (521, 548),
    (502, 592), (482, 640), (441, 675), FOOTER_FORK,
)
# Knots and adjacent lanes leave asymmetric voids of different sizes.
NEBULAE = (
    (344, -28), (204, 40), (80, 90), (124, 183), (55, 263), (161, 303),
    (125, 393), (31, 468), (171, 503), (93, 582), (215, 640), (125, 724),
    (62, 788), (239, 832), (301, 697), (219, 437), (230, 173),
    (683, 82), (739, 153), (602, 199), (698, 259), (594, 324), (704, 375),
    (626, 458), (734, 504), (647, 555), (734, 632), (616, 671), (704, 728),
    (573, 753), (697, 804), (555, 850), (374, 92), (518, 269), (455, 350),
    (350, 524), (374, 602), (273, 756), (531, 799),
)

# The orange field runs beside the teal signal and joins it at shared knots.
WARM_ROUTES = (
    ((675, -29), (668, 43), (618, 103), (602, 178), (523, 232), (431, 269),
     (377, 309), (350, 355), (383, 399), (445, 429), (548, 465), (606, 521),
     (585, 568), (544, 610), (523, 647), (552, 696), (611, 728), (640, 775),
     (609, 818), (599, 854)),
    ((80, 90), (154, 145), (124, 183), (171, 233), (229, 257), (289, 273), (377, 309)),
    ((126, 393), (168, 456), (171, 503), (249, 548), (322, 567), (374, 602)),
    ((374, 602), (307, 621), (215, 640), (153, 682), (125, 724), (166, 776), (204, 822)),
)


@dataclass(frozen=True)
class Filament:
    start: tuple[int, int]
    end: tuple[int, int]
    flow: bool = False


def topology():
    """Connect each neighboring cloud into an interlaced volumetric field."""
    routes = (FLOW, *FOOTER_BRANCHES)
    strands = [Filament(a, b, True) for route in routes for a, b in zip(route, route[1:])]
    nodes = tuple(dict.fromkeys(node for route in routes for node in route)) + NEBULAE
    seen = {frozenset((edge.start, edge.end)) for edge in strands}
    for start in NEBULAE:
        adjacent = sorted((point for point in nodes if point != start),
                          key=lambda point: (point[0]-start[0])**2 + (point[1]-start[1])**2)
        for end in adjacent[:3]:
            pair = frozenset((start, end))
            if pair not in seen:
                strands.append(Filament(start, end))
                seen.add(pair)
    return strands


def filament_path(np, strand, t, shift):
    x0, y0 = strand.start
    x1, y1 = strand.end
    # One broad bend with small turbulent variation. Both vanish into each cloud.
    turn = np.sin(pi*t) * shift + np.sin(tau*t) * shift * 0.17
    distance = max(1, ((x1-x0)**2 + (y1-y0)**2)**0.5)
    return x0+(x1-x0)*t-turn*(y1-y0)/distance, y0+(y1-y0)*t+turn*(x1-x0)/distance


def deposit(np, channel, x, y, weights):
    """Scatter energy bilinearly without clumping onto single raster cells."""
    # Include overscan knots so the profile crops lie inside the same cloud.
    y = y + FIBONACCI[-4]
    valid = (x >= 0) & (x < WIDTH-1) & (y >= 0) & (y < channel.shape[0]-1)
    x, y, weights = x[valid], y[valid], weights[valid]
    ix, iy = x.astype(int), y.astype(int)
    dx, dy = x-ix, y-iy
    for offset_x, wx in ((0, 1-dx), (1, dx)):
        for offset_y, wy in ((0, 1-dy), (1, dy)):
            np.add.at(channel, (iy+offset_y, ix+offset_x), weights*wx*wy)


def render_warm_field(shape):
    """Build orange dust, filaments and knots at three depths."""
    import numpy as np
    from scipy.ndimage import gaussian_filter

    rng = np.random.default_rng(4297)
    dust = np.zeros(shape, dtype=np.float32)
    wisps = np.zeros_like(dust)
    knots = np.zeros_like(dust)
    for path in WARM_ROUTES:
        for start, end in zip(path, path[1:]):
            t = rng.beta(0.95, 0.95, 290)
            bend = rng.uniform(-28, 28)
            x, y = filament_path(np, Filament(start, end), t, bend)
            grain = rng.lognormal(-0.37, 0.75, t.size)
            scatter = 9 + 13*np.sin(pi*t)
            deposit(np, dust, x + rng.normal(0, scatter), y + rng.normal(0, scatter), grain)
            deposit(np, wisps, x + rng.normal(0, 5, t.size), y + rng.normal(0, 4, t.size), grain*rng.uniform(0.48, 1.3, t.size))
        for index, (x, y) in enumerate(path[1:-1]):
            count = 82 if index % 3 == 0 else 36
            dx, dy = rng.normal(0, 5.4, (2, count))
            deposit(np, knots, x+dx, y+dy, rng.lognormal(-0.15, 0.78, count))

    veil = gaussian_filter(dust, (13, 21)) * 4.4
    filaments = gaussian_filter(wisps + dust*0.32, (3.1, 4.7)) * 2.3
    cluster = gaussian_filter(knots, (2.8, 4)) * 2
    sparks = gaussian_filter(wisps + knots*0.31, 1.1) * 0.61
    return (veil[..., None]*[0.84, 0.37, 0.14] +
            filaments[..., None]*[1.21, 0.53, 0.19] +
            cluster[..., None]*[1.23, 0.71, 0.35] +
            sparks[..., None]*[1.39, 0.88, 0.47])


def render_field():
    import numpy as np
    from scipy.ndimage import gaussian_filter

    rng = np.random.default_rng(8113)
    margin = FIBONACCI[-4]
    shape = (HEIGHT + 2*margin, WIDTH)
    dust = np.zeros(shape, dtype=np.float32)
    gas = np.zeros_like(dust)
    route = np.zeros_like(dust)
    cores = np.zeros_like(dust)
    background_dust = np.zeros_like(dust)
    for edge in topology():
        shift = rng.uniform(-34, 34)
        t = rng.beta(0.83, 0.83, 450 if edge.flow else 270)
        x, y = filament_path(np, edge, t, shift)
        dispersion = 5 + 13*np.sin(pi*t)**1.4
        density = (1.3 if edge.flow else 0.67) * rng.lognormal(-0.17, 0.85, t.size)
        deposit(np, gas, x+rng.normal(0, dispersion), y+rng.normal(0, dispersion), density)
        detail = rng.normal(0, 3.7 + 5*np.sin(pi*t), (2, t.size))
        deposit(np, dust, x+detail[0], y+detail[1], density*rng.uniform(0.35, 1.4, t.size))
        # Recessed wisps cross the deepest parts of the inter-cloud voids.
        fine_t = rng.beta(1.5, 1.5, 119)
        fx, fy = filament_path(np, edge, fine_t, -shift*1.25)
        deposit(np, background_dust, fx + rng.normal(0, 9.5, fine_t.size),
                fy + rng.normal(0, 9.5, fine_t.size), rng.uniform(0.08, 0.49, fine_t.size))
        if edge.flow:
            # Directed signal lights up a narrow selection of the same dust.
            steps = np.linspace(0, 1, 144)
            px, py = filament_path(np, edge, steps, shift)
            deposit(np, route, px, py, np.full(steps.size, 2.0))
    main_knots = FLOW[1:-1]
    branch_knots = tuple(node for route in FOOTER_BRANCHES for node in route[1:-1])
    for index, (x, y) in enumerate(main_knots + (FOOTER_FORK,) + branch_knots + NEBULAE):
        primary = index < len(main_knots)
        prominent = primary and index % 3 == 0
        count = 127 if prominent else 79 if primary else 41
        spread = 5.6 if prominent else 3.6 if primary else 3.75
        rx, ry = rng.normal(0, spread, (2, count))
        jitter = rng.lognormal(-0.23, 0.75, count)
        deposit(np, cores, x+rx, y+ry, (1.4 if prominent else 0.83)*jitter)
        deposit(np, dust, x+rx*2.1, y+ry*1.47, jitter*1.23)

    # Fibonacci blur scales separate broad blue density, luminous strands and
    # compact stellar knots. High-frequency variation stays spatial, not temporal.
    veil = gaussian_filter(gas + background_dust * 2, (13, 21)) * 6.2
    plasma = gaussian_filter(gas + dust * 0.39, (5, 8)) * 3.9
    filaments = gaussian_filter(dust, (1.5, 2.2)) * 1.58
    clusters = gaussian_filter(cores, (2.7, 4.3)) * 2.20
    motes = gaussian_filter(dust + cores*0.48, 0.58) * 0.30
    far = gaussian_filter(background_dust, (2.1, 3.4)) * 3.2
    columns = np.linspace(0, 1, WIDTH)
    rows = np.linspace(0, 1, shape[0])[:, None]
    hue = (0.48 + 0.39*np.sin(tau*(columns-rows*0.37+0.1)))[..., None]
    clouds = np.array([0.16, 0.67, 0.69])*hue + np.array([0.30, 0.42, 0.81])*(1-hue)
    light = (far[..., None]*[0.25, 0.41, 0.63] +
             veil[..., None]*[0.19, 0.28, 0.43] +
             plasma[..., None]*clouds +
             filaments[..., None]*[0.34, 0.74, 0.81] +
             clusters[..., None]*[0.59, 0.90, 0.87] +
             motes[..., None]*[0.68, 0.85, 0.91])
    light += render_warm_field(shape)
    core_light = gaussian_filter(route, (2.6, 4.6)) * 5.3
    return light[margin:margin+HEIGHT], core_light[margin:margin+HEIGHT]


def panel_image(light, route, name, offset, phase=None):
    import numpy as np
    from PIL import Image

    height = len(light)
    y, x = np.ogrid[:height, :WIDTH]
    # Ease each slice back into the README's negative space at the text seam.
    edge = np.minimum(1, np.minimum(y, height-1-y)/21)
    route_x, route_y = zip(*FLOW)
    handoff = np.interp(y+offset, route_y, route_x)
    edge_glow = np.exp(-((x-handoff)/34)**2)
    if name == "stitch-pulse":
        # Let the two tips trail toward the card columns while the rest fades.
        tips = [np.exp(-((x-branch[-2][0])/34)**2) for branch in FOOTER_BRANCHES]
        edge_glow = np.where(y >= height//2, np.maximum(*tips), edge_glow)
    fade = edge**0.72
    border = fade + (1-fade)*(0.13 + 0.49*edge_glow)
    border *= 0.68 + 0.32*np.minimum(1, np.minimum(x, WIDTH-1-x)/34)
    base = 1-np.exp(-light)
    boost = 0
    if phase is not None:
        period = FIBONACCI[-1]
        travel = (phase*period - offset-y + period/2) % period-period/2
        if name == "stitch-pulse":
            # An uneven split makes the two outgoing ripples feel like growth.
            travel = travel + np.clip((x-FOOTER_FORK[0])/170, -1, 1) * (y/height)*8
            pulse = np.exp(-(travel/11)**2)
            boost = (np.minimum(1, route)*pulse*(0.60 + 0.35*(y/height)**2))[..., None]
        else:
            pulse = np.exp(-(travel/6.5)**2)
            boost = (np.minimum(1, route)*pulse*0.92)[..., None]
    illumination = np.clip(base + boost*np.array([0.47, 0.78, 0.84]), 0, 1)
    # Use a single fixed image exposure and a screen-like highlight rolloff.
    rgb = np.asarray(BACKGROUND) + 224*illumination*border[..., None]
    image = Image.fromarray(np.rint(rgb).clip(0, 255).astype(np.uint8))
    return image.resize((DELIVERY_WIDTH, round(height*DELIVERY_WIDTH/WIDTH)),
                        Image.Resampling.LANCZOS)


def render(output):
    from PIL import Image

    field, route = render_field()
    offset = 0
    for name, height in PANELS:
        panel = field[offset:offset+height]
        signal = route[offset:offset+height]
        still = panel_image(panel, signal, name, offset)
        still.save(output / f"{name}.png", optimize=True)
        frames = [panel_image(panel, signal, name, offset, frame/FRAMES)
                  for frame in range(FRAMES)]
        # One palette keeps the stationary particles identical between frames.
        sample = Image.new("RGB", (still.width, still.height*5))
        for index, frame in enumerate((still, frames[0], frames[5], frames[10], frames[15])):
            sample.paste(frame, (0, index*still.height))
        palette = sample.quantize(colors=73, method=Image.Quantize.MEDIANCUT)
        encoded = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image in frames]
        encoded[0].save(output / f"{name}.gif", save_all=True, append_images=encoded[1:],
                        duration=FRAME_MS, loop=0, disposal=1, optimize=True)
        offset += height


# Coordinates are in the delivered image, with one vertical axis across both GIFs.
NEXUS_UPPER_HEIGHTS = (308, 257)
NEXUS_UPPER_EXPORT_WIDTH = 640
NEXUS_UPPER_LANES = (
    (0, 1.85, 0, .86, False, ((563, 0),(530, 58),(453, 113),(351, 168),(289, 233),
                              (244, 308),(297, 383),(368, 437),(333, 489),(138, 565))),
    (1, 1.65, 1.2, .88, False, ((631, 0),(583,72),(562,128),(491,176),(400,239),
                                (341,297),(417,374),(509,425),(541,485),(584, 565))),
    (0, 1.37, 2.2, 1.12, True, ((102, 0),(149,66),(125,141),(97,207),(130,276),
                                 (167,333),(103,417),(139,477),(174, 565))),
    (0, 1.12, 4.2, 1.4, False, ((674, 0),(610,50),(626,139),(645,208),(591,279),
                                 (629,351),(585,428),(651,482),(664, 565))),
    (1, .97, 3.7, 1.1, True, ((186, 0),(146,73),(219,127),(181,211),(191,282),
                              (155,374),(221,443),(209,502),(160, 565))),
)


def remap_filaments(material, x, y, trace, strength, phase, scale, reverse):
    """Lay overlapping short sections of footer material along a continuous curve."""
    import numpy as np
    from scipy.ndimage import map_coordinates

    height, width = material.shape[:2]
    layer = np.zeros((*x.shape, 3), dtype=np.float32)
    radial = x - trace
    stride = -.82 if reverse else .78
    for index, section in enumerate((35, 168, 307, 452, 579)):
        origin = 104 + 7 * np.sin(index*1.77 + phase)
        src_y = origin + (y - section) * stride
        src_y += 9 * np.sin(y / 29 + phase) + radial * (.27 if index % 2 else -.19)
        center = 48 + .42*(src_y - 60)
        direction = -1 if (index + reverse) % 3 == 2 else 1
        src_x = center + direction * radial * scale + 8 * np.sin(y / 44 + phase + index)
        src_x += 3 * np.sin(y / 16 + phase + radial / 26)
        fringe = np.clip((width - 1 - src_x) / 15, 0, 1)*np.clip(src_x / 18, 0, 1)
        end = np.clip((src_y - 20) / 39, 0, 1)*np.clip((height - 12 - src_y) / 41, 0, 1)
        mapped = np.stack([map_coordinates(channel, (src_y,src_x), order=1)
                           for channel in np.moveaxis(material, -1, 0)], axis=-1)
        layer += mapped*(fringe*end*strength)[...,None]
    return layer


def nexus_upper_plate(poster):
    """Recover the two text-free margins and weave both upper slices from them."""
    import numpy as np
    from PIL import Image
    from scipy.interpolate import PchipInterpolator

    height = sum(NEXUS_UPPER_HEIGHTS)
    y, x = np.mgrid[0:height, 0:DELIVERY_WIDTH].astype(np.float32)
    background = np.asarray(BACKGROUND, dtype=np.float32)
    source = np.maximum(0, np.asarray(poster, dtype=np.float32) - background)
    # Leave a safety margin before the first and after the last typeset pixel.
    material = (source[:, :155], source[:, -155:][:, ::-1])
    traces = []
    filaments = np.zeros((*x.shape, 3), dtype=np.float32)
    for side, strength, phase, scale, reverse, points in NEXUS_UPPER_LANES:
        route_x, route_y = np.asarray(points).T
        trace = PchipInterpolator(route_y, route_x)(y[:, :1])
        traces.append(trace)
        filaments += remap_filaments(material[side], x, y, trace, strength, phase, scale, reverse)

    # Keep a soft recessed layer from the current scene, below the sharp strands.
    prior, _ = render_field()
    fog = np.rint(224*(1-np.exp(-prior[:PANELS[0][1] + PANELS[1][1]]))).astype(np.uint8)
    fog = np.asarray(Image.fromarray(fog).resize((DELIVERY_WIDTH, height), Image.Resampling.LANCZOS))
    light = 238*(1-np.exp(-(filaments + .34*fog)/200))
    luminance = light @ np.array((.2126, .7152, .0722), dtype=np.float32)
    # Lift the existing brightest crossings; leave the dark fabric untouched.
    highlights = (np.clip((luminance-83)/65, 0, 1)**1.45) * 102
    warm = (filaments[..., 0] > filaments[..., 2] + 12)[...,None]
    color = np.where(warm, (1, .71, .42), (.73, .89, 1))
    return background + light + highlights[...,None]*color, traces[:2]


def nexus_junction(x, y, center_x, center_y):
    """A tight core and soft halo shared with the v10 invitation."""
    import numpy as np

    distance = ((x-center_x) / 1.16) ** 2 + (y-center_y) ** 2
    core = 130 * np.exp(-distance / (2 * 4.2 ** 2))
    halo = 72 * np.exp(-distance / (2 * 9.75 ** 2))
    return core + halo


def animate_upper_slice(pixels, traces, name, output, phase_offset):
    """Let cyan and ember glints light existing junctions in descending order."""
    import numpy as np
    from PIL import Image
    from scipy.ndimage import gaussian_filter

    height, width = pixels.shape[:2]
    y, x = np.ogrid[:height, :width]
    border = np.clip(np.minimum(y, height-1-y)/28,0,1)**.65
    anchor = np.maximum(np.exp(-((x-traces[0])/42)**2), np.exp(-((x-traces[1])/35)**2))
    shade = (.12 + .70*border + (1-border)*.18*anchor)
    shade *= np.clip(np.minimum(x,width-1-x)/36,0,1)**.64
    pixels = np.asarray(BACKGROUND) + (pixels-np.asarray(BACKGROUND))*shade[...,None]
    size = (NEXUS_UPPER_EXPORT_WIDTH, round(height * NEXUS_UPPER_EXPORT_WIDTH / width))

    def export(image):
        return Image.fromarray(np.rint(image).clip(0, 255).astype(np.uint8)).resize(
            size, Image.Resampling.LANCZOS)

    still = export(pixels)
    still.save(output / f"{name}.png", optimize=True)
    lightness = gaussian_filter(pixels @ np.array((.2126, .7152, .0722)), 4)
    emitters = []
    for lane, (trace, color) in enumerate(zip(traces, ((.28,.73,1), (1,.52,.19)))):
        for position, band in enumerate((.10,.23,.36,.49,.62,.75,.89)):
            row = round((height - 1) * band)
            column = round(float(trace[row, 0]))
            half_width = 35
            left, right = max(0, column - half_width), min(width, column + half_width)
            # Place the pulse next to a brighter strand with headroom to glow.
            row_light = lightness[row, left:right]
            center = left + int(np.argmin(np.abs(row_light-120)))
            glow = np.maximum(0, nexus_junction(x, y, center, row) - 19) * shade
            delay = phase_offset + position * .105 + lane * .031
            emitters.append((delay, glow[...,None]*np.asarray(color) * .98))

    frames = []
    for frame_index in range(FRAMES):
        phase = frame_index / FRAMES
        lit = pixels.copy()
        for delay, glow in emitters:
            pulse = max(0, np.cos(tau * (phase - delay))) ** 14
            echo = max(0, np.cos(tau * (phase - delay - .085))) ** 24
            lit += glow * (pulse + .18 * echo)
        frames.append(export(lit))
    samples = Image.new("RGB", (still.width, still.height * 4))
    for index, frame in enumerate((still, frames[3], frames[9], frames[15])):
        samples.paste(frame, (0, index * still.height))
    rows = np.asarray(samples).reshape(-1, 3).astype(np.int16)
    warmth = (rows[:, 0] >= 43) & (rows[:, 0]-rows[:, 1] >= 8) & (rows[:, 1]-rows[:, 2] >= 3)
    entries = []
    for sample, colors in ((rows[~warmth], 30), (rows[warmth], 15)):
        # Pillow's quantizer needs a modest row width on every supported host.
        swatches = Image.fromarray(sample[:(len(sample) // 256)*256].reshape(-1, 256, 3).astype(np.uint8))
        entries.extend(swatches.quantize(colors=colors).getpalette()[:3*colors])
    palette = Image.new("P", (1, 1))
    palette.putpalette(entries)
    encoded = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    encoded[0].save(output / f"{name}.gif", save_all=True, append_images=encoded[1:],
                    duration=FRAME_MS, loop=0, disposal=1, optimize=True, palette=bytes(entries))


def render_nexus_upper(output, poster_path):
    from PIL import Image

    with Image.open(poster_path) as source:
        poster = source.convert("RGB")
    if poster.size != NEXUS_SIZE:
        raise ValueError(f"The Nexus poster must be {NEXUS_SIZE[0]}×{NEXUS_SIZE[1]}.")
    plate, traces = nexus_upper_plate(poster)
    offset = 0
    for (name, _), height, phase in zip(PANELS, NEXUS_UPPER_HEIGHTS, (.02, .22)):
        end = offset + height
        animate_upper_slice(plate[offset:end], [trace[offset:end] for trace in traces], name, output, phase)
        offset = end


def render_nexus_footer(output):
    """Light the knots in both filaments from the typeset reduced-motion poster."""
    import numpy as np
    from PIL import Image

    still = Image.open(output / "stitch-pulse.png").convert("RGB")
    if still.size != NEXUS_SIZE:
        raise ValueError(f"The Nexus poster must be {NEXUS_SIZE[0]}×{NEXUS_SIZE[1]}.")
    pixels = np.asarray(still, dtype=np.float32)
    y, x = np.mgrid[0:still.height, 0:still.width]
    side = np.minimum(x, still.width - 1 - x) / still.width
    edge = np.clip((.225 - side) / .022, 0, 1)
    # Centers are aligned with luminous junctions in the fixed poster.
    lanes = (
        (((50, 70), (64, 99), (83, 122), (132, 150)), (.28, .73, 1)),
        (((650, 58), (621, 104), (623, 129), (568, 157)), (1, .52, .19)),
    )
    emitters = []
    for lane_index, (knots, color) in enumerate(lanes):
        ink = np.array(color, dtype=np.float32)
        for knot_index, (center_x, center_y) in enumerate(knots):
            glow = np.maximum(0, (nexus_junction(x, y, center_x, center_y) - 7) * edge)
            delay = .06 + knot_index * .111 + lane_index * .50
            emitters.append((delay, glow[..., None] * ink))

    frames = []
    for frame in range(NEXUS_FRAMES):
        phase = frame / NEXUS_FRAMES
        lit = pixels.copy()
        for delay, glow in emitters:
            pulse = max(0, np.cos(2 * np.pi * (phase-delay))) ** 28
            echo = max(0, np.cos(2 * np.pi * (phase-delay-.085))) ** 30
            lit += glow * (pulse + .18 * echo)
        frames.append(Image.fromarray(np.rint(np.clip(lit, 0, 255)).astype("uint8")))

    samples = Image.new("RGB", (still.width, still.height * 3))
    for index, image in enumerate((still, frames[7], frames[18])):
        samples.paste(image, (0, index * still.height))
    palette = samples.quantize(colors=44, method=Image.Quantize.MEDIANCUT)
    encoded = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    encoded[0].save(output / "stitch-pulse.gif", save_all=True, append_images=encoded[1:],
                    duration=NEXUS_FRAME_MS, loop=0, disposal=1, optimize=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ASSETS)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--nexus-footer", action="store_true",
                      help="Animate only the Nexus GIF from stitch-pulse.png in the output directory.")
    mode.add_argument("--nexus-upper", action="store_true",
                      help="Render both upper GIFs and their PNG stills using the v10 Nexus texture.")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.nexus_footer:
        render_nexus_footer(args.output)
    elif args.nexus_upper:
        render_nexus_upper(args.output, ASSETS / "profile-releases/v10/assets/stitch-pulse.png")
    else:
        render(args.output)


if __name__ == "__main__":
    main()
