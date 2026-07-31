/* Brickfolio – Frontend-Logik */
"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  token: localStorage.getItem("bf_token") || "",
  user: JSON.parse(localStorage.getItem("bf_user") || "null"),
  bricklinkPrices: false,
  catalogSearch: false,
  bricklinkLookup: false,
  // Zuletzt bekannte Währung: Sie steht schon beim ersten Zeichnen fest,
  // sonst blitzten die Beträge kurz in Euro auf, bevor /config antwortet.
  currency: localStorage.getItem("bf_currency") || "EUR",
  collection: [],
};

/* ------------------------------------------------------------- Sprache

   Nachträglich übersetzen, ohne die Oberfläche umzubauen: Der **deutsche
   Text ist der Schlüssel** (wie bei gettext). Das hat drei Folgen, die uns
   hier entgegenkommen:

   - Deutsch braucht keinen Katalog und keine zusätzliche Anfrage. Es ist
     das, was ohnehin im Dokument steht – kein Aufblitzen, kein Umweg.
   - Fehlt eine Übersetzung, erscheint der deutsche Satz. Nie ein nackter
     Schlüssel wie „nav.scan", nie eine leere Stelle.
   - Die 500 Textstellen in index.html mussten nicht angefasst werden.
     `translateTree` läuft einmal über das Dokument und tauscht, was im
     Katalog steht.

   Für Texte, die JavaScript baut, gibt es `tr()`. Platzhalter als {name}. */

const APP_I18N_V = (document.querySelector('meta[name="app-version"]')
  || {}).content || "0";
const LANGS = { de: "Deutsch", en: "English" };
let lang = "de";
let dict = {};                     // deutscher Satz -> Übersetzung

/* Übersetzen. Unbekanntes bleibt deutsch – besser als eine Lücke. */
function tr(text, vars) {
  let out = dict[text] || text;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      out = out.split("{" + k + "}").join(v);
    }
  }
  return out;
}

/* Datum und Uhrzeit in der Schreibweise der gewählten Sprache. */
function dateLocale() { return lang === "en" ? "en-GB" : "de-DE"; }

/* Welche Sprache gilt? Profil zuerst, sonst der Browser, sonst Deutsch. */
function pickLang() {
  const gespeichert = (state.user && state.user.lang)
    || localStorage.getItem("bf_lang");
  if (gespeichert && LANGS[gespeichert]) return gespeichert;
  for (const l of navigator.languages || [navigator.language || "de"]) {
    const kurz = String(l).slice(0, 2).toLowerCase();
    if (LANGS[kurz]) return kurz;
  }
  return "de";
}

async function loadLang(next) {
  lang = next || pickLang();
  localStorage.setItem("bf_lang", lang);
  document.documentElement.lang = lang;
  if (lang === "de") { dict = {}; return; }   // Quellsprache, nichts zu laden
  try {
    const r = await fetch(`/static/i18n/${lang}.json?v=${APP_I18N_V}`);
    dict = r.ok ? await r.json() : {};
  } catch (_) { dict = {}; }
}

/* Diese Attribute tragen ebenfalls sichtbaren Text. */
const I18N_ATTRS = ["placeholder", "title", "aria-label", "alt"];

/* Einmal über einen Teilbaum und alles ersetzen, was im Katalog steht.
   Reine Zahlen, Symbole und Nutzerdaten stehen dort nicht – die bleiben. */
/* Was vor dem Übersetzen dastand. Damit lässt sich zurückschalten, ohne die
   Seite neu zu laden – wichtig beim ersten Start, wo sonst der halb
   ausgefüllte Anmeldebogen verloren ginge. */
const i18nVorher = new Map();

/* Der Speicher oben hält **echte Verweise** auf DOM-Knoten. Wird eine Liste
   neu gezeichnet, sind die alten Knoten aus dem Dokument raus – aus dieser
   Karte aber nicht, und damit bleiben sie im Speicher. Bei tausend Karten und
   jedem Neuzeichnen summiert sich das. Deshalb ab und zu ausmisten: Was nicht
   mehr im Dokument hängt, kann auch nicht mehr zurückgesetzt werden. */
function i18nAufraeumen() {
  if (i18nVorher.size < 3000) return;
  for (const knoten of [...i18nVorher.keys()]) {
    if (knoten !== document && !knoten.isConnected) i18nVorher.delete(knoten);
  }
}

function translateTree(root = document.body) {
  if (lang === "de" || !Object.keys(dict).length) return;

  // Erst ganze Elemente: Ein Satz mit Auszeichnung („… einen <b>Code</b> von
  // jemandem") steht als eine Einheit im Katalog. Würde man nur Textknoten
  // vergleichen, zerfiele er in Bruchstücke – und Bruchstücke wie „und" darf
  // man nie ersetzen.
  //
  // Von außen nach innen, und das ist wesentlich: Übersetzt man erst das
  // innere <b>, passt der Satz des Elternteils nicht mehr auf seinen
  // Schlüssel – der ganze Absatz bliebe deutsch, mit einem einzelnen
  // englischen Wort darin. Der äußere Treffer gewinnt, seine Kinder sind
  // damit erledigt.
  const kandidaten = [root, ...root.querySelectorAll("*")];
  kandidaten.forEach((el) => {
    if (el.dataset.i18nDone) return;
    const inhalt = el.innerHTML.replace(/\s+/g, " ").trim();
    if (!inhalt || !dict[inhalt]) return;
    if (!i18nVorher.has(el)) i18nVorher.set(el, ["html", el.innerHTML]);
    el.innerHTML = dict[inhalt];
    el.dataset.i18nDone = "1";
    el.querySelectorAll("*").forEach((k) => { k.dataset.i18nDone = "1"; });
  });

  // Danach der Rest: einzelne Textknoten ohne umgebende Auszeichnung.
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const treffer = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (n.parentElement && n.parentElement.dataset.i18nDone) continue;
    const roh = n.nodeValue;
    const kern = roh.trim();
    if (kern.length < 2) continue;
    // Zeilenumbrüche im Quelltext sind Einrückung, kein Text: Ein Satz, der
    // in der Vorlage über zwei Zeilen läuft, soll denselben Schlüssel haben
    // wie derselbe Satz in einer Zeile.
    const wert = dict[kern] || dict[kern.replace(/\s+/g, " ")];
    if (!wert) continue;
    treffer.push([n, roh.replace(kern, wert)]);
  }
  treffer.forEach(([n, wert]) => {
    if (!i18nVorher.has(n)) i18nVorher.set(n, ["text", n.nodeValue]);
    n.nodeValue = wert;
  });

  i18nAufraeumen();

  root.querySelectorAll("*").forEach((el) => {
    I18N_ATTRS.forEach((a) => {
      const v = el.getAttribute(a);
      if (!v || !dict[v.trim()]) return;
      const merker = el.dataset.i18nAttr ? el.dataset.i18nAttr.split("|") : [];
      if (!merker.includes(a)) {
        el.setAttribute("data-i18n-" + a, v);
        el.dataset.i18nAttr = merker.concat(a).join("|");
      }
      el.setAttribute(a, dict[v.trim()]);
    });
  });
  // Der Titel des Fensters gehört auch dazu.
  if (root === document.body && dict[document.title]) {
    if (!i18nVorher.has(document)) {
      i18nVorher.set(document, ["title", document.title]);
    }
    document.title = dict[document.title];
  }
}

/* Alles auf den deutschen Stand zurücksetzen – die Quellsprache steht ja
   nirgends geschrieben, sie ist das, was vorher dastand. */
function restoreLang() {
  i18nVorher.forEach(([art, wert], knoten) => {
    if (art === "html") knoten.innerHTML = wert;
    else if (art === "text") knoten.nodeValue = wert;
    else if (art === "title") document.title = wert;
  });
  i18nVorher.clear();
  document.querySelectorAll("[data-i18n-done]").forEach((el) => {
    delete el.dataset.i18nDone;
  });
  document.querySelectorAll("[data-i18n-attr]").forEach((el) => {
    el.dataset.i18nAttr.split("|").forEach((a) => {
      const alt = el.getAttribute("data-i18n-" + a);
      if (alt !== null) { el.setAttribute(a, alt); }
      el.removeAttribute("data-i18n-" + a);
    });
    delete el.dataset.i18nAttr;
  });
}

/* Sprache im laufenden Betrieb wechseln, ohne neu zu laden. */
async function switchLang(pick) {
  if (pick === lang) return;
  if (i18nBeobachter) { i18nBeobachter.disconnect(); i18nBeobachter = null; }
  restoreLang();
  await loadLang(pick);
  translateTree(document.body);
  watchForTranslation();
}

/* Neu gezeichnete Listen mitnehmen.

   Die Oberfläche baut ihre Karten an 92 Stellen per innerHTML zusammen.
   Jede einzeln anzufassen wäre fehleranfällig und ginge bei der nächsten
   neuen Ansicht wieder vergessen. Stattdessen beobachten wir, was dazukommt,
   und übersetzen genau diesen Teilbaum – das gilt dann auch für Code, den es
   heute noch nicht gibt.

   Während des Übersetzens hört der Beobachter weg: translateTree ändert ja
   selbst den Baum und würde sich sonst endlos wiederholen. */
let i18nBeobachter = null;

function watchForTranslation() {
  if (lang === "de" || i18nBeobachter || !window.MutationObserver) return;
  const optionen = { childList: true, subtree: true };
  i18nBeobachter = new MutationObserver((aenderungen) => {
    const neu = [];
    aenderungen.forEach((a) => a.addedNodes.forEach((n) => {
      if (n.nodeType === 1) neu.push(n);
    }));
    if (!neu.length) return;
    i18nBeobachter.disconnect();
    try { neu.forEach((el) => translateTree(el)); }
    finally { i18nBeobachter.observe(document.body, optionen); }
  });
  i18nBeobachter.observe(document.body, optionen);
}

/* ---------------------------------------------------------------- API */
/* Die Prüfung der Eingaben macht die Bibliothek im Server, und die schreibt
   englisch: „Field required", „String should have at least 1 character".
   Ungefiltert stand das mitten im deutschen Satz – halb deutsch, halb
   englisch. Hier wird ein deutscher Satz daraus, der dann wie jeder andere
   durch die Übersetzung geht. */
const PRUEF_TEXTE = [
  [/^Field required$/, "Da fehlt eine Angabe"],
  [/^Input should be a valid integer/, "Hier gehört eine ganze Zahl hin"],
  [/^Input should be a valid number/, "Hier gehört eine Zahl hin"],
  [/^Input should be greater than or equal to (\d+)/, "Der Wert ist zu klein"],
  [/^Input should be less than or equal to (\d+)/, "Der Wert ist zu groß"],
  [/^String should have at least (\d+) character/, "Der Text ist zu kurz"],
  [/^String should have at most (\d+) character/, "Der Text ist zu lang"],
  [/^String should match pattern/, "Das passt nicht ins vorgegebene Format"],
  [/^Value error/, "Der Wert passt nicht"],
];

function pruefText(msg) {
  if (!msg) return "";
  for (const [muster, satz] of PRUEF_TEXTE) {
    if (muster.test(msg)) return tr(satz);
  }
  return msg;                    // Unbekanntes lieber im Original zeigen
}

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (state.token) headers["Authorization"] = "Bearer " + state.token;
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }
  let resp;
  try {
    resp = await fetch("/api" + path, { ...options, headers });
  } catch (_) {
    // Kein Netz, Server aus, NAS im Schlaf, Update läuft: `fetch` wirft dann
    // „Failed to fetch" – englisch, technisch, und das stand bisher als
    // ganzer Inhalt in der Statistik. Hier wird ein Satz daraus, den man
    // auch versteht.
    throw new Error(tr("Keine Verbindung zur Instanz. Läuft der Server, "
      + "und ist das Gerät im richtigen Netz?"));
  }
  let data = {};
  const roh = await resp.text();
  if (roh) {
    try {
      data = JSON.parse(roh);
    } catch (_) {
      // Antwort kam an, ist aber keine von uns. Typischer Fall: Zwischen App
      // und Instanz sitzt ein Zugangsschutz (Cloudflare Access) oder ein
      // Zwischenserver, der seine eigene Seite ausliefert – mit Status 200.
      // Ungeprüft wurde daraus ein leeres Objekt, die Oberfläche baute auf
      // Nichts weiter und fiel erst viel später über ein fehlendes Element.
      if (resp.ok) {
        throw new Error(tr("Unerwartete Antwort von der Instanz – dazwischen "
          + "sitzt etwas, das eine Anmeldung verlangt. Bitte neu laden."));
      }
    }
  }
  // Fehlertexte gleich hier übersetzen, nicht erst beim Anzeigen: Sie landen
  // an gut einem Dutzend Stellen – in Kurzmeldungen, in Fehlerzeilen, in
  // leeren Listen. Der Server schickt den deutschen Satz, und der ist der
  // Schlüssel.
  // Ein 401 bedeutet normalerweise „Sitzung abgelaufen" – dann abmelden.
  // Bei den Anmeldewegen selbst heißt es dagegen nur „falsche Eingabe";
  // dort abzumelden würde einen Tippfehler im Einmalcode zum Rauswurf aus
  // dem ganzen Vorgang machen.
  if (resp.status === 401 && !path.startsWith("/login")) {
    logout();
    throw new Error(tr(data.detail || "Bitte neu anmelden"));
  }
  if (!resp.ok) {
    // Bei Eingabefehlern schickt der Server eine Liste von Einzelfehlern statt
    // eines Satzes. Ungeprüft stünde dort „[object Object]" – lieber ein
    // verständlicher Satz mit dem Grund, sofern einer dabei ist.
    const d = data.detail;
    let text;
    if (typeof d === "string" && d) text = tr(d);
    else if (Array.isArray(d) && d.length) {
      const grund = d.map((f) => pruefText(f && f.msg)).filter(Boolean).join("; ");
      text = grund ? tr("Eingabe nicht gültig: {grund}", { grund })
        : tr("Eingabe nicht gültig");
    } else text = tr("Fehler {code}", { code: resp.status });
    throw new Error(text);
  }
  return data;
}

/* ---------------------------------------------------------------- UI-Helfer */
let toastTimer;
function toast(msg) {
  const el = $("toast");
  // Hier zentral übersetzen: Die rund 200 Aufrufstellen übergeben den
  // deutschen Satz – und der ist ja der Schlüssel. Meldungen, in die Zahlen
  // eingesetzt werden, rufen tr() selbst auf und kommen fertig hier an.
  el.textContent = tr(msg);
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 2600);
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const IMG_PLACEHOLDER = "data:image/svg+xml;utf8," + encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 72">
     <rect x="12" y="26" width="48" height="30" rx="5" fill="#FFCF00" stroke="#1D1D1B" stroke-width="3"/>
     <rect x="20" y="16" width="12" height="10" rx="3" fill="#FFCF00" stroke="#1D1D1B" stroke-width="3"/>
     <rect x="40" y="16" width="12" height="10" rx="3" fill="#FFCF00" stroke="#1D1D1B" stroke-width="3"/>
   </svg>`);

/* Woher ein Bild kommt.

   Fremde Adressen laufen über die eigene Instanz: Die holt das Bild einmal,
   legt es ab und liefert es fortan selbst. Der Browser fragt damit nie bei
   BrickLink, Rebrickable oder Brickognize an – die erfahren also nicht, wer
   hier gerade welche Figur ansieht. Eigene Uploads und Daten-URLs bleiben,
   wie sie sind. Klappt der Abruf nicht, antwortet die Instanz mit 404, und
   der Platzhalter springt ein. */
function imgSrc(url) {
  if (!url) return IMG_PLACEHOLDER;
  if (/^(https?:)?\/\//.test(url)) {
    return esc("/catalog?u=" + encodeURIComponent(url));
  }
  return esc(url);
}

/* Drehender Klemmbaustein als Lade-Anzeige. */
function brickSpinner(label, size = 46) {
  return `<svg class="spinner-brick" viewBox="0 0 48 48" width="${size}"`
    + ` height="${size}" role="status" aria-label="${esc(label)}"`
    + ' xmlns="http://www.w3.org/2000/svg">'
    + '<g stroke="var(--ink)" stroke-width="2" stroke-linejoin="round">'
    + '<rect x="11" y="15" width="6" height="9" rx="2" fill="var(--yellow)"/>'
    + '<rect x="21" y="15" width="6" height="9" rx="2" fill="var(--yellow)"/>'
    + '<rect x="31" y="15" width="6" height="9" rx="2" fill="var(--yellow)"/>'
    + '<rect x="8" y="22" width="32" height="14" rx="3" fill="var(--yellow)"/>'
    + "</g></svg>";
}

/* Ganzer Lade-Block: Baustein plus Text, wie in der Sammlung. */
function brickLoading(text) {
  return `<div class="list-loading">${brickSpinner(text)}`
    + `<span>${esc(text)}</span></div>`;
}

/* Für <img>: lädt die Quelle nicht (404, offline), zeigt den Platzhalter
   statt eines kaputten Bildsymbols. */
/* Bild kaputt oder blockiert? Dann den Platzhalter zeigen.

   Früher stand dafür ein `onerror="…"` im Markup. Das war ein Fehler: Die
   Sicherheits-Regeln der App verbieten Skript in Attributen (`script-src
   'self'`), der Browser führte es also nie aus – ein fehlgeschlagenes Bild
   blieb als zerbrochenes Symbol stehen. Ein einziger Lauscher am Dokument
   erledigt es für *alle* Bilder: `error` steigt zwar nicht auf, lässt sich
   aber auf dem Weg nach unten abfangen. */
document.addEventListener("error", (ev) => {
  const el = ev.target;
  if (el && el.tagName === "IMG" && el.getAttribute("src") !== IMG_PLACEHOLDER) {
    el.src = IMG_PLACEHOLDER;
  }
}, true);

/* Geldbeträge in der eingestellten Währung. BrickLink liefert die Preise
   bereits umgerechnet, hier wird also nur noch geschrieben – kein eigener
   Kurs, keine zweite Quelle, nichts, was veralten könnte. */
function fmtEur(value) {
  const w = state.currency || "EUR";
  try {
    return Number(value).toLocaleString(dateLocale(),
      { style: "currency", currency: w });
  } catch (_) {
    return Number(value).toFixed(2) + " " + w;
  }
}

/* Nur das Zeichen – für Eingabefelder („Bezahlt €"), wo der Betrag daneben
   steht und nicht mitformatiert wird. */
function curSymbol() {
  const w = state.currency || "EUR";
  try {
    const s = (0).toLocaleString(dateLocale(), { style: "currency",
      currency: w, minimumFractionDigits: 0, maximumFractionDigits: 0 });
    return s.replace(/[0-9\s\u00a0.,]/g, "") || w;
  } catch (_) { return w; }
}

/* Währung merken und alles nachziehen, was schon gezeichnet ist. */
function setCurrency(w) {
  const neu = w || "EUR";
  const anders = neu !== state.currency;
  state.currency = neu;
  localStorage.setItem("bf_currency", neu);
  applyCurrency();
  return anders;
}

/* Zeichen überall nachziehen, wo es fest im Dokument steht. Läuft nach dem
   Laden der Einstellungen und nach jedem Wechsel. */
function applyCurrency() {
  const z = curSymbol();
  document.querySelectorAll("[data-cur]").forEach((el) => {
    if (el.firstChild && el.firstChild.nodeType === 3) {
      el.firstChild.nodeValue = el.firstChild.nodeValue.replace(/\S+/, z);
    } else {
      el.textContent = z;
    }
  });
  const paid = document.querySelector('label[for="m-paid"]');
  if (paid) paid.textContent = tr("Bezahlt {cur} (optional)", { cur: z });
}

/* Preisgebiete → Flagge/Name. Stammt ein Ø-Preis nicht aus dem eingestellten
   Gebiet (weil es dort keine Verkäufe gab), zeigt eine Flagge das Gebiet, aus
   dem er wirklich kommt. */
const REGION_FLAG = { "": "🌍", DE: "🇩🇪", AT: "🇦🇹", CH: "🇨🇭", europe: "🇪🇺" };
const REGION_NAME = { "": "weltweit", DE: "Deutschland", AT: "Österreich",
                      CH: "Schweiz", europe: "Europa" };

function scopeFlag(scope) {
  return REGION_FLAG[scope ?? ""] || "🌍";
}

/* Für einen Preis-Datensatz (neu/gebraucht): Flagge als HTML mit Tooltip,
   aber nur, wenn der Preis aus einem anderen Gebiet stammt als eingestellt. */
function scopeFlagHtml(d) {
  if (!d || !d.fell_back) return "";
  const name = REGION_NAME[d.used_scope ?? ""] || "weltweit";
  return ` <span class="price-flag" title="Preis aus ${esc(name)} – im`
    + ` eingestellten Gebiet gab es keine Verkäufe">${scopeFlag(d.used_scope)}`
    + `</span>`;
}

/* Der Preis-Datensatz, der in der Karte gezeigt wird – spiegelt unitValue():
   der Zustand des Eintrags zuerst, sonst der jeweils andere. */
function shownPriceData(it) {
  let pd = null;
  try { pd = it.price_data ? JSON.parse(it.price_data) : null; } catch (_) { pd = null; }
  if (!pd) return null;
  const hasAvg = (x) => x && x.avg != null;
  const primary = it.condition === "new" ? pd.new : pd.used;
  const other = it.condition === "new" ? pd.used : pd.new;
  return hasAvg(primary) ? primary : (hasAvg(other) ? other : null);
}

/* Nur die Flaggen-Emoji (ohne Tooltip) für die eingeklappte Unterzeile. */
function fallbackFlagText(it) {
  const d = shownPriceData(it);
  return d && d.fell_back ? " " + scopeFlag(d.used_scope) : "";
}

/* Grundangaben (vorhanden / gemerkt / in eigenen Sets) für ALLE sichtbaren
   Treffer holen – das sind reine lokale Abfragen. Die teuren BrickLink-
   Details (Jahr, Preise) bleiben auf die ersten Treffer beschränkt. */
const SUGGEST_INFO_MAX = 60;    // Grenze des Endpoints
const SUGGEST_DETAIL_MAX = 8;   // teure Abrufe

async function enrichSuggestions(items) {
  const all = items.slice(0, SUGGEST_INFO_MAX).map((i) => ({
    item_id: i.item_id, item_type: i.item_type || "minifig" }));
  if (!all.length) return;
  try {
    const info = await api("/suggest_info",
      { method: "POST", body: { items: all } });
    applySuggestInfo(info, true);   // gespeicherte Jahre/Preise sofort zeigen
  } catch (_) { /* Badges sind nice-to-have */ }

  const detail = all.slice(0, SUGGEST_DETAIL_MAX);
  const detailIds = new Set(detail.map((i) => i.item_id));
  const hasBl = detail.some((i) => !/^(fig-|manuell-|custom-)/.test(i.item_id));
  if (state.bricklinkPrices && hasBl) {
    document.querySelectorAll("[data-sug-id]").forEach((card) => {
      const sub = card.querySelector("[data-sug-sub]");
      if (sub && detailIds.has(card.dataset.sugId)
          && !/^(fig-|manuell-|custom-)/.test(card.dataset.sugId)
          && sub.textContent === card.dataset.sugBase) {
        sub.textContent = card.dataset.sugBase + " · lade Jahr & Preise …";
      }
    });
    try {
      const info = await api("/suggest_info?detail=1",
        { method: "POST", body: { items: detail } });
      applySuggestInfo(info, true);
      // Angereicherte Details am Item merken, damit das Detail-Popup sie
      // nicht ein zweites Mal von BrickLink holen muss.
      items.forEach((it) => {
        if (info[it.item_id]) (it._infoById ||= {})[it.item_id] = info[it.item_id];
      });
    } catch (_) { /* dito */ }
    // Ladehinweis entfernen, wo nichts kam
    document.querySelectorAll("[data-sug-id]").forEach((card) => {
      const sub = card.querySelector("[data-sug-sub]");
      if (sub && sub.textContent.endsWith("lade Jahr & Preise …")) {
        sub.textContent = card.dataset.sugBase;
      }
    });
  }
}

function wireWantButtons(box, items) {
  box.querySelectorAll("[data-want]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const it = items[Number(btn.dataset.want)];
      btn.disabled = true;
      try {
        const res = await api("/wanted", { method: "POST", body: {
          item_id: it.item_id, item_type: it.item_type || "minifig",
          name: it.name, img_url: it.img_url || "",
          bricklink_url: it.bricklink_url || "", year: it.year || 0,
        }});
        if (res.exists) toast("Steht schon auf der Wunschliste ⭐");
        else if (res.owned > 0) toast(tr("Gemerkt ⭐ (habt ihr schon {n}×)", { n: res.owned }));
        else toast("Auf die Wunschliste gesetzt ⭐");
        btn.textContent = tr("⭐ Gemerkt");
      } catch (e) {
        toast(e.message);
      } finally {
        btn.disabled = false;
      }
    });
  });
}

async function loadWanted() {
  try {
    const data = await api("/wanted");
    $("stat-wanted").textContent = data.stats.count;
    $("stat-wanted-cost").textContent = data.stats.est_cost
      ? fmtEur(data.stats.est_cost) : "–";
    $("stat-wanted-cost-new").textContent = data.stats.est_cost_new
      ? fmtEur(data.stats.est_cost_new) : "–";
    renderWanted(data.items);
  } catch (e) { toast(e.message); }
}

function renderWanted(items) {
  const list = $("wanted-list");
  $("wanted-empty").hidden = items.length > 0;
  list.innerHTML = items.map((it) => {
    const prices = [
      it.price_new ? tr("Ø neu") + " " + fmtEur(it.price_new) : "",
      it.price_used ? tr("Ø gebr.") + " " + fmtEur(it.price_used) : "",
    ].filter(Boolean).join(" · ");
    const needsBlNo = /^(fig-|manuell-|custom-)/.test(it.item_id);
    return `
    <div class="card" data-wid="${it.id}">
      <div class="card-head">
        <img class="card-img" src="${imgSrc(it.img_url)}" data-gid="${esc(it.item_id)}" data-gtype="${esc(it.item_type || "minifig")}" alt="" loading="lazy">
        <div class="card-title">
          <strong>${esc(it.name)}</strong>
          <div class="sub">${esc(it.item_id)}${it.year > 0 ? " · " + it.year : ""}${prices ? " · " + prices : ""}</div>
          ${it.owned > 0 ? `<span class="badge badge-owned">✔ ${it.owned}× in eurer Sammlung</span>` : ""}
          ${it.in_sets && !it.owned ? `<div class="sub in-sets"><span class="in-sets-label">${esc(tr("🧩 fehlt zu eurem Set:"))}</span>${inSetLinks(it.in_sets)}</div>` : ""}
        </div>
      </div>
      ${needsBlNo && state.bricklinkLookup ? `
      <div class="detail-row">
        <input data-wfix-no placeholder="BrickLink-Nr. für Preise, z. B. sw0815" class="fix-input" autocapitalize="none">
        <button class="mini-btn add" data-wfix-btn>Setzen</button>
        ${it.img_url ? `<button class="mini-btn" data-wfix-auto>🔍 Auto</button>` : ""}
      </div>` : ""}
      <div class="card-actions btn-grid">
        <button class="mini-btn add" data-buy>✔ Gekauft!</button>
        ${priceGuideUrl(it) ? `<a class="mini-btn link" href="${esc(priceGuideUrl(it))}" target="_blank" rel="noopener">Preisverlauf ↗</a>` : ""}
        ${it.bricklink_url ? `<a class="mini-btn link" href="${esc(it.bricklink_url)}" target="_blank" rel="noopener">BrickLink ↗</a>` : ""}
        <button class="mini-btn danger" data-del>Löschen</button>
      </div>
    </div>`;
  }).join("");

  list.querySelectorAll(".card").forEach((card) => {
    const wid = Number(card.dataset.wid);
    const item = items.find((i) => i.id === wid);

    card.querySelectorAll("[data-jump-set]").forEach((b) => {
      b.addEventListener("click", (ev) => {
        ev.stopPropagation();
        jumpToSet(b.dataset.jumpSet);
      });
    });
    const moreBtn = card.querySelector("[data-more-sets]");
    if (moreBtn) {
      moreBtn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const span = card.querySelector(".more-sets");
        span.hidden = !span.hidden;
        moreBtn.textContent = span.hidden
          ? `+${span.querySelectorAll(".set-link").length} weitere ▾`
          : "weniger ▴";
      });
    }

    const wfixBtn = card.querySelector("[data-wfix-btn]");
    if (wfixBtn) {
      wfixBtn.addEventListener("click", async () => {
        const no = card.querySelector("[data-wfix-no]").value.trim();
        if (!no) return;
        wfixBtn.disabled = true;
        try {
          const found = await api(`/lookup/${item.item_type}/${encodeURIComponent(no)}`);
          await api("/wanted/" + wid, { method: "PATCH", body: {
            item_id: found.item_id, name: found.name,
            img_url: found.img_url, bricklink_url: found.bricklink_url,
            year: found.year || 0,
          }});
          toast(tr("{id} gesetzt – hole Preise …", { id: found.item_id }));
          await api(`/wanted/${wid}/refresh_prices`, { method: "POST" })
            .catch(() => {});
          loadWanted();
        } catch (e) {
          toast(e.message);
        } finally {
          wfixBtn.disabled = false;
        }
      });
    }
    const wfixAuto = card.querySelector("[data-wfix-auto]");
    if (wfixAuto) {
      wfixAuto.addEventListener("click", async () => {
        wfixAuto.disabled = true;
        wfixAuto.textContent = tr("Suche …");
        try {
          const data = await api("/resolve", { method: "POST",
            body: { img_url: item.img_url } });
          const filtered = (data.items || [])
            .filter((c) => !c.item_type || c.item_type === item.item_type);
          const best = filtered[0] || (data.items || [])[0];
          if (!best) {
            toast("Keine BrickLink-Nummer gefunden – bitte manuell eintragen");
            return;
          }
          await api("/wanted/" + wid, { method: "PATCH", body: {
            item_id: best.item_id, name: best.name,
            img_url: best.img_url || item.img_url,
            bricklink_url: best.bricklink_url || "",
          }});
          toast(tr("Gefunden: {name} ({id}, {score} % sicher) – hole Preise …",
      { name: best.name, id: best.item_id, score: best.score }));
          await api(`/wanted/${wid}/refresh_prices`, { method: "POST" })
            .catch(() => {});
          loadWanted();
        } catch (e) {
          toast(e.message);
        } finally {
          wfixAuto.disabled = false;
          wfixAuto.textContent = tr("🔍 Auto");
        }
      });
    }

    card.querySelector("[data-buy]").addEventListener("click", () => {
      const actions = card.querySelector(".card-actions");
      const dealer = state.user && state.user.is_dealer;
      actions.innerHTML = `
        <span class="buy-label">Gekauft als:</span>
        ${dealer ? `<span class="paid-row buy-paid">
          <span class="paid-label">Preis</span>
          <input data-buy-paid class="paid-input" inputmode="decimal" placeholder="0,00">
          <span class="paid-suffix" data-cur>${esc(curSymbol())}</span>
          <span class="sub">leer = BrickLink-Ø</span>
        </span>` : ""}
        <button class="mini-btn add" data-buy-cond="used">Gebraucht</button>
        <button class="mini-btn add" data-buy-cond="new">Neu</button>
        <button class="mini-btn" data-buy-cancel>Abbrechen</button>`;
      actions.querySelectorAll("[data-buy-cond]").forEach((b) => {
        b.addEventListener("click", async () => {
          const paidEl = actions.querySelector("[data-buy-paid]");
          let paid = null;
          if (paidEl && paidEl.value.trim() !== "") {
            paid = Number(paidEl.value.trim().replace(",", "."));
            if (!isFinite(paid) || paid < 0) {
              toast("Bitte einen gültigen Preis eingeben");
              return;
            }
          }
          b.disabled = true;
          try {
            const res = await api(`/wanted/${wid}/acquire`, { method: "POST",
              body: { condition: b.dataset.buyCond, paid_price: paid } });
            toast(res.merged
              ? "In der Sammlung: Anzahl erhöht ✔"
              : `In die Sammlung übernommen ✔ (${b.dataset.buyCond === "new" ? tr("Neu") : tr("Gebraucht")})`);
            await askSetFigures(item, b.dataset.buyCond);
            loadWanted();
          } catch (e) {
            toast(e.message);
            b.disabled = false;
          }
        });
      });
      actions.querySelector("[data-buy-cancel]").addEventListener("click",
        () => renderWanted(items));
    });
    card.querySelector("[data-del]").addEventListener("click", async () => {
      if (!confirm(tr("„{name}“ von der Wunschliste löschen?", { name: item.name }))) return;
      try {
        await api("/wanted/" + wid, { method: "DELETE" });
        loadWanted();
      } catch (e) { toast(e.message); }
    });
  });
}

function applySuggestInfo(info, withDetail) {
  document.querySelectorAll("[data-sug-id]").forEach((card) => {
    const d = info[card.dataset.sugId];
    if (!d) return;
    const ownedEl = card.querySelector("[data-owned]");
    const hasSets = d.in_sets || (d.all_sets && d.all_sets.length);
    if (hasSets) {
      const sub = card.querySelector("[data-sug-sub]");
      let el = card.querySelector(".in-sets");
      if (sub && !el) {
        el = document.createElement("div");
        el.className = "sub in-sets";
        sub.insertAdjacentElement("afterend", el);
      }
      if (el) {
        const links = [];
        const seen = new Set();
        if (d.in_sets) {
          d.in_sets.split(";;").forEach((s) => {
            const parts = s.split("|");
            const no = parts[0];
            const qty = Number(parts[parts.length - 1]) || 1;
            const name = parts.slice(1, -1).join("|");
            seen.add(no);
            links.push(`<button class="set-link owned" data-jump-set="${esc(no)}">`
              + `✔ ${esc(name)} (${esc(no)}${qty > 1 ? `, ${qty}×` : ""})</button>`);
          });
        }
        (d.all_sets || []).forEach((s) => {
          if (seen.has(s.no)) return;
          seen.add(s.no);
          links.push(`<a class="set-link ext" href="https://www.bricklink.com/v2/catalog/catalogitem.page?S=${encodeURIComponent(s.no)}" target="_blank" rel="noopener">`
            + `${esc(s.name)} (${esc(s.no)}${s.qty > 1 ? `, ${s.qty}×` : ""})</a>`);
        });
        // Gehört zu einem eigenen Set und fehlt noch? Dann deutlich sagen.
        const missingForOwn = d.in_sets && !(d.owned > 0);
        el.classList.toggle("missing", !!missingForOwn);
        let html = (missingForOwn ? tr("🧩 fehlt zu eurem Set:") + " "
          : tr("📦 in Sets:") + " ")
          + links[0];
        if (links.length > 1) {
          html += `<span class="more-sets" hidden> · ${links.slice(1).join(" · ")}</span> `
            + `<button class="set-link more-toggle" data-more-sets>+${links.length - 1} weitere ▾</button>`;
        }
        el.innerHTML = html;
        el.querySelectorAll("[data-jump-set]").forEach((b) => {
          b.addEventListener("click", (ev) => {
            ev.stopPropagation();
            jumpToSet(b.dataset.jumpSet);
          });
        });
        const mb = el.querySelector("[data-more-sets]");
        if (mb) {
          mb.addEventListener("click", (ev) => {
            ev.stopPropagation();
            const span = el.querySelector(".more-sets");
            span.hidden = !span.hidden;
            mb.textContent = span.hidden
              ? `+${span.querySelectorAll(".set-link").length} weitere ▾`
              : "weniger ▴";
          });
        }
      }
    }
    if (ownedEl && d.owned > 0) {
      ownedEl.textContent = `✔ ${d.owned}× in eurer Sammlung`;
      ownedEl.hidden = false;
    } else if (ownedEl && d.wanted) {
      ownedEl.textContent = tr("⭐ auf eurer Wunschliste");
      ownedEl.classList.remove("badge-owned");
      ownedEl.classList.add("badge-wanted");
      ownedEl.hidden = false;
    }
    if (d.on_lists && d.on_lists.length) {
      const card2 = ownedEl ? ownedEl.closest(".card") : null;
      if (card2 && !card2.querySelector(".badge-list")) {
        const lb = document.createElement("span");
        lb.className = "badge badge-list";
        lb.textContent = d.on_lists.length === 1
          ? `🛒 auf »${d.on_lists[0]}«`
          : `🛒 auf ${d.on_lists.length} Einkaufslisten`;
        if (ownedEl && !ownedEl.hidden) ownedEl.after(lb);
        else if (ownedEl) ownedEl.parentElement.appendChild(lb);
      }
    }
    if (withDetail) {
      const sub = card.querySelector("[data-sug-sub]");
      const parts = [];
      if (d.year > 0) parts.push(String(d.year));
      if (d.new != null) parts.push(tr("Ø neu") + " " + fmtEur(d.new));
      if (d.used != null) parts.push(tr("Ø gebr.") + " " + fmtEur(d.used));
      if (sub && parts.length) {
        sub.textContent = card.dataset.sugBase + " · " + parts.join(" · ");
      }
    }
  });
}

let gallery = { urls: [], idx: 0 };

/* Vergleichsschlüssel: dieselbe BrickLink-Figur (egal welcher Endpunkt/
   Auflösung) gilt als gleiches Bild; sonst nur Protokoll unabhängig. */
function imgKey(u) {
  const k = (u || "").trim().toLowerCase()
    .replace(/^https?:\/\//, "").replace(/^\/\//, "");
  const m = k.match(/^img\.bricklink\.com\/.*\/([^/]+?)(?:\.t\d+)?\.(?:png|jpe?g|gif)$/);
  return m ? "bl:" + m[1] : k;
}

function openGallery(startUrl, gid, gtype) {
  gallery = { urls: startUrl ? [startUrl] : [], idx: 0 };
  renderGallery();
  $("lightbox").hidden = false;
  if (gid && !gid.startsWith("manuell-")) {
    api(`/images/${encodeURIComponent(gtype || "minifig")}/${encodeURIComponent(gid)}`)
      .then((d) => {
        // Backend-Bilder bevorzugen (kanonisch, meist bessere Auflösung),
        // gleiches Motiv zusammenfassen; das Startbild nur behalten, wenn es
        // eine wirklich andere Quelle ist.
        const seen = new Set();
        const urls = [];
        (d.images || []).forEach((u) => {
          const k = imgKey(u);
          if (u && !seen.has(k)) { seen.add(k); urls.push(u); }
        });
        if (startUrl && !seen.has(imgKey(startUrl))) urls.unshift(startUrl);
        if (urls.length) {
          gallery.urls = urls;
          gallery.idx = Math.min(gallery.idx, urls.length - 1);
          renderGallery();
        }
      })
      .catch(() => {});
  }
}

function renderGallery() {
  $("lightbox-img").src = gallery.urls[gallery.idx] || "";
  const many = gallery.urls.length > 1;
  $("lb-count").textContent = many
    ? `${gallery.idx + 1} / ${gallery.urls.length}` : "";
  $("lb-prev").hidden = !many;
  $("lb-next").hidden = !many;
}

function stepGallery(delta) {
  const n = gallery.urls.length;
  if (n < 2) return;
  gallery.idx = (gallery.idx + delta + n) % n;
  renderGallery();
}

function closeGallery() {
  $("lightbox").hidden = true;
  $("lightbox-img").src = "";
  gallery = { urls: [], idx: 0 };
}

function priceGuideUrl(it) {
  if (/^(fig-|manuell-|custom-)/.test(it.item_id)) return "";
  const prefix = BL_URL_PREFIX[it.item_type] || "M";
  return `https://www.bricklink.com/v2/catalog/catalogitem.page?${prefix}=${encodeURIComponent(it.item_id)}#T=P`;
}

// Nach dem Hinzufügen eines Sets: enthaltene Figuren mit übernehmen?
async function askSetFigures(item, condition) {
  if ((item.item_type || "") !== "set") return 0;
  // Eigene und manuelle Sets stehen in keinem Katalog – nicht nachfragen.
  if (/^(custom-|manuell-)/.test(item.item_id || "")) return 0;
  const overlay = $("setfigs-overlay");
  const body = $("setfigs-body");
  if (!overlay || !body) return 0;
  let figs = [];
  try {
    const data = await api(`/set_figs/${encodeURIComponent(item.item_id)}`);
    figs = data.items || [];
  } catch (_) {
    return 0;   // keine BrickLink-Schlüssel oder Set unbekannt: still überspringen
  }
  if (!figs.length) return 0;
  const cond = condition === "new" ? "new" : "used";
  body.innerHTML = `
    <p class="search-hint">„${esc(item.name)}" enthält laut BrickLink
      <b>${figs.length} Minifigur${figs.length === 1 ? "" : "en"}</b>.
      Welche davon sind dabei?</p>
    <div class="setfigs-cond">
      <label for="setfigs-cond">Zustand der Figuren</label>
      <select id="setfigs-cond">
        <option value="used"${cond === "used" ? " selected" : ""}>Gebraucht</option>
        <option value="new"${cond === "new" ? " selected" : ""}>Neu</option>
      </select>
    </div>
    <button class="mini-btn setfigs-all" id="setfigs-toggle">Alle ab-/anwählen</button>
    <div class="setfigs-list">
      ${figs.map((f, i) => `
        <label class="setfigs-row">
          <input type="checkbox" data-fig="${i}" checked>
          <img class="card-img fig-img" src="${imgSrc(f.img_url)}" alt="" loading="lazy">
          <span><strong>${esc(f.name)}</strong><br>
            <span class="sub">${esc(f.item_id)}${f.qty > 1 ? ` · ${f.qty}× im Set` : ""}</span>
          </span>
        </label>`).join("")}
    </div>
    <div class="btn-grid">
      <button class="btn btn-outline" id="setfigs-none">Keine übernehmen</button>
      <button class="btn btn-primary" id="setfigs-ok">Übernehmen</button>
    </div>`;
  overlay.hidden = false;

  return new Promise((resolve) => {
    const finish = (n) => { overlay.hidden = true; resolve(n); };
    $("btn-setfigs-close").onclick = () => finish(0);
    $("setfigs-none").onclick = () => finish(0);
    $("setfigs-toggle").onclick = () => {
      const boxes = [...body.querySelectorAll("[data-fig]")];
      const anyOff = boxes.some((b) => !b.checked);
      boxes.forEach((b) => { b.checked = anyOff; });
    };
    $("setfigs-ok").onclick = async (ev) => {
      const btn = ev.currentTarget;
      const chosen = [...body.querySelectorAll("[data-fig]")]
        .filter((b) => b.checked).map((b) => figs[Number(b.dataset.fig)]);
      if (!chosen.length) return finish(0);
      const c = $("setfigs-cond").value;
      btn.disabled = true;
      btn.textContent = tr("Übernehme …");
      let done = 0;
      for (const f of chosen) {
        try {
          await api("/collection", { method: "POST", body: {
            item_id: f.item_id, item_type: "minifig", name: f.name,
            img_url: f.img_url, bricklink_url: f.bricklink_url,
            condition: c, quantity: f.qty || 1,
            // kam mit dem Set: kein eigener Kaufpreis, keine ⚙️-Schätzung
            paid_price: 0, paid_source: "set",
          }});
          done += 1;
        } catch (_) { /* einzelne Fehler überspringen */ }
      }
      toast(done === 1 ? tr("1 Figur zum Set übernommen 👥")
      : tr("{n} Figuren zum Set übernommen 👥", { n: done }));
      finish(done);
    };
  });
}

// Beim Löschen eines Sets: enthaltene Figuren mit entfernen?
async function askRemoveSetFigures(item) {
  if ((item.item_type || "") !== "set") return 0;
  const overlay = $("setfigs-overlay");
  const body = $("setfigs-body");
  if (!overlay || !body) return 0;
  let figs = [];
  try {
    const data = await api(
      `/set_figs_owned/${encodeURIComponent(item.item_id)}`);
    figs = data.items || [];
  } catch (_) {
    return 0;
  }
  if (!figs.length) return 0;
  body.innerHTML = `
    <p class="search-hint">Zu „${esc(item.name)}" sind
      <b>${figs.length} Figur${figs.length === 1 ? "" : "en"}</b> in eurer
      Sammlung. Sollen sie mit entfernt werden?</p>
    <button class="mini-btn setfigs-all" id="setfigs-toggle">Alle ab-/anwählen</button>
    <div class="setfigs-list">
      ${figs.map((f, i) => `
        <label class="setfigs-row">
          <input type="checkbox" data-fig="${i}" checked>
          <img class="card-img fig-img" src="${imgSrc(f.img_url)}" alt="" loading="lazy">
          <span><strong>${esc(f.name)}</strong><br>
            <span class="sub">${esc(f.item_id)} ·
              ${f.condition === "new" ? tr("Neu") : tr("Gebraucht")} ·
              ${f.remove}× entfernen${f.quantity > f.remove
                ? " " + tr("(von {q}, {rest} bleiben)",
                    { q: f.quantity, rest: f.quantity - f.remove })
                : ""}</span>
          </span>
        </label>`).join("")}
    </div>
    <div class="btn-grid">
      <button class="btn btn-outline" id="setfigs-none">Figuren behalten</button>
      <button class="btn btn-primary" id="setfigs-ok">Mit entfernen</button>
    </div>`;
  overlay.hidden = false;

  return new Promise((resolve) => {
    const finish = (n) => { overlay.hidden = true; resolve(n); };
    $("btn-setfigs-close").onclick = () => finish(0);
    $("setfigs-none").onclick = () => finish(0);
    $("setfigs-toggle").onclick = () => {
      const boxes = [...body.querySelectorAll("[data-fig]")];
      const anyOff = boxes.some((b) => !b.checked);
      boxes.forEach((b) => { b.checked = anyOff; });
    };
    $("setfigs-ok").onclick = async (ev) => {
      const btn = ev.currentTarget;
      const chosen = [...body.querySelectorAll("[data-fig]")]
        .filter((b) => b.checked).map((b) => figs[Number(b.dataset.fig)]);
      if (!chosen.length) return finish(0);
      btn.disabled = true;
      btn.textContent = tr("Entferne …");
      let done = 0;
      for (const f of chosen) {
        const rest = f.quantity - f.remove;
        try {
          if (rest > 0) {
            await api("/collection/" + f.id, { method: "PATCH",
              body: { quantity: rest } });
          } else {
            await api("/collection/" + f.id, { method: "DELETE" });
          }
          done += 1;
        } catch (_) { /* einzelne Fehler überspringen */ }
      }
      toast(done === 1 ? tr("1 Figur mit entfernt 🗑")
      : tr("{n} Figuren mit entfernt 🗑", { n: done }));
      finish(done);
    };
  });
}

async function loadSetFigs(card, item, btn) {
  const out = card.querySelector("[data-figs-out]");
  if (out.dataset.loaded) {
    out.hidden = !out.hidden;
    btn.textContent = out.hidden
      ? "👥 Enthaltene Figuren anzeigen" : "👥 Figuren ausblenden";
    return;
  }
  btn.disabled = true;
  btn.textContent = tr("Lade Figuren …");
  try {
    const data = await api(`/set_figs/${encodeURIComponent(item.item_id)}`);
    const figs = data.items || [];
    out.dataset.loaded = "1";
    if (!figs.length) {
      out.innerHTML = `<div class="price-note">Laut BrickLink enthält dieses Set keine Minifiguren.</div>`;
    } else {
      out.innerHTML = figs.map((f, i) => `
        <div class="fig-row" data-fig-row="${i}">
          <img class="card-img fig-img" src="${imgSrc(f.img_url)}" data-gid="${esc(f.item_id)}" data-gtype="minifig" alt="" loading="lazy">
          <div class="fig-info">
            <strong>${esc(f.name)}</strong>
            <div class="sub">${esc(f.item_id)}${f.qty > 1 ? ` · ${f.qty}× im Set` : ""}
              <span class="badge badge-owned" data-fig-badge hidden></span></div>
            <div class="fig-actions" data-fig-actions>
              <button class="mini-btn add" data-fig-add="${i}">＋ Sammlung</button>
              <button class="mini-btn" data-fig-want="${i}">☆ Merken</button>
            </div>
          </div>
        </div>`).join("");
      wireFigActions(out, figs);
      const own = await markFigOwnership(out, figs);
      const missing = figs.filter((f) => {
        const d = own[f.item_id] || {};
        return !(d.owned > 0) && !d.wanted;
      });
      if (missing.length) {
        const mrow = document.createElement("div");
        mrow.className = "fig-missing-row";
        mrow.innerHTML = `<button class="mini-btn" data-want-missing>${esc(tr("☆ {n} fehlende auf die Wunschliste", { n: missing.length }))}</button>`;
        out.appendChild(mrow);
        mrow.querySelector("[data-want-missing]").addEventListener("click",
          async (ev) => {
            const b = ev.currentTarget;
            b.disabled = true;
            let done = 0;
            for (const f of missing) {
              try {
                await api("/wanted", { method: "POST", body: {
                  item_id: f.item_id, item_type: "minifig", name: f.name,
                  img_url: f.img_url, bricklink_url: f.bricklink_url,
                }});
                done += 1;
              } catch (_) { /* einzelne Fehler überspringen */ }
            }
            toast(tr("{n} Figuren auf die Wunschliste gesetzt ⭐", { n: done }));
            mrow.remove();
            markFigOwnership(out, figs);
          });
      }
    }
    btn.textContent = tr("👥 Figuren ausblenden");
  } catch (e) {
    toast(e.message);
    btn.textContent = tr("👥 Enthaltene Figuren anzeigen");
  } finally {
    btn.disabled = false;
  }
}

async function loadFigParts(card, item, btn) {
  const out = card.querySelector("[data-parts-out]");
  if (out.dataset.loaded) {
    out.hidden = !out.hidden;
    btn.textContent = out.hidden
      ? "🧩 Enthaltene Teile anzeigen" : "🧩 Teile ausblenden";
    return;
  }
  btn.disabled = true;
  btn.textContent = tr("Lade Teile …");
  try {
    const data = await api(`/fig_parts/${encodeURIComponent(item.item_id)}`);
    const parts = data.items || [];
    out.dataset.loaded = "1";
    if (!parts.length) {
      out.innerHTML = `<div class="price-note">Für diese Figur hat BrickLink keine Teileliste.</div>`;
    } else {
      out.innerHTML = parts.map((p) => `
        <div class="fig-row">
          <img class="card-img fig-img" src="${imgSrc(p.img_url)}" alt="" loading="lazy">
          <div class="fig-info">
            <strong>${esc(p.name)}</strong>
            <div class="sub">${esc(p.item_id)}${p.color_name ? ` · ${esc(p.color_name)}` : ""}${p.qty > 1 ? ` · ${p.qty}×` : ""}</div>
            ${p.bricklink_url ? `<div class="fig-actions"><a class="mini-btn link" href="${esc(p.bricklink_url)}" target="_blank" rel="noopener">BrickLink ↗</a></div>` : ""}
          </div>
        </div>`).join("");
    }
    btn.textContent = tr("🧩 Teile ausblenden");
  } catch (e) {
    toast(e.message);
    btn.textContent = tr("🧩 Enthaltene Teile anzeigen");
  } finally {
    btn.disabled = false;
  }
}

async function markFigOwnership(out, figs) {
  const result = {};
  for (let i = 0; i < figs.length; i += 8) {
    const chunk = figs.slice(i, i + 8);
    try {
      const info = await api("/suggest_info", { method: "POST", body: {
        items: chunk.map((f) => ({ item_id: f.item_id, item_type: "minifig" })),
      }});
      chunk.forEach((f, j) => {
        result[f.item_id] = info[f.item_id] || {};
        const row = out.querySelector(`[data-fig-row="${i + j}"]`);
        const badge = row && row.querySelector("[data-fig-badge]");
        const d = info[f.item_id];
        if (!badge || !d) return;
        if (d.owned > 0) {
          badge.textContent = `✔ ${d.owned}× vorhanden`;
          badge.hidden = false;
        } else if (d.wanted) {
          badge.textContent = tr("⭐ auf der Wunschliste");
          badge.classList.remove("badge-owned");
          badge.classList.add("badge-wanted");
          badge.hidden = false;
        }
        // Liegt die Figur schon auf einer Einkaufsliste? Das ist eine eigene
        // Information – sie kann zugleich fehlen und bereits eingeplant sein.
        const old = row.querySelector("[data-fig-list]");
        if (old) old.remove();
        if (d.on_lists && d.on_lists.length) {
          const lb = document.createElement("span");
          lb.className = "badge badge-list";
          lb.setAttribute("data-fig-list", "");
          lb.textContent = d.on_lists.length === 1
            ? `🛒 auf »${d.on_lists[0]}«`
            : `🛒 auf ${d.on_lists.length} Listen`;
          badge.after(lb);
        }
      });
    } catch (_) { /* Badges sind nice-to-have */ }
  }
  return result;
}

function wireFigActions(out, figs) {
  out.querySelectorAll("[data-fig-add]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const f = figs[Number(btn.dataset.figAdd)];
      const area = btn.closest("[data-fig-actions]");
      const orig = area.innerHTML;
      area.innerHTML = `
        <button class="mini-btn add" data-fc="used">Gebraucht</button>
        <button class="mini-btn add" data-fc="new">Neu</button>
        <button class="mini-btn" data-fcx>✕</button>`;
      area.querySelector("[data-fcx]").addEventListener("click", () => {
        area.innerHTML = orig;
        wireFigActions(out, figs);
      });
      area.querySelectorAll("[data-fc]").forEach((b) => {
        b.addEventListener("click", async () => {
          b.disabled = true;
          try {
            const res = await api("/collection", { method: "POST", body: {
              item_id: f.item_id, item_type: "minifig", name: f.name,
              img_url: f.img_url, bricklink_url: f.bricklink_url,
              condition: b.dataset.fc,
            }});
            toast(res.merged
              ? tr("Schon vorhanden – Anzahl erhöht (jetzt {n}×)", { n: res.quantity })
              : `Zur Sammlung hinzugefügt ✔ (${b.dataset.fc === "new" ? tr("Neu") : tr("Gebraucht")})`);
            area.innerHTML = orig;
            wireFigActions(out, figs);
            markFigOwnership(out, figs);
          } catch (e) {
            toast(e.message);
            b.disabled = false;
          }
        });
      });
    });
  });
  out.querySelectorAll("[data-fig-want]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const f = figs[Number(btn.dataset.figWant)];
      btn.disabled = true;
      try {
        const res = await api("/wanted", { method: "POST", body: {
          item_id: f.item_id, item_type: "minifig", name: f.name,
          img_url: f.img_url, bricklink_url: f.bricklink_url,
        }});
        if (res.exists) toast("Steht schon auf der Wunschliste ⭐");
        else if (res.owned > 0) toast(tr("Gemerkt ⭐ (habt ihr schon {n}×)", { n: res.owned }));
        else toast("Auf die Wunschliste gesetzt ⭐");
        markFigOwnership(out, figs);
      } catch (e) {
        toast(e.message);
      } finally {
        btn.disabled = false;
      }
    });
  });
}

function fmtPaidInput(v) {
  return v == null ? "" : v.toFixed(2).replace(".", ",");
}

function paidSrcIcon(it) {
  const date = it.paid_at
    ? new Date(it.paid_at * 1000).toLocaleDateString(dateLocale()) : "";
  return it.paid_source === "manual"
    ? `<span title="manuell eingetragen${date ? " am " + date : ""}">✏️</span>`
    : `<span title="automatisch: BrickLink-Ø${date ? " vom " + date : ""}">⚙️</span>`;
}

/* Was der Artikel heute wert ist, gegen das Bezahlte.

   Der Betrag stand hier noch einmal, obwohl er direkt darüber im Feld
   „Bezahlt" steht – zweimal dieselbe Zahl untereinander. Jetzt beginnt die
   Zeile mit dem Wert; ohne Marktpreis bleibt sie leer, weil dann nur der
   Betrag von oben dastünde. */
function profitLine(it) {
  if (it.paid_price == null) return "";
  const value = unitValue(it) ? unitValue(it) * it.quantity : null;
  if (value == null) return "";
  const diff = value - it.paid_price;
  const cls = diff >= 0 ? "profit-pos" : "profit-neg";
  return esc(tr("Wert {wert}", { wert: fmtEur(value) })) + " · "
    + `<span class="${cls}">`
    + `${diff >= 0 ? "+" : "−"}${fmtEur(Math.abs(diff))}</span>`;
}

const TRASH_SVG = `<svg viewBox="0 0 24 24" width="18" height="18" `
  + `fill="none" stroke="currentColor" stroke-width="2.4" `
  + `stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">`
  + `<path d="M4 7h16"/><path d="M10 4h4a1 1 0 0 1 1 1v2H9V5a1 1 0 0 1 1-1z"/>`
  + `<path d="M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"/>`
  + `<path d="M10 11v6M14 11v6"/></svg>`;

/* Die Unterzeile der Karte steht auf zwei Zeilen: oben Nummer und Jahr,
   unten Zustand, Ø-Preis (mit Herkunfts-Flagge) und ggf. Set-Figuren. */
function collSubId(it) {
  return `${it.item_id}${it.year > 0 ? " · " + it.year : ""}`;
}

function collSubMeta(it) {
  let s = it.condition === "new" ? tr("Neu") : tr("Gebraucht");
  if (unitValue(it)) s += " · Ø " + fmtEur(unitValue(it)) + fallbackFlagText(it);
  return s;
}

/* Vollständigkeit der Set-Figuren („👥 3/4 ✔") – steht auf einer eigenen
   Zeile, damit das Icon nicht am Zeilenende umbricht. */
function setFigsText(it) {
  if (it.item_type !== "set" || !it.figs_total) return "";
  return `👥 ${it.figs_owned}/${it.figs_total}`
    + `${it.figs_owned === it.figs_total ? " ✔" : ""}`;
}

function inSetLinks(raw) {
  const links = raw.split(";;").map((s) => {
    const parts = s.split("|");
    const no = parts[0];
    const qty = Number(parts[parts.length - 1]) || 1;
    const name = parts.slice(1, -1).join("|");
    return `<button class="set-link owned" data-jump-set="${esc(no)}">`
      + `✔ ${esc(name)} (${esc(no)}${qty > 1 ? `, ${qty}×` : ""})</button>`;
  });
  if (links.length <= 1) return links.join("");
  return links[0]
    + `<span class="more-sets" hidden> · ${links.slice(1).join(" · ")}</span> `
    + `<button class="set-link more-toggle" data-more-sets>+${links.length - 1} weitere ▾</button>`;
}

function parseSetRefs(raw) {
  if (!raw) return [];
  return raw.split(";;").map((s) => {
    const parts = s.split("|");
    return { no: parts[0], qty: Number(parts[parts.length - 1]) || 1,
             name: parts.slice(1, -1).join("|") };
  });
}

/* Alle Sets einer Figur im Popup: eigene mit ✔ (Sprung in die Sammlung),
   fremde als BrickLink-Link. Die eigenen stehen sofort da, die vollständige
   Liste kommt von BrickLink nach (30-Tage-Cache). */
function renderFigSets(root, item) {
  const el = root.querySelector("[data-fig-sets]");
  if (!el) return;
  const owned = parseSetRefs(item.in_sets);

  const paint = (allSets) => {
    const seen = new Set();
    const links = [];
    owned.forEach((s) => {
      seen.add(s.no);
      links.push(`<button class="set-link owned" data-jump-set="${esc(s.no)}">`
        + `✔ ${esc(s.name)} (${esc(s.no)}${s.qty > 1 ? `, ${s.qty}×` : ""})</button>`);
    });
    (allSets || []).forEach((s) => {
      if (seen.has(s.no)) return;
      seen.add(s.no);
      links.push(`<a class="set-link ext" href="https://www.bricklink.com/v2/catalog/catalogitem.page?S=${encodeURIComponent(s.no)}" target="_blank" rel="noopener">`
        + `${esc(s.name)} (${esc(s.no)}${s.qty > 1 ? `, ${s.qty}×` : ""})</a>`);
    });
    if (!links.length) { el.hidden = true; return; }
    el.hidden = false;
    let html = `<span class="in-sets-label">${esc(tr("📦 Kommt vor in:"))}</span>`
      + links[0];
    if (links.length > 1) {
      html += `<span class="more-sets" hidden> · ${links.slice(1).join(" · ")}</span> `
        + `<button class="set-link more-toggle" data-more-sets>+${links.length - 1} weitere ▾</button>`;
    }
    el.innerHTML = html;
    el.querySelectorAll("[data-jump-set]").forEach((b) => {
      b.addEventListener("click", (ev) => {
        ev.stopPropagation();
        closeCardModal();
        jumpToSet(b.dataset.jumpSet);
      });
    });
    const mb = el.querySelector("[data-more-sets]");
    if (mb) {
      mb.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const span = el.querySelector(".more-sets");
        span.hidden = !span.hidden;
        mb.textContent = span.hidden
          ? `+${span.querySelectorAll(".set-link").length} weitere ▾` : "weniger ▴";
      });
    }
  };

  paint(null);   // eigene Sets sofort anzeigen
  if (item.item_type === "minifig" && state.bricklinkPrices
      && !/^(fig-|manuell-|custom-)/.test(item.item_id)) {
    api(`/fig_sets/${encodeURIComponent(item.item_id)}`)
      .then((d) => paint(d.sets)).catch(() => { /* eigene bleiben stehen */ });
  }
}

async function jumpToSet(setNo) {
  showTab("collection");
  $("type-filter").value = "";
  $("search").value = setNo;
  await loadCollection();
  const item = state.collection.find(
    (i) => i.item_id === setNo && i.item_type === "set");
  if (!item) { toast("Set nicht in der Sammlung gefunden"); return; }
  // Liegt das Set hinter dem ersten Block, ist seine Karte noch gar nicht da.
  karteSicherstellen(item.id);
  const card = $("collection-list").querySelector(`[data-id="${item.id}"]`);
  if (!card) return;
  const details = card.querySelector(".card-details");
  if (details && details.hidden) card.querySelector(".card-head").click();
  card.scrollIntoView({ behavior: "smooth", block: "start" });
  card.classList.add("flash");
  setTimeout(() => card.classList.remove("flash"), 1600);
}

function unitValue(it) {
  return it.condition === "new"
    ? (it.price_new ?? it.price_used)
    : (it.price_used ?? it.price_new);
}

function priceLine(label, d) {
  if (!d || !d.avg) {
    return `<div class="price-row"><span class="price-tag">${label}</span> ${esc(tr("keine Verkäufe"))}</div>`;
  }
  const range = (d.min != null && d.max != null)
    ? ` <span class="price-range">(${fmtEur(d.min)} – ${fmtEur(d.max)})</span>` : "";
  const sold = d.times_sold != null
    ? " · " + tr("{n}× verkauft", { n: d.times_sold }) : "";
  return `<div class="price-row"><span class="price-tag">${label}</span> `
    + `<strong>Ø ${fmtEur(d.avg)}</strong>${range}${sold}${scopeFlagHtml(d)}</div>`;
}

function showTab(name) {
  ["scan", "collection", "lists", "stats", "hub", "settings"].forEach((t) => {
    $("view-" + t).hidden = t !== name;
  });
  sammlungFreigeben(name);
  document.querySelectorAll(".tab").forEach((b) =>
    b.classList.toggle("active", b.dataset.tab === name));
  if (name === "collection") loadCollection(true);
  if (name === "lists") showListsTab(listsTab);
  if (name === "stats") loadStats();
  if (name === "hub") loadHubView();
  else updatePolling();          // außerhalb des Tausch-Tabs ruhiger takten
  if (name === "settings") loadSettings();
}

/* Die Sammlung ist mit Abstand die größte Ansicht: bei 815 Einträgen rund
   14.700 Elemente und ebenso viele Bilder. Bisher blieb das alles im
   Dokument stehen, auch wenn man längst in der Statistik war – gemessen bei
   5.000 Einträgen: 86.753 Elemente, dauerhaft. Wachsen tut das nicht, aber
   es ist der Sockel, auf dem jeder weitere Verbrauch aufsetzt.

   Beim Verlassen wird die Liste deshalb geleert. Die Daten bleiben in
   `state.collection`; beim Zurückkommen baut `loadCollection` sie neu auf. */
function sammlungFreigeben(neuerTab) {
  if (neuerTab === "collection") return;
  const liste = $("collection-list");
  if (!liste || !liste.firstChild) return;
  if (bgBeobachter) bgBeobachter.disconnect();
  liste.innerHTML = "";
}

/* Wünsche, Einkaufslisten und Archiv liegen in einem Tab.

   Vorher waren es zwei Einträge in der Leiste für dieselbe Frage – „was will
   ich noch, was nehme ich mit?" –, und das Archiv war ein Knopf, der
   dieselben Karten mit anderem Symbol zeigte. Als eigener Reiter ist es auf
   einen Blick etwas anderes. */
let listsTab = "wanted";

function showListsTab(name) {
  // Sind Einkaufslisten ausgeblendet, gibt es dort nichts zu sehen.
  if (name !== "wanted" && $("listtab-shop").hidden) name = "wanted";
  listsTab = name;
  state.showArchive = name === "archive";
  ["wanted", "shop", "archive"].forEach((t) => {
    $("listpane-" + t).hidden = t !== name;
  });
  document.querySelectorAll("[data-listtab]").forEach((b) =>
    b.classList.toggle("sel", b.dataset.listtab === name));
  if (name === "wanted") loadWanted();
  else loadLists();
}

/* Tausch-Tab nur zeigen, wenn diese Instanz mit dem Hub verbunden ist. */
function updateHubTab() {
  const tab = $("tab-hub");
  if (!tab) return;
  tab.hidden = !state.hubConnected;
  if (tab.hidden && !$("view-hub").hidden) showTab("scan");
}

/* Nach dem Zurückkommen (Tab/App wieder im Vordergrund) sofort nachsehen,
   statt bis zum nächsten Takt zu warten. */
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && state.hubConnected) pollTrades();
});

/* Escape schließt das oberste Tausch-Fenster. */
document.addEventListener("keydown", (ev) => {
  if (ev.key !== "Escape") return;
  if (!$("report-overlay").hidden) { closeReport(); return; }
  if (!$("interest-overlay").hidden) { closeInterest(); return; }
  if (!$("trade-overlay").hidden) closeTrade();
});

/* ---------------------------------------------------------------- Login */
async function refreshMe() {
  try {
    const me = await api("/me");
    state.user = { username: me.username, is_admin: me.is_admin,
      is_dealer: me.is_dealer, sortPref: me.sort_pref || "added" };
    applySortPref();
    localStorage.setItem("bf_user", JSON.stringify(state.user));
    applyServerTheme(me);
  } catch (_) { /* 401 wird von api() behandelt */ }
  updateListsTab();
  updateManualListBtn();
  checkForUpdate(false).then((info) => {
    if (info && info.update_available && !state.updateToastShown) {
      state.updateToastShown = true;
      toast(tr("⬆️ Update v{v} verfügbar – Details im Mehr-Tab", { v: info.latest }));
    }
  });
}

/* Der Tab ist immer da – die Wünsche gibt es ja immer. Ob es *Einkaufslisten*
   zu sehen gibt, entscheidet dagegen weiter der Bestand: Wer keine führt,
   soll auch keine leeren Reiter vor sich haben. */
async function updateListsTab() {
  const shop = $("listtab-shop");
  const arch = $("listtab-archive");
  if (!shop) return;
  let zeigen = !!(state.user && state.user.is_dealer);
  if (!zeigen) {
    try {
      const data = await api("/lists");
      zeigen = !!(data.lists && data.lists.length);
    } catch (_) { zeigen = false; }
  }
  shop.hidden = arch.hidden = !zeigen;
  if (!zeigen && listsTab !== "wanted" && !$("view-lists").hidden) {
    showListsTab("wanted");
  }
}

/* Titel der App inkl. Anzeigename – auch für Kopfzeilen im Druck */
function appTitle() {
  return (state.ownerName || "Finn") + "'s Brickfolio";
}

function applyOwnerName(name) {
  if (!name) return;
  state.ownerName = name;
  document.querySelectorAll(".logo-name").forEach((el) => {
    el.textContent = name.toUpperCase();
  });
  document.title = appTitle();
}

function showLogin() {
  $("view-login").hidden = false;
  $("app").hidden = true;
  // Ein angefangener zweiter Anmeldeschritt gehört zurückgesetzt – sonst
  // stünde nach dem Abmelden noch das Code-Feld von vorhin da.
  totpChallenge = "";
  if ($("totp-box")) $("totp-box").hidden = true;
  checkSetup();
}

async function checkSetup() {
  try {
    const s = await api("/setup");
    applyOwnerName(s.owner_name);
    if (s.default_theme) applyTheme(s.default_theme);   // Login-Screen: Instanz-Standard
    // Diese Abfrage läuft nebenher. Steht inzwischen der zweite
    // Anmeldeschritt auf dem Schirm, darf sie den Anmeldebogen nicht
    // wieder darüberlegen – sonst stünden beide Kästen gleichzeitig da.
    const im2fa = $("totp-box") && !$("totp-box").hidden;
    $("setup-box").hidden = !s.needed;
    $("login-box").hidden = s.needed || im2fa;
    if (s.needed) $("setup-user").focus();
  } catch (_) {
    const im2fa = $("totp-box") && !$("totp-box").hidden;
    $("setup-box").hidden = true;
    $("login-box").hidden = !!im2fa;
  }
}

async function doSetup() {
  const err = $("setup-error");
  err.hidden = true;
  const username = $("setup-user").value.trim();
  const p1 = $("setup-pass").value;
  const p2 = $("setup-pass2").value;
  if (username.length < 2) {
    err.textContent = tr("Bitte einen Benutzernamen eingeben (mind. 2 Zeichen)");
    err.hidden = false;
    return;
  }
  if (p1.length < 8) {
    err.textContent = tr("Das Passwort braucht mindestens 8 Zeichen");
    err.hidden = false;
    return;
  }
  if (p1 !== p2) {
    err.textContent = tr("Die Passwörter stimmen nicht überein");
    err.hidden = false;
    return;
  }
  $("btn-setup").disabled = true;
  try {
    const data = await api("/setup", { method: "POST",
      body: { username, password: p1 } });
    state.token = data.token;
    state.user = { username: data.username, is_admin: data.is_admin,
      is_dealer: data.is_dealer, sortPref: data.sort_pref || "added" };
    applySortPref();
    localStorage.setItem("bf_token", data.token);
    localStorage.setItem("bf_user", JSON.stringify(state.user));
    // Die Sprache, die beim Anlegen gewählt wurde, gehört ins frische Profil –
    // sonst gilt sie nur auf diesem Gerät.
    state.user.lang = lang;
    try { await api("/me/lang", { method: "POST", body: { lang } }); }
    catch (_) { /* lokal gilt sie trotzdem */ }
    toast(tr("Willkommen, {name}! 🧱", { name: data.username }));
    startWizard();
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  } finally {
    $("btn-setup").disabled = false;
  }
}

/* ------------------------------------------- Einrichtungsassistent
   Läuft genau einmal, direkt nach dem Anlegen des Admin-Kontos. Jeder
   Schritt ist überspringbar – die App ist ohne Schlüssel benutzbar (Scannen
   braucht keinen), deshalb darf hier nichts blockieren. */

const WIZ_LAST = 7;
let wizStep = 1;

function startWizard() {
  $("view-login").hidden = true;
  $("view-wizard").hidden = false;
  wizStep = 1;
  showWizStep();
  wireWizardOnce();
  ladeWizGebiet();
}

/* Welches Land steckt in den Browsereinstellungen? „en-GB" → GB. Ohne
   Länderteil bleibt nur die Sprache: Deutsch spricht für Deutschland,
   Englisch – mangels besserem Anhaltspunkt – für Großbritannien. */
function browserLand() {
  for (const l of navigator.languages || [navigator.language || ""]) {
    const teile = String(l).split("-");
    const land = teile.length > 1 ? teile[teile.length - 1].toUpperCase() : "";
    if (land.length === 2) return land;
  }
  const kurz = String(navigator.language || "de").slice(0, 2).toLowerCase();
  return kurz === "en" ? "GB" : kurz.toUpperCase();
}

/* Gebiet und Währung im Assistenten vorbelegen. Nichts wird hier gespeichert
   – erst „Weiter" schreibt die Auswahl weg. */
async function ladeWizGebiet() {
  try {
    const s = await api("/settings/price_region");
    const land = browserLand();
    const kennt = s.options.some((o) => o.value === land);
    const gebiet = s.region || (kennt ? land : "");
    const waehrung = s.currency !== "EUR" ? s.currency
      : (s.suggested[gebiet] || s.suggested[land] || "EUR");
    fuelleAuswahl($("wiz-region"), s.options, gebiet);
    fuelleAuswahl($("wiz-currency"), s.currencies, waehrung);
    // Land gewechselt? Dann die passende Währung mitziehen – wer bewusst
    // eine andere wählt, wird danach nicht mehr überstimmt.
    $("wiz-region").addEventListener("change", (ev) => {
      const w = s.suggested[ev.currentTarget.value];
      if (w) $("wiz-currency").value = w;
    });
  } catch (_) { /* ohne Liste bleibt der Schritt leer und überspringbar */ }
}

function showWizStep() {
  document.querySelectorAll("#view-wizard .wiz-step").forEach((el) => {
    el.hidden = Number(el.dataset.step) !== wizStep;
  });
  $("wiz-step-of").textContent = tr("Schritt {n} von {max}",
    { n: wizStep, max: WIZ_LAST });
  $("wiz-back").hidden = wizStep === 1;
  $("wiz-skip").hidden = wizStep === WIZ_LAST;
  $("wiz-next").textContent = wizStep === WIZ_LAST
    ? tr("Loslegen") : tr("Weiter");
  $("wiz-error").hidden = true;
}

function endWizard() {
  $("view-wizard").hidden = true;
  showApp();
}

/* Speichert, was der aktuelle Schritt eingesammelt hat. Leere Felder sind
   kein Fehler – dann wurde der Schritt eben nicht ausgefüllt. */
async function saveWizStep() {
  if (wizStep === 1) {
    const name = $("wiz-owner").value.trim();
    if (name) {
      await api("/settings/owner_name", { method: "POST", body: { name } });
      state.ownerName = name;
      applyOwnerName(name);
    }
  } else if (wizStep === 2) {
    const sel = $("wiz-region");
    if (sel && sel.options.length) {
      const res = await api("/settings/price_region", { method: "POST",
        body: { region: sel.value, currency: $("wiz-currency").value } });
      setCurrency(res.currency);
    }
  } else if (wizStep === 3 || wizStep === 4) {
    const fields = wizStep === 3
      ? { rebrickable_key: "wiz-rb" }
      : { bl_consumer_key: "wiz-bck", bl_consumer_secret: "wiz-bcs",
          bl_token: "wiz-bt", bl_token_secret: "wiz-bts" };
    const body = {};
    for (const [name, id] of Object.entries(fields)) {
      const v = $(id).value.trim();
      if (v) body[name] = v;
    }
    if (Object.keys(body).length) {
      const res = await api("/settings", { method: "PUT", body });
      state.bricklinkPrices = res.flags.bricklink_prices;
      state.bricklinkLookup = res.flags.bricklink_lookup;
      state.catalogSearch = res.flags.catalog_search;
    }
  } else if (wizStep === 6) {
    const invite_code = $("wiz-invite").value.trim();
    const display_name = $("wiz-hubname").value.trim();
    if (invite_code) {
      if (!display_name) throw new Error(tr("Bitte auch einen Anzeigenamen angeben."));
      await api("/hub/connect", { method: "POST",
        body: { invite_code, display_name } });
      state.hubConnected = true;
    }
  }
}

let wizWired = false;

function wireWizardOnce() {
  if (wizWired) return;
  wizWired = true;

  $("wiz-owner").addEventListener("input", () => {
    $("wiz-name-preview").textContent = $("wiz-owner").value.trim() || "Finn";
  });

  $("wiz-next").addEventListener("click", async () => {
    const btn = $("wiz-next");
    btn.disabled = true;
    try {
      await saveWizStep();
      if (wizStep === WIZ_LAST) { endWizard(); return; }
      wizStep += 1;
      showWizStep();
    } catch (e) {
      $("wiz-error").textContent = e.message;
      $("wiz-error").hidden = false;
    } finally { btn.disabled = false; }
  });

  $("wiz-skip").addEventListener("click", () => {
    wizStep = Math.min(wizStep + 1, WIZ_LAST);
    showWizStep();
  });
  $("wiz-back").addEventListener("click", () => {
    wizStep = Math.max(wizStep - 1, 1);
    showWizStep();
  });
  $("wiz-quit").addEventListener("click", endWizard);

  $("wiz-test").addEventListener("click", async () => {
    const out = $("wiz-test-out");
    out.hidden = false;
    out.textContent = tr("Teste …");
    try {
      const r = await api("/settings/test", { method: "POST" });
      out.innerHTML =
        `BrickLink: ${r.bricklink.ok ? "✅" : "❌"} ${esc(r.bricklink.info)}<br>`
        + `Rebrickable: ${r.rebrickable.ok ? "✅" : "❌"} ${esc(r.rebrickable.info)}`;
    } catch (e) { out.textContent = e.message; }
  });
}

function showApp() {
  updateListsTab();
  updateManualListBtn();
  updateInstallCard();
  $("view-login").hidden = true;
  $("app").hidden = false;
  $("whoami").textContent = state.user ? state.user.username : "";
  api("/config").then((c) => {
    state.offerPercent = c.offer_percent || 60;
    state.bricklinkPrices = c.bricklink_prices;
    state.catalogSearch = c.catalog_search;
    state.bricklinkLookup = c.bricklink_lookup;
    state.ownerName = c.owner_name || "Finn";
    applyOwnerName(state.ownerName);
    setCurrency(c.currency);
    state.hubConnected = !!c.hub_connected;
    updateHubTab();
    updatePolling();
    // Beim Öffnen einmal richtig nachsehen: `refreshUnread` allein liest nur
    // den zuletzt bekannten Stand aus der eigenen Datenbank – neue
    // Nachrichten lägen dann bis zum ersten Takt unbemerkt da.
    if (state.hubConnected) syncTrades(true).then(refreshUnread);
  }).catch(() => {});
  startUpdateWatch();
  diagStarten();
  initErrorReporting();
  loadNotifications();
  showTab("scan");
}

async function doLogin() {
  const err = $("login-error");
  err.hidden = true;
  try {
    const data = await api("/login", {
      method: "POST",
      body: { username: $("login-user").value.trim(), password: $("login-pass").value },
    });
    // Zweiter Faktor eingeschaltet? Dann kommt statt der Sitzung nur eine
    // Zwischenmarke zurück, die allein den nächsten Schritt erlaubt.
    if (data.totp_required) {
      totpChallenge = data.challenge;
      $("login-pass").value = "";
      $("login-box").hidden = true;
      $("totp-box").hidden = false;
      $("totp-code").value = "";
      $("totp-code").focus();
      return;
    }
    uebernehmeAnmeldung(data);
    return;
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  }
}

/* Der zweite Schritt: Einmalcode oder Rettungscode. */
let totpChallenge = "";

function abbrechenTotp() {
  totpChallenge = "";
  $("totp-box").hidden = true;
  $("login-box").hidden = false;
  $("totp-error").hidden = true;
}

async function doTotpLogin() {
  const err = $("totp-error");
  err.hidden = true;
  const code = $("totp-code").value.trim();
  if (!code) return;
  try {
    const data = await api("/login/2fa", { method: "POST",
      body: { challenge: totpChallenge, code } });
    totpChallenge = "";
    $("totp-box").hidden = true;
    $("login-box").hidden = false;
    if (data.recovery_used) {
      toast(tr("Rettungscode verbraucht – noch {n} übrig", 
        { n: data.recovery_left }));
    }
    uebernehmeAnmeldung(data);
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
    $("totp-code").select();
  }
}


/* ------------------------------------------- Zwei-Faktor im Profil

   Vier Zustände, die sich gegenseitig ausschließen: aus, gerade in
   Einrichtung, Rettungscodes anzeigen, an. */

async function ladeTfaStatus() {
  if (!$("tfa-off")) return;
  try {
    const s = await api("/me/2fa");
    zeigeTfa(s.active ? "an" : "aus", s);
  } catch (_) { /* nicht angemeldet o. Ä. */ }
}

function zeigeTfa(zustand, daten) {
  $("tfa-off").hidden = zustand !== "aus";
  $("tfa-setup").hidden = zustand !== "einrichtung";
  $("tfa-codes").hidden = zustand !== "codes";
  $("tfa-on").hidden = zustand !== "an";
  $("tfa-error").hidden = true;
  const info = $("tfa-info");
  if (zustand === "an") {
    info.textContent = tr("Aktiv – noch {n} Rettungscodes übrig.",
      { n: (daten && daten.recovery_left) || 0 });
  } else if (zustand === "aus") {
    info.textContent = tr("Zurzeit aus.");
  } else {
    info.textContent = "";
  }
}

function wireTfaOnce() {
  if (!$("btn-tfa-start") || $("btn-tfa-start").dataset.wired) return;
  $("btn-tfa-start").dataset.wired = "1";
  const err = $("tfa-error");
  const zeigeFehler = (e) => { err.textContent = e.message; err.hidden = false; };

  $("btn-tfa-start").addEventListener("click", async () => {
    err.hidden = true;
    try {
      const r = await api("/me/2fa/start", { method: "POST",
        body: { password: $("tfa-pass").value } });
      $("tfa-pass").value = "";
      $("tfa-secret").textContent = r.secret.replace(/(.{4})/g, "$1 ").trim();
      // QR frisch laden – der Endpunkt liefert ihn nur für die eigene,
      // noch offene Einrichtung.
      const svg = await fetch("/api/me/2fa/qr", {
        headers: { Authorization: "Bearer " + state.token } });
      $("tfa-qr").innerHTML = svg.ok ? await svg.text() : "";
      zeigeTfa("einrichtung");
      $("tfa-confirm").focus();
    } catch (e) { zeigeFehler(e); }
  });

  $("btn-tfa-confirm").addEventListener("click", async () => {
    err.hidden = true;
    try {
      const r = await api("/me/2fa/confirm", { method: "POST",
        body: { code: $("tfa-confirm").value.trim() } });
      $("tfa-confirm").value = "";
      $("tfa-codeliste").textContent = r.recovery_codes.join("\n");
      zeigeTfa("codes");
    } catch (e) { zeigeFehler(e); }
  });

  $("btn-tfa-copy").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText($("tfa-codeliste").textContent);
      toast(tr("Rettungscodes kopiert 📋"));
    } catch (_) { toast(tr("Kopieren nicht möglich – bitte abschreiben")); }
  });

  $("btn-tfa-done").addEventListener("click", () => {
    ladeTfaStatus();
    toast(tr("Zwei-Faktor ist aktiv 🔐"));
  });

  $("btn-tfa-disable").addEventListener("click", async () => {
    err.hidden = true;
    try {
      await api("/me/2fa/disable", { method: "POST", body: {
        password: $("tfa-off-pass").value, code: $("tfa-off-code").value.trim() } });
      $("tfa-off-pass").value = ""; $("tfa-off-code").value = "";
      toast(tr("Zwei-Faktor ausgeschaltet"));
      ladeTfaStatus();
    } catch (e) { zeigeFehler(e); }
  });
}

/* Gemeinsamer Abschluss beider Wege – mit und ohne zweiten Faktor. */
function uebernehmeAnmeldung(data) {
  state.token = data.token;
  state.user = { username: data.username, is_admin: data.is_admin,
    is_dealer: data.is_dealer, sortPref: data.sort_pref || "added" };
  applySortPref();
  localStorage.setItem("bf_token", data.token);
  localStorage.setItem("bf_user", JSON.stringify(state.user));
  applyServerTheme(data);
  $("login-pass").value = "";
  showApp();
}

function logout() {
  state.token = "";
  state.user = null;
  localStorage.removeItem("bf_token");
  localStorage.removeItem("bf_user");
  // Offene Overlays schließen – sonst bleiben sie über dem Login stehen
  closeCardModal();
  ["profile-overlay", "help-overlay"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.hidden = true;
  });
  document.body.style.overflow = "";
  showLogin();
}

/* ---------------------------------------------------------------- Scannen */

/* Adresse der aktuellen Vorschau. Sie muss gemerkt werden, um sie wieder
   freigeben zu können: Eine mit `createObjectURL` erzeugte Adresse hält die
   Datei **bis zum Neuladen der Seite** im Speicher, auch wenn längst ein
   anderes Bild angezeigt wird. Wer nacheinander mehrere Bildschirmfotos
   hineinzieht, sammelt sie also alle an – ein 2560×1440-Bild belegt entpackt
   rund 14 MB. Nach ein paar Dutzend ist der Tab am Ende, und der Browser
   beendet ihn („Auf dieser Seite gibt es ein Problem"). */
let vorschauUrl = null;

/* Ein Bild auf Arbeitsgröße bringen, **bevor** es irgendwo landet.

   Ein Bildschirmfoto ist schnell 2560×1440 oder größer. Der Browser hält es
   dann entpackt im Speicher – rund 14 MB bei dieser Größe, bei 4K das
   Doppelte –, obwohl die Vorschau es auf 300 Pixel Höhe zeigt. Wer mehrere
   nacheinander hineinzieht, treibt den Verbrauch so hoch, dass das System den
   Tab beendet („Auf dieser Seite gibt es ein Problem", Fehlercode 5).

   Verloren geht dabei nichts: Der Server verkleinert jedes Bild ohnehin auf
   1200 Pixel, bevor er es zur Erkennung weiterreicht. Wir tun es nur früher –
   und sparen nebenbei die Übertragung von zehn Megabyte durch den Tunnel. */
const SCAN_KANTE = 1200;

async function verkleinern(file, maxSeite = SCAN_KANTE) {
  if (!file || !("createImageBitmap" in window)) return file;
  let bmp;
  try {
    bmp = await createImageBitmap(file);
  } catch (_) {
    return file;                     // kein lesbares Bild – der Server sagt es
  }
  const faktor = Math.min(1, maxSeite / Math.max(bmp.width, bmp.height));
  if (faktor === 1) { bmp.close(); return file; }     // schon klein genug
  const c = document.createElement("canvas");
  c.width = Math.round(bmp.width * faktor);
  c.height = Math.round(bmp.height * faktor);
  c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
  bmp.close();                       // das Original sofort freigeben
  const blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.9));
  c.width = c.height = 0;            // auch die Zeichenfläche
  return blob ? new File([blob], "scan.jpg", { type: "image/jpeg" }) : file;
}

async function handlePhoto(file) {
  if (!file) return;
  file = await verkleinern(file);
  lastScanFile = file;          // fürs Anlegen einer eigenen Figur aufheben
  updateScanCustomBtns();
  if (vorschauUrl) URL.revokeObjectURL(vorschauUrl);
  vorschauUrl = URL.createObjectURL(file);
  const url = vorschauUrl;
  $("preview-img").src = url;
  rahmenZeigen(null);
  auswahlAnzeigen(null);
  scanAuswahl = null;
  document.querySelectorAll(".scan-mehr").forEach((e) => e.remove());
  gemerkteRahmen = [];
  gemerkteAnzeigen();
  $("scan-anzahl").hidden = true;
  $("scan-alle").hidden = false;
  $("scan-preview").hidden = false;
  $("scan-status").hidden = false;
  $("scan-results").innerHTML = "";

  const form = new FormData();
  form.append("file", file, "scan.jpg");
  try {
    const data = await api("/scan", { method: "POST", body: form });
    renderScanResults(data.items || []);
    rahmenZeigen(data.box);
  } catch (e) {
    toast(e.message);
  } finally {
    $("scan-status").hidden = true;
  }
}

/* ------------------------------------------------- Mehrere Figuren im Bild

   Die Erkennung sucht **ein** Objekt je Anfrage – so ist der Dienst gebaut,
   die Antwort enthält genau einen Rahmen. Liegen mehrere Figuren auf dem
   Foto, rät sie über eine davon und der Rest bleibt unbeachtet.

   Deshalb zeigt die Vorschau jetzt, *worüber* geraten wurde, und man kann
   einen eigenen Rahmen um die nächste Figur ziehen. Das Zuschneiden
   passiert hier im Browser; zum Server geht nur noch der Ausschnitt. */

let scanBox = null;              // vom Dienst erkannter Bereich
let gemerkteRahmen = [];         // selbst gezogene, für mehrere Figuren

function gemerkteAnzeigen() {
  const box = $("scan-gemerkt");
  if (!box) return;
  box.hidden = !gemerkteRahmen.length;
  const n = gemerkteRahmen.length;
  box.querySelector("[data-gemerkt-zahl]").textContent = n === 1
    ? tr("1 Rahmen gemerkt") : tr("{n} Rahmen gemerkt", { n });
}
let scanAuswahl = null;          // selbst gezogener Bereich (Bildkoordinaten)

function rahmenZeigen(box) {
  scanBox = box || null;
  const el = $("scan-rahmen");
  const tipp = $("scan-tipp");
  if (!el) return;
  el.hidden = !box;
  if (tipp) tipp.hidden = !box;
  if (!box) return;
  // Beschriftung, damit der Rahmen für sich spricht. Ohne sie stand er
  // neben den nummerierten Rahmen und sah aus wie eine weitere Figur –
  // dabei sagt er nur, wo die Erkennung hingeschaut hat.
  el.dataset.was = tr("hier geschaut");
  const img = $("preview-img");
  const skal = () => {
    if (!img.naturalWidth) return;
    const fx = img.clientWidth / img.naturalWidth;
    const fy = img.clientHeight / img.naturalHeight;
    el.style.left = (box.left * fx) + "px";
    el.style.top = (box.upper * fy) + "px";
    el.style.width = ((box.right - box.left) * fx) + "px";
    el.style.height = ((box.lower - box.upper) * fy) + "px";
  };
  if (img.complete) skal(); else img.addEventListener("load", skal, { once: true });
}

function auswahlAnzeigen(a) {
  const el = $("scan-auswahl");
  const knopf = $("scan-ausschnitt");
  const img = $("preview-img");
  if (!el || !img.naturalWidth) return;
  if (!a) {
    el.hidden = true;
    knopf.hidden = true;
    $("scan-merken").hidden = true;
    return;
  }
  const fx = img.clientWidth / img.naturalWidth;
  const fy = img.clientHeight / img.naturalHeight;
  el.hidden = false;
  el.style.left = (a.x * fx) + "px";
  el.style.top = (a.y * fy) + "px";
  el.style.width = (a.w * fx) + "px";
  el.style.height = (a.h * fy) + "px";
  // Zu kleine Ausschnitte ergeben keine brauchbare Erkennung
  const brauchbar = a.w > 40 && a.h > 40;
  knopf.hidden = !brauchbar;
  $("scan-merken").hidden = !brauchbar;
}

function scanAuswahlEinrichten() {
  const img = $("preview-img");
  const knopf = $("scan-ausschnitt");
  if (!img || !knopf) return;
  let start = null;

  const bildPunkt = (ev) => {
    const r = img.getBoundingClientRect();
    const p = ev.touches ? ev.touches[0] : ev;
    return {
      x: Math.max(0, Math.min(img.naturalWidth,
        (p.clientX - r.left) / r.width * img.naturalWidth)),
      y: Math.max(0, Math.min(img.naturalHeight,
        (p.clientY - r.top) / r.height * img.naturalHeight)),
    };
  };
  const ziehen = (ev) => {
    if (!start) return;
    ev.preventDefault();
    const jetzt = bildPunkt(ev);
    scanAuswahl = {
      x: Math.min(start.x, jetzt.x), y: Math.min(start.y, jetzt.y),
      w: Math.abs(jetzt.x - start.x), h: Math.abs(jetzt.y - start.y),
    };
    auswahlAnzeigen(scanAuswahl);
  };
  const ende = () => {
    start = null;
    document.removeEventListener("pointermove", ziehen);
    document.removeEventListener("pointerup", ende);
  };
  img.addEventListener("pointerdown", (ev) => {
    if (!lastScanFile) return;
    ev.preventDefault();
    start = bildPunkt(ev);
    scanAuswahl = null;
    auswahlAnzeigen(null);
    document.addEventListener("pointermove", ziehen);
    document.addEventListener("pointerup", ende);
  });

  $("scan-alle").addEventListener("click", () => alleFigurenErkennen(0));
  $("scan-weniger").addEventListener("click", () => anzahlAendern(-1));
  $("scan-mehr").addEventListener("click", () => anzahlAendern(1));

  // Mehrere Rahmen sammeln. Für Figuren, die kreuz und quer liegen oder
  // versetzt hintereinander stehen, findet keine automatische Trennung
  // verlässlich die Grenzen – das habe ich in vier Anläufen gemessen. Von
  // Hand gezogene Rahmen stimmen dagegen immer, und mehrere hintereinander
  // sind schnell gezogen.
  $("scan-merken").addEventListener("click", () => {
    if (!scanAuswahl) return;
    gemerkteRahmen.push({ ...scanAuswahl });
    mehrfachRahmen(gemerkteRahmen);
    $("scan-rahmen").hidden = true;
    auswahlAnzeigen(null);
    scanAuswahl = null;
    gemerkteAnzeigen();
  });

  $("scan-gemerkt-los").addEventListener("click", async () => {
    if (!gemerkteRahmen.length || !lastScanFile) return;
    const status = $("scan-status");
    const gefunden = [];
    try {
      for (let i = 0; i < gemerkteRahmen.length; i++) {
        status.hidden = false;
        status.querySelector("[data-scan-text]").textContent =
          tr("Figur {i} von {n} …", { i: i + 1, n: gemerkteRahmen.length });
        const teil = await ausschnittBild(lastScanFile, gemerkteRahmen[i]);
        const fd = new FormData();
        fd.append("file", teil, "scan.jpg");
        try {
          const d = await api("/scan", { method: "POST", body: fd });
          if (d.items && d.items[0]) gefunden.push(d.items[0]);
        } catch (_) { /* eine weniger, der Rest läuft weiter */ }
      }
      if (!gefunden.length) { toast(tr("Nichts erkannt.")); return; }
      renderScanResults(gefunden);
      toast(gefunden.length === 1 ? tr("1 Figur erkannt ✔")
        : tr("{n} Figuren erkannt ✔", { n: gefunden.length }));
    } finally {
      status.hidden = true;
      status.querySelector("[data-scan-text]").textContent = tr("Erkenne …");
    }
  });

  $("scan-gemerkt-weg").addEventListener("click", () => {
    gemerkteRahmen = [];
    document.querySelectorAll(".scan-mehr").forEach((e) => e.remove());
    gemerkteAnzeigen();
  });

  knopf.addEventListener("click", async () => {
    if (!scanAuswahl || !lastScanFile) return;
    knopf.disabled = true;
    $("scan-status").hidden = false;
    try {
      const teil = await ausschnittBild(lastScanFile, scanAuswahl);
      const form = new FormData();
      form.append("file", teil, "scan.jpg");
      const data = await api("/scan", { method: "POST", body: form });
      renderScanResults(data.items || []);
      if (!(data.items || []).length) toast(tr("In diesem Ausschnitt nichts erkannt."));
      auswahlAnzeigen(null);
      scanAuswahl = null;
    } catch (e) {
      toast(e.message);
    } finally {
      knopf.disabled = false;
      $("scan-status").hidden = true;
    }
  });
}

/* ------------------------------- Alle Figuren auf einem Bild finden

   Der Erkennungsdienst sucht **ein** Objekt je Anfrage. Mehrere Figuren
   gehen also nur, indem man sie vorher trennt – und das kann die App
   selbst, solange der Hintergrund halbwegs einfarbig ist. Genau das steht
   ohnehin auf der Scan-Karte: „Vor neutralem Hintergrund".

   Vorgehen: Das Bild klein rechnen, aus dem Rand die Hintergrundfarbe
   schätzen, alles deutlich Abweichende als Vordergrund markieren,
   zusammenhängende Flecken suchen und daraus Rahmen machen. Jeder Rahmen
   geht danach einzeln zur Erkennung. */

const FIND_BREITE = 320;         // Analysegröße – mehr braucht es nicht
const FIND_MAX = 10;             // mehr Figuren fragen wir nicht ab

/* Kanten statt Farben.

   Der erste Anlauf verglich jeden Bildpunkt mit einer aus dem Rand
   geschätzten Hintergrundfarbe. Auf weißem Papier geht das; in einer
   Vitrine nicht – dort spiegelt das Glas, der Regalboden ist hell, die
   Rückwand blaugrau, und die Figuren sind genau so blaugrau. Es gibt keine
   Hintergrundfarbe, von der sie sich abheben.

   Figuren nebeneinander haben aber immer eines: **Struktur**. Wo eine Figur
   steht, wechseln Helligkeiten dicht an dicht – Helm, Arme, Gürtel. In der
   Lücke dazwischen liegt eine ruhige Fläche. Deshalb misst die App jetzt
   die Kantendichte je Bildspalte und schneidet in den Tälern. */

function graustufen(px, w, h) {
  const g = new Float32Array(w * h);
  for (let i = 0; i < w * h; i++) {
    g[i] = (px[i * 4] * 0.299 + px[i * 4 + 1] * 0.587 + px[i * 4 + 2] * 0.114);
  }
  return g;
}

function glaetten(werte, fenster) {
  const out = new Float32Array(werte.length);
  const r = Math.max(1, Math.round(fenster));
  for (let i = 0; i < werte.length; i++) {
    let s = 0, n = 0;
    for (let j = Math.max(0, i - r); j <= Math.min(werte.length - 1, i + r); j++) {
      s += werte[j];
      n++;
    }
    out[i] = s / n;
  }
  return out;
}

async function figurenFinden(file, anzahlWunsch = 0) {
  const bmp = await createImageBitmap(file);
  const f = FIND_BREITE / bmp.width;
  const w = FIND_BREITE, h = Math.max(1, Math.round(bmp.height * f));
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  const ctx = c.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(bmp, 0, 0, w, h);
  const px = ctx.getImageData(0, 0, w, h).data;
  bmp.close();
  c.width = c.height = 0;
  const grau = graustufen(px, w, h);

  // Kantenstärke je Bildpunkt (einfacher Gradient, reicht völlig)
  const kante = new Float32Array(w * h);
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const i = y * w + x;
      kante[i] = Math.abs(grau[i + 1] - grau[i - 1])
        + Math.abs(grau[i + w] - grau[i - w]);
    }
  }

  // In welchem waagerechten Band stehen die Figuren? Dort ist am meisten los.
  const jeZeile = new Float32Array(h);
  for (let y = 0; y < h; y++) {
    let s = 0;
    for (let x = 0; x < w; x++) s += kante[y * w + x];
    jeZeile[y] = s;
  }
  const zg = glaetten(jeZeile, h * 0.03);
  // Schwelle am **Mittelwert**, nicht am Maximum: Eine einzelne sehr harte
  // Kante – etwa die beleuchtete Regalkante – ist um ein Vielfaches
  // stärker als eine Figur. Am Maximum gemessen fiele alles andere durch,
  // und das Band landete auf der Kante statt auf den Figuren. Genau das
  // ist beim ersten Versuch passiert: Zeile 165–187 von 198.
  const mittel = zg.reduce((a, b) => a + b, 0) / h;
  let oben = 0, unten = h - 1;
  while (oben < h - 1 && zg[oben] < mittel) oben++;
  while (unten > oben && zg[unten] < mittel) unten--;
  if (unten - oben < h * 0.15) { oben = 0; unten = h - 1; }   // nichts erkennbar
  // Das Band dient nur dem **Messen** der Spalten – als Schnittgrenze taugt
  // es nicht. Es endet dort, wo die Kantendichte nachlässt, und das ist bei
  // einer Figur der Helm: rund, ruhig, kaum Kanten. Gemessen fehlte er im
  // Ausschnitt (Band ab y=247, Kopf ab y=204). Geschnitten wird deshalb
  // über die **volle Höhe**; was oben und unten an Hintergrund mitkommt,
  // stört die Erkennung nicht – sie sucht sich ihr Objekt selbst.

  // Kantendichte je Spalte, nur im Figurenband
  const jeSpalte = new Float32Array(w);
  for (let x = 0; x < w; x++) {
    let s = 0;
    for (let y = oben; y <= unten; y++) s += kante[y * w + x];
    jeSpalte[x] = s;
  }
  const sg = glaetten(jeSpalte, w * 0.012);
  const maxS = Math.max(...sg);
  if (!maxS) return [];

  // Schnittstellen sind die **ausgeprägten** Täler, nicht die tiefsten.
  //
  // Ein fester Schwellwert scheitert, sobald Figuren dicht stehen: Gemessen
  // an einer Vitrinenaufnahme lagen die Lücken bei 41 % des Höchstwerts,
  // die Figuren bei 70–100 % – kein Wert trennt das sauber. Die Ausprägung
  // schon: Wie weit fällt ein Tal unter die Gipfel links und rechts? Bei
  // echten Lücken waren das 58, bei Rauschen 17 bis 22.
  const AUSPRAEGUNG = 0.35;
  const taeler = [];
  for (let x = 2; x < w - 2; x++) {
    if (!(sg[x] <= sg[x - 1] && sg[x] <= sg[x + 1])) continue;
    let li = sg[x], re = sg[x];
    for (let j = x; j >= 0 && sg[j] >= sg[x]; j--) li = Math.max(li, sg[j]);
    for (let j = x; j < w && sg[j] >= sg[x]; j++) re = Math.max(re, sg[j]);
    if ((Math.min(li, re) - sg[x]) / maxS >= AUSPRAEGUNG) taeler.push(x);
  }
  // Ein breites Tal liefert mehrere benachbarte Minima – die gehören zusammen
  const schnitte = [];
  for (const x of taeler) {
    if (!schnitte.length || x - schnitte[schnitte.length - 1] > w * 0.04) {
      schnitte.push(x);
    } else {
      schnitte[schnitte.length - 1] = Math.round(
        (schnitte[schnitte.length - 1] + x) / 2);
    }
  }
  // Zwischen den Schnitten liegen die Figuren; Ränder ohne Struktur weg
  const bereiche = [];
  const grenzen = [0, ...schnitte, w - 1];
  for (let i = 0; i < grenzen.length - 1; i++) {
    const a = grenzen[i], b = grenzen[i + 1];
    if (b - a < w * 0.04) continue;
    let hoch = 0;
    for (let x = a; x <= b; x++) hoch = Math.max(hoch, sg[x]);
    if (hoch >= maxS * 0.45) bereiche.push([a, b]);   // sonst ist da nichts
  }

  // Wenn eine Zahl vorgegeben ist und die Trennung nicht passt: gleichmäßig
  // teilen. Lieber gerade Schnitte als gar keine.
  let spalten = bereiche;
  if (anzahlWunsch > 0 && bereiche.length !== anzahlWunsch) {
    const l = bereiche.length ? bereiche[0][0] : 0;
    const r = bereiche.length ? bereiche[bereiche.length - 1][1] : w - 1;
    const breite = (r - l + 1) / anzahlWunsch;
    spalten = Array.from({ length: anzahlWunsch }, (_, i) =>
      [Math.round(l + i * breite), Math.round(l + (i + 1) * breite) - 1]);
  }

  return spalten.slice(0, FIND_MAX).map(([x0, x1]) => ({
    x: x0 / f, y: 0, w: (x1 - x0 + 1) / f, h: h / f,
  }));
}

/* Alle gefundenen Figuren nacheinander erkennen lassen. */
let letzteBoxen = [];

async function alleFigurenErkennen(anzahlWunsch = 0) {
  if (!lastScanFile) return;
  const knopf = $("scan-alle");
  const status = $("scan-status");
  knopf.disabled = true;
  try {
    const boxen = await figurenFinden(lastScanFile, anzahlWunsch);
    if (!boxen.length) {
      toast(tr("Keine Figuren gefunden – Rahmen von Hand ziehen."));
      return;
    }
    letzteBoxen = boxen;
    mehrfachRahmen(boxen);
    anzahlRegler(boxen.length);
    if (boxen.length < 2 && !anzahlWunsch) {
      toast(tr("Nur eine Figur gefunden. Stimmt das nicht, die Zahl unten "
        + "anpassen."));
    }
    const gefunden = [];
    for (let i = 0; i < boxen.length; i++) {
      status.hidden = false;
      status.querySelector("[data-scan-text]").textContent =
        tr("Figur {i} von {n} …", { i: i + 1, n: boxen.length });
      const teil = await ausschnittBild(lastScanFile, boxen[i]);
      try {
        const fd = new FormData();
        fd.append("file", teil, "scan.jpg");
        const d = await api("/scan", { method: "POST", body: fd });
        if (d.items && d.items[0]) gefunden.push(d.items[0]);
      } catch (_) { /* eine Figur weniger, der Rest läuft weiter */ }
    }
    if (!gefunden.length) { toast(tr("Nichts erkannt.")); return; }
    renderScanResults(gefunden);
    toast(gefunden.length === 1 ? tr("1 Figur erkannt ✔")
      : tr("{n} Figuren erkannt ✔", { n: gefunden.length }));
  } catch (e) {
    toast(e.message);
  } finally {
    knopf.disabled = false;
    status.hidden = true;
    status.querySelector("[data-scan-text]").textContent = tr("Erkenne …");
  }
}

/* Die Zahl der Figuren nachbessern.

   Kein Verfahren trifft jede Vitrine. Statt an Schwellwerten zu drehen,
   die man nie sieht, steht hier die gefundene Zahl – und wer sie ändert,
   bekommt das Bild gleichmäßig in so viele Streifen geteilt. Ein Tipp
   statt Raten. */
function anzahlRegler(n) {
  const box = $("scan-anzahl");
  if (!box) return;
  box.hidden = false;
  box.querySelector("[data-anzahl]").textContent = n;
  box.dataset.n = n;
}

function anzahlAendern(schritt) {
  const box = $("scan-anzahl");
  const n = Math.max(1, Math.min(FIND_MAX, Number(box.dataset.n || 1) + schritt));
  if (String(n) === box.dataset.n) return;
  anzahlRegler(n);
  alleFigurenErkennen(n);
}

/* Alle gefundenen Bereiche gleichzeitig einrahmen. */
function mehrfachRahmen(boxen) {
  const wrap = document.querySelector(".scan-bild");
  const img = $("preview-img");
  wrap.querySelectorAll(".scan-mehr").forEach((e) => e.remove());
  // Zwei Bedeutungen in derselben Farbe verunsichern nur: Sobald die
  // nummerierten Rahmen stehen, verschwindet der des Dienstes.
  $("scan-rahmen").hidden = true;
  if (!img.naturalWidth) return;
  const fx = img.clientWidth / img.naturalWidth;
  const fy = img.clientHeight / img.naturalHeight;
  boxen.forEach((b, i) => {
    const d = document.createElement("div");
    d.className = "scan-rahmen scan-mehr";
    d.style.left = (b.x * fx) + "px";
    d.style.top = (b.y * fy) + "px";
    d.style.width = (b.w * fx) + "px";
    d.style.height = (b.h * fy) + "px";
    d.dataset.nr = i + 1;
    wrap.appendChild(d);
  });
}

/* Ausschnitt aus dem aufgenommenen Bild – mit etwas Rand, weil die
   Erkennung mit ein wenig Umgebung besser zurechtkommt. */
async function ausschnittBild(file, a) {
  const bmp = await createImageBitmap(file);
  const rand = Math.round(Math.max(a.w, a.h) * 0.08);
  const x = Math.max(0, Math.round(a.x) - rand);
  const y = Math.max(0, Math.round(a.y) - rand);
  const w = Math.min(bmp.width - x, Math.round(a.w) + rand * 2);
  const h = Math.min(bmp.height - y, Math.round(a.h) + rand * 2);
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  c.getContext("2d").drawImage(bmp, x, y, w, h, 0, 0, w, h);
  bmp.close();
  const blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.9));
  c.width = c.height = 0;
  return new File([blob], "scan.jpg", { type: "image/jpeg" });
}

function renderScanResults(items) {
  const box = $("scan-results");
  if (!items.length) {
    box.innerHTML = `<p class="empty">Keine Übereinstimmung gefunden.<br>
      Versucht es mit besserem Licht und neutralem Hintergrund –
      oder legt sie unten als <b>eigene Figur</b> mit diesem Foto an.</p>`;
    return;
  }
  box.innerHTML = items.map((it, i) => {
    const scoreCls = it.score >= 60 ? "badge-score" : "badge badge-low";
    const base = `${it.item_id}${it.category ? " · " + it.category : ""}`;
    return `
    <div class="card" data-sug-id="${esc(it.item_id)}" data-sug-base="${esc(base)}">
      <div class="card-head">
        <img class="card-img" src="${imgSrc(it.img_url)}" data-gid="${esc(it.item_id)}" data-gtype="${esc(it.item_type || "minifig")}" alt="" loading="lazy">
        <div class="card-title">
          <strong>${esc(it.name)}</strong>
          <div class="sub" data-sug-sub>${esc(base)}</div>
          <span class="badge ${scoreCls}">${it.score} % sicher</span><span class="badge badge-type">${esc(it.item_type)}</span>
          <span class="badge badge-owned" data-owned hidden></span>
        </div>
      </div>
      <div class="card-actions">
        <button class="mini-btn add" data-add="${i}">＋ Zur Sammlung</button>
        <button class="mini-btn" data-want="${i}">☆ Merken</button>
        ${state.user && state.user.is_dealer ? `<button class="mini-btn" data-cart="${i}">🛒 Liste</button>` : ""}
        ${it.bricklink_url ? `<a class="mini-btn link" href="${esc(it.bricklink_url)}" target="_blank" rel="noopener">BrickLink ↗</a>` : ""}
      </div>
    </div>`;
  }).join("");

  enrichSuggestions(items);
  wireWantButtons(box, items);
  wireCartButtons(box, items);

  // Tipp auf ein Scan-Ergebnis öffnet die Detailansicht – wie in der Suche.
  // Nicht bei Knopf/Link/Bild/Eingabefeld und nicht, solange ein Formular
  // (Bezahlt/Zustand oder Listen-Ablauf) in der Karte offen ist.
  box.querySelectorAll("[data-sug-id]").forEach((card, i) => {
    card.classList.add("tappable");
    card.addEventListener("click", (ev) => {
      if (ev.target.closest("button, a, input, textarea, select, label, .card-img")) return;
      if (card.querySelector("[data-cond-row], [data-cart-row]")) return;
      openSuggestModal(items[i]);
    });
  });

  box.querySelectorAll("[data-add]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const it = items[Number(btn.dataset.add)];
      const card = btn.closest(".card");
      if (card.querySelector("[data-cond-row]")) return;
      const actions = card.querySelector(".card-actions");
      actions.hidden = true;
      const row = document.createElement("div");
      row.className = "card-actions btn-grid";
      row.setAttribute("data-cond-row", "");
      row.innerHTML = `
        <input data-add-paid class="paid-input" inputmode="decimal"
          placeholder="${esc(tr("Bezahlt {cur} (optional)", { cur: curSymbol() }))}" style="grid-column:1/-1">
        <span class="buy-label" style="grid-column:1/-1">Zustand wählen (wird sofort gespeichert):</span>
        <button class="mini-btn add" data-c="used">Gebraucht</button>
        <button class="mini-btn add" data-c="new">Neu</button>
        <button class="mini-btn" data-cancel style="grid-column:1/-1">Abbrechen</button>`;
      actions.after(row);
      row.querySelector("[data-cancel]").addEventListener("click", () => {
        row.remove();
        actions.hidden = false;
      });
      row.querySelectorAll("[data-c]").forEach((b) => {
        b.addEventListener("click", async () => {
          const paidRaw = row.querySelector("[data-add-paid]").value
            .trim().replace(",", ".");
          let paidPrice = null;
          if (paidRaw) {
            const n = Number(paidRaw);
            if (!Number.isFinite(n) || n < 0) {
              toast("Bezahlt bitte als Zahl, z. B. 4,50");
              return;
            }
            paidPrice = Math.round(n * 100) / 100;
          }
          b.disabled = true;
          try {
            const res = await api("/collection", { method: "POST", body: {
              item_id: it.item_id, item_type: it.item_type || "minifig",
              name: it.name, img_url: it.img_url,
              bricklink_url: it.bricklink_url,
              condition: b.dataset.c, paid_price: paidPrice,
            }});
            toast(res.merged
              ? tr("Schon vorhanden – Anzahl erhöht (jetzt {n}×)", { n: res.quantity })
              : `Zur Sammlung hinzugefügt ✔ (${b.dataset.c === "new" ? tr("Neu") : tr("Gebraucht")})`);
            row.remove();
            await askSetFigures(it, b.dataset.c);
            actions.hidden = false;
          } catch (e) {
            toast(e.message);
            b.disabled = false;
          }
        });
      });
    });
  });
}

/* ---------------------------------------------------------------- Sammlung */
async function loadCollection(showSpinner = false) {
  const q = $("search").value;
  const sort = $("sort").value;
  const typeFilter = $("type-filter").value;
  const list = $("collection-list");
  // Beim Öffnen des Tabs sofort eine Lade-Anzeige zeigen, damit die Sekunde
  // bis zum fertigen Aufbau nicht wie ein Hänger wirkt.
  if (showSpinner) {
    $("collection-empty").hidden = true;
    list.setAttribute("aria-busy", "true");
    list.innerHTML = brickLoading("Sammlung wird geladen …");
    // Dem Browser eine Bildaufbau-Runde geben, damit der Spinner sichtbar ist,
    // bevor der (bei großer Sammlung rechenintensive) Aufbau beginnt.
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  }
  try {
    const data = await api("/collection?q=" + encodeURIComponent(q)
      + "&sort=" + encodeURIComponent(sort)
      + "&item_type=" + encodeURIComponent(typeFilter));
    state.collection = data.items;
    $("stat-total").textContent = data.stats.total;
    $("stat-unique").textContent = data.stats.unique_items;
    $("stat-value").textContent = data.stats.total_value
      ? fmtEur(data.stats.total_value) : "–";
    $("stat-value-sub").textContent = data.stats.unpriced > 0
      ? tr("Wert · {n} ohne Preis", { n: data.stats.unpriced })
      : tr("Wert (BrickLink Ø)");
    renderCollection();
  } catch (e) {
    toast(e.message);
  } finally {
    list.removeAttribute("aria-busy");
  }
}

const ICON_LIST = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none"'
  + ' stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">'
  + '<path d="M8 6h13M8 12h13M8 18h13"/>'
  + '<circle cx="3.5" cy="6" r="1.3" fill="currentColor" stroke="none"/>'
  + '<circle cx="3.5" cy="12" r="1.3" fill="currentColor" stroke="none"/>'
  + '<circle cx="3.5" cy="18" r="1.3" fill="currentColor" stroke="none"/></svg>';
const ICON_GRID = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none"'
  + ' stroke="currentColor" stroke-width="2" aria-hidden="true">'
  + '<rect x="3" y="3" width="8" height="8" rx="1.5"/>'
  + '<rect x="13" y="3" width="8" height="8" rx="1.5"/>'
  + '<rect x="3" y="13" width="8" height="8" rx="1.5"/>'
  + '<rect x="13" y="13" width="8" height="8" rx="1.5"/></svg>';

function applyCollView() {
  const list = $("collection-list");
  const btn = $("btn-collview");
  const grid = localStorage.getItem("bf_collview") === "grid";
  if (list) list.classList.toggle("grid-mode", grid);
  if (btn) {
    // Zeigt Symbol und Namen der Ansicht, in die man wechselt
    btn.innerHTML = (grid ? ICON_LIST : ICON_GRID)
      + `<span class="vt-label">${grid ? "Liste" : "Raster"}</span>`;
    btn.title = grid ? "Zur Listenansicht wechseln"
                     : "Zur Rasteransicht wechseln";
    btn.setAttribute("aria-label", btn.title);
  }
}

function collCardDetails(it) {
  const needsBlNo = /^(fig-|manuell-|custom-)/.test(it.item_id);
  return `
      <div class="card-details" hidden>
        <div class="qty-edit">
          <span class="qty-edit-label">Anzahl</span>
          <div class="qty">
            <button data-qty="-1" class="${it.quantity <= 1 ? "qty-del" : ""}" aria-label="${esc(it.quantity <= 1 ? tr("Aus der Sammlung löschen") : tr("Anzahl verringern"))}">${it.quantity <= 1 ? TRASH_SVG : "−"}</button>
            <span data-qty-val>${it.quantity}</span>
            <button data-qty="1" aria-label="Anzahl erhöhen">＋</button>
          </div>
        </div>
        <label>Zustand</label>
        <div class="detail-row">
          <button class="mini-btn cond ${it.condition === "used" ? "sel" : ""}" data-cond="used">Gebraucht</button>
          <button class="mini-btn cond ${it.condition === "new" ? "sel" : ""}" data-cond="new">Neu</button>
        </div>
        ${state.user && state.user.is_dealer ? `
        <div class="paid-block">
          <div class="detail-row paid-row">
            <span class="paid-label">Bezahlt</span>
            <input data-paid class="paid-input" inputmode="decimal"
              placeholder="0,00" value="${fmtPaidInput(it.paid_price)}">
            <span class="paid-suffix" data-cur>${esc(curSymbol())} <span data-paid-src>${it.paid_price != null ? paidSrcIcon(it) : ""}</span></span>
            <button class="kauf-plus" data-kauf-neu
              title="Weiterer Kauf">＋</button>
          </div>
          <div class="kaufbuch" data-kaufbuch hidden></div>
          <div class="sub profit-line" data-profit>${profitLine(it)}</div>
        </div>` : ""}
        ${state.hubConnected ? `
        <label class="share-toggle">
          <input type="checkbox" data-share ${it.shared ? "checked" : ""}>
          🤝 In der Tauschbörse anbieten
        </label>` : ""}
        <label>Notizen <span class="notes-status" data-notes-status aria-live="polite"></span></label>
        <textarea data-notes placeholder="z. B. Zustand, Herkunft, Set …">${esc(it.notes)}</textarea>
        ${needsBlNo && state.bricklinkLookup ? `
        <label>BrickLink-Nr. setzen (für Preise & exakte Variante)</label>
        <div class="detail-row">
          <input data-fix-no placeholder="z. B. sw0815" autocapitalize="none" class="fix-input">
          <button class="mini-btn add" data-fix-btn>Übernehmen</button>
          ${it.img_url ? `<button class="mini-btn" data-fix-auto>🔍 Automatisch</button>` : ""}
        </div>` : ""}
        ${priceGuideUrl(it) || it.bricklink_url ? `
        <div class="detail-row btn-grid">
          ${priceGuideUrl(it) ? `<a class="mini-btn link" href="${esc(priceGuideUrl(it))}" target="_blank" rel="noopener">Preisverlauf ↗</a>` : ""}
          ${it.bricklink_url ? `<a class="mini-btn link" href="${esc(it.bricklink_url)}" target="_blank" rel="noopener">BrickLink ↗</a>` : ""}
        </div>` : ""}
        ${it.item_type === "set" && state.bricklinkPrices ? `
        <div class="detail-row">
          <button class="mini-btn" data-figs>👥 Enthaltene Figuren anzeigen</button>
        </div>
        <div class="set-figs" data-figs-out></div>` : ""}
        ${it.item_type === "minifig" && state.bricklinkPrices && !needsBlNo ? `
        <div class="detail-row">
          <button class="mini-btn" data-parts>🧩 Enthaltene Teile anzeigen</button>
        </div>
        <div class="set-figs" data-parts-out></div>` : ""}
        ${state.bricklinkPrices && !needsBlNo ? `
        <div class="price-head">
          <span>Marktpreise</span>
          <button class="icon-btn" data-price title="Preise jetzt aktualisieren" aria-label="Preise jetzt aktualisieren">↻</button>
        </div>` : ""}
        <div class="price-result" data-price-out></div>
        <div class="price-history" data-history></div>
        <div class="meta">Erfasst von ${esc(it.added_by_name || "unbekannt")} am ${new Date(it.added_at * 1000).toLocaleDateString(dateLocale())}</div>
      </div>`;
}

/* Kopf einer Sammlungs-Karte. Der (umfangreiche) Detailblock entsteht erst
   beim Aufklappen – das hält das DOM bei großen Sammlungen schlank. */
function collCardHtml(it) {
  return `
    <div class="card${it.img_url ? " has-bg" : ""}" data-id="${it.id}"${
      it.img_url ? ` data-bg="${imgSrc(it.img_url)}"` : ""}>
      <div class="card-head">
        <img class="card-img" src="${imgSrc(it.img_url)}" data-gid="${esc(it.item_id)}" data-gtype="${esc(it.item_type || "minifig")}" alt="" loading="lazy">
        <span class="qty-badge" data-qty-val>${it.quantity}</span>
        <div class="card-title">
          <strong>${esc(it.name)}</strong>
          <div class="sub" data-sub-id>${esc(collSubId(it))}</div>
          <div class="sub" data-sub>${esc(collSubMeta(it))}</div>
          ${setFigsText(it) ? `<div class="sub sub-figs">${esc(setFigsText(it))}</div>` : ""}
        </div>
        <div class="qty">
          <button data-qty="-1" class="${it.quantity <= 1 ? "qty-del" : ""}" aria-label="${esc(it.quantity <= 1 ? tr("Aus der Sammlung löschen") : tr("Anzahl verringern"))}">${it.quantity <= 1 ? TRASH_SVG : "−"}</button>
          <span data-qty-val>${it.quantity}</span>
          <button data-qty="1" aria-label="Anzahl erhöhen">＋</button>
        </div>
      </div>
    </div>`;
}

const THEME_NONE = "Ohne Thema";

function themeIcon(name) {
  if (name === THEME_NONE) return "❔";
  if (name === "Custom") return "🎨";       // wie der Schalter beim Erfassen
  return "🗂️";
}

/* Zugeklappte Themen merken, damit die Ansicht nach dem Neuladen bleibt. */
function collapsedThemes() {
  try {
    return new Set(JSON.parse(localStorage.getItem("bf_themes_closed") || "[]"));
  } catch (_) { return new Set(); }
}

function storeCollapsedThemes(set) {
  localStorage.setItem("bf_themes_closed", JSON.stringify([...set]));
}

/* Bei Sortierung „Thema" wird nach Thema gruppiert – jede Gruppe eine
   aufklappbare Karte mit Stückzahl und Wert. */
function renderThemeGroups(list, items) {
  const groups = [];
  const byName = new Map();
  items.forEach((it) => {
    const key = it.theme || THEME_NONE;
    let g = byName.get(key);
    if (!g) { g = { name: key, items: [], pieces: 0, value: 0 }; byName.set(key, g); groups.push(g); }
    g.items.push(it);
    g.pieces += it.quantity;
    // net_value kommt vom Server und folgt derselben Regel wie die Kopfsumme:
    // Figuren, die in eigenen Sets stecken, zählen nicht doppelt.
    if (it.net_value) g.value += it.net_value;
  });

  const closed = collapsedThemes();
  themenGruppen = groups;
  list.innerHTML = groups.map((g, gi) => {
    const isClosed = closed.has(g.name);
    return `
    <section class="theme-group${isClosed ? " closed" : ""}" data-theme="${esc(g.name)}" data-gruppe="${gi}">
      <button class="theme-head" aria-expanded="${!isClosed}">
        <span class="theme-caret" aria-hidden="true">▾</span>
        <span class="theme-name">${themeIcon(g.name)} ${esc(g.name)}</span>
        <span class="theme-count">${esc(g.items.length === 1
          ? tr("1 Eintrag") : tr("{n} Einträge", { n: g.items.length }))}${
          g.pieces !== g.items.length
            ? esc(tr(" · {n} Stück", { n: g.pieces })) : ""}${
          g.value > 0 ? ` · ${fmtEur(g.value)}` : ""}</span>
      </button>
      <div class="theme-body">${g.name === THEME_NONE
        ? `<p class="search-hint">${esc(tr("Für diese Einträge ist noch kein "
          + "Thema bestimmt."))} <button class="mini-btn" data-theme-fix>`
          + `${esc(tr("🔄 Themen nachladen"))}</button></p>` : ""}</div>
    </section>`;
    // Platzhalterhöhe, solange die Karten fehlen. Ohne sie stehen alle
    // Gruppen übereinander auf einem Fleck, liegen damit alle im
    // Sichtbereich – und füllen sich sofort alle auf einmal.
  }).join("");

  // Die Karten einer Gruppe entstehen erst, wenn die Gruppe zu sehen ist.
  // Zugeklappte Gruppen sind unsichtbar und kosten damit gar nichts – vorher
  // steckten auch sie mit allen Karten im Dokument.
  const koerper = [...list.querySelectorAll(".theme-body")];
  const proKarte = list.classList.contains("grid-mode") ? 65 : 104;
  koerper.forEach((b) => {
    const g = groups[Number(b.closest(".theme-group").dataset.gruppe)];
    if (g) b.style.minHeight = (g.items.length * proKarte) + "px";
  });
  if ("IntersectionObserver" in window) {
    nachschubBeobachter = new IntersectionObserver((eintraege) => {
      eintraege.forEach((e) => { if (e.isIntersecting) gruppeFuellen(e.target); });
    }, { rootMargin: "800px 0px" });
    koerper.forEach((b) => nachschubBeobachter.observe(b));
  } else koerper.forEach(gruppeFuellen);

  // Der Knopf steckte bisher nur unter „Mehr → Sortierung" – also weit weg
  // von der Stelle, an der die Lücke auffällt.
  list.querySelectorAll("[data-theme-fix]").forEach((b) => {
    b.addEventListener("click", (ev) => {
      ev.stopPropagation();
      refreshThemes();
    });
  });

  list.querySelectorAll(".theme-head").forEach((head) => {
    head.addEventListener("click", () => {
      const sec = head.closest(".theme-group");
      const name = sec.dataset.theme;
      const nowClosed = !sec.classList.contains("closed");
      sec.classList.toggle("closed", nowClosed);
      head.setAttribute("aria-expanded", String(!nowClosed));
      const set = collapsedThemes();
      nowClosed ? set.add(name) : set.delete(name);
      storeCollapsedThemes(set);
      if (!nowClosed) gruppeFuellen(sec.querySelector(".theme-body"));
    });
  });
}

/* Karten einer Themengruppe nachreichen – einmal je Gruppe. */
let themenGruppen = [];

function gruppeFuellen(body) {
  if (!body || body.dataset.gefuellt) return;
  const sec = body.closest(".theme-group");
  const g = themenGruppen[Number(sec && sec.dataset.gruppe)];
  if (!g) return;
  body.dataset.gefuellt = "1";
  body.style.minHeight = "";        // ab jetzt tragen die Karten die Höhe
  const huelle = document.createElement("div");
  huelle.innerHTML = g.items.map(collCardHtml).join("");
  [...huelle.children].forEach((c) => {
    body.appendChild(c);
    karteVerdrahten(c, state.collection);
    if (bgBeobachter && c.dataset.bg) bgBeobachter.observe(c);
  });
}

function renderCollection() {
  closeCardModal();     // ein offenes Popup gehört zu den alten Karten
  const list = $("collection-list");
  const items = state.collection;
  applyCollView();
  const gesucht = $("search").value.trim() !== "" || $("type-filter").value !== "";
  $("collection-empty").hidden = items.length > 0 || gesucht;
  const grouped = $("sort").value === "theme" && items.length > 0;
  list.classList.toggle("by-theme", grouped);
  nachschubBeenden();
  hintergrundBeobachten(list);      // erst der Beobachter, dann die Karten
  if (grouped) renderThemeGroups(list, items);
  else if (!items.length && gesucht) {
    // Vorher blieb hier eine leere Fläche: keine Karten, kein Hinweis –
    // man wusste nicht, ob nichts passt oder noch geladen wird.
    list.innerHTML = `<p class="empty">${esc(tr("Nichts gefunden."))}<br>`
      + `${esc(tr("Andere Schreibweise probieren oder die Filter zurücksetzen."))}`
      + ` <button class="mini-btn" data-filter-reset>${esc(tr("Filter zurücksetzen"))}</button></p>`;
    list.querySelector("[data-filter-reset]").addEventListener("click", () => {
      $("search").value = "";
      $("type-filter").value = "";
      loadCollection();
    });
  } else {
    list.innerHTML = "";
    kartenNachschub(list, items);
    return;                          // verdrahtet wird blockweise
  }

  list.querySelectorAll(".card").forEach((card) => karteVerdrahten(card, items));
}

/* Karten kommen blockweise ins Dokument.

   Bis hierher entstanden beim Öffnen der Sammlung alle Karten auf einmal:
   gemessen 14.697 Elemente und 837 Bilder in einem Rutsch, bei 815
   Einträgen. Der JS-Speicher blieb dabei klein – entpackte Bilder liegen
   außerhalb, und genau daran ist der Tab wiederholt gestorben.

   Jetzt steht am Ende der Liste eine Marke. Kommt sie in die Nähe des
   Fensters, wird der nächste Block angehängt. Wer oben bleibt, hat nie mehr
   als einen Block im Dokument; wer durchscrollt, bekommt sie nach und nach
   statt alle gleichzeitig. */
const KARTEN_BLOCK = 60;
let nachschubBeobachter = null;
let nachschubLaden = null;        // hängt den nächsten Block an

function nachschubBeenden() {
  if (nachschubBeobachter) {
    nachschubBeobachter.disconnect();
    nachschubBeobachter = null;
  }
  nachschubLaden = null;
}

function kartenNachschub(list, items) {
  let gezeigt = 0;
  const marke = document.createElement("div");
  marke.className = "nachschub-marke";
  list.appendChild(marke);

  const block = () => {
    const teil = items.slice(gezeigt, gezeigt + KARTEN_BLOCK);
    if (!teil.length) { fertig(); return; }
    const huelle = document.createElement("div");
    huelle.innerHTML = teil.map(collCardHtml).join("");
    const neue = [...huelle.children];
    neue.forEach((c) => list.insertBefore(c, marke));
    gezeigt += teil.length;
    neue.forEach((c) => {
      karteVerdrahten(c, items);
      if (bgBeobachter && c.dataset.bg) bgBeobachter.observe(c);
    });
    if (gezeigt >= items.length) fertig();
  };

  const fertig = () => { nachschubBeenden(); marke.remove(); };

  // `nachschub` gehört zur Liste, nicht zum Fenster: In der Rasteransicht
  // liegt die Marke sonst neben den Karten statt darunter.
  nachschubBeobachter = new IntersectionObserver((eintraege) => {
    if (eintraege.some((e) => e.isIntersecting)) block();
  }, { rootMargin: "1200px 0px" });

  nachschubLaden = block;
  block();                       // der erste Block sofort
  if (nachschubBeobachter) nachschubBeobachter.observe(marke);
}

/* Sorgt dafür, dass ein bestimmter Eintrag wirklich im Dokument steht –
   für den Sprung zu einem Set, das weiter hinten liegt. */
function karteSicherstellen(id) {
  const list = $("collection-list");
  const da = () => list.querySelector(`[data-id="${id}"]`);
  let schutz = 500;               // gegen eine Endlosschleife bei Unfug
  while (!da() && nachschubLaden && schutz-- > 0) nachschubLaden();
  // Nach Thema gruppiert gibt es keine Blöcke, sondern Gruppen – dann eben
  // alle aufmachen, bis der Eintrag dabei ist.
  if (!da()) {
    for (const b of list.querySelectorAll(".theme-body")) {
      gruppeFuellen(b);
      if (da()) break;
    }
  }
  return !!da();
}

/* Verdrahtung einer einzelnen Karte. Stand früher als Rumpf einer Schleife
   über *alle* Karten hier – das ging nur, solange alle auf einmal im
   Dokument standen. */
function karteVerdrahten(card, items) {
  {
    const id = Number(card.dataset.id);
    const item = items.find((i) => i.id === id);
    const canPrice = state.bricklinkPrices && !/^(fig-|manuell-|custom-)/.test(item.item_id);

    const deleteEntry = async () => {
      if (!confirm(tr("„{name}“ wirklich löschen?", { name: item.name }))) return;
      try {
        // Erst fragen (solange das Set noch da ist), dann löschen
        await askRemoveSetFigures(item);
        await api("/collection/" + id, { method: "DELETE" });
        loadCollection();
      } catch (e) { toast(e.message); }
    };

    // Mengen-Knöpfe verdrahten (im Kopf sofort, im Detailbereich nach dem
    // Aufklappen). `root` grenzt ein, welche Knöpfe gemeint sind.
    const wireQty = (root) => {
      // Aktualisiert wird die Karte, in der der Knopf sitzt – die Listen-Karte
      // oder (beim Popup) die Karte im Overlay.
      const scope = root.closest(".card") || root;
      root.querySelectorAll("[data-qty]").forEach((btn) => {
        btn.addEventListener("click", async (ev) => {
          ev.stopPropagation();
          const step = Number(btn.dataset.qty);
          // Letztes Exemplar: derselbe Ablauf wie der Löschen-Knopf
          if (step < 0 && item.quantity <= 1) { await deleteEntry(); return; }
          const newQty = item.quantity + step;
          if (newQty < 1) return;
          try {
            await api("/collection/" + id, { method: "PATCH", body: { quantity: newQty } });
            item.quantity = newQty;
            scope.querySelectorAll("[data-qty-val]").forEach((s) => {
              s.textContent = newQty;
            });
            // Minus-Knopf wird zum Papierkorb, sobald nur noch eines übrig ist
            scope.querySelectorAll('[data-qty="-1"]').forEach((b) => {
              b.innerHTML = newQty <= 1 ? TRASH_SVG : "−";
              b.classList.toggle("qty-del", newQty <= 1);
              b.setAttribute("aria-label", newQty <= 1
                ? tr("Aus der Sammlung löschen") : tr("Anzahl verringern"));
            });
            updateStatsOnly();
          } catch (e) { toast(e.message); }
        });
      });
    };

    card.querySelectorAll("[data-jump-set]").forEach((b) => {
      b.addEventListener("click", (ev) => {
        ev.stopPropagation();
        jumpToSet(b.dataset.jumpSet);
      });
    });

    const moreBtn = card.querySelector("[data-more-sets]");
    if (moreBtn) {
      moreBtn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const span = card.querySelector(".more-sets");
        span.hidden = !span.hidden;
        moreBtn.textContent = span.hidden
          ? `+${span.querySelectorAll(".set-link").length} weitere ▾`
          : "weniger ▴";
      });
    }

    wireQty(card.querySelector(".card-head"));

    card.querySelector(".card-head").addEventListener("click", (ev) => {
      if (ev.target.closest(".qty") || ev.target.closest(".card-img")
          || ev.target.closest(".set-link")) return;
      openCardModal(item, id, card, deleteEntry, wireQty, canPrice);
    });
  }
}

/* Der weiche Hintergrund ist der teuerste Teil einer Karte: ein zweites Bild
   pro Eintrag – und für CSS-Hintergründe gibt es kein `loading="lazy"`. Bei
   815 Einträgen wurden dadurch beim Öffnen der Sammlung 815 Bilder auf einmal
   geholt (gemessen), zusätzlich zu den ausgelieferten der Karten. Der
   JS-Speicher blieb dabei unauffällig – das Bildmaterial liegt außerhalb, und
   genau daran ist der Tab gestorben.

   Jetzt bekommt eine Karte ihr Hintergrundbild erst, wenn sie in die Nähe des
   Fensters kommt, und gibt es wieder her, sobald sie weit weg ist. Damit sind
   nie mehr als eine Handvoll gleichzeitig im Speicher. */
let bgBeobachter = null;

function cssUrl(url) {
  return `url("${String(url).replace(/["\\]/g, "\\$&")}")`;
}

function hintergrundBeobachten(root) {
  if (bgBeobachter) bgBeobachter.disconnect();
  if (!("IntersectionObserver" in window)) {
    // Ohne Beobachter lieber gar kein Hintergrund als alle auf einmal
    return;
  }
  bgBeobachter = new IntersectionObserver((eintraege) => {
    eintraege.forEach((e) => {
      const url = e.target.dataset.bg;
      if (!url) return;
      if (e.isIntersecting) e.target.style.setProperty("--bg-img", cssUrl(url));
      else e.target.style.removeProperty("--bg-img");
    });
  }, { rootMargin: "800px 0px" });
  root.querySelectorAll(".card[data-bg]").forEach((c) => bgBeobachter.observe(c));
}

/* Detailansicht als Popup. Enthält Kopf UND Details, damit die bestehende
   Verdrahtung (die sich auf `.card-head .sub`, `[data-price-out]` … stützt)
   unverändert funktioniert – die Popup-Karte ist einfach die „card". */
let cardModalKeyHandler = null;

function closeCardModal() {
  const m = document.getElementById("card-modal");
  if (m) m.remove();
  if (cardModalKeyHandler) {
    document.removeEventListener("keydown", cardModalKeyHandler);
    cardModalKeyHandler = null;
  }
}

function openCardModal(item, id, listCard, deleteEntry, wireQty, canPrice) {
  closeCardModal();
  const overlay = document.createElement("div");
  overlay.className = "card-modal-overlay";
  overlay.id = "card-modal";
  overlay.innerHTML = `
    <div class="card-modal">
      <button class="card-modal-close" aria-label="Schließen">✕</button>
      <div class="card modal-inner open" role="dialog" aria-modal="true">
        <div class="card-head">
          <div class="card-img-wrap">
            <img class="card-img" src="${imgSrc(item.img_url)}" data-gid="${esc(item.item_id)}" data-gtype="${esc(item.item_type || "minifig")}" alt="">
            ${state.bricklinkLookup && !/^(fig-|manuell-|custom-)/.test(item.item_id) ? `<button class="img-reload-btn" data-img-reload title="${item.img_url ? "Bild erneuern" : "Bild nachladen"}" aria-label="Bild erneuern">↻</button>` : ""}
          </div>
          <span class="qty-badge" data-qty-val>${item.quantity}</span>
          <div class="card-title">
            <strong>${esc(item.name)}</strong>
            <div class="sub" data-sub-id>${esc(collSubId(item))}</div>
            <div class="sub" data-sub>${esc(collSubMeta(item))}</div>
            ${setFigsText(item) ? `<div class="sub sub-figs">${esc(setFigsText(item))}</div>` : ""}
            ${(item.in_sets || item.item_type === "minifig") ? `<div class="sub in-sets" data-fig-sets hidden></div>` : ""}
          </div>
          <div class="qty">
            <button data-qty="-1" class="${item.quantity <= 1 ? "qty-del" : ""}" aria-label="${esc(item.quantity <= 1 ? tr("Aus der Sammlung löschen") : tr("Anzahl verringern"))}">${item.quantity <= 1 ? TRASH_SVG : "−"}</button>
            <span data-qty-val>${item.quantity}</span>
            <button data-qty="1" aria-label="Anzahl erhöhen">＋</button>
          </div>
        </div>
        ${collCardDetails(item)}
      </div>
    </div>`;
  document.body.appendChild(overlay);
  const inner = overlay.querySelector(".modal-inner");
  inner.querySelector(".card-details").hidden = false;

  // Verdrahtung – `inner` ist die „card"
  wireQty(inner.querySelector(".card-head"));
  wireCollectionDetails(inner, item, id, deleteEntry, wireQty);
  // „Kommt vor in"-Sets (eigene sofort, alle von BrickLink nach)
  renderFigSets(inner, item);
  if (canPrice) loadEntryPrice(inner, item, false);

  const done = () => {
    // Noch nicht gespeicherte Notiz vor dem Schließen sichern
    const n = inner.querySelector("[data-notes]");
    if (n && n._flushNotes) n._flushNotes();
    // Die Listen-Karte aus dem (in place geänderten) item nachziehen, damit
    // Zustand/Menge/Preis dort stimmen, ohne die ganze Liste neu zu laden.
    if (listCard && listCard.isConnected) {
      const sub = listCard.querySelector("[data-sub]");
      if (sub) sub.textContent = collSubMeta(item);
      listCard.querySelectorAll("[data-qty-val]").forEach((s) => {
        s.textContent = item.quantity;
      });
      listCard.querySelectorAll('[data-qty="-1"]').forEach((b) => {
        b.innerHTML = item.quantity <= 1 ? TRASH_SVG : "−";
        b.classList.toggle("qty-del", item.quantity <= 1);
      });
    }
    closeCardModal();
  };
  overlay.querySelector(".card-modal-close").addEventListener("click", done);
  overlay.addEventListener("click", (ev) => { if (ev.target === overlay) done(); });
  cardModalKeyHandler = (ev) => { if (ev.key === "Escape") done(); };
  document.addEventListener("keydown", cardModalKeyHandler);
}

/* ------------------------------------------------------- App-Dialog

   `prompt()` des Browsers passt zu nichts: eigene Schrift, eigene Farben,
   in der App vom Startbildschirm ein Fremdkörper – und für zwei Angaben
   braucht es zwei Fenster hintereinander. Dieser Dialog fragt alles auf
   einmal, im Stil der App, und liefert die Werte als Objekt (oder `null`,
   wenn abgebrochen wurde).

   `felder` ist eine Liste: { name, label, typ, wert, platzhalter, pflicht }
*/
function appDialog({ titel, text = "", felder = [], ok = "Übernehmen" }) {
  return new Promise((fertig) => {
    const alt = document.getElementById("app-dialog");
    if (alt) alt.remove();
    const overlay = document.createElement("div");
    overlay.className = "card-modal-overlay stacked";
    overlay.id = "app-dialog";
    overlay.innerHTML = `
      <div class="card-modal">
        <button class="card-modal-close" data-abbruch aria-label="${esc(tr("Schließen"))}">✕</button>
        <div class="card modal-inner open" role="dialog" aria-modal="true">
          <h3 style="margin:0 0 6px">${esc(titel)}</h3>
          ${text ? `<p class="search-hint">${esc(text)}</p>` : ""}
          ${felder.map((f) => `
            <label for="dlg-${esc(f.name)}">${esc(f.label)}</label>
            <input id="dlg-${esc(f.name)}" data-feld="${esc(f.name)}"
              type="${esc(f.typ === "zahl" ? "text" : f.typ || "text")}"
              ${f.typ === "zahl" ? 'inputmode="decimal"' : ""}
              value="${esc(f.wert == null ? "" : f.wert)}"
              placeholder="${esc(f.platzhalter || "")}"
              maxlength="${Number(f.max) || 200}">`).join("")}
          <div class="detail-row btn-grid">
            <button class="mini-btn add" data-ok>${esc(ok)}</button>
            <button class="mini-btn" data-abbruch>${esc(tr("Abbrechen"))}</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(overlay);

    const werte = () => {
      const d = {};
      overlay.querySelectorAll("[data-feld]").forEach((e) => {
        d[e.dataset.feld] = e.value.trim();
      });
      return d;
    };
    const schliessen = (ergebnis) => {
      document.removeEventListener("keydown", taste);
      overlay.remove();
      fertig(ergebnis);
    };
    const bestaetigen = () => {
      const d = werte();
      const fehlt = felder.find((f) => f.pflicht && !d[f.name]);
      if (fehlt) {
        const e = overlay.querySelector(`[data-feld="${fehlt.name}"]`);
        e.focus();
        e.classList.add("feld-fehlt");
        setTimeout(() => e.classList.remove("feld-fehlt"), 1200);
        return;
      }
      schliessen(d);
    };
    const taste = (ev) => {
      if (ev.key === "Escape") schliessen(null);
      if (ev.key === "Enter" && ev.target.matches("[data-feld]")) {
        ev.preventDefault();
        bestaetigen();
      }
    };
    overlay.querySelectorAll("[data-abbruch]").forEach((b) =>
      b.addEventListener("click", () => schliessen(null)));
    overlay.querySelector("[data-ok]").addEventListener("click", bestaetigen);
    overlay.addEventListener("click", (ev) => {
      if (ev.target === overlay) schliessen(null);
    });
    document.addEventListener("keydown", taste);
    const erstes = overlay.querySelector("[data-feld]");
    if (erstes) setTimeout(() => erstes.focus(), 50);
  });
}

/* Betrag aus einem Feld lesen – Komma wie Punkt. */
function betragLesen(text) {
  const n = Number(String(text || "").replace(",", ".").trim());
  return Number.isFinite(n) && n >= 0 ? n : null;
}

/* Kaufbuch einer Karte: die einzelnen Käufe hinter der Summe.

   Zwei gleiche Sets liegen in einer Zeile – „einmal 39,99 bei LEGO, einmal
   34,99 im Markt" ging dabei verloren. Oben steht weiterhin die Summe, hier
   die Posten dazu. */
async function kaufbuchLaden(card, item, id) {
  const box = card.querySelector("[data-kaufbuch]");
  const knopf = card.querySelector("[data-kauf-neu]");
  if (!box || !knopf) return;
  let kaeufe = [];
  try {
    kaeufe = (await api(`/collection/${id}/purchases`)).purchases || [];
  } catch (_) { return; }

  // Ein einzelner Posten sagt nichts, was nicht schon oben steht.
  box.hidden = kaeufe.length < 2;
  box.innerHTML = kaeufe.map((k) => `
    <div class="kauf-zeile" data-kauf="${k.id}">
      <span class="kauf-menge">${k.quantity}×</span>
      <span class="kauf-preis">${k.unit_price != null ? fmtEur(k.unit_price) : "–"}</span>
      <span class="kauf-quelle">${esc(kaufQuelle(k))}</span>
      <button class="kauf-weg" aria-label="${esc(tr("Kauf zurücknehmen"))}">✕</button>
    </div>`).join("");

  box.querySelectorAll("[data-kauf]").forEach((zeile) => {
    zeile.querySelector(".kauf-weg").addEventListener("click", async (ev) => {
      ev.stopPropagation();
      if (!confirm(tr("Diesen Kauf zurücknehmen? Die Stückzahl geht mit zurück."))) return;
      try {
        const r = await api(`/collection/${id}/purchases/${zeile.dataset.kauf}`,
          { method: "DELETE" });
        kaufStandUebernehmen(card, item, r);
        kaufbuchLaden(card, item, id);
      } catch (e) { toast(e.message); }
    });
  });

  if (knopf.dataset.wired) return;
  knopf.dataset.wired = "1";
  knopf.addEventListener("click", async (ev) => {
    ev.stopPropagation();
    const d = await appDialog({
      titel: tr("Weiterer Kauf"),
      text: tr("Dasselbe noch einmal woanders gekauft? Der Betrag gilt für "
        + "diesen Kauf, die Stückzahl wächst mit."),
      felder: [
        { name: "preis", label: tr("Gesamtpreis"), typ: "zahl",
          platzhalter: "34,99", pflicht: true },
        { name: "menge", label: tr("Stückzahl"), typ: "zahl", wert: "1" },
        { name: "quelle", label: tr("Wo gekauft? (frei lassen, wenn egal)"),
          platzhalter: "MediaMarkt", max: 80 },
      ],
      ok: tr("Kauf eintragen"),
    });
    if (!d) return;
    const betrag = betragLesen(d.preis);
    if (betrag == null) { toast(tr("Das ist kein Betrag.")); return; }
    const menge = Math.max(1, Math.round(Number(d.menge) || 1));
    try {
      const r = await api(`/collection/${id}/purchases`, { method: "POST",
        body: { quantity: menge, price: betrag, source: d.quelle.slice(0, 80) } });
      kaufStandUebernehmen(card, item, r);
      kaufbuchLaden(card, item, id);
      toast(tr("Kauf eingetragen ✔"));
    } catch (e) { toast(e.message); }
  });
}

/* Quelle lesbar machen – die internen Kürzel sagen niemandem etwas. */
function kaufQuelle(k) {
  const wann = k.bought_at
    ? new Date(k.bought_at * 1000).toLocaleDateString(dateLocale()) : "";
  const q = { manual: "", auto: tr("geschätzt"), CSV_IMPORT: "" }[k.source]
    ?? k.source;
  return [q, wann].filter(Boolean).join(" · ");
}

/* Stückzahl und Summe nach einem Kauf überall in der Karte nachziehen. */
function kaufStandUebernehmen(card, item, r) {
  if (r.quantity != null) {
    item.quantity = r.quantity;
    card.querySelectorAll("[data-qty-val]").forEach((s) => {
      s.textContent = r.quantity;
    });
  }
  if ("paid_price" in r) {
    item.paid_price = r.paid_price;
    const feld = card.querySelector("[data-paid]");
    if (feld) feld.value = fmtPaidInput(r.paid_price);
    const gewinn = card.querySelector("[data-profit]");
    if (gewinn) gewinn.innerHTML = profitLine(item);
  }
  updateStatsOnly();
}

function wireCollectionDetails(card, item, id, deleteEntry, wireQty) {
  const details = card.querySelector(".card-details");

  details.querySelectorAll("[data-cond]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const cond = btn.dataset.cond;
      if (cond === item.condition) return;
      try {
        const res = await api("/collection/" + id, { method: "PATCH",
          body: { condition: cond } });
        if (res.merged) {
          toast("Mit dem vorhandenen Eintrag in diesem Zustand "
            + "zusammengeführt ✔");
          loadCollection();
          return;
        }
        item.condition = cond;
        card.querySelectorAll("[data-cond]").forEach((b) =>
          b.classList.toggle("sel", b.dataset.cond === cond));
        const sub = card.querySelector(".card-head [data-sub]");
        if (sub) sub.textContent = collSubMeta(item);
        updateStatsOnly();
        toast(cond === "new" ? "Zustand: Neu ✔" : "Zustand: Gebraucht ✔");
      } catch (e) { toast(e.message); }
    });
  });

  wireQty(details);

  // Kaufpreis speichert sich beim Verlassen des Feldes (oder mit Enter),
  // kein eigener Knopf mehr. Nur bei echter Änderung wird gespeichert.
  const paidEl = card.querySelector("[data-paid]");
  if (paidEl) {
    let paidSaved = fmtPaidInput(item.paid_price);
    const savePaid = async () => {
      const raw = paidEl.value.trim();
      if (raw === paidSaved.trim()) return;         // nichts geändert
      const num = raw === "" ? null : Number(raw.replace(",", "."));
      if (raw !== "" && (!isFinite(num) || num < 0)) {
        toast("Bitte einen gültigen Betrag eingeben");
        paidEl.value = paidSaved;                   // ungültig → zurücksetzen
        return;
      }
      try {
        await api("/collection/" + id, { method: "PATCH",
          body: { paid_price: num } });
        item.paid_price = num;
        item.paid_source = num == null ? "auto" : "manual";
        item.paid_at = Math.floor(Date.now() / 1000);
        paidEl.value = fmtPaidInput(num);
        paidSaved = paidEl.value;
        card.querySelector("[data-paid-src]").innerHTML =
          num != null ? paidSrcIcon(item) : "";
        card.querySelector("[data-profit]").innerHTML = profitLine(item);
      } catch (e) { toast(e.message); }
    };
    paidEl.addEventListener("blur", savePaid);
    paidEl.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") { ev.preventDefault(); paidEl.blur(); }
    });
    kaufbuchLaden(card, item, id);
  }

  const shareBox = card.querySelector("[data-share]");
  if (shareBox) {
    shareBox.addEventListener("change", async () => {
      const want = shareBox.checked;
      shareBox.disabled = true;
      try {
        await api(`/collection/${id}/share`, { method: "POST",
          body: { shared: want } });
        item.shared = want ? 1 : 0;
        toast(want ? "Kommt in die Tauschbörse 🤝"
                   : "Aus der Tauschbörse genommen");
      } catch (e) {
        shareBox.checked = !want;
        toast(e.message);
      } finally { shareBox.disabled = false; }
    });
  }

  const figsBtn = card.querySelector("[data-figs]");
  if (figsBtn) {
    figsBtn.addEventListener("click", () => loadSetFigs(card, item, figsBtn));
  }

  const partsBtn = card.querySelector("[data-parts]");
  if (partsBtn) {
    partsBtn.addEventListener("click", () => loadFigParts(card, item, partsBtn));
  }

  const fixAutoBtn = card.querySelector("[data-fix-auto]");
  if (fixAutoBtn) {
    fixAutoBtn.addEventListener("click", async () => {
      fixAutoBtn.disabled = true;
      fixAutoBtn.textContent = tr("Suche …");
      try {
        const data = await api("/resolve", { method: "POST",
          body: { img_url: item.img_url } });
        const filtered = (data.items || [])
          .filter((c) => !c.item_type || c.item_type === item.item_type);
        const best = filtered[0] || (data.items || [])[0];
        if (!best) {
          toast("Keine BrickLink-Nummer gefunden – bitte manuell eintragen");
          return;
        }
        await api("/collection/" + id, { method: "PATCH", body: {
          item_id: best.item_id, name: best.name,
          img_url: best.img_url || item.img_url,
          bricklink_url: best.bricklink_url || "",
        }});
        toast(tr("Gefunden: {name} ({id}, {score} % sicher) ✔",
      { name: best.name, id: best.item_id, score: best.score }));
        loadCollection();
      } catch (e) {
        toast(e.message);
      } finally {
        fixAutoBtn.disabled = false;
        fixAutoBtn.textContent = tr("🔍 Automatisch");
      }
    });
  }

  const fixBtn = card.querySelector("[data-fix-btn]");
  if (fixBtn) {
    fixBtn.addEventListener("click", async () => {
      const no = card.querySelector("[data-fix-no]").value.trim();
      if (!no) return;
      fixBtn.disabled = true;
      try {
        const found = await api(`/lookup/${item.item_type}/${encodeURIComponent(no)}`);
        await api("/collection/" + id, { method: "PATCH", body: {
          item_id: found.item_id, name: found.name,
          img_url: found.img_url, bricklink_url: found.bricklink_url,
          year: found.year || 0,
        }});
        toast(tr("Aktualisiert: {name} ({id}) ✔",
      { name: found.name, id: found.item_id }));
        loadCollection();
      } catch (e) {
        toast(e.message);
      } finally {
        fixBtn.disabled = false;
      }
    });
  }

  // Notizen speichern sich von selbst – kurz nach dem Tippen und beim
  // Verlassen des Feldes; kein eigener Knopf mehr nötig.
  const notesEl = card.querySelector("[data-notes]");
  if (notesEl) {
    const status = card.querySelector("[data-notes-status]");
    let saved = item.notes || "";
    let timer = null;
    const save = async () => {
      clearTimeout(timer);
      const val = notesEl.value;
      if (val === saved) return;
      try {
        await api("/collection/" + id, { method: "PATCH", body: { notes: val } });
        saved = val; item.notes = val;
        if (status) {
          status.textContent = "✓ gespeichert";
          status.classList.add("show");
          setTimeout(() => status.classList.remove("show"), 1600);
        }
      } catch (e) { toast(e.message); }
    };
    notesEl.addEventListener("input", () => {
      if (status) status.classList.remove("show");
      clearTimeout(timer);
      timer = setTimeout(save, 800);
    });
    notesEl.addEventListener("blur", save);
    notesEl._flushNotes = save;     // beim Schließen des Popups nachziehen
  }

  const delBtn = card.querySelector("[data-delete]");
  if (delBtn) delBtn.addEventListener("click", deleteEntry);

  const priceBtn = card.querySelector("[data-price]");
  if (priceBtn) {
    priceBtn.addEventListener("click", async () => {
      priceBtn.disabled = true;
      priceBtn.classList.add("spin");
      try { await loadEntryPrice(card, item, true); }
      finally { priceBtn.disabled = false; priceBtn.classList.remove("spin"); }
    });
  }

  // Bild fehlt oder ist falsch: frisch von BrickLink holen (↻ am Bild)
  const imgBtn = card.querySelector("[data-img-reload]");
  if (imgBtn) {
    imgBtn.addEventListener("click", async () => {
      imgBtn.disabled = true;
      imgBtn.classList.add("spin");
      try {
        const found = await api(`/lookup/${item.item_type}/`
          + encodeURIComponent(item.item_id));
        if (!found.img_url) {
          toast("BrickLink hat zu dieser Nummer kein Bild");
          return;
        }
        await api("/collection/" + id, { method: "PATCH",
          body: { img_url: found.img_url } });
        item.img_url = found.img_url;
        const img = card.querySelector(".card-img");
        if (img) img.src = found.img_url;
        toast("Bild aktualisiert ✔");
      } catch (e) {
        toast(e.message);
      } finally {
        imgBtn.disabled = false;
        imgBtn.classList.remove("spin");
      }
    });
  }
}

async function loadEntryPrice(card, item, refresh) {
  const out = card.querySelector("[data-price-out]");
  out.textContent = refresh ? "Hole frische Preise von BrickLink …" : "Lade Preise …";
  try {
    const p = await api(`/collection/${item.id}/price${refresh ? "?refresh=1" : ""}`);
    if (!refresh && !p.updated_at) {
      // frisch erfasste Figur, Hintergrund-Abruf noch nicht durch → einmal live holen
      return loadEntryPrice(card, item, true);
    }
    const stand = p.updated_at
      ? new Date(p.updated_at * 1000).toLocaleDateString(dateLocale()) : "";
    out.innerHTML = priceLine(tr("Neu"), p.new) + priceLine(tr("Gebraucht"), p.used)
      + `<div class="price-note">`
      + esc(tr("Ø-Verkaufspreise, letzte 6 Monate (BrickLink)"))
      + `${stand ? esc(tr(" · Stand {d}", { d: stand })) : ""}</div>`;
    // Frische Preise sofort in Karte und Rechnung übernehmen
    if (p.new && p.new.avg != null) item.price_new = p.new.avg;
    if (p.used && p.used.avg != null) item.price_used = p.used.avg;
    const subEl = card.querySelector("[data-sub]");
    if (subEl) subEl.textContent = collSubMeta(item);
    const profitEl = card.querySelector("[data-profit]");
    if (profitEl) profitEl.innerHTML = profitLine(item);
    if (refresh) updateStatsOnly();   // Wert-Widget mitziehen
    loadPriceHistory(card, item);
  } catch (e) {
    out.textContent = e.message;
  }
}

async function loadPriceHistory(card, item) {
  const box = card.querySelector("[data-history]");
  if (!box) return;
  try {
    const data = await api(`/history/${encodeURIComponent(item.item_type)}/${encodeURIComponent(item.item_id)}`);
    const pts = (data.points || []).filter((p) => p.price_new || p.price_used);
    box.innerHTML = pts.length >= 2 ? historyChart(pts)
      : (pts.length === 1
         ? `<div class="price-note">Preisverlauf: Aufzeichnung gestartet – Chart erscheint, sobald weitere Datenpunkte vorliegen.</div>`
         : "");
  } catch (_) { box.innerHTML = ""; }
}

function historyChart(pts) {
  const w = 560, h = 130, padX = 8, padT = 10, padB = 22;
  const values = [];
  pts.forEach((p) => {
    if (p.price_new) values.push(p.price_new);
    if (p.price_used) values.push(p.price_used);
  });
  let lo = Math.min(...values), hi = Math.max(...values);
  if (hi - lo < 0.01) { lo -= 1; hi += 1; }
  const t0 = pts[0].ts, t1 = pts[pts.length - 1].ts || t0 + 1;
  const x = (ts) => padX + ((ts - t0) / Math.max(1, t1 - t0)) * (w - 2 * padX);
  const y = (v) => padT + (1 - (v - lo) / (hi - lo)) * (h - padT - padB);
  const line = (key) => pts.filter((p) => p[key])
    .map((p) => `${x(p.ts).toFixed(1)},${y(p[key]).toFixed(1)}`).join(" ");
  const dots = (key, farbe) => pts.filter((p) => p[key]).map((p) =>
    `<circle cx="${x(p.ts).toFixed(1)}" cy="${y(p[key]).toFixed(1)}" r="3.2"`
    + ` fill="${farbe}" stroke="var(--chart-bg)" stroke-width="1.6"/>`).join("");
  // Fläche unter der Kurve: dieselben Punkte, unten am Achsenrand
  // geschlossen. Macht aus zwei dünnen Strichen zwei lesbare Bänder.
  const flaeche = (key) => {
    const pl = pts.filter((p) => p[key]);
    if (pl.length < 2) return "";
    const boden = (h - padB).toFixed(1);
    return `${x(pl[0].ts).toFixed(1)},${boden} ${line(key)} `
      + `${x(pl[pl.length - 1].ts).toFixed(1)},${boden}`;
  };
  const dFmt = (ts) => new Date(ts * 1000).toLocaleDateString(dateLocale(),
    { day: "2-digit", month: "2-digit", year: "2-digit" });
  // Die Farben kommen aus dem Design, nicht aus dem Code: Im hellen Blau/Grün
  // wie gehabt, in Galaxy und Nova die Akzentfarben des jeweiligen Designs.
  // Die Verlaufs-Kennung enthält eine Zufallszahl, weil mehrere Diagramme
  // gleichzeitig im Dokument stehen können und `id` eindeutig sein muss.
  const uid = "h" + Math.random().toString(36).slice(2, 8);
  const band = (key, farbe) => flaeche(key)
    ? `<polygon points="${flaeche(key)}" fill="url(#${uid}-${key})"/>` : "";
  return `
  <svg viewBox="0 0 ${w} ${h}" class="history-svg" role="img" aria-label="${esc(tr("Preisverlauf"))}">
    <defs>
      <linearGradient id="${uid}-price_new" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="var(--chart-new)" stop-opacity=".34"/>
        <stop offset="100%" stop-color="var(--chart-new)" stop-opacity="0"/>
      </linearGradient>
      <linearGradient id="${uid}-price_used" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="var(--chart-used)" stop-opacity=".30"/>
        <stop offset="100%" stop-color="var(--chart-used)" stop-opacity="0"/>
      </linearGradient>
    </defs>
    <line x1="${padX}" y1="${(padT + (h - padT - padB) / 2).toFixed(1)}"
          x2="${w - padX}" y2="${(padT + (h - padT - padB) / 2).toFixed(1)}"
          class="hist-grid"/>
    <line x1="${padX}" y1="${h - padB}" x2="${w - padX}" y2="${h - padB}" class="hist-axis"/>
    ${band("price_new")}${band("price_used")}
    <polyline points="${line("price_new")}" fill="none" stroke="var(--chart-new)"
              stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"/>
    <polyline points="${line("price_used")}" fill="none" stroke="var(--chart-used)"
              stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"/>
    ${dots("price_new", "var(--chart-new)")}${dots("price_used", "var(--chart-used)")}
    <text x="${padX}" y="${h - 6}" class="hist-label">${dFmt(t0)}</text>
    <text x="${w - padX}" y="${h - 6}" text-anchor="end" class="hist-label">${dFmt(t1)}</text>
    <text x="${padX}" y="${padT + 2}" class="hist-label">${fmtEur(hi)}</text>
    <text x="${padX}" y="${h - padB - 4}" class="hist-label">${fmtEur(lo)}</text>
  </svg>
  <div class="price-note"><span class="hist-dot" style="background:var(--chart-new)"></span> Neu
    &nbsp;<span class="hist-dot" style="background:var(--chart-used)"></span> Gebraucht
    · eigene Aufzeichnung seit Erfassung</div>`;
}

async function updateStatsOnly() {
  try {
    const data = await api("/collection?q=");
    $("stat-total").textContent = data.stats.total;
    $("stat-unique").textContent = data.stats.unique_items;
    $("stat-value").textContent = data.stats.total_value
      ? fmtEur(data.stats.total_value) : "–";
    $("stat-value-sub").textContent = data.stats.unpriced > 0
      ? tr("Wert · {n} ohne Preis", { n: data.stats.unpriced })
      : tr("Wert (BrickLink Ø)");
  } catch (_) { /* still */ }
}

/* ---------------------------------------------------------------- Manuell erfassen */
const BL_URL_PREFIX = { minifig: "M", part: "P", set: "S" };
let suggestTimer;
let manualSelection = null;   // übernommener Vorschlag (Bild + BrickLink-Link)
let customImgUrl = "";        // hochgeladenes Bild für eine eigene Figur
let lastScanFile = null;      // zuletzt fotografiertes Bild (für Custom-Figuren)

/* Die beiden „Foto vom Scan"-Knöpfe erscheinen erst, wenn wirklich eines da
   ist – einer unter dem Scan, einer im Custom-Bereich des Formulars. */
function updateScanCustomBtns() {
  const a = $("btn-scan-custom");
  if (a) a.hidden = !lastScanFile;
  const b = $("m-img-from-scan");
  if (b) b.hidden = !lastScanFile;
}

/* Aus dem Scan heraus eine eigene Figur anlegen: Formular öffnen, in den
   Custom-Modus schalten und das Foto gleich als Bild übernehmen. */
async function customFromScan() {
  if (!lastScanFile) return;
  const form = $("manual-form");
  form.hidden = false;
  updateManualListBtn();
  if (!$("m-custom").checked) {
    $("m-custom").checked = true;
    applyCustomMode();
  }
  await uploadCustomImage(lastScanFile);
  $("m-name").focus();
  form.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* „Eigene Figur"-Modus: Beschriftungen umstellen, Bildfeld ein-/ausblenden
   und die Katalogsuche stilllegen (Custom-Figuren gibt es dort nicht). */
function applyCustomMode() {
  const on = $("m-custom").checked;
  $("m-custom-box").hidden = !on;
  $("m-id-label").textContent = on
    ? "Interne Nummer" : "BrickLink-Nr. (optional)";
  $("m-id").placeholder = on ? "wird vergeben …" : "z. B. sw0001a";
  if (on) {
    $("m-suggestions").innerHTML = "";
    $("m-search-hint").hidden = true;
    manualSelection = null;
    suggestCustomId();
    updateScanCustomBtns();
  } else if (/^custom-/.test($("m-id").value)) {
    $("m-id").value = "";        // Vorschlag beim Zurückschalten wegräumen
  }
}

/* Nächste freie Nummer vorschlagen – überschreibbar, falls jemand ein
   eigenes Schema führt. */
async function suggestCustomId() {
  const field = $("m-id");
  if (field.value.trim() && !/^custom-/.test(field.value.trim())) return;
  try {
    const res = await api("/next_custom_id");
    field.value = res.item_id;
    field.placeholder = "z. B. " + res.item_id;
  } catch (_) {
    field.placeholder = "z. B. eigen-001";
  }
}

function resetCustomImage() {
  customImgUrl = "";
  const inp = $("m-img");
  if (inp) inp.value = "";
  const prev = $("m-img-preview");
  if (prev) prev.hidden = true;
}

async function uploadCustomImage(file) {
  const form = new FormData();
  form.append("file", file);
  try {
    const res = await api("/upload_image", { method: "POST", body: form });
    customImgUrl = res.url;
    $("m-img-thumb").src = res.url;
    $("m-img-preview").hidden = false;
    toast("Bild hochgeladen ✔");
  } catch (e) {
    toast(e.message);
    resetCustomImage();
  }
}
let suggestState = null;      // laufende Katalogsuche (für seitenweises Nachladen)
let searchSeq = 0;            // nur die jeweils neueste Suche darf rendern

function setupCatalogSearch() {
  $("m-name").addEventListener("input", () => {
    manualSelection = null;
    clearTimeout(suggestTimer);
    suggestTimer = setTimeout(runCatalogSearch, 450);
  });
  $("m-id").addEventListener("input", () => {
    manualSelection = null;
    clearTimeout(suggestTimer);
    suggestTimer = setTimeout(runBricklinkLookup, 550);
  });
  $("m-type").addEventListener("change", () => {
    if ($("m-id").value.trim().length >= 3) runBricklinkLookup();
    else runCatalogSearch();
  });
}

async function runBricklinkLookup() {
  const seq = ++searchSeq;
  const no = $("m-id").value.trim();
  const box = $("m-suggestions");
  const hint = $("m-search-hint");
  if (!state.bricklinkLookup || no.length < 3) return;
  hint.textContent = tr("Suche bei BrickLink …");
  hint.hidden = false;
  const found = await lookupNumber(no);
  if (seq !== searchSeq) return;   // überholt – nichts rendern
  if (found.length) {
    renderSuggestions(found);
    hint.hidden = true;
  } else {
    box.innerHTML = "";
    hint.textContent = tr("„{no}“ nicht im BrickLink-Katalog gefunden",
      { no });
  }
}

const BL_NO_RE = /^[a-z]{2,4}\d{2,5}[a-z0-9]*$/i;   // sw0815, cty1234, hp123a …
const NUM_NO_RE = /^\d{3,7}(-\d{1,2})?$/;           // 75154, 75154-1, 3001 …

async function lookupNumber(no) {
  // Reine Zahl kann Set ODER Teil sein – gewählten Typ zuerst, dann die anderen
  const primary = $("m-type").value;
  const digits = NUM_NO_RE.test(no);
  const types = digits
    ? [...new Set([primary, "set", "part"])]
    : [primary];
  const found = [];
  for (const t of types) {
    try {
      found.push(await api(`/lookup/${t}/${encodeURIComponent(no)}`));
    } catch (_) { /* dieser Typ kennt die Nummer nicht */ }
    if (!digits) break;
  }
  return found;
}

async function runCatalogSearch() {
  const seq = ++searchSeq;   // ältere, noch laufende Suchen werden verworfen
  // Eigene Figuren stehen in keinem Katalog – dann gar nicht erst suchen.
  if ($("m-custom") && $("m-custom").checked) return;
  const q = $("m-name").value.trim();
  const box = $("m-suggestions");
  const hint = $("m-search-hint");
  if (q.length < 3) {
    box.innerHTML = "";
    if (q.length > 0) {
      hint.textContent = tr("Bitte mindestens 3 Zeichen eingeben …");
      hint.hidden = false;
    } else {
      hint.hidden = true;
    }
    return;
  }
  // Sieht nach BrickLink-Nummer aus? Dann zuerst dort direkt nachschlagen.
  if (state.bricklinkLookup && (BL_NO_RE.test(q) || NUM_NO_RE.test(q))) {
    hint.textContent = tr("Suche bei BrickLink …");
    hint.hidden = false;
    const found = await lookupNumber(q);
    if (seq !== searchSeq) return;   // eine neuere Suche läuft schon
    if (found.length) {
      renderSuggestions(found);
      hint.hidden = true;
      return;
    }
    /* kein Treffer – unten normal bei Rebrickable suchen */
  }
  if (!state.catalogSearch) {
    box.innerHTML = "";
    hint.hidden = true;
    return;
  }
  hint.textContent = tr("Suche im Katalog …");
  hint.hidden = false;
  const type = $("m-type").value;
  try {
    const data = await api(`/search?q=${encodeURIComponent(q)}`
      + `&item_type=${type}&page=1`);
    if (seq !== searchSeq) return;   // Ergebnis einer überholten Suche verwerfen
    suggestState = { q, type, page: 1, items: data.items || [],
                     count: data.count || (data.items || []).length,
                     hasMore: !!data.has_more };
    renderSuggestions(suggestState.items,
      { count: suggestState.count, hasMore: suggestState.hasMore });
    hint.hidden = true;
  } catch (e) {
    if (seq !== searchSeq) return;
    hint.textContent = e.message;
  }
}

async function loadMoreSuggestions() {
  if (!suggestState || !suggestState.hasMore) return;
  const btn = $("m-suggestions").querySelector("[data-more-suggest]");
  if (btn) { btn.disabled = true; btn.textContent = tr("Lade …"); }
  try {
    const next = suggestState.page + 1;
    const data = await api(`/search?q=${encodeURIComponent(suggestState.q)}`
      + `&item_type=${suggestState.type}&page=${next}`);
    suggestState.page = next;
    suggestState.items = suggestState.items.concat(data.items || []);
    suggestState.count = data.count || suggestState.count;
    suggestState.hasMore = !!data.has_more;
    renderSuggestions(suggestState.items,
      { count: suggestState.count, hasMore: suggestState.hasMore });
  } catch (e) {
    toast(e.message);
    if (btn) { btn.disabled = false; btn.textContent = tr("Weitere Ergebnisse laden"); }
  }
}

function renderSuggestions(items, meta) {
  const box = $("m-suggestions");
  if (!items.length) {
    box.innerHTML = "";
    const hint = $("m-search-hint");
    hint.textContent = tr("Nichts gefunden – einfach weitertippen oder unten manuell speichern.");
    hint.hidden = false;
    return;
  }
  const cards = items.map((it, i) => {
    const base = `${it.item_id}${it.sub ? " · " + it.sub : ""}`;
    return `
    <div class="card" data-sug-id="${esc(it.item_id)}" data-sug-base="${esc(base)}">
      <div class="card-head">
        <img class="card-img" src="${imgSrc(it.img_url)}" data-gid="${esc(it.item_id)}" data-gtype="${esc(it.item_type || "minifig")}" alt="" loading="lazy">
        <div class="card-title">
          <strong>${esc(it.name)}</strong>
          <div class="sub" data-sug-sub>${esc(base)}</div>
          <span class="badge badge-owned" data-owned hidden></span>
        </div>
      </div>
      <div class="card-actions">
        <button class="mini-btn add" data-suggest="${i}">✔ Übernehmen</button>
        <button class="mini-btn" data-want="${i}">☆ Merken</button>
        ${state.user && state.user.is_dealer ? `<button class="mini-btn" data-cart="${i}">🛒 Liste</button>` : ""}
        ${it.bricklink_url ? `<a class="mini-btn link" href="${esc(it.bricklink_url)}" target="_blank" rel="noopener">BrickLink ↗</a>` : ""}
      </div>
    </div>`;
  }).join("");

  let footer = "";
  if (meta && meta.count) {
    footer = `<div class="suggest-foot">
      <span class="suggest-count">${esc(tr("{n} von {max} angezeigt", { n: items.length, max: meta.count }))}</span>
      ${meta.hasMore ? `<button class="mini-btn" data-more-suggest>Weitere Ergebnisse laden</button>` : ""}
    </div>`;
  }
  box.innerHTML = cards + footer;

  const moreBtn = box.querySelector("[data-more-suggest]");
  if (moreBtn) moreBtn.addEventListener("click", loadMoreSuggestions);

  enrichSuggestions(items);
  wireWantButtons(box, items);
  wireCartButtons(box, items);

  box.querySelectorAll("[data-suggest]").forEach((btn) => {
    btn.addEventListener("click", () => takeSuggestion(items[Number(btn.dataset.suggest)]));
  });

  // Tipp auf die Karte (nicht auf Knopf/Link/Bild/Eingabefeld) öffnet die
  // Detailansicht. Solange ein Formular in der Karte offen ist (z. B. der
  // Listen-Ablauf mit Preisfeld), bleibt das Popup zu.
  box.querySelectorAll("[data-sug-id]").forEach((card, i) => {
    card.classList.add("tappable");
    card.addEventListener("click", (ev) => {
      if (ev.target.closest("button, a, input, textarea, select, label, .card-img")) return;
      if (card.querySelector("[data-cart-row]")) return;
      openSuggestModal(items[i]);
    });
  });
}

/* Vorschlag ins manuelle Formular übernehmen (Karte oder Detail-Popup). */
function takeSuggestion(it) {
  $("m-name").value = it.name;
  $("m-id").value = it.item_id;
  if (it.item_type) $("m-type").value = it.item_type;
  manualSelection = { item_id: it.item_id, img_url: it.img_url || "",
                      bricklink_url: it.bricklink_url || "",
                      year: it.year || 0 };
  $("m-suggestions").innerHTML = "";
  $("m-search-hint").hidden = true;
  if (/^fig-/.test(it.item_id) && it.img_url) {
    resolveBricklinkNo(it);        // automatisch sw-/dis-Nummer suchen
  } else {
    toast("Übernommen – unten Anzahl & Zustand prüfen und speichern");
    $("btn-manual-add").scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

/* Detail-Popup für einen Suchtreffer: Jahr, vorhanden/Wunschliste,
   Marktpreise, Sets und (bei Minifiguren) die enthaltenen Teile –
   alles bevor man die Figur übernimmt. */
function openSuggestModal(it) {
  closeCardModal();
  // Lokale Kopie – die Nummer kann sich beim Auflösen ändern, das soll die
  // Trefferliste dahinter nicht durcheinanderbringen.
  const pit = { ...it };
  const type = pit.item_type || "minifig";
  const isMini = type === "minifig";
  // Teile lohnen sich, wenn wir eine BrickLink-Nummer haben ODER über das
  // Bild eine finden können (Namenssuche liefert nur Rebrickable-Nummern).
  const resolvable = /^fig-/.test(pit.item_id) && !!pit.img_url;
  const canParts = state.bricklinkPrices && isMini
    && (!/^(fig-|manuell-|custom-)/.test(pit.item_id) || resolvable);
  // Bei Sets andersherum: die enthaltenen Figuren zeigen
  const canFigs = state.bricklinkPrices && type === "set"
    && !/^manuell-/.test(pit.item_id);
  const overlay = document.createElement("div");
  overlay.className = "card-modal-overlay";
  overlay.id = "card-modal";
  overlay.innerHTML = `
    <div class="card-modal">
      <button class="card-modal-close" aria-label="Schließen">✕</button>
      <div class="card modal-inner open" role="dialog" aria-modal="true">
        <div class="card-head">
          <div class="card-img-wrap">
            <img class="card-img" src="${imgSrc(pit.img_url)}" data-gid="${esc(pit.item_id)}" data-gtype="${esc(type)}" alt="">
          </div>
          <div class="card-title">
            <strong>${esc(pit.name)}</strong>
            <div class="sub" data-sug-meta>${esc(pit.item_id)}${pit.year > 0 ? " · " + pit.year : ""}</div>
            <span class="badge badge-owned" data-sug-owned hidden></span>
          </div>
        </div>
        <div class="card-details">
          ${state.bricklinkPrices ? `<div class="sug-prices" data-sug-prices><span class="price-note">Lade Details …</span></div>` : ""}
          ${isMini ? `<div class="sub in-sets" data-fig-sets hidden></div>` : ""}
          ${canParts ? `
          <div class="detail-row">
            <button class="mini-btn" data-parts>🧩 Enthaltene Teile anzeigen</button>
          </div>
          <div class="set-figs" data-parts-out></div>` : ""}
          ${canFigs ? `
          <div class="detail-row">
            <button class="mini-btn" data-figs>👥 Enthaltene Figuren anzeigen</button>
          </div>
          <div class="set-figs" data-figs-out></div>` : ""}
          <div class="card-actions suggest-actions">
            <button class="mini-btn add" data-sug-take>✔ Übernehmen</button>
            <button class="mini-btn" data-sug-want>☆ Merken</button>
            ${pit.bricklink_url ? `<a class="mini-btn link" data-sug-bl href="${esc(pit.bricklink_url)}" target="_blank" rel="noopener">BrickLink ↗</a>` : ""}
          </div>
        </div>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  const inner = overlay.querySelector(".modal-inner");

  const done = () => closeCardModal();
  overlay.querySelector(".card-modal-close").addEventListener("click", done);
  overlay.addEventListener("click", (ev) => { if (ev.target === overlay) done(); });
  cardModalKeyHandler = (ev) => { if (ev.key === "Escape") done(); };
  document.addEventListener("keydown", cardModalKeyHandler);

  const partsBtn = inner.querySelector("[data-parts]");
  if (partsBtn) {
    // pit.item_id ist beim Klick evtl. schon zur BrickLink-Nummer aufgelöst
    partsBtn.addEventListener("click", () => loadFigParts(inner, pit, partsBtn));
    // Solange die BrickLink-Nummer noch gesucht wird: erst danach klickbar
    if (/^fig-/.test(pit.item_id)) {
      partsBtn.disabled = true;
      partsBtn.textContent = tr("🧩 Teile (suche Nummer …)");
    }
  }
  const figsBtn = inner.querySelector("[data-figs]");
  if (figsBtn) {
    figsBtn.addEventListener("click", () => loadSetFigs(inner, pit, figsBtn));
  }
  inner.querySelector("[data-sug-take]").addEventListener("click", () => {
    done();
    takeSuggestion(pit);
  });
  inner.querySelector("[data-sug-want]").addEventListener("click", async (ev) => {
    const b = ev.currentTarget;
    b.disabled = true;
    try {
      const res = await api("/wanted", { method: "POST", body: {
        item_id: pit.item_id, item_type: type, name: pit.name,
        img_url: pit.img_url || "", bricklink_url: pit.bricklink_url || "",
        year: pit.year || 0,
      }});
      if (res.exists) toast("Steht schon auf der Wunschliste ⭐");
      else if (res.owned > 0) toast(tr("Gemerkt ⭐ (habt ihr schon {n}×)", { n: res.owned }));
      else toast("Auf die Wunschliste gesetzt ⭐");
      b.textContent = tr("⭐ Gemerkt");
    } catch (e) { toast(e.message); } finally { b.disabled = false; }
  });
  loadSuggestDetail(inner, pit, it);
}

/* Details eines Suchtreffers ins Popup laden. Bei Namenssuchen (Rebrickable-
   Nummer fig-…) wird zuerst über das Bild die BrickLink-Nummer gesucht, damit
   Preise, Sets und Teile ohne den Umweg über „Übernehmen" erscheinen.
   `orig` ist das Item aus der Trefferliste – dort werden aufgelöste Nummer und
   Details zwischengespeichert, damit erneutes Öffnen ohne neue Abrufe geht. */
async function loadSuggestDetail(inner, pit, orig) {
  const type = pit.item_type || "minifig";
  const meta = inner.querySelector("[data-sug-meta]");
  const pr = inner.querySelector("[data-sug-prices]");

  // 1) BrickLink-Nummer auflösen, falls nötig und möglich (Ergebnis gemerkt)
  if (state.bricklinkPrices && /^fig-/.test(pit.item_id) && pit.img_url) {
    let best = orig && orig._resolved;
    if (!best) {
      if (pr) pr.innerHTML = `<span class="price-note">🔎 BrickLink-Nummer wird gesucht …</span>`;
      try {
        const data = await api("/resolve", { method: "POST", body: { img_url: pit.img_url } });
        let cands = (data.items || []).filter((c) => !c.item_type || c.item_type === type);
        if (!cands.length) cands = data.items || [];
        best = cands[0];
        if (best && best.item_id && orig) orig._resolved = best;   // merken
      } catch (_) { /* ohne Nummer geht es mit Rebrickable-Daten weiter */ }
    }
    if (best && best.item_id) {
      pit.item_id = best.item_id;
      pit.bricklink_url = best.bricklink_url || pit.bricklink_url;
      if (best.img_url) pit.img_url = best.img_url;
      pit._score = best.score;
      const img = inner.querySelector(".card-img");
      if (img) {
        img.dataset.gid = best.item_id;            // Galerie nutzt BrickLink-Bilder
        if (best.img_url) img.src = imgSrc(best.img_url);
      }
      const bl = inner.querySelector("[data-sug-bl]");
      if (bl && best.bricklink_url) bl.href = best.bricklink_url;
    }
    // Teile-Knopf freigeben – oder entfernen, wenn keine Nummer gefunden wurde
    const pBtn = inner.querySelector("[data-parts]");
    if (pBtn) {
      if (/^fig-/.test(pit.item_id)) {
        pBtn.closest(".detail-row").remove();
        const po = inner.querySelector("[data-parts-out]");
        if (po) po.remove();
      } else {
        pBtn.disabled = false;
        pBtn.textContent = tr("🧩 Enthaltene Teile anzeigen");
      }
    }
  }

  // 2) Angereicherte Infos zur (ggf. aufgelösten) Nummer – aus dem Cache der
  //    Trefferliste, sonst einmal holen und dort ablegen.
  let d = orig && orig._infoById && orig._infoById[pit.item_id];
  if (!d) {
    try {
      const info = await api("/suggest_info?detail=1", { method: "POST",
        body: { items: [{ item_id: pit.item_id, item_type: type }] } });
      d = info[pit.item_id] || {};
      if (orig) (orig._infoById ||= {})[pit.item_id] = d;
    } catch (_) { d = {}; }
  }
  if (d.in_sets) pit.in_sets = d.in_sets;
  if (d.year && !pit.year) pit.year = d.year;

  if (meta) {
    const bits = [pit.item_id];
    if (pit._score) bits.push(`${pit._score} % sicher`);
    if (pit.year > 0) bits.push(String(pit.year));
    meta.textContent = bits.join(" · ");
  }

  const badge = inner.querySelector("[data-sug-owned]");
  if (badge) {
    if (d.owned > 0) {
      badge.textContent = `✔ ${d.owned}× in eurer Sammlung`;
      badge.hidden = false;
    } else if (d.wanted) {
      badge.textContent = tr("⭐ auf eurer Wunschliste");
      badge.classList.replace("badge-owned", "badge-wanted");
      badge.hidden = false;
    }
    if (d.on_lists && d.on_lists.length) {
      const lb = document.createElement("span");
      lb.className = "badge badge-list";
      lb.textContent = d.on_lists.length === 1
        ? `🛒 auf »${d.on_lists[0]}«` : `🛒 auf ${d.on_lists.length} Listen`;
      badge.after(lb);
    }
  }

  if (pr) {
    const parts = [];
    if (d.new != null) parts.push(`${tr("Ø neu")} ${fmtEur(d.new)}`);
    if (d.used != null) parts.push(`${tr("Ø gebr.")} ${fmtEur(d.used)}`);
    pr.innerHTML = parts.length
      ? `<span class="sug-price-label">Marktpreis</span> ${parts.join(" · ")}`
      : `<span class="price-note">${/^fig-/.test(pit.item_id)
          ? "Keine BrickLink-Nummer gefunden – Preise erst nach dem Übernehmen."
          : "Keine Preisdaten bei BrickLink."}</span>`;
  }

  if (type === "minifig") renderFigSets(inner, pit);
}

async function resolveBricklinkNo(it) {
  const hint = $("m-search-hint");
  hint.textContent = tr("Suche die passende BrickLink-Nummer (sw/dis/…) …");
  hint.hidden = false;
  try {
    const data = await api("/resolve", { method: "POST", body: { img_url: it.img_url } });
    let candidates = (data.items || [])
      .filter((c) => !c.item_type || c.item_type === $("m-type").value);
    if (!candidates.length) candidates = data.items || [];
    if (!candidates.length) {
      hint.textContent = tr("Keine BrickLink-Nummer gefunden – der Eintrag behält ")
        + "die Rebrickable-Nummer. Speichern ist trotzdem möglich.";
      return;
    }
    hint.textContent = tr("BrickLink-Treffer – bitte die exakte Variante wählen ")
      + "(Bild antippen für Großansicht):";
    renderSuggestions(candidates.map((c) => ({ ...c, sub: `${c.score} % sicher` })));
  } catch (e) {
    hint.textContent = e.message + " – der Eintrag behält die Rebrickable-Nummer.";
  }
}


/* Nummer, Bild und BrickLink-Link aus dem manuellen Formular ableiten.
   Bei „Eigene Figur" gibt es keine BrickLink-Identität: die Nummer bekommt
   das Präfix custom-, damit Preis- und Katalogabfragen sie überspringen. */
function manualIdentity(type) {
  const raw = $("m-id").value.trim();
  if ($("m-custom").checked) {
    const own = raw.replace(/^custom-/i, "")
      .replace(/[^A-Za-z0-9_.-]+/g, "-").replace(/^-+|-+$/g, "");
    return {
      itemId: "custom-" + (own || Date.now()),
      imgUrl: customImgUrl || "",
      blUrl: "",
      year: 0,
    };
  }
  let itemId = raw;
  let imgUrl = "";
  let blUrl = "";
  let year = 0;
  if (manualSelection && manualSelection.item_id === itemId) {
    imgUrl = manualSelection.img_url;
    blUrl = manualSelection.bricklink_url;
    year = manualSelection.year || 0;
  } else if (itemId) {
    blUrl = `https://www.bricklink.com/v2/catalog/catalogitem.page?${BL_URL_PREFIX[type]}=${encodeURIComponent(itemId)}`;
  }
  if (!itemId) itemId = "manuell-" + Date.now();
  return { itemId, imgUrl, blUrl, year };
}

async function addManual() {
  const err = $("manual-error");
  err.hidden = true;
  const name = $("m-name").value.trim();
  if (!name) {
    err.textContent = tr("Bitte mindestens einen Namen angeben.");
    err.hidden = false;
    return;
  }
  const type = $("m-type").value;
  const { itemId, imgUrl, blUrl, year } = manualIdentity(type);
  const paidRaw = $("m-paid").value.trim().replace(",", ".");
  let paidPrice = null;
  if (paidRaw) {
    const n = Number(paidRaw);
    if (!Number.isFinite(n) || n < 0) {
      err.textContent = tr("Bezahlt bitte als Zahl, z. B. 4,50");
      err.hidden = false;
      return;
    }
    paidPrice = Math.round(n * 100) / 100;
  }
  try {
    const res = await api("/collection", { method: "POST", body: {
      item_id: itemId, item_type: type, name, img_url: imgUrl,
      bricklink_url: blUrl, year,
      quantity: Math.max(1, Number($("m-qty").value) || 1),
      condition: $("m-cond").value, notes: $("m-notes").value,
      paid_price: paidPrice,
    }});
    toast(res.merged
      ? tr("Schon vorhanden – Anzahl erhöht (jetzt {n}×)", { n: res.quantity })
      : "Zur Sammlung hinzugefügt ✔");
    $("m-name").value = ""; $("m-id").value = "";
    $("m-qty").value = "1"; $("m-notes").value = ""; $("m-paid").value = "";
    $("m-suggestions").innerHTML = "";
    manualSelection = null;
    resetCustomImage();
    if ($("m-custom").checked) suggestCustomId();   // nächste Nummer bereit
    $("manual-form").hidden = true;
    await askSetFigures({ item_id: itemId, item_type: type, name },
                        $("m-cond").value);
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  }
}

/* ---------------------------------------------------------------- API-Schlüssel */
const KEY_FIELDS = {
  rebrickable_key: "k-rb",
  bl_consumer_key: "k-bck",
  bl_consumer_secret: "k-bcs",
  bl_token: "k-bt",
  bl_token_secret: "k-bts",
};

async function loadApiKeys() {
  try {
    const data = await api("/settings");
    for (const [name, id] of Object.entries(KEY_FIELDS)) {
      const input = $(id);
      input.value = "";
      const info = data[name] || {};
      input.placeholder = info.set
        ? tr("gespeichert: {wert}", { wert: info.masked })
          + (info.from_env ? " " + tr("(aus docker-compose)") : "")
        : tr("nicht gesetzt");
    }
  } catch (e) { toast(e.message); }
}

async function saveApiKeys() {
  const body = {};
  for (const [name, id] of Object.entries(KEY_FIELDS)) {
    const value = $(id).value.trim();
    if (value) body[name] = value;
  }
  if (!Object.keys(body).length) {
    toast("Keine Änderungen eingegeben");
    return;
  }
  try {
    const res = await api("/settings", { method: "PUT", body });
    state.bricklinkPrices = res.flags.bricklink_prices;
    state.bricklinkLookup = res.flags.bricklink_lookup;
    state.catalogSearch = res.flags.catalog_search;
    toast(tr("Gespeichert ({n} Schlüssel) ✔", { n: res.changed }));
    loadApiKeys();
  } catch (e) { toast(e.message); }
}

async function testApiKeys() {
  const out = $("keys-status");
  out.textContent = tr("Teste Verbindungen …");
  out.hidden = false;
  try {
    const r = await api("/settings/test", { method: "POST" });
    out.textContent =
      `BrickLink: ${r.bricklink.ok ? "✅" : "❌"} ${r.bricklink.info} — ` +
      `Rebrickable: ${r.rebrickable.ok ? "✅" : "❌"} ${r.rebrickable.info}`;
  } catch (e) {
    out.textContent = e.message;
  }
}

/* Aus dem manuellen Formular direkt auf eine Einkaufsliste legen – auch für
   eigene Figuren, die es in keinem Katalog gibt. */
function updateManualListBtn() {
  const b = $("btn-manual-list");
  if (b) b.hidden = !(state.user && state.user.is_dealer);
}

async function pickListForManual() {
  const err = $("manual-error");
  err.hidden = true;
  if (!$("m-name").value.trim()) {
    err.textContent = tr("Bitte mindestens einen Namen angeben.");
    err.hidden = false;
    return;
  }
  const box = $("manual-list-pick");
  if (!box.hidden) { box.hidden = true; return; }   // zweiter Klick schließt
  let lists = [];
  try {
    lists = (await api("/lists")).lists || [];
  } catch (e) { toast(e.message); return; }

  box.hidden = false;
  box.innerHTML = lists.map((l) =>
    `<button class="mini-btn add" data-ml="${l.id}">${esc(l.name)}</button>`).join("")
    + `<button class="mini-btn" data-ml-new>➕ Neue Liste</button>`
    + `<button class="mini-btn" data-ml-cancel>Abbrechen</button>`;

  box.querySelectorAll("[data-ml]").forEach((btn) => {
    btn.addEventListener("click", () => addManualToList(Number(btn.dataset.ml)));
  });
  box.querySelector("[data-ml-cancel]").addEventListener("click", () => {
    box.hidden = true;
  });
  box.querySelector("[data-ml-new]").addEventListener("click", async () => {
    const today = new Date().toLocaleDateString(dateLocale(),
      { day: "2-digit", month: "2-digit" });
    const d = await appDialog({
      titel: tr("Neue Liste"),
      felder: [{ name: "name", label: tr("Name der neuen Liste"),
                 wert: `Flohmarkt ${today}`, pflicht: true, max: 80 }],
      ok: tr("Anlegen"),
    });
    const name = d && d.name;
    if (name == null || !name.trim()) return;
    try {
      const res = await api("/lists", { method: "POST",
        body: { name: name.trim() } });
      addManualToList(res.id);
    } catch (e) { toast(e.message); }
  });
}

async function addManualToList(listId) {
  const err = $("manual-error");
  err.hidden = true;
  const name = $("m-name").value.trim();
  const type = $("m-type").value;
  const { itemId, imgUrl, blUrl, year } = manualIdentity(type);
  try {
    const res = await api(`/lists/${listId}/items`, { method: "POST", body: {
      item_id: itemId, item_type: type, name, img_url: imgUrl,
      bricklink_url: blUrl, year,
      qty: Math.max(1, Number($("m-qty").value) || 1),
      condition: $("m-cond").value,
    }});
    toast(res.merged
      ? tr("Schon auf der Liste – Anzahl erhöht (jetzt {n}×)", { n: res.qty })
      : "Auf die Liste gesetzt 🛒");
    $("manual-list-pick").hidden = true;
    $("m-name").value = ""; $("m-id").value = "";
    $("m-qty").value = "1"; $("m-notes").value = ""; $("m-paid").value = "";
    $("m-suggestions").innerHTML = "";
    manualSelection = null;
    resetCustomImage();
    if ($("m-custom").checked) suggestCustomId();
    $("manual-form").hidden = true;
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  }
}

async function addManualWanted() {
  const err = $("manual-error");
  err.hidden = true;
  const name = $("m-name").value.trim();
  if (!name) {
    err.textContent = tr("Bitte mindestens einen Namen angeben.");
    err.hidden = false;
    return;
  }
  const type = $("m-type").value;
  const { itemId, imgUrl, blUrl, year } = manualIdentity(type);
  try {
    const res = await api("/wanted", { method: "POST", body: {
      item_id: itemId, item_type: type, name, img_url: imgUrl,
      bricklink_url: blUrl, year, notes: $("m-notes").value,
    }});
    if (res.exists) toast("Steht schon auf der Wunschliste ⭐");
    else if (res.owned > 0) toast(tr("Gemerkt ⭐ (habt ihr schon {n}×)", { n: res.owned }));
    else toast("Auf die Wunschliste gesetzt ⭐");
    $("m-name").value = ""; $("m-id").value = "";
    $("m-qty").value = "1"; $("m-notes").value = ""; $("m-paid").value = "";
    $("m-suggestions").innerHTML = "";
    manualSelection = null;
    resetCustomImage();
    if ($("m-custom").checked) suggestCustomId();   // nächste Nummer bereit
    $("manual-form").hidden = true;
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  }
}

async function changeOwnUsername() {
  const err = $("own-name-error");
  err.hidden = true;
  const name = $("own-name").value.trim();
  if (name.length < 2) {
    err.textContent = tr("Bitte mindestens 2 Zeichen.");
    err.hidden = false;
    return;
  }
  try {
    const res = await api("/me/username", { method: "POST",
      body: { username: name } });
    state.token = res.token;
    state.user = { username: res.username, is_admin: res.is_admin,
      is_dealer: state.user && state.user.is_dealer };
    localStorage.setItem("bf_token", res.token);
    localStorage.setItem("bf_user", JSON.stringify(state.user));
    $("whoami").textContent = res.username;
    $("settings-user").textContent = res.username;
    toast(tr("Name geändert: {name} ✔", { name: res.username }));
    loadSettings();
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  }
}

/* ---------------------------------------------------------------- Einkaufslisten */
async function loadLists() {
  const dealer = state.user && state.user.is_dealer;
  $("lists-admin").hidden = !dealer;
  if (!dealer) $("duplicates-box").hidden = true;
  try {
    const data = await api("/lists" + (state.showArchive ? "?archived=1" : ""));
    renderLists(data.lists || []);
  } catch (e) { toast(e.message); }
}

function renderLists(lists) {
  const dealer = state.user && state.user.is_dealer;
  const box = $(state.showArchive ? "archive-container" : "lists-container");
  const leer = $(state.showArchive ? "archive-empty" : "lists-empty");
  leer.hidden = lists.length > 0;
  box.innerHTML = lists.map((l) => `
    <div class="card list-card${state.showArchive ? " list-card-archiv" : ""}" data-lid="${l.id}">
      <div class="card-head">
        <div class="card-title">
          <strong>${state.showArchive ? "📦 " : "🛒 "}<span data-l-name>${esc(l.name)}</span>${dealer && !state.showArchive ? ` <button class="set-link rename-btn" data-l-rename title="${esc(tr("Liste umbenennen"))}">✏️</button>` : ""}</strong>
          <div class="sub">${esc(tr("{n} Artikel · {offen} offen · Marktwert ca. {wert} (je Zustand)",
            { n: l.stats.count, offen: l.stats.open, wert: fmtEur(l.stats.est) }))}${
            l.stats.paid_sum > 0 ? esc(tr(" · Einkauf {sum}", { sum: fmtEur(l.stats.paid_sum) })) : ""}</div>
        </div>
      </div>
      <div class="set-figs">
        ${l.items.map((it) => listItemRow(it, dealer)).join("")}
        ${!l.items.length ? `<div class="price-note">Noch leer – beim Scannen oder Suchen auf 🛒 tippen.</div>` : ""}
      </div>
      ${dealer ? `<div class="card-actions btn-grid" style="margin-top:8px">
        ${!state.showArchive && l.stats.open > 0 ? `<button class="mini-btn add" data-l-offer>💰 Gesamtangebot</button>` : ""}
        ${state.showArchive
          ? `<button class="mini-btn" data-l-restore>↩︎ Reaktivieren</button>`
          : `<button class="mini-btn" data-l-archive>📦 Archivieren</button>`}
        <button class="mini-btn danger" data-l-del>Liste löschen</button>
      </div>` : ""}
    </div>`).join("");

  box.querySelectorAll(".list-card").forEach((card) => {
    const lid = Number(card.dataset.lid);
    const storeKey = "bf_listcard_" + lid;
    if (localStorage.getItem(storeKey) !== "open") {
      card.classList.add("collapsed");
    }
    card.querySelector(".card-head").addEventListener("click", (ev) => {
      if (ev.target.closest("[data-l-rename]")) return;
      card.classList.toggle("collapsed");
      localStorage.setItem(storeKey,
        card.classList.contains("collapsed") ? "closed" : "open");
    });
    const renameBtn = card.querySelector("[data-l-rename]");
    if (renameBtn) {
      renameBtn.addEventListener("click", () => {
        if (card.querySelector("[data-l-rename-row]")) return;
        const nameEl = card.querySelector("[data-l-name]");
        const current = nameEl.textContent;
        const row = document.createElement("div");
        row.className = "card-actions btn-grid";
        row.setAttribute("data-l-rename-row", "");
        row.innerHTML = `
          <input data-l-newname maxlength="120" style="grid-column:1/-1">
          <button class="mini-btn add" data-l-rename-save>Umbenennen</button>
          <button class="mini-btn" data-l-rename-cancel style="grid-column:auto">Abbrechen</button>`;
        nameEl.closest(".card-head").after(row);
        const input = row.querySelector("[data-l-newname]");
        input.value = current;
        input.focus();
        input.select();
        const closeRow = () => row.remove();
        row.querySelector("[data-l-rename-cancel]")
          .addEventListener("click", closeRow);
        const save = async () => {
          const name = input.value.trim();
          if (!name) { toast("Bitte einen Namen eingeben"); return; }
          if (name === current) { closeRow(); return; }
          try {
            await api(`/lists/${lid}/rename`, { method: "POST",
              body: { name } });
            toast(tr("Liste heißt jetzt »{name}« ✔", { name }));
            loadLists();
          } catch (e) { toast(e.message); }
        };
        row.querySelector("[data-l-rename-save]")
          .addEventListener("click", save);
        input.addEventListener("keydown", (ev) => {
          if (ev.key === "Enter") save();
          if (ev.key === "Escape") { ev.stopPropagation(); closeRow(); }
        });
      });
    }
    const list = lists.find((l) => l.id === lid);
    const lOffer = card.querySelector("[data-l-offer]");
    if (lOffer) lOffer.addEventListener("click", () => {
      if (card.querySelector("[data-offer-row]")) return;
      const actions = lOffer.closest(".card-actions");
      actions.hidden = true;
      const openValue = list.items.filter((i) => !i.done)
        .reduce((s, i) => s + (((i.condition === "new"
          ? (i.price_new || i.price_used)
          : (i.price_used || i.price_new)) || 0) * i.qty), 0);
      const pct = (state.offerPercent || 60) / 100;
      const suggestion = Math.round(openValue * pct * 100) / 100;
      const row = document.createElement("div");
      row.className = "card-actions btn-grid";
      row.setAttribute("data-offer-row", "");
      row.innerHTML = `
        <span class="buy-label">Gesamtpreis für alle offenen Artikel –
          wird anteilig nach Marktwert verteilt.<br>
          Ø-Marktwert gesamt: ${fmtEur(openValue)}</span>
        <span class="paid-row buy-paid">
          <span class="paid-label">Gesamt</span>
          <input data-offer-total class="paid-input" inputmode="decimal" placeholder="0,00">
          <span class="paid-suffix" data-cur>${esc(curSymbol())}</span>
          ${suggestion > 0 ? `<button class="set-link offer-suggest" data-offer-suggest>Vorschlag: ${fmtEur(suggestion)}</button>` : ""}
        </span>
        <button class="mini-btn add" data-offer-go>Verteilen</button>
        <button class="mini-btn" data-offer-cancel>Abbrechen</button>`;
      actions.after(row);
      row.querySelector("[data-offer-cancel]").addEventListener("click",
        () => { row.remove(); actions.hidden = false; });
      const sugBtn = row.querySelector("[data-offer-suggest]");
      if (sugBtn) sugBtn.addEventListener("click", () => {
        row.querySelector("[data-offer-total]").value = fmtPaidInput(suggestion);
      });
      row.querySelector("[data-offer-go]").addEventListener("click",
        async (ev) => {
          const raw = row.querySelector("[data-offer-total]").value.trim()
            .replace(",", ".");
          const total = Number(raw);
          if (raw === "" || !isFinite(total) || total < 0) {
            toast("Bitte einen gültigen Gesamtpreis eingeben");
            return;
          }
          ev.currentTarget.disabled = true;
          try {
            const res = await api(`/lists/${lid}/offer`, { method: "POST",
              body: { total } });
            toast(tr("{sum} anteilig auf {n} Artikel verteilt ✔",
      { sum: fmtEur(total), n: res.count }));
            loadLists();
          } catch (e) {
            toast(e.message);
            ev.currentTarget.disabled = false;
          }
        });
    });

    const lArch = card.querySelector("[data-l-archive]");
    if (lArch) lArch.addEventListener("click", async () => {
      try {
        await api(`/lists/${lid}/archive`, { method: "POST",
          body: { archived: true } });
        toast("Liste archiviert 📦");
        loadLists();
        updateListsTab();
      } catch (e) { toast(e.message); }
    });
    const lRest = card.querySelector("[data-l-restore]");
    if (lRest) lRest.addEventListener("click", async () => {
      try {
        await api(`/lists/${lid}/archive`, { method: "POST",
          body: { archived: false } });
        toast("Liste reaktiviert ✔");
        loadLists();
        updateListsTab();
      } catch (e) { toast(e.message); }
    });
    const lDel = card.querySelector("[data-l-del]");
    if (lDel) lDel.addEventListener("click", async () => {
      if (!confirm(tr("Liste „{name}“ mitsamt Artikeln löschen?",
        { name: list.name }))) return;
      try {
        await api("/lists/" + lid, { method: "DELETE" });
        loadLists();
        updateListsTab();
      } catch (e) { toast(e.message); }
    });

    card.querySelectorAll("[data-ic]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (btn.classList.contains("sel")) return;
        try {
          await api(`/lists/items/${btn.dataset.icid}`, { method: "PATCH",
            body: { condition: btn.dataset.ic } });
          loadLists();
        } catch (e) { toast(e.message); }
      });
    });

    card.querySelectorAll("[data-ip-save]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const iid = btn.dataset.ipSave;
        const raw = card.querySelector(`[data-ip="${iid}"]`).value.trim()
          .replace(",", ".");
        const paid = Number(raw);
        if (raw === "" || !isFinite(paid) || paid < 0) {
          toast("Bitte einen gültigen Betrag eingeben");
          return;
        }
        btn.disabled = true;
        try {
          await api(`/lists/items/${iid}`, { method: "PATCH",
            body: { paid_price: paid } });
          toast("Einkaufspreis gespeichert ✔");
          loadLists();
        } catch (e) {
          toast(e.message);
          btn.disabled = false;
        }
      });
    });

    card.querySelectorAll("[data-i-recv]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const iid = Number(btn.dataset.iRecv);
        const listItem = list.items.find((x) => x.id === iid);
        const row = btn.closest(".fig-row");
        if (row.querySelector("[data-recv-row]")) return;
        const actions = row.querySelector(".fig-actions");
        const dealer2 = state.user && state.user.is_dealer;
        // Zustand steht am Listeneintrag schon fest – nicht erneut abfragen.
        const cond = listItem && listItem.condition === "new" ? "new" : "used";
        const condLabel = cond === "new" ? tr("Neu") : tr("Gebraucht");

        const send = async (mode, paid) => {
          const res = await api(`/lists/items/${iid}/receive`,
            { method: "POST", body: { condition: cond,
              paid_price: paid, mode } });
          if (res.need_mode) return res;
          toast(res.list_archived
            ? "In die Sammlung ✔ – Liste abgearbeitet, ab ins Archiv 🎉"
            : (mode === "replace" ? "Eintrag überschrieben ✔"
               : (res.merged
                  ? "Anzahl erhöht, Einkaufspreis gemittelt ✔"
                  : "In die Sammlung übernommen ✔")));
          if (listItem) {
            await askSetFigures(listItem, cond);
          }
          loadLists();
          updateListsTab();
          return res;
        };

        // Rückfrage, falls der Artikel in diesem Zustand schon vorhanden ist
        const askMode = (owned, paid) => {
          actions.hidden = true;
          const mc = document.createElement("div");
          mc.className = "fig-actions";
          mc.setAttribute("data-recv-row", "");
          mc.style.flexWrap = "wrap";
          mc.innerHTML = `
            <span class="buy-label">Schon ${owned}× in der Sammlung:</span>
            <button class="mini-btn add" data-rm="add">＋ Zusätzlich</button>
            <button class="mini-btn" data-rm="replace">Überschreiben</button>
            <button class="mini-btn" data-rm-cancel>✕</button>`;
          actions.after(mc);
          mc.querySelector("[data-rm-cancel]").addEventListener(
            "click", () => { mc.remove(); actions.hidden = false; });
          mc.querySelectorAll("[data-rm]").forEach((mb) => {
            mb.addEventListener("click", async () => {
              mb.disabled = true;
              try {
                await send(mb.dataset.rm, paid);
              } catch (e2) {
                toast(e2.message);
                mb.disabled = false;
              }
            });
          });
        };

        const doReceive = async (paid) => {
          btn.disabled = true;
          try {
            const res = await send(null, paid);
            if (res.need_mode) askMode(res.owned, paid);
          } catch (e) {
            toast(e.message);
            btn.disabled = false;
            actions.hidden = false;
          }
        };

        if (dealer2) {
          // Profi: Einkaufspreis bestätigen (Zustand ist bereits gewählt)
          actions.hidden = true;
          const chooser = document.createElement("div");
          chooser.className = "fig-actions";
          chooser.setAttribute("data-recv-row", "");
          chooser.style.flexWrap = "wrap";
          chooser.innerHTML = `
            <span class="paid-row buy-paid" style="flex-basis:100%">
              <span class="paid-label">Preis</span>
              <input data-recv-paid class="paid-input" inputmode="decimal" placeholder="0,00" value="${listItem && listItem.paid_price != null ? fmtPaidInput(listItem.paid_price) : ""}">
              <span class="paid-suffix" data-cur>${esc(curSymbol())}</span>
              <span class="sub">leer = BrickLink-Ø</span></span>
            <button class="mini-btn add" data-rc-go>✔ ${condLabel} übernehmen</button>
            <button class="mini-btn" data-rc-cancel>✕</button>`;
          actions.after(chooser);
          chooser.querySelector("[data-rc-cancel]").addEventListener("click",
            () => { chooser.remove(); actions.hidden = false; });
          chooser.querySelector("[data-rc-go]").addEventListener("click",
            async () => {
              const paidEl = chooser.querySelector("[data-recv-paid]");
              let paid = null;
              if (paidEl && paidEl.value.trim() !== "") {
                paid = Number(paidEl.value.trim().replace(",", "."));
                if (!isFinite(paid) || paid < 0) {
                  toast("Bitte einen gültigen Preis eingeben");
                  return;
                }
              }
              chooser.remove();
              await doReceive(paid);
            });
        } else {
          // Kein Profi: direkt mit dem angegebenen Zustand verbuchen
          doReceive(null);
        }
      });
    });
    card.querySelectorAll("[data-i-undo]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await api(`/lists/items/${btn.dataset.iUndo}/undo`,
            { method: "POST" });
          toast("Rückgängig – Sammlung ggf. manuell anpassen");
          showListsTab("shop");
        } catch (e) { toast(e.message); }
      });
    });
    card.querySelectorAll("[data-i-del]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await api("/lists/items/" + btn.dataset.iDel,
            { method: "DELETE" });
          loadLists();
        } catch (e) { toast(e.message); }
      });
    });
  });
}

function listItemRow(it, dealer) {
  const condPrice = it.condition === "new"
    ? (it.price_new || it.price_used) : (it.price_used || it.price_new);
  const prices = condPrice
    ? `${it.condition === "new" ? tr("Ø neu") : tr("Ø gebr.")} `
      + fmtEur(condPrice) : "";
  const doneInfo = it.done
    ? `<div class="sub done-note">✔ in Sammlung${it.done_by_name ? " von " + esc(it.done_by_name) : ""}${it.done_at ? " am " + new Date(it.done_at * 1000).toLocaleDateString(dateLocale()) : ""}</div>`
    : "";
  return `
  <div class="fig-row ${it.done ? "done" : ""}" data-iid="${it.id}">
    <img class="card-img fig-img" src="${imgSrc(it.img_url)}" data-gid="${esc(it.item_id)}" data-gtype="${esc(it.item_type)}" alt="" loading="lazy">
    <div class="fig-info">
      <strong>${esc(it.name)}</strong>
      <div class="sub">${esc(it.item_id)}${it.qty > 1 ? ` · ${it.qty}×` : ""} · ${it.condition === "new" ? tr("Neu") : tr("Gebraucht")}${prices ? " · " + prices : ""}${it.paid_price != null ? esc(tr(" · Einkauf {sum}", { sum: fmtEur(it.paid_price) })) : ""}</div>
      ${doneInfo}
      ${!it.done && dealer ? `
      <div class="fig-actions" style="margin-top:6px">
        <button class="mini-btn cond-mini ${it.condition !== "new" ? "sel" : ""}" data-ic="used" data-icid="${it.id}">Gebraucht</button>
        <button class="mini-btn cond-mini ${it.condition === "new" ? "sel" : ""}" data-ic="new" data-icid="${it.id}">Neu</button>
      </div>
      <div class="paid-row" style="margin-top:6px">
        <span class="paid-label">Einkauf</span>
        <input data-ip="${it.id}" class="paid-input" inputmode="decimal" placeholder="0,00" value="${it.paid_price != null ? fmtPaidInput(it.paid_price) : ""}">
        <span class="paid-suffix" data-cur>${esc(curSymbol())}</span>
        <button class="mini-btn add" data-ip-save="${it.id}" style="flex:1;min-height:38px">✓</button>
      </div>` : ""}
      <div class="fig-actions">
        ${!it.done ? `<button class="mini-btn add" data-i-recv="${it.id}">✔ Da! Ab in die Sammlung</button>` : ""}
        ${!it.done && dealer ? `<button class="mini-btn danger" data-i-del="${it.id}">✕</button>` : ""}
        ${it.done && dealer ? `<button class="mini-btn" data-i-undo="${it.id}">↩︎ Rückgängig</button>` : ""}
      </div>
    </div>
  </div>`;
}

async function addToList(list, it, condition, paidPrice) {
  const cond = condition === "new" ? "new" : "used";
  try {
    const body = { item_id: it.item_id, item_type: it.item_type || "minifig",
      name: it.name, img_url: it.img_url || "",
      bricklink_url: it.bricklink_url || "", year: it.year || 0,
      condition: cond };
    if (paidPrice != null) body.paid_price = paidPrice;
    const res = await api(`/lists/${list.id}/items`, { method: "POST",
      body });
    const suffix = cond === "new" ? " (Neu)" : "";
    toast(res.merged ? tr("Menge erhöht in „{name}“ 🛒", { name: list.name }) + suffix
                     : `Auf "${list.name}" gesetzt 🛒${suffix}`);
  } catch (e) { toast(e.message); }
}

function wireCartButtons(box, items) {
  box.querySelectorAll("[data-cart]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      let lists;
      try {
        lists = (await api("/lists")).lists || [];
      } catch (e) { toast(e.message); return; }
      const it = items[Number(btn.dataset.cart)];
      const card = btn.closest(".card");
      if (card.querySelector("[data-cart-row]")) return;
      const actions = card.querySelector(".card-actions");
      actions.hidden = true;
      const row = document.createElement("div");
      row.className = "card-actions btn-grid";
      row.setAttribute("data-cart-row", "");
      actions.after(row);

      const close = () => { row.remove(); actions.hidden = false; };
      let cond = "used";
      let priceVal = "";
      const priceField = () => `
        <input data-cl-price inputmode="decimal" value="${esc(priceVal)}"
          placeholder="${esc(tr("Einkauf {cur} (optional)", { cur: curSymbol() }))}" style="grid-column:1/-1">`;
      const wirePriceField = () => {
        const inp = row.querySelector("[data-cl-price]");
        if (inp) inp.addEventListener("input", () => {
          priceVal = inp.value;
        });
      };
      const readPrice = () => {
        const raw = priceVal.trim().replace(",", ".");
        if (!raw) return null;
        const n = Number(raw);
        if (!Number.isFinite(n) || n < 0) return undefined;
        return Math.round(n * 100) / 100;
      };
      const condChips = () => `
        <button class="mini-btn cond-mini ${cond !== "new" ? "sel" : ""}" data-cc="used">Gebraucht</button>
        <button class="mini-btn cond-mini ${cond === "new" ? "sel" : ""}" data-cc="new">Neu</button>`;
      const wireCondChips = (rerender) => {
        row.querySelectorAll("[data-cc]").forEach((c) => {
          c.addEventListener("click", () => {
            if (c.dataset.cc === cond) return;
            cond = c.dataset.cc;
            rerender();
          });
        });
      };

      const renderNew = () => {
        const today = new Date().toLocaleDateString(dateLocale(),
          { day: "2-digit", month: "2-digit" });
        row.innerHTML = `
          ${condChips()}${priceField()}
          <span class="buy-label">Neue Einkaufsliste anlegen:</span>
          <input data-cl-name maxlength="120" style="grid-column:1/-1"
            value="Flohmarkt ${today}">
          <button class="mini-btn add" data-cl-create>Anlegen &amp; drauflegen</button>
          <button class="mini-btn" data-cl-back>${lists.length ? "Zurück" : "Abbrechen"}</button>`;
        const input = row.querySelector("[data-cl-name]");
        input.focus();
        input.select();
        row.querySelector("[data-cl-back]").addEventListener("click",
          () => { lists.length ? renderChooser() : close(); });
        const create = async () => {
          const name = input.value.trim();
          if (!name) { toast("Bitte einen Namen eingeben"); return; }
          const price = readPrice();
          if (price === undefined) {
            toast("Preis bitte als Zahl, z. B. 4,50");
            return;
          }
          const createBtn = row.querySelector("[data-cl-create]");
          createBtn.disabled = true;
          try {
            const res = await api("/lists", { method: "POST",
              body: { name } });
            await addToList({ id: res.id, name }, it, cond, price);
            updateListsTab();
            close();
          } catch (e) {
            toast(e.message);
            createBtn.disabled = false;
          }
        };
        row.querySelector("[data-cl-create]").addEventListener("click",
          create);
        input.addEventListener("keydown", (ev) => {
          if (ev.key === "Enter") create();
        });
        wireCondChips(renderNew);
        wirePriceField();
      };

      const renderChooser = () => {
        row.innerHTML = condChips() + priceField()
          + `<span class="buy-label">Auf welche Liste?</span>`
          + lists.map((l) => `<button class="mini-btn" data-cl="${l.id}">${esc(l.name)}</button>`).join("")
          + `<button class="mini-btn add" data-cl-new>＋ Neue Liste</button>`
          + `<button class="mini-btn" data-cl-cancel>Abbrechen</button>`;
        row.querySelector("[data-cl-cancel]").addEventListener("click",
          close);
        row.querySelector("[data-cl-new]").addEventListener("click",
          renderNew);
        row.querySelectorAll("[data-cl]").forEach((b) => {
          b.addEventListener("click", async () => {
            const price = readPrice();
            if (price === undefined) {
              toast("Preis bitte als Zahl, z. B. 4,50");
              return;
            }
            const l = lists.find((x) => x.id === Number(b.dataset.cl));
            await addToList(l, it, cond, price);
            close();
          });
        });
        wireCondChips(renderChooser);
        wirePriceField();
      };

      if (lists.length) renderChooser(); else renderNew();
    });
  });
}

/* ---------------------------------------------------------------- Statistik */
const TYPE_LABELS = { minifig: "Figuren", set: "Sets", part: "Teile" };

async function loadStats() {
  const box = $("stats-view");
  box.innerHTML = brickLoading("Statistik wird geladen …");
  try {
    const data = await api("/stats/dashboard");
    renderStats(data);
  } catch (e) {
    box.innerHTML = `<p class="empty">${esc(e.message)}</p>`;
  }
}

function renderStats(data) {
  const t = data.totals;
  const dealer = state.user && state.user.is_dealer;
  const profitCls = t.profit >= 0 ? "profit-pos" : "profit-neg";

  const chips = `
  <div class="card">
    <div class="stats-row">
      <div class="stat-chip"><strong>${t.pieces}</strong><span>Stück</span></div>
      <div class="stat-chip"><strong>${t.unique}</strong><span>verschieden</span></div>
      <div class="stat-chip"><strong>${fmtEur(t.avg_piece)}</strong><span>Ø je Stück</span></div>
    </div>
    <div class="stats-row">
      <div class="stat-chip"><strong>${fmtEur(t.value)}</strong><span>Gesamtwert</span></div>
      ${dealer ? `
      <div class="stat-chip"><strong>${fmtEur(t.paid)}</strong><span>bezahlt</span></div>
      <div class="stat-chip"><strong class="${profitCls}">${t.profit >= 0 ? "+" : "−"}${fmtEur(Math.abs(t.profit))}</strong><span>Gewinn</span></div>` : ""}
    </div>
    ${dealer && data.lists_breakdown && data.lists_breakdown.length ? `
    <div class="stats-row">
      <div class="stat-chip tappable" data-lists-modal title="Listen anzeigen und verwalten">
        <strong data-lists-total>${fmtEur(t.lists_paid)}</strong>
        <span><span data-lists-label>${esc(t.lists_count === 1 ? tr("Einkauf auf 1 Liste") : tr("Einkauf auf {n} Listen", { n: t.lists_count }))}</span> ⚙️</span>
      </div>
    </div>` : ""}
    ${t.paid_estimated > 0 ? `<div class="price-note" style="margin-top:6px">${
      esc(tr("Bei Figuren, die in euren Sets stecken, zählt ein nur ⚙️ "
        + "automatisch ermittelter Kaufpreis nicht extra – der Set-Preis "
        + "deckt sie ab ({sum}). ✏️ Selbst eingetragene Preise zählen immer "
        + "mit, auch bei Set-Figuren.", { sum: fmtEur(t.paid_estimated) }))
    }</div>` : ""}
    ${t.in_sets_value > 0 ? `<div class="price-note" style="margin-top:6px">${
      esc(tr("Figuren, die in euren Sets stecken, sind im Set-Preis enthalten "
        + "und werden nicht doppelt gezählt ({sum}). Details unter ❓ Hilfe → "
        + "„Wie der Wert berechnet wird“.", { sum: fmtEur(t.in_sets_value) }))
    }</div>` : ""}
  </div>`;

  const chart = `
  <div class="card">
    <h3 style="margin:0 0 4px">Wertentwicklung</h3>
    ${data.timeline.length >= 2 ? totalChart(data.timeline)
      : `<div class="price-note">Der Wertverlauf wächst mit jedem
         Preis-Update – schau in ein paar Tagen wieder rein.</div>`}
  </div>`;

  const typeRows = Object.entries(data.by_type)
    .sort((a, b) => b[1].value - a[1].value)
    .map(([k, v]) => statBarRow(TYPE_LABELS[k] || k, v, t.value)).join("");
  const condRows = Object.entries(data.by_condition)
    .sort((a, b) => b[1].value - a[1].value)
    .map(([k, v]) => statBarRow(k === "new" ? tr("Neu") : tr("Gebraucht"), v,
      t.value)).join("");
  const split = `
  <div class="card">
    <h3 style="margin:0 0 8px">Aufteilung</h3>
    ${typeRows}
    <div style="height:8px"></div>
    ${condRows}
  </div>`;

  const years = data.by_year.length >= 2 ? `
  <div class="card">
    <h3 style="margin:0 0 4px">Wert nach Erscheinungsjahr</h3>
    ${yearChart(data.by_year)}
  </div>` : "";

  const top = data.top.length ? `
  <div class="card">
    <h3 style="margin:0 0 6px">${esc(tr("Top {n} nach Wert", { n: data.top.length }))}</h3>
    <div class="set-figs">
      ${data.top.map((it, i) => `
      <div class="fig-row">
        <img class="card-img fig-img" src="${imgSrc(it.img_url)}" data-gid="${esc(it.item_id)}" data-gtype="${esc(it.item_type)}" alt="" loading="lazy">
        <div class="fig-info" style="display:flex;align-items:center;justify-content:space-between;gap:8px">
          <strong style="font-size:14px">${i + 1}. ${esc(it.name)}${it.quantity > 1 ? ` (${it.quantity}×)` : ""}</strong>
          <b style="white-space:nowrap">${fmtEur(it.value)}</b>
        </div>
      </div>`).join("")}
    </div>
  </div>` : "";

  const winners = dealer && data.winners.length ? `
  <div class="card">
    <h3 style="margin:0 0 6px">Beste Wertsteigerungen</h3>
    ${data.winners.map((it, i) => `
      <div class="sub" style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px dashed var(--line)">
        <span>${i + 1}. ${esc(it.name)}</span>
        <b class="${it.gain >= 0 ? "profit-pos" : "profit-neg"}">${it.gain >= 0 ? "+" : "−"}${fmtEur(Math.abs(it.gain))}</b>
      </div>`).join("")}
    <div class="price-note" style="margin-top:6px">Aktueller Wert minus Kaufpreis</div>
  </div>` : "";

  $("stats-view").innerHTML = chips + chart + split + years + top + winners;
  wireYearChart();

  const lm = $("stats-view").querySelector("[data-lists-modal]");
  if (lm) lm.addEventListener("click", () => openListsPaidModal(data.lists_breakdown, lm));
}

/* Popup: Einkauf je Liste, mit „inventarisiert"-Haken. Angehakte Listen
   zählen nicht in die Summe (bereits erfasst). */
function openListsPaidModal(breakdown, chipEl) {
  closeCardModal();
  const rows = breakdown.map((l) => `
    <label class="lists-paid-row">
      <input type="checkbox" data-inv="${l.id}" ${l.inventoried ? "checked" : ""}>
      <span class="lists-paid-name">${esc(l.name)}${l.archived ? ` <span class="badge badge-archived">archiviert</span>` : ""}</span>
      <b class="lists-paid-sum">${fmtEur(l.paid)}</b>
    </label>`).join("");
  const overlay = document.createElement("div");
  overlay.className = "card-modal-overlay";
  overlay.id = "card-modal";
  overlay.innerHTML = `
    <div class="card-modal">
      <button class="card-modal-close" aria-label="Schließen">✕</button>
      <div class="card modal-inner open" role="dialog" aria-modal="true">
        <h3 style="margin:0 0 2px">Einkauf auf Listen</h3>
        <div class="price-note" style="margin-bottom:10px">Häkchen bei <b>inventarisiert</b> nimmt eine Liste aus der Summe – sie ist dann ja schon erfasst.</div>
        <div class="lists-paid-list">${rows}</div>
        <div class="lists-paid-total">
          <span>Zählt zusammen</span>
          <b data-lp-total></b>
        </div>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  const inner = overlay.querySelector(".modal-inner");

  const recalc = () => {
    // Popup zählt alle Listen (offen + archiviert), die nicht inventarisiert sind
    const sum = breakdown.reduce((s, l) => s + (l.inventoried ? 0 : l.paid), 0);
    inner.querySelector("[data-lp-total]").textContent = fmtEur(sum);
    // Übersichts-Feld zählt nur offene, nicht inventarisierte Listen
    if (chipEl) {
      const openSum = breakdown.reduce((s, l) =>
        s + (!l.archived && !l.inventoried ? l.paid : 0), 0);
      const openN = breakdown.filter((l) => !l.archived && !l.inventoried).length;
      chipEl.querySelector("[data-lists-total]").textContent = fmtEur(openSum);
      chipEl.querySelector("[data-lists-label]").textContent =
        "Einkauf auf " + (openN === 1 ? "1 Liste" : openN + " Listen");
    }
  };
  recalc();

  inner.querySelectorAll("[data-inv]").forEach((cb) => {
    cb.addEventListener("change", async () => {
      const id = Number(cb.dataset.inv);
      const l = breakdown.find((x) => x.id === id);
      const want = cb.checked;
      cb.disabled = true;
      try {
        await api(`/lists/${id}/inventoried`, { method: "POST",
          body: { inventoried: want } });
        l.inventoried = want;
        recalc();
      } catch (e) {
        cb.checked = !want;         // Fehler: zurücksetzen
        toast(e.message);
      } finally { cb.disabled = false; }
    });
  });

  const done = () => closeCardModal();
  overlay.querySelector(".card-modal-close").addEventListener("click", done);
  overlay.addEventListener("click", (ev) => { if (ev.target === overlay) done(); });
  cardModalKeyHandler = (ev) => { if (ev.key === "Escape") done(); };
  document.addEventListener("keydown", cardModalKeyHandler);
}

function wireYearChart() {
  const detail = $("year-detail");
  const bars = document.querySelectorAll(".year-bar");
  if (!detail || !bars.length) return;
  const show = (bar) => {
    document.querySelectorAll(".year-bar").forEach((b) =>
      b.setAttribute("fill", "var(--chart-new)"));
    bar.setAttribute("fill", "var(--chart-pick)");
    detail.innerHTML = `<b>${bar.dataset.year}</b>: `
      + `${bar.dataset.value} · ${bar.dataset.pieces} Stück`;
  };
  bars.forEach((bar) => {
    bar.addEventListener("click", () => show(bar));
  });
}

function statBarRow(label, v, total) {
  const pct = total > 0 ? Math.round((v.value / total) * 100) : 0;
  return `
  <div class="stat-bar-row">
    <div class="sub" style="display:flex;justify-content:space-between">
      <span>${esc(tr("{label} · {n} Stück",
        { label: tr(label), n: v.pieces }))}</span>
      <b>${fmtEur(v.value)} (${pct} %)</b>
    </div>
    <div class="stat-bar"><div class="stat-bar-fill" style="width:${pct}%"></div></div>
  </div>`;
}

function totalChart(pts) {
  const w = 560, h = 150, padX = 8, padT = 12, padB = 22;
  const values = pts.map((p) => p.value);
  let lo = Math.min(...values), hi = Math.max(...values);
  if (hi - lo < 0.01) { lo -= 1; hi += 1; }
  const t0 = pts[0].ts, t1 = pts[pts.length - 1].ts || t0 + 1;
  const x = (ts) => padX + ((ts - t0) / Math.max(1, t1 - t0)) * (w - 2 * padX);
  const y = (v) => padT + (1 - (v - lo) / (hi - lo)) * (h - padT - padB);
  const line = pts.map((p) => `${x(p.ts).toFixed(1)},${y(p.value).toFixed(1)}`)
    .join(" ");
  const dFmt = (ts) => new Date(ts * 1000).toLocaleDateString(dateLocale(),
    { day: "2-digit", month: "2-digit", year: "2-digit" });
  const uid = "v" + Math.random().toString(36).slice(2, 8);
  const boden = (h - padB).toFixed(1);
  const flaeche = pts.length > 1
    ? `${x(pts[0].ts).toFixed(1)},${boden} ${line} ${x(pts[pts.length - 1].ts).toFixed(1)},${boden}`
    : "";
  return `
  <svg viewBox="0 0 ${w} ${h}" class="history-svg" role="img" aria-label="${esc(tr("Wertentwicklung"))}">
    <defs>
      <linearGradient id="${uid}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="var(--chart-new)" stop-opacity=".34"/>
        <stop offset="100%" stop-color="var(--chart-new)" stop-opacity="0"/>
      </linearGradient>
    </defs>
    <line x1="${padX}" y1="${(padT + (h - padT - padB) / 2).toFixed(1)}"
          x2="${w - padX}" y2="${(padT + (h - padT - padB) / 2).toFixed(1)}"
          class="hist-grid"/>
    <line x1="${padX}" y1="${h - padB}" x2="${w - padX}" y2="${h - padB}" class="hist-axis"/>
    ${flaeche ? `<polygon points="${flaeche}" fill="url(#${uid})"/>` : ""}
    <polyline points="${line}" fill="none" stroke="var(--chart-new)"
              stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"/>
    ${pts.map((p) => `<circle cx="${x(p.ts).toFixed(1)}" cy="${y(p.value).toFixed(1)}" r="3" fill="var(--chart-new)" stroke="var(--chart-bg)" stroke-width="1.6"/>`).join("")}
    <text x="${padX}" y="${h - 6}" class="hist-label">${dFmt(t0)}</text>
    <text x="${w - padX}" y="${h - 6}" text-anchor="end" class="hist-label">${dFmt(t1)}</text>
    <text x="${padX}" y="${padT + 2}" class="hist-label">${fmtEur(hi)}</text>
    <text x="${padX}" y="${h - padB - 4}" class="hist-label">${fmtEur(lo)}</text>
  </svg>
  <div class="price-note">Wertentwicklung eurer heutigen Sammlung
    (eigene Preisaufzeichnung)</div>`;
}

function yearChart(list) {
  const w = 560, h = 150, padB = 22, padT = 16;
  const maxV = Math.max(...list.map((e) => e.value)) || 1;
  const gap = 3;
  const bw = Math.max(4, Math.floor((w - 16) / list.length) - gap);
  const bars = list.map((e, i) => {
    const bh = Math.max(2, (e.value / maxV) * (h - padT - padB));
    const bx = 8 + i * (bw + gap);
    const by = h - padB - bh;
    return `<rect class="year-bar" x="${bx}" y="${by.toFixed(1)}" `
      + `width="${bw}" height="${bh.toFixed(1)}" rx="3" fill="var(--chart-new)" `
      + `style="cursor:pointer" data-year="${e.year}" `
      + `data-value="${fmtEur(e.value)}" data-pieces="${e.pieces}">`
      + `<title>${esc(tr("{jahr}: {wert} ({n} Stück)",
        { jahr: e.year, wert: fmtEur(e.value), n: e.pieces }))}</title></rect>`;
  }).join("");
  const first = list[0], last = list[list.length - 1];
  const peak = list.reduce((a, b) => (b.value > a.value ? b : a), list[0]);
  const px = 8 + list.indexOf(peak) * (bw + gap) + bw / 2;
  return `
  <svg viewBox="0 0 ${w} ${h}" class="history-svg" role="img" aria-label="Wert nach Jahr">
    ${bars}
    <text x="8" y="${h - 6}" class="hist-label">${first.year}</text>
    <text x="${w - 8}" y="${h - 6}" text-anchor="end" class="hist-label">${last.year}</text>
    <text x="${Math.min(Math.max(px, 30), w - 30)}" y="${padT - 4}" text-anchor="middle" class="hist-label">${peak.year}: ${fmtEur(peak.value)}</text>
  </svg>
  <div class="year-detail" id="year-detail">Balken antippen für Details je Jahr</div>`;
}

/* ---------------------------------------------------------------- CSV-Import */
function downloadCsvSample() {
  downloadCsv("brickfolio-import-beispiel.csv", [
    ["Nummer", "Typ", "Name", "Anzahl", "Zustand", "Bezahlt", "Jahr",
     "Notizen"],
    ["sw0815", "Figur", "Shoretrooper", "2", "Gebraucht", "24,50", "2016",
     "Flohmarkt Ottobrunn"],
    ["75154", "Set", "TIE Striker", "1", "Neu", "89,99", "2016", ""],
    ["col424", "Figur", "", "1", "Gebraucht", "", "", "leerer Name: Nummer wird als Name verwendet"],
    ["manuell-01", "Figur", "Eigenbau-Ritter", "1", "Gebraucht", "3,00", "",
     "eigene Nummern bekommen keine BrickLink-Preise"],
  ]);
  toast("Beispiel-CSV heruntergeladen 💾");
}

async function importCsvFile(file) {
  let text;
  try {
    text = await file.text();
  } catch (_) {
    toast("Datei konnte nicht gelesen werden");
    return;
  }
  try {
    const res = await api("/import/csv", { method: "POST",
      body: { csv: text } });
    let msg = tr("Import fertig: {neu} neu, {zus} zusammengeführt",
      { neu: res.created, zus: res.merged });
    if (res.error_count) msg += `, ${res.error_count} Fehler`;
    toast(msg + " ✔");
    if (res.errors && res.errors.length) {
      alert("Nicht importierte Zeilen:\n" + res.errors
        .map((e) => `Zeile ${e.line}: ${e.error}`).join("\n")
        + (res.error_count > res.errors.length ? "\n…" : ""));
    }
  } catch (e) { toast(e.message); }
}

/* ---------------------------------------------------------------- Verkaufsliste */
async function toggleDuplicates() {
  const box = $("duplicates-box");
  if (!box.hidden) {
    box.hidden = true;
    $("btn-duplicates").textContent = tr("📋 Verkaufsliste (Doppelte)");
    return;
  }
  try {
    const data = await api("/duplicates");
    state.duplicates = data;
    renderDuplicates(data);
    box.hidden = false;
    $("btn-duplicates").textContent = tr("📋 Verkaufsliste ausblenden");
  } catch (e) { toast(e.message); }
}

function renderDuplicates(data) {
  const box = $("duplicates-box");
  if (!data.items.length) {
    box.innerHTML = `<div class="card"><div class="price-note">
      Keine Doppelten – alles Einzelstücke.</div></div>`;
    return;
  }
  box.innerHTML = `
  <div class="card">
    <div class="card-head"><div class="card-title">
      <strong>📋 Verkaufsliste – Doppelte</strong>
      <div class="sub">${esc(tr("{n} Stück abgebbar · Verkaufswert ca. {wert}",
        { n: data.stats.pieces, wert: fmtEur(data.stats.value) }))}
        <span class="search-hint">(1 Exemplar bleibt immer · für eigene Sets gebrauchte Figuren zusätzlich reserviert)</span></div>
    </div></div>
    <div class="set-figs">
      ${data.items.map((it) => `
      <div class="fig-row">
        <img class="card-img fig-img" src="${imgSrc(it.img_url)}" data-gid="${esc(it.item_id)}" data-gtype="${esc(it.item_type)}" alt="" loading="lazy">
        <div class="fig-info">
          <strong>${esc(it.name)}</strong>
          <div class="sub">${esc(it.item_id)} · ${it.condition === "new" ? tr("Neu") : tr("Gebraucht")}
            · ${it.quantity}× vorhanden${
              it.set_reserved > 0
                ? " " + tr("({n}× für Sets reserviert)", { n: it.set_reserved })
                : (it.reserved > 0 ? ` (1 behalten)` : "")
            } → <b>${it.surplus}× abgebbar</b>
            ${it.unit_price ? ` · Ø ${fmtEur(it.unit_price)}${it.surplus > 1 ? " → " + fmtEur(it.value) : ""}` : ""}</div>
        </div>
      </div>`).join("")}
    </div>
    <div class="card-actions btn-grid" style="margin-top:8px">
      <button class="mini-btn" id="btn-dup-csv">Als CSV</button>
      <button class="mini-btn" id="btn-dup-print">Drucken</button>
    </div>
  </div>`;
  $("btn-dup-csv").addEventListener("click", exportDuplicatesCsv);
  $("btn-dup-print").addEventListener("click", printDuplicates);
}

function exportDuplicatesCsv() {
  const data = state.duplicates;
  const rows = [[tr("Nummer"), tr("Name"), tr("Zustand"), tr("Vorhanden"),
    tr("Abgebbar"), geldSpalte("Ø Stück"), geldSpalte("Wert")]];
  data.items.forEach((it) => rows.push([it.item_id, it.name,
    it.condition === "new" ? tr("Neu") : tr("Gebraucht"), it.quantity, it.surplus,
    numLoc(it.unit_price), numLoc(it.value)]));
  downloadCsv(tr("brickfolio-verkaufsliste.csv"), rows);
  toast(tr("Verkaufsliste exportiert ✔"));
}

function printDuplicates() {
  const data = state.duplicates;
  const rows = data.items.map((it) => [it.item_id, it.name,
    it.condition === "new" ? tr("Neu") : tr("Gebraucht"),
    it.surplus, it.unit_price ? fmtEur(it.unit_price) : "",
    it.value ? fmtEur(it.value) : ""]);
  printTable(tr("Verkaufsliste – Doppelte"),
    tr("{n} Stück abgebbar · Verkaufswert ca. {wert}",
      { n: data.stats.pieces, wert: fmtEur(data.stats.value) }),
    [tr("Nummer"), tr("Name"), tr("Zustand"), tr("Abgebbar"), tr("Ø Stück"),
     tr("Wert")], rows,
    ["num", "name", "cond", "qty", "price", "price"]);
}

/* ------------------------------------------------- Fehlende Set-Figuren */
function missingSetLinks(sets) {
  const links = sets.map((s) =>
    `<button class="set-link owned" data-jump-set="${esc(s.no)}">`
    + `${esc(s.name)} (${esc(s.no)}${s.qty > 1 ? `, ${s.qty}×` : ""})</button>`);
  if (links.length <= 1) return links.join("");
  return links[0]
    + `<span class="more-sets" hidden> · ${links.slice(1).join(" · ")}</span> `
    + `<button class="set-link more-toggle" data-more-sets>+${links.length - 1} weitere ▾</button>`;
}

async function toggleMissingFigs() {
  const box = $("missing-figs-box");
  const btn = $("btn-missing-figs");
  if (!box.hidden) {
    box.hidden = true;
    btn.textContent = tr("🧩 Fehlende Set-Figuren");
    return;
  }
  btn.disabled = true;
  try {
    const data = await api("/missing_set_figs");
    state.missingFigs = data;
    renderMissingFigs(data);
    box.hidden = false;
    btn.textContent = tr("🧩 Fehlende ausblenden");
  } catch (e) {
    toast(e.message);
  } finally {
    btn.disabled = false;
  }
}

function renderMissingFigs(data) {
  const box = $("missing-figs-box");
  const s = data.stats;
  if (!data.items.length) {
    box.innerHTML = `<div class="card"><div class="price-note">${
      s.sets_total
        ? "Alle Figuren eurer Sets sind vollständig ✔"
        : "Noch keine Sets in der Sammlung."
    }</div></div>`;
    return;
  }
  box.innerHTML = `
  <div class="card">
    <div class="card-head"><div class="card-title">
      <strong>🧩 Fehlende Set-Figuren</strong>
      <div class="sub">${esc(tr("{n} Figuren fehlen in {offen} von {ges} Sets",
        { n: s.pieces, offen: s.sets_incomplete, ges: s.sets_total }))}${
          s.est_cost > 0 ? esc(tr(" · Nachkauf ca. {wert}",
            { wert: fmtEur(s.est_cost) })) : ""}</div>
    </div></div>
    ${s.details_pending > 0 ? `
    <div class="mf-pending">
      <span>ℹ️ Bei ${s.details_pending} ${s.details_pending === 1 ? "Set" : "Sets"}
        fehlen noch Figuren-Namen und -Bilder (unten nur die Nummer zu sehen).</span>
      ${s.can_fetch
        ? `<button class="mini-btn" id="btn-mf-details">🔄 Namen &amp; Bilder nachladen</button>`
        : `<span class="search-hint">Dafür wird ein BrickLink-Schlüssel benötigt
            (Mehr → API-Schlüssel).</span>`}
    </div>` : ""}
    <div class="set-figs">
      ${data.items.map((it, i) => `
      <div class="fig-row" data-mf-row="${i}">
        <img class="card-img fig-img" src="${imgSrc(it.img_url)}" data-gid="${esc(it.item_id)}" data-gtype="minifig" alt="" loading="lazy">
        <div class="fig-info">
          <strong>${esc(it.name)}</strong>
          <div class="sub">${esc(it.item_id)} · <b>${it.missing}× fehlt</b>${
            it.owned > 0 ? " " + esc(tr("({n} von {max} da)",
              { n: it.owned, max: it.needed })) : ""}${
            it.unit_price ? ` · Ø ${fmtEur(it.unit_price)}` : ""}</div>
          <div class="sub in-sets">📦 für: ${missingSetLinks(it.sets)}</div>
          ${it.on_lists && it.on_lists.length ? `<span class="badge badge-list">🛒 ${it.on_lists_qty}× auf ${it.on_lists.length === 1 ? `»${esc(it.on_lists[0])}«` : `${it.on_lists.length} Listen`}</span>` : ""}
          ${it.wanted ? `<span class="badge badge-wanted">⭐ auf der Wunschliste</span>` : ""}
          <div class="fig-actions">
            ${it.wanted ? "" : `<button class="mini-btn" data-mf-want="${i}">☆ Merken</button>`}
            <a class="mini-btn link" href="${esc(it.bricklink_url)}" target="_blank" rel="noopener">BrickLink ↗</a>
          </div>
        </div>
      </div>`).join("")}
    </div>
    <div class="card-actions btn-grid" style="margin-top:8px">
      <button class="mini-btn add" id="btn-mf-want-all">☆ Alle auf die Wunschliste</button>
      <button class="mini-btn" id="btn-mf-csv">Als CSV</button>
      <button class="mini-btn" id="btn-mf-print">Drucken</button>
    </div>
  </div>`;

  const detailsBtn = $("btn-mf-details");
  if (detailsBtn) detailsBtn.addEventListener("click", fetchMissingFigDetails);

  box.querySelectorAll("[data-jump-set]").forEach((b) => {
    b.addEventListener("click", (ev) => {
      ev.stopPropagation();
      jumpToSet(b.dataset.jumpSet);
    });
  });
  box.querySelectorAll("[data-more-sets]").forEach((mb) => {
    mb.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const span = mb.closest(".in-sets").querySelector(".more-sets");
      span.hidden = !span.hidden;
      mb.textContent = span.hidden
        ? `+${span.querySelectorAll(".set-link").length} weitere ▾`
        : "weniger ▴";
    });
  });
  box.querySelectorAll("[data-mf-want]").forEach((b) => {
    b.addEventListener("click", async () => {
      b.disabled = true;
      try {
        await wantMissingFig(data.items[Number(b.dataset.mfWant)]);
        toast("Auf die Wunschliste ✔");
        loadWanted();
        refreshMissingFigs();
      } catch (e) { toast(e.message); b.disabled = false; }
    });
  });
  $("btn-mf-want-all").addEventListener("click", async (ev) => {
    const b = ev.currentTarget;
    b.disabled = true;
    const open = data.items.filter((i) => !i.wanted);
    let done = 0;
    for (const it of open) {
      try { await wantMissingFig(it); done += 1; } catch (_) { /* weiter */ }
    }
    toast(done ? tr("{n} auf die Wunschliste ✔", { n: done })
      : tr("Schon alle gemerkt"));
    loadWanted();
    refreshMissingFigs();
  });
  $("btn-mf-csv").addEventListener("click", exportMissingFigsCsv);
  $("btn-mf-print").addEventListener("click", printMissingFigs);
}

/* Holt die fehlenden Figuren-Details in Häppchen und zeigt den Fortschritt. */
async function fetchMissingFigDetails() {
  const btn = $("btn-mf-details");
  if (btn) btn.disabled = true;
  let total = 0;
  try {
    for (let round = 0; round < 20; round += 1) {
      if (btn) btn.textContent = `🔄 Lade Details … (${total} Sets)`;
      const res = await api("/set_contents/refresh?limit=10",
        { method: "POST" });
      total += res.updated;
      if (res.failed && res.failed.length) {
        toast(tr("{n} Set(s) übersprungen: {grund}",
          { n: res.failed.length, grund: res.failed[0].error }));
      }
      if (!res.remaining || !res.updated) break;
    }
    toast(total ? tr("Details für {n} Sets geladen ✔", { n: total })
                : "Keine weiteren Details verfügbar");
  } catch (e) {
    toast(e.message);
  } finally {
    await refreshMissingFigs();
  }
}

async function refreshMissingFigs() {
  try {
    const data = await api("/missing_set_figs");
    state.missingFigs = data;
    renderMissingFigs(data);
  } catch (e) { toast(e.message); }
}

function wantMissingFig(it) {
  return api("/wanted", { method: "POST", body: {
    item_id: it.item_id, item_type: "minifig", name: it.name,
    img_url: it.img_url || "", bricklink_url: it.bricklink_url || "",
  }});
}

function exportMissingFigsCsv() {
  const data = state.missingFigs;
  const rows = [[tr("Nummer"), tr("Name"), tr("Fehlt"), tr("Benötigt"),
    tr("Vorhanden"), geldSpalte("Ø Stück"), tr("Für Sets"), tr("Auf Liste")]];
  data.items.forEach((it) => rows.push([it.item_id, it.name, it.missing,
    it.needed, it.owned, numLoc(it.unit_price),
    it.sets.map((s) => `${s.name} (${s.no})`).join(" / "),
    (it.on_lists || []).join(" / ")]));
  downloadCsv(tr("brickfolio-fehlende-set-figuren.csv"), rows);
  toast(tr("Liste exportiert ✔"));
}

function printMissingFigs() {
  const data = state.missingFigs;
  const rows = data.items.map((it) => [it.item_id, it.name, it.missing,
    it.unit_price ? fmtEur(it.unit_price) : "",
    it.sets.map((s) => `${s.name} (${s.no})`).join(", ")]);
  printTable(tr("Fehlende Set-Figuren"),
    // Das „von N Sets" stand hier zweimal – einmal im übersetzten Satz und
    // einmal fest angehängt: „… in 3 von 12 Setsvon 12 Sets".
    tr("{n} Figuren fehlen in {offen} von {ges} Sets",
      { n: data.stats.pieces, offen: data.stats.sets_incomplete,
        ges: data.stats.sets_total })
    + (data.stats.est_cost > 0
        ? tr(" · Nachkauf ca. {wert}", { wert: fmtEur(data.stats.est_cost) })
        : ""),
    [tr("Nummer"), tr("Name"), tr("Fehlt"), tr("Ø Stück"), tr("Für Sets")], rows,
    ["num", "name", "qty", "price", "name"]);
}

/* ---------------------------------------------------------------- Passwörter */
async function changeOwnPassword() {
  const err = $("own-pass-error");
  err.hidden = true;
  try {
    const res = await api("/me/password", { method: "POST", body: {
      current_password: $("own-pass-current").value,
      new_password: $("own-pass-new").value,
    }});
    // Der Wechsel beendet **alle** bisherigen Sitzungen – auch die eigene.
    // Der Server legt deshalb eine frische bei; ohne sie flöge man beim
    // eigenen Passwortwechsel aus der App.
    if (res.token) {
      state.token = res.token;
      localStorage.setItem("bf_token", res.token);
    }
    $("own-pass-current").value = "";
    $("own-pass-new").value = "";
    toast("Passwort geändert ✔ – andere Geräte müssen sich neu anmelden");
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  }
}

/* ---------------------------------------------------------------- Export & Druck */
function csvCell(v) {
  v = String(v ?? "");
  return /[";\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
}

/* Zahl fürs Tabellenblatt. Deutsch trennt mit Komma, Englisch mit Punkt –
   sonst liest das Tabellenprogramm den Preis als Text ein. */
function numLoc(v) {
  if (v == null) return "";
  return lang === "en" ? String(v) : String(v).replace(".", ",");
}

function downloadCsv(filename, rows) {
  const csv = "\ufeff" + rows.map((r) => r.map(csvCell).join(";")).join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

const _dateDe = (ts) => new Date(ts * 1000).toLocaleDateString(dateLocale());

/* Spaltenkopf mit Währung – die stand fest auf EUR, auch wenn jemand in
   Pfund rechnet. */
const geldSpalte = (text) => tr(text) + " (" + (state.currency || "EUR") + ")";

async function exportCollectionCsv() {
  const data = await api("/collection?q=&sort=name");
  const rows = [[tr("Nummer"), tr("Name"), tr("Typ"), tr("Jahr"), tr("Anzahl"),
    tr("Zustand"), geldSpalte("Ø Neu"), geldSpalte("Ø Gebraucht"),
    geldSpalte("Wert"), tr("Notizen"), tr("Erfasst von"), tr("Erfasst am")]];
  data.items.forEach((it) => {
    const unit = unitValue(it);
    rows.push([it.item_id, it.name, it.item_type, it.year > 0 ? it.year : "",
      it.quantity, it.condition === "new" ? tr("Neu") : tr("Gebraucht"),
      numLoc(it.price_new), numLoc(it.price_used),
      unit ? numLoc((unit * it.quantity).toFixed(2)) : "",
      it.notes, it.added_by_name || "", _dateDe(it.added_at)]);
  });
  downloadCsv(tr("brickfolio-sammlung.csv"), rows);
  toast(tr("Sammlung exportiert ✔"));
}

async function exportWantedCsv() {
  const data = await api("/wanted");
  const rows = [[tr("Nummer"), tr("Name"), tr("Typ"), tr("Jahr"),
    geldSpalte("Ø Neu"), geldSpalte("Ø Gebraucht"), tr("Notizen"),
    tr("Erfasst von"), tr("Erfasst am")]];
  data.items.forEach((it) => {
    rows.push([it.item_id, it.name, it.item_type, it.year > 0 ? it.year : "",
      numLoc(it.price_new), numLoc(it.price_used), it.notes,
      it.added_by_name || "", _dateDe(it.added_at)]);
  });
  downloadCsv(tr("brickfolio-wunschliste.csv"), rows);
  toast(tr("Wunschliste exportiert ✔"));
}

function printTable(title, subtitle, headers, rows, cols) {
  cols = cols || headers.map(() => "");
  const cls = (i) => (cols[i] ? ` class="pc-${cols[i]}"` : "");
  const area = $("print-area");
  area.innerHTML = `<h1>${esc(title)}</h1>`
    + `<p>${esc(subtitle)}${esc(tr(" · Stand {d}",
        { d: new Date().toLocaleDateString(dateLocale()) }))} · ${esc(appTitle())}</p>`
    + `<table><colgroup>${cols.map((c) => `<col${c ? ` class="pc-${c}"` : ""}>`).join("")}</colgroup>`
    + `<thead><tr>${headers.map((h, i) => `<th${cls(i)}>${esc(h)}</th>`).join("")}</tr></thead>`
    + `<tbody>${rows.map((r) =>
        `<tr>${r.map((c, i) => `<td${cls(i)}>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  window.print();
}

async function printCollection() {
  const data = await api("/collection?q=&sort=name");
  const rows = data.items.map((it) => [it.item_id, it.name,
    it.year > 0 ? it.year : "", it.quantity,
    it.condition === "new" ? tr("Neu") : tr("Gebraucht"),
    unitValue(it) ? fmtEur(unitValue(it)) : ""]);
  const sub = tr("{n} Stück ({v} verschiedene)",
    { n: data.stats.total, v: data.stats.unique_items })
    + (data.stats.total_value
      ? " · " + tr("Gesamtwert ca. {wert}", { wert: fmtEur(data.stats.total_value) })
      : "");
  printTable(tr("Deine LEGO-Sammlung"), sub,
    [tr("Nummer"), tr("Name"), tr("Jahr"), tr("Anz."), tr("Zustand"),
     tr("Ø Preis")], rows,
    ["num", "name", "year", "qty", "cond", "price"]);
}

async function printWanted() {
  const data = await api("/wanted");
  const rows = data.items.map((it) => [it.item_id, it.name,
    it.year > 0 ? it.year : "",
    it.price_used ? fmtEur(it.price_used) : "",
    it.price_new ? fmtEur(it.price_new) : ""]);
  const sub = (data.stats.count === 1 ? tr("1 Wunsch")
                : tr("{n} Wünsche", { n: data.stats.count }))
    + (data.stats.est_cost ? tr(" · geschätzt {wert} (gebraucht)",
      { wert: fmtEur(data.stats.est_cost) }) : "");
  printTable(tr("Deine Wunschliste"), sub,
    [tr("Nummer"), tr("Name"), tr("Jahr"), tr("Ø gebr."), tr("Ø neu")], rows,
    ["num", "name", "year", "price", "price"]);
}

async function downloadBackup() {
  try {
    const data = await api("/backup");
    const blob = new Blob([JSON.stringify(data)],
      { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `brickfolio-sicherung-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    toast("Sicherung heruntergeladen 💾");
  } catch (e) { toast(e.message); }
}

async function restoreBackupFile(file) {
  let data;
  try {
    data = JSON.parse(await file.text());
  } catch (_) {
    toast("Datei ist kein gültiges JSON");
    return;
  }
  const when = data.created_at
    ? new Date(data.created_at * 1000).toLocaleString(dateLocale())
    : tr("unbekannt");
  if (!confirm(tr("Sicherung vom {wann} einspielen?", { wann: when })
    + "\n\n" + tr("ACHTUNG: ALLE aktuellen Daten werden ersetzt!"))) return;
  try {
    const res = await api("/restore", { method: "POST", body: data });
    const n = res.restored && res.restored.collection;
    toast(tr("Sicherung eingespielt ✔ ({n} Sammlungseinträge)", { n: n ?? "?" }));
    setTimeout(() => neuLadenMit("Sicherung eingespielt"), 1200);
  } catch (e) { toast(e.message); }
}

/* ---------------------------------------------------------------- Design */
const THEME_COLOR = { classic: "#FFCF00", galaxy: "#0C1322", nova: "#0A0E1A" };

function applyTheme(name) {
  if (!THEME_COLOR[name]) name = "classic";
  if (name === "classic") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = name;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = THEME_COLOR[name];
  document.querySelectorAll("[data-theme-pick]").forEach((b) =>
    b.classList.toggle("sel", b.dataset.themePick === name));
}

/* ----------------------------------------------- Standard-Sortierung (Profil) */
let sortCardWired = false;

/* Gespeicherte Sortierung auf die Sammlungs-Ansicht anwenden. */
function applySortPref() {
  const pref = state.user && state.user.sortPref;
  const sel = $("sort");
  if (sel && pref && [...sel.options].some((o) => o.value === pref)) {
    sel.value = pref;
  }
  const card = $("sort-pref");
  if (card && pref) card.value = pref;
}

/* Sortierung im Profil merken. Wird sowohl von der Sammlung als auch von
   der Einstellungskarte benutzt – beide zeigen danach dasselbe. */
async function saveSortPref(sort, quiet = true) {
  if (!state.user || state.user.sortPref === sort) return;
  state.user.sortPref = sort;
  localStorage.setItem("bf_user", JSON.stringify(state.user));
  const card = $("sort-pref");
  if (card) card.value = sort;
  const sel = $("sort");
  if (sel) sel.value = sort;
  try {
    await api("/me/sort", { method: "POST", body: { sort } });
    if (!quiet) toast("Standard-Sortierung gespeichert ✔");
  } catch (e) {
    if (!quiet) toast(e.message);
  }
}

async function loadSortCard() {
  const sel = $("sort-pref");
  if (!sel) return;
  sel.value = (state.user && state.user.sortPref) || "added";
  if (!sortCardWired) {
    sortCardWired = true;
    sel.addEventListener("change", async () => {
      await saveSortPref(sel.value, false);
      loadCollection();
    });
    $("btn-themes-refresh").addEventListener("click", refreshThemes);
  }
  loadThemeStatus();
}

/* Wie viele Einträge haben noch kein Thema? Nur dann lohnt der Knopf. */
async function loadThemeStatus() {
  try {
    const s = await api("/themes/status");
    const hint = $("theme-pending-hint");
    hint.hidden = s.pending === 0;
    if (s.pending > 0) {
      $("theme-pending-text").textContent =
        (s.pending === 1 ? tr("Bei 1 Eintrag ist das Thema noch unbekannt.")
          : tr("Bei {n} Einträgen ist das Thema noch unbekannt.",
            { n: s.pending })) + " ";
    }
  } catch (_) { /* Hinweis ist nice-to-have */ }
}

async function refreshThemes() {
  const btn = $("btn-themes-refresh");
  const out = $("theme-refresh-status");
  // Der Knopf steht auch in der Sammlung – dort gibt es diese Zeile nicht.
  // Deshalb geht die Rückmeldung zusätzlich als Meldung raus.
  const sagen = (text) => {
    if (out) { out.hidden = false; out.textContent = text; }
  };
  if (btn) btn.disabled = true;
  sagen(tr("Themen werden bestimmt …"));
  try {
    let total = 0;
    let offen = [];
    for (;;) {
      const res = await api("/themes/refresh?limit=25", { method: "POST" });
      total += res.updated;
      offen = res.unresolved || [];
      sagen(tr("{n} zugeordnet, noch {rest} offen …",
        { n: total, rest: res.remaining }));
      if (res.remaining === 0 || res.updated === 0) break;
    }
    // Wenn etwas übrig bleibt: die Nummern nennen. „Lässt sich nicht
    // bestimmen" allein lässt einen raten, welcher Eintrag gemeint ist.
    const fertig = total
      ? tr("{n} Einträge haben jetzt ein Thema ✔", { n: total })
      : (offen.length
        ? tr("Kein Thema bestimmbar für: {nummern}",
          { nummern: offen.slice(0, 5).join(", ") })
        : tr("Für die übrigen Einträge lässt sich kein Thema bestimmen."));
    sagen(fertig);
    toast(fertig);
    loadThemeStatus();
    loadCollection();
  } catch (e) {
    sagen(e.message);
    toast(e.message);
  } finally { if (btn) btn.disabled = false; }
}

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
      [t.id, t.status, t.unread, t.updated_at, t.last_body]));
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

async function renderTrade(quiet = false) {
  try {
    const { trade, messages } = await api(`/hub/trades/${openTradeId}`);
    // Nur neu zeichnen, wenn sich etwas geändert hat: sonst springt beim
    // automatischen Nachladen die Bildlaufleiste und Getipptes ginge unter.
    const sig = JSON.stringify([trade.status, trade.item_gone, messages.map((m) =>
      [m.id, m.delivered])]);
    if (quiet && sig === tradeSig) return;
    const box = $("trade-msgs");
    const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
    tradeSig = sig;
    $("trade-title").textContent = trade.item_name || trade.item_id;
    $("trade-sub").textContent =
      `${trade.direction === "out" ? "an" : "von"} ${trade.other_name || "?"}`
      + ` · ${tradeStatusText(trade.status)}`;
    $("trade-gone").hidden = !trade.item_gone;
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
          <img class="card-img" src="${imgSrc(it.img_url)}" alt="" loading="lazy">
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
      else renderTrade();
    } catch (e) { toast(e.message); }
  };
  $("trade-accept").addEventListener("click", () => setStatus("accepted"));
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
      to: o.m, item_id: o.i, item_name: o.n, text } });
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
          <img class="card-img" src="${o.img_data ? esc(o.img_data) : imgSrc(o.img_url)}" data-gid="${esc(o.item_id)}" data-gtype="${esc(o.item_type || "minifig")}" alt="" loading="lazy">
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
                     id_: o.item_id };
      card.addEventListener("click", (ev) => {
        if (ev.target.closest("a, .card-img")) return;
        openOffer(data);
      });
    });
  } catch (e) {
    box.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

/* ------------------------------------------------- Externer Zugriff (Cloudflare)
   Reiner Generator: baut aus Token und Adresse den docker-compose-Block. Der
   Token bleibt im Browser – die App kann den Tunnel selbst nicht starten (kein
   Docker-Zugriff), deshalb erzeugt sie nur die fertige Konfiguration. */
function cfSnippet() {
  const host = ($("cf-host").value.trim()) || tr("brickfolio.deine-domain.de");
  const token = ($("cf-token").value.trim()) || tr("DEIN-CLOUDFLARE-TUNNEL-TOKEN");
  return "  cloudflared:\n"
    + "    image: cloudflare/cloudflared:latest\n"
    + "    container_name: brickfolio-tunnel\n"
    + "    restart: unless-stopped\n"
    + "    command: tunnel run\n"
    + "    environment:\n"
    + `      TUNNEL_TOKEN: "${token}"\n`
    + `    # ${tr("Public Hostname im Cloudflare-Dashboard")}: ${host}\n`
    + "    #   -> Service: http://brickfolio:8300";
}

function renderCfSnippet() {
  const el = $("cf-snippet");
  if (el) el.textContent = cfSnippet();
  const url = $("cf-url");
  if (url) {
    const host = ($("cf-host").value.trim()) || tr("brickfolio.deine-domain.de");
    url.textContent = "https://" + host;
  }
}

function initExternalAccess() {
  ["cf-host", "cf-token"].forEach((id) => {
    const el = $(id);
    if (el) el.addEventListener("input", renderCfSnippet);
  });
  renderCfSnippet();
  const copy = $("cf-copy");
  if (copy) {
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(cfSnippet());
        toast("Block kopiert ✔");
      } catch (_) {
        toast("Kopieren nicht möglich – Block bitte von Hand markieren");
      }
    });
  }
}

/* Stern-Bubble: ⭐ am aktuellen Instanz-Standard, ☆ an den übrigen. */
function markDefaultTheme() {
  const def = state.defaultTheme || "classic";
  document.querySelectorAll("[data-default-theme-pick]").forEach((b) => {
    const on = b.dataset.defaultThemePick === def;
    b.classList.toggle("on", on);
    b.textContent = on ? "⭐" : "☆";
    b.title = on ? tr("Aktuelles Standard-Design der Instanz")
                 : tr("Als Standard-Design festlegen");
    b.setAttribute("aria-label", b.title);
  });
}

/* Design nach Login/Refresh setzen: eigene Wahl hat Vorrang, sonst der
   Instanz-Standard, sonst Klassisch. Wird lokal gemerkt (schnelles Zeichnen
   beim nächsten Start ohne Aufblitzen). */
function applyServerTheme(data) {
  state.defaultTheme = data.default_theme || "classic";
  const eff = data.theme || state.defaultTheme;
  applyTheme(eff);
  try { localStorage.setItem("bf_theme", eff); } catch (_) { /* egal */ }
  markDefaultTheme();
}

/* Sprachwahl. Ein Wechsel lädt die Seite neu – das ist ehrlicher als der
   Versuch, jede schon gezeichnete Liste nachträglich umzuschreiben. */
function markLangButtons() {
  document.querySelectorAll("[data-lang-pick]").forEach((b) => {
    b.classList.toggle("sel", b.dataset.langPick === lang);
  });
}

function initLangPicker() {
  markLangButtons();
  document.querySelectorAll("[data-lang-pick]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const pick = btn.dataset.langPick;
      if (pick === lang) return;
      localStorage.setItem("bf_lang", pick);
      await switchLang(pick);           // ohne Neuladen, Eingaben bleiben
      markLangButtons();
      if (state.user) {
        state.user.lang = pick;
        localStorage.setItem("bf_user", JSON.stringify(state.user));
      }
      if (state.token) {
        try {
          await api("/me/lang", { method: "POST", body: { lang: pick } });
        } catch (_) { /* lokal gilt sie trotzdem */ }
      }
    });
  });
}

function initThemePicker() {
  document.querySelectorAll("[data-theme-pick]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const pick = btn.dataset.themePick;
      applyTheme(pick);
      try { localStorage.setItem("bf_theme", pick); } catch (_) { /* egal */ }
      // Im Profil merken, damit es auf allen Geräten gilt
      if (state.token) {
        api("/me/theme", { method: "POST", body: { theme: pick } }).catch(() => {});
      }
    });
  });
  // Admin: Standard-Design der Instanz
  document.querySelectorAll("[data-default-theme-pick]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const pick = btn.dataset.defaultThemePick;
      try {
        await api("/settings/default_theme", { method: "POST",
          body: { theme: pick } });
        state.defaultTheme = pick;
        markDefaultTheme();
        toast("Standard-Design gespeichert ✔");
      } catch (e) { toast(e.message); }
    });
  });
  let stored = "classic";
  try { stored = localStorage.getItem("bf_theme") || "classic"; } catch (_) { /* egal */ }
  applyTheme(stored);
  markDefaultTheme();
}

/* ------------------------------------------------------------ Fehlerberichte
   Aufgetretene Fehler landen beim Server, damit der Admin sie sieht – auch
   die vom Handy der Kinder. Doppelte werden dort zusammengefasst. */
const errorSeen = new Set();      // pro Sitzung nur einmal senden

/* Schleifen sind hier nicht möglich: Der Aufruf fängt seine eigenen Fehler
   ab und wirft nie weiter. Ein „gerade beschäftigt"-Riegel würde dagegen
   echte, gleichzeitig auftretende Fehler verschlucken. */
async function reportError(message, detail, context) {
  if (!state.token) return;
  const key = (message || "") + "|" + (context || "");
  if (!message || errorSeen.has(key)) return;
  errorSeen.add(key);
  try {
    await api("/errors", { method: "POST", body: {
      message: String(message).slice(0, 500),
      detail: detail ? String(detail).slice(0, 4000) : null,
      context: context ? String(context).slice(0, 500) : null,
      app_version: state.appVersion || null,
    }});
  } catch (_) {
    /* Melden darf nie selbst stören */
  }
}

let errorsState = null;

function errorWhen(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleDateString(dateLocale(), { day: "2-digit", month: "2-digit" })
    + " " + d.toLocaleTimeString(dateLocale(), { hour: "2-digit", minute: "2-digit" });
}

function renderErrors() {
  const box = $("errors-list");
  const data = errorsState;
  if (!data) return;
  // Ob ein Token liegt, war bisher nur daran zu erkennen, dass der
  // Melden-Knopf erschien – und der erscheint erst, wenn es einen Fehler
  // gibt. Also hier direkt sagen, was Sache ist.
  zeigeGithubToken(data.token_masked || "");
  loadPushCard();
  renderDiag();
  if (!data.items.length) {
    box.innerHTML = `<div class="price-note">Keine Fehler aufgezeichnet ✔</div>`;
    return;
  }
  box.innerHTML = data.items.map((e) => `
    <div class="fig-row" data-err-row="${e.id}">
      <div class="fig-info">
        <strong>${esc(e.message)}</strong>
        <div class="sub">${e.count}× · zuletzt ${errorWhen(e.last_at)}
          · v${esc(e.app_version || "?")}${
            e.context ? " · " + esc(e.context) : ""}</div>
        ${e.detail ? `<details class="help" style="margin-top:6px">
          <summary>Details</summary>
          <pre class="update-cmd" style="white-space:pre-wrap">${esc(e.detail)}</pre>
        </details>` : ""}
        ${e.issue_url || data.can_report ? `<div class="fig-actions">
          ${e.issue_url
            ? `<a class="mini-btn link" href="${esc(e.issue_url)}" target="_blank" rel="noopener">Issue ansehen ↗</a>`
            : `<button class="mini-btn add" data-err-issue="${e.id}">🐙 Issue anlegen</button>`}
        </div>` : ""}
      </div>
    </div>`).join("")
    // Hinweis einmal für die ganze Karte, nicht je Eintrag
    + (data.can_report ? "" : `<p class="search-hint">Zum Anlegen von Issues
        fehlt der GitHub-Token – siehe unten.</p>`);

  box.querySelectorAll("[data-err-issue]").forEach((b) => {
    b.addEventListener("click", async () => {
      b.disabled = true;
      b.textContent = tr("Lege an …");
      try {
        const res = await api(`/errors/${b.dataset.errIssue}/issue`,
          { method: "POST" });
        toast(res.existed ? "War schon gemeldet" : "Issue angelegt ✔");
        loadErrors();
      } catch (e) {
        toast(e.message);
        b.disabled = false;
        b.textContent = tr("🐙 Issue anlegen");
      }
    });
  });
}

async function loadErrors() {
  try {
    errorsState = await api("/errors");
    renderErrors();
  } catch (_) { /* Karte bleibt leer */ }
}

function errorsAsText() {
  const data = errorsState;
  if (!data || !data.items.length) return "Keine Fehler aufgezeichnet.";
  return data.items.map((e) =>
    `## ${e.message}\n`
    + `- ${e.count}×, zuletzt ${errorWhen(e.last_at)}\n`
    + `- Version: ${e.app_version || "?"}\n`
    + (e.context ? `- Stelle: ${e.context}\n` : "")
    + (e.user_agent ? `- Browser: ${e.user_agent}\n` : "")
    + (e.detail ? `\n\`\`\`\n${e.detail}\n\`\`\`\n` : "")
  ).join("\n");
}

function initErrorReporting() {
  window.addEventListener("error", (ev) => {
    reportError(ev.message, ev.error && ev.error.stack,
      `${ev.filename || "?"}:${ev.lineno || 0}`);
  });
  window.addEventListener("unhandledrejection", (ev) => {
    const r = ev.reason;
    reportError(r && r.message ? r.message : String(r),
      r && r.stack, "unhandledrejection");
  });

  // Blockiert der Browser etwas wegen der Sicherheits-Regeln, ist das kein
  // Programmfehler – `window.onerror` sieht davon nichts. Genau deshalb
  // konnten die Bilder gescannter Artikel wochenlang fehlen, während das
  // Protokoll „keine Fehler" meldete. Gemeldet wird je Regel und Host
  // einmal, nicht je Bild: Sonst stünden hundert gleiche Zeilen darin.
  document.addEventListener("securitypolicyviolation", (ev) => {
    let host = ev.blockedURI || "?";
    try { host = new URL(ev.blockedURI).host || host; } catch (_) { /* inline */ }
    reportError(`Vom Browser blockiert: ${ev.violatedDirective} → ${host}`,
      ev.blockedURI, "csp");
  });

  // Ein Bild, das nicht lädt, wird **nicht** gemeldet.
  //
  // Es war einmal richtig: Damals holte der Browser die Katalogbilder direkt,
  // und ein blockiertes Bild war ein Hinweis auf ein echtes Problem. Seit die
  // Bilder über die eigene Instanz laufen, heißt ein Fehlschlag nur noch: Das
  // CDN hat gerade nicht geantwortet. Das ist kein Fehler der App, der Server
  // fasst von sich aus nach, und der Platzhalter sagt es dem Auge ohnehin.
  // Gemeldet hat es dagegen sehr wohl – bis hin zu einem GitHub-Issue und
  // einer Meldung aufs Handy, für ein einziges hakeliges Vorschaubild.
}

/* ------------------------------------------------- Speicher beobachten

   Ein abgestürzter Tab hinterlässt nichts: keine Konsole, keinen
   Fehlerbericht, kein Netzwerkprotokoll. Genau deshalb schreibt diese
   Messung in den **Browser-Speicher** – der überlebt das Ende des Tabs. Nach
   dem nächsten Start steht also da, was in den Minuten davor passiert ist.

   Gemessen wird, was ohne Sonderrechte messbar ist: der JavaScript-Speicher
   (nur Chromium/Edge), die Zahl der Elemente im Dokument und der Bilder. Das
   entpackte Bild selbst steckt **nicht** im JS-Speicher – bleibt die Kurve
   flach, während der Tab trotzdem stirbt, liegt es also nicht am
   JavaScript, und dann lohnt der Blick auf die anderen Tabs. Auch das ist
   ein Ergebnis. */

const DIAG_KEY = "bf_mem";
const DIAG_MAX = 240;                 // 240 × 30 s = zwei Stunden
const DIAG_TAKT = 30000;
const DIAG_WEG_KEY = "bf_weg";        // Zeitpunkt des ordentlichen Abschieds

function diagLesen() {
  try { return JSON.parse(localStorage.getItem(DIAG_KEY) || "[]"); }
  catch (_) { return []; }
}

function diagMessen(grund = "", geplant = null) {
  const m = performance.memory;
  const punkt = {
    t: Date.now(),
    // MB, gerundet – Nachkommastellen wären hier Scheingenauigkeit
    heap: m ? Math.round(m.usedJSHeapSize / 1048576) : null,
    limit: m ? Math.round(m.jsHeapSizeLimit / 1048576) : null,
    knoten: document.getElementsByTagName("*").length,
    bilder: document.getElementsByTagName("img").length,
    v: (state.appVersion || "").slice(0, 12),
    // Welches Design lief? Nova zeichnet Flächen mit Echtzeit-Weichzeichner
    // („Glas"), und das kostet Grafikspeicher, den keine Messung hier sieht.
    // Ohne diese Angabe ließe sich nie feststellen, ob Abstürze daran hängen.
    d: (document.documentElement.getAttribute("data-theme") || "klassisch"),
    // Startzeit des Servers. Ändert sie sich, ist der Container neu
    // gestartet – und die App lädt sich daraufhin selbst neu. Ohne diese
    // Zahl sah genau das im Verlauf aus wie ein Absturz.
    s: state.serverStartedAt || null,
  };
  if (grund) punkt.g = grund;
  if (grund === "start") {
    // Woher kam dieser Start? `p` ist der Grund, falls die App selbst neu
    // geladen hat. `nav` unterscheidet Neuladen von normalem Aufruf, und
    // `disc` sagt, ob der Browser den Tab wegen Speichermangel weggeräumt
    // hat – das ist der einzige Hinweis auf Speicher, den er herausrückt.
    if (geplant) punkt.p = geplant;
    const nav = performance.getEntriesByType("navigation")[0];
    if (nav && nav.type) punkt.nav = nav.type;
    if (document.wasDiscarded) punkt.disc = 1;
    // Hat sich die vorige Seite ordentlich verabschiedet? `pagehide` läuft
    // bei jedem gewollten Ende – Neuladen, Weiterklicken, Schließen. Bei
    // einem Absturz läuft es nicht.
    //
    // Verglichen wird der Abschied mit dem *letzten Messwert*, nicht mit der
    // Uhr: Wer die App zumacht und drei Stunden später wieder aufmacht, hat
    // sich trotzdem ordentlich verabschiedet. Mit einer Frist von Sekunden
    // wäre genau das als Absturz durchgegangen. Und der Zettel liegt im
    // localStorage – sessionStorage verschwindet ausgerechnet dann, wenn die
    // App geschlossen wird, also im häufigsten sauberen Fall.
    try {
      const weg = Number(localStorage.getItem(DIAG_WEG_KEY) || 0);
      localStorage.removeItem(DIAG_WEG_KEY);
      const vorher = diagLesen();
      const letzte = vorher.length ? vorher[vorher.length - 1].t : 0;
      if (weg && weg + 2000 >= letzte) punkt.sauber = 1;
    } catch (_) { /* egal */ }
  }
  const liste = diagLesen();
  liste.push(punkt);
  while (liste.length > DIAG_MAX) liste.shift();
  try { localStorage.setItem(DIAG_KEY, JSON.stringify(liste)); }
  catch (_) { /* Speicher voll – dann eben nicht */ }
  return punkt;
}

let diagTimer = null;

/* Die App lädt sich an einigen Stellen selbst neu – nach einem Server-Neustart
   etwa, oder nach dem Einspielen einer Sicherung. Im Verlauf sah das bisher
   aus wie ein Absturz: ein „start" wenige Sekunden nach dem letzten Messwert.
   Deshalb hinterlässt jedes gewollte Neuladen hier seinen Grund. */
const DIAG_GRUND_KEY = "bf_reload_grund";

function neuLadenMit(grund) {
  try { sessionStorage.setItem(DIAG_GRUND_KEY, grund); } catch (_) { /* egal */ }
  location.reload();
}

function diagStarten() {
  if (diagTimer) return;
  // „start" markiert den Beginn einer Sitzung. Steht davor ein Messwert von
  // vor wenigen Sekunden, ist die Seite dazwischen weggewesen. Ob sie
  // abgestürzt ist oder ordentlich neu geladen wurde, steht daneben.
  let geplant = null;
  try {
    geplant = sessionStorage.getItem(DIAG_GRUND_KEY);
    sessionStorage.removeItem(DIAG_GRUND_KEY);
  } catch (_) { /* egal */ }
  diagMessen("start", geplant);
  diagTimer = setInterval(diagMessen, DIAG_TAKT);
  // Der Abschiedszettel. Läuft bei Neuladen, Weiterklicken und Schließen –
  // und ausgerechnet dann nicht, wenn der Browser die Seite abwürgt.
  addEventListener("pagehide", () => {
    try { localStorage.setItem(DIAG_WEG_KEY, String(Date.now())); }
    catch (_) { /* egal */ }
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) diagMessen("zurück");
  });
}

function diagZeitraum(ms) {
  const min = Math.round(ms / 60000);
  return min < 60 ? `${min} min` : `${Math.round(min / 60 * 10) / 10} h`;
}

function renderDiag() {
  const box = $("diag-box");
  if (!box) return;
  const liste = diagLesen();
  const zus = $("diag-summary");
  const chart = $("diag-chart");
  if (liste.length < 2) {
    zus.textContent = tr("Noch keine Messwerte – die erste Messung kommt "
      + "innerhalb einer Minute.");
    chart.innerHTML = "";
    return;
  }
  const heaps = liste.map((p) => p.heap).filter((x) => x != null);
  const letzte = liste[liste.length - 1];
  // Ein Neustart kurz nach dem letzten Messwert heißt: Die Seite war weg.
  // Warum, steht am Eintrag – gewolltes Neuladen der App zählt nicht als
  // Absturz, sonst hätte jeder Server-Neustart wie einer ausgesehen.
  let abbruch = 0, geplant = 0, weggeraeumt = 0, serverNeu = 0, sauber = 0;
  // Verglichen wird mit der zuletzt *bekannten* Startzeit: Direkt nach einem
  // Neuladen steht sie noch nicht fest, der Eintrag hat dort kein `s`.
  let letzterServer = null;
  for (let i = 0; i < liste.length; i++) {
    const p = liste[i], vor = liste[i - 1];
    if (p.s) {
      if (letzterServer && p.s !== letzterServer) serverNeu++;
      letzterServer = p.s;
    }
    if (!i || p.g !== "start") continue;
    // Die Frist von 90 Sekunden ist weg: Sie war nur der Notbehelf, solange
    // es den Abschiedszettel nicht gab. Ein Absturz um 21:08, bemerkt beim
    // Wiederöffnen um 21:16, fiel damit durchs Raster.
    if (p.disc) weggeraeumt++;
    else if (p.p) geplant++;
    else if (p.sauber) sauber++;       // von Hand neu geladen o. Ä.
    else if (p.nav === "navigate" && p.t - vor.t >= 90000) continue;
    // Ein frisch geöffneter zweiter Tab lange nach dem letzten Messwert hat
    // weder Zettel noch Vorgeschichte – der zählt nicht. Abgestürzt heißt:
    // die Seite war weg, ohne sich zu verabschieden.
    else abbruch++;
  }
  const teile = [
    tr("{n} Messwerte über {zeit}", { n: liste.length,
      zeit: diagZeitraum(letzte.t - liste[0].t) }),
  ];
  if (heaps.length) {
    teile.push(tr("JS-Speicher jetzt {jetzt} MB (von {min} bis {max}, "
      + "Grenze {limit} MB)", { jetzt: letzte.heap, min: Math.min(...heaps),
      max: Math.max(...heaps), limit: letzte.limit || "?" }));
  } else {
    teile.push(tr("Dieser Browser gibt den Speicherstand nicht preis – "
      + "gemessen werden nur Elemente und Bilder."));
  }
  teile.push(tr("{n} Elemente, {b} Bilder", { n: letzte.knoten, b: letzte.bilder }));
  if (abbruch) {
    teile.push(tr("⚠️ {n}× brach die Seite ab, ohne sich zu verabschieden – "
      + "das ist ein echter Absturz.", { n: abbruch }));
  }
  if (sauber) {
    teile.push(tr("🔄 {n}× wurde die Seite von Hand neu geladen – kein "
      + "Absturz.", { n: sauber }));
  }
  if (weggeraeumt) {
    teile.push(tr("🧹 {n}× hat der Browser den Tab weggeräumt – das tut er "
      + "bei Speichermangel.", { n: weggeraeumt }));
  }
  if (geplant) {
    teile.push(tr("↻ {n}× hat die App selbst neu geladen (z. B. nach einem "
      + "Server-Neustart) – das ist kein Absturz.", { n: geplant }));
  }
  if (serverNeu) {
    teile.push(tr("🖥 {n}× ist der Server in dieser Zeit neu gestartet.",
      { n: serverNeu }));
  }
  zus.innerHTML = teile.map(esc).join("<br>");

  // Verlauf zeichnen – dieselbe Sprache wie die Preiskurven
  const werte = liste.map((p) => p.heap != null ? p.heap : p.knoten / 100);
  const w = 560, h = 90, padX = 8, padT = 8, padB = 16;
  const hi = Math.max(...werte, 1), lo = Math.min(...werte, 0);
  const x = (i) => padX + (i / Math.max(1, werte.length - 1)) * (w - 2 * padX);
  const y = (v) => padT + (1 - (v - lo) / Math.max(0.001, hi - lo)) * (h - padT - padB);
  const linie = werte.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const marken = liste.map((p, i) => p.g === "start" && i
    ? `<line x1="${x(i).toFixed(1)}" y1="${padT}" x2="${x(i).toFixed(1)}"`
      + ` y2="${h - padB}" class="hist-grid"/>` : "").join("");
  chart.innerHTML = `
  <svg viewBox="0 0 ${w} ${h}" class="diag-svg" role="img"
       aria-label="${esc(tr("Speicher-Verlauf"))}">
    ${marken}
    <polyline points="${linie}" fill="none" stroke="var(--chart-new)"
              stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    <text x="${padX}" y="${padT + 8}" class="hist-label">${esc(String(Math.round(hi)))}</text>
    <text x="${padX}" y="${h - padB - 2}" class="hist-label">${esc(String(Math.round(lo)))}</text>
  </svg>
  <div class="price-note">${esc(tr("Senkrechte Linien: hier begann eine neue "
    + "Sitzung. Steht darüber kein Grund, kam sie ohne Zutun – dann ist der "
    + "Tab abgestürzt."))}</div>`;
}

/* ------------------------------------------- Benachrichtigung aufs Gerät

   Web-Push von der eigenen Instanz. Zustellen muss der Push-Dienst des
   Browser-Herstellers – anders geht es nicht –, deshalb steht in der Meldung
   nur, *dass* etwas passiert ist. Der Weg führt ausdrücklich **nicht** über
   den Tausch-Hub: Fehler sind Sache dieser Instanz. */

/* base64url → Bytes, wie `applicationServerKey` es verlangt. */
function b64Bytes(b64) {
  const voll = (b64 + "=".repeat((4 - b64.length % 4) % 4))
    .replace(/-/g, "+").replace(/_/g, "/");
  const roh = atob(voll);
  return Uint8Array.from(roh, (c) => c.charCodeAt(0));
}

let pushState = null;

async function eigenesAbo() {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return null;
  const reg = await navigator.serviceWorker.ready;
  return reg.pushManager.getSubscription();
}

async function loadPushCard() {
  const box = $("push-box");
  if (!box) return;
  // Ohne HTTPS gibt es keine Push-Berechtigung – dann die Karte gar nicht
  // erst zeigen, statt einen Knopf anzubieten, der nur scheitern kann.
  const geht = window.isSecureContext && "serviceWorker" in navigator
    && "PushManager" in window && "Notification" in window;
  try {
    pushState = await api("/push");
  } catch (_) { pushState = null; }
  box.hidden = !(geht && pushState && pushState.available);
  if (box.hidden) return;
  const abo = await eigenesAbo();
  const an = !!abo;
  $("push-state").textContent = an
    ? tr("Auf diesem Gerät eingeschaltet · {n} Gerät(e) insgesamt",
      { n: pushState.devices.length })
    : (Notification.permission === "denied"
      ? tr("Der Browser hat Benachrichtigungen für diese Seite blockiert – "
        + "das lässt sich nur in seinen Einstellungen zurücknehmen.")
      : tr("Auf diesem Gerät aus."));
  $("btn-push-on").hidden = an || Notification.permission === "denied";
  $("btn-push-off").hidden = !an;
  $("btn-push-test").hidden = !pushState.devices.length;
}

async function pushEinschalten() {
  const out = $("push-out");
  out.hidden = false;
  out.textContent = tr("Wird eingerichtet …");
  try {
    const erlaubt = await Notification.requestPermission();
    if (erlaubt !== "granted") {
      out.textContent = tr("Ohne Erlaubnis des Browsers geht es nicht.");
      loadPushCard();
      return;
    }
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: b64Bytes(pushState.key),
    });
    await api("/push/subscribe", { method: "POST",
      body: { subscription: sub.toJSON() } });
    out.textContent = tr("Eingeschaltet ✔");
  } catch (e) {
    out.textContent = e.message;
  }
  loadPushCard();
}

async function pushAusschalten() {
  const out = $("push-out");
  out.hidden = false;
  try {
    const abo = await eigenesAbo();
    if (abo) {
      // Erst beim Server abmelden, dann im Browser: Andersherum wäre die
      // Adresse weg, bevor der Server sie löschen konnte – der Eintrag
      // bliebe als Leiche stehen.
      await api("/push/unsubscribe", { method: "POST",
        body: { endpoint: abo.endpoint } });
      await abo.unsubscribe();
    }
    out.textContent = tr("Ausgeschaltet.");
  } catch (e) { out.textContent = e.message; }
  loadPushCard();
}

/* Liegt ein Token, hat das Eingabefeld nichts mehr zu suchen: Es stünde
   leer da und lüde dazu ein, versehentlich zu überschreiben. Stattdessen der
   maskierte Stand und die beiden Wege weiter – ersetzen oder entfernen. */
let githubFeldOffen = false;

function zeigeGithubToken(maskiert) {
  const stand = $("github-token-state");
  if (!stand) return;
  const hat = !!maskiert;
  const feldZeigen = !hat || githubFeldOffen;
  stand.textContent = hat
    ? tr("Gespeichert: {wert}", { wert: maskiert })
    : tr("Kein Token hinterlegt – die App kann keine Issues anlegen.");
  $("github-token-input").hidden = !feldZeigen;
  $("btn-github-token").hidden = !feldZeigen;
  $("btn-github-replace").hidden = !hat || githubFeldOffen;
  $("btn-github-del").hidden = !hat;
  // Ohne Token gibt es nichts zu prüfen.
  $("btn-github-test").hidden = !hat;
}

/* ------------------------------------------------------- Benachrichtigungen */
/* Hinweise auf dem Startbildschirm, die stehen bleiben, bis sie jemand
   wegklickt – etwa wenn BrickLink eine Nummer der Sammlung ändert. */

async function loadNotifications() {
  try {
    const data = await api("/notifications");
    renderNotifications(data.items || []);
  } catch (_) { /* Hinweise dürfen den Start nie blockieren */ }
}

function renderNotifications(items) {
  const box = $("notifications");
  if (!box) return;
  box.innerHTML = "";
  items.forEach((n) => {
    const card = document.createElement("div");
    card.className = "notice-card";
    card.innerHTML = `
      <button class="notice-close" data-close="${n.id}"
              title="Hinweis entfernen" aria-label="Hinweis entfernen">✕</button>
      <div class="notice-title">🔔 ${esc(n.title)}</div>
      ${n.body ? `<p class="notice-body">${esc(n.body)}</p>` : ""}
      ${n.kind === "error"
        ? `<button class="btn btn-primary" data-goto-errors>Fehlerbericht öffnen</button>`
        : n.kind === "dublette" ? `
          <p class="notice-body">${esc(tr("Zusammenführen?"))}</p>
          <div class="notice-wahl">
            <button class="btn btn-primary" data-merge="${n.id}" data-modus="ersetzen">
              ${esc(tr("Ein Exemplar"))}</button>
            <button class="btn" data-merge="${n.id}" data-modus="zusammen">
              ${esc(tr("Zwei Exemplare"))}</button>
          </div>
          <p class="notice-hint">${esc(tr("„Ein Exemplar\u201c heißt: derselbe "
            + "Kasten, zweimal erfasst. „Zwei Exemplare\u201c addiert die "
            + "Stückzahlen."))}</p>`
        : n.new_item_id ? `<button class="btn btn-primary notice-apply"
          data-apply="${n.id}">Nummer übernehmen</button>` : ""}`;
    box.appendChild(card);
  });

  box.querySelectorAll("[data-merge]").forEach((b) => {
    b.addEventListener("click", async () => {
      box.querySelectorAll("[data-merge]").forEach((x) => { x.disabled = true; });
      try {
        const r = await api(`/notifications/${b.dataset.merge}/merge`,
          { method: "POST", body: { modus: b.dataset.modus } });
        toast(r.modus === "zusammen"
          ? tr("Zusammengeführt – Stückzahlen addiert ✔")
          : tr("Zusammengeführt ✔"));
        loadNotifications();
        loadCollection();
      } catch (e) {
        toast(e.message);
        box.querySelectorAll("[data-merge]").forEach((x) => { x.disabled = false; });
      }
    });
  });

  // Direkt zur Stelle springen, statt den Weg zu beschreiben.
  box.querySelectorAll("[data-goto-errors]").forEach((b) => {
    b.addEventListener("click", async () => {
      showTab("settings");
      await new Promise((r) => setTimeout(r, 300));
      const karte = $("errors-card");
      if (!karte) return;
      karte.classList.remove("collapsed");
      karte.scrollIntoView({ block: "center", behavior: "smooth" });
    });
  });

  box.querySelectorAll("[data-close]").forEach((b) => {
    b.onclick = async () => {
      await api(`/notifications/${b.dataset.close}`, { method: "DELETE" });
      loadNotifications();
    };
  });
  box.querySelectorAll("[data-apply]").forEach((b) => {
    b.onclick = async () => {
      b.disabled = true;
      b.textContent = tr("Wird übernommen …");
      try {
        const res = await api(`/notifications/${b.dataset.apply}/apply`,
          { method: "POST" });
        toast(tr("Neue Nummer {id} übernommen", { id: res.new_item_id }));
        loadNotifications();
        loadCollection();
      } catch (e) {
        toast(e.message || "Hat nicht geklappt");
        b.disabled = false;
        b.textContent = tr("Nummer übernehmen");
      }
    };
  });
}

/* ---------------------------------------------------------------- Preisgebiet */
let priceRegionState = null;

function renderPriceRegion() {
  const s = priceRegionState;
  if (!s) return;
  const status = $("price-region-status");
  const run = $("price-region-run");
  if (!s.can_fetch) {
    status.textContent = tr("Für Preise wird ein BrickLink-Schlüssel "
      + "benötigt (Mehr → API-Schlüssel).");
    run.hidden = true;
    return;
  }
  if (s.pending > 0) {
    status.innerHTML = "⚠️ <b>" + esc(tr("{n} Artikel", { n: s.pending }))
      + "</b> " + esc(tr("haben noch Preise aus einem anderen Gebiet. Das "
        + "Umrechnen holt je Artikel zwei Preise von BrickLink – bei vielen "
        + "Artikeln also in mehreren Durchgängen."));
    run.hidden = false;
  } else {
    status.textContent = tr("✅ Alle Preise stammen aus dem eingestellten Gebiet.");
    run.hidden = true;
  }

  // Getrennt davon: Artikel, die (noch) gar keinen Preis haben.
  const mStatus = $("price-missing-status");
  const mRun = $("price-missing-run");
  if (s.missing > 0) {
    mStatus.hidden = false;
    mStatus.innerHTML = "⚠️ <b>" + esc(s.missing === 1 ? tr("1 Artikel")
      : tr("{n} Artikel", { n: s.missing })) + "</b> "
      + esc(tr("hat/haben noch keinen Preis – oft, weil im gewählten Gebiet "
        + "nichts verkauft wurde. Ein erneuter Abruf weitet auf Europa und "
        + "weltweit aus."));
    mRun.hidden = false;
  } else {
    mStatus.hidden = true;
    mRun.hidden = true;
  }
}

/* Auswahlliste füllen. Die Namen der Gebiete und Währungen kommen vom
   Server auf Deutsch – also durch denselben Katalog wie alles andere. */
function fuelleAuswahl(sel, optionen, gewaehlt) {
  sel.innerHTML = optionen.map((o) =>
    `<option value="${esc(o.value)}"${o.value === gewaehlt ? " selected" : ""}>`
    + `${esc(tr(o.label))}</option>`).join("");
}

async function loadPriceRegion() {
  try {
    const s = await api("/settings/price_region");
    priceRegionState = s;
    fuelleAuswahl($("price-region"), s.options, s.region);
    fuelleAuswahl($("price-currency"), s.currencies, s.currency);
    setCurrency(s.currency);
    renderPriceRegion();
  } catch (e) { /* Karte bleibt leer */ }
}

async function savePriceRegion(region, waehrung) {
  const sel = $("price-region");
  const wsel = $("price-currency");
  sel.disabled = wsel.disabled = true;
  try {
    const body = { region };
    if (waehrung) body.currency = waehrung;
    const res = await api("/settings/price_region", { method: "POST", body });
    priceRegionState.region = res.region;
    priceRegionState.currency = res.currency;
    priceRegionState.pending = res.pending;
    sel.value = res.region;          // Anzeige an den Server angleichen
    wsel.value = res.currency;
    setCurrency(res.currency);
    renderPriceRegion();
    toast(res.pending > 0
      ? tr("Gespeichert – {n} Artikel neu zu berechnen", { n: res.pending })
      : tr("Gespeichert ✔"));
    if (!$("view-collection").hidden) loadCollection();
  } catch (e) {
    toast(e.message);
    loadPriceRegion();               // Auswahl zurück auf den echten Stand
  } finally {
    sel.disabled = wsel.disabled = false;
  }
}

/* ------------------------------------------------- Bilder auf der Instanz */

async function loadImagesStatus() {
  const status = $("images-status");
  const btn = $("btn-images-fetch");
  if (!status) return;
  try {
    const s = await api("/images/status");
    const da = s.total - s.pending;
    status.textContent = s.pending > 0
      ? tr("{n} von {max} Bildern liegen hier – {rest} fehlen noch.",
        { n: da, max: s.total, rest: s.pending })
      : (s.total > 0
        ? tr("Alle {n} Bilder liegen auf der Instanz ✔", { n: s.total })
        : tr("Noch keine Artikel mit Bild."));
    btn.hidden = s.pending === 0;
  } catch (_) { status.textContent = ""; btn.hidden = true; }
}

/* Holt in Häppchen und zeigt den Fortschritt – jedes Bild ist ein Abruf beim
   CDN, alles auf einmal wäre bei einer großen Sammlung unhöflich. */
async function fetchImages() {
  const btn = $("btn-images-fetch");
  btn.disabled = true;
  let total = 0;
  try {
    for (let runde = 0; runde < 200; runde += 1) {
      const res = await api("/images/fetch?limit=25", { method: "POST" });
      total += res.fetched;
      btn.textContent = tr("🖼 {n} geholt, {rest} offen …",
        { n: total, rest: res.remaining });
      // Nichts mehr offen – oder eine ganze Runde ohne einen einzigen
      // Treffer: Dann helfen weitere Versuche auch nicht.
      if (!res.remaining || !res.fetched) break;
    }
    toast(total ? tr("{n} Bilder geholt ✔", { n: total })
      : tr("Nichts zu tun"));
  } catch (e) {
    toast(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = tr("🖼 Bilder jetzt holen");
    loadImagesStatus();
    if (!$("view-collection").hidden) loadCollection();
  }
}

/* Rechnet in Häppchen um und zeigt den Fortschritt. */
async function recalcPrices() {
  const btn = $("btn-price-recalc");
  btn.disabled = true;
  let total = 0;
  try {
    for (let round = 0; round < 40; round += 1) {
      const res = await api("/prices/refresh_region?limit=20",
        { method: "POST" });
      total += res.updated;
      priceRegionState.pending = res.remaining;
      btn.textContent = tr("🔄 {n} umgerechnet, {rest} offen …",
        { n: total, rest: res.remaining });
      if (res.failed && res.failed.length) {
        toast(tr("{n} übersprungen: {grund}",
      { n: res.failed.length, grund: res.failed[0].error }));
      }
      if (!res.remaining || !res.updated) break;
    }
    toast(total ? tr("{n} Artikel umgerechnet ✔", { n: total })
      : tr("Nichts zu tun"));
  } catch (e) {
    toast(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = tr("🔄 Preise jetzt umrechnen");
    renderPriceRegion();
    if (!$("view-collection").hidden) loadCollection();
  }
}

/* Ruft preislose Artikel erneut ab – jetzt mit Rückfall Europa → weltweit. */
async function fillMissingPrices() {
  const btn = $("btn-price-fill");
  btn.disabled = true;
  let total = 0, filled = 0;
  try {
    for (let round = 0; round < 40; round += 1) {
      const res = await api("/prices/refresh_missing?limit=20",
        { method: "POST" });
      total += res.updated;
      filled += res.filled;
      priceRegionState.missing = res.remaining;
      btn.textContent = `🔄 ${filled} gefunden, ${res.remaining} offen …`;
      if (res.failed && res.failed.length) {
        toast(tr("{n} übersprungen: {grund}",
      { n: res.failed.length, grund: res.failed[0].error }));
      }
      if (!res.remaining || !res.updated) break;
    }
    toast(total
      ? tr("{n} von {max} geprüften Artikeln haben jetzt einen Preis",
        { n: filled, max: total })
      : "Nichts zu tun");
  } catch (e) {
    toast(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = tr("🔄 Preislose erneut abrufen");
    loadPriceRegion();     // echten Reststand zeigen (nirgends verkauft bleibt)
    if (!$("view-collection").hidden) loadCollection();
  }
}

/* ---------------------------------------------------------------- Einstellungen */
function initCollapsibleCards() {
  document.querySelectorAll("#view-settings .settings-card > h3")
    .forEach((h3) => {
      const card = h3.parentElement;
      const key = "bf_card_" + h3.textContent.replace(/\W+/g, "");
      const stored = localStorage.getItem(key);
      if (stored === "open") card.classList.remove("collapsed");
      else card.classList.add("collapsed");
      h3.addEventListener("click", () => {
        card.classList.toggle("collapsed");
        localStorage.setItem(key,
          card.classList.contains("collapsed") ? "closed" : "open");
      });
    });
}

async function loadPriceLog(limit) {
  const box = $("pricelog-list");
  if (!box) return;
  box.innerHTML = brickLoading("Protokoll wird geladen …");
  try {
    const res = await api(`/price_log?limit=${limit}`);
    const staleEl = $("pricelog-stale");
    if (staleEl) {
      const days = res.stale_days || 7;
      const n = res.stale_count || 0;
      staleEl.textContent = n > 0
        ? (n === 1
          ? tr("🕒 Bei einem Artikel ist der Preisabruf älter als {d} Tage – "
            + "der Hintergrundjob frischt ihn auf.", { d: days })
          : tr("🕒 Bei {n} Artikeln ist der Preisabruf älter als {d} Tage – "
            + "der Hintergrundjob frischt sie nach und nach auf.",
            { n, d: days }))
        : tr("✔ Alle Sammlungs-Preise sind jünger als {d} Tage.", { d: days });
      staleEl.hidden = false;
    }
    if (!res.entries.length) {
      box.textContent = tr("Noch keine Aufzeichnungen.");
      $("btn-pricelog-more").hidden = true;
      return;
    }
    box.innerHTML = res.entries.map((e) => {
      const d = new Date(e.ts * 1000);
      const when = d.toLocaleDateString(dateLocale(),
        { day: "2-digit", month: "2-digit" }) + " "
        + d.toLocaleTimeString(dateLocale(),
          { hour: "2-digit", minute: "2-digit" });
      const prices = [
        e.price_new != null ? tr("neu") + " " + fmtEur(e.price_new) : null,
        e.price_used != null ? tr("gebr.") + " " + fmtEur(e.price_used) : null,
      ].filter(Boolean).join(" · ");
      const src = e.source === "manuell"
        ? `<span class="pl-src manual">${esc(tr("manuell"))}</span>`
        : e.source === "auto"
          ? `<span class="pl-src">auto</span>` : "";
      return `<div class="pl-row">
        <span class="pl-when">${when}</span>
        <span class="pl-name">${esc(e.name)}</span>
        <span class="pl-prices">${prices || "–"}</span>${src}
      </div>`;
    }).join("");
    $("btn-pricelog-more").hidden = limit >= 200
      || res.entries.length < limit;
  } catch (e) {
    box.textContent = e.message;
  }
}

/* ------------------------------------------------- Update-Ankündigung
   Der Server ist während des Updates weg – die Sperre muss deshalb hier im
   Browser laufen. Wir fragen kurz nach, zeigen Countdown bzw. Sperre und
   laden neu, sobald der Server wieder da ist. */
const UPDATE_POLL_MS = 20000;     // normale Nachfrage
const UPDATE_WAIT_MS = 5000;      // während der Sperre häufiger
const UPDATE_GIVEUP_MS = 8 * 60 * 1000;
let updateTimer = null;
let updateLockedSince = 0;
let serverStartedKnown = null;   // Startzeit des Servers, von dem diese Seite stammt

function fmtCountdown(sec) {
  const m = Math.floor(sec / 60);
  return m > 0 ? `${m}:${String(sec % 60).padStart(2, "0")} Minuten`
               : `${sec} Sekunden`;
}

/* Balken ein-/ausblenden und den Inhalt entsprechend nach unten rücken */
function showUpdateBar(on, text) {
  const bar = $("update-bar");
  if (!bar) return;
  if (on) $("update-bar-text").textContent = text;
  bar.hidden = !on;
  document.body.classList.toggle("update-pending", on);
  if (on) {
    // Erst im nächsten Frame messen – vorher steht die Höhe (Umbruch!)
    // noch nicht fest und der Inhalt würde zu wenig verschoben.
    requestAnimationFrame(() => {
      document.documentElement.style.setProperty(
        "--update-bar-h", bar.offsetHeight + "px");
    });
  }
}

function showUpdateLock(on) {
  const lock = $("update-lock");
  if (!lock) return;
  if (on && lock.hidden) updateLockedSince = Date.now();
  lock.hidden = !on;
  document.body.style.overflow = on ? "hidden" : "";
}

async function pollUpdateStatus() {
  const bar = $("update-bar");
  const lock = $("update-lock");
  if (!bar || !lock) return;
  let next = UPDATE_POLL_MS;
  try {
    const s = await api("/update/status");
    state.appVersion = s.version;
    state.serverStartedAt = s.started_at;

    // Hat der Server seit dem Laden dieser Seite neu gestartet? Dann ist der
    // Programmcode im Browser veraltet – unabhängig davon, ob die Sperre
    // sichtbar war. Wichtig für Tabs, die während des Updates im Hintergrund
    // lagen: dort stehen die Timer still, die Sperre erscheint gar nicht.
    if (s.started_at) {
      if (serverStartedKnown === null) {
        serverStartedKnown = s.started_at;
      } else if (s.started_at !== serverStartedKnown) {
        neuLadenMit("Server neu gestartet");
        return;
      }
    }

    const helperBefore = state.helperActive;
    state.helperActive = !!s.helper_active;
    state.helperSeenAt = s.helper_seen_at || null;
    // Helfer erst später eingerichtet? Dann Karte nachziehen.
    if (helperBefore !== state.helperActive && !$("update-card").hidden) {
      checkForUpdate(false).then(renderUpdateInfo);
    }
    if (!s.pending) {
      showUpdateBar(false);
      // Die Sperre bleibt bewusst stehen: Der Helfer löscht die Markierung,
      // BEVOR er das Update ausführt – der Server geht also erst danach weg.
      // Aufgehoben wird sie durch das Neuladen nach dem Neustart (siehe oben)
      // oder nach Zeitablauf durch den Hinweis samt Knopf.
    } else if (s.seconds_left > 0) {
      showUpdateBar(true, tr("⬆️ Update in {zeit}",
        { zeit: fmtCountdown(s.seconds_left) })
        + " – bitte Eingaben abschließen");
      $("btn-update-abort").hidden = !(state.user && state.user.is_admin);
      next = s.seconds_left <= 30 ? 3000 : UPDATE_POLL_MS;
    } else {
      showUpdateBar(false);
      showUpdateLock(true);
      next = UPDATE_WAIT_MS;
    }
  } catch (_) {
    // Server nicht erreichbar: läuft das Update gerade, ist das erwartet.
    if (!lock.hidden) next = UPDATE_WAIT_MS;
  }
  if (!lock.hidden) {
    const waited = Date.now() - updateLockedSince;
    if (waited > UPDATE_GIVEUP_MS) {
      $("update-lock-text").textContent =
        "Das dauert länger als erwartet. Läuft der Update-Helfer auf dem "
        + "Server? Du kannst es auch von Hand prüfen.";
      $("btn-update-reload").hidden = false;
    }
    next = UPDATE_WAIT_MS;
  }
  clearTimeout(updateTimer);
  updateTimer = setTimeout(pollUpdateStatus, next);
}

function startUpdateWatch() {
  clearTimeout(updateTimer);
  pollUpdateStatus();
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) pollUpdateStatus();     // beim Zurückkommen sofort
  });
}

async function checkForUpdate(force) {
  if (!(state.user && state.user.is_admin)) return null;
  try {
    return await api("/update_check" + (force ? "?force=1" : ""));
  } catch (_) {
    return null;
  }
}

function renderUpdateInfo(info) {
  if (!info) return;
  $("ver-current").textContent = "v" + info.current;
  const hasUpdate = info.update_available;
  $("update-hint").hidden = !hasUpdate;
  $("ver-latest-ok").hidden = hasUpdate || !info.latest;
  if (hasUpdate) {
    $("ver-latest").textContent = "v" + info.latest;
    $("ver-url").href = info.url || "https://github.com/Melle79/brickfolio/releases";
  }
  // Direkt einspielen nur anbieten, wenn der Helfer auf dem Server läuft –
  // sonst würde die App auf ein Update warten, das nie kommt.
  const admin = !!(state.user && state.user.is_admin);
  const helper = !!state.helperActive;
  const run = $("update-run");
  if (run) run.hidden = !(admin && helper);
  // Status des Update-Helfers – auch ohne anstehendes Update sichtbar,
  // damit sich die Einrichtung jederzeit prüfen lässt.
  const hint = $("update-helper-hint");
  const diag = $("update-helper-diag");
  if (hint) hint.hidden = !admin;
  if (diag && admin) {
    const seen = state.helperSeenAt;
    const anleitung = tr("Einrichtung (eine Aufgabe je Instanz, die jede "
      + "Minute läuft) steht im <a href=\"https://github.com/Melle79/brickfolio"
      + "#update-aus-der-app-heraus-optional\" target=\"_blank\""
      + " rel=\"noopener\">README</a>.");
    if (helper) {
      diag.innerHTML = tr("✅ <b>Update-Helfer läuft.</b> Sobald eine neue "
        + "Version bereitsteht, kannst du sie hier direkt einspielen – ohne "
        + "SSH.");
    } else if (!seen) {
      diag.innerHTML = tr("💡 <b>Optional:</b> Mit dem Helfer "
        + "<code>update-watch.sh</code> auf dem Server lässt sich ein Update "
        + "direkt hier auslösen – ohne SSH. ") + anleitung
        + tr("<br><b>Stand:</b> Die Aufgabe hat sich hier noch <b>nie</b> "
          + "gemeldet – meist stimmt der Pfad im Skriptfeld nicht oder sie "
          + "läuft nicht als <code>root</code>.");
    } else {
      const min = Math.floor((Date.now() / 1000 - seen) / 60);
      const wann = min < 120 ? tr("vor {n} Minuten", { n: min })
        : tr("vor {n} Stunden", { n: Math.floor(min / 60) });
      diag.innerHTML = tr("⚠️ <b>Update-Helfer meldet sich nicht.</b> Die "
        + "Aufgabe lief zuletzt <b>{wann}</b> – sie ist also eingerichtet, "
        + "läuft aber nicht jede Minute. Häufigster Grund: „Letzte "
        + "Ausführungszeit“ steht auf <code>00:59</code> statt "
        + "<code>23:59</code>.", { wann });
    }
  }
  const status = $("update-status");
  if (info.error) {
    status.textContent = info.error;
    status.hidden = false;
  } else {
    status.hidden = true;
  }
}

/* Eine Gruppe, deren Karten alle ausgeblendet sind, hat nichts zu sagen –
   dann verschwindet auch ihre Überschrift. Sonst stünde bei einem normalen
   Benutzer dreimal eine leere Zwischenzeile. */
function gruppenAufraeumen() {
  document.querySelectorAll(".settings-group").forEach((g) => {
    const sichtbar = [...g.querySelectorAll(".settings-card")]
      .some((c) => !c.hidden);
    g.hidden = !sichtbar;
  });
}

async function loadSettings() {
  const dealerUi = state.user && state.user.is_dealer;
  if ($("dealer-card")) {
    $("dealer-card").hidden = !dealerUi;
    if (dealerUi) $("offer-percent").value = state.offerPercent || 60;
  }
  if ($("pricelog-card")) {
    $("pricelog-card").hidden = !dealerUi;
    if (dealerUi) loadPriceLog(50);
  }
  $("settings-user").textContent = state.user ? state.user.username : "";
  $("own-name").value = state.user ? state.user.username : "";
  const isAdmin = !!(state.user && state.user.is_admin);
  $("api-panel").hidden = !isAdmin;
  $("name-card").hidden = !isAdmin;
  document.querySelectorAll(".theme-default-star").forEach((s) => {
    s.hidden = !isAdmin;
  });
  $("default-theme-hint").hidden = !isAdmin;
  if (isAdmin) markDefaultTheme();
  if (isAdmin && $("owner-name")) {
    $("owner-name").value =
      (state.ownerName && state.ownerName !== "Finn") ? state.ownerName : "";
    $("owner-name").placeholder = "Finn";
  }
  $("backup-card").hidden = !isAdmin;
  if (isAdmin) {
    api("/backup_info").then((b) => {
      if (!b || b.keep <= 0) return;
      const el = $("backup-auto-info");
      el.textContent = b.latest
        ? tr("Automatische Sicherung: täglich nach data/backups/ · {n} von "
          + "{max} Tagesständen", { n: b.count, max: b.keep })
        : tr("Automatische Sicherung: täglich nach data/backups/ (die erste "
          + "entsteht kurz nach dem Start).");
      const block = $("backup-restore-block");
      if (b.files && b.files.length) {
        block.hidden = false;
        $("backup-select").innerHTML = b.files.map((f) => {
          const time = f.mtime
            ? " · " + new Date(f.mtime * 1000).toLocaleTimeString(dateLocale(),
                { hour: "2-digit", minute: "2-digit" }) + " Uhr"
            : "";
          const label = f.name.replace("brickfolio-", "").replace(".db", "")
            + time + ` (${(f.size / 1024).toFixed(0)} KB)`;
          return `<option value="${esc(f.name)}">${esc(label)}</option>`;
        }).join("");
      }
    }).catch(() => {});
  }
  $("errors-card").hidden = !isAdmin;
  if (isAdmin) loadErrors();
  $("price-region-card").hidden = !isAdmin;
  if (isAdmin) loadPriceRegion();
  $("images-card").hidden = !isAdmin;
  if (isAdmin) loadImagesStatus();
  $("external-access-card").hidden = !isAdmin;
  loadSortCard();               // Sortierung darf jeder für sich einstellen
  $("hub-card").hidden = !isAdmin;
  if (isAdmin) loadHubCard();
  $("update-card").hidden = !isAdmin;
  if (isAdmin) checkForUpdate(false).then(renderUpdateInfo);
  const panel = $("admin-panel");
  panel.hidden = !isAdmin;
  gruppenAufraeumen();
  if (!isAdmin) return;
  loadApiKeys();
  try {
    const users = await api("/users");
    $("user-list").innerHTML = users.map((u) => `
      <li>${esc(u.username)}${u.is_admin ? " 👑" : ""}
        <span class="user-actions">
          <button class="pw ${u.is_admin ? "dealer-on" : ""}" data-admin-user="${u.id}" data-admin-state="${u.is_admin ? 1 : 0}" title="Admin-Rechte">${u.is_admin ? "Admin ✔" : "Admin"}</button>
          <button class="pw ${u.is_dealer ? "dealer-on" : ""}" data-dealer-user="${u.id}" data-dealer-state="${u.is_dealer ? 1 : 0}" title="Sammlerprofi-Modus">${u.is_dealer ? "Profi ✔" : "Profi"}</button>
          <button class="pw" data-pass-user="${u.id}" data-pass-name="${esc(u.username)}">Passwort</button>
          ${u.username !== state.user.username
            ? `<button class="del" data-del-user="${u.id}">Entfernen</button>` : ""}
        </span>
      </li>`).join("");
    $("user-list").querySelectorAll("[data-admin-user]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const makeAdmin = btn.dataset.adminState !== "1";
        if (!makeAdmin && !confirm(tr("Admin-Rechte wirklich entziehen?"))) return;
        try {
          await api(`/users/${btn.dataset.adminUser}/admin`,
            { method: "POST", body: { is_admin: makeAdmin } });
          toast(makeAdmin ? "Zum Admin gemacht ✔" : "Admin-Rechte entzogen");
          refreshMe().then(loadSettings);
        } catch (e) { toast(e.message); }
      });
    });
    $("user-list").querySelectorAll("[data-dealer-user]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const makeDealer = btn.dataset.dealerState !== "1";
        try {
          await api(`/users/${btn.dataset.dealerUser}/dealer`,
            { method: "POST", body: { is_dealer: makeDealer } });
          toast(makeDealer ? "Sammlerprofi aktiviert ✔"
                           : "Sammlerprofi deaktiviert");
          refreshMe().then(loadSettings);
        } catch (e) { toast(e.message); }
      });
    });
    $("user-list").querySelectorAll("[data-pass-user]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const d = await appDialog({
          titel: tr("Passwort setzen"),
          text: tr("Neues Passwort für {name} (mind. 8 Zeichen):",
                   { name: btn.dataset.passName }),
          felder: [{ name: "pw", label: tr("Neues Passwort"),
                     typ: "password", pflicht: true, max: 200 }],
          ok: tr("Setzen"),
        });
        if (!d) return;
        const pw = d.pw;
        if (pw.length < 8) { toast(tr("Bitte mindestens 8 Zeichen")); return; }
        try {
          await api(`/users/${btn.dataset.passUser}/password`,
            { method: "POST", body: { password: pw } });
          toast(tr("Passwort für {name} gesetzt ✔", { name: btn.dataset.passName }));
        } catch (e) { toast(e.message); }
      });
    });
    $("user-list").querySelectorAll("[data-del-user]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm(tr("Benutzer wirklich entfernen?"))) return;
        try { await api("/users/" + btn.dataset.delUser, { method: "DELETE" }); loadSettings(); }
        catch (e) { toast(e.message); }
      });
    });
  } catch (e) { toast(e.message); }
}

async function addUser() {
  const err = $("user-error");
  err.hidden = true;
  try {
    await api("/users", { method: "POST", body: {
      username: $("new-user").value.trim(), password: $("new-pass").value,
    }});
    $("new-user").value = ""; $("new-pass").value = "";
    toast("Benutzer angelegt ✔");
    loadSettings();
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  }
}

/* ---------------------------------------------------------------- Start */
document.addEventListener("DOMContentLoaded", async () => {
  // Sprache zuerst: Danach steht das Dokument fertig übersetzt da, ohne dass
  // deutscher Text kurz aufblitzt. Bei Deutsch kostet das nichts.
  await loadLang();
  translateTree(document.body);
  watchForTranslation();

  $("btn-login").addEventListener("click", doLogin);
  $("btn-totp").addEventListener("click", doTotpLogin);
  $("btn-totp-cancel").addEventListener("click", abbrechenTotp);
  $("totp-code").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") { ev.preventDefault(); doTotpLogin(); }
  });
  $("topbar-unread").addEventListener("click", () => {
    showTab("hub");
    showHubTab("trades");
  });

  $("btn-help").addEventListener("click", () => {
    $("help-overlay").hidden = false;
    document.body.style.overflow = "hidden";
  });
  const closeHelp = () => {
    $("help-overlay").hidden = true;
    document.body.style.overflow = "";
  };
  initCollapsibleCards();
  initLangPicker();
  initThemePicker();
  initExternalAccess();
  const ownerBtn = $("btn-owner-name");
  if (ownerBtn) {
    ownerBtn.addEventListener("click", async () => {
      try {
        const res = await api("/settings/owner_name", { method: "POST",
          body: { name: $("owner-name").value.trim() } });
        state.ownerName = res.owner_name;
        applyOwnerName(res.owner_name);
        toast("Anzeigename gespeichert ✔");
      } catch (e) { toast(e.message); }
    });
  }
  $("btn-help-close").addEventListener("click", closeHelp);
  $("help-overlay").addEventListener("click", (ev) => {
    if (ev.target === $("help-overlay")) closeHelp();
  });
  const closeProfile = () => {
    $("profile-overlay").hidden = true;
    document.body.style.overflow = "";
  };
  $("whoami").addEventListener("click", () => {
    if (!state.user) return;
    $("settings-user").textContent = state.user.username;
    $("own-name").value = state.user.username;
    $("own-name-error").hidden = true;
    $("own-pass-error").hidden = true;
    $("own-pass-current").value = "";
    $("own-pass-new").value = "";
    $("profile-overlay").hidden = false;
    document.body.style.overflow = "hidden";
    wireTfaOnce();
    ladeTfaStatus();
  });
  $("btn-profile-close").addEventListener("click", closeProfile);
  $("profile-overlay").addEventListener("click", (ev) => {
    if (ev.target === $("profile-overlay")) closeProfile();
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && !$("help-overlay").hidden) closeHelp();
    if (ev.key === "Escape" && !$("profile-overlay").hidden) closeProfile();
  });
  $("btn-setup").addEventListener("click", doSetup);
  $("setup-pass2").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") doSetup();
  });
  $("login-pass").addEventListener("keydown", (e) => { if (e.key === "Enter") doLogin(); });
  $("btn-logout").addEventListener("click", logout);
  $("btn-add-user").addEventListener("click", addUser);
  $("btn-own-pass").addEventListener("click", changeOwnPassword);
  $("btn-backup").addEventListener("click", downloadBackup);
  $("btn-new-list").addEventListener("click", async () => {
    const name = $("new-list-name").value.trim();
    if (!name) { toast("Bitte einen Namen eingeben"); return; }
    try {
      await api("/lists", { method: "POST", body: { name } });
      $("new-list-name").value = "";
      toast(tr('Liste "{name}" angelegt 🛒', { name }));
      await updateListsTab();
      showListsTab("shop");
    } catch (e) { toast(e.message); }
  });
  $("btn-duplicates").addEventListener("click", toggleDuplicates);
  $("btn-missing-figs").addEventListener("click", toggleMissingFigs);
  // Beide Felder schicken immer beides mit: Wer nur die Währung ändert,
  // soll das Gebiet nicht zurücksetzen (und umgekehrt).
  $("price-region").addEventListener("change", (ev) =>
    savePriceRegion(ev.currentTarget.value, $("price-currency").value));
  $("price-currency").addEventListener("change", (ev) =>
    savePriceRegion($("price-region").value, ev.currentTarget.value));
  $("btn-price-recalc").addEventListener("click", recalcPrices);
  $("btn-images-fetch").addEventListener("click", fetchImages);
  $("btn-price-fill").addEventListener("click", fillMissingPrices);

  $("btn-errors-copy").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(errorsAsText());
      toast("Bericht kopiert ✔");
    } catch (_) {
      toast("Kopieren nicht möglich – Text bitte von Hand markieren");
    }
  });
  $("btn-errors-clear").addEventListener("click", async () => {
    if (!confirm(tr("Alle aufgezeichneten Fehler löschen?"))) return;
    try {
      await api("/errors", { method: "DELETE" });
      loadErrors();
    } catch (e) { toast(e.message); }
  });
  $("btn-github-token").addEventListener("click", async (ev) => {
    const btn = ev.currentTarget;
    btn.disabled = true;
    try {
      const res = await api("/settings/github_token", { method: "POST",
        body: { token: $("github-token").value } });
      $("github-token").value = "";
      githubFeldOffen = false;
      toast(res.set ? tr("Token gespeichert ✔") : tr("Token entfernt"));
      $("github-test-out").hidden = true;
      loadErrors();
    } catch (e) { toast(e.message); }
    btn.disabled = false;
  });
  $("btn-diag-copy").addEventListener("click", async () => {
    const liste = diagLesen();
    let bekannt = null;
    const zeilen = liste.map((p) => {
      const sprung = p.s && bekannt && p.s !== bekannt;
      if (p.s) bekannt = p.s;
      return [
        new Date(p.t).toLocaleString(dateLocale()),
        p.heap != null ? p.heap + " MB" : "–",
        p.knoten + " Elemente", p.bilder + " Bilder",
        p.v ? "v" + p.v : "", p.d && p.d !== "klassisch" ? p.d : "",
        p.g || "",
        // Nur beim Start belegt: Woher kam er?
        p.disc ? "vom Browser weggeräumt" : "", p.p ? "geplant: " + p.p : "",
        p.g === "start" && !p.p && !p.disc
          ? (p.sauber ? "ordentlich beendet" : "OHNE ABSCHIED") : "",
        p.nav && p.g === "start" ? "nav=" + p.nav : "",
        // Server-Neustart dort, wo seine Startzeit springt
        sprung ? "SERVER NEU GESTARTET" : "",
      ].filter(Boolean).join("  ·  ");
    });
    const text = "Brickfolio – Speicher-Verlauf\n" + zeilen.join("\n");
    try {
      await navigator.clipboard.writeText(text);
      toast(tr("Verlauf kopiert ✔"));
    } catch (_) {
      toast(tr("Kopieren nicht möglich – Text bitte von Hand markieren"));
    }
  });
  $("btn-diag-clear").addEventListener("click", () => {
    localStorage.removeItem(DIAG_KEY);
    renderDiag();
    toast(tr("Verlauf geleert"));
  });
  $("btn-push-on").addEventListener("click", pushEinschalten);
  $("btn-push-off").addEventListener("click", pushAusschalten);
  $("btn-push-test").addEventListener("click", async () => {
    const out = $("push-out");
    out.hidden = false;
    out.textContent = tr("Wird gesendet …");
    try {
      const res = await api("/push/test", { method: "POST" });
      out.textContent = res.sent
        ? tr("An {n} Gerät(e) geschickt – gleich müsste sie ankommen.",
          { n: res.sent })
        : tr("Kein Gerät erreicht. Ist die Benachrichtigung eingeschaltet?");
    } catch (e) { out.textContent = e.message; }
  });
  $("btn-github-replace").addEventListener("click", () => {
    githubFeldOffen = true;
    zeigeGithubToken(errorsState ? errorsState.token_masked : "");
    $("github-token").focus();
  });
  $("btn-github-del").addEventListener("click", async () => {
    // Rückfrage, weil GitHub einen Token nur einmal zeigt: Wer ihn hier
    // löscht und nicht anderswo notiert hat, muss einen neuen erzeugen.
    if (!confirm(tr("Token entfernen? GitHub zeigt ihn kein zweites Mal – "
      + "zum Wiederherstellen bräuchtest du einen neuen."))) return;
    try {
      await api("/settings/github_token", { method: "POST", body: { token: "" } });
      githubFeldOffen = false;
      $("github-test-out").hidden = true;
      toast(tr("Token entfernt"));
      loadErrors();
    } catch (e) { toast(e.message); }
  });
  $("btn-github-test").addEventListener("click", async (ev) => {
    const btn = ev.currentTarget;
    const out = $("github-test-out");
    btn.disabled = true;
    out.hidden = false;
    out.textContent = tr("Wird geprüft …");
    try {
      const res = await api("/settings/github_token/test", { method: "POST" });
      out.textContent = (res.ok ? "✅ " : "❌ ")
        + tr(res.info, { repo: res.repo, code: res.code });
    } catch (e) { out.textContent = "❌ " + e.message; }
    btn.disabled = false;
  });
  $("btn-csv-sample").addEventListener("click", downloadCsvSample);
  $("btn-pricelog-more").addEventListener("click",
    () => loadPriceLog(200));
  document.querySelectorAll("[data-update-go]").forEach((b) => {
    b.addEventListener("click", async () => {
      const delay = Number(b.dataset.updateGo);
      const wann = delay ? tr("in {n} Minute(n)", { n: delay / 60 })
        : tr("sofort");
      if (!confirm(tr("Update {wann} einspielen?", { wann }) + "\n\n"
        + tr("Die App sperrt sich für alle Benutzer und lädt danach neu."))) return;
      b.disabled = true;
      try {
        await api("/update/request", { method: "POST", body: { delay } });
        toast(delay ? "Update angekündigt ✔" : "Update angefordert ✔");
        pollUpdateStatus();
      } catch (e) {
        toast(e.message);
      } finally {
        b.disabled = false;
      }
    });
  });
  $("btn-update-abort").addEventListener("click", async (ev) => {
    ev.currentTarget.disabled = true;
    try {
      await api("/update/cancel", { method: "POST" });
      toast("Update abgebrochen");
      showUpdateBar(false);
    } catch (e) { toast(e.message); }
    ev.currentTarget.disabled = false;
    pollUpdateStatus();
  });
  $("btn-update-reload").addEventListener("click",
    () => neuLadenMit("Knopf „Neu laden“"));

  $("btn-update-check").addEventListener("click", async (ev) => {
    const btn = ev.currentTarget;
    btn.disabled = true;
    const info = await checkForUpdate(true);
    renderUpdateInfo(info);
    if (info && !info.update_available && !info.error) {
      toast("Brickfolio ist aktuell ✔");
    }
    btn.disabled = false;
  });
  $("btn-offer-percent").addEventListener("click", async () => {
    const pct = Number($("offer-percent").value.trim());
    if (!Number.isInteger(pct) || pct < 1 || pct > 100) {
      toast("Bitte eine ganze Zahl zwischen 1 und 100 eingeben");
      return;
    }
    try {
      await api("/settings/offer_percent", { method: "POST",
        body: { percent: pct } });
      state.offerPercent = pct;
      toast(tr("Vorschlag steht jetzt auf {pct} % ✔", { pct }));
    } catch (e) { toast(e.message); }
  });
  $("btn-csv-import").addEventListener("click", () => $("csv-file").click());
  $("csv-file").addEventListener("change", (ev) => {
    const file = ev.target.files[0];
    ev.target.value = "";
    if (file) importCsvFile(file);
  });
  document.querySelectorAll("[data-listtab]").forEach((b) => {
    b.addEventListener("click", () => showListsTab(b.dataset.listtab));
  });
  $("btn-restore").addEventListener("click", () => $("restore-file").click());
  $("btn-backup-dl").addEventListener("click", async () => {
    const name = $("backup-select").value;
    if (!name) return;
    try {
      const res = await fetch(`/api/backup_file/${encodeURIComponent(name)}`,
        { headers: { Authorization: `Bearer ${state.token}` } });
      if (!res.ok) throw new Error("Download fehlgeschlagen");
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
      toast("Tagesstand heruntergeladen 💾");
    } catch (e) { toast(e.message); }
  });
  $("btn-restore-snap").addEventListener("click", async () => {
    const name = $("backup-select").value;
    if (!name) return;
    const label = name.replace("brickfolio-", "").replace(".db", "");
    if (!confirm(tr("Wirklich den Stand vom {wann} wiederherstellen?",
      { wann: label }) + "\n\n"
      + tr("Alle aktuellen Daten werden durch diesen Tagesstand ersetzt. "
        + "Der jetzige Stand wird vorher automatisch als zusätzliche "
        + "Sicherung weggeschrieben."))) return;
    try {
      const res = await api("/backup_restore_file", { method: "POST",
        body: { name } });
      alert(tr("Stand {wann} wiederhergestellt.", { wann: label }) + "\n"
        + tr("Sicherheitskopie: {name}", { name: res.safety })
        + "\n\n" + tr("Die App lädt jetzt neu."));
      neuLadenMit("Sicherung wiederhergestellt");
    } catch (e) { toast(e.message); }
  });
  $("restore-file").addEventListener("change", (ev) => {
    const file = ev.target.files[0];
    ev.target.value = "";
    if (file) restoreBackupFile(file);
  });
  $("btn-own-name").addEventListener("click", changeOwnUsername);
  $("btn-csv-col").addEventListener("click", () => exportCollectionCsv().catch((e) => toast(e.message)));
  $("btn-csv-want").addEventListener("click", () => exportWantedCsv().catch((e) => toast(e.message)));
  $("btn-print-col").addEventListener("click", () => printCollection().catch((e) => toast(e.message)));
  $("btn-print-want").addEventListener("click", () => printWanted().catch((e) => toast(e.message)));
  $("btn-save-keys").addEventListener("click", saveApiKeys);
  $("btn-test-keys").addEventListener("click", testApiKeys);
  $("btn-camera").addEventListener("click", () => $("file-input").click());
  $("btn-manual-toggle").addEventListener("click", () => {
    const f = $("manual-form");
    f.hidden = !f.hidden;
    if (!f.hidden) { updateManualListBtn(); $("m-name").focus(); }
  });
  $("btn-manual-list").addEventListener("click", pickListForManual);
  $("btn-manual-add").addEventListener("click", addManual);
  $("btn-manual-want").addEventListener("click", addManualWanted);
  $("m-custom").addEventListener("change", applyCustomMode);
  $("m-img").addEventListener("change", (e) => {
    const f = e.target.files && e.target.files[0];
    if (f) uploadCustomImage(f);
  });
  $("m-img-clear").addEventListener("click", resetCustomImage);
  $("btn-scan-custom").addEventListener("click", customFromScan);
  $("m-img-from-scan").addEventListener("click", () => {
    if (lastScanFile) uploadCustomImage(lastScanFile);
  });
  setupCatalogSearch();
  $("file-input").addEventListener("change", (e) => {
    handlePhoto(e.target.files[0]);
    e.target.value = "";
  });

  // Bild per Drag & Drop auf die Scan-Fläche ziehen (Desktop)
  const dropZone = document.querySelector("[data-scan-drop]");
  if (dropZone) {
    ["dragenter", "dragover"].forEach((ev) =>
      dropZone.addEventListener(ev, (e) => {
        e.preventDefault();
        dropZone.classList.add("drag-over");
      }));
    ["dragleave", "dragend"].forEach((ev) =>
      dropZone.addEventListener(ev, (e) => {
        e.preventDefault();
        dropZone.classList.remove("drag-over");
      }));
    dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropZone.classList.remove("drag-over");
      const file = [...(e.dataTransfer.files || [])]
        .find((f) => f.type.startsWith("image/"));
      if (file) handlePhoto(file);
      else toast("Bitte eine Bilddatei ablegen");
    });
  }

  // Screenshot/Bild aus der Zwischenablage einfügen (nur im Scan-Tab)
  document.addEventListener("paste", (e) => {
    const scanView = $("view-scan");
    if (!scanView || scanView.hidden) return;
    const item = [...(e.clipboardData?.items || [])]
      .find((i) => i.type.startsWith("image/"));
    if (item) {
      const file = item.getAsFile();
      if (file) { handlePhoto(file); toast("Bild eingefügt 📋"); }
    }
  });
  document.querySelectorAll(".tab").forEach((b) =>
    b.addEventListener("click", () => showTab(b.dataset.tab)));
  // Die zuletzt gewählte Sortierung gilt als persönliche Einstellung und
  // wird im Profil gespeichert – auf dem nächsten Gerät steht sie genauso.
  $("sort").addEventListener("change", () => {
    loadCollection();
    saveSortPref($("sort").value);
  });
  $("type-filter").addEventListener("change", loadCollection);
  const collViewBtn = $("btn-collview");
  if (collViewBtn) {
    collViewBtn.addEventListener("click", () => {
      const grid = localStorage.getItem("bf_collview") === "grid";
      localStorage.setItem("bf_collview", grid ? "list" : "grid");
      applyCollView();
    });
  }
  let searchTimer;
  $("search").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadCollection, 300);
  });

  // X in Suchfeldern: leert das Feld und stößt die zugehörige Suche neu an
  document.querySelectorAll(".search-clear").forEach((btn) => {
    const input = $(btn.dataset.clear);
    if (!input) return;
    const sync = () => btn.classList.toggle("show", input.value !== "");
    input.addEventListener("input", sync);
    btn.addEventListener("click", () => {
      input.value = "";
      sync();
      input.focus();
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    sync();
  });

  if (state.token) { refreshMe(); showApp(); } else showLogin();

  // Galerie: Tipp auf ein Kartenbild öffnet alle Katalogbilder der Figur
  document.addEventListener("click", (ev) => {
    const img = ev.target.closest(".card-img");
    if (img && img.src && !img.src.startsWith("data:")) {
      openGallery(img.src, img.dataset.gid, img.dataset.gtype);
    }
  });
  $("lightbox").addEventListener("click", (ev) => {
    if (ev.target.closest(".lb-nav")) return;
    closeGallery();
  });
  $("lb-prev").addEventListener("click", () => stepGallery(-1));
  $("lb-next").addEventListener("click", () => stepGallery(1));
  document.addEventListener("keydown", (ev) => {
    if ($("lightbox").hidden) return;
    if (ev.key === "Escape") closeGallery();
    if (ev.key === "ArrowLeft") stepGallery(-1);
    if (ev.key === "ArrowRight") stepGallery(1);
  });
  let touchX = null;
  $("lightbox").addEventListener("touchstart",
    (ev) => { touchX = ev.touches[0].clientX; }, { passive: true });
  $("lightbox").addEventListener("touchend", (ev) => {
    if (touchX == null) return;
    const dx = ev.changedTouches[0].clientX - touchX;
    touchX = null;
    if (Math.abs(dx) > 40) stepGallery(dx < 0 ? 1 : -1);
  }, { passive: true });
  $("lightbox-img").addEventListener("error", () => {
    // Nicht existierende Bildvarianten still aussortieren
    if (gallery.urls.length <= 1) { closeGallery(); return; }
    gallery.urls.splice(gallery.idx, 1);
    gallery.idx = gallery.idx % gallery.urls.length;
    renderGallery();
  });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
  wireInstallCard();
  zugZumNeuladen();
  scanAuswahlEinrichten();
});

/* --------------------------------------- „Auf den Startbildschirm"

   Ob die App aus dem Browser oder vom Startbildschirm läuft, verrät der
   Anzeigemodus – auf iOS über ein eigenes Merkmal, das Apple nie ersetzt hat.
   Anbieten lässt sich das Hinzufügen aber nur dort, wo der Browser es
   erlaubt: Chromium meldet sich vorher mit `beforeinstallprompt`, Safari
   kennt keinen solchen Weg – dort bleibt nur die Anleitung. */

function isStandalone() {
  return window.matchMedia("(display-mode: standalone)").matches
    || window.navigator.standalone === true;
}

function isIOS() {
  const ua = navigator.userAgent;
  // iPad meldet sich seit iPadOS 13 als Macintosh – am Touch erkennbar.
  return /iPhone|iPod|iPad/.test(ua)
    || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
}

/* --------------------------------------- Nach unten ziehen = neu laden

   Vom Startbildschirm gestartet fehlt die Adressleiste – und damit der
   Knopf zum Neuladen. Auf iOS gibt es dort auch keine Geste dafür. Deshalb
   hier eine eigene, und nur dort: Im Browser macht der das schon selbst,
   zwei Anzeigen übereinander will niemand sehen. */

const PTR_SCHWELLE = 70;      // ab hier löst das Loslassen aus
const PTR_MAX = 110;          // weiter zieht es nicht mit

function zugZumNeuladen() {
  if (!isStandalone() || !("ontouchstart" in window)) return;
  // Der eigene Zug ersetzt den des Browsers, falls es ihn gibt
  document.body.style.overscrollBehaviorY = "contain";

  const anzeige = document.createElement("div");
  anzeige.className = "ptr";
  anzeige.setAttribute("aria-hidden", "true");
  anzeige.innerHTML = brickSpinner(tr("Neu laden"), 26);
  document.body.appendChild(anzeige);

  let startY = null, startX = 0, zug = 0, laeuft = false;

  const zurueck = () => {
    startY = null;
    zug = 0;
    anzeige.classList.remove("ptr-an", "ptr-bereit");
    anzeige.style.transform = "";
  };

  // Nur ganz oben und nur, wenn nichts darüber liegt: Ein offenes Popup
  // scrollt selbst, da wäre der Zug ein Griff ins Leere.
  const freieBahn = () => window.scrollY <= 0
    && !document.getElementById("card-modal")
    && $("lightbox").hidden
    && $("update-lock").hidden;

  document.addEventListener("touchstart", (ev) => {
    if (laeuft || ev.touches.length !== 1 || !freieBahn()) return;
    startY = ev.touches[0].clientY;
    startX = ev.touches[0].clientX;
  }, { passive: true });

  document.addEventListener("touchmove", (ev) => {
    if (startY == null || laeuft) return;
    const dy = ev.touches[0].clientY - startY;
    const dx = Math.abs(ev.touches[0].clientX - startX);
    // Nach oben, quer oder inzwischen weggescrollt: kein Zug
    if (dy <= 0 || dx > dy || !freieBahn()) { zurueck(); return; }
    ev.preventDefault();                 // sonst wandert die Seite mit
    zug = Math.min(PTR_MAX, dy * 0.5);   // Widerstand, wie man ihn erwartet
    anzeige.classList.add("ptr-an");
    anzeige.classList.toggle("ptr-bereit", zug >= PTR_SCHWELLE);
    anzeige.style.transform = `translate(-50%, ${zug.toFixed(1)}px)`;
  }, { passive: false });

  document.addEventListener("touchend", () => {
    if (startY == null) return;
    if (zug >= PTR_SCHWELLE) {
      // Das Neuladen braucht einen Moment. Bis dahin muss der Zug beendet
      // sein, sonst hinge das Scrollen an einem Startpunkt von eben.
      laeuft = true;
      startY = null;
      zug = 0;
      anzeige.classList.add("ptr-laeuft");
      // Über `neuLadenMit`, damit der Speicher-Verlauf das nicht für einen
      // Absturz hält – dieselbe Falle wie beim Neustart des Servers.
      neuLadenMit("Nach unten gezogen");
      return;
    }
    zurueck();
  }, { passive: true });

  document.addEventListener("touchcancel", zurueck, { passive: true });
}

let installPrompt = null;

window.addEventListener("beforeinstallprompt", (ev) => {
  ev.preventDefault();            // eigenen Zeitpunkt wählen
  installPrompt = ev;
  updateInstallCard();
});

window.addEventListener("appinstalled", () => {
  installPrompt = null;
  updateInstallCard();
  toast("Brickfolio liegt jetzt auf dem Startbildschirm 📲");
});

function updateInstallCard() {
  const card = $("install-card");
  if (!card) return;
  const touch = window.matchMedia("(pointer: coarse)").matches;
  // Nichts anbieten, wenn es schon liegt, weggeklickt wurde, oder am Rechner:
  // dort bietet der Browser das Installieren ohnehin in der Adresszeile an.
  if (isStandalone() || localStorage.getItem("bf_install_hidden") || !touch) {
    card.hidden = true;
    return;
  }

  const go = $("install-go");
  const text = $("install-text");
  if (installPrompt) {
    text.textContent = tr("Ein Tipp, und Brickfolio startet künftig wie eine "
      + "eigene App – ohne Adresszeile, mit eigenem Symbol.");
    go.hidden = false;
    card.hidden = false;
  } else if (isIOS()) {
    // Safari kennt keinen Knopf dafür – hier hilft nur der Weg über „Teilen".
    text.innerHTML = tr("In Safari unten auf <b>Teilen</b> tippen (das "
      + "Quadrat mit dem Pfeil nach oben), dann <b>„Zum Home-Bildschirm“</b>. "
      + "Danach startet Brickfolio wie eine eigene App.");
    go.hidden = true;
    card.hidden = false;
  } else if (!window.isSecureContext) {
    // Ohne HTTPS lässt kein Browser das Hinzufügen zu – das ist der Grund,
    // nicht ein fehlendes Feature. Also sagen, woran es liegt.
    text.innerHTML = tr("Dafür muss die App über <b>https</b> erreichbar "
      + "sein – über eine reine <b>http</b>-Adresse im Heimnetz erlauben die "
      + "Browser das Hinzufügen nicht. Einen verschlüsselten Zugang richtet "
      + "der Assistent unter <b>Mehr → Externer Zugriff</b> ein.");
    go.hidden = true;
    card.hidden = false;
  } else {
    card.hidden = true;           // Browser meldet sich vielleicht noch
  }
}

function wireInstallCard() {
  const go = $("install-go");
  if (!go) return;
  go.addEventListener("click", async () => {
    if (!installPrompt) return;
    go.disabled = true;
    try {
      installPrompt.prompt();
      await installPrompt.userChoice;
    } catch (_) { /* abgebrochen – dann bleibt die Karte stehen */ }
    installPrompt = null;         // gilt nur einmal
    go.disabled = false;
    updateInstallCard();
  });
  $("install-hide").addEventListener("click", () => {
    localStorage.setItem("bf_install_hidden", "1");
    updateInstallCard();
  });
}
