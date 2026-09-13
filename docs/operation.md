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

Der Button beendet keine bereits laufende Speicherladung hart. **WW Erzeugung**
zeigt den Zustand der Speicherladepumpe und ist damit aussagekräftiger als die
Betriebsart. **Letzte Aktion** meldet Annahme, Fehler oder Bestätigung eines
Schreibbefehls. Manche regelmäßig gelesenen Werte erscheinen erst beim nächsten
Polling aktualisiert.

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

Die Profile gelten getrennt für HK1, Warmwasser und Zirkulation. Das gleichnamige
Profil kann deshalb in jedem der drei Programme andere Zeitfenster enthalten.
Jedes Tagesprogramm unterstützt maximal vier Fenster in Zehn-Minuten-Schritten.

## Fehlermeldungen

Die Störungserkennung kombiniert drei Quellen. Das Sammelstörungsbit im
Relaisstatus `0xA152` meldet einen neuen, noch nicht quittierten Alarm
unmittelbar. Der aktuelle `nvoAlarm`-Block an `0xA132` liefert zusätzlich
Zeitstempel, gestörten Teilnehmer und Fehlercode. Dadurch kann Home Assistant
zum Beispiel `Störung Teilnehmer 99` statt nur einer allgemeinen Meldung senden.

Der erste Eintrag der Viessmann-Fehlerhistorie an `0x7507` wird zusätzlich
zyklisch gelesen. Der neun Byte lange Datensatz enthält Fehlercode und
Anlagenzeit. Sobald dieser Eintrag aktualisiert wurde, ersetzt der Dienst den
allgemeinen Störungstext durch Code, Klartext und Zeitstempel. Ein neuer
Zeitstempel erzeugt auch bei identischem Fehlercode ein neues Ereignis.

Code `00` bedeutet keine Störung und löst keine Push-Nachricht aus. Unbekannte
Codes werden mit ihrem Hex-Code angezeigt, damit sie anhand der Serviceunterlage
des konkreten Geräts geprüft werden können.

Eine Quittierung kann das Sammelstörungsbit löschen, obwohl das Warndreieck am
Regler noch sichtbar ist. Quittiert ist deshalb nicht gleichbedeutend mit
behoben; maßgeblich bleibt die Anzeige am Gerät, bis ein belastbarer Datenpunkt
für diesen gespeicherten Anzeigezustand identifiziert ist.

Die Einrichtung der Push-Mitteilung ist unter
[Störungsmeldungen auf das Handy](notifications.md) beschrieben.
