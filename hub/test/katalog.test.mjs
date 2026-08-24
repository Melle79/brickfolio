/**
 * Was sich ohne Cloudflare pruefen laesst – und das ist mehr, als es aussieht.
 *
 * Der wichtigste Test ist die **OAuth-Signatur**. Es gibt dafuer in einem
 * Worker keine Bibliothek; sie ist von Hand zusammengesetzt, und eine falsche
 * Signatur ist ein stummer 401 – BrickLink sagt nicht, was daran nicht passte.
 * Die Referenz kommt aus `requests_oauthlib`, derselben Bibliothek, mit der
 * die App seit Monaten erfolgreich bei BrickLink anfragt: gleiche Eingaben,
 * fester Nonce und Zeitstempel, gleiche Signatur.
 *
 * Laufen mit:  node --test test/
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { oauthKopf, suchtext, antwortLesen, merkmaleBauen } from
  "../src/katalog.js";

const ENV = {
  BL_CONSUMER_KEY: "CKEY", BL_CONSUMER_SECRET: "CSECRET",
  BL_TOKEN: "TKEY", BL_TOKEN_SECRET: "TSECRET",
};

test("die Signatur stimmt mit requests_oauthlib ueberein", async () => {
  const kopf = await oauthKopf(
    ENV, "https://api.bricklink.com/api/store/v1/items/minifig/sw0344",
    {}, "abc123def456", "1787576000");
  const m = kopf.match(/oauth_signature="([^"]+)"/);
  assert.ok(m, "keine Signatur im Kopf");
  // Referenz, erzeugt am 24.08.2026 mit requests_oauthlib bei gleichem
  // Nonce und Zeitstempel.
  assert.equal(decodeURIComponent(m[1]), "0s9fa2W+spzsxNEIDrxdzaRXq0U=");
});

test("Abfrageparameter gehen in die Signatur ein", async () => {
  const ohne = await oauthKopf(ENV, "https://x.test/a", {}, "n", "1");
  const mit = await oauthKopf(ENV, "https://x.test/a", { seit: "5" }, "n", "1");
  assert.notEqual(ohne, mit,
    "die Abfrage blieb aussen vor – BrickLink antwortet darauf mit 401");
});

test("der Suchtext benutzt dieselbe Elle wie die Instanz", () => {
  // `LIKE '%c3%'` auf dem rohen Namen scheitert am Bindestrich – deshalb
  // liegt der Name ein zweites Mal ohne Satzzeichen daneben.
  assert.equal(suchtext("R-3PO Protocol Droid"), "r 3po protocol droid");
  assert.equal(suchtext("C-3PO"), "c 3po");
});

test("die Antwort wird auch aus Fliesstext geschaelt", () => {
  const roh = { response: 'Sure! Here you go:\n{"kind": "Knight", "parts": []}\nHope that helps.' };
  assert.deepEqual(antwortLesen(roh), { kind: "Knight", parts: [] });
});

test("unlesbare Antworten geben null statt zu werfen", () => {
  assert.equal(antwortLesen({ response: "I cannot see an image." }), null);
  assert.equal(antwortLesen({ response: "{kaputt" }), null);
  assert.equal(antwortLesen(""), null);
});

test("aus den Teilen wird durchsuchbarer Text", () => {
  const d = merkmaleBauen({
    kind: "Knight",
    parts: [{ part: "torso", color: "red", print: "black and yellow dragon" },
            { part: "cape", color: "yellow", print: "green dragon red wings" }],
    accessories: ["sword"],
  });
  assert.equal(d.art, "knight");
  assert.equal(d.farben, "red, yellow");
  assert.equal(d.merkmale,
    "torso red black and yellow dragon; cape yellow green dragon red wings; "
    + "holding sword");
});

test("„none\" wird nicht zum Suchwort", () => {
  // So sagt das Modell „hat es nicht". Als Wort im Suchtext traefe es jede
  // Suche nach Nichtvorhandenem.
  const d = merkmaleBauen({
    kind: "Knight",
    parts: [{ part: "torso", color: "red", print: "dragon" },
            { part: "cape", color: "none", print: "none" }],
    accessories: ["none"],
  });
  assert.equal(d.merkmale, "torso red dragon");
  assert.ok(!d.farben.includes("none"));
});

test("ein ganzer Satz wird auf Suchlaenge gekuerzt", () => {
  // Sonst traefe der Suchtext irgendwann alles.
  const d = merkmaleBauen({
    kind: "a very elaborate ceremonial knight of the realm",
    parts: [{ part: "torso", color: "red",
              print: "one two three four five six seven eight nine ten "
                     + "eleven twelve thirteen fourteen" }],
  });
  assert.equal(d.art, "a very");
  assert.ok(!d.merkmale.includes("thirteen"), d.merkmale);
});
