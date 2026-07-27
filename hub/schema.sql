-- Brickfolio-Hub – D1-Schema (Cloudflare)
-- Dünne Austausch-Schicht: NUR freigegebene Angebote, Identitäten und (später)
-- Postfach. KEINE Sammlungen, keine Bilder-Blobs, kein Volltext.

CREATE TABLE IF NOT EXISTS members (
  id           TEXT PRIMARY KEY,            -- öffentliche Member-ID (mem_…)
  display_name TEXT NOT NULL,
  token_hash   TEXT NOT NULL UNIQUE,        -- SHA-256 des Instanz-Tokens
  is_admin     INTEGER NOT NULL DEFAULT 0,
  status       TEXT NOT NULL DEFAULT 'active',   -- active | disabled
  invite_quota INTEGER NOT NULL DEFAULT 3,  -- wie viele Einladungen erlaubt
  public_key   TEXT,                        -- für Ende-zu-Ende-Nachrichten
  created_at   INTEGER NOT NULL,
  last_seen_at INTEGER
);

-- Wer mehr als sein Kontingent einladen möchte, stellt eine Anfrage; ein
-- Hub-Admin genehmigt sie (erhöht das Kontingent) oder lehnt ab.
CREATE TABLE IF NOT EXISTS invite_requests (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  member_id   TEXT NOT NULL,
  reason      TEXT,
  want        INTEGER NOT NULL DEFAULT 3,
  status      TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | denied
  created_at  INTEGER NOT NULL,
  decided_at  INTEGER,
  decided_by  TEXT
);
CREATE INDEX IF NOT EXISTS idx_invreq_status
  ON invite_requests(status, created_at);

CREATE TABLE IF NOT EXISTS invites (
  code_hash   TEXT PRIMARY KEY,             -- SHA-256 des Einladungscodes
  created_by  TEXT,                         -- Member-ID des Einladenden
  note        TEXT,
  expires_at  INTEGER,                      -- NULL = unbegrenzt
  redeemed_by TEXT,                         -- Member-ID, NULL = noch offen
  redeemed_at INTEGER,
  created_at  INTEGER NOT NULL
);

-- Freigegebener Abgebbar-Bestand einer Instanz. Beim Sync ersetzt eine Instanz
-- ihren KOMPLETTEN Satz (delete-all + insert), damit entfernte Angebote auch
-- wieder verschwinden.
CREATE TABLE IF NOT EXISTS offers (
  member_id     TEXT NOT NULL,
  item_id       TEXT NOT NULL,
  item_type     TEXT NOT NULL,
  name          TEXT NOT NULL,
  img_url       TEXT,
  img_data      TEXT,                       -- kleines Bild für eigene Figuren
  bricklink_url TEXT,
  condition     TEXT,
  qty           INTEGER NOT NULL DEFAULT 1,
  note          TEXT,
  updated_at    INTEGER NOT NULL,
  PRIMARY KEY (member_id, item_id, item_type, condition)
);
CREATE INDEX IF NOT EXISTS idx_offers_member ON offers(member_id);
CREATE INDEX IF NOT EXISTS idx_offers_item   ON offers(item_id, item_type);

-- Angebotsabgaben: „Ich hätte Interesse an deinem Yoda.“ Der Hub kennt nur
-- die Beteiligten und den Artikel – der Text steckt in den Nachrichten und
-- ist Ende-zu-Ende verschlüsselt.
CREATE TABLE IF NOT EXISTS trades (
  id           TEXT PRIMARY KEY,            -- trd_…
  from_member  TEXT NOT NULL,
  to_member    TEXT NOT NULL,
  item_id      TEXT NOT NULL,
  item_name    TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'open',  -- open|accepted|declined|closed
  created_at   INTEGER NOT NULL,
  updated_at   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trades_parties
  ON trades(to_member, from_member, updated_at);

-- Briefkasten: verschlüsselte Umschläge. Sie verschwinden, sobald der
-- Empfänger sie geholt UND der Absender die Zustellung gesehen hat.
CREATE TABLE IF NOT EXISTS trade_messages (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  trade_id    TEXT NOT NULL,
  from_member TEXT NOT NULL,
  to_member   TEXT NOT NULL,
  box         TEXT NOT NULL,                -- verschlüsselter Umschlag
  created_at  INTEGER NOT NULL,
  fetched_at  INTEGER,                      -- vom Empfänger geholt
  acked_at    INTEGER                       -- vom Absender als zugestellt gesehen
);
CREATE INDEX IF NOT EXISTS idx_msg_to ON trade_messages(to_member, fetched_at);
CREATE INDEX IF NOT EXISTS idx_msg_trade ON trade_messages(trade_id, id);

-- Meldungen. Wer meldet, gibt den Verlauf selbst frei (entschlüsselt auf der
-- eigenen Instanz) – der Hub kann Nachrichten nicht von sich aus lesen.
CREATE TABLE IF NOT EXISTS reports (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  trade_id    TEXT,
  reporter    TEXT NOT NULL,
  against     TEXT NOT NULL,
  reason      TEXT NOT NULL,
  disclosed   TEXT,                         -- freiwillig offengelegter Verlauf
  status      TEXT NOT NULL DEFAULT 'open', -- open|handled
  created_at  INTEGER NOT NULL,
  handled_at  INTEGER,
  handled_by  TEXT,
  note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status, created_at);
