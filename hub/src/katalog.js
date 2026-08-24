/**
 * Den Katalogabzug erzeugen – im Hub statt in jeder Instanz.
 *
 * Bis 2.40.0 baute ihn jede Instanz selbst: Nummern der Reihe nach bei
 * BrickLink abklappern und danach jedes Bild von einem Sehmodell beschreiben
 * lassen. Viermal dieselbe Arbeit für dasselbe Ergebnis – der Abzug
 * beschreibt BrickLinks Fotos, nicht die Sammlung von irgendwem. Und jede
 * Instanz brauchte dafür eigene BrickLink-Zugangsdaten und ein Sehmodell.
 *
 * Jetzt erzeugt ihn der Hub einmal, die Instanzen holen ihn nur noch ab.
 */

const rfc3986 = (s) =>
  encodeURIComponent(String(s)).replace(/[!*'()]/g,
    (c) => "%" + c.charCodeAt(0).toString(16).toUpperCase());

/* ------------------------------------------------- BrickLink (OAuth 1.0a) */

async function hmacSha1(schluessel, text) {
  const k = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(schluessel),
    { name: "HMAC", hash: "SHA-1" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", k, new TextEncoder().encode(text));
  return btoa(String.fromCharCode(...new Uint8Array(sig)));
}

/**
 * Einen BrickLink-Aufruf signieren und absetzen.
 *
 * OAuth 1.0a, HMAC-SHA1. Es gibt dafür in einem Worker keine Bibliothek –
 * `crypto.subtle` kann HMAC-SHA1, den Rest muss man selbst zusammensetzen.
 * Zwei Stolpersteine, die beide zu einem stummen 401 führen:
 *
 * - Die Signaturbasis verlangt **RFC-3986**-Kodierung, nicht die von
 *   `encodeURIComponent`. Die lässt `!*'()` stehen.
 * - Die Parameter müssen **sortiert** in die Basis, und zwar die aus der
 *   Abfrage **zusammen** mit den `oauth_*`-Feldern.
 */
/**
 * Der BrickLink-Zugang – aus der Datenbank, sonst aus den Secrets.
 *
 * Die Konsole trägt ihn in `hub_settings` ein; ein Wechsel braucht damit
 * keinen Rechner mit angemeldetem Wrangler. Wer die Werte lieber
 * verschlüsselt liegen hat, setzt sie weiter mit `wrangler secret put` –
 * sie gelten, solange in der Datenbank nichts steht.
 *
 * Gemerkt wird das Ergebnis je Isolat: Sonst kostete jeder einzelne
 * BrickLink-Abruf vier zusätzliche Datenbankzeilen, und bei zwanzig Abrufen
 * je Takt ist das reine Verschwendung.
 */
let _zugang = null;

export async function blZugang(env) {
  if (_zugang) return _zugang;
  const rows = (await env.DB.prepare(
    "SELECT name, value FROM hub_settings WHERE name IN "
    + "('bl_consumer_key','bl_consumer_secret','bl_token','bl_token_secret')")
    .all()).results || [];
  const db = Object.fromEntries(rows.map((r) => [r.name.toUpperCase(), r.value]));
  _zugang = {
    BL_CONSUMER_KEY: db.BL_CONSUMER_KEY || env.BL_CONSUMER_KEY || "",
    BL_CONSUMER_SECRET: db.BL_CONSUMER_SECRET || env.BL_CONSUMER_SECRET || "",
    BL_TOKEN: db.BL_TOKEN || env.BL_TOKEN || "",
    BL_TOKEN_SECRET: db.BL_TOKEN_SECRET || env.BL_TOKEN_SECRET || "",
  };
  return _zugang;
}

/** Nach dem Ändern in der Konsole: Der gemerkte Zugang ist überholt. */
export function zugangVergessen() { _zugang = null; }


export async function oauthKopf(env, basis, suche = {}, nonce = "",
                               zeitstempel = "") {
  const oauth = {
    oauth_consumer_key: env.BL_CONSUMER_KEY,
    oauth_token: env.BL_TOKEN,
    oauth_signature_method: "HMAC-SHA1",
    oauth_timestamp: zeitstempel || String(Math.floor(Date.now() / 1000)),
    oauth_nonce: nonce || crypto.randomUUID().replace(/-/g, ""),
    oauth_version: "1.0",
  };
  const alle = { ...suche, ...oauth };
  const normiert = Object.keys(alle).sort()
    .map((k) => rfc3986(k) + "=" + rfc3986(alle[k])).join("&");
  const grundlage = "GET&" + rfc3986(basis) + "&" + rfc3986(normiert);
  const key = rfc3986(env.BL_CONSUMER_SECRET) + "&"
    + rfc3986(env.BL_TOKEN_SECRET);
  oauth.oauth_signature = await hmacSha1(key, grundlage);
  return "OAuth " + Object.keys(oauth).sort()
    .map((k) => rfc3986(k) + '="' + rfc3986(oauth[k]) + '"').join(", ");
}

async function blHolen(env, pfad, suche = {}) {
  const basis = "https://api.bricklink.com/api/store/v1" + pfad;
  // `oauthKopf` liest die vier Werte aus dem, was hier hereingereicht wird –
  // deshalb den zusammengeführten Zugang übergeben, nicht `env` selbst.
  const kopf = await oauthKopf(await blZugang(env), basis, suche);
  const url = basis + (Object.keys(suche).length
    ? "?" + Object.keys(suche).map((k) => rfc3986(k) + "=" + rfc3986(suche[k])).join("&")
    : "");

  const r = await fetch(url, {
    headers: { Authorization: kopf, "User-Agent": "Brickfolio-Hub" },
  });
  if (r.status === 404) return null;                 // gibt es nicht
  if (!r.ok) throw new Error("BrickLink " + r.status);
  const d = await r.json();
  // BrickLink verpackt alles in `meta` + `data`; ein 200 mit meta.code 404
  // kommt vor und heißt dasselbe wie ein echter 404.
  if (d && d.meta && d.meta.code >= 400) {
    if (d.meta.code === 404) return null;
    throw new Error("BrickLink " + d.meta.code);
  }
  return d && d.data ? d.data : null;
}

/* ------------------------------------------------------------ Abklappern */

// Wie viele BrickLink-Abrufe je Lauf. Der Zugang ist derselbe, über den auch
// die Preise laufen, und BrickLink lässt 5.000 Aufrufe am Tag zu. Bei einem
// Lauf alle 15 Minuten sind 20 Abrufe rund 1.900 am Tag – genug Luft für die
// Preise, und der Abzug ist ohnehin fertig; hier geht es um Nachschub.
export const ABRUFE_JE_LAUF = 20;

// Nach so vielen 404 am Stück gilt ein Thema als durch. BrickLink lässt
// Lücken in der Nummerierung; 25 sind gemessen großzügig genug.
const LUECKE = 25;

/**
 * Gibt es dieses Präfix – und mit wie vielen Ziffern?
 *
 * Ohne diese Auskunft trägt man ein Thema ein und merkt erst Stunden später,
 * wenn der Takt dort ankommt, dass es ein Tippfehler war.
 */
export async function praefixPruefen(env, praefix) {
  const breite = await breiteErmitteln(env, praefix);
  if (!breite) return { praefix, gibt_es: false };
  for (const n of [1, 2, 3, 5, 10]) {
    const nr = praefix + String(n).padStart(breite, "0");
    const d = await blHolen(env, "/items/minifig/" + nr);
    if (d) return { praefix, gibt_es: true, breite, beispiel: nr,
                    name: String(d.name || "") };
  }
  return { praefix, gibt_es: true, breite };
}


/** Wie viele Ziffern hat dieses Thema – drei oder vier? */
async function breiteErmitteln(env, praefix) {
  for (const breite of [4, 3]) {
    for (const n of [1, 2, 3, 5, 10]) {
      const nr = praefix + String(n).padStart(breite, "0");
      try {
        if (await blHolen(env, "/items/minifig/" + nr)) return breite;
      } catch (e) {
        // Kein 404, sondern etwas anderes (Kontingent, Zugang): Dann ist
        // nicht die Breite falsch, sondern der Aufruf. Nicht weiterraten.
        throw e;
      }
    }
  }
  return 0;
}

/**
 * Ein Stück abklappern. Nimmt das erste unfertige Thema und arbeitet
 * `ABRUFE_JE_LAUF` Nummern ab – mehr passt nicht in ein Kontingent, das
 * sich der Abzug mit den Preisen teilt.
 */
// Wann ein fertiges Thema noch einmal angesehen wird. **Ohne das passiert
// genau nichts mehr**: Sind alle achtzehn einmal durch, stünde der Takt für
// immer still – und der Nachschub, für den er da ist, käme nie an. BrickLink
// legt laufend neue Figuren an. Eine Woche ist reichlich; die Nachschau
// kostet nur die 25 Fehlgriffe bis zur nächsten Lücke.
export const NACHSCHAU = 7 * 24 * 3600;

export async function abklappern(env, budget = ABRUFE_JE_LAUF) {
  const jetzt0 = Math.floor(Date.now() / 1000);
  // Unfertige zuerst, dann die am längsten nicht nachgesehenen.
  const thema = await env.DB.prepare(
    "SELECT * FROM katalog_lauf WHERE aktiv = 1 "
    + "AND (fertig_at IS NULL OR fertig_at < ?) "
    + "ORDER BY fertig_at IS NOT NULL, zuletzt ASC LIMIT 1")
    .bind(jetzt0 - NACHSCHAU).first();
  if (!thema) return { abgerufen: 0, grund: "alle Themen frisch nachgesehen" };

  let breite = thema.breite;
  let abgerufen = 0;
  if (!breite) {
    breite = await breiteErmitteln(env, thema.praefix);
    abgerufen += 10;                       // die Probe kostet auch Abrufe
    if (!breite) {
      await env.DB.prepare(
        "UPDATE katalog_lauf SET aktiv = 0, fertig_at = ? WHERE praefix = ?")
        .bind(Math.floor(Date.now() / 1000), thema.praefix).run();
      return { abgerufen, praefix: thema.praefix, grund: "gibt es nicht" };
    }
    await env.DB.prepare("UPDATE katalog_lauf SET breite = ? WHERE praefix = ?")
      .bind(breite, thema.praefix).run();
  }

  let nummer = thema.zuletzt;
  // Bei einer Nachschau von vorn zählen: Die 25 Fehlgriffe von damals sind
  // abgearbeitet, sonst gälte das Thema sofort wieder als fertig, ohne einen
  // einzigen Abruf.
  let luecke = thema.fertig_at ? 0 : thema.luecke;
  let neu = 0;
  const jetzt = Math.floor(Date.now() / 1000);
  while (abgerufen < budget && luecke < LUECKE) {
    nummer += 1;
    abgerufen += 1;
    const nr = thema.praefix + String(nummer).padStart(breite, "0");
    let d;
    try {
      d = await blHolen(env, "/items/minifig/" + nr);
    } catch (e) {
      // Kontingent erschöpft oder Zugang falsch: Der Rest des Laufs würde
      // dasselbe erleben. Stand sichern und aufhören.
      await env.DB.prepare(
        "UPDATE katalog_lauf SET zuletzt = ?, luecke = ? WHERE praefix = ?")
        .bind(nummer - 1, luecke, thema.praefix).run();
      throw e;
    }
    if (!d) { luecke += 1; continue; }
    luecke = 0;
    neu += 1;
    const name = String(d.name || "");
    await env.DB.prepare(
      "INSERT INTO katalog (item_no, item_type, name, such, category_id, "
      + "jahr, img_url, farben, art, merkmale, modell, updated_at) "
      + "VALUES (?, 'minifig', ?, ?, ?, ?, ?, '', '', '', '', ?) "
      + "ON CONFLICT(item_no, item_type) DO UPDATE SET "
      + "name = excluded.name, such = excluded.such, "
      + "category_id = excluded.category_id, jahr = excluded.jahr, "
      + "img_url = excluded.img_url, updated_at = excluded.updated_at")
      .bind(nr, name, suchtext(name), String(d.category_id || ""),
        Number(d.year_released) || 0,
        "https://img.bricklink.com/ML/" + nr + ".jpg", jetzt).run();
  }

  const fertig = luecke >= LUECKE;
  await env.DB.prepare(
    "UPDATE katalog_lauf SET zuletzt = ?, luecke = ?, gefunden = gefunden + ?, "
    + "fertig_at = ? WHERE praefix = ?")
    .bind(nummer, luecke, neu, fertig ? jetzt : null, thema.praefix).run();
  return { abgerufen, neu, praefix: thema.praefix, bis: nummer, fertig };
}

/**
 * Derselbe Suchtext wie in der Instanz: kleingeschrieben, ohne Satzzeichen.
 * Der Vorfilter in SQL muss dieselbe Elle benutzen wie der Vergleich in
 * Python – „c3 po" soll `C-3PO` finden, und `LIKE '%c3%'` auf dem rohen
 * Namen scheitert am Bindestrich.
 */
export function suchtext(name) {
  // **Zusammengezogen, nicht mit Leerzeichen.** Die Instanz filtert mit
  // `such LIKE '%c3%'` vor; „C-3PO" muss dafuer zu `c3po` werden. Mit
  // Leerzeichen (`c 3po`) findet dieser Vorfilter nichts, und die Suche,
  // fuer die der ganze Abzug da ist, geht ins Leere. Dieselbe Elle wie
  // `_wortanfaenge` in der App.
  return String(name || "").toLowerCase()
    .split(/[^a-z0-9]+/).filter(Boolean).join("");
}

/* ------------------------------------------------------- Bilder ansehen */

// Wie viele Bilder je Lauf. Jedes ist ein Abruf beim Bildserver plus ein
// Modellaufruf; acht sind bei einem Lauf alle 15 Minuten rund 770 am Tag –
// weit mehr als der Nachschub je braucht.
export const BILDER_JE_LAUF = 8;

// Workers AI. Beim Wechsel des Modells **muss** `modell` in der Zeile
// mitgeschrieben werden: Nur daran ist später zu erkennen, welche
// Beschreibungen von wem stammen – und nur so lassen sich die schwächeren
// gezielt neu machen, ohne die guten anzutasten.
export const BILD_MODELL = "@cf/meta/llama-3.2-11b-vision-instruct";

const BILD_FRAGE =
  "This LEGO minifigure. First: what kind of figure is it? Answer with one "
  + "or two English words (e.g. Soldier, Droid, Robot, Animal, Knight, Pilot, "
  + "Alien, Police, Wizard). "
  + "Then describe it part by part for a catalogue search: head, hair, "
  + "helmet or headgear, torso, arms, legs, cape. For each, give its main "
  + "colour in plain English (red, dark blue, light gray, tan) and a short "
  + "description of what is printed on it - pattern, markings, face, insignia, "
  + "and the colours of that printing. "
  + "Only list parts that stand out by colour or printing; skip plain parts "
  + "and anything you cannot see. Finally list what the figure holds. "
  + 'Answer as JSON: {"kind": "...", "parts": [{"part": "...", '
  + '"color": "...", "print": "..."}], "accessories": ["..."]}';

/** Aus der Modellantwort das JSON herausschälen – notfalls aus Fließtext. */
export function antwortLesen(roh) {
  const text = typeof roh === "string" ? roh
    : (roh && (roh.response || roh.description || roh.text)) || "";
  const a = text.indexOf("{");
  const b = text.lastIndexOf("}");
  if (a < 0 || b <= a) return null;
  try { return JSON.parse(text.slice(a, b + 1)); } catch (e) { return null; }
}

const wort = (roh, hoechstens) =>
  String(roh || "").toLowerCase().replace(/[^a-z ]+/g, " ")
    .split(/\s+/).filter(Boolean).slice(0, hoechstens).join(" ");

/** Die Modellantwort in `art`, `farben` und `merkmale` umsetzen. */
export function merkmaleBauen(d) {
  if (!d) return null;
  const farben = [];
  const stuecke = [];
  for (const teil of Array.isArray(d.parts) ? d.parts : []) {
    if (!teil || typeof teil !== "object") continue;
    const name = wort(teil.part, 3);
    let farbe = wort(teil.color, 3);
    let druck = wort(teil.print, 12);
    // „none" ist die Art, wie das Modell „hat es nicht" sagt – als Wort im
    // Suchtext träfe es jede Suche nach Nichtvorhandenem.
    if (farbe === "none" || farbe === "") farbe = "";
    if (druck === "none" || druck === "plain" || druck === "") druck = "";
    if (!name || (!farbe && !druck)) continue;
    stuecke.push([name, farbe, druck].filter(Boolean).join(" "));
    for (const w of farbe.split(" ")) {
      if (w.length >= 3 && !farben.includes(w)) farben.push(w);
    }
  }
  for (const ding of Array.isArray(d.accessories) ? d.accessories : []) {
    const x = wort(ding, 4);
    if (x && x !== "none") stuecke.push("holding " + x);
  }
  return {
    art: wort(d.kind, 2),
    farben: farben.slice(0, 5).join(", "),
    merkmale: stuecke.join("; "),
  };
}

/**
 * Ein Stück beschreiben lassen.
 *
 * **Nur Zeilen ohne Beschreibung.** Die 9.741 vorhandenen stammen von
 * `qwen3-vl` und werden nicht angetastet – wer sie überschreibt, macht den
 * Abzug uneinheitlich, ohne dass jemand es merkt.
 */
export const AUFGEBEN_NACH = 3;

export async function beschreiben(env, budget = BILDER_JE_LAUF) {
  const rows = (await env.DB.prepare(
    "SELECT item_no, img_url, versuche FROM katalog WHERE merkmale = '' "
    + "AND img_url <> '' ORDER BY versuche ASC LIMIT ?")
    .bind(budget).all()).results || [];
  let getan = 0;
  let erkannt = 0;
  for (const r of rows) {
    let d = null;
    let fehler = "";
    try {
      const bild = await fetch(r.img_url, {
        headers: { "User-Agent": "Brickfolio-Hub" },
      });
      if (!bild.ok) throw new Error("Bild " + bild.status);
      const bytes = new Uint8Array(await bild.arrayBuffer());
      const antwort = await env.AI.run(BILD_MODELL, {
        image: [...bytes], prompt: BILD_FRAGE, max_tokens: 512,
      });
      d = merkmaleBauen(antwortLesen(antwort));
    } catch (e) {
      fehler = String((e && e.message) || e);
    }
    if (fehler) {
      // **Zwei Fälle, die gleich aussehen und es nicht sind.**
      //
      // Der Dienst ist weg: Dann nichts schreiben und aufhören. Ein Ausfall
      // darf nicht aussehen wie „angesehen, nichts erkannt" – sonst hakt der
      // Lauf den ganzen Bestand ab, ohne je hingesehen zu haben. Am
      // 21.08.2026 waren so 45 Figuren verbrannt, bevor es auffiel.
      //
      // Diese eine Figur bringt das Modell aus dem Tritt: Dann hält sie den
      // ganzen Abzug auf, denn ein Fehlschlag schreibt nichts weg und sie
      // steht beim nächsten Griff wieder vorn. Am 24.08.2026 blieb der Lauf
      // deshalb bei 9.740 von 9.741 stehen – `cty0131`, zwölf Anläufe an
      // derselben Figur.
      //
      // Unterschieden wird am Zähler: Die ersten Male gilt „Dienst weg",
      // danach gilt die Figur als hoffnungslos und wird abgehakt.
      const n = (r.versuche || 0) + 1;
      await env.DB.prepare(
        "UPDATE katalog SET versuche = ? WHERE item_no = ?")
        .bind(n, r.item_no).run();
      console.error("Katalog-Bild", r.item_no, "Versuch", n, fehler);
      if (n < AUFGEBEN_NACH) break;
      // Kein `break`: Sie läuft in das Wegschreiben unten und gilt damit als
      // angesehen, ohne Ergebnis – sonst kommt der Abzug nie ans Ende.
      d = null;
    }
    getan += 1;
    if (d && (d.merkmale || d.art)) erkannt += 1;
    await env.DB.prepare(
      "UPDATE katalog SET farben = ?, art = ?, merkmale = ?, modell = ?, "
      + "updated_at = ? WHERE item_no = ?")
      .bind((d && d.farben) || "–", (d && d.art) || "",
        (d && d.merkmale) || "–", BILD_MODELL,
        Math.floor(Date.now() / 1000), r.item_no).run();
  }
  return { getan, erkannt, offen: rows.length - getan };
}

/* --------------------------------------------------------------- Der Takt */

/** Ein Lauf: erst Nachschub holen, dann Bilder ansehen. */
export async function katalogTakt(env) {
  const ergebnis = { abzug: null, bilder: null };
  try {
    ergebnis.abzug = await abklappern(env);
  } catch (e) {
    ergebnis.abzug = { fehler: String((e && e.message) || e) };
    console.error("Katalog-Abzug:", e);
  }
  try {
    ergebnis.bilder = await beschreiben(env);
  } catch (e) {
    ergebnis.bilder = { fehler: String((e && e.message) || e) };
    console.error("Katalog-Bilder:", e);
  }
  return ergebnis;
}
