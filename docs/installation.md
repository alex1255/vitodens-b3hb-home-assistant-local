# Installation

## Voraussetzungen

- funktionierende Installation von `optolink-splitter`
- Python 3.9 oder neuer
- `pyserial` und `paho-mqtt`
- erreichbarer MQTT-Broker
- konfigurierte MQTT-Integration in Home Assistant
- funktionierender reiner Lesezugriff auf die Heizung

Vor dem ersten Schreibtest ein vollständiges Backup des Splitter-Verzeichnisses
und der systemd-Units erstellen.

## 1. Optolink-Splitter prüfen

Die Installation des Splitters erfolgt nach dessen eigener Dokumentation. Für
den parallelen Betrieb mit Vitoconnect sind gekreuzte RX/TX-Leitungen und ein
3,3-V-UART erforderlich. Auf Raspberry Pi 3 und neuer sollte in der Regel
`/dev/ttyAMA0` statt `/dev/ttyS0` verwendet werden.

Für den Optolink-USB-Adapter einen stabilen Pfad aus `/dev/serial/by-id/`
verwenden. Gerätenamen wie `/dev/ttyUSB0` können sich nach einem Neustart ändern.

## 2. Erweiterung installieren

Die folgenden Dateien in das vorhandene Verzeichnis von `optolink-splitter`
kopieren:

```text
homeassistant_poll_list.py
vitodens_ww_actions.py
```

Die lokale `settings_ini.py` bleibt außerhalb dieses Repositorys. Dort werden
MQTT-Broker, Zugangsdaten und serielle Ports konfiguriert.

Syntax prüfen:

```bash
python3 -m py_compile homeassistant_poll_list.py vitodens_ww_actions.py
```

MQTT Discovery des Splitters veröffentlichen:

```bash
python3 homeassistant_publish.py
```

## 3. systemd-Dienst

Pfade und Benutzer in `vitodens_ww_actions.service` an die lokale Installation
anpassen. Danach:

```bash
sudo cp vitodens_ww_actions.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vitodens_ww_actions.service
```

Status prüfen:

```bash
systemctl is-enabled optolinkvs2_switch.service vitodens_ww_actions.service
systemctl is-active optolinkvs2_switch.service vitodens_ww_actions.service
journalctl -u vitodens_ww_actions.service -n 50 --no-pager
```

Der Zusatzdienst benötigt den Splitter und startet deshalb erst danach.

## 4. Home-Assistant-Karten

Die drei JavaScript-Dateien nach `/config/www/` kopieren:

```text
vitodens-heating-control-card.js
vitodens-schedule-bars-card.js
vitodens-profile-editor-card.js
```

Unter **Einstellungen > Dashboards > Ressourcen** jeweils als JavaScript-Modul
registrieren:

```text
/local/vitodens-heating-control-card.js
/local/vitodens-schedule-bars-card.js
/local/vitodens-profile-editor-card.js
```

Danach das Beispiel-Dashboard über den Rohkonfigurationseditor übernehmen. Die
Entity-IDs zusätzlicher externer Temperaturfühler müssen lokal angepasst werden.

## 5. Kontrollierte Inbetriebnahme

1. Prüfen, ob alle Sensoren plausible Werte liefern.
2. Einen Sollwert höchstens um einen Schritt verändern.
3. Rückmeldung des Lesesensors abwarten.
4. Den ursprünglichen Wert wiederherstellen.
5. Erst danach Betriebsarten oder Zeitprogramme testen.

Die Anwendung schreibt niemals automatisch eine Heizkennlinie. Profil- und
Zeitprogrammänderungen werden nur nach einer ausdrücklichen Bedienaktion
ausgeführt.

