/* Brickfolio-Hub – Verwaltung.
   Eigenständige Seite: spricht den Hub direkt per Admin-Token an. Der Token
   liegt (auf Wunsch) im localStorage dieses Browsers und geht nur an den Hub. */

const DEFAULT_HUB = "https://brickfolio-hub.bfhub.workers.dev";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtDate = (ts) => ts ? new Date(ts * 1000).toLocaleString("de-DE") : "–";

/* Für „zuletzt gesehen" zählt der Abstand, nicht der Zeitstempel. Der genaue
   Wert bleibt als Tooltip erhalten. */
function rel(ts) {
  if (!ts) return "nie";
  const s = Math.floor(Date.now() / 1000) - ts;
  if (s < 90) return "gerade eben";
  const m = Math.round(s / 60);
  if (m < 60) return `vor ${m} Min.`;
  const h = Math.round(m / 60);
  if (h < 24) return `vor ${h} Std.`;
  const d = Math.round(h / 24);
  if (d < 31) return `vor ${d} ${d === 1 ? "Tag" : "Tagen"}`;
  const mo = Math.round(d / 30);
  return mo < 12 ? `vor ${mo} Mon.` : `vor ${Math.round(mo / 12)} J.`;
}
const seit = (ts) => `<span title="${esc(fmtDate(ts))}">${rel(ts)}</span>`;

let session = { url: "", token: "", me: null };
let toastTimer;

function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 3200);
}

async function api(path, { method = "GET", body } = {}) {
  const resp = await fetch(session.url.replace(/\/$/, "") + path, {
    method,
    headers: {
      authorization: "Bearer " + session.token,
      ...(body ? { "content-type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = {};
  try { data = await resp.json(); } catch (_) { /* leere Antwort */ }
  if (!resp.ok) throw new Error(data.error || `Fehler ${resp.status}`);
  return data;
}

/* ------------------------------------------------------------- Anmeldung */

async function login(url, token, remember) {
  session = { url, token, me: null };
  const me = await api("/v1/me");                 // prüft den Token
  if (!me.is_admin) throw new Error("Dieser Token gehört keinem Hub-Admin.");
  session.me = me;
  // Stand des Hubs daneben – sonst sieht man nach einem Deploy nicht, ob
  // der neue Code oben ist. Ältere Hubs melden ihn nicht; dann bleibt es
  // bei der Konsolen-Version allein.
  if (me.hub_version) {
    const el = $("ver");
    el.textContent = (el.textContent ? el.textContent + " · " : "")
      + "Hub v" + me.hub_version;
  }
  if (remember) {
    localStorage.setItem("bfa_url", url);
    localStorage.setItem("bfa_token", token);
  } else {
    localStorage.removeItem("bfa_url");
    localStorage.removeItem("bfa_token");
  }
  showApp();
}

function showApp() {
  $("login").hidden = true;
  $("app").hidden = false;
  $("tabs").hidden = false;
  $("foot").hidden = false;
  $("who").hidden = false;
  $("who").textContent = `${session.me.display_name} · ${session.url.replace(/^https?:\/\//, "")}`;
  $("btn-logout").hidden = false;
  $("btn-refresh").hidden = false;
  zeigeTab(localStorage.getItem("bfa_tab") || "overview");
  loadAll();
}

function logout() {
  localStorage.removeItem("bfa_token");
  localStorage.removeItem("bfa_url");
  session = { url: "", token: "", me: null };
  location.reload();
}

/* ----------------------------------------------------------------- Tabs */

function zeigeTab(name) {
  const tabs = [...document.querySelectorAll(".tab")];
  if (!tabs.some((t) => t.dataset.tab === name)) name = "overview";
  tabs.forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".panel").forEach((p) => {
    p.hidden = p.id !== "panel-" + name;
  });
  localStorage.setItem("bfa_tab", name);
}

/* Zahl am Reiter. `alarm` färbt sie rot – das gilt für alles, was auf eine
   Entscheidung wartet. Ohne Zahl bleibt die Blase weg. */
function badge(id, n, alarm = false) {
  const el = $(id);
  el.hidden = !n;
  el.textContent = n;
  el.classList.toggle("alert", !!alarm);
}

/* ----------------------------------------------------------------- Daten */

const daten = { instances: [], members: [], reports: [], requests: [] };

async function loadAll() {
  const b = $("btn-refresh");
  b.classList.add("busy");
  try {
    await Promise.all([loadOverview(), loadMembers(), loadReports(),
                       loadOffers(), loadRequests(), loadInvites(),
                       loadInstances(), loadCrashes()]);
  } finally {
    b.classList.remove("busy");
  }
  renderStand();
}

/* Instanzen: die Installationen selbst, mit ihrer Namensgeschichte. Wer
   gesperrt wurde und unter neuem Namen zurückkommt, taucht hier unter
   derselben Kennung wieder auf. */
async function loadInstances() {
  const box = $("instances");
  box.innerHTML = `<p class="empty">Lade …</p>`;
  try {
    const { instances } = await api("/v1/admin/instances");
    daten.instances = instances;
    badge("b-instances", instances.length);
    renderInstances();
  } catch (e) {
    box.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

function renderInstances() {
  const box = $("instances");
  const q = ($("inst-search").value || "").toUpperCase().replace(/[^0-9A-Z]/g, "");
  const list = q ? daten.instances.filter((i) =>
    i.code.replace(/-/g, "").includes(q)
    || (i.first_name || "").toUpperCase().includes(q)) : daten.instances;
  if (!list.length) {
    box.innerHTML = `<p class="empty">${daten.instances.length
      ? "Keine Instanz passt zur Suche." : "Noch keine Instanzen."}</p>`;
    return;
  }
  box.innerHTML = list.map((i) => `
    <div class="row-item" data-code="${esc(i.code)}">
      <div class="row-main">
        <div class="name">${esc(i.code)}
          ${i.blocked ? '<span class="tag off">gesperrt</span>' : ""}
        </div>
        <div class="sub">Erstanmeldung als „${esc(i.first_name)}"
          am ${fmtDate(i.created_at)} · zuletzt gesehen ${seit(i.last_seen_at)}</div>
        <div class="sub">Konten: ${i.members.length
          ? i.members.map((m) => `${esc(m.display_name)}${
              m.status === "active" ? "" : " (deaktiviert)"}`).join(" → ")
          : "keins mehr"}</div>
        ${i.note ? `<div class="sub">📝 ${esc(i.note)}</div>` : ""}
      </div>
      <div class="row-actions">
        <button class="btn small" data-inst="block">${
          i.blocked ? "Freischalten" : "Neubeitritt sperren"}</button>
        <button class="btn small" data-inst="note">Notiz</button>
      </div>
    </div>`).join("");
  box.querySelectorAll("[data-inst]").forEach((b) => {
    b.addEventListener("click", () => instanceAction(b));
  });
}

async function instanceAction(btn) {
  const code = btn.closest(".row-item").dataset.code;
  const i = daten.instances.find((x) => x.code === code);
  try {
    if (btn.dataset.inst === "block") {
      await api(`/v1/admin/instances/${encodeURIComponent(code)}`,
        { method: "PATCH", body: { blocked: !i.blocked } });
      toast(i.blocked ? "Instanz freigeschaltet ✔" : "Neubeitritt gesperrt ✔");
    } else {
      const note = prompt("Notiz zu dieser Instanz:", i.note || "");
      if (note == null) return;
      await api(`/v1/admin/instances/${encodeURIComponent(code)}`,
        { method: "PATCH", body: { note: note.trim() } });
      toast("Notiz gespeichert ✔");
    }
    loadInstances();
    loadMembers();
  } catch (e) { toast(e.message); }
}

/* Angebote im Netzwerk – nach Mitglied gruppiert, einzeln oder komplett
   löschbar. Wichtig für Altbestände, die niemand mehr anbietet. */
/* Absturz-Einschätzungen. Der Rohverlauf (bis 200 KB Messwerte) wird vom
   Sammler auf dem Mac mini abgeholt und im Hub gelöscht – hier steht nur,
   was dabei herauskam. Priorität 1 ist die höchste; ab 2 wird die Zahl am
   Reiter rot, weil das etwas ist, das jemand ansehen sollte. */

async function loadCrashes() {
  const box = $("crashes");
  box.innerHTML = `<p class="empty">Lade …</p>`;
  try {
    const { findings } = await api("/v1/admin/crash_findings");
    const offen = findings.filter((f) => !f.erledigt);
    badge("b-crashes", offen.length, offen.some((f) => f.prio <= 2));
    if (!findings.length) {
      box.innerHTML = `<p class="empty">Nichts gemeldet. Gut so.</p>`;
      return;
    }
    box.innerHTML = findings.map((f) => `
      <div class="row-item" data-fid="${esc(f.id)}">
        <div class="row-main">
          <div class="name">
            <span class="tag${f.prio <= 2 ? " off" : ""}">Prio ${f.prio}</span>
            ${esc(f.label)}
            ${f.erledigt ? '<span class="tag">erledigt</span>' : ""}
          </div>
          <div class="sub">v${esc(f.app_version || "?")} ·
            ${f.crashes}× Absturz · Ansicht ${esc(f.views || "–")} ·
            ${fmtDate(f.created_at)}</div>
          <div class="sub"><b>${esc(f.kurz)}</b></div>
          ${f.analyse ? `<details><summary class="sub">Ausführlich</summary>
            <div class="note">${esc(f.analyse).replace(/\n/g, "<br>")}</div>
          </details>` : ""}
        </div>
        <div class="row-actions">
          <button class="btn small" data-crash="done">${
            f.erledigt ? "Wieder offen" : "Erledigt"}</button>
          <button class="btn small danger" data-crash="del">Löschen</button>
        </div>
      </div>`).join("");
    box.querySelectorAll("[data-crash]").forEach((b) => {
      b.addEventListener("click", () => crashAction(b, findings));
    });
  } catch (e) {
    box.innerHTML = `<p class="empty">Nicht ladbar: ${esc(e.message)}</p>`;
  }
}

async function crashAction(btn, findings) {
  const id = btn.closest(".row-item").dataset.fid;
  const f = findings.find((x) => x.id === id);
  try {
    if (btn.dataset.crash === "del") {
      if (!confirm("Diese Einschätzung löschen?")) return;
      await api(`/v1/admin/crash_findings/${encodeURIComponent(id)}`,
                { method: "DELETE" });
    } else {
      await api(`/v1/admin/crash_findings/${encodeURIComponent(id)}`,
                { method: "PATCH", body: { erledigt: f && !f.erledigt } });
    }
    loadCrashes();
  } catch (e) {
    toast(e.message);
  }
}

async function loadOffers() {
  const box = $("offers");
  box.innerHTML = `<p class="empty">Lade …</p>`;
  try {
    const { offers } = await api("/v1/admin/offers");
    badge("b-offers", offers.length);
    if (!offers.length) { box.innerHTML = `<p class="empty">Keine Angebote.</p>`; return; }
    const byMember = new Map();
    offers.forEach((o) => {
      const k = o.member_id;
      if (!byMember.has(k)) {
        byMember.set(k, { name: o.display_name, status: o.member_status, items: [] });
      }
      byMember.get(k).items.push(o);
    });
    box.innerHTML = [...byMember.entries()].map(([mid, g]) => `
      <div class="row-item" data-owner="${esc(mid)}">
        <div class="row-main">
          <div class="name">${esc(g.name || "(gelöschtes Mitglied)")}
            ${!g.name ? '<span class="tag off">verwaist</span>' : ""}
            ${g.status && g.status !== "active" ? '<span class="tag off">deaktiviert</span>' : ""}
          </div>
          <div class="sub">${g.items.length} Angebote:
            ${g.items.slice(0, 6).map((i) => esc(i.name)).join(", ")}${g.items.length > 6 ? " …" : ""}</div>
        </div>
        <div class="row-actions">
          <button class="btn small danger" data-del-offers>Alle löschen</button>
        </div>
      </div>`).join("");

    box.querySelectorAll("[data-del-offers]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const mid = btn.closest(".row-item").dataset.owner;
        if (!confirm("Wirklich alle Angebote dieses Mitglieds löschen?\n\n"
          + "Es kann sie jederzeit neu veröffentlichen.")) return;
        try {
          const r = await api(`/v1/admin/offers/${encodeURIComponent(mid)}`,
            { method: "DELETE" });
          toast(`${r.deleted} Angebote gelöscht ✔`);
          loadOffers(); loadOverview();
        } catch (e) { toast(e.message); }
      });
    });
  } catch (e) {
    box.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

/* Meldungen. Der Verlauf steht nur dort, wo ihn jemand freiwillig
   offengelegt hat – der Hub kann Nachrichten nicht selbst lesen. */
async function loadReports() {
  const box = $("reports");
  try {
    const { reports } = await api("/v1/admin/reports");
    daten.reports = reports;
    if (!reports.length) {
      box.innerHTML = `<p class="empty done">Keine Meldungen. ✔</p>`;
      return;
    }
    // Offenes zuerst, sonst das Neueste oben.
    const sortiert = [...reports].sort((a, b) =>
      (a.status === "open" ? 0 : 1) - (b.status === "open" ? 0 : 1)
      || (b.created_at || 0) - (a.created_at || 0));
    box.innerHTML = sortiert.map((r) => {
      let history = "";
      if (r.disclosed) {
        try {
          history = JSON.parse(r.disclosed).map((m) =>
            `<div class="sub"><b>${esc(m.von)}:</b> ${esc(m.text)}</div>`).join("");
        } catch (_) { history = ""; }
      }
      return `
      <div class="row-item${r.status === "open" ? "" : " dim"}" data-rep="${r.id}">
        <div class="row-main">
          <div class="name">${esc(r.reporter_name || "?")} meldet
            ${esc(r.against_name || "?")}
            ${r.status === "open" ? '<span class="tag open">offen</span>'
                                  : '<span class="tag used">erledigt</span>'}</div>
          <div class="sub">${esc(r.reason)} · ${fmtDate(r.created_at)}</div>
          ${history ? `<details><summary class="sub">Offengelegter Verlauf</summary>${history}</details>`
                    : `<div class="sub">(kein Verlauf mitgeschickt)</div>`}
          ${r.note ? `<div class="sub">Notiz: ${esc(r.note)}</div>` : ""}
        </div>
        ${r.status === "open" ? `<div class="row-actions">
          <button class="btn small" data-handle>Als erledigt markieren</button>
        </div>` : ""}
      </div>`;
    }).join("");

    box.querySelectorAll("[data-handle]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.closest(".row-item").dataset.rep;
        const note = prompt("Notiz (optional):", "") || "";
        try {
          await api(`/v1/admin/reports/${id}/handle`, { method: "POST",
            body: { note } });
          toast("Als erledigt markiert ✔");
          await loadReports();
          renderStand();
        } catch (e) { toast(e.message); }
      });
    });
  } catch (e) {
    box.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

/* Anfragen nach mehr Einladungen (offene zuerst). */
async function loadRequests() {
  const box = $("requests");
  try {
    const { requests } = await api("/v1/admin/invite_requests");
    daten.requests = requests;
    if (!requests.length) {
      box.innerHTML = `<p class="empty done">Keine Anfragen. ✔</p>`;
      return;
    }
    box.innerHTML = requests.map((r) => {
      const open = r.status === "pending";
      const tag = open ? `<span class="tag open">offen</span>`
        : r.status === "approved" ? `<span class="tag used">genehmigt</span>`
        : `<span class="tag off">abgelehnt</span>`;
      return `
      <div class="row-item" data-req="${r.id}">
        <div class="row-main">
          <div class="name">${esc(r.display_name || "?")} möchte
            ${r.want} weitere ${tag}</div>
          <div class="sub">bisher ${r.used} von ${r.invite_quota} vergeben ·
            gestellt ${fmtDate(r.created_at)}${
              r.reason ? ` · „${esc(r.reason)}"` : ""}${
              r.decided_at ? ` · entschieden ${fmtDate(r.decided_at)}` : ""}</div>
        </div>
        ${open ? `<div class="row-actions">
          <button class="btn small" data-approve>Genehmigen</button>
          <button class="btn small danger" data-deny>Ablehnen</button>
        </div>` : ""}
      </div>`;
    }).join("");

    box.querySelectorAll("[data-approve], [data-deny]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.closest(".row-item").dataset.req;
        const ok = btn.hasAttribute("data-approve");
        try {
          await api(`/v1/admin/invite_requests/${id}/${ok ? "approve" : "deny"}`,
            { method: "POST", body: {} });
          toast(ok ? "Genehmigt – Kontingent erhöht ✔" : "Abgelehnt");
          await loadRequests();
          renderStand();
          loadMembers();
        } catch (e) { toast(e.message); }
      });
    });
  } catch (e) {
    box.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

async function loadOverview() {
  try {
    const s = await api("/v1/admin/overview");
    $("stats").innerHTML = [
      ["Mitglieder", s.members, "members"], ["aktiv", s.active, "members"],
      ["Admins", s.admins, "members"], ["Angebote", s.offers, "offers"],
      ["offene Einladungen", s.open_invites, "invites"],
    ].map(([label, val, tab]) =>
      `<button class="stat" data-goto="${tab}"><b>${val}</b><span>${label}</span></button>`)
      .join("");
    $("stats").querySelectorAll("[data-goto]").forEach((b) => {
      b.addEventListener("click", () => zeigeTab(b.dataset.goto));
    });
  } catch (e) { toast(e.message); }
}

/* Übersicht: was wartet, in einem Satz je Punkt. Ist nichts offen, steht
   das auch da – sonst rätselt man, ob die Karte nur nicht geladen hat. */
function renderStand() {
  const box = $("todo-summary");
  const offeneMeldungen = daten.reports.filter((r) => r.status === "open").length;
  const offeneAnfragen = daten.requests.filter((r) => r.status === "pending").length;
  badge("b-todo", offeneMeldungen + offeneAnfragen, true);

  const zeilen = [];
  if (offeneMeldungen) {
    zeilen.push(["⚑", `<b>${offeneMeldungen}</b> offene ${offeneMeldungen === 1
      ? "Meldung" : "Meldungen"}`, "todo"]);
  }
  if (offeneAnfragen) {
    zeilen.push(["🙋", `<b>${offeneAnfragen}</b> offene ${offeneAnfragen === 1
      ? "Anfrage" : "Anfragen"} nach mehr Einladungen`, "todo"]);
  }
  const gesperrt = daten.instances.filter((i) => i.blocked).length;
  if (gesperrt) {
    zeilen.push(["🚫", `<b>${gesperrt}</b> gesperrte ${gesperrt === 1
      ? "Instanz" : "Instanzen"}`, "instances"]);
  }
  const stumm = daten.members.filter((m) => m.status !== "active").length;
  if (stumm) {
    zeilen.push(["💤", `<b>${stumm}</b> deaktivierte ${stumm === 1
      ? "Mitgliedschaft" : "Mitgliedschaften"}`, "members"]);
  }
  if (!zeilen.length) {
    box.innerHTML = `<p class="empty done">Nichts zu tun – alles erledigt. ✔</p>`;
    return;
  }
  box.innerHTML = zeilen.map(([icon, text, tab]) => `
    <div class="todo-line">
      <span aria-hidden="true">${icon}</span>
      <span class="txt">${text}</span>
      <button class="btn small" data-goto="${tab}">Ansehen</button>
    </div>`).join("");
  box.querySelectorAll("[data-goto]").forEach((b) => {
    b.addEventListener("click", () => {
      zeigeTab(b.dataset.goto);
      window.scrollTo({ top: 0 });
    });
  });
}

async function loadMembers() {
  const box = $("members");
  box.innerHTML = `<p class="empty">Lade …</p>`;
  try {
    const { members } = await api("/v1/admin/members");
    daten.members = members;
    badge("b-members", members.length);
    renderMembers();
  } catch (e) {
    box.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

function renderMembers() {
  const box = $("members");
  const q = ($("mem-search").value || "").trim().toLowerCase();
  const list = q ? daten.members.filter((m) =>
    (m.display_name || "").toLowerCase().includes(q)
    || (m.instance_code || "").toLowerCase().includes(q)) : daten.members;
  if (!list.length) {
    box.innerHTML = `<p class="empty">${daten.members.length
      ? "Kein Mitglied passt zur Suche." : "Keine Mitglieder."}</p>`;
    return;
  }
  box.innerHTML = list.map((m) => `
    <div class="row-item" data-id="${esc(m.id)}">
      <div class="row-main">
        <div class="name">${esc(m.display_name)}
          ${m.is_admin ? '<span class="tag admin">Admin</span>' : ""}
          ${m.status !== "active" ? '<span class="tag off">deaktiviert</span>' : ""}
        </div>
        <div class="sub">${m.offer_count} Angebote · dabei seit ${fmtDate(m.created_at)}
          · zuletzt aktiv ${seit(m.last_seen_at)}</div>
        ${m.instance_code ? `<div class="sub">🏠 ${esc(m.instance_code)}${
          m.instance_first_name && m.instance_first_name !== m.display_name
            ? ` · erstmals als „${esc(m.instance_first_name)}"` : ""}${
          m.instance_blocked ? " · Instanz gesperrt" : ""}</div>` : ""}
      </div>
      <div class="row-actions">
        <button class="btn small" data-act="rename">Umbenennen</button>
        <button class="btn small" data-act="admin">${m.is_admin ? "Admin entziehen" : "Zum Admin"}</button>
        <button class="btn small" data-act="status">${m.status === "active" ? "Deaktivieren" : "Aktivieren"}</button>
        <button class="btn small danger" data-act="delete">Löschen</button>
      </div>
    </div>`).join("");

  box.querySelectorAll("[data-act]").forEach((btn) => {
    btn.addEventListener("click", () => memberAction(btn, daten.members));
  });
}

async function memberAction(btn, members) {
  const row = btn.closest(".row-item");
  const id = row.dataset.id;
  const m = members.find((x) => x.id === id);
  const act = btn.dataset.act;
  try {
    if (act === "rename") {
      const name = prompt("Neuer Anzeigename:", m.display_name);
      if (name == null || !name.trim()) return;
      await api(`/v1/admin/members/${encodeURIComponent(id)}`,
        { method: "PATCH", body: { display_name: name.trim() } });
      toast("Umbenannt ✔");
    } else if (act === "admin") {
      await api(`/v1/admin/members/${encodeURIComponent(id)}`,
        { method: "PATCH", body: { is_admin: !m.is_admin } });
      toast(m.is_admin ? "Admin-Rechte entzogen ✔" : "Zum Admin gemacht ✔");
    } else if (act === "status") {
      const next = m.status === "active" ? "disabled" : "active";
      await api(`/v1/admin/members/${encodeURIComponent(id)}`,
        { method: "PATCH", body: { status: next } });
      toast(next === "active" ? "Aktiviert ✔" : "Deaktiviert ✔");
    } else if (act === "delete") {
      if (!confirm(`"${m.display_name}" wirklich löschen?\n\n`
        + `Die ${m.offer_count} Angebote dieses Mitglieds werden mitgelöscht. `
        + `Der Token wird dadurch ungültig.`)) return;
      await api(`/v1/admin/members/${encodeURIComponent(id)}`, { method: "DELETE" });
      toast("Gelöscht ✔");
    }
    await loadMembers();
    renderStand();
    loadOverview();
  } catch (e) { toast(e.message); }
}

async function loadInvites() {
  const box = $("invites");
  box.innerHTML = `<p class="empty">Lade …</p>`;
  try {
    const { invites } = await api("/v1/admin/invites");
    const now = Math.floor(Date.now() / 1000);
    badge("b-invites", invites.filter((i) =>
      !i.redeemed_at && !(i.expires_at && i.expires_at < now)).length);
    if (!invites.length) { box.innerHTML = `<p class="empty">Keine Einladungen.</p>`; return; }
    box.innerHTML = invites.map((i) => {
      const expired = i.expires_at && i.expires_at < now;
      const state = i.redeemed_at
        ? `<span class="tag used">eingelöst</span>`
        : expired ? `<span class="tag off">abgelaufen</span>` : `<span class="tag open">offen</span>`;
      return `
      <div class="row-item${i.redeemed_at || expired ? " dim" : ""}" data-id="${esc(i.id)}">
        <div class="row-main">
          <div class="name">${esc(i.note || "(ohne Notiz)")} ${state}</div>
          <div class="sub">erstellt ${fmtDate(i.created_at)} von ${esc(i.created_by_name || "?")}
            ${i.redeemed_at ? ` · eingelöst von ${esc(i.redeemed_by_name || "?")} am ${fmtDate(i.redeemed_at)}` : ""}
            ${i.expires_at ? ` · gültig bis ${fmtDate(i.expires_at)}` : " · unbegrenzt"}</div>
        </div>
        <div class="row-actions">
          <button class="btn small danger" data-inv-del>Zurückziehen</button>
        </div>
      </div>`;
    }).join("");

    box.querySelectorAll("[data-inv-del]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.closest(".row-item").dataset.id;
        if (!confirm("Diese Einladung zurückziehen?")) return;
        try {
          await api(`/v1/admin/invites/${encodeURIComponent(id)}`, { method: "DELETE" });
          toast("Zurückgezogen ✔");
          loadInvites();
          loadOverview();
        } catch (e) { toast(e.message); }
      });
    });
  } catch (e) {
    box.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

/* --------------------------------------------------------------- Aufbau */

document.addEventListener("DOMContentLoaded", () => {
  $("in-url").value = localStorage.getItem("bfa_url") || DEFAULT_HUB;

  // Version dieser Konsole (Datei VERSION im Image). Ausdrücklich
  // beschriftet: Sie stand bisher unbeschriftet neben „Hub-Admin" und
  // wurde prompt für die Version des Hubs gehalten – der hatte gar keine.
  fetch("VERSION", { cache: "no-store" })
    .then((r) => (r.ok ? r.text() : ""))
    .then((v) => { if (v.trim()) $("ver").textContent = "Konsole v" + v.trim(); })
    .catch(() => {});

  $("btn-login").addEventListener("click", async () => {
    const errEl = $("login-error");
    errEl.hidden = true;
    const url = $("in-url").value.trim();
    const token = $("in-token").value.trim();
    if (!url || !token) {
      errEl.textContent = "Adresse und Token angeben."; errEl.hidden = false; return;
    }
    $("btn-login").disabled = true;
    try {
      await login(url, token, $("in-remember").checked);
    } catch (e) {
      errEl.textContent = e.message; errEl.hidden = false;
    } finally { $("btn-login").disabled = false; }
  });

  $("in-token").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") $("btn-login").click();
  });

  document.querySelectorAll(".tab").forEach((t) => {
    t.addEventListener("click", () => zeigeTab(t.dataset.tab));
  });

  $("btn-logout").addEventListener("click", logout);
  $("btn-refresh").addEventListener("click", loadAll);
  $("inst-search").addEventListener("input", renderInstances);
  $("mem-search").addEventListener("input", renderMembers);
  $("btn-del-orphans").addEventListener("click", async () => {
    if (!confirm("Angebote löschen, deren Mitglied es nicht mehr gibt?")) return;
    try {
      const r = await api("/v1/admin/offers/orphans", { method: "DELETE" });
      toast(r.deleted ? `${r.deleted} verwaiste Angebote gelöscht ✔`
                      : "Keine verwaisten Angebote gefunden");
      loadOffers(); loadOverview();
    } catch (e) { toast(e.message); }
  });

  $("btn-new-invite").addEventListener("click", async (ev) => {
    const b = ev.currentTarget;
    b.disabled = true;
    try {
      const note = $("inv-note").value.trim();
      const days = Number($("inv-days").value) || 0;
      const res = await api("/v1/invites", { method: "POST",
        body: { note, ...(days > 0 ? { expires_in_days: days } : {}) } });
      $("invite-out").hidden = false;
      $("invite-code").textContent = res.invite_code;
      $("inv-note").value = "";
      $("inv-days").value = "";
      toast("Einladung erstellt – Code kopieren und weitergeben");
      loadInvites();
      loadOverview();
    } catch (e) { toast(e.message); } finally { b.disabled = false; }
  });

  $("btn-copy-invite").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText($("invite-code").textContent);
      toast("Code kopiert ✔");
    } catch (_) { toast("Kopieren nicht möglich – bitte markieren."); }
  });

  // Gespeicherte Sitzung fortsetzen
  const savedToken = localStorage.getItem("bfa_token");
  const savedUrl = localStorage.getItem("bfa_url");
  if (savedToken && savedUrl) {
    login(savedUrl, savedToken, true).catch(() => {
      localStorage.removeItem("bfa_token");    // abgelaufen/ungültig
    });
  }
});
