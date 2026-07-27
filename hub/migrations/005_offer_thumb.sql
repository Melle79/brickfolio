-- Vorschaubild für eigene Figuren (Issue: Custom-Bilder im Tauschnetzwerk)
--
-- Eigene Figuren haben nur einen instanz-lokalen Pfad; damit sie beim
-- Gegenüber sichtbar sind, reist ein verkleinertes Bild als Daten-URL mit.
-- Steht allein in einer Datei, weil ALTER TABLE beim zweiten Lauf meckert.
--
--   npx wrangler d1 execute brickfolio-hub --remote --file=migrations/005_offer_thumb.sql

ALTER TABLE offers ADD COLUMN img_data TEXT;
