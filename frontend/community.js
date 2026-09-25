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
      // Direkt danach durch die Einstellungen führen – überspringbar.
      communityPlanerStarten();
    } catch (e) { err.textContent = e.message; err.hidden = false; }
  });

  $("hub-disconnect").addEventListener("click", async () => {
    if (!confirm(tr("Aus dem Tausch-Netzwerk abmelden? Deine Angebote und "
      + "Wünsche werden dort herausgenommen. Zum Wiederkommen brauchst du "
      + "eine neue Einladung."))) return;
    try {
      const r = await api("/hub/disconnect", { method: "POST" });
      renderHubStatus({ connected: false });
      state.hubConnected = false;
      updateHubTab();
      toast(r.hub_informiert === false
        ? tr("Getrennt – der Hub war nicht erreichbar. Deine Angebote "
          + "verschwinden dort erst mit der Pause wegen Inaktivität.")
        : tr("Abgemeldet – deine Angebote sind aus dem Netzwerk genommen."));
    } catch (e) { toast(e.message); }
  });
}

/* Waren die eigenen Angebote pausiert, weil man länger nicht da war? Das
   sagt der Hub erst beim Zurückkommen – hier steht es dann zwei Wochen. */
function zeigePause(s) {
  const el = $("hub-pause");
  const p = s && s.pause;
  el.hidden = !p;
  if (!p) return;
  const datum = (ts) => new Date(ts * 1000).toLocaleDateString(dateLocale());
  el.textContent = tr("⏸ Deine Angebote waren vom {von} bis {bis} pausiert, "
    + "weil du länger als {tage} Tage nicht im Netzwerk warst. Jetzt sind "
    + "sie wieder sichtbar – schau am besten, ob noch alles stimmt.",
  { von: datum(p.von), bis: datum(p.bis), tage: s.inaktiv_tage || 30 });
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
    hubIch = { member_id: s.member_id, display_name: s.display_name };
    $("hub-ich-avatar").textContent = avatarText(s.display_name);
    $("hub-blocked").hidden = !s.blocked;
    zeigePause(s);
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
let hubTab = "entdecken";
let openTradeId = null;

function showHubTab(name) {
  hubTab = name;
  ["entdecken", "offers", "trades", "share"].forEach((t) => {
    $("hubpane-" + t).hidden = t !== name;
  });
  document.querySelectorAll("[data-hubtab]").forEach((b) =>
    b.classList.toggle("sel", b.dataset.hubtab === name));
  // Angebote beim Zurückwechseln neu laden – sonst stünde dort noch der
  // Stand von vorhin, ohne die inzwischen gestarteten Gespräche.
  if (name === "entdecken") loadEntdecken();
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
    box.innerHTML = brickLoading("Nachrichten werden geladen …");
    await syncTrades();
  }
  try {
    const { trades } = await api("/hub/trades");
    markUnread(trades.reduce((s, t) => s + (t.unread || 0), 0));
    // Beim Hintergrund-Nachladen nur zeichnen, wenn sich wirklich etwas
    // geändert hat – sonst flackert die Liste im Takt.
    const sig = JSON.stringify(trades.map((t) =>
      [t.id, t.status, t.unread, t.updated_at, t.last_body, t.taken_at,
        t.shipped_at, t.arrived_at]));
    if (quiet && sig === tradesSig) return;
    tradesSig = sig;
    if (!trades.length) {
      box.innerHTML = `<p class="search-hint">${esc(tr("Noch keine Nachrichten. "
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
              ${esc(t.other_name || "?")} · ${["left", "gone"].includes(t.other_status)
    ? esc(tr("hat das Netzwerk verlassen")) : tradeStatusText(t.status)}
              ${t.item_gone ? " · nicht mehr angeboten" : ""}</div>
            ${t.last_body ? `<div class="sub">${esc(t.last_body.slice(0, 70))}${t.last_body.length > 70 ? "…" : ""}</div>` : ""}
            ${t.unread ? `<span class="badge badge-wanted">${t.unread} neu</span>` : ""}
            ${["accepted", "closed"].includes(t.status) && !t.taken_at
    ? `<span class="badge badge-wanted">${esc(tauschStand(t))}</span>` : ""}
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

/* Was als Nächstes ansteht – als Kennzeichen in der Gesprächsliste. */
function tauschStand(t) {
  if (tauschKommt(t)) {
    if (t.arrived_at) return tr("noch nicht verbucht");
    return t.shipped_at ? tr("📦 unterwegs") : tr("wartet auf Versand");
  }
  return t.shipped_at ? tr("noch nicht ausgetragen")
    : tr("noch nicht verschickt");
}

function tradeStatusText(s) {
  return tr({ open: "offen", accepted: "angenommen ✔",
           declined: "abgelehnt", closed: "abgeschlossen",
           removed: "vom Gegenüber gelöscht" }[s] || s);
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
      typ: "auswahl",
      wert: (kandidaten.find((k) => k.condition === t.condition)
        || kandidaten[0]).condition,
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
    toast((res.geloescht
      ? tr("Ausgetragen – der Eintrag ist weg 📤")
      : tr("Ausgetragen – noch {n}× in der Sammlung", { n: res.rest }))
      + (res.status === "closed" ? " · " + tr("Tausch abgeschlossen 🏁") : ""));
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
    toast((aufListe
      ? (e.merged ? tr("Schon auf der Liste – Anzahl erhöht (jetzt {n}×)",
        { n: e.qty }) : tr("Auf die Liste gesetzt 🛒"))
      : (e.merged ? tr("Schon vorhanden – Anzahl erhöht (jetzt {n}×)",
        { n: e.quantity }) : tr("Zur Sammlung hinzugefügt ✔")))
      + (res.wunsch_erledigt ? " · " + tr("von der Wunschliste genommen") : "")
      + (res.status === "closed" ? " · " + tr("Tausch abgeschlossen 🏁") : ""));
    renderTrade();
  } catch (e) { toast(e.message); }
}

/* Kommt der Artikel zu mir? Bei einer Anfrage zum Anfragenden, bei einem
   Angebot (das Gegenüber sucht, ich gebe ab) zum Empfänger. */
function tauschKommt(t) {
  return (t.direction === "out") !== (t.kind === "angebot");
}

async function renderTrade(quiet = false) {
  try {
    const { trade, messages } = await api(`/hub/trades/${openTradeId}`);
    // Nur neu zeichnen, wenn sich etwas geändert hat: sonst springt beim
    // automatischen Nachladen die Bildlaufleiste und Getipptes ginge unter.
    const sig = JSON.stringify([trade.status, trade.item_gone, trade.taken_at,
      trade.shipped_at, trade.arrived_at, trade.other_status,
      messages.map((m) => [m.id, m.delivered])]);
    if (quiet && sig === tradeSig) return;
    const box = $("trade-msgs");
    const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
    tradeSig = sig;
    $("trade-title").textContent = trade.item_name || trade.item_id;
    $("trade-sub").textContent =
      `${trade.direction === "out" ? "an" : "von"} ${trade.other_name || "?"}`
      + ` · ${tradeStatusText(trade.status)}`;
    // Abgemeldet oder ganz gelöscht: Dort holt nie wieder jemand etwas ab.
    const weg = ["left", "gone"].includes(trade.other_status);
    const entfernt = trade.status === "removed" || weg;
    $("trade-gone").hidden = !trade.item_gone || entfernt;
    $("trade-removed").hidden = trade.status !== "removed";
    $("trade-left").hidden = !weg || trade.status === "removed";
    $("trade-gesperrt").hidden = trade.other_status !== "disabled";
    $("trade-write-row").hidden = entfernt;
    // Annehmen oder ablehnen kann nur, wer gefragt wurde – und nur, solange
    // noch nichts entschieden ist. Bis 2.88.55 standen beide Knöpfe auch
    // beim Fragenden, der so seine eigene Anfrage „annehmen“ konnte.
    const entscheiden = trade.direction === "in" && trade.status === "open";
    $("trade-accept").hidden = !entscheiden;
    $("trade-decline").hidden = !entscheiden;
    // Zugesagt heißt noch nicht da: Zwischen Annehmen und Buchen stehen
    // „verschickt“ (wer abgibt) und „angekommen“ (wer bekommt). Der Knopf
    // zeigt immer den nächsten eigenen Schritt.
    offenerTausch = trade;
    // Auch ein abgeschlossener Tausch zeigt seine Schritte – und den Knopf,
    // falls hier noch gebucht werden soll („noch einmal buchen“).
    const zugesagt = trade.status === "accepted" || trade.status === "closed";
    $("trade-schritte").hidden = !zugesagt;
    $("trade-take-row").hidden = !zugesagt;
    if (zugesagt) {
      $("trade-schritte").innerHTML = tauschSchritte(trade);
      const kommt = tauschKommt(trade);
      const knopf = $("trade-take");
      const wann = datumKurz(trade.taken_at);
      let text;
      let farbe = "add";
      if (trade.taken_at) {
        text = kommt
          ? tr("✔ Verbucht am {datum} · noch einmal buchen", { datum: wann })
          : tr("✔ Ausgetragen am {datum} · noch einmal austragen",
            { datum: wann });
        farbe = "";
      } else if (kommt) {
        text = trade.arrived_at ? tr("📥 In die Sammlung übernehmen")
          : tr("📬 Ist angekommen");
      } else if (!trade.shipped_at) {
        text = tr("📦 Verschickt / übergeben");
      } else {
        text = tr("📤 Aus der Sammlung austragen");
        farbe = "danger";
      }
      knopf.textContent = text;
      knopf.classList.toggle("add", farbe === "add");
      knopf.classList.toggle("danger", farbe === "danger");
    }
  zeigeSicherheitsnummer(trade.other_id);
    box.innerHTML = messages.map((m) => `
      <div class="trade-msg${m.mine ? " mine" : ""}">
        ${esc(m.body)}
        <span class="when">${new Date(m.created_at * 1000)
          .toLocaleString(dateLocale())}${m.mine ? (m.delivered ? " · zugestellt ✓"
          : (entfernt ? "" : " · unterwegs …")) : ""}</span>
      </div>`).join("");
    if (!quiet || atBottom) box.scrollTop = box.scrollHeight;
    refreshUnread();
  } catch (e) { if (!quiet) toast(e.message); }
}

function datumKurz(ts) {
  return ts ? new Date(ts * 1000).toLocaleDateString(dateLocale(),
    { day: "numeric", month: "numeric" }) : "";
}

/* Die Schritte als Leiste – in der Reihenfolge, in der sie für mich
   kommen: Wer bekommt, bucht nach der Ankunft; wer abgibt, trägt nach dem
   Verschicken aus und erfährt danach, dass es angekommen ist. */
function tauschSchritte(t) {
  const kommt = tauschKommt(t);
  const gebucht = { an: !!t.taken_at, wann: t.taken_at,
    text: kommt ? tr("📥 Übernommen") : tr("📤 Ausgetragen") };
  const angekommen = { an: !!t.arrived_at, wann: t.arrived_at,
    text: tr("📬 Angekommen") };
  const schritte = [
    { an: true, text: tr("✔ Angenommen") },
    { an: !!t.shipped_at, wann: t.shipped_at, text: tr("📦 Verschickt") },
  ].concat(kommt ? [angekommen, gebucht] : [gebucht, angekommen]);
  schritte.push({ an: t.status === "closed", text: tr("🏁 Abgeschlossen") });
  return schritte.map((s) => `<span class="trade-schritt${s.an ? " an" : ""}">`
    + `${esc(s.text)}${s.wann ? ` <small>${esc(datumKurz(s.wann))}</small>` : ""}`
    + "</span>").join('<span class="trade-pfeil">→</span>');
}

/* Verschickt oder angekommen melden. Dazu geht eine Nachricht ins
   Gespräch – vorbelegt, aber änderbar, etwa für eine Sendungsnummer. So
   erfährt das Gegenüber davon wie von jeder anderen Nachricht. */
async function tauschSchrittMelden(step) {
  const t = offenerTausch;
  if (!t) return false;
  const verschickt = step === "shipped";
  const d = await appDialog({
    titel: verschickt ? tr("Verschickt oder übergeben?")
      : tr("Ist es angekommen?"),
    text: verschickt
      ? tr("{wer} bekommt dazu eine Nachricht – gern mit Sendungsnummer.",
        { wer: t.other_name || "?" })
      : tr("{was} ist bei dir? {wer} bekommt dazu eine Nachricht.",
        { was: t.item_name || t.item_id, wer: t.other_name || "?" }),
    felder: [{ name: "nachricht", label: tr("Nachricht"), typ: "text",
      wert: verschickt ? tr("📦 Ist verschickt!")
        : tr("📬 Ist angekommen – danke!") }],
    ok: verschickt ? tr("Verschickt") : tr("Angekommen"),
  });
  if (!d) return false;
  try {
    await api(`/hub/trades/${openTradeId}/progress`, { method: "POST",
      body: { step, text: (d.nachricht || "").trim() } });
  } catch (e) { toast(e.message); return false; }
  await renderTrade();
  return true;
}

/* Der Knopf unter dem Verlauf: immer der nächste eigene Schritt. */
async function tauschWeiter() {
  const t = offenerTausch;
  if (!t || !["accepted", "closed"].includes(t.status)) return;
  if (tauschKommt(t)) {
    if (!t.arrived_at && !(await tauschSchrittMelden("arrived"))) return;
    tauschUebernehmen();
  } else {
    if (!t.shipped_at && !(await tauschSchrittMelden("shipped"))) return;
    tauschAbgeben();
  }
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
        <div class="cm-art-zeile">
          <div class="erf-wahl cm-art" data-art="${it.id}" role="radiogroup" aria-label="${esc(tr("Angeboten zum"))}">
            ${["tausch", "verkauf", "beides"].map((w) =>
              `<button type="button" role="radio" data-wert="${w}" class="${(it.deal || "tausch") === w ? "sel" : ""}"
                aria-checked="${(it.deal || "tausch") === w}">${esc(cmArtName(w))}</button>`).join("")}
          </div>
        </div>
        ${it.quantity > 1 ? `
        <label class="share-qty">${esc(tr("Menge:"))}
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
    box.querySelectorAll("[data-art]").forEach((gruppe) => {
      gruppe.querySelectorAll("button").forEach((b) => {
        b.addEventListener("click", async () => {
          if (b.classList.contains("sel")) return;
          try {
            await api(`/collection/${gruppe.dataset.art}/share`, { method: "POST",
              body: { shared: true, deal: b.dataset.wert } });
            gruppe.querySelectorAll("button").forEach((x) => {
              x.classList.toggle("sel", x === b);
              x.setAttribute("aria-checked", String(x === b));
            });
            toast(tr("Gemerkt – gilt ab dem nächsten „Im Netzwerk anbieten“"));
          } catch (e) { toast(e.message); }
        });
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
  $("hub-mein-profil").addEventListener("click", openMeinProfil);
  $("profil-close").addEventListener("click", closeProfil);
  $("profil-overlay").addEventListener("click", (ev) => {
    if (ev.target === $("profil-overlay")) closeProfil();
  });
  $("meinprofil-close").addEventListener("click", closeMeinProfil);
  $("meinprofil-overlay").addEventListener("click", (ev) => {
    if (ev.target === $("meinprofil-overlay")) closeMeinProfil();
  });
  $("meinprofil-speichern").addEventListener("click", meinProfilSpeichern);
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
        // Gebucht wird erst nach „verschickt“ bzw. „angekommen“ – beim
        // Annehmen ist das Stück ja noch nicht unterwegs.
        toast(offenerTausch && !tauschKommt(offenerTausch)
          ? tr("Angenommen ✔ – als Nächstes verschicken")
          : tr("Angenommen ✔"));
        await renderTrade();
      }
    } catch (e) { toast(e.message); }
  };
  $("trade-accept").addEventListener("click", () => setStatus("accepted"));
  $("trade-take").addEventListener("click", tauschWeiter);
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
  document.querySelectorAll("[data-art-filter]").forEach((b) => {
    b.addEventListener("click", () => {
      hubArtFilter = b.dataset.artFilter;
      document.querySelectorAll("[data-art-filter]").forEach((x) =>
        x.classList.toggle("an", x === b));
      loadHubOffers();
    });
  });
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

function openInterest(o, text = "") {
  interestOffer = o;
  $("interest-name").textContent = o.n;
  $("interest-sub").textContent = o.id_ + " · " + (o.kind === "angebot"
    ? tr("für {name}", { name: o.who }) : tr("von {name}", { name: o.who }));
  $("interest-img").src = o.img || IMG_PLACEHOLDER;
  // Vorschlag steht im Feld – anpassbar, nicht in einem Systemfenster
  $("interest-text").value = text || (o.art === "verkauf"
    ? tr("Hallo {name}, ich würde dir den {was} gern abkaufen – was stellst du dir vor?",
      { name: o.who, was: o.n })
    : tr("Hallo {name}, hättest du Interesse, den {was} zu tauschen?",
      { name: o.who, was: o.n }));
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
      bricklink_url: o.bl || "", condition: o.zustand || "",
      kind: o.kind || "anfrage", other_name: o.who || "" } });
    closeInterest();
    toast(o.kind === "angebot"
      ? "Angeboten – das Gespräch steht unter Nachrichten 💬"
      : "Angefragt – das Gespräch steht unter Nachrichten 💬");
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
    const offers = offerRes.offers.filter((o) => cmArtPasst(o.deal));
    tradeByOffer = new Map((tradeRes.trades || []).map((t) =>
      [offerKey(t.other_id, t.item_id), t]));
    if (seq !== hubSearchSeq) return;
    if (!offers.length) {
      box.innerHTML = `<p class="search-hint">${q
        ? `Nichts gefunden zu „${esc(q)}".`
        : hubArtFilter ? esc(tr("Keine Angebote dieser Art."))
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
            <span class="badge badge-owned">von <button type="button" class="cm-name" data-profil="${esc(o.member_id)}">${esc(o.display_name)}</button></span>
            <span class="badge cm-art-schild">${esc(cmArtName(o.deal))}</span>
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
                     zustand: o.condition || "", art: o.deal || "tausch" };
      card.addEventListener("click", (ev) => {
        if (ev.target.closest("a, .card-img")) return;
        const wer = ev.target.closest("[data-profil]");
        if (wer) { openProfil(wer.dataset.profil); return; }
        openOffer(data);
      });
    });
  } catch (e) {
    box.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}


/* ----------------------------------------- Community: Entdecken und Profile

   **Ausgerechnet wird auf dieser Instanz.** `/api/hub/entdecken` vergleicht
   die eigene Wunschliste mit den Angeboten im Hub und das eigene Abgebbare
   mit den gezeigten Wunschlisten der anderen. Die eigene Wunschliste geht
   dafür nicht hinaus – erst, wenn jemand „Wunschliste zeigen" einschaltet.

   Alles hier ist optional: Ohne Beitritt per Einladung ist der Tab gar
   nicht da, und jedes Profilfeld darf leer bleiben. */

const THEMEN_ERSATZ = ["Star Wars", "City", "Super Heroes", "Ninjago",
  "Harry Potter", "Castle", "Collectible Minifigures", "Friends", "Town",
  "Space", "Pirates", "Jurassic World", "Disney", "Creator"];
let communityThemen = null;          // aus dem Katalog, einmal je Sitzung
let hubIch = null;                   // { member_id, display_name }
let meinProfil = null;               // zuletzt geladenes eigenes Profil

function avatarText(name) {
  return ((name || "").trim().charAt(0) || "?").toUpperCase();
}

function cmBild(x) { return x.img_data ? x.img_data : imgSrc(x.img_url, true); }

/* So rundet auch der Hub – die Vorschau zeigt, was andere sehen werden. */
function cmGerundet(n) {
  const z = Math.max(0, Math.floor(Number(n) || 0));
  if (z < 10) return z;
  if (z < 100) return Math.round(z / 10) * 10;
  if (z < 1000) return Math.round(z / 50) * 50;
  return Math.round(z / 100) * 100;
}

async function communityThemenLaden() {
  if (communityThemen) return communityThemen;
  try {
    const d = await api("/katalog/liste/themen");
    const liste = (d.themen || []).map((t) =>
      ({ name: t.thema, besitz: t.besitz || 0, anzahl: t.anzahl || 0 }));
    communityThemen = liste.length ? liste
      : THEMEN_ERSATZ.map((n) => ({ name: n, besitz: 0, anzahl: 0 }));
  } catch (_) {
    communityThemen = THEMEN_ERSATZ.map((n) => ({ name: n, besitz: 0, anzahl: 0 }));
  }
  // Was man selbst am meisten hat, zuerst – das sind die naheliegenden.
  communityThemen.sort((a, b) => (b.besitz - a.besitz) || (b.anzahl - a.anzahl));
  return communityThemen;
}

/* Tausch, Verkauf oder beides. Fehlt die Angabe (ältere Instanzen), ist es
   ein Tausch – so war jedes Angebot gemeint, bevor es die Wahl gab. */
function cmArtName(art) {
  if (art === "verkauf") return tr("💶 Verkauf");
  if (art === "beides") return tr("🔄 Tausch · 💶 Verkauf");
  return tr("🔄 Tausch");
}

let hubArtFilter = "";               // "" | "tausch" | "verkauf"

function cmArtPasst(art) {
  const a = art || "tausch";
  return !hubArtFilter || a === hubArtFilter || a === "beides";
}

function cmName(id, name) {
  return `<button type="button" class="cm-name" data-profil="${esc(id)}">${esc(name || "?")}</button>`;
}

function cmZustand(c) {
  return c ? " · " + (c === "new" ? tr("Neu") : tr("Gebraucht")) : "";
}

async function loadEntdecken() {
  const box = $("hub-entdecken");
  box.innerHTML = brickLoading(tr("Suche Passendes im Netzwerk …"));
  let d, laufend = new Map();
  try {
    const [e, t] = await Promise.all([
      api("/hub/entdecken"),
      api("/hub/trades").catch(() => ({ trades: [] })),
    ]);
    d = e;
    laufend = new Map((t.trades || []).map((x) => [offerKey(x.other_id, x.item_id), x]));
  } catch (e) {
    box.innerHTML = `<p class="error">${esc(e.message)}</p>`;
    return;
  }
  const teile = [];

  teile.push(`<div class="cm-abschnitt">⭐ ${esc(tr("Hat, was du suchst"))}
    <small>${d.hat.length ? esc(tr("{n} Treffer", { n: d.hat.length })) : ""}</small></div>`);
  if (!d.wuensche_anzahl) {
    teile.push(`<div class="cm-leer">${esc(tr("Deine Wunschliste ist leer. Merk dir Figuren mit ☆ – dann sucht Entdecken im Netzwerk danach."))}</div>`);
  } else if (!d.hat.length) {
    teile.push(`<div class="cm-leer">${esc(tr("Gerade bietet niemand etwas von deiner Wunschliste an."))}</div>`);
  } else {
    d.hat.forEach((h, i) => {
      const lauf = laufend.get(offerKey(h.member_id, h.item_id));
      teile.push(`<div class="cm-karte">
        <img src="${cmBild(h)}" alt="" loading="lazy">
        <div class="cm-mitte"><strong>${esc(h.name)}</strong>
          <div class="sub">${esc(h.item_id)}${cmZustand(h.condition)} · ${esc(cmArtName(h.deal))} · ${esc(tr("von"))} ${cmName(h.member_id, h.display_name)}</div></div>
        <button class="mini-btn add" data-cm-hat="${i}">${lauf ? "💬 " + esc(tr("Gespräch")) : "💬 " + esc(tr("Anfragen"))}</button>
      </div>`);
    });
  }

  teile.push(`<div class="cm-abschnitt">🔄 ${esc(tr("Sucht, was du übrig hast"))}
    <small>${d.sucht.length ? esc(tr("{n} Treffer", { n: d.sucht.length })) : ""}</small></div>`);
  d.sucht.forEach((w, i) => {
    teile.push(`<div class="cm-karte">
      <img src="${cmBild(w)}" alt="" loading="lazy">
      <div class="cm-mitte"><strong>${esc(w.name)}</strong>
        <div class="sub">${esc(w.item_id)} · ${esc(tr("du hast {n}× übrig", { n: w.hier_abgebbar }))} · ${esc(tr("sucht"))} ${cmName(w.member_id, w.display_name)}</div></div>
      <button class="mini-btn" data-cm-sucht="${i}">🤝 ${esc(tr("Anbieten"))}</button>
    </div>`);
  });
  if (!d.sucht.length) {
    teile.push(`<div class="cm-leer">${esc(tr("Niemand, der seine Wunschliste zeigt, sucht gerade etwas, das du übrig hast."))}</div>`);
  }
  if (!d.wuensche_zeigen) {
    teile.push(`<div class="cm-leer">${esc(tr("Nur wer seine Wunschliste zeigt, taucht hier auf. Deine ist nicht sichtbar."))}
      <button type="button" class="link-btn" data-cm-profil-bearbeiten>${esc(tr("Mein Profil"))}</button></div>`);
  }

  teile.push(`<div class="cm-abschnitt">🧩 ${esc(tr("Passt zu dir"))} <small>${esc(tr("gleiche Lieblingsthemen"))}</small></div>`);
  if (!d.meine_themen.length) {
    teile.push(`<div class="cm-leer">${esc(tr("Trag Lieblingsthemen ein, dann zeigt Entdecken, wer zu dir passt."))}
      <button type="button" class="link-btn" data-cm-profil-bearbeiten>${esc(tr("Mein Profil"))}</button></div>`);
  } else if (!d.passt.length) {
    teile.push(`<div class="cm-leer">${esc(tr("Noch niemand mit denselben Lieblingsthemen."))}</div>`);
  } else {
    d.passt.forEach((p) => {
      const zeile = [p.gemeinsam.join(" · ")];
      if (p.region) zeile.push(p.region);
      zeile.push(tr("{n} Angebote", { n: p.offers || 0 }));
      teile.push(`<div class="cm-karte">
        <span class="cm-avatar klein">${esc(avatarText(p.display_name))}</span>
        <div class="cm-mitte">${cmName(p.member_id, p.display_name)}
          <div class="sub">${esc(zeile.join(" · "))}</div></div>
        <button class="mini-btn" data-profil="${esc(p.member_id)}">${esc(tr("Profil"))}</button>
      </div>`);
    });
  }
  box.innerHTML = teile.join("");

  box.querySelectorAll("[data-cm-hat]").forEach((b) => {
    b.addEventListener("click", () => {
      const h = d.hat[Number(b.dataset.cmHat)];
      openOffer({ m: h.member_id, i: h.item_id, n: h.name, who: h.display_name,
        img: h.img_data || h.img_url, id_: h.item_id, typ: h.item_type || "",
        bild: h.img_url || "", bl: "", zustand: h.condition || "", art: h.deal || "tausch" });
    });
  });
  box.querySelectorAll("[data-cm-sucht]").forEach((b) => {
    b.addEventListener("click", () => cmAnbieten(d.sucht[Number(b.dataset.cmSucht)]));
  });
  box.querySelectorAll("[data-profil]").forEach((b) => {
    b.addEventListener("click", () => openProfil(b.dataset.profil));
  });
  box.querySelectorAll("[data-cm-profil-bearbeiten]").forEach((b) => {
    b.addEventListener("click", openMeinProfil);
  });
}

/* Jemandem etwas anbieten, das er sucht: dasselbe Gespräch wie bei einer
   Anfrage, nur mit passendem Vorschlag im Feld. */
function cmAnbieten(w) {
  openInterest({ m: w.member_id, i: w.item_id, n: w.name, who: w.display_name,
    img: w.img_url, id_: w.item_id, typ: w.item_type || "", bild: w.img_url || "",
    bl: "", zustand: "", kind: "angebot" },
  tr("Hallo {name}, du suchst den {was} – ich hätte einen abzugeben. Interesse?",
    { name: w.display_name, was: w.name }));
}

/* ------------------------------------------------------------ Profil ansehen */

function closeProfil() {
  $("profil-overlay").hidden = true;
  document.body.style.overflow = "";
}

async function openProfil(memberId) {
  const box = $("profil-inhalt");
  box.innerHTML = brickLoading(tr("Profil wird geladen …"));
  $("profil-overlay").hidden = false;
  document.body.style.overflow = "hidden";
  let p;
  try { p = await api("/hub/profil/" + encodeURIComponent(memberId)); }
  catch (e) { box.innerHTML = `<p class="error">${esc(e.message)}</p>`; return; }
  const eigen = hubIch && p.member_id === hubIch.member_id;
  const seit = p.created_at ? new Date(p.created_at * 1000)
    .toLocaleDateString(dateLocale(), { month: "long", year: "numeric" }) : "";
  const unterzeile = [seit ? tr("Mitglied seit {wann}", { wann: seit }) : ""];
  if (p.region) unterzeile.push("📍 " + p.region);
  const zahlen = [
    `<div class="cm-zahl"><b>${p.stats ? p.stats.offers : 0}</b><span>${esc(tr("Angebote"))}</span></div>`,
    `<div class="cm-zahl"><b>${p.stats ? p.stats.trades : 0}</b><span>${esc(tr("Tausche"))}</span></div>`,
  ];
  if (p.collection_count != null) {
    zahlen.push(`<div class="cm-zahl"><b>≈ ${p.collection_count}</b><span>${esc(tr("Figuren"))}</span></div>`);
  }
  const bilder = (liste, markiere) => `<div class="cm-bilder">${liste.map((x, i) =>
    `<button type="button" class="cm-bild${markiere(x) ? " an" : ""}" data-i="${i}" title="${esc(x.name)} (${esc(x.item_id)})${x.deal ? " · " + esc(cmArtName(x.deal)) : ""}">
      <img src="${cmBild(x)}" alt="" loading="lazy"></button>`).join("")}</div>`;
  const angebote = p.offers || [];
  const wuensche = p.wants || [];
  const passend = wuensche.filter((w) => w.hier_abgebbar > 0);
  box.innerHTML = `
    <div class="cm-kopf"><span class="cm-avatar">${esc(avatarText(p.display_name))}</span>
      <div><h3>${esc(p.display_name)}</h3>
        <div class="sub">${esc(unterzeile.filter(Boolean).join(" · "))}</div></div></div>
    ${p.about ? `<p class="cm-ueber">${esc(p.about)}</p>` : ""}
    ${p.themes && p.themes.length ? `<div class="cm-chips">${p.themes.map((t) =>
      `<span class="cm-chip an">${esc(t)}</span>`).join("")}</div>` : ""}
    <div class="cm-zahlen">${zahlen.join("")}</div>
    ${angebote.length ? `<div class="cm-abschnitt">📤 ${esc(tr("Bietet an"))}</div>
      ${bilder(angebote, (o) => o.auf_wunschliste)}
      ${angebote.some((o) => o.auf_wunschliste) ? `<p class="search-hint">⭐ ${esc(tr("gelb umrandet: steht auf deiner Wunschliste"))}</p>` : ""}` : ""}
    ${wuensche.length ? `<div class="cm-abschnitt">⭐ ${esc(tr("Sucht"))}</div>
      ${bilder(wuensche, (w) => w.hier_abgebbar > 0)}
      ${passend.length ? `<p class="search-hint">🔄 ${esc(tr("{n} davon hast du übrig", { n: passend.length }))}</p>
        <div class="card-actions scan-tasten cm-anbieten">${passend.slice(0, 3).map((w, i) =>
          `<button class="mini-btn add" data-cm-biete="${i}">🤝 ${esc(tr("{nr} anbieten", { nr: w.item_id }))}</button>`).join("")}</div>` : ""}` : ""}
    ${eigen ? `<div class="card-actions scan-tasten" style="margin-top:12px">
      <button class="mini-btn" data-cm-profil-bearbeiten>✏️ ${esc(tr("Bearbeiten"))}</button></div>` : ""}`;

  box.querySelectorAll(".cm-bilder").forEach((reihe, r) => {
    const liste = r === 0 && angebote.length ? angebote : wuensche;
    reihe.querySelectorAll(".cm-bild").forEach((b) => {
      const x = liste[Number(b.dataset.i)];
      b.addEventListener("click", () => {
        if (eigen) return;
        if (liste === angebote) {
          closeProfil();
          openOffer({ m: p.member_id, i: x.item_id, n: x.name, who: p.display_name,
            img: x.img_data || x.img_url, id_: x.item_id, typ: x.item_type || "",
            bild: x.img_url || "", bl: "", zustand: x.condition || "", art: x.deal || "tausch" });
        } else if (x.hier_abgebbar > 0) {
          closeProfil();
          cmAnbieten({ ...x, member_id: p.member_id, display_name: p.display_name });
        }
      });
    });
  });
  box.querySelectorAll("[data-cm-biete]").forEach((b) => {
    b.addEventListener("click", () => {
      const w = passend[Number(b.dataset.cmBiete)];
      closeProfil();
      cmAnbieten({ ...w, member_id: p.member_id, display_name: p.display_name });
    });
  });
  box.querySelectorAll("[data-cm-profil-bearbeiten]").forEach((b) => {
    b.addEventListener("click", () => { closeProfil(); openMeinProfil(); });
  });
}

/* ------------------------------------------------------------- Mein Profil */

/* Die Felder, aus denen Profil-Fenster und Planer ihre Schritte bauen.
   `teile` wählt aus: about, region, themen, sichtbar. */
function cmFelder(p, themen, teile, alleThemen = false) {
  const gewaehlt = new Set((p.themes || []).map((t) => t.toLowerCase()));
  const html = [];
  if (teile.includes("about")) {
    html.push(`<label for="cm-about">${esc(tr("Über mich"))}</label>
      <textarea id="cm-about" maxlength="280" rows="3"
        placeholder="${esc(tr("z. B. was du sammelst und wie du am liebsten tauschst"))}">${esc(p.about || "")}</textarea>`);
  }
  if (teile.includes("region")) {
    html.push(`<label for="cm-region">${esc(tr("Gegend"))}</label>
      <input id="cm-region" maxlength="60" value="${esc(p.region || "")}"
        placeholder="${esc(tr("z. B. Raum München – keine Adresse"))}">`);
  }
  if (teile.includes("themen")) {
    // Erst die eigenen Hauptthemen und alles schon Gewählte, der Rest auf Tipp.
    const vorn = themen.filter((t, i) => i < 12 || gewaehlt.has(t.name.toLowerCase()));
    const zeigen = alleThemen ? themen : vorn;
    html.push(`<label>${esc(tr("Lieblingsthemen"))}</label>
      <div class="cm-chips" id="cm-themen">${zeigen.map((t) =>
        `<button type="button" class="cm-chip${gewaehlt.has(t.name.toLowerCase()) ? " an" : ""}"
          data-thema="${esc(t.name)}">${esc(t.name)}</button>`).join("")}
        ${!alleThemen && themen.length > zeigen.length
          ? `<button type="button" class="cm-chip mehr" id="cm-themen-mehr">＋ ${esc(tr("weitere"))}</button>` : ""}</div>`);
  }
  if (teile.includes("sichtbar")) {
    const fig = p.figuren_hier || 0;
    html.push(`<div class="cm-abschnitt">🔒 ${esc(tr("Was andere sehen"))}</div>
      <label class="cm-schalter-zeile"><input type="checkbox" class="cm-schalter" id="cm-wuensche"${p.wants_public ? " checked" : ""}>
        <span><b>${esc(tr("Meine Wunschliste im Netzwerk zeigen"))}</b>
        <small>${esc(tr("Dann sehen andere, was du suchst – und dir wird angezeigt, wer deine Doppelten sucht. Nur Nummer, Name und Bild."))}</small></span></label>
      <label class="cm-schalter-zeile"><input type="checkbox" class="cm-schalter" id="cm-sammlung"${p.show_collection ? " checked" : ""}>
        <span><b>${esc(tr("Sammlungsgröße zeigen"))}</b>
        <small>${esc(tr("Gerundet – bei dir wären das „≈ {n} Figuren“.", { n: cmGerundet(fig) }))}</small></span></label>`);
  }
  return html.join("");
}

/* Liest aus, was gerade in den Feldern steht – und lässt weg, was es im
   aktuellen Schritt nicht gibt (dann gilt der bisherige Stand). */
function cmFelderLesen(p) {
  const neu = { about: p.about || "", region: p.region || "",
    themes: p.themes || [], wants_public: !!p.wants_public,
    show_collection: !!p.show_collection };
  if ($("cm-about")) neu.about = $("cm-about").value.trim();
  if ($("cm-region")) neu.region = $("cm-region").value.trim();
  if ($("cm-themen")) {
    neu.themes = [...document.querySelectorAll("#cm-themen .cm-chip.an")]
      .map((b) => b.dataset.thema);
  }
  if ($("cm-wuensche")) neu.wants_public = $("cm-wuensche").checked;
  if ($("cm-sammlung")) neu.show_collection = $("cm-sammlung").checked;
  return neu;
}

function cmThemenVerdrahten(wurzel, p, themen, neuZeichnen) {
  wurzel.querySelectorAll("#cm-themen .cm-chip[data-thema]").forEach((b) => {
    b.addEventListener("click", () => b.classList.toggle("an"));
  });
  const mehr = wurzel.querySelector("#cm-themen-mehr");
  if (mehr) {
    mehr.addEventListener("click", () => {
      // Gewähltes behalten, dann mit allen Themen neu zeichnen.
      p.themes = [...wurzel.querySelectorAll("#cm-themen .cm-chip.an")]
        .map((x) => x.dataset.thema);
      neuZeichnen(true);
    });
  }
}

function closeMeinProfil() {
  $("meinprofil-overlay").hidden = true;
  document.body.style.overflow = "";
}

async function openMeinProfil() {
  const box = $("meinprofil-felder");
  $("meinprofil-fehler").hidden = true;
  box.innerHTML = brickLoading(tr("Profil wird geladen …"));
  $("meinprofil-overlay").hidden = false;
  document.body.style.overflow = "hidden";
  try {
    const [p, themen] = await Promise.all([api("/hub/profil"), communityThemenLaden()]);
    meinProfil = p;
    const zeichnen = (alle = false) => {
      box.innerHTML = cmFelder(meinProfil, themen,
        ["about", "region", "themen", "sichtbar"], alle);
      cmThemenVerdrahten(box, meinProfil, themen, zeichnen);
    };
    zeichnen();
  } catch (e) {
    box.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

async function meinProfilSpeichern() {
  if (!meinProfil) return;
  const b = $("meinprofil-speichern");
  b.disabled = true;
  try {
    meinProfil = await api("/hub/profil", { method: "PUT",
      body: cmFelderLesen(meinProfil) });
    closeMeinProfil();
    toast(tr("Profil gespeichert ✔"));
    if (hubTab === "entdecken" && !$("view-hub").hidden) loadEntdecken();
  } catch (e) {
    $("meinprofil-fehler").textContent = e.message;
    $("meinprofil-fehler").hidden = false;
  } finally { b.disabled = false; }
}

/* ------------------------------------------- Einrichtungsplaner (Beitritt)

   Startet direkt nach dem Beitritt per Einladung. „Beitreten" ist dann
   schon erledigt; die übrigen fünf Schritte sind alle überspringbar und
   später unter „Mein Profil" änderbar. Gespeichert wird nach jedem Schritt –
   wer mittendrin aufhört, verliert nichts. */
const PLANER_SCHRITTE = [
  { key: "beitreten", titel: "Beitreten" },
  { key: "ueber", titel: "Über dich" },
  { key: "themen", titel: "Themen" },
  { key: "sichtbar", titel: "Sichtbarkeit" },
  { key: "angebote", titel: "Angebote" },
  { key: "los", titel: "Los" },
];
let planerSchritt = 1;
let planerProfil = null;
let planerThemen = [];
let planerWired = false;

async function communityPlanerStarten() {
  planerSchritt = 1;
  $("planer-overlay").hidden = false;
  document.body.style.overflow = "hidden";
  if (!planerWired) {
    planerWired = true;
    $("planer-weiter").addEventListener("click", () => planerWeiter(true));
    $("planer-ueberspringen").addEventListener("click", () => planerWeiter(false));
    $("planer-zurueck").addEventListener("click", () => {
      if (planerSchritt > 1) { planerSchritt -= 1; planerZeigen(); }
    });
    $("planer-spaeter").addEventListener("click", planerSchliessen);
  }
  $("planer-inhalt").innerHTML = brickLoading(tr("Einen Moment …"));
  try {
    [planerProfil, planerThemen] = await Promise.all([
      api("/hub/profil"), communityThemenLaden()]);
  } catch (e) {
    // Ein Hub ohne Profile (vor 1.12.0): dann gibt es hier nichts einzurichten.
    planerSchliessen();
    toast(e.message);
    return;
  }
  planerZeigen();
}

function planerSchliessen() {
  $("planer-overlay").hidden = true;
  document.body.style.overflow = "";
}

function planerZeigen() {
  const s = PLANER_SCHRITTE[planerSchritt];
  $("planer-schritt").textContent = tr("Schritt {n} von {max}",
    { n: planerSchritt + 1, max: PLANER_SCHRITTE.length });
  $("planer-leiste").innerHTML = PLANER_SCHRITTE.map((x, i) =>
    `<span class="cm-chip${i < planerSchritt ? " an" : ""}${i === planerSchritt ? " jetzt" : ""}">${i < planerSchritt ? "✔ " : ""}${esc(tr(x.titel))}</span>`).join("");
  $("planer-fehler").hidden = true;
  $("planer-zurueck").hidden = planerSchritt <= 1;
  const letzter = s.key === "los";
  $("planer-ueberspringen").hidden = letzter;
  $("planer-weiter").textContent = letzter ? tr("Zum Entdecken") : tr("Weiter");
  const box = $("planer-inhalt");
  if (s.key === "ueber") {
    box.innerHTML = `<h3>👤 ${esc(tr("Über dich"))}</h3>
      <p class="search-hint">${esc(tr("Ein paar Worte für die anderen im Netzwerk – beides darf leer bleiben."))}</p>
      ${cmFelder(planerProfil, planerThemen, ["about", "region"])}`;
  } else if (s.key === "themen") {
    const zeichnen = (alle = false) => {
      box.innerHTML = `<h3>🧩 ${esc(tr("Lieblingsthemen"))}</h3>
        <p class="search-hint">${esc(tr("Vorne stehen die Themen, von denen du am meisten hast. Damit findet Entdecken, wer zu dir passt."))}</p>
        ${cmFelder(planerProfil, planerThemen, ["themen"], alle)}`;
      cmThemenVerdrahten(box, planerProfil, planerThemen, zeichnen);
    };
    zeichnen();
  } else if (s.key === "sichtbar") {
    box.innerHTML = `<h3>🔒 ${esc(tr("Was andere sehen"))}</h3>
      <p class="search-hint">${esc(tr("Beides ist aus, solange du es nicht einschaltest. Deine Sammlung selbst sieht niemand – nur, was du ausdrücklich teilst."))}</p>
      ${cmFelder(planerProfil, planerThemen, ["sichtbar"]).replace(/<div class="cm-abschnitt">.*?<\/div>/, "")}`;
  } else if (s.key === "angebote") {
    const admin = state.user && state.user.is_admin;
    box.innerHTML = `<h3>📤 ${esc(tr("Was du anbietest"))}</h3>
      <p class="search-hint">${esc(tr("Andere sehen nur, was du ausdrücklich anbietest. Am schnellsten geht das mit deinen Doppelten."))}</p>
      ${admin ? `<div class="card-actions scan-tasten"><button class="mini-btn add" id="planer-doppelte">➕ ${esc(tr("Doppelte übernehmen und veröffentlichen"))}</button></div>
        <p class="search-hint" id="planer-doppelte-out" hidden></p>`
        : `<p class="search-hint">${esc(tr("Veröffentlichen darf auf dieser Instanz nur ein Admin."))}</p>`}
      <p class="search-hint">${esc(tr("Einzelne Artikel wählst du später in der Sammlung aus: Karte öffnen → „🤝 In der Tauschbörse anbieten“."))}</p>`;
    const k = $("planer-doppelte");
    if (k) {
      k.addEventListener("click", async () => {
        k.disabled = true;
        const out = $("planer-doppelte-out");
        try {
          const r = await api("/share/from_duplicates", { method: "POST" });
          const v = await api("/hub/publish", { method: "POST" });
          out.textContent = tr("Übernommen: {n} · im Netzwerk angeboten: {m} 📤",
            { n: r.added, m: v.count });
        } catch (e) { out.textContent = e.message; k.disabled = false; }
        out.hidden = false;
      });
    }
  } else {
    box.innerHTML = `<h3>🎉 ${esc(tr("Fertig"))}</h3>
      <p class="search-hint">${esc(tr("Unter 🧭 Entdecken siehst du jetzt, wer hat, was du suchst – und wer zu dir passt. Ändern kannst du alles unter „Mein Profil“."))}</p>`;
  }
}

async function planerWeiter(uebernehmen) {
  const s = PLANER_SCHRITTE[planerSchritt];
  if (s.key === "los") {
    planerSchliessen();
    showTab("hub");
    showHubTab("entdecken");
    return;
  }
  if (uebernehmen && ["ueber", "themen", "sichtbar"].includes(s.key)) {
    const b = $("planer-weiter");
    b.disabled = true;
    try {
      planerProfil = await api("/hub/profil", { method: "PUT",
        body: cmFelderLesen(planerProfil) });
    } catch (e) {
      $("planer-fehler").textContent = e.message;
      $("planer-fehler").hidden = false;
      b.disabled = false;
      return;
    }
    b.disabled = false;
  }
  planerSchritt += 1;
  planerZeigen();
}

