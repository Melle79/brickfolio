-- Der Katalogabzug zieht in den Hub.
--
-- Bisher baute ihn jede Instanz selbst: Nummern der Reihe nach bei BrickLink
-- abklappern (Tage, eigenes Kontingent) und anschliessend jedes Bild von
-- einem Sehmodell beschreiben lassen (rund 24 Stunden Grafikeinheit fuer
-- 9.741 Figuren). Dreimal dieselbe Arbeit fuer dasselbe Ergebnis -- der
-- Katalog ist fuer alle identisch, er beschreibt BrickLinks Fotos und nicht
-- die Sammlung von irgendwem.
--
-- Hier liegt er nun einmal. Die Instanzen holen sich einen Schnappschuss.

CREATE TABLE IF NOT EXISTS katalog (
  item_no      TEXT NOT NULL,
  item_type    TEXT NOT NULL DEFAULT 'minifig',
  name         TEXT NOT NULL DEFAULT '',   -- Katalogtext von BrickLink
  such         TEXT NOT NULL DEFAULT '',   -- derselbe Text ohne Satzzeichen
  category_id  TEXT NOT NULL DEFAULT '',
  jahr         INTEGER NOT NULL DEFAULT 0,
  img_url      TEXT NOT NULL DEFAULT '',
  -- Was auf dem Bild zu sehen ist. Das ist die teure Haelfte und stammt
  -- nicht von BrickLink, sondern aus der Bildanalyse.
  farben       TEXT NOT NULL DEFAULT '',
  art          TEXT NOT NULL DEFAULT '',
  merkmale     TEXT NOT NULL DEFAULT '',
  -- Welches Modell die Beschreibung erzeugt hat.
  --
  -- Nicht Zierde: Modelle sehen unterschiedlich. Am 22.08.2026 gemessen
  -- machte `qwen2.5vl` aus Luke Skywalker einen "Knight" und faerbte den
  -- ganzen Torso "tan", wo `qwen3-vl` "white tunic" sah. Ohne diese Spalte
  -- waere ein Modellwechsel ein stilles Umschreiben aller Zeilen, und
  -- niemand koennte zwei Beschreibungen daraufhin ansehen, ob sie
  -- ueberhaupt vergleichbar sind.
  modell       TEXT NOT NULL DEFAULT '',
  updated_at   INTEGER NOT NULL,
  PRIMARY KEY (item_no, item_type)
);

-- Die Instanzen holen nur, was sich seit ihrem Stand geaendert hat.
CREATE INDEX IF NOT EXISTS idx_katalog_stand ON katalog(updated_at);

-- Schreibrecht als eigenes Recht, wie `can_collect` bei den Absturzberichten.
--
-- Es muss auf dieser Seite stehen, nicht in der App: Die Instanzen sind
-- selbst gehostet: Wer seinen eigenen Container betreibt, kann dessen Code
-- aendern, und eine Absprache "nur eine Instanz laedt hoch" waere damit
-- keine Regel, sondern eine Bitte.
--
-- Der Schaden waere auch nicht Unordnung, sondern Verschlechterung: Eine
-- schwaechere Analyse ueberschreibt eine bessere, und man sieht es der
-- Beschreibung nicht an. Eine falsche Bildanalyse schadet mehr als keine.
ALTER TABLE report_tokens ADD COLUMN can_katalog INTEGER NOT NULL DEFAULT 0;
