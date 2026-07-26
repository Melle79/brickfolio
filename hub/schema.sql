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
  bricklink_url TEXT,
  condition     TEXT,
  qty           INTEGER NOT NULL DEFAULT 1,
  note          TEXT,
  updated_at    INTEGER NOT NULL,
  PRIMARY KEY (member_id, item_id, item_type, condition)
);
CREATE INDEX IF NOT EXISTS idx_offers_member ON offers(member_id);
CREATE INDEX IF NOT EXISTS idx_offers_item   ON offers(item_id, item_type);

-- Postfach (Stufe 3) – Struktur schon da, wird später genutzt.
CREATE TABLE IF NOT EXISTS messages (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  from_member TEXT NOT NULL,
  to_member   TEXT NOT NULL,
  item_id     TEXT,                         -- optionaler Bezug auf ein Angebot
  body        TEXT NOT NULL,
  created_at  INTEGER NOT NULL,
  read_at     INTEGER
);
CREATE INDEX IF NOT EXISTS idx_msg_to ON messages(to_member, read_at);
