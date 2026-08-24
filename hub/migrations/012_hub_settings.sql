-- Einstellungen, die sich ohne Deploy aendern lassen sollen.
--
-- Der BrickLink-Zugang gehoert eigentlich in `wrangler secret put`: Dort
-- liegt er verschluesselt und ist nicht zurueckzulesen. Ein Wechsel setzt
-- dann aber einen Rechner mit angemeldetem Wrangler voraus -- und wenn sich
-- die Zugangsdaten einmal aendern, ist das der unbequemere Weg.
--
-- Der Preis steht hier im Klartext: Wer an diese Tabelle kommt, liest sie.
-- Was sich dagegen tun liess, ist getan -- die Konsole gibt die Werte nie
-- zurueck, sondern nur „gesetzt (24 Zeichen)". Das schuetzt nicht gegen
-- Datenbankzugriff, aber gegen alles davor.
--
-- Was in `hub_settings` fehlt, wird weiter aus den Secrets genommen. Beides
-- geht also nebeneinander; die Datenbank hat Vorrang.
CREATE TABLE IF NOT EXISTS hub_settings (
  name       TEXT PRIMARY KEY,
  value      TEXT NOT NULL,
  updated_at INTEGER NOT NULL
);
