# Backup und Wiederherstellung

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

