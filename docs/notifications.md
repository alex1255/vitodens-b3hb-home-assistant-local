# Störungsmeldungen auf das Handy

Der Raspberry veröffentlicht zwei unterschiedliche Informationen über MQTT:

- `binary_sensor.vitodens_stoerung_aktiv` meldet eine aktive Sammelstörung.
- `sensor.vitodens_stoerung_aktuell` liefert, soweit auslesbar, Fehlercode,
  Klartext und Zeitstempel aus der Heizung.

Die mitgelieferte Automation sendet diese Angaben als Push-Mitteilung und öffnet
beim Antippen direkt die Kontrollseite des Vitodens-Dashboards.

## 1. Mobilgerät in Home Assistant einrichten

1. Die Home-Assistant-Companion-App auf dem Mobilgerät installieren und mit dem
   eigenen Home Assistant verbinden.
2. Benachrichtigungen für die App im Betriebssystem erlauben.
3. In Home Assistant unter **Entwicklerwerkzeuge > Aktionen** nach
   `notify.mobile_app` suchen.
4. Den vollständigen Aktionsnamen des gewünschten Geräts notieren, zum Beispiel
   `notify.mobile_app_mein_telefon`.

Erscheint keine solche Aktion, die Companion-App einmal öffnen und unter
**Einstellungen > Begleit-App > Benachrichtigungen** prüfen, ob Push-Mitteilungen
aktiviert sind.

## 2. Automation importieren

1. **Einstellungen > Automatisierungen & Szenen > Automatisierungen** öffnen.
2. Eine neue leere Automation anlegen.
3. Im Dreipunktmenü **In YAML bearbeiten** wählen.
4. Den Inhalt von
   [`examples/fault-notification-automation.yaml`](../examples/fault-notification-automation.yaml)
   einfügen.
5. `notify.mobile_app_your_phone` durch den zuvor ermittelten Aktionsnamen
   ersetzen und speichern.
6. Optional die Automation mit dem Home-Assistant-Label **Notify** versehen.

Die Zieladresse `/vitodens-lokal/kontrolle` setzt voraus, dass das Beispiel-
Dashboard unter dem Pfad `vitodens-lokal` angelegt wurde. Bei einem anderen
Dashboard-Pfad müssen `url` und `clickAction` angepasst werden.

## 3. Push-Funktion ohne Heizungsfehler testen

In **Entwicklerwerkzeuge > Aktionen** die eigene
`notify.mobile_app_mein_telefon`-Aktion auswählen und eine harmlose Testnachricht
senden. Damit werden App-Berechtigung und Zustellung geprüft, ohne an der Heizung
eine Störung zu erzeugen.

Danach die Automation öffnen und über **Ausführen** einmal manuell starten. Die
Bedingung einer aktiven Störung kann diesen manuellen Test verhindern. Für einen
reinen Funktionstest darf die Bedingung kurzzeitig in der UI deaktiviert werden;
anschließend muss sie wieder aktiviert werden.

## Verhalten und Grenzen

- Gemeldet wird nur eine **aktive** Sammelstörung.
- Sobald die Detaildaten eintreffen, enthält die Nachricht nach Möglichkeit
  Klartext, Fehlercode und Heizungszeitpunkt.
- Das Quittieren am Heizungsdisplay bedeutet nicht zwingend, dass die Ursache
  behoben oder der Eintrag aus dem Fehlerspeicher gelöscht ist.
- Unbekannte herstellerspezifische Codes können ohne Klartext erscheinen.
- Der auffällige Störungsstatus bleibt zusätzlich oben auf der Kontrollseite
  sichtbar.

Bei ausbleibenden Nachrichten zuerst den Zustand beider Entitäten, dann die
Spuren der Automation und zuletzt die Benachrichtigungseinstellungen des
Mobilgeräts prüfen.
