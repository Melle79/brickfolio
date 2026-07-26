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

async function register(req, env) {
  const body = await req.json().catch(() => ({}));
  const name = (body.display_name || "").toString().trim().slice(0, 80);
  if (!name) return err(400, "display_name fehlt");

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

async function createInvite(req, member, env) {
  // Einladen darf jedes aktive Mitglied – so kann das Netzwerk wachsen.
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

/* ------------------------------------------------------- Admin (Konsole) */

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

async function adminRoute(req, member, env, p, method) {
  if (!member.is_admin) return err(403, "nur für Hub-Admins");

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
      if (p === "/v1/invites" && method === "POST") return await createInvite(req, member, env);

      return err(404, "unbekannter Endpunkt");
    } catch (e) {
      return err(500, "interner Fehler: " + (e && e.message ? e.message : e));
    }
  },
};
