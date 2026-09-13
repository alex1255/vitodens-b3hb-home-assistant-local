# Backup und Wiederherstellung

## Überblick

`optolink-backup.timer` erstellt täglich ein bereinigtes, komprimiertes Archiv
und überträgt es per SSH nach `/config/optolink-backup` auf dem Home-Assistant-
System. Der Zeitplan startet täglich um 03:30 Uhr und verteilt den tatsächlichen
Start zufällig über die folgenden 30 Minuten. Verpasste Läufe werden durch
`Persistent=true` nach dem nächsten Start des Raspberry Pi nachgeholt.

Standardmäßig bleiben die sieben neuesten Archive erhalten. Das entspricht bei
störungsfreiem täglichem Betrieb ungefähr sieben Tagen, ist aber eine Anzahl von
Dateien und keine garantierte Tagesfrist. `KEEP` kann lokal geändert werden.
Logs, Git-Metadaten, Python-Caches und Entwicklungs-Sicherungen werden
ausgelassen.

Das Archiv enthält die lokale Splitter-Konfiguration, Zusatzdienste und Profile,
systemd-Units, UART-Bootkonfiguration sowie Paket- und Python-Abhängigkeiten. Der
Zielordner wird danach von einem vollständigen, verschlüsselten Home-Assistant-
Backup erfasst. Das Archiv selbst enthält lokale Zugangsdaten und darf deshalb
nicht in das öffentliche Repository gelangen.

Ein typisches Archiv dieser Installation ist nur ungefähr 100 bis 150 KiB groß.
Die Größe hängt von Konfiguration und Zustandsdateien ab. Selbst sieben Stände
belegen normalerweise deutlich weniger als 2 MiB; der konkrete Wert steht als
Attribut am MQTT-Backup-Sensor.

## Voraussetzungen

- Home Assistant OS mit der App **Terminal & SSH**
- SSH-Zugriff vom Raspberry Pi auf diese App
- `rsync`, `zstd`, `openssh-client` und Python mit `paho-mqtt` auf dem Raspberry
- ein vollständiges und verschlüsseltes Home-Assistant-Backup, das `/config`
  einschließt

## 1. Ziel und Aufbewahrung festlegen

Die lokale Datei `/etc/default/optolink-backup` legt Ziel und Aufbewahrung fest,
ohne private Adressen im Repository zu veröffentlichen:

```ini
DEST_HOST=homeassistant.local
DEST_DIR=/config/optolink-backup
KEEP=7
```

`DEST_HOST` darf ein lokaler DNS-Name oder eine IP-Adresse sein. `DEST_DIR`
muss innerhalb von `/config` liegen, damit ein vollständiges Home-Assistant-
Backup die Archive einschließt.

## 2. Eigenen SSH-Schlüssel einrichten

Für die Übertragung wird ein eigener SSH-Schlüssel ohne interaktive
Passworteingabe verwendet. Auf dem Raspberry als `root`:

```bash
install -d -m 0700 /root/.ssh
ssh-keygen -t ed25519 -f /root/.ssh/optolink_ha_backup_ed25519 \
  -C optolink-backup -N ''
cat /root/.ssh/optolink_ha_backup_ed25519.pub
```

Nur die ausgegebene **öffentliche** Zeile in der Konfiguration der
Home-Assistant-App **Terminal & SSH** unter `authorized_keys` ergänzen und die
App neu starten. Der private Schlüssel bleibt ausschließlich auf dem Raspberry.
Verbindung testen:

```bash
ssh -i /root/.ssh/optolink_ha_backup_ed25519 root@homeassistant.local \
  'mkdir -p /config/optolink-backup && test -w /config/optolink-backup'
```

Dieser Schlüssel ermöglicht dem Raspberry den privilegierten SSH-Zugriff auf
die Terminal-App. Die private Datei muss deshalb mit Modus `0600` geschützt und
darf weder ins Repository noch ins Backup-Archiv kopiert werden. Das lokale Netz
und der Raspberry müssen als vertrauenswürdig gelten. Wer den Schlüssel verliert
oder einen kompromittierten Raspberry ersetzt, entfernt die zugehörige
öffentliche Zeile aus `authorized_keys` und erzeugt ein neues Schlüsselpaar.

## 3. Backup-Dienst installieren

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

## 4. Regelmäßig kontrollieren

```bash
systemctl list-timers optolink-backup.timer
systemctl show optolink-backup.service -p Result -p ExecMainStatus
journalctl -u optolink-backup.service -n 30 --no-pager
```

In Home Assistant zeigt der Badge auf der Profilseite Zeitpunkt, Zielpfad und
Größe des letzten erfolgreichen Laufs. Auf dem Home-Assistant-System müssen
unter `/config/optolink-backup` bis zu `KEEP` Dateien mit der Endung
`.tar.zst` liegen.

Der Badge ist nur verfügbar, wenn der Backup-Dienst mindestens einmal
erfolgreich gelaufen ist und seine MQTT-Discovery-Nachricht veröffentlicht hat.
Wird das optionale Backup nicht installiert, muss der Badge aus dem Beispiel-
Dashboard entfernt werden.

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

## Zusammenspiel mit dem Home-Assistant-Backup

Das Skript sichert den Raspberry **in** das Home-Assistant-Konfigurationsverzeichnis.
Es ersetzt nicht das Home-Assistant-Backup. Erst ein nachfolgendes vollständiges
HA-Backup nimmt `/config/optolink-backup` mit. Dieses HA-Backup sollte
verschlüsselt und zusätzlich außerhalb des Home-Assistant-Geräts gespeichert
werden, beispielsweise über das integrierte Backup-Ziel einer NAS oder Cloud.

Empfohlen sind tägliche vollständige HA-Backups nach Abschluss des Raspberry-
Laufs, also mit genügend Abstand nach 04:00 Uhr. Nach größeren Änderungen sollte
zusätzlich ein manueller, benannter HA-Sicherungsstand erstellt werden.

## Wiederherstellung nach einem SD-Kartenausfall

1. Falls nötig zuerst das vollständige Home-Assistant-Backup wiederherstellen.
2. Aus `/config/optolink-backup` das gewünschte Archiv auf einen frisch
   installierten Raspberry Pi kopieren.
3. Archiv als `root` in ein leeres Arbeitsverzeichnis entpacken:

```bash
mkdir -p /root/optolink-restore
tar --zstd -xf optolink-YYYYMMDD-HHMMSS.tar.zst \
  -C /root/optolink-restore
cat /root/optolink-restore/RESTORE.txt
```

4. Benötigte Pakete installieren und UART anhand der gesicherten Dateien unter
   `boot/` wieder konfigurieren. Bootdateien nicht blind über eine neuere
   Raspberry-Pi-OS-Version kopieren, sondern die relevanten UART-Zeilen
   vergleichen.
5. `optolink-splitter` nach `/home/optolink/optolink-splitter` und die Units
   nach `/etc/systemd/system` zurückkopieren. Eigentümer und Pfade an die neue
   Installation anpassen.
6. Die Backup-Skripte aus `usr/local/sbin` sowie optional
   `etc/default/optolink-backup` wiederherstellen.
7. Den privaten Backup-SSH-Schlüssel neu erzeugen und dessen öffentlichen Teil
   erneut in **Terminal & SSH** hinterlegen. Private Schlüssel sind absichtlich
   nicht im Archiv enthalten.
8. Dienste aktivieren:

```bash
systemctl daemon-reload
systemctl enable --now optolinkvs2_switch.service
systemctl enable --now vitodens_ww_actions.service
systemctl enable --now optolink-backup.timer
```

9. Stabile Gerätenamen, UART-Verdrahtung, MQTT und zunächst ausschließlich
   Lesewerte prüfen. Erst danach einen kontrollierten Schreibtest durchführen.

Eine Rücksicherung sollte mindestens einmal mit einer Ersatz-SD-Karte geprobt
werden. Nur damit ist geprüft, dass Betriebssystemversion, Pakete und Hardware
zum Archiv passen.
