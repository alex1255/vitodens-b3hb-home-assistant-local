#!/usr/bin/env python3
import importlib.util
import json
import sys
from pathlib import Path

import paho.mqtt.client as mqtt


def load_settings():
    path = Path("/home/optolink/optolink-splitter/settings_ini.py")
    spec = importlib.util.spec_from_file_location("optolink_settings", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    timestamp, size = sys.argv[1], int(sys.argv[2])
    settings = load_settings()
    host, port = settings.mqtt_broker.rsplit(":", 1)
    username, password = settings.mqtt_user.split(":", 1)
    topic = "vitodens/backup"
    config = {
        "name": "Raspberry Optolink-Backup · /config/optolink-backup",
        "unique_id": "vitodens_optolink_backup_last_success",
        "default_entity_id": "sensor.vitodens_letztes_optolink_backup",
        "state_topic": f"{topic}/last_success",
        "json_attributes_topic": f"{topic}/attributes",
        "device_class": "timestamp",
        "expire_after": 172800,
        "icon": "mdi:backup-restore",
        "device": {
            "identifiers": ["vitodens_local"],
            "name": "Vitodens 300-W Lokal",
            "manufacturer": "Viessmann / lokal",
        },
    }
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="optolink-backup")
    client.username_pw_set(username, password)
    client.connect(host, int(port), 30)
    client.loop_start()
    client.publish(
        "homeassistant/sensor/vitodens/optolink_backup/config",
        json.dumps(config), retain=True,
    ).wait_for_publish()
    client.publish(f"{topic}/last_success", timestamp, retain=True).wait_for_publish()
    client.publish(
        f"{topic}/attributes",
        json.dumps({
            "quelle": "Raspberry Pi Optolink-Erweiterung",
            "zielpfad": "/config/optolink-backup",
            "size_bytes": size,
            "size_kib": round(size / 1024, 1),
            "status": "Aktuell",
        }),
        retain=True,
    ).wait_for_publish()
    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
