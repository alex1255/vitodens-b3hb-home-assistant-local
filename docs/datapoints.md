# Datenpunkte

Die Adressen gelten für die getestete Vitodens 300-W B3HB mit
`VScotHO1_72`. Vor Schreibzugriffen müssen sie für das eigene Gerät bestätigt
werden.

| Funktion | Adresse | Länge | Format |
| --- | ---: | ---: | --- |
| Anlagenzeit | `0x088E` | 8 | Viessmann-Datum/Zeit |
| Außentemperatur | `0x0800` | 2 | Faktor 0,1, vorzeichenbehaftet |
| Kesseltemperatur | `0x0802` | 2 | Faktor 0,1 |
| Speichertemperatur | `0x0804` | 2 | Faktor 0,1 |
| Brennerstarts | `0x088A` | 4 | Zähler |
| Betriebsstunden | `0x08A7` | 4 | Sekunden |
| Betriebsart HK1 | `0x2323` | 1 | Enumeration |
| Sparbetrieb HK1 | `0x2331` | 1 | Boolesch |
| Partybetrieb HK1 | `0x2330` | 1 | Boolesch |
| Normaltemperatur HK1 | `0x2306` | 1 | Grad Celsius |
| Reduzierte Temperatur HK1 | `0x2307` | 1 | Grad Celsius |
| Komforttemperatur HK1 | `0x2308` | 1 | Grad Celsius |
| Heizkennlinie Neigung | `0x27D3` | 1 | Faktor 0,1 |
| Heizkennlinie Niveau | `0x27D4` | 1 | vorzeichenbehaftet |
| Warmwasser-Sollwert | `0x6300` | 1 | Grad Celsius |
| HK1-Zeitprogramm Montag | `0x2000` | 8 | vier Zeitfenster |
| Warmwasser Montag | `0x2100` | 8 | vier Zeitfenster |
| Zirkulation Montag | `0x2200` | 8 | vier Zeitfenster |
| Aktueller Alarm (`nvoAlarm`) | `0xA132` | 29 | Zeitstempel, gestörter Teilnehmer und Fehlercode |
| Sammelstörung | `0xA152` | 2 | Byte 0, Bit `0x01`; neuer/unquittierter Alarm |
| Fehlerhistorie, neuester Eintrag | `0x7507` | 9 | Code und Zeitstempel |

Die folgenden Wochentage liegen jeweils im Abstand von acht Byte. Dadurch
reichen die Bereiche `0x2000` bis `0x2030`, `0x2100` bis `0x2130` und `0x2200`
bis `0x2230` von Montag bis Sonntag.

## Schreibbare Funktionen

`homeassistant_poll_list.py` selbst ist vollständig read-only. Ausschließlich
der Zusatzdienst `vitodens_ww_actions.py` führt die folgenden Schreibzugriffe
nach einer ausdrücklichen Bedienaktion aus:

| Funktion | Adresse/Bereich | Zulässiger Wert |
| --- | ---: | --- |
| Betriebsart HK1 | `0x2323` | `0` Aus, `1` Nur Warmwasser, `2` Heizen und Warmwasser |
| Sparbetrieb HK1 | `0x2331` | `0` oder `1` |
| Partybetrieb HK1 | `0x2330` | `0` oder `1` |
| Normaltemperatur HK1 | `0x2306` | 3 bis 37 °C |
| Reduzierte Temperatur HK1 | `0x2307` | 3 bis 37 °C |
| Komforttemperatur HK1 | `0x2308` | 4 bis 37 °C |
| Warmwasser-Sollwert | `0x6300` | 10 bis 60 °C |
| Heizkennlinie Neigung | `0x27D3` | 0,2 bis 3,5 in 0,1-Schritten |
| Heizkennlinie Niveau | `0x27D4` | -13 bis 40 |
| HK1-Zeitprogramme | `0x2000` bis `0x2030` | vier Zeitfenster je Tag |
| Warmwasser-Zeitprogramme | `0x2100` bis `0x2130` | vier Zeitfenster je Tag |
| Zirkulations-Zeitprogramme | `0x2200` bis `0x2230` | vier Zeitfenster je Tag |

Zeitpunkte werden in Zehn-Minuten-Schritten codiert. Ein unbenutztes Fenster
besteht aus `0xFF 0xFF`. Beim Schreiben eines Tages wird immer der vollständige
Acht-Byte-Block übertragen und danach zurückgelesen. Die Bereiche und Grenzwerte
sind nur für den dokumentierten Gerätetyp geprüft.

## Polling

Das Basisintervall beträgt zehn Sekunden. Je nach Gruppe wird ein Datenpunkt alle
10, 30, 120 oder 600 Sekunden gelesen. Die Zuordnung steht direkt in
`homeassistant_poll_list.py`; eine verständliche Übersicht befindet sich unter
[Architektur und Betriebsdaten](architecture.md).
