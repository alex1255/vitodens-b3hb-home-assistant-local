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

Getestete UART-Verdrahtung am 40-Pin-Header:

| Raspberry Pi | Physischer Pin | USB-TTL-Adapter |
| --- | ---: | --- |
| GND | 6 | GND |
| GPIO14 / UART0 TX | 8 | RX |
| GPIO15 / UART0 RX | 10 | TX |

Die VCC-Leitung bleibt frei. Vor dem Anschluss sicherstellen, dass der Adapter
mit 3,3-V-Logik arbeitet. Die Pinbelegung des konkreten Raspberry-Modells und
Adapters anhand deren Dokumentation nochmals prüfen.

Für den Optolink-USB-Adapter einen stabilen Pfad aus `/dev/serial/by-id/`
verwenden. Gerätenamen wie `/dev/ttyUSB0` können sich nach einem Neustart ändern.

## 2. Erweiterung installieren

Dieses Repository zusätzlich zum bereits eingerichteten Splitter klonen:

```bash
git clone https://github.com/alex1255/vitodens-b3hb-home-assistant-local.git
cd vitodens-b3hb-home-assistant-local
EXTENSION_DIR="$PWD"
```

Python-Abhängigkeit der Erweiterung installieren:

```bash
python3 -m pip install -r "$EXTENSION_DIR/requirements.txt"
```

Installationsverzeichnis und Dienstbenutzer an die eigene Splitter-Installation
anpassen. Das folgende Beispiel verwendet die Vorgaben der mitgelieferten
systemd-Unit:

```bash
SPLITTER_DIR=/home/optolink/optolink-splitter
SPLITTER_USER=optolink

sudo install -o "$SPLITTER_USER" -g "$SPLITTER_USER" -m 0644 \
  "$EXTENSION_DIR/homeassistant_poll_list.py" \
  "$EXTENSION_DIR/vitodens_ww_actions.py" \
  "$SPLITTER_DIR/"
```

Folgende Dateien liegen danach direkt im vorhandenen
`optolink-splitter`-Verzeichnis:

```text
homeassistant_poll_list.py
vitodens_ww_actions.py
```

Die lokale `settings_ini.py` bleibt außerhalb dieses Repositorys. Dort werden
MQTT-Broker, Zugangsdaten und serielle Ports konfiguriert.

Der Zusatzdienst verwendet aus der Splitter-Konfiguration mindestens:

| Einstellung | Bedeutung |
| --- | --- |
| `port_optolink` | stabiler Gerätepfad des USB-Optolink-Adapters |
| `port_vitoconnect` | Raspberry-UART für Vitoconnect, im getesteten Aufbau `/dev/ttyAMA0` |
| `mqtt_broker` | MQTT-Broker im Format `host:port` |
| `mqtt_user` | optional im Format `benutzer:passwort` |
| `mqtt_topic` | gemeinsames Topic-Präfix, beispielsweise `vitodens` |
| `mqtt_listen` | MQTT-Empfang des Splitters aktivieren |
| `mqtt_respond` | MQTT-Ausgabe des Splitters aktivieren |
| `tcpip_port` | lokaler TCP-Port des laufenden Splitters |

Zusätzlich muss der primäre UART in der Boot-Konfiguration aktiviert und die
serielle Linux-Konsole auf diesem Port deaktiviert sein. Nach jeder Änderung der
Boot-Konfiguration neu starten und mit `ls -l /dev/ttyAMA0` prüfen. Die konkrete
Datei ist abhängig von der Raspberry-Pi-OS-Version (`/boot/config.txt` oder
`/boot/firmware/config.txt`).

Der TCP-Server und die Home-Assistant-/MQTT-Ausgabe des Splitters müssen aktiv
sein. Zugangsdaten gehören ausschließlich in die lokale `settings_ini.py` und
nicht in dieses Repository.

Syntax prüfen:

```bash
cd "$SPLITTER_DIR"
sudo -u "$SPLITTER_USER" python3 -m py_compile \
  homeassistant_poll_list.py vitodens_ww_actions.py
```

MQTT Discovery des Splitters veröffentlichen:

```bash
python3 homeassistant_publish.py
```

## 3. systemd-Dienst

Pfade, Benutzer und Gruppe in `vitodens_ww_actions.service` anpassen, falls die
Installation nicht unter `/home/optolink/optolink-splitter` läuft. Auch der in
`After=` und `Requires=` genannte Name der Splitter-Unit muss mit der lokalen
Installation übereinstimmen. Danach aus dem geklonten Erweiterungs-Repository:

```bash
sudo cp "$EXTENSION_DIR/vitodens_ww_actions.service" /etc/systemd/system/
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

Ein erfolgreicher Start enthält keine dauerhafte Python-Ausnahme und meldet den
Dienst als `active (running)`. Nach einem Neustart müssen beide Units weiterhin
`enabled` und `active` sein.

Für den parallelen ViCare-Betrieb zuerst Raspberry und Splitter vollständig
starten lassen. Anschließend Vitoconnect mit dem USB-TTL-Anschluss verbinden
beziehungsweise versorgen. Die Power-LED bestätigt nur die Versorgung; RX/TX-
Aktivität und eine wieder erreichbare ViCare-App bestätigen die Kommunikation.

## 4. Home-Assistant-Karten

Die drei JavaScript-Dateien aus diesem Repository nach `/config/www/` der
Home-Assistant-Installation kopieren:

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

Nach dem Start des Zusatzdienstes sollte unter **Einstellungen > Geräte &
Dienste > MQTT** ein Gerät mit dem Namen **Vitodens 300-W Lokal** erscheinen.
Fehlt es, zuerst MQTT-Verbindung und Dienstprotokoll prüfen, bevor ein
Schreibtest erfolgt.

## 5. Kontrollierte Inbetriebnahme

1. Prüfen, ob alle Sensoren plausible Werte liefern.
2. Einen Sollwert höchstens um einen Schritt verändern.
3. Rückmeldung des Lesesensors abwarten.
4. Den ursprünglichen Wert wiederherstellen.
5. Erst danach Betriebsarten oder Zeitprogramme testen.

Die Anwendung schreibt niemals automatisch eine Heizkennlinie. Profil- und
Zeitprogrammänderungen werden nur nach einer ausdrücklichen Bedienaktion
ausgeführt.

Zum Abschluss den Raspberry einmal kontrolliert neu starten und danach Dienste,
MQTT-Entitäten, ViCare-Verbindung und Lesewerte erneut prüfen. Die ausführliche
Diagnose steht unter [Fehlersuche und Wartung](troubleshooting.md).

## Aktualisierung

```bash
cd vitodens-b3hb-home-assistant-local
git pull --ff-only
```

Anschließend die beiden Python-Dateien und gegebenenfalls geänderte
JavaScript-Karten erneut an ihre Zielorte kopieren. Falls die Backup-Dateien
geändert wurden, auch Skripte und Units nach der Anleitung in
[Backup und Wiederherstellung](backup.md) aktualisieren. Danach:

```bash
sudo systemctl restart vitodens_ww_actions.service
```

Bei Änderungen an der systemd-Unit zusätzlich `sudo systemctl daemon-reload`
ausführen. Browser und Home-Assistant-App benötigen nach einem Update der
JavaScript-Karten möglicherweise einen vollständig geleerten Frontend-Cache.

Vor einem größeren Update ein manuelles Home-Assistant-Backup erzeugen. Für ein
Rollback den vorherigen Git-Commit auschecken, die Dateien erneut installieren
und die Dienste neu starten. Produktive `settings_ini.py` und JSON-Zustandsdateien
dabei nicht durch Repository-Dateien ersetzen.
