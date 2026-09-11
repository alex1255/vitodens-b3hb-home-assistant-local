#!/usr/bin/env python3
"""Dedicated MQTT actions for safe Vitodens hot-water schedule control."""

from __future__ import annotations

import json
import socket
import threading
import time
from datetime import datetime, timedelta
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import paho.mqtt.client as paho

from c_settings_adapter import settings


MQTT_BASE = settings.mqtt_topic or "vitodens"
DISCOVERY_PREFIX = "homeassistant"
ACTION_BASE = f"{MQTT_BASE}/action"
STATUS_TOPIC = f"{ACTION_BASE}/status"
LWT_TOPIC = f"{ACTION_BASE}/LWT"
STATE_FILE = Path(__file__).with_name("ww_action_state.json")
EDITOR_STATE_FILE = Path(__file__).with_name("schedule_editor_state.json")
MODE_STATE_TOPIC = f"{ACTION_BASE}/betriebsart/state"
WW_GENERATION_TOPIC = f"{MQTT_BASE}/ww_erzeugung_aktiv"
SPAR_STATE_TOPIC = f"{MQTT_BASE}/m1_sparbetrieb_roh"
PARTY_STATE_TOPIC = f"{MQTT_BASE}/m1_partybetrieb_roh"
EDITOR_BASE = f"{MQTT_BASE}/zeitprogramm_editor"
EDITOR_COMMAND_BASE = f"{ACTION_BASE}/zeitprogramm_editor"
PROFILE_MATRIX_STATE_TOPIC = f"{EDITOR_BASE}/profile_matrix/state"
PROFILE_MATRIX_ATTR_TOPIC = f"{EDITOR_BASE}/profile_matrix/attributes"
FAULT_RAW_TOPIC = f"{MQTT_BASE}/letzte_stoerung_roh"
FAULT_STATE_TOPIC = f"{MQTT_BASE}/stoerung_aktuell"
FAULT_ATTR_TOPIC = f"{MQTT_BASE}/stoerung_aktuell/attributes"
FAULT_ACTIVE_TOPIC = f"{MQTT_BASE}/stoerung_aktiv"
SCHEDULE_VIEW_HOST = "0.0.0.0"
SCHEDULE_VIEW_PORT = 8097

DEVICE = {
    "identifiers": ["vitodens_300w_b3hb_local"],
    "name": "Vitodens 300-W Lokal",
    "model": "Vitodens 300-W B3HB",
    "manufacturer": "Viessmann",
}

FAULT_CODES = {
    0x00: "Keine Störung",
    0x0F: "Wartung durchführen",
    0x10: "Kurzschluss Außentemperatursensor",
    0x18: "Unterbrechung Außentemperatursensor",
    0x19: "Fehler externer Außentemperatursensor",
    0x1D: "Störung Volumenstromsensor",
    0x1E: "Störung Volumenstromsensor",
    0x1F: "Störung Volumenstromsensor",
    0x20: "Kurzschluss Vorlaufsensor Anlage",
    0x28: "Unterbrechung Vorlaufsensor Anlage",
    0x30: "Kurzschluss Kesseltemperatursensor",
    0x38: "Unterbrechung Kesseltemperatursensor",
    0x50: "Kurzschluss Speichertemperatursensor",
    0x51: "Kurzschluss Auslauftemperatursensor",
    0x58: "Unterbrechung Speichertemperatursensor",
    0x59: "Unterbrechung Auslauftemperatursensor",
    0x90: "Solarmodul: Kurzschluss Sensor 7",
    0x91: "Solarmodul: Kurzschluss Sensor 10",
    0x92: "Solarregelung: Kurzschluss Kollektortemperatursensor",
    0x93: "Solarregelung: Kurzschluss Kollektorrücklaufsensor",
    0x94: "Solarregelung: Kurzschluss Speichertemperatursensor",
    0x98: "Solarmodul: Unterbrechung Sensor 7",
    0x99: "Solarmodul: Unterbrechung Sensor 10",
    0x9A: "Solarregelung: Unterbrechung Kollektortemperatursensor",
    0x9B: "Solarregelung: Unterbrechung Kollektorrücklaufsensor",
    0x9C: "Solarregelung: Unterbrechung Speichertemperatursensor",
    0x9E: "Solarmodul: Temperaturdifferenz-Überwachung",
    0x9F: "Solarregelung: allgemeiner Fehler",
    0xA2: "Wasserdruck zu niedrig",
    0xA3: "Abgastemperatursensor gesteckt",
    0xA4: "Anlagenmaximaldruck überschritten",
    0xA6: "Fremdstromanode nicht in Ordnung",
    0xA7: "Fehler Uhrenbaustein Bedienteil",
    0xA8: "Interne Pumpe meldet Luft",
    0xA9: "Interne Pumpe blockiert",
    0xB0: "Kurzschluss Abgastemperatursensor",
    0xB1: "Fehler Bedienteil",
    0xB4: "Interner Fehler Temperaturmessung",
    0xB5: "Interner Fehler EEPROM",
    0xB7: "Kesselcodierkarte falsch oder fehlerhaft",
    0xB8: "Unterbrechung Abgastemperatursensor",
    0xB9: "Fehlerhafte Übertragung der Codiersteckerdaten",
    0xBA: "Kommunikationsfehler Mischer HK2",
    0xBB: "Kommunikationsfehler Mischer HK3",
    0xBC: "Fehler Fernbedienung HK1",
    0xBD: "Fehler Fernbedienung HK2",
    0xBE: "Fehler Fernbedienung HK3",
    0xBF: "LON-Modul falsch oder fehlerhaft",
    0xC1: "Kommunikationsfehler Erweiterung EA1",
    0xC2: "Kommunikationsfehler Solarregelung",
    0xC3: "Kommunikationsfehler Erweiterung AM1",
    0xC4: "Kommunikationsfehler Erweiterung OpenTherm",
    0xC5: "Fehler drehzahlgeregelte interne Pumpe",
    0xC6: "Fehler drehzahlgeregelte Pumpe HK2",
    0xC7: "Fehler drehzahlgeregelte Pumpe HK1",
    0xC8: "Fehler drehzahlgeregelte Pumpe HK3",
    0xC9: "Kommunikationsfehler KM-BUS-Gerät DAP1",
    0xCA: "Kommunikationsfehler KM-BUS-Gerät DAP2",
    0xCD: "Kommunikationsfehler Vitocom 100",
    0xCE: "Kommunikationsfehler externe Anschlusserweiterung",
    0xCF: "Kommunikationsfehler LON-Modul",
    0xD1: "Brennerstörung",
    0xD6: "Störung digitaler Eingang 1",
    0xD7: "Störung digitaler Eingang 2",
    0xD8: "Störung digitaler Eingang 3",
    0xDA: "Kurzschluss Raumtemperatursensor HK1",
    0xDB: "Kurzschluss Raumtemperatursensor HK2",
    0xDC: "Kurzschluss Raumtemperatursensor HK3",
    0xDD: "Unterbrechung Raumtemperatursensor HK1",
    0xDE: "Unterbrechung Raumtemperatursensor HK2",
    0xDF: "Unterbrechung Raumtemperatursensor HK3",
    0xE0: "Fehler externer LON-Teilnehmer",
    0xE1: "SCOT-Kalibrationswert oberhalb Grenzwert",
    0xE2: "Keine Kalibration wegen mangelnder Strömung",
    0xE3: "Thermischer Kalibrationsfehler",
    0xE4: "Fehler 24-V-Spannungsversorgung Feuerungsautomat",
    0xE5: "Fehler Flammenverstärker",
    0xE6: "Mindest-Luft- oder Wasserdruck nicht erreicht",
    0xE7: "SCOT-Kalibrationswert unterhalb Grenzwert",
    0xE8: "SCOT-Ionisationssignal weicht ab",
    0xEA: "SCOT-Kalibrationswert weicht vom Vorgänger ab",
    0xEB: "SCOT-Kalibration nicht ausgeführt",
    0xEC: "SCOT-Ionisationssollwert fehlerhaft",
    0xED: "SCOT-Systemfehler",
    0xEE: "Keine Flammbildung",
    0xEF: "Flammenausfall in der Sicherheitszeit",
    0xF0: "Kommunikationsfehler zum Feuerungsautomaten",
    0xF1: "Abgastemperaturbegrenzer ausgelöst",
    0xF2: "Temperaturbegrenzer ausgelöst: Übertemperatur",
    0xF3: "Flammenvortäuschung",
    0xF4: "Keine Flammenbildung",
    0xF5: "Fehler Luftdruckwächter",
    0xF6: "Fehler Gasdruckschalter",
    0xF7: "Fehler Luftdruckschalter",
    0xF8: "Fehler Gasventil",
    0xF9: "Gebläsedrehzahl nicht erreicht",
    0xFA: "Gebläsestillstand nicht erreicht",
    0xFB: "Flammenausfall im Betrieb",
    0xFC: "Fehler elektrische Ansteuerung der Gasarmatur",
    0xFD: "Interner Fehler Feuerungsautomat",
    0xFE: "Vorwarnung: Wartung fällig",
    0xFF: "Feuerungsautomat ohne eigenen Fehlercode",
}

WEEKDAYS = [
    ("montag", 0x2100),
    ("dienstag", 0x2108),
    ("mittwoch", 0x2110),
    ("donnerstag", 0x2118),
    ("freitag", 0x2120),
    ("samstag", 0x2128),
    ("sonntag", 0x2130),
]
WEEKDAY_KEYS = [weekday for weekday, _addr in WEEKDAYS]
SCHEDULE_ADDR_BASE = {
    "hk1": 0x2000,
    "ww": 0x2100,
    "zirkulation": 0x2200,
}
SCHEDULE_ADDRS = {
    program: {weekday: base + index * 8 for index, weekday in enumerate(WEEKDAY_KEYS)}
    for program, base in SCHEDULE_ADDR_BASE.items()
}
DAY_OPTIONS = [
    ("Montag", "montag"),
    ("Dienstag", "dienstag"),
    ("Mittwoch", "mittwoch"),
    ("Donnerstag", "donnerstag"),
    ("Freitag", "freitag"),
    ("Samstag", "samstag"),
    ("Sonntag", "sonntag"),
]
DAY_LABEL_TO_KEY = {label: key for label, key in DAY_OPTIONS}
DAY_KEY_TO_LABEL = {key: label for label, key in DAY_OPTIONS}
PROFILE_OPTIONS = [
    ("Schaukelstuhl", "schaukelstuhl"),
    ("Werktag", "werktag"),
]
PROFILE_LABEL_TO_KEY = {label: key for label, key in PROFILE_OPTIONS}
PROFILE_KEY_TO_LABEL = {key: label for label, key in PROFILE_OPTIONS}
SLOT_OPTIONS = [(f"Fenster {index}", index - 1) for index in range(1, 5)]
SLOT_LABEL_TO_INDEX = {label: index for label, index in SLOT_OPTIONS}
SLOT_INDEX_TO_LABEL = {index: label for label, index in SLOT_OPTIONS}

SCHEDULE_TOPIC_PREFIXES = {
    "ww": f"{MQTT_BASE}/ww_zeitprogramm_",
    "zirkulation": f"{MQTT_BASE}/zirkulation_zeitprogramm_",
    "hk1": f"{MQTT_BASE}/hk1_zeitprogramm_",
}
EDITOR_PROGRAMS = [
    ("Heizkreis 1", "hk1"),
    ("Warmwasser", "ww"),
    ("Zirkulation", "zirkulation"),
]
PROGRAM_LABEL_TO_KEY = {label: key for label, key in EDITOR_PROGRAMS}
PROGRAM_KEY_TO_LABEL = {key: label for label, key in EDITOR_PROGRAMS}

MODE_TO_VALUE = {
    "Aus": 0,
    "Nur Warmwasser": 1,
    "Heizen und Warmwasser": 2,
}
VALUE_TO_MODE = {value: name for name, value in MODE_TO_VALUE.items()}

NUMBER_TARGETS = {
    f"{ACTION_BASE}/hk1_normaltemperatur_soll/set": {
        "addr": 0x2306,
        "name": "HK1 Normaltemperatur",
        "min": 3,
        "max": 37,
    },
    f"{ACTION_BASE}/hk1_reduzierte_temperatur_soll/set": {
        "addr": 0x2307,
        "name": "HK1 Reduzierte Temperatur",
        "min": 3,
        "max": 37,
    },
    f"{ACTION_BASE}/hk1_komforttemperatur_soll/set": {
        "addr": 0x2308,
        "name": "HK1 Komforttemperatur",
        "min": 4,
        "max": 37,
    },
    f"{ACTION_BASE}/ww_temperatur_soll/set": {
        "addr": 0x6300,
        "name": "WW Temperatur",
        "min": 10,
        "max": 60,
    },
    f"{ACTION_BASE}/hk1_heizkurve_neigung/set": {
        "addr": 0x27D3,
        "name": "HK1 Heizkennlinie Neigung",
        "min": 0.2,
        "max": 3.5,
        "scale": 0.1,
        "decimals": 1,
        "state_topic": f"{MQTT_BASE}/hk1_heizkurve_neigung",
    },
    f"{ACTION_BASE}/hk1_heizkurve_niveau/set": {
        "addr": 0x27D4,
        "name": "HK1 Heizkennlinie Niveau",
        "min": -13,
        "max": 40,
        "scale": 1,
        "decimals": 0,
        "state_topic": f"{MQTT_BASE}/hk1_heizkurve_niveau",
    },
}
EDITOR_NUMBER_FIELDS = {
    f"{EDITOR_COMMAND_BASE}/start_stunde/set": ("start_hour", 0, 23, 1),
    f"{EDITOR_COMMAND_BASE}/start_minute/set": ("start_minute", 0, 50, 10),
    f"{EDITOR_COMMAND_BASE}/ende_stunde/set": ("end_hour", 0, 24, 1),
    f"{EDITOR_COMMAND_BASE}/ende_minute/set": ("end_minute", 0, 50, 10),
}
PROFILE_NUMBER_FIELDS = {
    f"{EDITOR_COMMAND_BASE}/profil_start_stunde/set": ("profile_start_hour", 0, 23, 1),
    f"{EDITOR_COMMAND_BASE}/profil_start_minute/set": ("profile_start_minute", 0, 50, 10),
    f"{EDITOR_COMMAND_BASE}/profil_ende_stunde/set": ("profile_end_hour", 0, 24, 1),
    f"{EDITOR_COMMAND_BASE}/profil_ende_minute/set": ("profile_end_minute", 0, 50, 10),
}
EDITOR_COMMAND_TOPICS = [
    f"{EDITOR_COMMAND_BASE}/programm/set",
    f"{EDITOR_COMMAND_BASE}/tag/set",
    f"{EDITOR_COMMAND_BASE}/fenster/set",
    f"{EDITOR_COMMAND_BASE}/kopieren_von/set",
    f"{EDITOR_COMMAND_BASE}/kopieren_nach/set",
    f"{EDITOR_COMMAND_BASE}/profil/set",
    f"{EDITOR_COMMAND_BASE}/profil_zieltag/set",
    f"{EDITOR_COMMAND_BASE}/profil_fenster/set",
    f"{EDITOR_COMMAND_BASE}/profil_fenster_aktiv/set",
    f"{EDITOR_COMMAND_BASE}/fenster_aktiv/set",
    f"{EDITOR_COMMAND_BASE}/original_laden",
    f"{EDITOR_COMMAND_BASE}/entwurf_verwerfen",
    f"{EDITOR_COMMAND_BASE}/tag_kopieren",
    f"{EDITOR_COMMAND_BASE}/profil_anwenden",
    f"{EDITOR_COMMAND_BASE}/profil_anwenden_direkt",
    f"{EDITOR_COMMAND_BASE}/profil_mo_fr_anwenden",
    f"{EDITOR_COMMAND_BASE}/profil_sa_so_anwenden",
    f"{EDITOR_COMMAND_BASE}/profil_woche_anwenden",
    f"{EDITOR_COMMAND_BASE}/auswahl_als_profil_speichern",
    f"{EDITOR_COMMAND_BASE}/auswahl_uebernehmen",
    f"{EDITOR_COMMAND_BASE}/alle_entwuerfe_uebernehmen",
    f"{EDITOR_COMMAND_BASE}/alle_entwuerfe_verwerfen",
    f"{EDITOR_COMMAND_BASE}/letzte_aenderung_zurueck",
    *EDITOR_NUMBER_FIELDS.keys(),
    *PROFILE_NUMBER_FIELDS.keys(),
]

schedule_cache: dict[str, dict[str, str]] = {
    "ww": {},
    "zirkulation": {},
    "hk1": {},
}
last_speicherladepumpe = "0"
state_lock = threading.Lock()
restore_timer: threading.Timer | None = None
mqtt_client: paho.Client | None = None
editor_state: dict = {}


def publish_status(message: str) -> None:
    if mqtt_client and mqtt_client.is_connected():
        mqtt_client.publish(STATUS_TOPIC, message, retain=True)


def time_to_byte(value: str) -> int:
    hour_s, minute_s = value.split(":", 1)
    hour = int(hour_s)
    minute = int(minute_s)
    return (hour << 3) + round(minute / 10)


def byte_to_time(value: int) -> str:
    if value == 0xFF:
        return "na"
    return f"{value >> 3:02d}:{(value & 7) * 10:02d}"


def schedule_to_bytes(schedule: str) -> bytes:
    data = bytearray()
    for part in [p.strip() for p in schedule.split(",") if p.strip()]:
        start, stop = part.split("-", 1)
        if start == "na" or stop == "na":
            data.extend([0xFF, 0xFF])
        else:
            data.extend([time_to_byte(start), time_to_byte(stop)])
    return bytes((data + b"\xff" * 8)[:8])


def bytes_to_schedule(data: bytes) -> str:
    parts = []
    for i in range(0, 8, 2):
        parts.append(f"{byte_to_time(data[i])}-{byte_to_time(data[i + 1])}")
    return ",".join(parts)


def parse_windows(schedule: str) -> list[tuple[int, int]]:
    windows = []
    for part in schedule.split(","):
        part = part.strip()
        if not part or part == "na-na" or "-" not in part:
            continue
        start_s, stop_s = part.split("-", 1)
        if start_s == "na" or stop_s == "na":
            continue
        try:
            sh, sm = [int(x) for x in start_s.split(":", 1)]
            eh, em = [int(x) for x in stop_s.split(":", 1)]
        except ValueError:
            continue
        start = sh * 60 + sm
        stop = eh * 60 + em
        if stop > start:
            windows.append((start, stop))
    return windows


def windows_to_schedule(windows: list[tuple[int, int]]) -> str:
    parts = []
    for start, stop in windows[:4]:
        parts.append(f"{start // 60:02d}:{start % 60:02d}-{stop // 60:02d}:{stop % 60:02d}")
    while len(parts) < 4:
        parts.append("na-na")
    return ",".join(parts)


def merge_windows(windows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, stop in sorted(windows):
        if stop <= start:
            continue
        if not merged or start > merged[-1][1]:
            merged.append((start, stop))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], stop))
    return merged


def is_active(schedule: str, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    minutes = now.hour * 60 + now.minute
    return any(start <= minutes < stop for start, stop in parse_windows(schedule))


def tcp_request(command: str, timeout: float = 8.0) -> str:
    host = "127.0.0.1"
    port = int(settings.tcpip_port)
    last_error: OSError | None = None

    for attempt in range(1, 8):
        try:
            with socket.create_connection((host, port), timeout=timeout) as sock:
                sock.settimeout(timeout)
                sock.sendall((command.strip() + "\n").encode())
                data = b""
                while b"\n" not in data:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    data += chunk
            return data.decode(errors="replace").strip()
        except (ConnectionRefusedError, TimeoutError, OSError) as exc:
            last_error = exc
            time.sleep(min(0.25 * attempt, 1.5))

    raise ConnectionError(f"Optolink TCP nicht erreichbar auf {host}:{port}: {last_error}")


def read_schedule(addr: int) -> str:
    response = tcp_request(f"read;0x{addr:04x};8;schedvdens;false")
    parts = response.split(";", 2)
    if len(parts) != 3 or parts[0] != "1":
        raise RuntimeError(f"read failed: {response}")
    return parts[2]


def write_schedule(addr: int, schedule: str) -> str:
    payload = schedule_to_bytes(schedule).hex()
    response = tcp_request(f"writeraw;0x{addr:04x};{payload}")
    parts = response.split(";", 2)
    if len(parts) < 2 or parts[0] != "1":
        raise RuntimeError(f"write failed: {response}")
    return response


def write_integer(addr: int, value: int) -> str:
    response = tcp_request(f"write;0x{addr:04x};1;{value}")
    parts = response.split(";", 2)
    if len(parts) < 2 or parts[0] != "1":
        raise RuntimeError(f"write failed: {response}")
    return response


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.replace(STATE_FILE)


def clear_state() -> None:
    try:
        STATE_FILE.unlink()
    except FileNotFoundError:
        pass


def empty_schedule() -> str:
    return "na-na,na-na,na-na,na-na"


def safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def normalize_editor_state(state: dict | None = None) -> dict:
    current_day = DAY_KEY_TO_LABEL[WEEKDAYS[datetime.now().weekday()][0]]
    state = dict(state or {})
    if state.get("program") not in PROGRAM_LABEL_TO_KEY:
        state["program"] = "Warmwasser"
    if state.get("day") not in DAY_LABEL_TO_KEY:
        state["day"] = current_day
    if state.get("copy_from") not in DAY_LABEL_TO_KEY:
        state["copy_from"] = state["day"]
    if state.get("copy_to") not in DAY_LABEL_TO_KEY:
        state["copy_to"] = state["day"]
    if state.get("profile") not in PROFILE_LABEL_TO_KEY:
        state["profile"] = "Schaukelstuhl"
    if state.get("profile_target") not in DAY_LABEL_TO_KEY:
        state["profile_target"] = state["day"]
    if state.get("profile_slot") not in SLOT_LABEL_TO_INDEX:
        state["profile_slot"] = "Fenster 1"
    if state.get("slot") not in SLOT_LABEL_TO_INDEX:
        state["slot"] = "Fenster 1"
    state["active"] = "ON" if str(state.get("active", "OFF")).upper() in ("1", "ON", "TRUE", "YES") else "OFF"
    state["profile_active"] = (
        "ON" if str(state.get("profile_active", "OFF")).upper() in ("1", "ON", "TRUE", "YES") else "OFF"
    )
    state["start_hour"] = max(0, min(23, safe_int(state.get("start_hour", 0))))
    state["start_minute"] = max(0, min(50, safe_int(state.get("start_minute", 0)) // 10 * 10))
    state["end_hour"] = max(0, min(24, safe_int(state.get("end_hour", 0))))
    state["end_minute"] = max(0, min(50, safe_int(state.get("end_minute", 0)) // 10 * 10))
    if state["end_hour"] == 24:
        state["end_minute"] = 0
    state["profile_start_hour"] = max(0, min(23, safe_int(state.get("profile_start_hour", 0))))
    state["profile_start_minute"] = max(0, min(50, safe_int(state.get("profile_start_minute", 0)) // 10 * 10))
    state["profile_end_hour"] = max(0, min(24, safe_int(state.get("profile_end_hour", 0))))
    state["profile_end_minute"] = max(0, min(50, safe_int(state.get("profile_end_minute", 0)) // 10 * 10))
    if state["profile_end_hour"] == 24:
        state["profile_end_minute"] = 0
    state["drafts"] = dict(state.get("drafts") or {})
    profiles = state.get("profiles") or {}
    if not isinstance(profiles, dict):
        profiles = {}
    state["profiles"] = {
        program_key: dict(profiles.get(program_key) or {})
        for _program_label, program_key in EDITOR_PROGRAMS
    }
    assignments = state.get("profile_assignments") or {}
    if not isinstance(assignments, dict):
        assignments = {}
    normalized_assignments: dict[str, dict[str, str]] = {}
    for _program_label, program_key in EDITOR_PROGRAMS:
        program_assignments = assignments.get(program_key) or {}
        if not isinstance(program_assignments, dict):
            program_assignments = {}
        normalized_assignments[program_key] = {
            day_key: profile_key
            for day_key, profile_key in program_assignments.items()
            if day_key in DAY_KEY_TO_LABEL and profile_key in PROFILE_KEY_TO_LABEL
        }
    state["profile_assignments"] = normalized_assignments
    state["last_apply_backup"] = dict(state.get("last_apply_backup") or {})
    state.setdefault("status", "Zeitprogramm-Editor bereit")
    return state


def load_editor_state() -> dict:
    if not EDITOR_STATE_FILE.exists():
        return normalize_editor_state()
    try:
        return normalize_editor_state(json.loads(EDITOR_STATE_FILE.read_text()))
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return normalize_editor_state()


def save_editor_state() -> None:
    tmp = EDITOR_STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(editor_state, indent=2, sort_keys=True))
    tmp.replace(EDITOR_STATE_FILE)


def schedule_to_slots(schedule: str) -> list[tuple[int, int] | None]:
    slots: list[tuple[int, int] | None] = []
    parts = [part.strip() for part in schedule.split(",")]
    parts = (parts + ["na-na"] * 4)[:4]
    for part in parts:
        if part == "na-na" or "-" not in part:
            slots.append(None)
            continue
        start_s, stop_s = part.split("-", 1)
        if start_s == "na" or stop_s == "na":
            slots.append(None)
            continue
        try:
            sh, sm = [int(x) for x in start_s.split(":", 1)]
            eh, em = [int(x) for x in stop_s.split(":", 1)]
        except ValueError:
            slots.append(None)
            continue
        start = sh * 60 + sm
        stop = eh * 60 + em
        slots.append((start, stop) if 0 <= start < stop <= 24 * 60 else None)
    return slots


def slots_to_schedule(slots: list[tuple[int, int] | None]) -> str:
    parts = []
    for slot in (slots + [None] * 4)[:4]:
        if slot is None:
            parts.append("na-na")
            continue
        start, stop = slot
        parts.append(f"{start // 60:02d}:{start % 60:02d}-{stop // 60:02d}:{stop % 60:02d}")
    return ",".join(parts)


def validate_schedule(schedule: str) -> str:
    parts = [part.strip() for part in str(schedule).split(",")]
    if len(parts) != 4:
        raise ValueError("Zeitprogramm muss genau vier Fenster enthalten")
    windows: list[tuple[int, int]] = []
    for part in parts:
        if part == "na-na":
            continue
        if "-" not in part:
            raise ValueError(f"Ungültiges Zeitfenster: {part}")
        start_s, stop_s = part.split("-", 1)
        try:
            sh, sm = [int(x) for x in start_s.split(":", 1)]
            eh, em = [int(x) for x in stop_s.split(":", 1)]
        except ValueError as exc:
            raise ValueError(f"Ungültiges Zeitfenster: {part}") from exc
        start = sh * 60 + sm
        stop = eh * 60 + em
        windows.append((start, stop))
    for start, stop in windows:
        if start % 10 or stop % 10:
            raise ValueError("Zeiten müssen im 10-Minuten-Raster liegen")
        if start == 24 * 60:
            raise ValueError("Start darf nicht 24:00 sein")
        if not 0 <= start < stop <= 24 * 60:
            raise ValueError("Zeitfenster muss innerhalb eines Tages liegen")
    merged = merge_windows(windows)
    if len(merged) != len(windows):
        raise ValueError("Zeitfenster dürfen sich nicht überlappen")
    if len(merged) > 4:
        raise ValueError("Maximal vier Zeitfenster pro Tag sind erlaubt")
    return windows_to_schedule(merged)


def schedule_topic(program_key: str, day_key: str) -> str:
    return f"{SCHEDULE_TOPIC_PREFIXES[program_key]}{day_key}"


def editor_draft_keys() -> list[tuple[str, str, str]]:
    drafts = normalize_editor_state(editor_state).get("drafts", {})
    keys: list[tuple[str, str, str]] = []
    for key, draft in drafts.items():
        if ":" not in key:
            continue
        program_key, day_key = key.split(":", 1)
        if program_key in SCHEDULE_ADDRS and day_key in SCHEDULE_ADDRS[program_key]:
            keys.append((program_key, day_key, str(draft)))
    return sorted(keys, key=lambda item: (item[0], WEEKDAY_KEYS.index(item[1])))


def selected_editor_keys() -> tuple[str, str, int]:
    state = normalize_editor_state(editor_state)
    return (
        PROGRAM_LABEL_TO_KEY[state["program"]],
        DAY_LABEL_TO_KEY[state["day"]],
        SLOT_LABEL_TO_INDEX[state["slot"]],
    )


def selected_editor_key() -> str:
    program_key, day_key, _slot_index = selected_editor_keys()
    return f"{program_key}:{day_key}"


def get_original_schedule(program_key: str, day_key: str) -> str:
    return schedule_cache.get(program_key, {}).get(day_key) or empty_schedule()


def get_effective_schedule(program_key: str, day_key: str) -> str:
    key = f"{program_key}:{day_key}"
    return editor_state.get("drafts", {}).get(key) or get_original_schedule(program_key, day_key)


def selected_profile_keys() -> tuple[str, str, str]:
    state = normalize_editor_state(editor_state)
    return (
        PROGRAM_LABEL_TO_KEY[state["program"]],
        PROFILE_LABEL_TO_KEY[state["profile"]],
        DAY_LABEL_TO_KEY[state["profile_target"]],
    )


def selected_profile_slot_index() -> int:
    state = normalize_editor_state(editor_state)
    return SLOT_LABEL_TO_INDEX[state["profile_slot"]]


def first_known_schedule(program_key: str) -> str:
    for day_key in WEEKDAY_KEYS:
        schedule = schedule_cache.get(program_key, {}).get(day_key)
        if schedule:
            return validate_schedule(schedule)
    return ""


def get_profile_schedule(program_key: str, profile_key: str) -> str:
    schedule = editor_state.get("profiles", {}).get(program_key, {}).get(profile_key)
    if schedule:
        return validate_schedule(str(schedule))
    if profile_key == "schaukelstuhl":
        return first_known_schedule(program_key)
    return ""


def matching_profile_label(program_key: str, schedule: str) -> str:
    try:
        normalized = validate_schedule(schedule)
    except ValueError:
        return "Unbekannt"
    for profile_label, profile_key in PROFILE_OPTIONS:
        try:
            profile_schedule = get_profile_schedule(program_key, profile_key)
        except ValueError:
            profile_schedule = ""
        if profile_schedule and validate_schedule(profile_schedule) == normalized:
            return profile_label
    return "Individuell"


def effective_profile_label(program_key: str, day_key: str, schedule: str) -> str:
    try:
        normalized = validate_schedule(schedule)
    except ValueError:
        return "Unbekannt"
    assignment = normalize_editor_state(editor_state).get("profile_assignments", {}).get(program_key, {}).get(day_key)
    if assignment in PROFILE_KEY_TO_LABEL:
        try:
            assigned_schedule = get_profile_schedule(program_key, assignment)
        except ValueError:
            assigned_schedule = ""
        if assigned_schedule and validate_schedule(assigned_schedule) == normalized:
            return PROFILE_KEY_TO_LABEL[assignment]
    return matching_profile_label(program_key, normalized)


def profile_matrix_payload() -> dict:
    programs: dict[str, dict] = {}
    drafts = normalize_editor_state(editor_state).get("drafts", {})
    for program_label, program_key in EDITOR_PROGRAMS:
        profiles: dict[str, str] = {}
        for profile_label, profile_key in PROFILE_OPTIONS:
            try:
                schedule = get_profile_schedule(program_key, profile_key)
            except ValueError:
                schedule = ""
            profiles[profile_label] = schedule or ""

        days: dict[str, dict] = {}
        for day_label, day_key in DAY_OPTIONS:
            original = get_original_schedule(program_key, day_key)
            draft_key = f"{program_key}:{day_key}"
            effective = drafts.get(draft_key) or original
            days[day_key] = {
                "label": day_label,
                "original": original,
                "effective": effective,
                "draft": draft_key in drafts,
                "profile": effective_profile_label(program_key, day_key, effective) if effective else "Keine Daten",
            }

        programs[program_key] = {
            "label": program_label,
            "profiles": profiles,
            "days": days,
        }

    return {
        "updated": datetime.now().isoformat(timespec="seconds"),
        "draft_count": len(editor_draft_keys()),
        "profile_labels": [label for label, _key in PROFILE_OPTIONS],
        "programs": programs,
    }


def get_profile_edit_schedule(program_key: str, profile_key: str) -> str:
    return get_profile_schedule(program_key, profile_key) or empty_schedule()


def set_profile_schedule(program_key: str, profile_key: str, schedule: str) -> str:
    normalized = validate_schedule(schedule)
    editor_state.setdefault("profiles", {}).setdefault(program_key, {})[profile_key] = normalized
    return normalized


def apply_profile_to_days(day_keys: list[str]) -> None:
    state = normalize_editor_state(editor_state)
    editor_state.update(state)
    program_key, profile_key, _target_day = selected_profile_keys()
    schedule = get_profile_schedule(program_key, profile_key)
    if not schedule:
        editor_state["status"] = (
            f"Profil {state['profile']} hat für {PROGRAM_KEY_TO_LABEL[program_key]} noch keinen Zeitplan"
        )
        save_editor_state()
        return

    normalized = validate_schedule(schedule)
    changed_days: list[str] = []
    cleared_days: list[str] = []
    for day_key in day_keys:
        if day_key not in DAY_KEY_TO_LABEL:
            continue
        editor_state.setdefault("profile_assignments", {}).setdefault(program_key, {})[day_key] = profile_key
        target_key = f"{program_key}:{day_key}"
        original = get_original_schedule(program_key, day_key)
        if normalized == original:
            editor_state.get("drafts", {}).pop(target_key, None)
            cleared_days.append(DAY_KEY_TO_LABEL[day_key])
        else:
            editor_state.setdefault("drafts", {})[target_key] = normalized
            changed_days.append(DAY_KEY_TO_LABEL[day_key])

    if day_keys:
        editor_state["day"] = DAY_KEY_TO_LABEL[day_keys[0]]
    load_selected_editor_slot()

    if changed_days:
        editor_state["status"] = (
            f"Profil {state['profile']} als Entwurf gesetzt für: {', '.join(changed_days)}"
        )
    elif cleared_days:
        editor_state["status"] = f"Profil {state['profile']} entspricht bereits: {', '.join(cleared_days)}"
    else:
        editor_state["status"] = "Kein gültiger Zieltag für Profil-Anwendung"
    save_editor_state()


def apply_profile_direct(payload: str) -> None:
    try:
        request = json.loads(payload)
    except json.JSONDecodeError:
        editor_state["status"] = "Profil-Direktanwendung ungültig: kein JSON"
        save_editor_state()
        return

    program_value = str(request.get("program") or "")
    day_value = str(request.get("day") or "")
    profile_value = str(request.get("profile") or "")
    program_key = program_value if program_value in PROGRAM_KEY_TO_LABEL else PROGRAM_LABEL_TO_KEY.get(program_value)
    day_key = day_value if day_value in DAY_KEY_TO_LABEL else DAY_LABEL_TO_KEY.get(day_value)
    profile_key = profile_value if profile_value in PROFILE_KEY_TO_LABEL else PROFILE_LABEL_TO_KEY.get(profile_value)
    if not program_key or not day_key or not profile_key:
        editor_state["status"] = "Profil-Direktanwendung ungültig: Programm, Tag oder Profil unbekannt"
        save_editor_state()
        return

    editor_state["program"] = PROGRAM_KEY_TO_LABEL[program_key]
    editor_state["day"] = DAY_KEY_TO_LABEL[day_key]
    editor_state["profile"] = PROFILE_KEY_TO_LABEL[profile_key]
    editor_state["profile_target"] = DAY_KEY_TO_LABEL[day_key]
    load_selected_profile_slot()
    apply_profile_to_days([day_key])


def save_selected_day_as_profile() -> None:
    state = normalize_editor_state(editor_state)
    editor_state.update(state)
    program_key, profile_key, _target_day = selected_profile_keys()
    source_day = DAY_LABEL_TO_KEY[state["day"]]
    schedule = get_effective_schedule(program_key, source_day)
    normalized = set_profile_schedule(program_key, profile_key, schedule)
    editor_state.setdefault("profile_assignments", {}).setdefault(program_key, {})[source_day] = profile_key
    editor_state["status"] = (
        f"{PROGRAM_KEY_TO_LABEL[program_key]} {state['day']} als Profil {state['profile']} gespeichert: "
        f"{normalized}"
    )
    save_editor_state()


def load_selected_profile_slot() -> None:
    program_key, profile_key, _target_day = selected_profile_keys()
    slots = schedule_to_slots(get_profile_edit_schedule(program_key, profile_key))
    slot = slots[selected_profile_slot_index()]
    if slot is None:
        editor_state.update(
            {
                "profile_active": "OFF",
                "profile_start_hour": 0,
                "profile_start_minute": 0,
                "profile_end_hour": 0,
                "profile_end_minute": 0,
            }
        )
        return
    start, stop = slot
    editor_state.update(
        {
            "profile_active": "ON",
            "profile_start_hour": start // 60,
            "profile_start_minute": start % 60,
            "profile_end_hour": stop // 60,
            "profile_end_minute": stop % 60,
        }
    )


def update_profile_from_controls() -> None:
    state = normalize_editor_state(editor_state)
    editor_state.update(state)
    program_key, profile_key, _target_day = selected_profile_keys()
    slots = schedule_to_slots(get_profile_edit_schedule(program_key, profile_key))
    active = str(editor_state.get("profile_active", "OFF")).upper() == "ON"
    if active:
        start = int(editor_state["profile_start_hour"]) * 60 + int(editor_state["profile_start_minute"])
        stop = int(editor_state["profile_end_hour"]) * 60 + int(editor_state["profile_end_minute"])
        if int(editor_state["profile_end_hour"]) == 24:
            stop = 24 * 60
        if stop <= start:
            editor_state["status"] = "Profil ungültig: Ende muss nach Start liegen"
            save_editor_state()
            return
        slots[selected_profile_slot_index()] = (start, stop)
    else:
        slots[selected_profile_slot_index()] = None

    try:
        normalized = set_profile_schedule(program_key, profile_key, slots_to_schedule(slots))
    except ValueError as exc:
        editor_state["status"] = f"Profil ungültig: {exc}"
        save_editor_state()
        return

    editor_state["status"] = (
        f"Profil {state['profile']} für {PROGRAM_KEY_TO_LABEL[program_key]} gespeichert: {normalized}"
    )
    save_editor_state()


def get_draft_schedule() -> str:
    program_key, day_key, _slot_index = selected_editor_keys()
    key = selected_editor_key()
    return editor_state.get("drafts", {}).get(key) or get_original_schedule(program_key, day_key)


def load_selected_editor_slot() -> None:
    _program_key, _day_key, slot_index = selected_editor_keys()
    slots = schedule_to_slots(get_draft_schedule())
    slot = slots[slot_index]
    if slot is None:
        editor_state.update({"active": "OFF", "start_hour": 0, "start_minute": 0, "end_hour": 0, "end_minute": 0})
        return
    start, stop = slot
    editor_state.update(
        {
            "active": "ON",
            "start_hour": start // 60,
            "start_minute": start % 60,
            "end_hour": stop // 60,
            "end_minute": stop % 60,
        }
    )


def update_editor_draft_from_controls() -> None:
    program_key, day_key, slot_index = selected_editor_keys()
    original = get_original_schedule(program_key, day_key)
    slots = schedule_to_slots(get_draft_schedule())
    active = str(editor_state.get("active", "OFF")).upper() == "ON"
    if active:
        start = int(editor_state["start_hour"]) * 60 + int(editor_state["start_minute"])
        stop = int(editor_state["end_hour"]) * 60 + int(editor_state["end_minute"])
        if int(editor_state["end_hour"]) == 24:
            stop = 24 * 60
        if stop <= start:
            editor_state["status"] = "Entwurf ungültig: Ende muss nach Start liegen"
            save_editor_state()
            return
        slots[slot_index] = (start, stop)
    else:
        slots[slot_index] = None

    draft = slots_to_schedule(slots)
    if draft == original:
        editor_state.get("drafts", {}).pop(selected_editor_key(), None)
        editor_state["status"] = "Entwurf entspricht dem aktuellen Zeitprogramm"
    else:
        editor_state.setdefault("drafts", {})[selected_editor_key()] = draft
        editor_state["status"] = "Entwurf aktualisiert; noch nicht an die Heizung geschrieben"
    save_editor_state()


def discard_selected_editor_draft() -> None:
    editor_state.get("drafts", {}).pop(selected_editor_key(), None)
    load_selected_editor_slot()
    editor_state["status"] = "Entwurf verworfen; aktuelles Zeitprogramm geladen"
    save_editor_state()


def discard_all_editor_drafts() -> None:
    count = len(editor_draft_keys())
    editor_state["drafts"] = {}
    load_selected_editor_slot()
    editor_state["status"] = (
        f"{count} Entwurf{' wurde' if count == 1 else 'e wurden'} verworfen"
        if count
        else "Keine offenen Entwuerfe vorhanden"
    )
    save_editor_state()


def copy_editor_day() -> None:
    state = normalize_editor_state(editor_state)
    editor_state.update(state)
    program_key = PROGRAM_LABEL_TO_KEY[state["program"]]
    source_day = DAY_LABEL_TO_KEY[state["copy_from"]]
    target_day = DAY_LABEL_TO_KEY[state["copy_to"]]

    source_schedule = get_effective_schedule(program_key, source_day)
    target_original = get_original_schedule(program_key, target_day)
    target_key = f"{program_key}:{target_day}"

    if source_day == target_day:
        editor_state["status"] = "Quelle und Ziel sind gleich; nichts kopiert"
    elif source_schedule == target_original:
        editor_state.get("drafts", {}).pop(target_key, None)
        editor_state["status"] = (
            f"{PROGRAM_KEY_TO_LABEL[program_key]} {state['copy_from']} entspricht bereits {state['copy_to']}"
        )
    else:
        editor_state.setdefault("drafts", {})[target_key] = source_schedule
        editor_state["status"] = (
            f"{PROGRAM_KEY_TO_LABEL[program_key]} {state['copy_from']} auf {state['copy_to']} "
            "in den Entwurf kopiert; noch nicht an die Heizung geschrieben"
        )

    editor_state["day"] = state["copy_to"]
    load_selected_editor_slot()
    save_editor_state()


def apply_editor_drafts(client: paho.Client, only_selected: bool) -> None:
    selected_key = selected_editor_key()
    candidates = []
    for program_key, day_key, draft in editor_draft_keys():
        if only_selected and f"{program_key}:{day_key}" != selected_key:
            continue
        candidates.append((program_key, day_key, validate_schedule(draft)))

    if not candidates:
        editor_state["status"] = "Kein geänderter Entwurf zum Übernehmen vorhanden"
        save_editor_state()
        return

    live_originals: dict[str, str] = {}
    for program_key, day_key, _draft in candidates:
        addr = SCHEDULE_ADDRS[program_key][day_key]
        live = validate_schedule(read_schedule(addr))
        cached = validate_schedule(get_original_schedule(program_key, day_key))
        if live != cached:
            schedule_cache[program_key][day_key] = live
            client.publish(schedule_topic(program_key, day_key), live, retain=True)
            editor_state["status"] = (
                f"Abgebrochen: {PROGRAM_KEY_TO_LABEL[program_key]} {DAY_KEY_TO_LABEL[day_key]} "
                "wurde extern geändert. Bitte Entwurf prüfen."
            )
            save_editor_state()
            return
        live_originals[f"{program_key}:{day_key}"] = live

    applied: list[str] = []
    for program_key, day_key, draft in candidates:
        addr = SCHEDULE_ADDRS[program_key][day_key]
        write_schedule(addr, draft)
        confirmed = validate_schedule(read_schedule(addr))
        schedule_cache[program_key][day_key] = confirmed
        client.publish(schedule_topic(program_key, day_key), confirmed, retain=True)
        editor_state.get("drafts", {}).pop(f"{program_key}:{day_key}", None)
        applied.append(f"{PROGRAM_KEY_TO_LABEL[program_key]} {DAY_KEY_TO_LABEL[day_key]}")

    editor_state["last_apply_backup"] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "originals": live_originals,
    }
    load_selected_editor_slot()
    editor_state["status"] = "Übernommen: " + ", ".join(applied)
    save_editor_state()


def restore_last_editor_apply(client: paho.Client) -> None:
    backup = normalize_editor_state(editor_state).get("last_apply_backup", {})
    originals = backup.get("originals", {})
    if not originals:
        editor_state["status"] = "Keine letzte Zeitprogramm-Änderung zum Wiederherstellen vorhanden"
        save_editor_state()
        return

    restored: list[str] = []
    for key, schedule in sorted(originals.items()):
        if ":" not in key:
            continue
        program_key, day_key = key.split(":", 1)
        if program_key not in SCHEDULE_ADDRS or day_key not in SCHEDULE_ADDRS[program_key]:
            continue
        normalized = validate_schedule(str(schedule))
        write_schedule(SCHEDULE_ADDRS[program_key][day_key], normalized)
        confirmed = validate_schedule(read_schedule(SCHEDULE_ADDRS[program_key][day_key]))
        schedule_cache[program_key][day_key] = confirmed
        client.publish(schedule_topic(program_key, day_key), confirmed, retain=True)
        editor_state.get("drafts", {}).pop(key, None)
        restored.append(f"{PROGRAM_KEY_TO_LABEL[program_key]} {DAY_KEY_TO_LABEL[day_key]}")

    editor_state["last_apply_backup"] = {}
    load_selected_editor_slot()
    editor_state["status"] = "Letzte Änderung wiederhergestellt: " + ", ".join(restored)
    save_editor_state()


def publish_editor_state(client: paho.Client) -> None:
    state = normalize_editor_state(editor_state)
    editor_state.update(state)
    program_key, day_key, _slot_index = selected_editor_keys()
    original = get_original_schedule(program_key, day_key)
    draft = get_draft_schedule()
    changed = draft != original
    draft_count = len(editor_draft_keys())
    backup = state.get("last_apply_backup", {})
    backup_created = str(backup.get("created_at") or "Keine")
    values = {
        "programm/state": state["program"],
        "tag/state": state["day"],
        "fenster/state": state["slot"],
        "kopieren_von/state": state["copy_from"],
        "kopieren_nach/state": state["copy_to"],
        "profil/state": state["profile"],
        "profil_zieltag/state": state["profile_target"],
        "profil_fenster/state": state["profile_slot"],
        "profil_fenster_aktiv/state": state["profile_active"],
        "fenster_aktiv/state": state["active"],
        "start_stunde/state": str(state["start_hour"]),
        "start_minute/state": str(state["start_minute"]),
        "ende_stunde/state": str(state["end_hour"]),
        "ende_minute/state": str(state["end_minute"]),
        "profil_start_stunde/state": str(state["profile_start_hour"]),
        "profil_start_minute/state": str(state["profile_start_minute"]),
        "profil_ende_stunde/state": str(state["profile_end_hour"]),
        "profil_ende_minute/state": str(state["profile_end_minute"]),
        "original/state": original,
        "entwurf/state": draft,
        "status/state": state["status"],
        "geaendert/state": "ON" if changed else "OFF",
        "anzahl_entwuerfe/state": str(draft_count),
        "letzte_sicherung/state": backup_created,
        "profil_plan/state": get_profile_schedule(program_key, PROFILE_LABEL_TO_KEY[state["profile"]]) or "Nicht gespeichert",
    }
    for suffix, value in values.items():
        client.publish(f"{EDITOR_BASE}/{suffix}", value, retain=True)
    matrix = profile_matrix_payload()
    client.publish(PROFILE_MATRIX_STATE_TOPIC, matrix["updated"], retain=True)
    client.publish(PROFILE_MATRIX_ATTR_TOPIC, json.dumps(matrix, ensure_ascii=False), retain=True)


def handle_editor_command(client: paho.Client, topic: str, payload: str) -> bool:
    if topic == f"{EDITOR_COMMAND_BASE}/programm/set":
        if payload not in PROGRAM_LABEL_TO_KEY:
            editor_state["status"] = f"Unbekanntes Zeitprogramm: {payload}"
        else:
            editor_state["program"] = payload
            load_selected_editor_slot()
            load_selected_profile_slot()
            editor_state["status"] = f"Zeitprogramm gewählt: {payload}"
        save_editor_state()
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/tag/set":
        if payload not in DAY_LABEL_TO_KEY:
            editor_state["status"] = f"Unbekannter Tag: {payload}"
        else:
            editor_state["day"] = payload
            load_selected_editor_slot()
            editor_state["status"] = f"Tag gewählt: {payload}"
        save_editor_state()
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/fenster/set":
        if payload not in SLOT_LABEL_TO_INDEX:
            editor_state["status"] = f"Unbekanntes Zeitfenster: {payload}"
        else:
            editor_state["slot"] = payload
            load_selected_editor_slot()
            editor_state["status"] = f"Zeitfenster gewählt: {payload}"
        save_editor_state()
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/kopieren_von/set":
        if payload not in DAY_LABEL_TO_KEY:
            editor_state["status"] = f"Unbekannter Quelltag: {payload}"
        else:
            editor_state["copy_from"] = payload
            editor_state["status"] = f"Kopierquelle gewählt: {payload}"
        save_editor_state()
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/kopieren_nach/set":
        if payload not in DAY_LABEL_TO_KEY:
            editor_state["status"] = f"Unbekannter Zieltag: {payload}"
        else:
            editor_state["copy_to"] = payload
            editor_state["status"] = f"Kopierziel gewählt: {payload}"
        save_editor_state()
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/profil/set":
        if payload not in PROFILE_LABEL_TO_KEY:
            editor_state["status"] = f"Unbekanntes Profil: {payload}"
        else:
            editor_state["profile"] = payload
            load_selected_profile_slot()
            editor_state["status"] = f"Profil gewählt: {payload}"
        save_editor_state()
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/profil_zieltag/set":
        if payload not in DAY_LABEL_TO_KEY:
            editor_state["status"] = f"Unbekannter Profil-Zieltag: {payload}"
        else:
            editor_state["profile_target"] = payload
            editor_state["status"] = f"Profil-Zieltag gewählt: {payload}"
        save_editor_state()
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/profil_fenster/set":
        if payload not in SLOT_LABEL_TO_INDEX:
            editor_state["status"] = f"Unbekanntes Profil-Zeitfenster: {payload}"
        else:
            editor_state["profile_slot"] = payload
            load_selected_profile_slot()
            editor_state["status"] = f"Profil-Zeitfenster gewählt: {payload}"
        save_editor_state()
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/profil_fenster_aktiv/set":
        editor_state["profile_active"] = "ON" if payload.upper() in ("1", "ON", "TRUE", "YES") else "OFF"
        update_profile_from_controls()
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/fenster_aktiv/set":
        editor_state["active"] = "ON" if payload.upper() in ("1", "ON", "TRUE", "YES") else "OFF"
        update_editor_draft_from_controls()
        publish_editor_state(client)
        return True

    if topic in EDITOR_NUMBER_FIELDS:
        field, minimum, maximum, step = EDITOR_NUMBER_FIELDS[topic]
        value = max(minimum, min(maximum, safe_int(payload, safe_int(editor_state.get(field, minimum), minimum))))
        if step > 1:
            value = value // step * step
        editor_state[field] = value
        editor_state.update(normalize_editor_state(editor_state))
        if editor_state.get("active") == "ON":
            update_editor_draft_from_controls()
        else:
            editor_state["status"] = "Zeitwert geändert; Fenster ist aktuell deaktiviert"
            save_editor_state()
        publish_editor_state(client)
        return True

    if topic in PROFILE_NUMBER_FIELDS:
        field, minimum, maximum, step = PROFILE_NUMBER_FIELDS[topic]
        value = max(minimum, min(maximum, safe_int(payload, safe_int(editor_state.get(field, minimum), minimum))))
        if step > 1:
            value = value // step * step
        editor_state[field] = value
        editor_state.update(normalize_editor_state(editor_state))
        if editor_state.get("profile_active") == "ON":
            update_profile_from_controls()
        else:
            editor_state["status"] = "Profil-Zeitwert geändert; Profil-Fenster ist aktuell deaktiviert"
            save_editor_state()
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/original_laden":
        discard_selected_editor_draft()
        editor_state["status"] = "Original für Auswahl geladen; nichts an die Heizung geschrieben"
        save_editor_state()
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/entwurf_verwerfen":
        discard_selected_editor_draft()
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/tag_kopieren":
        copy_editor_day()
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/auswahl_als_profil_speichern":
        save_selected_day_as_profile()
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/profil_anwenden":
        _program_key, _profile_key, target_day = selected_profile_keys()
        apply_profile_to_days([target_day])
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/profil_anwenden_direkt":
        apply_profile_direct(payload)
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/profil_mo_fr_anwenden":
        apply_profile_to_days(WEEKDAY_KEYS[:5])
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/profil_sa_so_anwenden":
        apply_profile_to_days(WEEKDAY_KEYS[5:])
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/profil_woche_anwenden":
        apply_profile_to_days(WEEKDAY_KEYS)
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/auswahl_uebernehmen":
        apply_editor_drafts(client, only_selected=True)
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/alle_entwuerfe_uebernehmen":
        apply_editor_drafts(client, only_selected=False)
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/alle_entwuerfe_verwerfen":
        discard_all_editor_drafts()
        publish_editor_state(client)
        return True

    if topic == f"{EDITOR_COMMAND_BASE}/letzte_aenderung_zurueck":
        restore_last_editor_apply(client)
        publish_editor_state(client)
        return True

    return False


def schedule_percent(minutes: int) -> float:
    return max(0, min(100, minutes / (24 * 60) * 100))


def render_schedule_bar(program_key: str, schedule: str) -> str:
    if program_key == "hk1":
        base_class = "reduced"
        segment_class = "normal"
        segment_label = "Normal"
    elif program_key == "ww":
        base_class = "idle"
        segment_class = "hotwater"
        segment_label = "WW"
    else:
        base_class = "idle"
        segment_class = "circulation"
        segment_label = "Zirk"

    segments = []
    for start, stop in parse_windows(schedule):
        left = schedule_percent(start)
        width = max(0, schedule_percent(stop) - left)
        label = segment_label if width >= 5 else ""
        segments.append(
            f'<span class="segment {segment_class}" style="left:{left:.4f}%;width:{width:.4f}%">'
            f"{escape(label)}</span>"
        )

    if program_key == "hk1":
        base_label = '<span class="base-label left">Reduziert</span><span class="base-label right">Reduziert</span>'
    else:
        base_label = ""
    return f'<div class="bar {base_class}">{base_label}{"".join(segments)}</div>'


def render_schedule_row(program_key: str, day_label: str, day_key: str, today_key: str) -> str:
    schedule = get_effective_schedule(program_key, day_key)
    original = get_original_schedule(program_key, day_key)
    changed = schedule != original
    today = ' <span class="today">(Heute)</span>' if day_key == today_key else ""
    changed_marker = '<span class="draft">Entwurf</span>' if changed else ""
    missing_marker = '<span class="draft muted">keine Daten</span>' if not schedule_cache.get(program_key, {}).get(day_key) else ""
    return (
        '<article class="day-row">'
        f'<div class="day-head"><div class="day-name">{escape(day_label)}{today}</div>{changed_marker}{missing_marker}</div>'
        '<div class="axis-labels"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div>'
        '<div class="ticks"></div>'
        f"{render_schedule_bar(program_key, schedule)}"
        f'<div class="raw">{escape(schedule)}</div>'
        "</article>"
    )


def render_program_section(program_key: str, program_label: str, today_key: str) -> str:
    rows = [
        render_schedule_row(program_key, day_label, day_key, today_key)
        for day_label, day_key in DAY_OPTIONS
    ]
    return (
        f'<section class="program" id="{escape(program_key)}">'
        f'<h2>{escape(program_label)}</h2>'
        f'{"".join(rows)}'
        "</section>"
    )


def render_schedule_page(selected_program: str = "all") -> str:
    selected_program = selected_program if selected_program in {"all", "hk1", "ww", "zirkulation"} else "all"
    today_key = WEEKDAYS[datetime.now().weekday()][0]
    visible_programs = [
        (label, key)
        for label, key in EDITOR_PROGRAMS
        if selected_program in ("all", key)
    ]
    nav_items = [("Alle", "all"), *[(label, key) for label, key in EDITOR_PROGRAMS]]
    nav = "".join(
        f'<a class="chip {"active" if selected_program == key else ""}" href="/schedules?program={escape(key)}">{escape(label)}</a>'
        for label, key in nav_items
    )
    sections = "".join(
        render_program_section(program_key, program_label, today_key)
        for program_label, program_key in visible_programs
    )
    generated = datetime.now().strftime("%H:%M:%S")
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>Vitodens Zeitprogramme</title>
<style>
:root {{
  color-scheme: light dark;
  --bg: #f6f7f8;
  --panel: #ffffff;
  --text: #202124;
  --muted: #667085;
  --line: #dde1e6;
  --tick: #a8afb8;
  --idle: #eceff1;
  --reduced: #2ea7ee;
  --normal: #ff8a3d;
  --hotwater: #ff8a3d;
  --circulation: #19a78f;
  --draft: #7a4cff;
  --shadow: 0 1px 2px rgba(16, 24, 40, .06), 0 1px 3px rgba(16, 24, 40, .1);
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #111418;
    --panel: #1a1f25;
    --text: #eef2f6;
    --muted: #a9b2bd;
    --line: #303842;
    --tick: #667085;
    --idle: #313842;
    --shadow: none;
  }}
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 15px/1.35 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
}}
.page {{
  max-width: 1040px;
  margin: 0 auto;
  padding: 14px;
}}
.top {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}}
h1 {{
  font-size: 20px;
  margin: 0;
  font-weight: 700;
}}
.updated {{
  color: var(--muted);
  font-size: 13px;
  white-space: nowrap;
}}
.nav {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}}
.chip {{
  display: inline-flex;
  min-height: 34px;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 6px 13px;
  color: var(--text);
  text-decoration: none;
  background: var(--panel);
}}
.chip.active {{
  background: #1f6feb;
  border-color: #1f6feb;
  color: white;
}}
.program {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
  margin-bottom: 14px;
  overflow: hidden;
}}
h2 {{
  margin: 0;
  padding: 11px 14px;
  background: color-mix(in srgb, var(--line) 48%, transparent);
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: .02em;
  color: var(--muted);
}}
.day-row {{
  padding: 13px 14px 12px;
  border-top: 1px solid var(--line);
}}
.day-head {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 24px;
  margin-bottom: 6px;
}}
.day-name {{
  font-size: 17px;
  font-weight: 600;
}}
.today {{
  color: var(--muted);
  font-weight: 500;
}}
.draft {{
  border-radius: 999px;
  padding: 3px 8px;
  background: color-mix(in srgb, var(--draft) 16%, transparent);
  color: var(--draft);
  font-size: 12px;
  font-weight: 700;
}}
.draft.muted {{
  background: transparent;
  color: var(--muted);
}}
.axis-labels {{
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  color: var(--muted);
  font-size: 13px;
  margin-bottom: 3px;
}}
.axis-labels span:nth-child(1) {{ text-align: left; }}
.axis-labels span:nth-child(2),
.axis-labels span:nth-child(3),
.axis-labels span:nth-child(4) {{ text-align: center; }}
.axis-labels span:nth-child(5) {{ text-align: right; }}
.ticks {{
  height: 10px;
  background:
    repeating-linear-gradient(to right, transparent 0, transparent calc(4.1667% - 1px), var(--tick) calc(4.1667% - 1px), var(--tick) 4.1667%),
    linear-gradient(to right, var(--tick), var(--tick));
  background-size: 100% 5px, 100% 1px;
  background-position: left bottom, left bottom;
  background-repeat: no-repeat;
  opacity: .65;
}}
.bar {{
  position: relative;
  height: 30px;
  border-radius: 3px;
  overflow: hidden;
  background: var(--idle);
  box-shadow: inset 0 0 0 1px rgba(0,0,0,.05);
}}
.bar.reduced {{ background: var(--reduced); }}
.segment {{
  position: absolute;
  top: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 2px;
  color: white;
  font-size: 12px;
  font-weight: 700;
  overflow: hidden;
}}
.normal {{ background: var(--normal); }}
.hotwater {{ background: var(--hotwater); }}
.circulation {{ background: var(--circulation); }}
.base-label {{
  position: absolute;
  z-index: 1;
  top: 50%;
  transform: translateY(-50%);
  color: white;
  font-size: 11px;
  font-weight: 700;
  opacity: .95;
}}
.base-label.left {{ left: 12px; }}
.base-label.right {{ right: 12px; }}
.raw {{
  margin-top: 6px;
  color: var(--muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
@media (max-width: 520px) {{
  .page {{ padding: 10px; }}
  .top {{ align-items: flex-start; flex-direction: column; }}
  .axis-labels {{ font-size: 12px; }}
  .day-name {{ font-size: 16px; }}
  .bar {{ height: 28px; }}
  .base-label, .segment {{ font-size: 10px; }}
}}
</style>
</head>
<body>
<main class="page">
  <div class="top">
    <h1>Zeitprogramme</h1>
    <div class="updated">Aktualisiert {escape(generated)}</div>
  </div>
  <nav class="nav">{nav}</nav>
  {sections}
</main>
</body>
</html>"""


def schedule_snapshot() -> dict:
    return {
        program_key: {day_key: get_effective_schedule(program_key, day_key) for _label, day_key in DAY_OPTIONS}
        for _program_label, program_key in EDITOR_PROGRAMS
    }


class ScheduleViewHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/schedules":
            body = json.dumps(schedule_snapshot(), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path not in ("/", "/schedules"):
            self.send_error(404)
            return

        selected = parse_qs(parsed.query).get("program", ["all"])[0]
        body = render_schedule_page(selected).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args) -> None:
        return


def start_schedule_view_server() -> ThreadingHTTPServer | None:
    try:
        server = ThreadingHTTPServer((SCHEDULE_VIEW_HOST, SCHEDULE_VIEW_PORT), ScheduleViewHandler)
    except OSError as exc:
        publish_status(f"Zeitprogramm-Balkenanzeige nicht gestartet: {exc}")
        return None

    thread = threading.Thread(target=server.serve_forever, name="schedule-view", daemon=True)
    thread.start()
    return server


def schedule_restore(state: dict) -> None:
    global restore_timer
    if restore_timer:
        restore_timer.cancel()
    restore_at = float(state.get("restore_at", 0))
    delay = max(0, restore_at - time.time())
    restore_timer = threading.Timer(delay, restore_original_schedule)
    restore_timer.daemon = True
    restore_timer.start()


def restore_original_schedule() -> None:
    with state_lock:
        state = load_state()
        if not state:
            publish_status("Kein temporäres WW-Zeitprogramm zur Wiederherstellung vorgemerkt")
            return
        addr = int(state["addr"])
        original_schedule = state["original_schedule"]
        weekday = state.get("weekday", "heute")
        write_schedule(addr, original_schedule)
        clear_state()
    publish_status(
        f"WW-Zeitprogramm {weekday} wiederhergestellt; laufende Speicherladung endet geregelt: "
        f"{original_schedule}"
    )


def rounded_window(minutes: int, now: datetime | None = None) -> tuple[int, int]:
    now = now or datetime.now()
    start = now.hour * 60 + (now.minute // 10) * 10
    end_dt = now + timedelta(minutes=minutes)
    end = end_dt.hour * 60 + ((end_dt.minute + 9) // 10) * 10
    if end_dt.date() != now.date():
        end = 23 * 60 + 50
    end = min(end, 23 * 60 + 50)
    if end <= start:
        end = min(start + 10, 23 * 60 + 50)
    return start, end


def hot_water_now(minutes: int) -> None:
    with state_lock:
        today_name, today_addr = WEEKDAYS[datetime.now().weekday()]
        state = load_state()
        if state:
            original_schedule = state["original_schedule"]
        else:
            original_schedule = read_schedule(today_addr)
        if is_active(original_schedule):
            publish_status(f"WW-Zeitfenster {today_name} ist bereits aktiv: {original_schedule}")
            return

        start, stop = rounded_window(minutes)
        new_schedule = windows_to_schedule(merge_windows(parse_windows(original_schedule) + [(start, stop)]))
        write_schedule(today_addr, new_schedule)

        state = {
            "addr": today_addr,
            "weekday": today_name,
            "original_schedule": original_schedule,
            "temporary_schedule": new_schedule,
            "restore_at": time.time() + minutes * 60,
        }
        save_state(state)
        schedule_restore(state)
    publish_status(f"WW-Ladung gestartet ({minutes} min Freigabe): {today_name} {new_schedule}")


def set_mode(mode: str) -> None:
    if mode not in MODE_TO_VALUE:
        raise ValueError(f"Unbekannte Betriebsart: {mode}")
    write_integer(0x2323, MODE_TO_VALUE[mode])
    if mqtt_client:
        mqtt_client.publish(MODE_STATE_TOPIC, mode, retain=True)
    publish_status(f"Betriebsart gesetzt: {mode}")


def set_switch(name: str, addr: int, topic: str, payload: str) -> None:
    value = 1 if payload.upper() in ("1", "ON", "TRUE", "YES") else 0
    write_integer(addr, value)
    if mqtt_client:
        mqtt_client.publish(topic, "1" if value else "0", retain=True)
    publish_status(f"{name}: {'ein' if value else 'aus'}")


def set_number(topic: str, payload: str) -> None:
    target = NUMBER_TARGETS[topic]
    value = float(payload)
    value = max(target["min"], min(target["max"], value))
    scale = target.get("scale", 1)
    raw_value = int(round(value / scale))
    write_integer(target["addr"], raw_value)
    decimals = target.get("decimals", 0)
    display_value = f"{value:.{decimals}f}"
    if mqtt_client and target.get("state_topic"):
        mqtt_client.publish(target["state_topic"], display_value, retain=True)
    unit = " °C" if "temperatur" in target["name"].lower() else ""
    publish_status(f"{target['name']} gesetzt: {display_value}{unit}")


def publish_discovery(client: paho.Client) -> None:
    availability = {"availability_topic": LWT_TOPIC}
    entities = [
        (
            "sensor",
            "stoerung_aktuell",
            {
                "name": "Störung aktuell",
                "unique_id": "vitodens_stoerung_aktuell",
                "default_entity_id": "sensor.vitodens_stoerung_aktuell",
                "state_topic": FAULT_STATE_TOPIC,
                "json_attributes_topic": FAULT_ATTR_TOPIC,
                "icon": "mdi:alert-circle-outline",
            },
        ),
        (
            "binary_sensor",
            "stoerung_aktiv",
            {
                "name": "Störung aktiv",
                "unique_id": "vitodens_stoerung_aktiv",
                "default_entity_id": "binary_sensor.vitodens_stoerung_aktiv",
                "state_topic": FAULT_ACTIVE_TOPIC,
                "payload_on": "ON",
                "payload_off": "OFF",
                "device_class": "problem",
                "icon": "mdi:alert",
            },
        ),
        (
            "select",
            "betriebsart",
            {
                "name": "Betriebsart",
                "unique_id": "vitodens_betriebsart",
                "default_entity_id": "select.vitodens_betriebsart",
                "state_topic": MODE_STATE_TOPIC,
                "command_topic": f"{ACTION_BASE}/betriebsart/set",
                "options": list(MODE_TO_VALUE.keys()),
                "icon": "mdi:thermostat",
            },
        ),
        (
            "switch",
            "sparbetrieb_dauerhaft",
            {
                "name": "Sparbetrieb Dauerhaft",
                "unique_id": "vitodens_sparbetrieb_dauerhaft",
                "default_entity_id": "switch.vitodens_sparbetrieb_dauerhaft",
                "state_topic": SPAR_STATE_TOPIC,
                "command_topic": f"{ACTION_BASE}/sparbetrieb/set",
                "payload_on": "1",
                "payload_off": "0",
                "state_on": "1",
                "state_off": "0",
                "icon": "mdi:weather-night",
            },
        ),
        (
            "switch",
            "partybetrieb_dauerhaft",
            {
                "name": "Partybetrieb Dauerhaft",
                "unique_id": "vitodens_partybetrieb_dauerhaft",
                "default_entity_id": "switch.vitodens_partybetrieb_dauerhaft",
                "state_topic": PARTY_STATE_TOPIC,
                "command_topic": f"{ACTION_BASE}/partybetrieb/set",
                "payload_on": "1",
                "payload_off": "0",
                "state_on": "1",
                "state_off": "0",
                "icon": "mdi:white-balance-sunny",
            },
        ),
        (
            "button",
            "ww_jetzt_30_min",
            {
                "name": "WW-Ladung Start 30 Min",
                "unique_id": "vitodens_ww_jetzt_30_min",
                "default_entity_id": "button.vitodens_ww_jetzt_30_min",
                "command_topic": f"{ACTION_BASE}/ww_now_30",
                "payload_press": "PRESS",
                "icon": "mdi:water-boiler",
            },
        ),
        (
            "button",
            "ww_jetzt_60_min",
            {
                "name": "WW-Ladung Start 60 Min",
                "unique_id": "vitodens_ww_jetzt_60_min",
                "default_entity_id": "button.vitodens_ww_jetzt_60_min",
                "command_topic": f"{ACTION_BASE}/ww_now_60",
                "payload_press": "PRESS",
                "icon": "mdi:water-boiler",
            },
        ),
        (
            "button",
            "ww_zeitprogramm_wiederherstellen",
            {
                "name": "WW Zeitprogramm zurück",
                "unique_id": "vitodens_ww_zeitprogramm_wiederherstellen",
                "default_entity_id": "button.vitodens_ww_zeitprogramm_wiederherstellen",
                "command_topic": f"{ACTION_BASE}/ww_restore",
                "payload_press": "PRESS",
                "icon": "mdi:restore",
            },
        ),
        (
            "sensor",
            "betriebsart_klartext",
            {
                "name": "Betriebsart Klartext",
                "unique_id": "vitodens_betriebsart_klartext",
                "default_entity_id": "sensor.vitodens_betriebsart_klartext",
                "state_topic": MODE_STATE_TOPIC,
                "icon": "mdi:thermostat",
            },
        ),
        (
            "sensor",
            "ww_aktion_status",
            {
                "name": "WW Aktion Status",
                "unique_id": "vitodens_ww_aktion_status",
                "default_entity_id": "sensor.vitodens_ww_aktion_status",
                "state_topic": STATUS_TOPIC,
                "icon": "mdi:message-text-clock",
            },
        ),
        (
            "binary_sensor",
            "ww_erzeugung_aktiv",
            {
                "name": "WW Erzeugung Aktiv",
                "unique_id": "vitodens_ww_erzeugung_aktiv",
                "default_entity_id": "binary_sensor.vitodens_ww_erzeugung_aktiv",
                "state_topic": WW_GENERATION_TOPIC,
                "payload_on": "ON",
                "payload_off": "OFF",
                "device_class": "running",
                "icon": "mdi:water-boiler",
            },
        ),
        (
            "binary_sensor",
            "ww_zeitfenster_aktiv",
            {
                "name": "WW Zeitfenster Aktiv",
                "unique_id": "vitodens_ww_zeitfenster_aktiv",
                "default_entity_id": "binary_sensor.vitodens_ww_zeitfenster_aktiv",
                "state_topic": f"{MQTT_BASE}/ww_zeitfenster_aktiv",
                "payload_on": "ON",
                "payload_off": "OFF",
                "icon": "mdi:calendar-check",
            },
        ),
        (
            "binary_sensor",
            "zirkulation_zeitfenster_aktiv",
            {
                "name": "Zirkulation Zeitfenster Aktiv",
                "unique_id": "vitodens_zirkulation_zeitfenster_aktiv",
                "default_entity_id": "binary_sensor.vitodens_zirkulation_zeitfenster_aktiv",
                "state_topic": f"{MQTT_BASE}/zirkulation_zeitfenster_aktiv",
                "payload_on": "ON",
                "payload_off": "OFF",
                "icon": "mdi:calendar-check",
            },
        ),
        (
            "number",
            "hk1_normaltemperatur_soll",
            {
                "name": "HK1 Normaltemperatur Soll",
                "unique_id": "vitodens_hk1_normaltemperatur_soll_number",
                "default_entity_id": "number.vitodens_hk1_normaltemperatur_soll",
                "state_topic": f"{MQTT_BASE}/hk1_normaltemperatur_soll",
                "command_topic": f"{ACTION_BASE}/hk1_normaltemperatur_soll/set",
                "min": 3,
                "max": 37,
                "step": 1,
                "mode": "box",
                "unit_of_measurement": "°C",
                "device_class": "temperature",
                "icon": "mdi:thermometer-lines",
            },
        ),
        (
            "number",
            "hk1_reduzierte_temperatur_soll",
            {
                "name": "HK1 Reduzierte Temperatur Soll",
                "unique_id": "vitodens_hk1_reduzierte_temperatur_soll_number",
                "default_entity_id": "number.vitodens_hk1_reduzierte_temperatur_soll",
                "state_topic": f"{MQTT_BASE}/hk1_reduzierte_temperatur_soll",
                "command_topic": f"{ACTION_BASE}/hk1_reduzierte_temperatur_soll/set",
                "min": 3,
                "max": 37,
                "step": 1,
                "mode": "box",
                "unit_of_measurement": "°C",
                "device_class": "temperature",
                "icon": "mdi:thermometer-lines",
            },
        ),
        (
            "number",
            "hk1_komforttemperatur_soll",
            {
                "name": "HK1 Komforttemperatur Soll",
                "unique_id": "vitodens_hk1_komforttemperatur_soll_number",
                "default_entity_id": "number.vitodens_hk1_komforttemperatur_soll",
                "state_topic": f"{MQTT_BASE}/hk1_komforttemperatur_soll",
                "command_topic": f"{ACTION_BASE}/hk1_komforttemperatur_soll/set",
                "min": 4,
                "max": 37,
                "step": 1,
                "mode": "box",
                "unit_of_measurement": "°C",
                "device_class": "temperature",
                "icon": "mdi:thermometer-lines",
            },
        ),
        (
            "number",
            "ww_temperatur_soll",
            {
                "name": "WW Temperatur Soll",
                "unique_id": "vitodens_ww_temperatur_soll_number",
                "default_entity_id": "number.vitodens_ww_temperatur_soll",
                "state_topic": f"{MQTT_BASE}/warmwasser_temperatur_soll",
                "command_topic": f"{ACTION_BASE}/ww_temperatur_soll/set",
                "min": 10,
                "max": 60,
                "step": 1,
                "mode": "box",
                "unit_of_measurement": "°C",
                "device_class": "temperature",
                "icon": "mdi:water-thermometer",
            },
        ),
        (
            "number",
            "hk1_heizkurve_neigung",
            {
                "name": "HK1 Heizkennlinie Neigung",
                "unique_id": "vitodens_hk1_heizkurve_neigung_number",
                "default_entity_id": "number.vitodens_hk1_heizkurve_neigung",
                "state_topic": f"{MQTT_BASE}/hk1_heizkurve_neigung",
                "command_topic": f"{ACTION_BASE}/hk1_heizkurve_neigung/set",
                "min": 0.2,
                "max": 3.5,
                "step": 0.1,
                "mode": "box",
                "icon": "mdi:slope-uphill",
            },
        ),
        (
            "number",
            "hk1_heizkurve_niveau",
            {
                "name": "HK1 Heizkennlinie Niveau",
                "unique_id": "vitodens_hk1_heizkurve_niveau_number",
                "default_entity_id": "number.vitodens_hk1_heizkurve_niveau",
                "state_topic": f"{MQTT_BASE}/hk1_heizkurve_niveau",
                "command_topic": f"{ACTION_BASE}/hk1_heizkurve_niveau/set",
                "min": -13,
                "max": 40,
                "step": 1,
                "mode": "box",
                "icon": "mdi:plus-minus-variant",
            },
        ),
        (
            "binary_sensor",
            "hk1_zeitfenster_aktiv",
            {
                "name": "HK1 Zeitfenster Aktiv",
                "unique_id": "vitodens_hk1_zeitfenster_aktiv",
                "default_entity_id": "binary_sensor.vitodens_hk1_zeitfenster_aktiv",
                "state_topic": f"{MQTT_BASE}/hk1_zeitfenster_aktiv",
                "payload_on": "ON",
                "payload_off": "OFF",
                "icon": "mdi:calendar-check",
            },
        ),
        (
            "select",
            "zeitprogramm_editor_programm",
            {
                "name": "Zeitprogramm Editor Programm",
                "unique_id": "vitodens_zeitprogramm_editor_programm",
                "default_entity_id": "select.vitodens_zeitprogramm_editor_programm",
                "state_topic": f"{EDITOR_BASE}/programm/state",
                "command_topic": f"{EDITOR_COMMAND_BASE}/programm/set",
                "options": [label for label, _key in EDITOR_PROGRAMS],
                "icon": "mdi:calendar-edit",
            },
        ),
        (
            "select",
            "zeitprogramm_editor_tag",
            {
                "name": "Zeitprogramm Editor Tag",
                "unique_id": "vitodens_zeitprogramm_editor_tag",
                "default_entity_id": "select.vitodens_zeitprogramm_editor_tag",
                "state_topic": f"{EDITOR_BASE}/tag/state",
                "command_topic": f"{EDITOR_COMMAND_BASE}/tag/set",
                "options": [label for label, _key in DAY_OPTIONS],
                "icon": "mdi:calendar-week",
            },
        ),
        (
            "select",
            "zeitprogramm_editor_fenster",
            {
                "name": "Zeitprogramm Editor Fenster",
                "unique_id": "vitodens_zeitprogramm_editor_fenster",
                "default_entity_id": "select.vitodens_zeitprogramm_editor_fenster",
                "state_topic": f"{EDITOR_BASE}/fenster/state",
                "command_topic": f"{EDITOR_COMMAND_BASE}/fenster/set",
                "options": [label for label, _index in SLOT_OPTIONS],
                "icon": "mdi:calendar-clock",
            },
        ),
        (
            "select",
            "zeitprogramm_editor_kopieren_von",
            {
                "name": "Zeitprogramm Editor Kopieren Von",
                "unique_id": "vitodens_zeitprogramm_editor_kopieren_von",
                "default_entity_id": "select.vitodens_zeitprogramm_editor_kopieren_von",
                "state_topic": f"{EDITOR_BASE}/kopieren_von/state",
                "command_topic": f"{EDITOR_COMMAND_BASE}/kopieren_von/set",
                "options": [label for label, _key in DAY_OPTIONS],
                "icon": "mdi:content-copy",
            },
        ),
        (
            "select",
            "zeitprogramm_editor_kopieren_nach",
            {
                "name": "Zeitprogramm Editor Kopieren Nach",
                "unique_id": "vitodens_zeitprogramm_editor_kopieren_nach",
                "default_entity_id": "select.vitodens_zeitprogramm_editor_kopieren_nach",
                "state_topic": f"{EDITOR_BASE}/kopieren_nach/state",
                "command_topic": f"{EDITOR_COMMAND_BASE}/kopieren_nach/set",
                "options": [label for label, _key in DAY_OPTIONS],
                "icon": "mdi:content-paste",
            },
        ),
        (
            "select",
            "zeitprogramm_editor_profil",
            {
                "name": "Zeitprogramm Editor Profil",
                "unique_id": "vitodens_zeitprogramm_editor_profil",
                "default_entity_id": "select.vitodens_zeitprogramm_editor_profil",
                "state_topic": f"{EDITOR_BASE}/profil/state",
                "command_topic": f"{EDITOR_COMMAND_BASE}/profil/set",
                "options": [label for label, _key in PROFILE_OPTIONS],
                "icon": "mdi:bookmark-box-multiple",
            },
        ),
        (
            "select",
            "zeitprogramm_editor_profil_zieltag",
            {
                "name": "Zeitprogramm Editor Profil Zieltag",
                "unique_id": "vitodens_zeitprogramm_editor_profil_zieltag",
                "default_entity_id": "select.vitodens_zeitprogramm_editor_profil_zieltag",
                "state_topic": f"{EDITOR_BASE}/profil_zieltag/state",
                "command_topic": f"{EDITOR_COMMAND_BASE}/profil_zieltag/set",
                "options": [label for label, _key in DAY_OPTIONS],
                "icon": "mdi:calendar-arrow-right",
            },
        ),
        (
            "select",
            "zeitprogramm_editor_profil_fenster",
            {
                "name": "Zeitprogramm Editor Profil Fenster",
                "unique_id": "vitodens_zeitprogramm_editor_profil_fenster",
                "default_entity_id": "select.vitodens_zeitprogramm_editor_profil_fenster",
                "state_topic": f"{EDITOR_BASE}/profil_fenster/state",
                "command_topic": f"{EDITOR_COMMAND_BASE}/profil_fenster/set",
                "options": [label for label, _index in SLOT_OPTIONS],
                "icon": "mdi:calendar-clock",
            },
        ),
        (
            "switch",
            "zeitprogramm_editor_fenster_aktiv",
            {
                "name": "Zeitprogramm Editor Fenster Aktiv",
                "unique_id": "vitodens_zeitprogramm_editor_fenster_aktiv",
                "default_entity_id": "switch.vitodens_zeitprogramm_editor_fenster_aktiv",
                "state_topic": f"{EDITOR_BASE}/fenster_aktiv/state",
                "command_topic": f"{EDITOR_COMMAND_BASE}/fenster_aktiv/set",
                "payload_on": "ON",
                "payload_off": "OFF",
                "state_on": "ON",
                "state_off": "OFF",
                "icon": "mdi:toggle-switch",
            },
        ),
        (
            "switch",
            "zeitprogramm_editor_profil_fenster_aktiv",
            {
                "name": "Zeitprogramm Editor Profil Fenster Aktiv",
                "unique_id": "vitodens_zeitprogramm_editor_profil_fenster_aktiv",
                "default_entity_id": "switch.vitodens_zeitprogramm_editor_profil_fenster_aktiv",
                "state_topic": f"{EDITOR_BASE}/profil_fenster_aktiv/state",
                "command_topic": f"{EDITOR_COMMAND_BASE}/profil_fenster_aktiv/set",
                "payload_on": "ON",
                "payload_off": "OFF",
                "state_on": "ON",
                "state_off": "OFF",
                "icon": "mdi:toggle-switch",
            },
        ),
        (
            "number",
            "zeitprogramm_editor_start_stunde",
            {
                "name": "Zeitprogramm Editor Start Stunde",
                "unique_id": "vitodens_zeitprogramm_editor_start_stunde",
                "default_entity_id": "number.vitodens_zeitprogramm_editor_start_stunde",
                "state_topic": f"{EDITOR_BASE}/start_stunde/state",
                "command_topic": f"{EDITOR_COMMAND_BASE}/start_stunde/set",
                "min": 0,
                "max": 23,
                "step": 1,
                "mode": "box",
                "icon": "mdi:clock-start",
            },
        ),
        (
            "number",
            "zeitprogramm_editor_start_minute",
            {
                "name": "Zeitprogramm Editor Start Minute",
                "unique_id": "vitodens_zeitprogramm_editor_start_minute",
                "default_entity_id": "number.vitodens_zeitprogramm_editor_start_minute",
                "state_topic": f"{EDITOR_BASE}/start_minute/state",
                "command_topic": f"{EDITOR_COMMAND_BASE}/start_minute/set",
                "min": 0,
                "max": 50,
                "step": 10,
                "mode": "box",
                "icon": "mdi:clock-start",
            },
        ),
        (
            "number",
            "zeitprogramm_editor_ende_stunde",
            {
                "name": "Zeitprogramm Editor Ende Stunde",
                "unique_id": "vitodens_zeitprogramm_editor_ende_stunde",
                "default_entity_id": "number.vitodens_zeitprogramm_editor_ende_stunde",
                "state_topic": f"{EDITOR_BASE}/ende_stunde/state",
                "command_topic": f"{EDITOR_COMMAND_BASE}/ende_stunde/set",
                "min": 0,
                "max": 24,
                "step": 1,
                "mode": "box",
                "icon": "mdi:clock-end",
            },
        ),
        (
            "number",
            "zeitprogramm_editor_ende_minute",
            {
                "name": "Zeitprogramm Editor Ende Minute",
                "unique_id": "vitodens_zeitprogramm_editor_ende_minute",
                "default_entity_id": "number.vitodens_zeitprogramm_editor_ende_minute",
                "state_topic": f"{EDITOR_BASE}/ende_minute/state",
                "command_topic": f"{EDITOR_COMMAND_BASE}/ende_minute/set",
                "min": 0,
                "max": 50,
                "step": 10,
                "mode": "box",
                "icon": "mdi:clock-end",
            },
        ),
        (
            "number",
            "zeitprogramm_editor_profil_start_stunde",
            {
                "name": "Zeitprogramm Editor Profil Start Stunde",
                "unique_id": "vitodens_zeitprogramm_editor_profil_start_stunde",
                "default_entity_id": "number.vitodens_zeitprogramm_editor_profil_start_stunde",
                "state_topic": f"{EDITOR_BASE}/profil_start_stunde/state",
                "command_topic": f"{EDITOR_COMMAND_BASE}/profil_start_stunde/set",
                "min": 0,
                "max": 23,
                "step": 1,
                "mode": "box",
                "icon": "mdi:clock-start",
            },
        ),
        (
            "number",
            "zeitprogramm_editor_profil_start_minute",
            {
                "name": "Zeitprogramm Editor Profil Start Minute",
                "unique_id": "vitodens_zeitprogramm_editor_profil_start_minute",
                "default_entity_id": "number.vitodens_zeitprogramm_editor_profil_start_minute",
                "state_topic": f"{EDITOR_BASE}/profil_start_minute/state",
                "command_topic": f"{EDITOR_COMMAND_BASE}/profil_start_minute/set",
                "min": 0,
                "max": 50,
                "step": 10,
                "mode": "box",
                "icon": "mdi:clock-start",
            },
        ),
        (
            "number",
            "zeitprogramm_editor_profil_ende_stunde",
            {
                "name": "Zeitprogramm Editor Profil Ende Stunde",
                "unique_id": "vitodens_zeitprogramm_editor_profil_ende_stunde",
                "default_entity_id": "number.vitodens_zeitprogramm_editor_profil_ende_stunde",
                "state_topic": f"{EDITOR_BASE}/profil_ende_stunde/state",
                "command_topic": f"{EDITOR_COMMAND_BASE}/profil_ende_stunde/set",
                "min": 0,
                "max": 24,
                "step": 1,
                "mode": "box",
                "icon": "mdi:clock-end",
            },
        ),
        (
            "number",
            "zeitprogramm_editor_profil_ende_minute",
            {
                "name": "Zeitprogramm Editor Profil Ende Minute",
                "unique_id": "vitodens_zeitprogramm_editor_profil_ende_minute",
                "default_entity_id": "number.vitodens_zeitprogramm_editor_profil_ende_minute",
                "state_topic": f"{EDITOR_BASE}/profil_ende_minute/state",
                "command_topic": f"{EDITOR_COMMAND_BASE}/profil_ende_minute/set",
                "min": 0,
                "max": 50,
                "step": 10,
                "mode": "box",
                "icon": "mdi:clock-end",
            },
        ),
        (
            "button",
            "zeitprogramm_editor_original_laden",
            {
                "name": "Zeitprogramm Editor Original Laden",
                "unique_id": "vitodens_zeitprogramm_editor_original_laden",
                "default_entity_id": "button.vitodens_zeitprogramm_editor_original_laden",
                "command_topic": f"{EDITOR_COMMAND_BASE}/original_laden",
                "payload_press": "PRESS",
                "icon": "mdi:database-import",
            },
        ),
        (
            "button",
            "zeitprogramm_editor_entwurf_verwerfen",
            {
                "name": "Zeitprogramm Editor Entwurf Verwerfen",
                "unique_id": "vitodens_zeitprogramm_editor_entwurf_verwerfen",
                "default_entity_id": "button.vitodens_zeitprogramm_editor_entwurf_verwerfen",
                "command_topic": f"{EDITOR_COMMAND_BASE}/entwurf_verwerfen",
                "payload_press": "PRESS",
                "icon": "mdi:delete-restore",
            },
        ),
        (
            "button",
            "zeitprogramm_editor_tag_kopieren",
            {
                "name": "Zeitprogramm Editor Tag Kopieren",
                "unique_id": "vitodens_zeitprogramm_editor_tag_kopieren",
                "default_entity_id": "button.vitodens_zeitprogramm_editor_tag_kopieren",
                "command_topic": f"{EDITOR_COMMAND_BASE}/tag_kopieren",
                "payload_press": "PRESS",
                "icon": "mdi:content-copy",
            },
        ),
        (
            "button",
            "zeitprogramm_editor_auswahl_als_profil_speichern",
            {
                "name": "Zeitprogramm Editor Auswahl Als Profil Speichern",
                "unique_id": "vitodens_zeitprogramm_editor_auswahl_als_profil_speichern",
                "default_entity_id": "button.vitodens_zeitprogramm_editor_auswahl_als_profil_speichern",
                "command_topic": f"{EDITOR_COMMAND_BASE}/auswahl_als_profil_speichern",
                "payload_press": "PRESS",
                "icon": "mdi:content-save-cog",
            },
        ),
        (
            "button",
            "zeitprogramm_editor_profil_anwenden",
            {
                "name": "Zeitprogramm Editor Profil Anwenden",
                "unique_id": "vitodens_zeitprogramm_editor_profil_anwenden",
                "default_entity_id": "button.vitodens_zeitprogramm_editor_profil_anwenden",
                "command_topic": f"{EDITOR_COMMAND_BASE}/profil_anwenden",
                "payload_press": "PRESS",
                "icon": "mdi:calendar-import",
            },
        ),
        (
            "button",
            "zeitprogramm_editor_profil_mo_fr_anwenden",
            {
                "name": "Zeitprogramm Editor Profil Mo-Fr Anwenden",
                "unique_id": "vitodens_zeitprogramm_editor_profil_mo_fr_anwenden",
                "default_entity_id": "button.vitodens_zeitprogramm_editor_profil_mo_fr_anwenden",
                "command_topic": f"{EDITOR_COMMAND_BASE}/profil_mo_fr_anwenden",
                "payload_press": "PRESS",
                "icon": "mdi:calendar-week-begin",
            },
        ),
        (
            "button",
            "zeitprogramm_editor_profil_sa_so_anwenden",
            {
                "name": "Zeitprogramm Editor Profil Sa-So Anwenden",
                "unique_id": "vitodens_zeitprogramm_editor_profil_sa_so_anwenden",
                "default_entity_id": "button.vitodens_zeitprogramm_editor_profil_sa_so_anwenden",
                "command_topic": f"{EDITOR_COMMAND_BASE}/profil_sa_so_anwenden",
                "payload_press": "PRESS",
                "icon": "mdi:calendar-weekend",
            },
        ),
        (
            "button",
            "zeitprogramm_editor_profil_woche_anwenden",
            {
                "name": "Zeitprogramm Editor Profil Woche Anwenden",
                "unique_id": "vitodens_zeitprogramm_editor_profil_woche_anwenden",
                "default_entity_id": "button.vitodens_zeitprogramm_editor_profil_woche_anwenden",
                "command_topic": f"{EDITOR_COMMAND_BASE}/profil_woche_anwenden",
                "payload_press": "PRESS",
                "icon": "mdi:calendar-sync",
            },
        ),
        (
            "button",
            "zeitprogramm_editor_auswahl_uebernehmen",
            {
                "name": "Zeitprogramm Editor Auswahl Übernehmen",
                "unique_id": "vitodens_zeitprogramm_editor_auswahl_uebernehmen",
                "default_entity_id": "button.vitodens_zeitprogramm_editor_auswahl_uebernehmen",
                "command_topic": f"{EDITOR_COMMAND_BASE}/auswahl_uebernehmen",
                "payload_press": "PRESS",
                "icon": "mdi:database-arrow-up",
            },
        ),
        (
            "button",
            "zeitprogramm_editor_alle_entwuerfe_uebernehmen",
            {
                "name": "Zeitprogramm Editor Alle Entwürfe Übernehmen",
                "unique_id": "vitodens_zeitprogramm_editor_alle_entwuerfe_uebernehmen",
                "default_entity_id": "button.vitodens_zeitprogramm_editor_alle_entwuerfe_uebernehmen",
                "command_topic": f"{EDITOR_COMMAND_BASE}/alle_entwuerfe_uebernehmen",
                "payload_press": "PRESS",
                "icon": "mdi:database-sync",
            },
        ),
        (
            "button",
            "zeitprogramm_editor_letzte_aenderung_zurueck",
            {
                "name": "Zeitprogramm Editor Letzte Änderung Zurück",
                "unique_id": "vitodens_zeitprogramm_editor_letzte_aenderung_zurueck",
                "default_entity_id": "button.vitodens_zeitprogramm_editor_letzte_aenderung_zurueck",
                "command_topic": f"{EDITOR_COMMAND_BASE}/letzte_aenderung_zurueck",
                "payload_press": "PRESS",
                "icon": "mdi:restore-alert",
            },
        ),
        (
            "sensor",
            "zeitprogramm_editor_original",
            {
                "name": "Zeitprogramm Editor Original",
                "unique_id": "vitodens_zeitprogramm_editor_original",
                "default_entity_id": "sensor.vitodens_zeitprogramm_editor_original",
                "state_topic": f"{EDITOR_BASE}/original/state",
                "icon": "mdi:calendar-text",
            },
        ),
        (
            "sensor",
            "zeitprogramm_editor_entwurf",
            {
                "name": "Zeitprogramm Editor Entwurf",
                "unique_id": "vitodens_zeitprogramm_editor_entwurf",
                "default_entity_id": "sensor.vitodens_zeitprogramm_editor_entwurf",
                "state_topic": f"{EDITOR_BASE}/entwurf/state",
                "icon": "mdi:calendar-edit",
            },
        ),
        (
            "sensor",
            "zeitprogramm_editor_profil_plan",
            {
                "name": "Zeitprogramm Editor Profil Plan",
                "unique_id": "vitodens_zeitprogramm_editor_profil_plan",
                "default_entity_id": "sensor.vitodens_zeitprogramm_editor_profil_plan",
                "state_topic": f"{EDITOR_BASE}/profil_plan/state",
                "icon": "mdi:bookmark-check",
            },
        ),
        (
            "sensor",
            "zeitprogramm_profile_matrix",
            {
                "name": "Zeitprogramm Profil Matrix",
                "unique_id": "vitodens_zeitprogramm_profile_matrix",
                "default_entity_id": "sensor.vitodens_zeitprogramm_profile_matrix",
                "state_topic": PROFILE_MATRIX_STATE_TOPIC,
                "json_attributes_topic": PROFILE_MATRIX_ATTR_TOPIC,
                "icon": "mdi:table-clock",
            },
        ),
        (
            "sensor",
            "zeitprogramm_editor_status",
            {
                "name": "Zeitprogramm Editor Status",
                "unique_id": "vitodens_zeitprogramm_editor_status",
                "default_entity_id": "sensor.vitodens_zeitprogramm_editor_status",
                "state_topic": f"{EDITOR_BASE}/status/state",
                "icon": "mdi:message-processing",
            },
        ),
        (
            "sensor",
            "zeitprogramm_editor_anzahl_entwuerfe",
            {
                "name": "Zeitprogramm Editor Anzahl Entwürfe",
                "unique_id": "vitodens_zeitprogramm_editor_anzahl_entwuerfe",
                "default_entity_id": "sensor.vitodens_zeitprogramm_editor_anzahl_entwuerfe",
                "state_topic": f"{EDITOR_BASE}/anzahl_entwuerfe/state",
                "icon": "mdi:counter",
            },
        ),
        (
            "sensor",
            "zeitprogramm_editor_letzte_sicherung",
            {
                "name": "Zeitprogramm Editor Letzte Sicherung",
                "unique_id": "vitodens_zeitprogramm_editor_letzte_sicherung",
                "default_entity_id": "sensor.vitodens_zeitprogramm_editor_letzte_sicherung",
                "state_topic": f"{EDITOR_BASE}/letzte_sicherung/state",
                "icon": "mdi:backup-restore",
            },
        ),
        (
            "binary_sensor",
            "zeitprogramm_editor_entwurf_geaendert",
            {
                "name": "Zeitprogramm Editor Entwurf Geändert",
                "unique_id": "vitodens_zeitprogramm_editor_entwurf_geaendert",
                "default_entity_id": "binary_sensor.vitodens_zeitprogramm_editor_entwurf_geaendert",
                "state_topic": f"{EDITOR_BASE}/geaendert/state",
                "payload_on": "ON",
                "payload_off": "OFF",
                "icon": "mdi:file-compare",
            },
        ),
    ]
    for domain, object_id, payload in entities:
        payload = {**payload, **availability, "device": DEVICE}
        topic = f"{DISCOVERY_PREFIX}/{domain}/vitodens/{object_id}/config"
        client.publish(topic, json.dumps(payload), retain=True)


def publish_active_states(client: paho.Client) -> None:
    weekday = WEEKDAYS[datetime.now().weekday()][0]
    for key in ("ww", "zirkulation", "hk1"):
        schedule = schedule_cache[key].get(weekday)
        if schedule:
            state = "ON" if is_active(schedule) else "OFF"
            client.publish(f"{MQTT_BASE}/{key}_zeitfenster_aktiv", state, retain=True)
    client.publish(WW_GENERATION_TOPIC, "ON" if last_speicherladepumpe != "0" else "OFF", retain=True)


def decode_fault_history(raw: str) -> tuple[str, dict, bool]:
    cleaned = "".join(raw.split()).lower()
    try:
        data = bytes.fromhex(cleaned)
        if len(data) != 9:
            raise ValueError("unexpected length")
        code = data[0]
        timestamp = (
            f"{data[4]:02x}.{data[3]:02x}.{data[1]:02x}{data[2]:02x} "
            f"{data[6]:02x}:{data[7]:02x}:{data[8]:02x}"
        )
        description = FAULT_CODES.get(code, "Unbekannter Viessmann-Fehlercode")
        state = f"{code:02X} · {description} · {timestamp}"
        attributes = {
            "code": f"{code:02X}",
            "beschreibung": description,
            "zeitpunkt": timestamp,
            "rohwert": cleaned,
        }
        return state, attributes, code != 0
    except (ValueError, IndexError):
        return "Fehlerspeicher nicht lesbar", {"rohwert": raw}, False


def publish_fault_state(client: paho.Client, raw: str) -> None:
    state, attributes, active = decode_fault_history(raw)
    client.publish(FAULT_ACTIVE_TOPIC, "ON" if active else "OFF", retain=True)
    client.publish(FAULT_ATTR_TOPIC, json.dumps(attributes, ensure_ascii=False), retain=True)
    client.publish(FAULT_STATE_TOPIC, state, retain=True)


def on_connect(client, userdata, flags, reason_code, properties):
    client.publish(LWT_TOPIC, "online", retain=True)
    action_topics = [
        f"{ACTION_BASE}/ww_now_30",
        f"{ACTION_BASE}/ww_now_60",
        f"{ACTION_BASE}/ww_restore",
        f"{ACTION_BASE}/betriebsart/set",
        f"{ACTION_BASE}/sparbetrieb/set",
        f"{ACTION_BASE}/partybetrieb/set",
        *NUMBER_TARGETS.keys(),
        *EDITOR_COMMAND_TOPICS,
    ]
    schedule_topics = [
        f"{prefix}{weekday}"
        for prefix in SCHEDULE_TOPIC_PREFIXES.values()
        for weekday, _addr in WEEKDAYS
    ]
    state_topics = [
        f"{MQTT_BASE}/m1_betriebsart_roh",
        f"{MQTT_BASE}/speicherladepumpe",
        FAULT_RAW_TOPIC,
        SPAR_STATE_TOPIC,
        PARTY_STATE_TOPIC,
    ]
    client.subscribe([(topic, 0) for topic in action_topics + schedule_topics + state_topics])
    publish_discovery(client)
    publish_status("WW-Aktionsdienst online")
    publish_editor_state(client)
    pending = load_state()
    if pending:
        schedule_restore(pending)


def on_message(client, userdata, msg):
    global last_speicherladepumpe
    topic = str(msg.topic)
    payload = msg.payload.decode(errors="replace").strip()

    if topic == f"{MQTT_BASE}/m1_betriebsart_roh":
        try:
            mode = VALUE_TO_MODE.get(int(payload), f"Unbekannt ({payload})")
        except ValueError:
            mode = f"Unbekannt ({payload})"
        client.publish(MODE_STATE_TOPIC, mode, retain=True)
        return

    if topic == f"{MQTT_BASE}/speicherladepumpe":
        last_speicherladepumpe = payload
        publish_active_states(client)
        return

    if topic == FAULT_RAW_TOPIC:
        publish_fault_state(client, payload)
        return

    for key, prefix in SCHEDULE_TOPIC_PREFIXES.items():
        if topic.startswith(prefix):
            weekday = topic.removeprefix(prefix)
            schedule_cache[key][weekday] = payload
            publish_active_states(client)
            if editor_state and PROGRAM_LABEL_TO_KEY.get(editor_state.get("program")) == key:
                if DAY_LABEL_TO_KEY.get(editor_state.get("day")) == weekday and selected_editor_key() not in editor_state.get("drafts", {}):
                    load_selected_editor_slot()
                load_selected_profile_slot()
                publish_editor_state(client)
            return

    try:
        if handle_editor_command(client, topic, payload):
            return
        if topic == f"{ACTION_BASE}/ww_now_30":
            hot_water_now(30)
        elif topic == f"{ACTION_BASE}/ww_now_60":
            hot_water_now(60)
        elif topic == f"{ACTION_BASE}/ww_restore":
            restore_original_schedule()
        elif topic == f"{ACTION_BASE}/betriebsart/set":
            set_mode(payload)
        elif topic == f"{ACTION_BASE}/sparbetrieb/set":
            set_switch("Sparbetrieb dauerhaft", 0x2331, SPAR_STATE_TOPIC, payload)
        elif topic == f"{ACTION_BASE}/partybetrieb/set":
            set_switch("Partybetrieb dauerhaft", 0x2330, PARTY_STATE_TOPIC, payload)
        elif topic in NUMBER_TARGETS:
            set_number(topic, payload)
    except Exception as exc:
        publish_status(f"Fehler: {exc}")


def main() -> None:
    global editor_state, mqtt_client
    broker, port_s = str(settings.mqtt_broker).split(":", 1)
    editor_state = load_editor_state()
    schedule_view_server: ThreadingHTTPServer | None = None
    mqtt_client = paho.Client(paho.CallbackAPIVersion.VERSION2, "vitodens_ww_actions")
    if settings.mqtt_user:
        user, password = str(settings.mqtt_user).split(":", 1)
        mqtt_client.username_pw_set(user, password)
    mqtt_client.will_set(LWT_TOPIC, "offline", retain=True)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(broker, int(port_s), keepalive=60)
    mqtt_client.loop_start()
    schedule_view_server = start_schedule_view_server()
    try:
        while True:
            publish_active_states(mqtt_client)
            time.sleep(30)
    finally:
        if schedule_view_server:
            schedule_view_server.shutdown()
            schedule_view_server.server_close()
        mqtt_client.publish(LWT_TOPIC, "offline", retain=True)
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


if __name__ == "__main__":
    main()
