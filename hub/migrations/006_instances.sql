-- Instanz-Kennung: die Installation bleibt dieselbe, auch wenn das
-- Mitgliedskonto wechselt. Nur anlegen und erweitern – nie löschen.
CREATE TABLE IF NOT EXISTS instances (
  id           TEXT PRIMARY KEY,
  code         TEXT NOT NULL UNIQUE,
  secret_hash  TEXT NOT NULL,
  first_name   TEXT NOT NULL,
  blocked      INTEGER NOT NULL DEFAULT 0,
  note         TEXT,
  created_at   INTEGER NOT NULL,
  last_seen_at INTEGER
);

ALTER TABLE members ADD COLUMN instance_id TEXT;
CREATE INDEX IF NOT EXISTS idx_members_instance ON members(instance_id);
