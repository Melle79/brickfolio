-- Die **Einschätzung** bleibt im Hub, der Rohbericht nicht.
--
-- Der Rohverlauf sind bis zu 200 KB Messwerte – die gehören abgeholt und
-- weggeräumt, sonst ist der Hub doch wieder ein Archiv. Was Sven ansehen
-- will, ist aber nicht die Zahlenkolonne, sondern was dabei herauskam. Das
-- sind ein paar hundert Zeichen und bleibt hier liegen.
--
-- `prio` von 1 (höchste) bis 5. Die Meldung aufs Handy trägt nur Priorität
-- und einen Satz; alles Weitere steht in der Konsole. Ein Bericht, der als
-- Benachrichtigung nach drei Absätzen abgeschnitten wird, ist keiner.
CREATE TABLE IF NOT EXISTS crash_findings (
  id           TEXT PRIMARY KEY,
  label        TEXT NOT NULL,
  app_version  TEXT,
  crashes      INTEGER NOT NULL DEFAULT 0,
  views        TEXT,
  prio         INTEGER NOT NULL DEFAULT 5,
  kurz         TEXT NOT NULL,
  analyse      TEXT,
  erledigt     INTEGER NOT NULL DEFAULT 0,
  created_at   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_findings_created ON crash_findings(created_at);
CREATE INDEX IF NOT EXISTS idx_findings_offen ON crash_findings(erledigt, prio);
