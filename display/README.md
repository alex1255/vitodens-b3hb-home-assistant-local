# GC9A01 display development

Development target: Raspberry Pi 4 Model B with a 240 x 240 GC9A01 SPI display.

## Wiring

| Display | BCM | Physical pin |
| --- | ---: | ---: |
| VCC | 3.3 V | 1 |
| GND | GND | 6 |
| SCL | GPIO11 / SCLK | 23 |
| SDA | GPIO10 / MOSI | 19 |
| DC | GPIO25 | 22 |
| CS | GPIO8 / CE0 | 24 |
| RST | GPIO27 | 13 |

Run `test_display.py` from the application directory to display the hardware test image.

`vitodens_display.py` is the read-only production application. It subscribes to
existing MQTT state topics and never publishes heating commands. HK1 flow and
return temperatures are read directly from the encrypted ESPHome Native API so
they continue to use the two deliberately remote pipe sensors. The display
service is `vitodens-display.service`; its credentials belong in the protected
`/etc/default/vitodens-display` file, never in version control.
