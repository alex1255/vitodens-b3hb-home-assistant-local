#!/usr/bin/env python3
"""Animated main-screen concept for the round Vitodens display."""

import math
import signal
import time

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from gc9a01 import GC9A01


SIZE = 240
SCALE = 4
CANVAS = SIZE * SCALE
RUNNING = True
DEMO_MODE = "fault"


def stop(_signum, _frame):
    global RUNNING
    RUNNING = False


def font(size, bold=False):
    names = (
        "/opt/vitodens-display/assets/Arial Bold.ttf" if bold else
        "/opt/vitodens-display/assets/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size * SCALE)
        except OSError:
            pass
    return ImageFont.load_default(size=size * SCALE)


def centered(draw, y, text, text_font, fill, spacing=0):
    box = draw.textbbox((0, 0), text, font=text_font, stroke_width=spacing)
    width = box[2] - box[0]
    draw.text(
        ((CANVAS - width) / 2, y * SCALE),
        text,
        font=text_font,
        fill=fill,
        stroke_width=spacing,
        stroke_fill=fill,
    )


def arc(draw, bounds, start, end, color, width):
    draw.arc(tuple(value * SCALE for value in bounds), start, end, fill=color, width=width * SCALE)


def render_fault(pulse):
    red = int(65 + pulse * 175)
    image = Image.new("RGB", (CANVAS, CANVAS), (red, 0, 7))
    draw = ImageDraw.Draw(image)

    ring = int(175 + pulse * 80)
    arc(draw, (8, 8, 232, 232), 0, 359, (ring, ring, ring), 10)

    # Large warning sign that remains legible at the dark and bright pulse ends.
    draw.polygon(
        ((120 * SCALE, 43 * SCALE),
         (80 * SCALE, 111 * SCALE),
         (160 * SCALE, 111 * SCALE)),
        outline="white",
        width=5 * SCALE,
    )
    centered(draw, 56, "!", font(38, True), "white")
    centered(draw, 124, "STÖRUNG", font(30, True), "white")
    centered(draw, 165, "TEILNEHMER 99", font(15, True), "#fff1f2")

    return image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def render(phase):
    pulse = (math.sin(phase) + 1) / 2
    if DEMO_MODE == "fault":
        return render_fault(pulse)
    burner_active = DEMO_MODE == "normal"
    image = Image.new("RGBA", (CANVAS, CANVAS), "#030608")
    draw = ImageDraw.Draw(image)

    # One uninterrupted, steady ring communicates one operating mode.
    ring_colors = {
        "normal": ("#3b1b14", "#ff711f"),
        "reduced": ("#102b45", "#2997e8"),
        "hot_water": ("#0d3639", "#20c6c9"),
    }
    ring_base, ring_color = ring_colors[DEMO_MODE]
    arc(draw, (8, 8, 232, 232), 0, 359, ring_base, 12)
    arc(draw, (8, 8, 232, 232), 0, 359, ring_color, 10)

    # The whole face visibly pulses only while the burner is active.
    face_color = (
        (int(8 + pulse * 142), int(13 + pulse * 45), int(18 - pulse * 5), 255)
        if burner_active
        else ((5, 27, 31, 255) if DEMO_MODE == "hot_water" else (7, 18, 32, 255))
    )
    draw.ellipse(
        (28 * SCALE, 28 * SCALE, 212 * SCALE, 212 * SCALE),
        fill=face_color,
    )

    # A small flickering flame makes the meaning of the pulse explicit.
    if burner_active:
        flicker = int(math.sin(phase * 2.7) * 3)
        flame_outer = [
            (184 * SCALE, (77 + flicker) * SCALE),
            (178 * SCALE, 65 * SCALE),
            (183 * SCALE, 52 * SCALE),
            (190 * SCALE, 62 * SCALE),
            (195 * SCALE, 48 * SCALE),
            (202 * SCALE, 64 * SCALE),
            (201 * SCALE, 75 * SCALE),
            (194 * SCALE, 83 * SCALE),
        ]
        draw.polygon(flame_outer, fill="#ff6a1a")
        draw.ellipse(
            (187 * SCALE, (64 + flicker) * SCALE, 197 * SCALE, 79 * SCALE),
            fill="#ffd34e",
        )

    primary_label = "SPEICHER" if DEMO_MODE == "hot_water" else "VORLAUF"
    centered(draw, 55, primary_label, font(19, True), "#d3dadd")

    # Main reading. Degree sign is separated to keep the number dominant.
    value_font = font(64, True)
    values = {"normal": "42", "reduced": "35", "hot_water": "46"}
    value = values[DEMO_MODE]
    box = draw.textbbox((0, 0), value, font=value_font)
    number_width = box[2] - box[0]
    total_width = number_width + 22 * SCALE
    number_x = (CANVAS - total_width) / 2
    draw.text((number_x, 82 * SCALE), value, font=value_font, fill="#f8fafc")
    draw.text((number_x + number_width + 3 * SCALE, 88 * SCALE), "°", font=font(28, True), fill="#ff8a55")

    # One large secondary value is more useful than a dense status row.
    draw.rounded_rectangle(
        (43 * SCALE, 157 * SCALE, 197 * SCALE, 198 * SCALE),
        radius=18 * SCALE,
        fill="#101b22",
        outline="#263740",
        width=2 * SCALE,
    )
    if DEMO_MODE == "hot_water":
        centered(draw, 165, "BEREIT", font(25, True), "#8cf1e8")
    else:
        draw.text((57 * SCALE, 170 * SCALE), "RL", font=font(17, True), fill="#70c7ec")
        return_value = "32°" if DEMO_MODE == "normal" else "30°"
        draw.text((103 * SCALE, 159 * SCALE), return_value, font=font(31, True), fill="#edf9fc")

    return image.convert("RGB").resize((SIZE, SIZE), Image.Resampling.LANCZOS)


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)

display = GC9A01(speed_hz=40_000_000)
try:
    display.init()
    phase = 0.0
    while RUNNING:
        display.display(render(phase))
        phase += 0.32
        time.sleep(0.08)
finally:
    display.close()
