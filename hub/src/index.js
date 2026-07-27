/**
 * Brickfolio-Hub – Cloudflare Worker (Stufe 1: Registrierung/Token, Freigabe/
 * Push, Angebote lesen). Dünne Austausch-Schicht über D1.
 *
 * Auth: jede Instanz spricht server-zu-server mit einem Bearer-Token; der Token
 * bleibt auf der Instanz (nie im Browser). Deshalb kein CORS nötig.
 */

const MAX_OFFERS = 2000;              // Obergrenze je Instanz (Missbrauchsschutz)
const OFFER_FIELDS = ["item_id", "item_type", "name", "img_url",
  "bricklink_url", "condition", "qty", "note"];

/* ----------------------------------------------------------------- Helfer */

const now = () => Math.floor(Date.now() / 1000);

/* CORS: Die Admin-Konsole ist eine eigene Seite auf anderer Domain und ruft
   den Hub direkt aus dem Browser. Geschützt wird über den Bearer-Token, nicht
   über Cookies – deshalb ist „*" hier unbedenklich (kein Credential-Modus). */
const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
  "access-control-allow-headers": "authorization,content-type",
  "access-control-max-age": "86400",
};

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", ...CORS },
  });
const err = (status, message) => json({ error: message }, status);

function randomToken(prefix) {
  const b = new Uint8Array(24);
  crypto.getRandomValues(b);
  const hex = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${prefix}_${hex}`;
}

async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((x) => x.toString(16).padStart(2, "0")).join("");
}

function bearer(req) {
  const h = req.headers.get("authorization") || "";
  const m = h.match(/^Bearer\s+(.+)$/i);
  return m ? m[1].trim() : null;
}

async function auth(req, env) {
  const tok = bearer(req);
  if (!tok) return null;
  const row = await env.DB.prepare(
    "SELECT * FROM members WHERE token_hash = ? AND status = 'active'")
    .bind(await sha256(tok)).first();
  if (row) {
    // last_seen best-effort, nicht blockierend fürs Ergebnis
    env.DB.prepare("UPDATE members SET last_seen_at = ? WHERE id = ?")
      .bind(now(), row.id).run();
  }
  return row || null;
}

/* --------------------------------------------------------------- Endpunkte */

const MIN_NAME = 4;

/* Ist der Anzeigename schon vergeben? Groß-/Kleinschreibung ignorieren,
   damit „Paul" und „paul" nicht nebeneinander stehen. */
async function nameTaken(env, name, exceptId = null) {
  const row = await env.DB.prepare(
    "SELECT id FROM members WHERE lower(display_name) = lower(?)")
    .bind(name).first();
  return !!row && row.id !== exceptId;
}

async function register(req, env) {
  const body = await req.json().catch(() => ({}));
  const name = (body.display_name || "").toString().trim().slice(0, 80);
  if (!name) return err(400, "display_name fehlt");
  if (name.length < MIN_NAME) {
    return err(400, `Der Name braucht mindestens ${MIN_NAME} Zeichen`);
  }
  if (await nameTaken(env, name)) {
    return err(409, `Der Name „${name}" ist im Netzwerk schon vergeben – `
      + "bitte einen anderen wählen");
  }

  let isAdmin = 0;
  const count = (await env.DB.prepare("SELECT COUNT(*) AS c FROM members").first()).c;

  // Erststart: mit dem Bootstrap-Secret wird der erste Admin angelegt.
  if (body.bootstrap_secret) {
    if (!env.HUB_BOOTSTRAP_SECRET || body.bootstrap_secret !== env.HUB_BOOTSTRAP_SECRET) {
      return err(403, "Bootstrap-Secret ungültig");
    }
    isAdmin = 1;
  } else {
    // Sonst: gültigen, offenen Einladungscode einlösen.
    const code = (body.invite_code || "").toString().trim();
    if (!code) return err(400, "invite_code fehlt");
    const inv = await env.DB.prepare("SELECT * FROM invites WHERE code_hash = ?")
      .bind(await sha256(code)).first();
    if (!inv) return err(403, "Einladungscode unbekannt");
    if (inv.redeemed_by) return err(409, "Einladungscode bereits benutzt");
    if (inv.expires_at && inv.expires_at < now()) return err(410, "Einladungscode abgelaufen");
  }

  const id = randomToken("mem");
  const token = randomToken("bft");           // brickfolio token
  const t = now();
  await env.DB.prepare(
    "INSERT INTO members (id, display_name, token_hash, is_admin, created_at) "
    + "VALUES (?, ?, ?, ?, ?)")
    .bind(id, name, await sha256(token), isAdmin, t).run();

  if (!isAdmin && count > 0) {
    const code = (body.invite_code || "").toString().trim();
    await env.DB.prepare(
      "UPDATE invites SET redeemed_by = ?, redeemed_at = ? WHERE code_hash = ?")
      .bind(id, t, await sha256(code)).run();
  }
  // Token wird NUR hier einmal ausgeliefert.
  return json({ member_id: id, display_name: name, is_admin: !!isAdmin, token }, 201);
}

async function me(member) {
  return json({
    member_id: member.id, display_name: member.display_name,
    is_admin: !!member.is_admin, created_at: member.created_at,
  });
}

async function updateMe(req, member, env) {
  const body = await req.json().catch(() => ({}));
  const name = (body.display_name || "").toString().trim().slice(0, 80);
  if (!name) return err(400, "display_name fehlt");
  if (name.length < MIN_NAME) {
    return err(400, `Der Name braucht mindestens ${MIN_NAME} Zeichen`);
  }
  if (await nameTaken(env, name, member.id)) {
    return err(409, `Der Name „${name}" ist schon vergeben`);
  }
  await env.DB.prepare("UPDATE members SET display_name = ? WHERE id = ?")
    .bind(name, member.id).run();
  return json({ member_id: member.id, display_name: name,
                is_admin: !!member.is_admin });
}

async function rotateToken(member, env) {
  const token = randomToken("bft");
  await env.DB.prepare("UPDATE members SET token_hash = ? WHERE id = ?")
    .bind(await sha256(token), member.id).run();
  return json({ token });
}

async function putOffers(req, member, env) {
  const body = await req.json().catch(() => ({}));
  const list = Array.isArray(body.offers) ? body.offers : null;
  if (!list) return err(400, "offers[] fehlt");
  if (list.length > MAX_OFFERS) return err(413, `zu viele Angebote (max. ${MAX_OFFERS})`);

  const t = now();
  const stmts = [env.DB.prepare("DELETE FROM offers WHERE member_id = ?").bind(member.id)];
  const ins = env.DB.prepare(
    "INSERT OR REPLACE INTO offers (member_id, item_id, item_type, name, "
    + "img_url, bricklink_url, condition, qty, note, updated_at) "
    + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)");
  let n = 0;
  for (const o of list) {
    if (!o || !o.item_id || !o.name) continue;
    stmts.push(ins.bind(
      member.id, String(o.item_id).slice(0, 60),
      String(o.item_type || "minifig").slice(0, 20),
      String(o.name).slice(0, 200),
      o.img_url ? String(o.img_url).slice(0, 400) : null,
      o.bricklink_url ? String(o.bricklink_url).slice(0, 400) : null,
      o.condition ? String(o.condition).slice(0, 10) : null,
      Number(o.qty) > 0 ? Math.min(Number(o.qty), 9999) : 1,
      o.note ? String(o.note).slice(0, 300) : null, t));
    n += 1;
  }
  await env.DB.batch(stmts);          // atomar: erst leeren, dann neu füllen
  return json({ ok: true, count: n });
}

async function listOffers(req, member, env) {
  const url = new URL(req.url);
  const mine = url.searchParams.get("mine") === "1";
  const q = (url.searchParams.get("q") || "").trim().toLowerCase();
  const wantMember = url.searchParams.get("member");

  let sql = "SELECT o.*, m.display_name FROM offers o "
    + "JOIN members m ON m.id = o.member_id AND m.status = 'active' WHERE 1=1";
  const args = [];
  if (mine) { sql += " AND o.member_id = ?"; args.push(member.id); }
  else { sql += " AND o.member_id != ?"; args.push(member.id); }
  if (wantMember) { sql += " AND o.member_id = ?"; args.push(wantMember); }
  if (q) { sql += " AND (lower(o.name) LIKE ? OR lower(o.item_id) LIKE ?)";
    args.push(`%${q}%`, `%${q}%`); }
  sql += " ORDER BY o.updated_at DESC LIMIT 500";

  const rows = (await env.DB.prepare(sql).bind(...args).all()).results || [];
  return json({ offers: rows });
}

async function listMembers(member, env) {
  const rows = (await env.DB.prepare(
    "SELECT m.id, m.display_name, m.last_seen_at, "
    + "(SELECT COUNT(*) FROM offers o WHERE o.member_id = m.id) AS offer_count "
    + "FROM members m WHERE m.status = 'active' ORDER BY m.display_name").all()).results || [];
  return json({ members: rows });
}

const DEFAULT_QUOTA = 3;

/* Wie viele Einladungen hat jemand schon ausgesprochen und wie viele darf er? */
async function inviteQuota(member, env) {
  const used = (await env.DB.prepare(
    "SELECT COUNT(*) AS c FROM invites WHERE created_by = ?")
    .bind(member.id).first()).c || 0;
  const quota = member.invite_quota == null ? DEFAULT_QUOTA : member.invite_quota;
  const pending = await env.DB.prepare(
    "SELECT id, want, created_at FROM invite_requests "
    + "WHERE member_id = ? AND status = 'pending'").bind(member.id).first();
  return {
    used, quota, left: Math.max(0, quota - used),
    pending_request: pending ? { id: pending.id, want: pending.want,
                                 created_at: pending.created_at } : null,
  };
}

async function getQuota(member, env) {
  return json(await inviteQuota(member, env));
}

async function requestMoreInvites(req, member, env) {
  const body = await req.json().catch(() => ({}));
  const q = await inviteQuota(member, env);
  if (q.pending_request) {
    return err(409, "Es läuft schon eine Anfrage – bitte auf die Antwort warten");
  }
  const want = Math.max(1, Math.min(Number(body.want) || DEFAULT_QUOTA, 50));
  await env.DB.prepare(
    "INSERT INTO invite_requests (member_id, reason, want, created_at) "
    + "VALUES (?, ?, ?, ?)")
    .bind(member.id, body.reason ? String(body.reason).slice(0, 300) : null,
      want, now()).run();
  return json({ ok: true, want }, 201);
}

async function createInvite(req, member, env) {
  // Einladen darf jedes aktive Mitglied – begrenzt durch sein Kontingent.
  const q = await inviteQuota(member, env);
  if (q.left <= 0) {
    return json({
      error: `Dein Kontingent von ${q.quota} Einladungen ist aufgebraucht. `
        + "Du kannst weitere anfragen.",
      quota_reached: true, used: q.used, quota: q.quota,
      pending_request: !!q.pending_request,
    }, 403);
  }
  const body = await req.json().catch(() => ({}));
  const code = randomToken("inv");
  const days = Number(body.expires_in_days);
  const exp = days > 0 ? now() + Math.floor(days) * 86400 : null;
  await env.DB.prepare(
    "INSERT INTO invites (code_hash, created_by, note, expires_at, created_at) "
    + "VALUES (?, ?, ?, ?, ?)")
    .bind(await sha256(code), member.id,
      body.note ? String(body.note).slice(0, 120) : null, exp, now()).run();
  return json({ invite_code: code, expires_at: exp }, 201);   // Code nur einmal
}

/* --------------------------------- Schlüssel, Handel, Nachrichten (E2E) */

async function putKey(req, member, env) {
  const body = await req.json().catch(() => ({}));
  const key = (body.public_key || "").toString().trim().slice(0, 200);
  if (!key) return err(400, "public_key fehlt");
  await env.DB.prepare("UPDATE members SET public_key = ? WHERE id = ?")
    .bind(key, member.id).run();
  return json({ ok: true });
}

async function getKey(env, memberId) {
  const row = await env.DB.prepare(
    "SELECT id, display_name, public_key FROM members "
    + "WHERE id = ? AND status = 'active'").bind(memberId).first();
  if (!row) return err(404, "Mitglied nicht gefunden");
  if (!row.public_key) {
    return err(409, `${row.display_name} kann noch keine verschlüsselten `
      + "Nachrichten empfangen (Instanz muss sich einmal melden)");
  }
  return json({ member_id: row.id, display_name: row.display_name,
                public_key: row.public_key });
}

/* Angebotsabgabe eröffnen: Artikel + erste (verschlüsselte) Nachricht. */
async function createTrade(req, member, env) {
  const body = await req.json().catch(() => ({}));
  const to = (body.to || "").toString();
  const itemId = (body.item_id || "").toString().slice(0, 60);
  const itemName = (body.item_name || "").toString().slice(0, 200);
  const box = (body.box || "").toString();
  if (!to || !itemId || !box) return err(400, "to, item_id und box nötig");
  if (to === member.id) return err(400, "An sich selbst geht nicht");

  const other = await env.DB.prepare(
    "SELECT id FROM members WHERE id = ? AND status = 'active'")
    .bind(to).first();
  if (!other) return err(404, "Mitglied nicht gefunden");

  const id = randomToken("trd");
  const t = now();
  const res = await env.DB.batch([
    env.DB.prepare(
      "INSERT INTO trades (id, from_member, to_member, item_id, item_name, "
      + "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)")
      .bind(id, member.id, to, itemId, itemName, t, t),
    env.DB.prepare(
      "INSERT INTO messages (trade_id, from_member, to_member, box, created_at)"
      + " VALUES (?, ?, ?, ?, ?)").bind(id, member.id, to, box, t),
  ]);
  // Die Absender-Instanz braucht die ID, um später die Zustellung zu erkennen.
  const msgId = res[1] && res[1].meta ? res[1].meta.last_row_id : null;
  return json({ ok: true, trade_id: id, message_id: msgId }, 201);
}

async function listTrades(member, env) {
  const rows = (await env.DB.prepare(
    "SELECT t.*, "
    + "f.display_name AS from_name, o.display_name AS to_name, "
    + "(SELECT COUNT(*) FROM messages m WHERE m.trade_id = t.id "
    + " AND m.to_member = ? AND m.fetched_at IS NULL) AS unread "
    + "FROM trades t "
    + "LEFT JOIN members f ON f.id = t.from_member "
    + "LEFT JOIN members o ON o.id = t.to_member "
    + "WHERE t.from_member = ? OR t.to_member = ? "
    + "ORDER BY t.updated_at DESC LIMIT 200")
    .bind(member.id, member.id, member.id).all()).results || [];
  return json({ trades: rows });
}

async function sendMessage(req, member, env, tradeId) {
  const body = await req.json().catch(() => ({}));
  const box = (body.box || "").toString();
  if (!box) return err(400, "box fehlt");
  const t = await env.DB.prepare(
    "SELECT * FROM trades WHERE id = ?").bind(tradeId).first();
  if (!t) return err(404, "Vorgang nicht gefunden");
  if (t.from_member !== member.id && t.to_member !== member.id) {
    return err(403, "Nicht beteiligt");
  }
  const to = t.from_member === member.id ? t.to_member : t.from_member;
  const ts = now();
  const res = await env.DB.batch([
    env.DB.prepare(
      "INSERT INTO messages (trade_id, from_member, to_member, box, created_at)"
      + " VALUES (?, ?, ?, ?, ?)").bind(tradeId, member.id, to, box, ts),
    env.DB.prepare("UPDATE trades SET updated_at = ? WHERE id = ?")
      .bind(ts, tradeId),
  ]);
  const msgId = res[0] && res[0].meta ? res[0].meta.last_row_id : null;
  return json({ ok: true, message_id: msgId }, 201);
}

/* Nachrichten abholen. Dabei gilt die Abmachung aus dem Konzept: Umschläge
   bleiben nur so lange liegen, bis beide Seiten sie gesehen haben – der
   Empfänger holt sie ab, der Absender sieht die Zustellung. Danach löscht
   der Hub sie sofort. */
async function fetchMessages(member, env, tradeId) {
  const t = await env.DB.prepare("SELECT * FROM trades WHERE id = ?")
    .bind(tradeId).first();
  if (!t) return err(404, "Vorgang nicht gefunden");
  if (t.from_member !== member.id && t.to_member !== member.id) {
    return err(403, "Nicht beteiligt");
  }
  const ts = now();

  // Für mich bestimmte Umschläge – die bekomme ich genau einmal.
  const incoming = (await env.DB.prepare(
    "SELECT id, from_member, box, created_at FROM messages "
    + "WHERE trade_id = ? AND to_member = ? ORDER BY id")
    .bind(tradeId, member.id).all()).results || [];
  // Meine eigenen: nur der Zustellstatus, kein Inhalt nötig.
  const mine = (await env.DB.prepare(
    "SELECT id, created_at, fetched_at FROM messages "
    + "WHERE trade_id = ? AND from_member = ? ORDER BY id")
    .bind(tradeId, member.id).all()).results || [];

  const stmts = [];
  if (incoming.length) {
    stmts.push(env.DB.prepare(
      "UPDATE messages SET fetched_at = COALESCE(fetched_at, ?) "
      + "WHERE trade_id = ? AND to_member = ?").bind(ts, tradeId, member.id));
  }
  // Zugestellte eigene Nachrichten sind hiermit quittiert -> löschen.
  stmts.push(env.DB.prepare(
    "UPDATE messages SET acked_at = COALESCE(acked_at, ?) "
    + "WHERE trade_id = ? AND from_member = ? AND fetched_at IS NOT NULL")
    .bind(ts, tradeId, member.id));
  stmts.push(env.DB.prepare(
    "DELETE FROM messages WHERE fetched_at IS NOT NULL "
    + "AND acked_at IS NOT NULL"));
  await env.DB.batch(stmts);

  return json({ messages: incoming, sent: mine });
}

async function setTradeStatus(req, member, env, tradeId) {
  const body = await req.json().catch(() => ({}));
  const status = ["accepted", "declined", "closed", "open"]
    .includes(body.status) ? body.status : null;
  if (!status) return err(400, "Unbekannter Status");
  const t = await env.DB.prepare("SELECT * FROM trades WHERE id = ?")
    .bind(tradeId).first();
  if (!t) return err(404, "Vorgang nicht gefunden");
  if (t.from_member !== member.id && t.to_member !== member.id) {
    return err(403, "Nicht beteiligt");
  }
  await env.DB.prepare("UPDATE trades SET status = ?, updated_at = ? "
    + "WHERE id = ?").bind(status, now(), tradeId).run();
  return json({ ok: true, status });
}

/* Melden. Der Verlauf kommt entschlüsselt von der meldenden Instanz – nur
   sie kann ihn lesen und entscheidet, was sie offenlegt. */
async function createReport(req, member, env) {
  const body = await req.json().catch(() => ({}));
  const against = (body.against || "").toString();
  const reason = (body.reason || "").toString().trim().slice(0, 1000);
  if (!against || !reason) return err(400, "against und reason nötig");
  if (against === member.id) return err(400, "Sich selbst melden geht nicht");
  const disclosed = body.disclosed
    ? JSON.stringify(body.disclosed).slice(0, 20000) : null;
  await env.DB.prepare(
    "INSERT INTO reports (trade_id, reporter, against, reason, disclosed, "
    + "created_at) VALUES (?, ?, ?, ?, ?, ?)")
    .bind(body.trade_id || null, member.id, against, reason, disclosed, now())
    .run();
  return json({ ok: true }, 201);
}

/* ------------------------------------------------------- Admin (Konsole) */

async function adminReports(env) {
  const rows = (await env.DB.prepare(
    "SELECT r.*, a.display_name AS reporter_name, "
    + "b.display_name AS against_name FROM reports r "
    + "LEFT JOIN members a ON a.id = r.reporter "
    + "LEFT JOIN members b ON b.id = r.against "
    + "ORDER BY CASE r.status WHEN 'open' THEN 0 ELSE 1 END, "
    + "r.created_at DESC LIMIT 200").all()).results || [];
  return json({ reports: rows });
}

async function adminHandleReport(req, member, env, id) {
  const body = await req.json().catch(() => ({}));
  const res = await env.DB.prepare(
    "UPDATE reports SET status = 'handled', handled_at = ?, handled_by = ?, "
    + "note = ? WHERE id = ? AND status = 'open'")
    .bind(now(), member.id,
      body.note ? String(body.note).slice(0, 500) : null, id).run();
  if (!res.meta || res.meta.changes === 0) {
    return err(404, "Meldung nicht gefunden oder schon erledigt");
  }
  return json({ ok: true });
}

async function adminOverview(env) {
  const m = await env.DB.prepare(
    "SELECT COUNT(*) AS total, "
    + "SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active, "
    + "SUM(CASE WHEN is_admin = 1 THEN 1 ELSE 0 END) AS admins "
    + "FROM members").first();
  const o = await env.DB.prepare("SELECT COUNT(*) AS c FROM offers").first();
  const i = await env.DB.prepare(
    "SELECT COUNT(*) AS c FROM invites WHERE redeemed_by IS NULL "
    + "AND (expires_at IS NULL OR expires_at > ?)").bind(now()).first();
  return json({
    members: m.total || 0, active: m.active || 0, admins: m.admins || 0,
    offers: o.c || 0, open_invites: i.c || 0,
  });
}

async function adminMembers(env) {
  const rows = (await env.DB.prepare(
    "SELECT m.id, m.display_name, m.is_admin, m.status, m.created_at, "
    + "m.last_seen_at, "
    + "(SELECT COUNT(*) FROM offers o WHERE o.member_id = m.id) AS offer_count "
    + "FROM members m ORDER BY m.status, m.display_name COLLATE NOCASE").all()
  ).results || [];
  return json({ members: rows });
}

async function adminUpdateMember(req, member, env, id) {
  const body = await req.json().catch(() => ({}));
  const row = await env.DB.prepare("SELECT * FROM members WHERE id = ?")
    .bind(id).first();
  if (!row) return err(404, "Mitglied nicht gefunden");

  const sets = [];
  const args = [];
  if (typeof body.display_name === "string") {
    const name = body.display_name.trim().slice(0, 80);
    if (!name) return err(400, "display_name darf nicht leer sein");
    sets.push("display_name = ?"); args.push(name);
  }
  if (typeof body.is_admin === "boolean") {
    // Den letzten Admin nicht entrechten – sonst sperrt man sich selbst aus.
    if (!body.is_admin && row.is_admin) {
      const c = await env.DB.prepare(
        "SELECT COUNT(*) AS c FROM members WHERE is_admin = 1 "
        + "AND status = 'active'").first();
      if ((c.c || 0) <= 1) return err(400, "Das ist der letzte Admin");
    }
    sets.push("is_admin = ?"); args.push(body.is_admin ? 1 : 0);
  }
  if (typeof body.status === "string") {
    const st = body.status === "disabled" ? "disabled" : "active";
    if (st === "disabled" && row.is_admin) {
      const c = await env.DB.prepare(
        "SELECT COUNT(*) AS c FROM members WHERE is_admin = 1 "
        + "AND status = 'active'").first();
      if ((c.c || 0) <= 1) return err(400, "Das ist der letzte aktive Admin");
    }
    sets.push("status = ?"); args.push(st);
  }
  if (!sets.length) return err(400, "Nichts zu ändern");

  args.push(id);
  await env.DB.prepare(`UPDATE members SET ${sets.join(", ")} WHERE id = ?`)
    .bind(...args).run();
  return json({ ok: true });
}

async function adminDeleteMember(member, env, id) {
  const row = await env.DB.prepare("SELECT * FROM members WHERE id = ?")
    .bind(id).first();
  if (!row) return err(404, "Mitglied nicht gefunden");
  if (row.id === member.id) return err(400, "Sich selbst kann man nicht löschen");
  if (row.is_admin) {
    const c = await env.DB.prepare(
      "SELECT COUNT(*) AS c FROM members WHERE is_admin = 1").first();
    if ((c.c || 0) <= 1) return err(400, "Das ist der letzte Admin");
  }
  await env.DB.batch([
    env.DB.prepare("DELETE FROM offers WHERE member_id = ?").bind(id),
    env.DB.prepare("DELETE FROM messages WHERE from_member = ? OR to_member = ?")
      .bind(id, id),
    env.DB.prepare("DELETE FROM members WHERE id = ?").bind(id),
  ]);
  return json({ ok: true });
}

async function adminInvites(env) {
  // Der Klartext-Code ist nicht gespeichert (nur Hash) – der Hash dient als ID.
  const rows = (await env.DB.prepare(
    "SELECT i.code_hash AS id, i.note, i.expires_at, i.created_at, "
    + "i.redeemed_at, c.display_name AS created_by_name, "
    + "r.display_name AS redeemed_by_name "
    + "FROM invites i "
    + "LEFT JOIN members c ON c.id = i.created_by "
    + "LEFT JOIN members r ON r.id = i.redeemed_by "
    + "ORDER BY i.created_at DESC LIMIT 200").all()).results || [];
  return json({ invites: rows });
}

async function adminDeleteInvite(env, id) {
  const res = await env.DB.prepare("DELETE FROM invites WHERE code_hash = ?")
    .bind(id).run();
  if (!res.meta || res.meta.changes === 0) {
    return err(404, "Einladung nicht gefunden");
  }
  return json({ ok: true });
}

async function adminInviteRequests(env) {
  const rows = (await env.DB.prepare(
    "SELECT r.*, m.display_name, m.invite_quota, "
    + "(SELECT COUNT(*) FROM invites i WHERE i.created_by = r.member_id) AS used "
    + "FROM invite_requests r LEFT JOIN members m ON m.id = r.member_id "
    + "ORDER BY CASE r.status WHEN 'pending' THEN 0 ELSE 1 END, "
    + "r.created_at DESC LIMIT 200").all()).results || [];
  return json({ requests: rows });
}

async function adminDecideInviteRequest(req, member, env, id, approve) {
  const row = await env.DB.prepare(
    "SELECT * FROM invite_requests WHERE id = ?").bind(id).first();
  if (!row) return err(404, "Anfrage nicht gefunden");
  if (row.status !== "pending") return err(409, "Anfrage ist schon entschieden");

  const body = await req.json().catch(() => ({}));
  const stmts = [env.DB.prepare(
    "UPDATE invite_requests SET status = ?, decided_at = ?, decided_by = ? "
    + "WHERE id = ?")
    .bind(approve ? "approved" : "denied", now(), member.id, id)];
  if (approve) {
    // Genehmigt heißt: das Kontingent wächst um die gewünschte Zahl.
    const grant = Math.max(1, Math.min(Number(body.grant) || row.want, 50));
    stmts.push(env.DB.prepare(
      "UPDATE members SET invite_quota = COALESCE(invite_quota, ?) + ? "
      + "WHERE id = ?").bind(DEFAULT_QUOTA, grant, row.member_id));
  }
  await env.DB.batch(stmts);
  return json({ ok: true });
}

async function adminRoute(req, member, env, p, method) {
  if (!member.is_admin) return err(403, "nur für Hub-Admins");

  if (p === "/v1/admin/invite_requests" && method === "GET") {
    return await adminInviteRequests(env);
  }
  if (p === "/v1/admin/reports" && method === "GET") return await adminReports(env);
  const rm = p.match(/^\/v1\/admin\/reports\/(\d+)\/handle$/);
  if (rm && method === "POST") {
    return await adminHandleReport(req, member, env, Number(rm[1]));
  }
  let ir = p.match(/^\/v1\/admin\/invite_requests\/(\d+)\/(approve|deny)$/);
  if (ir && method === "POST") {
    return await adminDecideInviteRequest(req, member, env, Number(ir[1]),
                                          ir[2] === "approve");
  }

  if (p === "/v1/admin/overview" && method === "GET") return await adminOverview(env);
  if (p === "/v1/admin/members" && method === "GET") return await adminMembers(env);
  if (p === "/v1/admin/invites" && method === "GET") return await adminInvites(env);

  let m = p.match(/^\/v1\/admin\/members\/([^/]+)$/);
  if (m) {
    const id = decodeURIComponent(m[1]);
    if (method === "PATCH") return await adminUpdateMember(req, member, env, id);
    if (method === "DELETE") return await adminDeleteMember(member, env, id);
  }
  m = p.match(/^\/v1\/admin\/invites\/([^/]+)$/);
  if (m && method === "DELETE") {
    return await adminDeleteInvite(env, decodeURIComponent(m[1]));
  }
  return err(404, "unbekannter Admin-Endpunkt");
}

/* ------------------------------------------------------------------ Router */

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const p = url.pathname;
    const method = req.method;

    try {
      if (method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
      if (p === "/" || p === "/v1/health") return json({ ok: true, service: "brickfolio-hub" });
      if (p === "/v1/register" && method === "POST") return await register(req, env);

      // ab hier: Auth nötig
      const member = await auth(req, env);
      if (!member) return err(401, "Token fehlt oder ungültig");

      if (p.startsWith("/v1/admin/")) return await adminRoute(req, member, env, p, method);

      if (p === "/v1/me" && method === "GET") return await me(member);
      if (p === "/v1/me" && method === "PATCH") return await updateMe(req, member, env);
      if (p === "/v1/token/rotate" && method === "POST") return await rotateToken(member, env);
      if (p === "/v1/offers" && method === "PUT") return await putOffers(req, member, env);
      if (p === "/v1/offers" && method === "GET") return await listOffers(req, member, env);
      if (p === "/v1/members" && method === "GET") return await listMembers(member, env);
      if (p === "/v1/key" && method === "PUT") return await putKey(req, member, env);
      if (p === "/v1/trades" && method === "POST") return await createTrade(req, member, env);
      if (p === "/v1/trades" && method === "GET") return await listTrades(member, env);
      if (p === "/v1/reports" && method === "POST") return await createReport(req, member, env);
      let km = p.match(/^\/v1\/key\/([^/]+)$/);
      if (km && method === "GET") return await getKey(env, decodeURIComponent(km[1]));
      let tm = p.match(/^\/v1\/trades\/([^/]+)\/messages$/);
      if (tm && method === "POST") return await sendMessage(req, member, env, tm[1]);
      if (tm && method === "GET") return await fetchMessages(member, env, tm[1]);
      tm = p.match(/^\/v1\/trades\/([^/]+)\/status$/);
      if (tm && method === "POST") return await setTradeStatus(req, member, env, tm[1]);
      if (p === "/v1/invites" && method === "POST") return await createInvite(req, member, env);
      if (p === "/v1/invites/quota" && method === "GET") return await getQuota(member, env);
      if (p === "/v1/invite_requests" && method === "POST") return await requestMoreInvites(req, member, env);

      return err(404, "unbekannter Endpunkt");
    } catch (e) {
      return err(500, "interner Fehler: " + (e && e.message ? e.message : e));
    }
  },
};
