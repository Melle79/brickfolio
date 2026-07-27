-- Öffentlicher Schlüssel je Mitglied, für Ende-zu-Ende-Nachrichten (Issue #2)
--
-- Steht bewusst allein in einer Datei: ALTER TABLE lässt sich in SQLite nicht
-- „nur falls nötig" schreiben. Läuft die Erweiterung ein zweites Mal, meldet
-- sie „duplicate column name" – das ist der Normalfall und stört nichts.
--
--   npx wrangler d1 execute brickfolio-hub --remote --file=migrations/004_public_key.sql

ALTER TABLE members ADD COLUMN public_key TEXT;
