#!/usr/bin/env python3
"""Render a detailed eye demo for the round GC9A01 display."""

import math
import random

from PIL import Image, ImageDraw, ImageFilter

from gc9a01 import GC9A01


SCALE = 4
SIZE = 240
CANVAS = SIZE * SCALE


def scaled(points):
    return tuple(int(value * SCALE) for value in points)


random.seed(9)
image = Image.new("RGB", (CANVAS, CANVAS), "#020305")
draw = ImageDraw.Draw(image)

# Subtle halo behind the eye.
halo = Image.new("RGBA", image.size, (0, 0, 0, 0))
halo_draw = ImageDraw.Draw(halo)
halo_draw.ellipse(scaled((12, 36, 228, 204)), fill=(120, 0, 0, 80))
halo = halo.filter(ImageFilter.GaussianBlur(18 * SCALE))
image = Image.alpha_composite(image.convert("RGBA"), halo)
draw = ImageDraw.Draw(image)

# Almond-shaped sclera.
eye_shape = scaled((18, 55, 222, 185))
draw.ellipse(eye_shape, fill="#eee7dc", outline="#7a1018", width=5 * SCALE)
draw.pieslice(scaled((3, 14, 237, 160)), 0, 180, fill="#020305")
draw.pieslice(scaled((3, 80, 237, 226)), 180, 360, fill="#020305")

# Fine veins, kept away from the center.
for side in (-1, 1):
    for index in range(11):
        y = 82 + index * 7 + random.randint(-3, 3)
        start_x = 27 if side < 0 else 213
        end_x = 84 if side < 0 else 156
        middle_x = 55 if side < 0 else 185
        points = [
            (start_x, y),
            (middle_x, y + random.randint(-8, 8)),
            (end_x, 108 + random.randint(-18, 18)),
        ]
        draw.line([(x * SCALE, yy * SCALE) for x, yy in points], fill="#a52a32", width=SCALE)

# Iris with concentric depth.
center = (120, 120)
for radius in range(57, 9, -1):
    ratio = radius / 57
    red = int(18 + 42 * (1 - ratio))
    green = int(75 + 105 * (1 - ratio))
    blue = int(88 + 96 * ratio)
    draw.ellipse(
        scaled((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)),
        fill=(red, green, blue, 255),
    )

# Radial iris fibres.
for angle in range(0, 360, 5):
    jitter = random.uniform(-0.035, 0.035)
    radians = math.radians(angle) + jitter
    inner = random.randint(18, 28)
    outer = random.randint(45, 56)
    x1 = (120 + math.cos(radians) * inner) * SCALE
    y1 = (120 + math.sin(radians) * inner) * SCALE
    x2 = (120 + math.cos(radians) * outer) * SCALE
    y2 = (120 + math.sin(radians) * outer) * SCALE
    color = "#8bd3c7" if angle % 15 else "#d7a94b"
    draw.line((x1, y1, x2, y2), fill=color, width=SCALE)

# Dark limbal ring, pupil and reflections.
draw.ellipse(scaled((62, 62, 178, 178)), outline="#071517", width=5 * SCALE)
draw.ellipse(scaled((91, 91, 149, 149)), fill="#010204")
draw.ellipse(scaled((101, 101, 139, 139)), fill="#000000")
draw.ellipse(scaled((91, 78, 110, 97)), fill=(255, 255, 255, 235))
draw.ellipse(scaled((112, 101, 121, 110)), fill=(255, 255, 255, 150))

# Heavy upper and lower lids.
draw.arc(scaled((11, 43, 229, 194)), 198, 342, fill="#c51d2d", width=8 * SCALE)
draw.arc(scaled((12, 48, 228, 193)), 18, 162, fill="#5c0910", width=6 * SCALE)

image = image.convert("RGB").resize((SIZE, SIZE), Image.Resampling.LANCZOS)

display = GC9A01()
try:
    display.init()
    display.display(image)
    print("Auge wurde an das Display gesendet.")
finally:
    display.close()
