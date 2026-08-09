-- Fehlerberichte: ein Kanal, der **neben** dem Tausch-Netzwerk steht.
--
-- Bewusst eigene Tabellen und eigene Token statt der Mitglieds-Token:
--
-- 1. Nicht jede Instanz ist Mitglied. Von vier Instanzen im Haushalt waren
--    es zwei – ein Kanal am Mitgliedskonto hätte die Hälfte stumm gelassen,
--    und zwar ausgerechnet die, deren Daten am meisten erklärt hätten.
-- 2. Wer einen Fehlerbericht schickt, gibt damit nichts über sein Tauschen
--    preis. Der Token hier kann nichts anderes als Berichte abliefern: Er
--    kommt in der Mitglieder-Tabelle gar nicht vor.
-- 3. Umgekehrt lässt sich der Kanal einzeln sperren, ohne jemandem das
--    Tauschen zu nehmen.

CREATE TABLE IF NOT EXISTS report_tokens (
  id           TEXT PRIMARY KEY,
  label        TEXT NOT NULL,          -- „Kello", „Nerdfan" – wer schickt
  token_hash   TEXT NOT NULL UNIQUE,
  revoked      INTEGER NOT NULL DEFAULT 0,
  created_at   INTEGER NOT NULL,
  last_seen_at INTEGER
);

CREATE TABLE IF NOT EXISTS crash_reports (
  id           TEXT PRIMARY KEY,
  token_id     TEXT NOT NULL REFERENCES report_tokens(id),
  label        TEXT NOT NULL,          -- mitgeschrieben, damit der Bericht
                                       -- lesbar bleibt, wenn der Token weg ist
  app_version  TEXT,
  crashes      INTEGER NOT NULL DEFAULT 0,
  views        TEXT,                   -- „scan (2×), collection"
  payload      TEXT NOT NULL,          -- der Verlauf, wie er gezeigt wurde
  created_at   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_crash_created ON crash_reports(created_at);
CREATE INDEX IF NOT EXISTS idx_crash_label ON crash_reports(label);
