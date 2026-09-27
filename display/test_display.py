#!/usr/bin/env python3
"""Draw a high-contrast wiring and orientation test on the round display."""

from PIL import Image, ImageDraw, ImageFont

from gc9a01 import GC9A01


SCALE = 4
SIZE = 240


def font(size):
    paths = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    )
    for path in paths:
        try:
            return ImageFont.truetype(path, size * SCALE)
        except OSError:
            pass
    return ImageFont.load_default(size=size * SCALE)


def centered(draw, position_y, text, text_font, fill):
    box = draw.textbbox((0, 0), text, font=text_font)
    width = box[2] - box[0]
    draw.text(((SIZE * SCALE - width) // 2, position_y * SCALE), text, font=text_font, fill=fill)


display = GC9A01()
try:
    display.init()
    image = Image.new("RGB", (SIZE * SCALE, SIZE * SCALE), "#08131f")
    draw = ImageDraw.Draw(image)
    draw.ellipse(
        (3 * SCALE, 3 * SCALE, 236 * SCALE, 236 * SCALE),
        outline="#22c55e",
        width=4 * SCALE,
    )
    draw.arc(
        (13 * SCALE, 13 * SCALE, 226 * SCALE, 226 * SCALE),
        205,
        335,
        fill="#ff7a1a",
        width=9 * SCALE,
    )
    draw.ellipse((110 * SCALE, 22 * SCALE, 130 * SCALE, 42 * SCALE), fill="#ef4444")
    centered(draw, 58, "DISPLAY", font(35), "white")
    centered(draw, 112, "SPI OK", font(48), "#22c55e")
    image = image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    display.display(image)
    print("Testbild wurde an das Display gesendet.")
finally:
    display.close()
