# Fehlersuche und Wartung

## Schnellprüfung

Auf dem Raspberry Pi:

```bash
systemctl is-enabled optolinkvs2_switch.service \
  vitodens_ww_actions.service optolink-backup.timer
systemctl is-active optolinkvs2_switch.service \
  vitodens_ww_actions.service optolink-backup.timer
journalctl -u optolinkvs2_switch.service -n 50 --no-pager
journalctl -u vitodens_ww_actions.service -n 50 --no-pager
```

Alle drei Einheiten müssen `enabled` sein. Splitter und Zusatzdienst müssen
`active` melden; beim Backup ist der Timer dauerhaft `active`, während der
zugehörige Oneshot-Dienst zwischen den Läufen `inactive (dead)` sein darf.

## Home Assistant zeigt keine oder alte Werte

1. MQTT-Gerät **Vitodens 300-W Lokal** auf Verfügbarkeit prüfen.
2. Den Zustand von `sensor.vitodens_ww_aktion_status` ansehen.
3. Beide Dienstprotokolle prüfen.
4. TCP-Port aus `settings_ini.py` mit einem reinen Lesebefehl testen.
5. Erst danach Dienste neu starten:

```bash
systemctl restart optolinkvs2_switch.service
systemctl restart vitodens_ww_actions.service
```

Einige Datenpunkte werden nur alle zwei oder zehn Minuten gelesen. Die in
[`architecture.md`](architecture.md) dokumentierten Pollingzeiten berücksichtigen,
bevor ein funktionierender Schreibzugriff wiederholt wird.

## Optolink-USB-Adapter wurde abgezogen

Der Adapter sollte unter `/dev/serial/by-id/` wieder erscheinen. Bleibt der
Splitter trotz eingestecktem Adapter offline:

```bash
ls -l /dev/serial/by-id/
systemctl restart optolinkvs2_switch.service
journalctl -u optolinkvs2_switch.service -n 80 --no-pager
```

Für den Adapter in `settings_ini.py` einen stabilen `by-id`-Pfad verwenden. Ein
wechselnder Name wie `/dev/ttyUSB0` kann nach dem Wiedereinstecken oder Neustart
auf ein anderes Gerät zeigen.

## Vitoconnect blinkt fehlerhaft oder ViCare ist offline

- Prüfen, ob der Raspberry-UART aktiviert und als `/dev/ttyAMA0` verfügbar ist.
- RX und TX müssen gekreuzt sein: Adapter-RX an Raspberry-TX, Adapter-TX an
  Raspberry-RX, dazu gemeinsame Masse.
- Nur 3,3-V-UART verwenden und keine zusätzliche VCC-Leitung verbinden.
- Splitter zuerst stabil starten lassen, danach Vitoconnect neu verbinden oder
  mit Strom versorgen.
- Bei RX/TX-Aktivität müssen am USB-TTL-Adapter Datenimpulse sichtbar sein;
  dauerhaft leuchtende Power-LEDs allein belegen keine Kommunikation.

Funktioniert Vitoconnect direkt an der Heizung, aber nicht über den Splitter,
liegt das Problem typischerweise an UART-Port, Pegel, gekreuzten Leitungen oder
Startreihenfolge und nicht an der ViCare-Registrierung.

## Bedienaktion meldet `Connection refused`

Der Zusatzdienst erreicht den lokalen TCP-Server des Splitters nicht. Prüfen:

```bash
systemctl status optolinkvs2_switch.service
ss -ltnp
journalctl -u optolinkvs2_switch.service -n 50 --no-pager
```

`tcpip_port` in `settings_ini.py` muss mit dem lauschenden Splitter-Port
übereinstimmen. Der Zusatzdienst versucht einen fehlgeschlagenen TCP-Aufbau
mehrfach; ein dauerhaftes `Connection refused` wird dadurch nicht behoben.

## Zeitprogramm oder Profil scheint nicht übernommen

- Profile werden im Profileditor nur lokal gespeichert.
- Erst **Anwenden** in der Zeitprogramm-Ansicht schreibt das gewählte Profil auf
  einen Wochentag.
- Ein Zeitprogramm besteht aus vier Fenstern und wird immer als kompletter
  Acht-Byte-Block geschrieben.
- Nach dem Schreiben den zurückgelesenen Tagesbalken und die letzte Aktion
  kontrollieren.
- Nicht mehrfach schnell hintereinander drücken. Erst die Rückmeldung abwarten.

## Warmwasser läuft nach „Wiederherstellen“ weiter

Der Button stellt das vorherige Zeitprogramm wieder her. Er schaltet nicht hart
die Speicherladepumpe ab. Die Regelung kann eine bereits begonnene Ladung wegen
interner Mindestlaufzeit, Nachlauf oder eigener Speicherlogik fortführen. Der
Status **WW Erzeugung** zeigt die tatsächliche Speicherladepumpe; die Betriebsart
**Nur Warmwasser** allein sagt nicht, dass gerade geladen wird.

## Störung am Gerät, aber keine Push-Nachricht

1. `binary_sensor.vitodens_stoerung_aktiv` und
   `sensor.vitodens_stoerung_aktuell` prüfen.
2. In der Automation die Spuren des letzten Laufs öffnen.
3. Die konfigurierte `notify.mobile_app_...`-Aktion manuell testen.
4. App-Berechtigungen des Mobilgeräts prüfen.
5. Details stehen in [`notifications.md`](notifications.md).

Eine quittierte Störung kann weiter als Dreieck am Heizgerät stehen. Quittieren
und Beheben sind unterschiedliche Zustände.

## Backup fehlt oder ist älter als 48 Stunden

```bash
systemctl list-timers optolink-backup.timer
systemctl start optolink-backup.service
journalctl -u optolink-backup.service -n 50 --no-pager
```

Danach SSH-Verbindung, Schreibrecht auf `/config/optolink-backup` und freien
Speicher auf dem Home-Assistant-System prüfen. Details zur Rücksicherung stehen
in [`backup.md`](backup.md).

## Wartung nach einem Update

Nach `git pull --ff-only` geänderte Python- und JavaScript-Dateien erneut an die
Installationsorte kopieren. Python syntaxprüfen, Dienste neu starten und den
Frontend-Cache der Home-Assistant-App beziehungsweise des Browsers vollständig
leeren. Danach Lesewerte, eine ungefährliche Bedienaktion und den Backup-Status
prüfen.
