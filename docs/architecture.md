# Architektur und Betriebsdaten

## Komponenten

| Komponente | Ort | Aufgabe |
| --- | --- | --- |
| Vitodens-Regelung | Heizgerät | Quelle und Ziel der VS2/P300-Datenpunkte |
| USB-Optolink-Adapter | Raspberry Pi | Direkte optische Verbindung zur Heizung |
| `optolink-splitter` | Raspberry Pi | Serielle Kommunikation, TCP-Schnittstelle und MQTT-Polling |
| `vitodens_ww_actions.py` | Raspberry Pi | Zusatzlogik, Profile, geprüfte Schreibaktionen und MQTT Discovery |
| Vitoconnect | Heizraum | ViCare-/Cloud-Zugang über den zweiten Splitter-Anschluss |
| MQTT-Broker | Home Assistant | Zustände und Befehle zwischen Raspberry und Home Assistant |
| drei JavaScript-Karten | Home Assistant `/config/www` | Bedienung, Zeitbalken und Profileditor |

Home Assistant spricht nicht direkt mit der seriellen Heizung. Die Karten bedienen
MQTT-Entitäten. Der Zusatzdienst empfängt deren Befehle und spricht über den nur
lokal erreichbaren TCP-Port des Splitters mit der Vitodens.

## Datenfluss und Schreibschutz

```text
Vitodens <-> USB-Optolink <-> optolink-splitter <-> MQTT <-> Home Assistant
                                  ^
                                  |
                         lokale TCP-Schnittstelle
                                  |
                         vitodens_ww_actions.py
                                  |
                    UART <-> USB-TTL <-> Vitoconnect
```

`homeassistant_poll_list.py` enthält ausschließlich Lesedatenpunkte. Schreibbare
Entitäten werden bewusst nur durch `vitodens_ww_actions.py` angelegt. Der Dienst
prüft Wertebereiche und liest Zeitprogramme nach einem Schreibvorgang erneut aus.
Ein grüner Status in Home Assistant ersetzt trotzdem keine Plausibilitätskontrolle
am Heizgerät.

## Lokale Dateien

| Pfad | Inhalt | Sicherung |
| --- | --- | --- |
| `/home/optolink/optolink-splitter/settings_ini.py` | MQTT-, TCP- und serielle Konfiguration; enthält Zugangsdaten | ja, nur verschlüsselt |
| `schedule_editor_state.json` im Splitter-Verzeichnis | Profile, Profilzuordnungen und Editorzustand | ja |
| `ww_action_state.json` im Splitter-Verzeichnis | temporäre Sicherung während eines Warmwasser-Schnellstarts | nur vorhanden, solange eine Aktion läuft |
| `/etc/systemd/system/*.service` | Startreihenfolge und Neustartverhalten | ja |
| `/etc/default/optolink-backup` | privates Backup-Ziel und Aufbewahrung | ja, nur verschlüsselt |
| `/root/.ssh/optolink_ha_backup_ed25519` | privater Übertragungsschlüssel | nein, bewusst neu erzeugen |
| `/config/www/vitodens-*.js` | Home-Assistant-Karten | durch vollständiges HA-Backup |
| Home-Assistant-Dashboard und Automation | UI-Konfiguration | durch vollständiges HA-Backup |

Die JSON-Zustandsdateien werden atomar über eine temporäre Datei ersetzt. Sie
dürfen nicht gleichzeitig von Hand editiert werden, während der Zusatzdienst
läuft.

## Dienste und Startreihenfolge

1. Netzwerk und MQTT-Broker werden erreichbar.
2. `optolinkvs2_switch.service` startet den Splitter und wird bei einem Fehler
   nach zehn Sekunden neu gestartet.
3. `vitodens_ww_actions.service` verlangt den Splitter-Dienst und startet danach.
4. MQTT Discovery legt die Entitäten in Home Assistant an beziehungsweise
   aktualisiert sie.
5. `optolink-backup.timer` läuft unabhängig einmal täglich.

Der MQTT-Verfügbarkeitsstatus des Zusatzdienstes liegt unter
`<mqtt_topic>/action/LWT`. Bei einem geregelten Stopp wird `offline` gesendet;
bei einem Verbindungsabbruch übernimmt die MQTT-Will-Nachricht. Nach einem
Neustart werden gespeicherte Profile wieder geladen. Eine noch laufende
Warmwasseraktion wird aus `ww_action_state.json` aufgenommen und ihre geplante
Wiederherstellung erneut angesetzt.

## Polling und sichtbare Verzögerungen

Der Splitter verwendet ein Basisintervall von zehn Sekunden. Die Gruppen in
`homeassistant_poll_list.py` sind Multiplikatoren:

| Gruppe | Typischer Abstand |
| --- | ---: |
| `ALWAYS` | 10 Sekunden |
| `OFTEN` | 30 Sekunden |
| `SOMETIMES` | 120 Sekunden |
| `RARELY` | 600 Sekunden |

Darum können bestätigte Heizkennlinienwerte oder Zeitprogramme später als der
Aktionsstatus erscheinen. Der Schreibbefehl kann bereits erfolgreich sein,
während der regulär gepollte Lesewert noch den alten Stand zeigt. Die
Warmwassererzeugung wird nicht aus der Betriebsart abgeleitet, sondern aus der
tatsächlichen Speicherladepumpe.

## Verantwortungsgrenzen

- Der Raspberry enthält Kommunikation und Zusatzlogik.
- Home Assistant enthält Darstellung, Bedienoberfläche und Push-Automation.
- Die Heizung bleibt für Zeitprogramme, Grenzwerte und Schutzfunktionen
  maßgeblich.
- ViCare kann parallel laufen, ist aber für die lokale Bedienung nicht nötig.
- Das Projekt verändert keine Servicecodierungen und optimiert die Heizkennlinie
  nicht automatisch.
