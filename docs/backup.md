# Backup und Wiederherstellung

## Automatisches Backup in Home Assistant

`optolink-backup.timer` erstellt täglich ein bereinigtes, komprimiertes Archiv
und überträgt es per SSH nach `/config/optolink-backup` auf dem Home-Assistant-
System. Die sieben neuesten Generationen bleiben erhalten. Logs, Git-Metadaten,
Python-Caches und Entwicklungs-Sicherungen werden ausgelassen.

Das Archiv enthält die lokale Splitter-Konfiguration, Zusatzdienste und Profile,
systemd-Units, UART-Bootkonfiguration sowie Paket- und Python-Abhängigkeiten. Der
Zielordner wird danach von einem vollständigen, verschlüsselten Home-Assistant-
Backup erfasst. Das Archiv selbst enthält lokale Zugangsdaten und darf deshalb
nicht in das öffentliche Repository gelangen.

Die lokale Datei `/etc/default/optolink-backup` kann bei Bedarf Ziel und
Aufbewahrung festlegen, ohne private Adressen zu veröffentlichen:

```ini
DEST_HOST=homeassistant.local
DEST_DIR=/config/optolink-backup
KEEP=7
```

Für die Übertragung wird ein eigener SSH-Schlüssel ohne interaktive
Passworteingabe verwendet. Sein öffentlicher Teil wird in der Home-Assistant-App
**Terminal & SSH** hinterlegt; der private Schlüssel bleibt ausschließlich unter
`/root/.ssh/optolink_ha_backup_ed25519` auf dem Raspberry Pi.

Installation auf dem Raspberry Pi:

```bash
sudo cp optolink-backup.sh /usr/local/sbin/optolink-backup
sudo cp optolink-backup-status.py /usr/local/sbin/optolink-backup-status
sudo chmod 0755 /usr/local/sbin/optolink-backup \
  /usr/local/sbin/optolink-backup-status
sudo cp optolink-backup.service optolink-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now optolink-backup.timer
sudo systemctl start optolink-backup.service
```

Der letzte Befehl dient als sofortiger Übertragungs- und Berechtigungstest.
`systemctl status optolink-backup.service optolink-backup.timer` zeigt Ergebnis
und nächsten geplanten Lauf.

Nach jedem erfolgreichen Lauf aktualisiert der Dienst den MQTT-Sensor
`sensor.vitodens_letztes_optolink_backup`. Bleibt ein Backup länger als 48
Stunden aus, wird der Sensor nicht verfügbar.

## Zu sichern

Auf dem Raspberry:

- vollständiges Verzeichnis von `optolink-splitter`
- `/etc/systemd/system/optolinkvs2_switch.service`
- `/etc/systemd/system/vitodens_ww_actions.service`
- Udev-Regeln oder Boot-Konfiguration für UART, sofern angepasst

In Home Assistant:

- Dashboard `vitodens-lokal`
- JavaScript-Ressourcen unter `/config/www/`
- Störungsautomation
- MQTT-Konfiguration und Broker-Backup

Nicht in ein öffentliches Git-Repository gehören:

- `settings_ini.py`
- MQTT-Passwörter
- IP-Adressen und Hostnamen des Heimnetzes
- private Schlüssel
- produktive Zustandsdateien

## Empfohlene Strategie

1. Tägliches komprimiertes Raspberry-Backup auf ein NAS.
2. Aufbewahrung von mindestens sieben täglichen und vier wöchentlichen Ständen.
3. Home-Assistant-Backups ebenfalls automatisiert auf ein zweites System
   übertragen.
4. Nach Änderungen zusätzlich einen bezeichneten funktionierenden Stand sichern.
5. Wiederherstellung mindestens einmal auf einer Ersatz-SD-Karte testen.

## Wiederherstellungsreihenfolge

1. Betriebssystem installieren und UART aktivieren.
2. `optolink-splitter` samt lokaler Konfiguration wiederherstellen.
3. Stabile Gerätenamen unter `/dev/serial/by-id/` prüfen.
4. systemd-Units wiederherstellen und aktivieren.
5. MQTT-Erreichbarkeit und reine Lesewerte prüfen.
6. Erst anschließend Home-Assistant-Bedienelemente freigeben.
