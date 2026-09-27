"""Minimal GC9A01 SPI display driver for Raspberry Pi."""

import time

import numpy as np
import spidev
from gpiozero import DigitalOutputDevice


class GC9A01:
    width = 240
    height = 240

    def __init__(self, dc_pin=25, reset_pin=27, bus=0, device=0, speed_hz=40_000_000):
        self.dc = DigitalOutputDevice(dc_pin, initial_value=False)
        self.reset = DigitalOutputDevice(reset_pin, initial_value=True)
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = speed_hz
        self.spi.mode = 0
        self.spi.no_cs = False

    def command(self, value, data=None):
        self.dc.off()
        self.spi.writebytes([value])
        if data:
            self.dc.on()
            self.spi.writebytes(list(data))

    def reset_display(self):
        self.reset.on()
        time.sleep(0.01)
        self.reset.off()
        time.sleep(0.02)
        self.reset.on()
        time.sleep(0.12)

    def init(self):
        self.reset_display()
        sequence = (
            (0xEF, ()),
            (0xEB, (0x14,)),
            (0xFE, ()),
            (0xEF, ()),
            (0xEB, (0x14,)),
            (0x84, (0x40,)),
            (0x85, (0xFF,)),
            (0x86, (0xFF,)),
            (0x87, (0xFF,)),
            (0x88, (0x0A,)),
            (0x89, (0x21,)),
            (0x8A, (0x00,)),
            (0x8B, (0x80,)),
            (0x8C, (0x01,)),
            (0x8D, (0x01,)),
            (0x8E, (0xFF,)),
            (0x8F, (0xFF,)),
            (0xB6, (0x00, 0x20)),
            (0x36, (0x08,)),
            (0x3A, (0x05,)),
            (0x90, (0x08, 0x08, 0x08, 0x08)),
            (0xBD, (0x06,)),
            (0xBC, (0x00,)),
            (0xFF, (0x60, 0x01, 0x04)),
            (0xC3, (0x13,)),
            (0xC4, (0x13,)),
            (0xC9, (0x22,)),
            (0xBE, (0x11,)),
            (0xE1, (0x10, 0x0E)),
            (0xDF, (0x21, 0x0C, 0x02)),
            (0xF0, (0x45, 0x09, 0x08, 0x08, 0x26, 0x2A)),
            (0xF1, (0x43, 0x70, 0x72, 0x36, 0x37, 0x6F)),
            (0xF2, (0x45, 0x09, 0x08, 0x08, 0x26, 0x2A)),
            (0xF3, (0x43, 0x70, 0x72, 0x36, 0x37, 0x6F)),
            (0xED, (0x1B, 0x0B)),
            (0xAE, (0x77,)),
            (0xCD, (0x63,)),
            (0x70, (0x07, 0x07, 0x04, 0x0E, 0x0F, 0x09, 0x07, 0x08, 0x03)),
            (0xE8, (0x34,)),
            (0x62, (0x18, 0x0D, 0x71, 0xED, 0x70, 0x70, 0x18, 0x0F, 0x71, 0xEF, 0x70, 0x70)),
            (0x63, (0x18, 0x11, 0x71, 0xF1, 0x70, 0x70, 0x18, 0x13, 0x71, 0xF3, 0x70, 0x70)),
            (0x64, (0x28, 0x29, 0xF1, 0x01, 0xF1, 0x00, 0x07)),
            (0x66, (0x3C, 0x00, 0xCD, 0x67, 0x45, 0x45, 0x10, 0x00, 0x00, 0x00)),
            (0x67, (0x00, 0x3C, 0x00, 0x00, 0x00, 0x01, 0x54, 0x10, 0x32, 0x98)),
            (0x74, (0x10, 0x85, 0x80, 0x00, 0x00, 0x4E, 0x00)),
            (0x98, (0x3E, 0x07)),
            (0x35, ()),
            (0x21, ()),
        )
        for command, data in sequence:
            self.command(command, data)
        self.command(0x11)
        time.sleep(0.12)
        self.command(0x29)
        time.sleep(0.02)

    def display(self, image):
        image = image.convert("RGB").resize((self.width, self.height))
        rgb = np.asarray(image, dtype=np.uint16)
        pixels = (
            ((rgb[:, :, 0] & 0xF8) << 8)
            | ((rgb[:, :, 1] & 0xFC) << 3)
            | (rgb[:, :, 2] >> 3)
        ).astype(">u2", copy=False).tobytes()

        self.command(0x2A, (0, 0, 0, self.width - 1))
        self.command(0x2B, (0, 0, 0, self.height - 1))
        self.command(0x2C)
        self.dc.on()
        for start in range(0, len(pixels), 4096):
            self.spi.writebytes2(pixels[start : start + 4096])

    def close(self):
        self.spi.close()
        self.dc.close()
        self.reset.close()
