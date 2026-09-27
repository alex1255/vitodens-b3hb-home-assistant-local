#!/usr/bin/env python3
"""Read-only MQTT display for the local Vitodens installation."""

import asyncio
import math
import os
import signal
import threading
import time
from dataclasses import dataclass, field

import paho.mqtt.client as mqtt
from PIL import Image, ImageDraw, ImageFont

from gc9a01 import GC9A01


SIZE = 240
SCALE = 2
CANVAS = SIZE * SCALE
TOPIC_BASE = os.getenv("VITO_DISPLAY_TOPIC_BASE", "vitodens").rstrip("/")
DATA_TIMEOUT = int(os.getenv("VITO_DISPLAY_DATA_TIMEOUT", "120"))
PRIMARY_TOPIC = os.getenv("VITO_DISPLAY_PRIMARY_TOPIC", f"{TOPIC_BASE}/kesseltemperatur")
PRIMARY_LABEL = os.getenv("VITO_DISPLAY_PRIMARY_LABEL", "VORLAUF")
ESPHOME_TIMEOUT = int(os.getenv("VITO_DISPLAY_ESPHOME_TIMEOUT", "120"))
ESPHOME_FLOW_KEY = int(os.getenv("VITO_DISPLAY_ESPHOME_FLOW_KEY", "3829056379"))
ESPHOME_RETURN_KEY = int(os.getenv("VITO_DISPLAY_ESPHOME_RETURN_KEY", "2845531972"))
RUNNING = True


TOPICS = {
    "availability": f"{TOPIC_BASE}/LWT",
    "storage": f"{TOPIC_BASE}/speichertemperatur",
    "burner": f"{TOPIC_BASE}/brenner_modulation",
    "mode": f"{TOPIC_BASE}/action/betriebsart/state",
    "heating_window": f"{TOPIC_BASE}/hk1_zeitfenster_aktiv",
    "hot_water_active": f"{TOPIC_BASE}/ww_erzeugung_aktiv",
    "fault_active": f"{TOPIC_BASE}/stoerung_aktiv",
    "fault_text": f"{TOPIC_BASE}/stoerung_aktuell",
}


@dataclass
class State:
    values: dict[str, str] = field(default_factory=dict)
    mqtt_connected: bool = False
    esphome_connected: bool = False
    last_optolink: float = 0.0
    last_esphome: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def set(self, key, value):
        with self.lock:
            self.values[key] = value
            if key in {"storage", "burner"}:
                self.last_optolink = time.monotonic()

    def set_esphome(self, key, value):
        with self.lock:
            self.values[key] = str(value)
            self.last_esphome = time.monotonic()

    def snapshot(self):
        with self.lock:
            return (
                dict(self.values),
                self.mqtt_connected,
                self.esphome_connected,
                self.last_optolink,
                self.last_esphome,
            )


state = State()


def stop(_signum, _frame):
    global RUNNING
    RUNNING = False


def font(size, bold=False):
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/opt/vitodens-display/assets/Arial Bold.ttf" if bold else
        "/opt/vitodens-display/assets/Arial.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size * SCALE)
        except OSError:
            pass
    return ImageFont.load_default(size=size * SCALE)


def centered(draw, y, text, text_font, fill):
    box = draw.textbbox((0, 0), text, font=text_font)
    width = box[2] - box[0]
    draw.text(((CANVAS - width) / 2, y * SCALE), text, font=text_font, fill=fill)


def arc(draw, bounds, start, end, color, width):
    draw.arc(tuple(value * SCALE for value in bounds), start, end, fill=color, width=width * SCALE)


def number(value, fallback=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def on_connect(client, _userdata, _flags, reason_code, _properties):
    with state.lock:
        state.mqtt_connected = reason_code == 0
    if reason_code == 0:
        client.subscribe([(topic, 0) for topic in TOPICS.values()])


def on_disconnect(_client, _userdata, _disconnect_flags, _reason_code, _properties):
    with state.lock:
        state.mqtt_connected = False


def on_message(_client, _userdata, message):
    payload = message.payload.decode(errors="replace").strip()
    for key, topic in TOPICS.items():
        if message.topic == topic:
            state.set(key, payload)
            break


def current_view(values, mqtt_connected, esphome_connected, last_optolink, last_esphome):
    if not mqtt_connected:
        return "communication", "MQTT OFFLINE"
    if values.get("availability", "offline").lower() != "online":
        return "communication", "OPTOLINK OFFLINE"
    if not last_optolink or time.monotonic() - last_optolink > DATA_TIMEOUT:
        return "communication", "KEINE HEIZUNGSDATEN"
    if not esphome_connected:
        return "communication", "TEMPERATUR-ESP OFFLINE"
    if not last_esphome or time.monotonic() - last_esphome > ESPHOME_TIMEOUT:
        return "communication", "KEINE FÜHLERDATEN"
    if values.get("fault_active", "OFF").upper() == "ON":
        return "fault", values.get("fault_text", "STÖRUNG")

    mode = values.get("mode", "")
    if "Nur Warmwasser" in mode:
        return "hot_water", ""
    if mode == "Aus":
        return "off", ""
    if values.get("heating_window", "OFF").upper() == "ON":
        return "normal", ""
    return "reduced", ""


async def esphome_loop():
    from aioesphomeapi import APIClient

    host = os.getenv("VITO_DISPLAY_ESPHOME_HOST", "esphome-device.local")
    port = int(os.getenv("VITO_DISPLAY_ESPHOME_PORT", "6053"))
    noise_psk = os.getenv("VITO_DISPLAY_ESPHOME_NOISE_PSK", "") or None
    while RUNNING:
        client = APIClient(host, port, noise_psk=noise_psk)
        cancel_subscription = None
        try:
            await client.connect(login=True)
            with state.lock:
                state.esphome_connected = True

            def receive(sensor_state):
                if sensor_state.key == ESPHOME_FLOW_KEY:
                    state.set_esphome("primary", sensor_state.state)
                elif sensor_state.key == ESPHOME_RETURN_KEY:
                    state.set_esphome("return", sensor_state.state)

            cancel_subscription = client.subscribe_states(receive)
            while RUNNING and client.is_connected:
                await asyncio.sleep(1)
        except Exception:
            pass
        finally:
            with state.lock:
                state.esphome_connected = False
            if callable(cancel_subscription):
                cancel_subscription()
            try:
                await client.disconnect()
            except Exception:
                pass
        if RUNNING:
            await asyncio.sleep(5)


def run_esphome_client():
    asyncio.run(esphome_loop())


def render_alarm(pulse, title, detail, communication=False):
    if communication:
        red = int(45 + pulse * 150)
    else:
        red = int(65 + pulse * 175)
    image = Image.new("RGB", (CANVAS, CANVAS), (red, 0, 7))
    draw = ImageDraw.Draw(image)
    ring = int(175 + pulse * 80)
    arc(draw, (8, 8, 232, 232), 0, 359, (ring, ring, ring), 10)
    draw.polygon(
        ((120 * SCALE, 40 * SCALE), (78 * SCALE, 109 * SCALE), (162 * SCALE, 109 * SCALE)),
        outline="white",
        width=5 * SCALE,
    )
    centered(draw, 53, "!", font(40, True), "white")
    centered(draw, 121, title, font(28, True), "white")
    # Keep long device text readable on the small round panel.
    detail = detail.replace(" · ", " ")
    if len(detail) > 23:
        detail = detail[:22] + "…"
    centered(draw, 164, detail, font(14, True), "#fff1f2")
    return image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def draw_flame(draw, phase):
    flicker = int(math.sin(phase * 2.7) * 3)
    draw.polygon(
        [
            (184 * SCALE, (77 + flicker) * SCALE),
            (178 * SCALE, 65 * SCALE),
            (183 * SCALE, 52 * SCALE),
            (190 * SCALE, 62 * SCALE),
            (195 * SCALE, 48 * SCALE),
            (202 * SCALE, 64 * SCALE),
            (201 * SCALE, 75 * SCALE),
            (194 * SCALE, 83 * SCALE),
        ],
        fill="#ff6a1a",
    )
    draw.ellipse((187 * SCALE, (64 + flicker) * SCALE, 197 * SCALE, 79 * SCALE), fill="#ffd34e")


def render_main(phase, view, values):
    pulse = (math.sin(phase) + 1) / 2
    burner_active = number(values.get("burner"), 0) > 0
    ring_colors = {
        "normal": ("#3b1b14", "#ff711f"),
        "reduced": ("#102b45", "#2997e8"),
        "hot_water": ("#0d3639", "#20c6c9"),
        "off": ("#252b2f", "#69737a"),
    }
    ring_base, ring_color = ring_colors[view]
    if burner_active:
        face_color = (int(8 + pulse * 142), int(13 + pulse * 45), int(18 - pulse * 5), 255)
    elif view == "hot_water":
        face_color = (5, 27, 31, 255)
    elif view == "reduced":
        face_color = (7, 18, 32, 255)
    else:
        face_color = (10, 15, 18, 255)

    image = Image.new("RGBA", (CANVAS, CANVAS), "#030608")
    draw = ImageDraw.Draw(image)
    arc(draw, (8, 8, 232, 232), 0, 359, ring_base, 12)
    arc(draw, (8, 8, 232, 232), 0, 359, ring_color, 10)
    draw.ellipse((28 * SCALE, 28 * SCALE, 212 * SCALE, 212 * SCALE), fill=face_color)
    if burner_active:
        draw_flame(draw, phase)

    hot_water = view == "hot_water"
    label = "SPEICHER" if hot_water else PRIMARY_LABEL
    primary = number(values.get("storage" if hot_water else "primary"))
    value_text = "--" if primary is None else str(round(primary))
    centered(draw, 55, label, font(19, True), "#d3dadd")

    value_font = font(64, True)
    box = draw.textbbox((0, 0), value_text, font=value_font)
    value_width = box[2] - box[0]
    total_width = value_width + 22 * SCALE
    value_x = (CANVAS - total_width) / 2
    draw.text((value_x, 82 * SCALE), value_text, font=value_font, fill="#f8fafc")
    draw.text((value_x + value_width + 3 * SCALE, 88 * SCALE), "°", font=font(28, True), fill="#ff8a55")

    draw.rounded_rectangle(
        (43 * SCALE, 157 * SCALE, 197 * SCALE, 198 * SCALE),
        radius=18 * SCALE,
        fill="#101b22",
        outline="#263740",
        width=2 * SCALE,
    )
    if hot_water:
        status = "LÄDT" if values.get("hot_water_active", "OFF").upper() == "ON" else "BEREIT"
        centered(draw, 165, status, font(25, True), "#8cf1e8")
    else:
        return_temp = number(values.get("return"))
        return_text = "--°" if return_temp is None else f"{round(return_temp)}°"
        draw.text((57 * SCALE, 170 * SCALE), "RL", font=font(17, True), fill="#70c7ec")
        draw.text((103 * SCALE, 159 * SCALE), return_text, font=font(31, True), fill="#edf9fc")

    return image.convert("RGB").resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="vitodens-display")
    username = os.getenv("VITO_DISPLAY_MQTT_USER", "")
    password = os.getenv("VITO_DISPLAY_MQTT_PASSWORD", "")
    if username:
        client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=2, max_delay=30)
    client.connect_async(
        os.getenv("VITO_DISPLAY_MQTT_HOST", "127.0.0.1"),
        int(os.getenv("VITO_DISPLAY_MQTT_PORT", "1883")),
        keepalive=30,
    )
    client.loop_start()
    esphome_thread = threading.Thread(target=run_esphome_client, name="esphome-reader", daemon=True)
    esphome_thread.start()

    display = GC9A01(speed_hz=int(os.getenv("VITO_DISPLAY_SPI_HZ", "40000000")))
    try:
        display.init()
        phase = 0.0
        while RUNNING:
            values, mqtt_connected, esphome_connected, last_optolink, last_esphome = state.snapshot()
            view, detail = current_view(
                values,
                mqtt_connected,
                esphome_connected,
                last_optolink,
                last_esphome,
            )
            if view == "fault":
                frame = render_alarm(pulse=(math.sin(phase) + 1) / 2, title="STÖRUNG", detail=detail)
            elif view == "communication":
                frame = render_alarm(
                    pulse=(math.sin(phase) + 1) / 2,
                    title="STÖRUNG",
                    detail=detail,
                    communication=True,
                )
            else:
                frame = render_main(phase, view, values)
            display.display(frame)
            animate = view in {"fault", "communication"} or number(values.get("burner"), 0) > 0
            phase += 0.8 if animate else 0.2
            time.sleep(0.20 if animate else 0.75)
    finally:
        client.loop_stop()
        client.disconnect()
        display.close()


if __name__ == "__main__":
    main()
