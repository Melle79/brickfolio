-- Angebotsabgaben, verschlüsselte Nachrichten und Meldungen (Issue #2)
--
-- Gefahrlos wiederholbar: legt nur an, löscht nichts. Die alte, nie benutzte
-- messages-Tabelle aus Stufe 1 bleibt einfach liegen – die neuen Umschläge
-- stehen bewusst in trade_messages.
--
--   npx wrangler d1 execute brickfolio-hub --remote --file=migrations/003_trades_messages.sql

CREATE TABLE IF NOT EXISTS trades (
  id           TEXT PRIMARY KEY,
  from_member  TEXT NOT NULL,
  to_member    TEXT NOT NULL,
  item_id      TEXT NOT NULL,
  item_name    TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'open',
  created_at   INTEGER NOT NULL,
  updated_at   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trades_parties
  ON trades(to_member, from_member, updated_at);

CREATE TABLE IF NOT EXISTS trade_messages (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  trade_id    TEXT NOT NULL,
  from_member TEXT NOT NULL,
  to_member   TEXT NOT NULL,
  box         TEXT NOT NULL,
  created_at  INTEGER NOT NULL,
  fetched_at  INTEGER,
  acked_at    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_msg_to ON trade_messages(to_member, fetched_at);
CREATE INDEX IF NOT EXISTS idx_msg_trade ON trade_messages(trade_id, id);

CREATE TABLE IF NOT EXISTS reports (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  trade_id    TEXT,
  reporter    TEXT NOT NULL,
  against     TEXT NOT NULL,
  reason      TEXT NOT NULL,
  disclosed   TEXT,
  status      TEXT NOT NULL DEFAULT 'open',
  created_at  INTEGER NOT NULL,
  handled_at  INTEGER,
  handled_by  TEXT,
  note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status, created_at);
