-- Einladungs-Kontingent und Mehr-Anfragen (Issue #4)
--
-- Einmalig auf eine bestehende Hub-Datenbank anwenden:
--   npx wrangler d1 execute brickfolio-hub --remote --file=migrations/002_invite_quota.sql
--
-- Bei einer frisch angelegten Datenbank steckt beides schon in schema.sql;
-- dann meldet die erste Zeile "duplicate column name" – das ist unkritisch,
-- die Datenbank ist bereits auf dem Stand.

ALTER TABLE members ADD COLUMN invite_quota INTEGER NOT NULL DEFAULT 3;

CREATE TABLE IF NOT EXISTS invite_requests (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  member_id   TEXT NOT NULL,
  reason      TEXT,
  want        INTEGER NOT NULL DEFAULT 3,
  status      TEXT NOT NULL DEFAULT 'pending',
  created_at  INTEGER NOT NULL,
  decided_at  INTEGER,
  decided_by  TEXT
);
CREATE INDEX IF NOT EXISTS idx_invreq_status
  ON invite_requests(status, created_at);
