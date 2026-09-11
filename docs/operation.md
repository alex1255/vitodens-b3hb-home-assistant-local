# Bedienkonzept

## Kontrolle

Die erste Ansicht bündelt häufige Aktionen und Livewerte:

- Betriebsart: Aus, Nur Warmwasser, Heizen und Warmwasser
- dauerhafter Spar- und Partybetrieb
- normale, reduzierte und Komfort-Solltemperatur für HK1
- Warmwasser-Solltemperatur
- Warmwasserfreigabe für 30 oder 60 Minuten
- Heizkennlinie mit Neigung und Niveau
- Anlagenzeit und aktuelle Betriebswerte

Die temporäre Warmwasserfreigabe erweitert das aktuelle Zeitfenster. Der
vorherige Wochenplan wird gesichert und nach Ablauf wiederhergestellt. Der
Wiederherstellen-Button kann dies vorzeitig auslösen.

## Zeitprogramme

Die zweite Ansicht zeigt HK1, Warmwasser und Zirkulation als Tagesbalken. Pro
Tag kann ein gespeichertes Profil ausgewählt und anschließend bewusst in die
Heizung geschrieben werden.

## Profile

Die dritte Ansicht bearbeitet ausschließlich die Profile `Schaukelstuhl` und
`Werktag`. Jedes Programm besitzt eigene Profilzeiten:

- HK1
- Warmwasser
- Zirkulation

Ein Profil ist zunächst nur lokal gespeichert. Erst die Anwendung in der
Zeitprogramm-Ansicht schreibt es auf ausgewählte Tage der Heizung.

## Fehlermeldungen

Der erste Eintrag der Viessmann-Fehlerhistorie wird zyklisch gelesen. Der
neun Byte lange Datensatz enthält Fehlercode und Anlagenzeit. Ein neuer
Zeitstempel erzeugt auch bei identischem Fehlercode ein neues Ereignis.

Code `00` bedeutet keine Störung und löst keine Push-Nachricht aus. Unbekannte
Codes werden mit ihrem Hex-Code angezeigt, damit sie anhand der Serviceunterlage
des konkreten Geräts geprüft werden können.

