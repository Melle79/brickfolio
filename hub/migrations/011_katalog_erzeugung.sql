-- Der Hub erzeugt den Abzug jetzt selbst statt ihn nur entgegenzunehmen.
--
-- Bis 2.40.0 klapperte jede Instanz BrickLink ab und liess ein eigenes
-- Sehmodell die Bilder beschreiben. Viermal dieselbe Arbeit fuer dasselbe
-- Ergebnis, und jede Instanz brauchte dafuer eigene BrickLink-Zugangsdaten.
-- Hier steht, wie weit der Hub mit jedem Thema ist.

CREATE TABLE IF NOT EXISTS katalog_lauf (
  praefix    TEXT PRIMARY KEY,          -- „sw", „cty", „cas" …
  -- Drei oder vier Ziffern. 0 heisst „noch nicht ermittelt"; der Lauf misst
  -- es dann selbst nach. Fest verdrahtete vier Ziffern liessen am
  -- 21.08.2026 acht Themen komplett leer ausgehen – und meldeten „fertig".
  breite     INTEGER NOT NULL DEFAULT 0,
  zuletzt    INTEGER NOT NULL DEFAULT 0,   -- letzte geprueft Nummer
  -- 404 am Stueck. BrickLink laesst Luecken in der Nummerierung; erst nach
  -- 25 aufeinander folgenden gilt ein Thema als durch.
  luecke     INTEGER NOT NULL DEFAULT 0,
  gefunden   INTEGER NOT NULL DEFAULT 0,
  fertig_at  INTEGER,
  aktiv      INTEGER NOT NULL DEFAULT 1
);

-- Die am 21./24.08.2026 gemessenen Themen. Keine vollstaendige Liste --
-- BrickLink gibt keine heraus --, aber alle, die der Abzug bisher gefunden
-- hat. Weitere traegt man einfach dazu; die Breite misst der Lauf selbst.
INSERT OR IGNORE INTO katalog_lauf (praefix) VALUES
  ('sw'), ('cty'), ('njo'), ('sh'), ('frnd'), ('cas'), ('pi'), ('hp'),
  ('jw'), ('sp'), ('ww'), ('lor'), ('iaj'), ('gen'), ('col'), ('adv'),
  ('trn'), ('idea');
