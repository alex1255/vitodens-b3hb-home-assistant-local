#!/usr/bin/env python3
"""Animated eye demo for the round GC9A01 display."""

import math
import random
import signal
import time

from PIL import Image, ImageDraw

from gc9a01 import GC9A01


SCALE = 3
SIZE = 240
RUNNING = True


def stop(_signum, _frame):
    global RUNNING
    RUNNING = False


def s(values):
    return tuple(int(value * SCALE) for value in values)


def render_eye(look_x=0, look_y=0, blink=0.0, pupil_scale=1.0):
    canvas = SIZE * SCALE
    image = Image.new("RGB", (canvas, canvas), "#010204")
    draw = ImageDraw.Draw(image)

    # White of the eye and subtle veins.
    draw.ellipse(s((15, 53, 225, 187)), fill="#eee8dc", outline="#7b1018", width=4 * SCALE)
    random.seed(17)
    for side in (-1, 1):
        for index in range(9):
            start_x = 25 if side < 0 else 215
            end_x = 79 if side < 0 else 161
            y = 84 + index * 8
            draw.line(
                [(start_x * SCALE, y * SCALE),
                 (((start_x + end_x) / 2) * SCALE, (y + random.randint(-8, 8)) * SCALE),
                 (end_x * SCALE, (112 + random.randint(-18, 18)) * SCALE)],
                fill="#9d2931",
                width=SCALE,
            )

    cx = 120 + look_x
    cy = 120 + look_y
    # Iris depth and fibres.
    for radius in range(56, 8, -1):
        ratio = radius / 56
        color = (
            int(20 + 40 * (1 - ratio)),
            int(78 + 100 * (1 - ratio)),
            int(92 + 86 * ratio),
        )
        draw.ellipse(s((cx - radius, cy - radius, cx + radius, cy + radius)), fill=color)

    for angle in range(0, 360, 6):
        radians = math.radians(angle)
        inner = 19
        outer = 53
        draw.line(
            ((cx + math.cos(radians) * inner) * SCALE,
             (cy + math.sin(radians) * inner) * SCALE,
             (cx + math.cos(radians) * outer) * SCALE,
             (cy + math.sin(radians) * outer) * SCALE),
            fill="#9bd8ca" if angle % 18 else "#d3a445",
            width=SCALE,
        )

    draw.ellipse(s((cx - 57, cy - 57, cx + 57, cy + 57)), outline="#071517", width=5 * SCALE)
    pupil = int(27 * pupil_scale)
    draw.ellipse(s((cx - pupil, cy - pupil, cx + pupil, cy + pupil)), fill="#000000")
    draw.ellipse(s((cx - 27, cy - 39, cx - 8, cy - 20)), fill="#ffffff")
    draw.ellipse(s((cx - 7, cy - 18, cx + 1, cy - 10)), fill="#bfefff")

    # The two black masks form closing eyelids.
    lid = int(67 * max(0.0, min(1.0, blink)))
    if lid:
        draw.rectangle(s((0, 0, 240, 53 + lid)), fill="#010204")
        draw.rectangle(s((0, 187 - lid, 240, 240)), fill="#010204")
        edge_y_top = 53 + lid
        edge_y_bottom = 187 - lid
        draw.arc(s((12, edge_y_top - 30, 228, edge_y_top + 38)), 195, 345, fill="#c51d2d", width=5 * SCALE)
        draw.arc(s((12, edge_y_bottom - 38, 228, edge_y_bottom + 30)), 15, 165, fill="#6f0c15", width=4 * SCALE)
    else:
        draw.arc(s((10, 42, 230, 195)), 198, 342, fill="#c51d2d", width=7 * SCALE)
        draw.arc(s((11, 47, 229, 194)), 18, 162, fill="#620b13", width=5 * SCALE)

    return image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def ease(value):
    return (1 - math.cos(value * math.pi)) / 2


def animation_frames():
    while True:
        # Look left, center, right and center again.
        for target in (-28, 0, 28, 0):
            start = getattr(animation_frames, "last_x", 0)
            for step in range(9):
                amount = ease(step / 8)
                x = round(start + (target - start) * amount)
                yield render_eye(x, round(abs(x) * 0.08), pupil_scale=0.95)
            animation_frames.last_x = target
            for _ in range(5):
                yield render_eye(target, round(abs(target) * 0.08), pupil_scale=0.95)

        # Smooth blink.
        for blink in (0.15, 0.35, 0.62, 0.88, 1.0, 0.72, 0.38, 0.12, 0.0):
            yield render_eye(blink=blink, pupil_scale=0.9)

        # Brief pupil reaction.
        for pupil in (0.9, 0.78, 0.66, 0.58, 0.66, 0.78, 0.9, 1.0):
            yield render_eye(pupil_scale=pupil)


def run():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    display = GC9A01(speed_hz=40_000_000)
    try:
        display.init()
        for frame in animation_frames():
            if not RUNNING:
                break
            display.display(frame)
            time.sleep(0.035)
    finally:
        display.close()


if __name__ == "__main__":
    run()
