/* Tausch-Netzwerk (Community) – der Teil der Oberfläche.

   Verbindung per Einladung (Karte unter Mehr), der Tausch-Tab mit Angeboten
   und Mitgliedern, Vorgänge mit Ende-zu-Ende-verschlüsselten Nachrichten,
   Melden. Der Gegenpart auf dem Server ist `backend/community.py`.

   **Warum eine eigene Datei.** Bis 2.88.51 stand das mitten in `app.js`.
   Das Netzwerk soll zu einer Community wachsen (Profile, Entdecken); dafür
   braucht es einen eigenen Platz. Verhalten hat sich beim Umzug nicht
   geändert.

   **Geladen vor `app.js`**, als gewöhnliches Skript: Beide teilen sich die
   globalen Namen (`state`, `api`, `tr`, `$` …). Hier steht auf oberster
   Ebene nichts, das beim Laden schon etwas aus `app.js` bräuchte – nur
   Funktionen und Variablen mit festem Anfangswert. Ein Test hält das fest.

   **Bleibt optional.** Ohne Einladung ist nichts davon sichtbar: Der Tab
   erscheint erst, wenn die Instanz beigetreten ist (`updateHubTab`). */

/* ---------------------------------------- Tausch-Hub: Verbindung (Einstellungen)
   Adresse ist fest hinterlegt; hier nur Token (Admin) bzw. Einladungscode. */
let hubWired = false;

async function loadHubCard() {
  wireHubConnectOnce();
  try {
    renderHubStatus(await api("/hub?refresh=1"));
  } catch (_) { /* Karte bleibt leer, wenn der Status nicht kommt */ }
}

function renderHubStatus(s) {
  const on = s && s.connected;
  $("hub-connect-box").hidden = on;
  $("hub-connected-box").hidden = !on;
  if (s && s.url) $("hub-url-line").textContent = s.url;
  if (!on) return;
  $("hub-member-name").textContent = s.display_name || "(unbenannt)";
  $("hub-admin-badge").hidden = !s.is_admin;
}

function wireHubConnectOnce() {
  if (hubWired) return;
  hubWired = true;
  const err = $("hub-connect-error");

  const afterConnect = (s, msg) => {
    renderHubStatus(s);
    state.hubConnected = true;
    updateHubTab();
    toast(msg);
  };

  $("hub-connect-invite").addEventListener("click", async () => {
    err.hidden = true;
    const invite_code = $("hub-invite-in").value.trim();
    const display_name = $("hub-name-in").value.trim();
    if (!invite_code || !display_name) {
      err.textContent = tr("Einladungscode und Anzeigename angeben.");
      err.hidden = false; return;
    }
    try {
      afterConnect(await api("/hub/connect", { method: "POST",
        body: { invite_code, display_name } }), "Dem Netzwerk beigetreten 🤝");
    } catch (e) { err.textContent = e.message; err.hidden = false; }
  });

  $("hub-disconnect").addEventListener("click", async () => {
    if (!confirm(tr("Verbindung zum Hub trennen? Deine Angebote bleiben "
      + "dort, bis du sie ersetzt."))) return;
    try {
      await api("/hub/disconnect", { method: "POST" });
      renderHubStatus({ connected: false });
      state.hubConnected = false;
      updateHubTab();
    } catch (e) { toast(e.message); }
  });
}

/* ------------------------------------------------ Tausch-Hub: Nutzung (Tab) */
let hubViewWired = false;

async function loadHubView() {
  wireHubViewOnce();
  showHubTab(hubTab);
  // Veröffentlichen nur für Admins (steuert, was die Instanz preisgibt)
  $("hub-publish").hidden = !(state.user && state.user.is_admin);
  syncTrades().then(() => api("/hub/trades")
    .then((d) => markUnread((d.trades || [])
      .reduce((s, t) => s + (t.unread || 0), 0)))
    .catch(() => {}));
  try {
    const s = await api("/hub?refresh=1");
    $("hub-view-who").textContent = s.display_name
      ? tr("Angemeldet als {name}", { name: s.display_name }) : "";
    $("hub-blocked").hidden = !s.blocked;
    const lp = s.last_publish;
    const lpEl = $("hub-last-publish");
    lpEl.hidden = !lp;
    if (lp) {
      lpEl.textContent = tr("Zuletzt veröffentlicht: {n} Angebote am {wann}",
        { n: lp.count, wann: new Date(lp.ts * 1000).toLocaleString(dateLocale()) });
    }
  } catch (_) { /* egal */ }
  loadInviteQuota();
  // Die Liste lädt showHubTab() weiter oben – hier nicht doppelt anstoßen.
}

/* ------------------------------------------- Vorgänge, Chat, Melden (E2E) */
let hubTab = "offers";
let openTradeId = null;

function showHubTab(name) {
  hubTab = name;
  ["offers", "trades", "share"].forEach((t) => {
    $("hubpane-" + t).hidden = t !== name;
  });
  document.querySelectorAll("[data-hubtab]").forEach((b) =>
    b.classList.toggle("sel", b.dataset.hubtab === name));
  // Angebote beim Zurückwechseln neu laden – sonst stünde dort noch der
  // Stand von vorhin, ohne die inzwischen gestarteten Gespräche.
  if (name === "offers") loadHubOffers();
  if (name === "trades") loadTrades();
  if (name === "share") loadShareView();
  updatePolling();
}

/* Die Sicherheitsnummer – zwei kurze Zahlenreihen zum Vergleichen.

   Sie ist nicht der Schlüssel, sondern sein Fingerabdruck. Wer sie einmal am
   Telefon abgleicht, weiß: Es wird wirklich für das Gegenüber verschlüsselt
   und nicht für jemanden, der sich dazwischengeschoben hat. Die Instanz merkt
   sich einen Schlüssel ohnehin beim ersten Mal und bricht ab, wenn er sich
   ändert – das hier ist die Möglichkeit, es selbst nachzusehen. */
async function zeigeSicherheitsnummer(memberId) {
  const box = $("trade-fp-box");
  if (!box) return;
  box.hidden = true;
  if (!memberId) return;
  try {
    const d = await api(`/hub/key/${encodeURIComponent(memberId)}`);
    if (!d.known) return;
    $("trade-fp-mine").textContent = d.mine;
    $("trade-fp-theirs").textContent = d.theirs;
    box.hidden = false;
  } catch (_) { /* ohne Nummer bleibt der Abschnitt einfach zu */ }
}

/* Ungelesene Nachrichten anzeigen – am Unter-Tab und oben in der Kopfzeile.

   Den Unter-Tab sieht nur, wer schon im Tausch-Bereich ist. Damit blieb eine
   neue Nachricht unbemerkt, solange man woanders war oder die App gerade erst
   geöffnet hat. Das Zeichen in der Kopfzeile ist von überall zu sehen – und
   verschwindet wieder, sobald nichts mehr offen ist. */
function markUnread(n) {
  const b = $("hub-unread");
  if (b) {
    b.hidden = !n;
    b.textContent = n;
  }
  const oben = $("topbar-unread");
  if (oben) {
    oben.hidden = !n;
    oben.querySelector("[data-unread-count]").textContent = n > 99 ? "99+" : n;
    oben.title = n === 1 ? tr("1 ungelesene Nachricht")
      : tr("{n} ungelesene Nachrichten", { n });
  }
}

async function syncTrades(quiet = true, focus = "") {
  try {
    const q = focus ? `?focus=${encodeURIComponent(focus)}` : "";
    const res = await api("/hub/trades/sync" + q, { method: "POST" });
    if (!quiet) {
      toast(res.new_messages
        ? `${res.new_messages} neue Nachricht(en) 📬` : "Nichts Neues");
    }
    return res;
  } catch (e) {
    if (!quiet) toast(e.message);
    return null;
  }
}

/* Automatisches Nachladen. Drei Takte, je nachdem wo man gerade ist:
   im offenen Gespräch schnell, in der Vorgangsliste gemächlich, sonst nur
   ab und zu für den Zähler am Tab. Bei verborgenem Fenster pausiert alles. */
let pollTimer = null;
let pollEvery = 0;

function setPolling(seconds) {
  if (pollEvery === seconds) return;
  pollEvery = seconds;
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  if (!seconds) return;
  pollTimer = setInterval(pollTrades, seconds * 1000);
}

async function pollTrades() {
  if (document.hidden || !state.hubConnected) return;
  const res = await syncTrades(true, openTradeId || "");
  if (!res) return;
  if (openTradeId) renderTrade(true);
  else if (hubTab === "trades" && !$("view-hub").hidden) loadTrades(true);
  else refreshUnread();
  if (res.new_messages && !openTradeId) {
    toast(tr("{n} neue Nachricht(en) 📬", { n: res.new_messages }));
  }
}

async function refreshUnread() {
  try {
    const d = await api("/hub/trades");
    markUnread((d.trades || []).reduce((s, t) => s + (t.unread || 0), 0));
  } catch (_) { /* Zähler ist nice-to-have */ }
}

/* Takt an die Ansicht anpassen. */
function updatePolling() {
  if (!state.hubConnected) { setPolling(0); return; }
  if (openTradeId) setPolling(8);                       // Gespräch offen
  else if (hubTab === "trades" && !$("view-hub").hidden) setPolling(20);
  else setPolling(60);                                  // nur der Zähler
}

let tradesSig = "";

async function loadTrades(quiet = false) {
  const box = $("hub-trades");
  if (!quiet) {
    box.innerHTML = brickLoading("Vorgänge werden geladen …");
    await syncTrades();
  }
  try {
    const { trades } = await api("/hub/trades");
    markUnread(trades.reduce((s, t) => s + (t.unread || 0), 0));
    // Beim Hintergrund-Nachladen nur zeichnen, wenn sich wirklich etwas
    // geändert hat – sonst flackert die Liste im Takt.
    const sig = JSON.stringify(trades.map((t) =>
      [t.id, t.status, t.unread, t.updated_at, t.last_body, t.taken_at]));
    if (quiet && sig === tradesSig) return;
    tradesSig = sig;
    if (!trades.length) {
      box.innerHTML = `<p class="search-hint">${esc(tr("Noch keine Vorgänge. "
        + "Melde bei einem Angebot „Interesse“ an – daraus wird ein "
        + "Gespräch."))}</p>`;
      return;
    }
    box.innerHTML = trades.map((t) => `
      <div class="card trade-row-item" data-trade="${esc(t.id)}">
        <div class="card-head">
          <div class="card-title">
            <strong>${esc(t.item_name || t.item_id)}</strong>
            <div class="sub">${t.direction === "out" ? "→ an" : "← von"}
              ${esc(t.other_name || "?")} · ${tradeStatusText(t.status)}
              ${t.item_gone ? " · nicht mehr angeboten" : ""}</div>
            ${t.last_body ? `<div class="sub">${esc(t.last_body.slice(0, 70))}${t.last_body.length > 70 ? "…" : ""}</div>` : ""}
            ${t.unread ? `<span class="badge badge-wanted">${t.unread} neu</span>` : ""}
            ${t.status === "accepted" && !t.taken_at
    ? `<span class="badge badge-wanted">${t.direction === "out"
      ? tr("noch nicht verbucht") : tr("noch nicht ausgetragen")}</span>` : ""}
          </div>
        </div>
      </div>`).join("");
    box.querySelectorAll("[data-trade]").forEach((el) => {
      el.addEventListener("click", () => openTrade(el.dataset.trade));
    });
  } catch (e) {
    box.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

function tradeStatusText(s) {
  return { open: "offen", accepted: "angenommen ✔",
           declined: "abgelehnt", closed: "abgeschlossen" }[s] || s;
}

async function openTrade(id) {
  openTradeId = id;
  tradeSig = "";
  const ov = $("trade-overlay");
  ov.hidden = false;
  document.body.style.overflow = "hidden";
  await syncTrades(true, id);       // gleich den neuesten Stand holen
  await renderTrade();
  updatePolling();
}

let tradeSig = "";
let offenerTausch = null;

/* Angenommener Tausch → Sammlung oder Liste.

   „Annehmen" war bisher eine reine Zusage im Gespräch: Der Artikel blieb, wo
   er war, und musste von Hand nachgetragen werden. Gebucht wird trotzdem
   nicht automatisch – zwischen Zusage und Karton in der Hand liegen beim
   Tauschen gern ein paar Tage, und der Preis steht oft erst dann fest. */
/* Gegenstück: ein zugesagtes Stück geht weg.

   Hier verschwindet etwas aus der Sammlung, deshalb passiert es nur nach
   ausdrücklicher Bestätigung im App-Fenster – und nie von allein. */
async function tauschAbgeben() {
  const t = offenerTausch;
  if (!t) return;
  let kandidaten = [];
  try {
    kandidaten = (await api(`/hub/trades/${openTradeId}/candidates`))
      .candidates || [];
  } catch (e) { toast(e.message); return; }
  if (!kandidaten.length) {
    toast(tr("Der Artikel steht nicht in deiner Sammlung."));
    return;
  }
  const vorhanden = kandidaten.reduce((s, k) => s + k.quantity, 0);
  const felder = [];
  // Dieselbe Nummer kann neu und gebraucht dastehen – dann muss die Wahl
  // getroffen werden, bevor etwas verschwindet.
  if (kandidaten.length > 1) {
    felder.push({ name: "zustand", label: tr("Welches Stück?"),
      typ: "auswahl", wert: kandidaten[0].condition,
      optionen: kandidaten.map((k) => ({ wert: k.condition,
        label: `${k.condition === "new" ? tr("Neu") : tr("Gebraucht")} · `
          + tr("{n}× vorhanden", { n: k.quantity }) })) });
  }
  felder.push({ name: "anzahl", label: tr("Anzahl"), typ: "zahl", wert: "1" });
  const d = await appDialog({
    titel: tr("Aus der Sammlung austragen"),
    text: tr("{was} geht an {wer}. In der Sammlung: {n}×.",
      { was: t.item_name || t.item_id, wer: t.other_name || "?",
        n: vorhanden }),
    felder, ok: tr("Austragen"), gefahr: true,
  });
  if (!d) return;
  try {
    const res = await api(`/hub/trades/${openTradeId}/give`, {
      method: "POST", body: {
        quantity: Math.min(999, Math.max(1, Number(d.anzahl) || 1)),
        condition: d.zustand || (kandidaten.length === 1
          ? kandidaten[0].condition : null),
      } });
    toast(res.geloescht
      ? tr("Ausgetragen – der Eintrag ist weg 📤")
      : tr("Ausgetragen – noch {n}× in der Sammlung", { n: res.rest }));
    renderTrade();
  } catch (e) { toast(e.message); }
}

async function tauschUebernehmen() {
  const t = offenerTausch;
  if (!t) return;
  let listen = [];
  if (state.user && state.user.is_dealer) {
    try { listen = (await api("/lists")).lists || []; } catch (e) { listen = []; }
  }
  const ziele = [{ wert: "sammlung", label: tr("Sammlung") }].concat(
    listen.map((l) => ({ wert: `l${l.id}`, label: `🛒 ${l.name}` })));
  const d = await appDialog({
    titel: tr("Tausch übernehmen"),
    text: t.taken_at
      ? tr("Dieser Vorgang wurde schon einmal verbucht – noch einmal buchen "
        + "erhöht die Anzahl.")
      : tr("{was} von {wer} eintragen.",
        { was: t.item_name || t.item_id, wer: t.other_name || "?" }),
    felder: [
      { name: "ziel", label: tr("Wohin?"), typ: "auswahl", optionen: ziele,
        wert: "sammlung" },
      { name: "anzahl", label: tr("Anzahl"), typ: "zahl", wert: "1" },
      { name: "zustand", label: tr("Zustand"), typ: "auswahl", optionen: [
        { wert: "used", label: tr("Gebraucht") },
        { wert: "new", label: tr("Neu") }], wert: t.condition || "used" },
      { name: "preis", label: tr("Bezahlt (optional)"), typ: "zahl",
        platzhalter: "0,00" },
    ],
    ok: tr("Übernehmen"),
  });
  if (!d) return;
  const aufListe = d.ziel !== "sammlung";
  try {
    const res = await api(`/hub/trades/${openTradeId}/take`, {
      method: "POST", body: {
        ziel: aufListe ? "liste" : "sammlung",
        list_id: aufListe ? Number(d.ziel.slice(1)) : null,
        quantity: Math.min(999, Math.max(1, Number(d.anzahl) || 1)),
        condition: d.zustand,
        paid_price: betragLesen(d.preis),
      } });
    const e = res.ergebnis || {};
    toast(aufListe
      ? (e.merged ? tr("Schon auf der Liste – Anzahl erhöht (jetzt {n}×)",
        { n: e.qty }) : tr("Auf die Liste gesetzt 🛒"))
      : (e.merged ? tr("Schon vorhanden – Anzahl erhöht (jetzt {n}×)",
        { n: e.quantity }) : tr("Zur Sammlung hinzugefügt ✔")));
    renderTrade();
  } catch (e) { toast(e.message); }
}

async function renderTrade(quiet = false) {
  try {
    const { trade, messages } = await api(`/hub/trades/${openTradeId}`);
    // Nur neu zeichnen, wenn sich etwas geändert hat: sonst springt beim
    // automatischen Nachladen die Bildlaufleiste und Getipptes ginge unter.
    const sig = JSON.stringify([trade.status, trade.item_gone, trade.taken_at,
      messages.map((m) => [m.id, m.delivered])]);
    if (quiet && sig === tradeSig) return;
    const box = $("trade-msgs");
    const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
    tradeSig = sig;
    $("trade-title").textContent = trade.item_name || trade.item_id;
    $("trade-sub").textContent =
      `${trade.direction === "out" ? "an" : "von"} ${trade.other_name || "?"}`
      + ` · ${tradeStatusText(trade.status)}`;
    $("trade-gone").hidden = !trade.item_gone;
    // Zugesagt heisst noch nicht verbucht: Solange der Tausch angenommen ist
    // und der Artikel zu mir kommt, steht hier der Weg in die Sammlung.
    offenerTausch = trade;
    const zugesagt = trade.status === "accepted";
    const kommt = zugesagt && trade.direction === "out";
    const geht = zugesagt && trade.direction === "in";
    $("trade-take-row").hidden = !(kommt || geht);
    if (kommt || geht) {
      const knopf = $("trade-take");
      const wann = trade.taken_at
        ? new Date(trade.taken_at * 1000).toLocaleDateString(dateLocale()) : "";
      knopf.textContent = trade.taken_at
        ? (kommt
          ? tr("✔ Verbucht am {datum} · noch einmal buchen", { datum: wann })
          : tr("✔ Ausgetragen am {datum} · noch einmal austragen",
            { datum: wann }))
        : (kommt ? tr("📥 In die Sammlung übernehmen")
          : tr("📤 Aus der Sammlung austragen"));
      knopf.classList.toggle("add", kommt && !trade.taken_at);
      knopf.classList.toggle("danger", geht && !trade.taken_at);
    }
  zeigeSicherheitsnummer(trade.other_id);
    box.innerHTML = messages.map((m) => `
      <div class="trade-msg${m.mine ? " mine" : ""}">
        ${esc(m.body)}
        <span class="when">${new Date(m.created_at * 1000)
          .toLocaleString(dateLocale())}${m.mine ? (m.delivered ? " · zugestellt ✓" : " · unterwegs …") : ""}</span>
      </div>`).join("");
    if (!quiet || atBottom) box.scrollTop = box.scrollHeight;
    refreshUnread();
  } catch (e) { if (!quiet) toast(e.message); }
}

function closeTrade() {
  $("trade-overlay").hidden = true;
  $("report-overlay").hidden = true;   // hing es noch daran, geht es mit
  document.body.style.overflow = "";
  openTradeId = null;
  offenerTausch = null;
  updatePolling();
  if (hubTab === "trades" && !$("view-hub").hidden) loadTrades(true);
}

/* Auswahl: was biete ich an? */
async function loadShareView() {
  $("hub-publish").hidden = !(state.user && state.user.is_admin);
  const box = $("hub-share-list");
  box.innerHTML = brickLoading("Auswahl wird geladen …");
  try {
    const s = await api("/share/status");
    const wartet = s.known_state ? s.items.filter((i) => !i.published).length : 0;
    $("hub-share-info").textContent = s.shared
      ? tr("{n} Artikel ausgewählt (Vorschlag aus der Abgabeliste: {v})",
        { n: s.shared, v: s.suggested })
        + (s.known_state
          ? tr(" · {n} veröffentlicht, {wartet} wartet auf das Veröffentlichen.",
            { n: s.published, wartet })
          : ".")
      : tr("Noch nichts ausgewählt. Vorschlag aus der Abgabeliste: {n} Artikel.",
        { n: s.suggested });

    // Was noch im Hub steht, aber nicht mehr ausgewählt ist, verschwindet
    // beim nächsten Veröffentlichen – das gehört gesagt, nicht verschwiegen.
    const stale = (s.stale || []).length ? `
      <p class="warn-line">Im Netzwerk stehen noch
        ${s.stale.length} Artikel, die hier nicht mehr ausgewählt sind
        (${s.stale.map((o) => esc(o.name || o.item_id)).slice(0, 3).join(", ")}${s.stale.length > 3 ? " …" : ""}).
        Sie verschwinden beim nächsten Veröffentlichen.</p>` : "";

    box.innerHTML = s.items.length ? stale + s.items.map((it) => `
      <div class="card">
        <div class="card-head">
          <img class="card-img" src="${imgSrc(it.img_url, true)}" alt="" loading="lazy">
          <div class="card-title">
            <strong>${esc(it.name)}</strong>
            <div class="sub">${esc(it.item_id)} · ${it.quantity}× vorhanden ·
              ${it.condition === "new" ? tr("Neu") : tr("Gebraucht")}</div>
            ${s.known_state ? `<span class="badge ${it.published ? "badge-owned" : "badge-wanted"}">${
              it.published ? tr("veröffentlicht ({n}×)", { n: it.published_qty })
                : tr("noch nicht veröffentlicht")}</span>` : ""}
          </div>
          <button class="mini-btn" data-unshare="${it.id}">Entfernen</button>
        </div>
        ${it.quantity > 1 ? `
        <label class="share-qty">Zum Tausch anbieten:
          <select data-shareqty="${it.id}">
            ${Array.from({ length: it.quantity }, (_, n) => n + 1).map((n) =>
              `<option value="${n}"${n === it.share_qty ? " selected" : ""}>${n}×</option>`).join("")}
          </select>
        </label>` : ""}
      </div>`).join("")
      : stale + `<p class="search-hint">Nichts ausgewählt – veröffentlicht wird dann nichts.</p>`;
    box.querySelectorAll("[data-unshare]").forEach((b) => {
      b.addEventListener("click", async () => {
        try {
          await api(`/collection/${b.dataset.unshare}/share`, { method: "POST",
            body: { shared: false } });
          loadShareView();
        } catch (e) { toast(e.message); }
      });
    });
    box.querySelectorAll("[data-shareqty]").forEach((sel) => {
      sel.addEventListener("change", async () => {
        try {
          await api(`/collection/${sel.dataset.shareqty}/share`, {
            method: "POST",
            body: { shared: true, qty: Number(sel.value) } });
          toast("Menge gemerkt – beim Veröffentlichen wird sie übernommen");
        } catch (e) { toast(e.message); loadShareView(); }
      });
    });
  } catch (e) {
    box.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

function wireHubViewOnce() {
  if (hubViewWired) return;
  hubViewWired = true;

  document.querySelectorAll("[data-hubtab]").forEach((b) => {
    b.addEventListener("click", () => showHubTab(b.dataset.hubtab));
  });
  $("hub-sync").addEventListener("click", async () => {
    await syncTrades(false);
    loadTrades();
  });
  $("hub-share-dupes").addEventListener("click", async () => {
    try {
      const r = await api("/share/from_duplicates", { method: "POST" });
      toast(tr("{n} Artikel übernommen", { n: r.added }));
      loadShareView();
    } catch (e) { toast(e.message); }
  });
  $("hub-share-clear").addEventListener("click", async () => {
    if (!confirm(tr("Die ganze Auswahl leeren?"))) return;
    try {
      await api("/share/clear", { method: "POST" });
      loadShareView();
    } catch (e) { toast(e.message); }
  });

  // Chat
  $("trade-close").addEventListener("click", closeTrade);
  $("trade-overlay").addEventListener("click", (ev) => {
    if (ev.target === $("trade-overlay")) closeTrade();
  });
  const send = async () => {
    const inp = $("trade-input");
    const text = inp.value.trim();
    if (!text || !openTradeId) return;
    inp.value = "";
    try {
      await api(`/hub/trades/${openTradeId}/messages`, { method: "POST",
        body: { text } });
      renderTrade();
    } catch (e) { toast(e.message); inp.value = text; }
  };
  $("trade-send").addEventListener("click", send);
  $("trade-input").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") { ev.preventDefault(); send(); }
  });
  const setStatus = async (status) => {
    try {
      await api(`/hub/trades/${openTradeId}/status`, { method: "POST",
        body: { status } });
      // Ablehnen beendet das Gespräch – dann soll das Fenster auch zugehen,
      // sonst steht man vor einem Chat, in dem es nichts mehr zu sagen gibt.
      if (status === "declined") { toast("Abgelehnt"); closeTrade(); }
      else {
        toast("Angenommen ✔");
        await renderTrade();
        // Zusage steht – jetzt gleich fragen, wohin der Artikel soll. Ohne
        // das passierte auf „Annehmen" sichtbar gar nichts.
        if (status === "accepted" && offenerTausch) {
          if (offenerTausch.direction === "out") await tauschUebernehmen();
          else await tauschAbgeben();
        }
      }
    } catch (e) { toast(e.message); }
  };
  $("trade-accept").addEventListener("click", () => setStatus("accepted"));
  $("trade-take").addEventListener("click", () => {
    if (offenerTausch && offenerTausch.direction === "in") tauschAbgeben();
    else tauschUebernehmen();
  });
  $("trade-decline").addEventListener("click", () => setStatus("declined"));
  $("trade-report").addEventListener("click", openReport);
  $("trade-delete").addEventListener("click", async () => {
    if (!openTradeId) return;
    if (!confirm(tr("Diese Unterhaltung endgültig löschen? Auch beim "
      + "Gegenüber verschwindet sie aus dem Hub."))) return;
    try {
      await api(`/hub/trades/${openTradeId}`, { method: "DELETE" });
      closeTrade();
      tradesSig = "";
      loadTrades();
    } catch (e) { toast(e.message); }
  });

  // Anfrage-Fenster
  $("interest-close").addEventListener("click", closeInterest);
  $("interest-cancel").addEventListener("click", closeInterest);
  $("interest-overlay").addEventListener("click", (ev) => {
    if (ev.target === $("interest-overlay")) closeInterest();
  });
  $("interest-send").addEventListener("click", sendInterest);

  // Melde-Fenster
  $("report-close").addEventListener("click", closeReport);
  $("report-cancel").addEventListener("click", closeReport);
  $("report-overlay").addEventListener("click", (ev) => {
    if (ev.target === $("report-overlay")) closeReport();
  });
  $("report-send").addEventListener("click", sendReport);

  $("hub-publish").addEventListener("click", async (ev) => {
    const b = ev.currentTarget; b.disabled = true;
    try {
      const res = await api("/hub/publish", { method: "POST" });
      toast(tr("{n} Angebote veröffentlicht 📤", { n: res.count }));
      loadHubView();
    } catch (e) { toast(e.message); } finally { b.disabled = false; }
  });

  $("hub-refresh-offers").addEventListener("click", () => loadHubOffers());
  // Suche im Netzwerk – kurz abwarten, damit nicht jeder Tastendruck fragt
  let hubSearchTimer;
  $("hub-search").addEventListener("input", () => {
    clearTimeout(hubSearchTimer);
    hubSearchTimer = setTimeout(loadHubOffers, 350);
  });
  $("hub-search").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") { clearTimeout(hubSearchTimer); loadHubOffers(); }
  });

  $("hub-make-invite").addEventListener("click", async (ev) => {
    const b = ev.currentTarget; b.disabled = true;
    try {
      const res = await api("/hub/invite", { method: "POST", body: {} });
      const out = $("hub-invite-out");
      out.hidden = false;
      out.innerHTML = esc(tr("Einladungscode (einmal gültig, an einen "
        + "Freund geben):")) + ` <code>${esc(res.invite_code)}</code>`;
      loadInviteQuota();
    } catch (e) {
      // Kontingent aufgebraucht: statt bloßer Fehlermeldung den Weg anbieten
      if (/Kontingent/.test(e.message)) offerInviteRequest(e.message);
      else toast(e.message);
    } finally { b.disabled = false; }
  });
}

/* Einladungs-Kontingent anzeigen – und ab null den Weg zur Anfrage. */
async function loadInviteQuota() {
  const el = $("hub-quota");
  if (!el) return;
  try {
    const q = await api("/hub/invite_quota");
    if (!q.quota) { el.hidden = true; return; }
    el.hidden = false;
    if (q.pending_request) {
      el.textContent = tr("✉️ Einladungen: {n} von {max} vergeben · Anfrage "
        + "über {want} weitere läuft.",
        { n: q.used, max: q.quota, want: q.pending_request.want });
    } else if (q.left > 0) {
      el.textContent = tr("✉️ Einladungen: noch {n} von {max} frei.",
        { n: q.left, max: q.quota });
    } else {
      el.innerHTML = esc(tr("✉️ Alle {max} Einladungen vergeben.",
        { max: q.quota })) + " "
        + `<button class="mini-btn" data-req-invites>${esc(tr("Mehr anfragen"))}</button>`;
      el.querySelector("[data-req-invites]")
        .addEventListener("click", () => offerInviteRequest());
    }
  } catch (_) { el.hidden = true; }
}

/* Anfrage nach mehr Einladungen stellen. */
async function offerInviteRequest(hint) {
  const d = await appDialog({
    titel: tr("Mehr Einladungen anfragen"),
    text: hint || "",
    felder: [
      { name: "want", label: tr("Wie viele zusätzliche Einladungen brauchst du?"),
        typ: "zahl", wert: "3" },
      { name: "reason", label: tr("Kurz begründen (optional)"), max: 300 },
    ],
    ok: tr("Anfragen"),
  });
  if (!d) return;
  const n = Math.max(1, Math.min(Number(d.want) || 3, 50));
  const reason = d.reason || "";
  try {
    await api("/hub/invite_request", { method: "POST",
      body: { want: n, reason } });
    toast("Anfrage gestellt – ein Hub-Admin entscheidet darüber ✉️");
    loadInviteQuota();
  } catch (e) { toast(e.message); }
}

/* Tipp auf ein Angebot: Läuft schon ein Gespräch dazu, geht es direkt auf –
   sonst das Fenster für die Anfrage. */
let interestOffer = null;

async function openOffer(o) {
  // Beim Laden der Angebote schon ermittelt – kein zweiter Abruf nötig
  const known = tradeByOffer.get(offerKey(o.m, o.i));
  if (known) { showHubTab("trades"); openTrade(known.id); return; }
  openInterest(o);
}

function openInterest(o) {
  interestOffer = o;
  $("interest-name").textContent = o.n;
  $("interest-sub").textContent = o.id_ + " · " + tr("von {name}", { name: o.who });
  $("interest-img").src = o.img || IMG_PLACEHOLDER;
  // Vorschlag steht im Feld – anpassbar, nicht in einem Systemfenster
  $("interest-text").value =
    tr("Hallo {name}, hättest du Interesse, den {was} zu tauschen?",
      { name: o.who, was: o.n });
  $("interest-overlay").hidden = false;
  document.body.style.overflow = "hidden";
  const ta = $("interest-text");
  ta.focus();
  ta.setSelectionRange(ta.value.length, ta.value.length);
}

function closeInterest() {
  $("interest-overlay").hidden = true;
  document.body.style.overflow = "";
  interestOffer = null;
}

async function sendInterest() {
  const o = interestOffer;
  const text = $("interest-text").value.trim();
  if (!o || !text) { toast("Bitte eine Nachricht schreiben"); return; }
  const btn = $("interest-send");
  btn.disabled = true;
  try {
    const res = await api("/hub/trades", { method: "POST", body: {
      to: o.m, item_id: o.i, item_name: o.n, text,
      // Aus dem Angebot mitgeben: Wird der Tausch angenommen, lässt sich der
      // Artikel damit ohne Nachfragen in die Sammlung buchen.
      item_type: o.typ || "", img_url: o.bild || "",
      bricklink_url: o.bl || "", condition: o.zustand || "" } });
    closeInterest();
    toast("Angefragt – das Gespräch steht unter Meine Vorgänge 💬");
    showHubTab("trades");
    openTrade(res.trade_id);
  } catch (e) { toast(e.message); } finally { btn.disabled = false; }
}

/* Melden. Der Verlauf geht nur mit, wenn man ausdrücklich zustimmt – sonst
   sieht der Hub-Admin nur die Begründung. */
function openReport() {
  if (!openTradeId) return;
  $("report-reason").value = "";
  $("report-history").checked = true;
  // Das Gespräch tritt zur Seite, bleibt aber der offene Vorgang – nach dem
  // Melden (oder Abbrechen) kommt es wieder. Sonst stünden zwei Fenster
  // übereinander, samt zweier Schließen-Knöpfe.
  $("trade-overlay").hidden = true;
  $("report-overlay").hidden = false;
  $("report-reason").focus();
}

function closeReport() {
  $("report-overlay").hidden = true;
  if (openTradeId) $("trade-overlay").hidden = false;
}

async function sendReport() {
  if (!openTradeId) { closeReport(); return; }
  const reason = $("report-reason").value.trim();
  if (reason.length < 3) { toast("Bitte kurz beschreiben, was war"); return; }
  const btn = $("report-send");
  btn.disabled = true;
  try {
    await api(`/hub/trades/${openTradeId}/report`, { method: "POST", body: {
      reason, include_history: $("report-history").checked } });
    closeReport();
    toast("Gemeldet – ein Hub-Admin schaut sich das an ⚑");
  } catch (e) { toast(e.message); } finally { btn.disabled = false; }
}

let hubSearchSeq = 0;
let tradeByOffer = new Map();      // "mitglied|artikel" -> laufender Vorgang

function offerKey(memberId, itemId) { return memberId + "|" + itemId; }

async function loadHubOffers() {
  const seq = ++hubSearchSeq;      // ältere Suchen dürfen nicht überholen
  const box = $("hub-offers");
  const q = ($("hub-search") ? $("hub-search").value : "").trim();
  box.innerHTML = brickLoading("Angebote werden geladen …");
  try {
    // Angebote und eigene Vorgänge zusammen holen, damit an der Karte gleich
    // steht, wo schon ein Gespräch läuft.
    const [offerRes, tradeRes] = await Promise.all([
      api("/hub/offers" + (q ? `?q=${encodeURIComponent(q)}` : "")),
      api("/hub/trades").catch(() => ({ trades: [] })),
    ]);
    const { offers } = offerRes;
    tradeByOffer = new Map((tradeRes.trades || []).map((t) =>
      [offerKey(t.other_id, t.item_id), t]));
    if (seq !== hubSearchSeq) return;
    if (!offers.length) {
      box.innerHTML = `<p class="search-hint">${q
        ? `Nichts gefunden zu „${esc(q)}".`
        : "Noch keine Angebote von anderen im Netzwerk."}</p>`;
      return;
    }
    box.innerHTML = offers.map((o) => {
      const t = tradeByOffer.get(offerKey(o.member_id, o.item_id));
      return `
      <div class="card tappable" data-offer-card>
        <div class="card-head">
          <img class="card-img" src="${o.img_data ? esc(o.img_data) : imgSrc(o.img_url, true)}" data-gid="${esc(o.item_id)}" data-gtype="${esc(o.item_type || "minifig")}" alt="" loading="lazy">
          <div class="card-title">
            <strong>${esc(o.name)}</strong>
            <div class="sub">${esc(o.item_id)}${o.condition ? " · " + (o.condition === "new" ? tr("Neu") : tr("Gebraucht")) : ""}${o.qty > 1 ? " · " + o.qty + "×" : ""}</div>
            <span class="badge badge-owned">von ${esc(o.display_name)}</span>
            ${t ? `<span class="badge badge-wanted">💬 angefragt · ${tradeStatusText(t.status)}${t.unread ? ` · ${t.unread} neu` : ""}</span>` : ""}
          </div>
        </div>
        <div class="card-actions">
          <button class="mini-btn add" data-interest>${t ? "💬 Gespräch öffnen" : "💬 Interesse"}</button>
          ${o.bricklink_url ? `<a class="mini-btn link" href="${esc(o.bricklink_url)}" target="_blank" rel="noopener">BrickLink ↗</a>` : ""}
        </div>
      </div>`;
    }).join("");

    // Ganze Karte antippbar – nicht nur der Knopf
    box.querySelectorAll("[data-offer-card]").forEach((card, i) => {
      const o = offers[i];
      const data = { m: o.member_id, i: o.item_id, n: o.name,
                     who: o.display_name, img: o.img_data || o.img_url,
                     id_: o.item_id, typ: o.item_type || "",
                     bild: o.img_url || "", bl: o.bricklink_url || "",
                     zustand: o.condition || "" };
      card.addEventListener("click", (ev) => {
        if (ev.target.closest("a, .card-img")) return;
        openOffer(data);
      });
    });
  } catch (e) {
    box.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}
