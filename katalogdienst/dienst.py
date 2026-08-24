"""Die Schnittstelle, über die die Hub-Konsole den Abzug bedient.

Die Konsole ist eine **reine statische Seite** (nginx, nur HTML und JS). Sie
kann selbst nichts abklappern: An eine OAuth-Signatur kommt ein Browser nicht
heran, ohne die Zugangsdaten preiszugeben, und BrickLink lässt Anfragen aus
einer fremden Seite ohnehin nicht zu. Deshalb dieser Dienst daneben – die
Konsole bleibt die Bedienung, hier liegt die Arbeit.

Beides läuft auf derselben NAS: Die BrickLink-Zugangsdaten bleiben zu Hause,
und geplante Arbeit läuft auf einem Rechner, der sie nachweislich ausführt.
"""
import os
import re
import threading
import time

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import bild as bildmodul
import katalog
import laeufe
import veroeffentlichen as veroeffentlichung
from katalog import bl_enabled, db, init_db

VERSION = "1.0.0"

app = FastAPI(title="Brickfolio-Katalogdienst", version=VERSION)

# Die Konsole liegt auf derselben NAS, aber auf einem anderen Port – für den
# Browser ist das eine fremde Herkunft. Geschützt wird über den Token im
# Kopf, nicht über Cookies; deshalb ist „*" hier unbedenklich.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
    allow_headers=["authorization", "content-type"], allow_credentials=False)


def admin(authorization: str = Header(default="")):
    """Derselbe Token wie in der Konsole, aus der Umgebung dieses Dienstes.

    Ohne gesetzten Token verweigert der Dienst **alles** – ein offener
    Katalogdienst im Heimnetz könnte fremdes Kontingent verbrennen.
    """
    erwartet = (os.environ.get("ADMIN_TOKEN") or "").strip()
    if not erwartet:
        raise HTTPException(503, "Kein ADMIN_TOKEN gesetzt")
    gegeben = authorization.removeprefix("Bearer ").strip()
    if gegeben != erwartet:
        raise HTTPException(401, "Token fehlt oder stimmt nicht")
    return True


@app.on_event("startup")
def start():
    init_db()
    print("[katalogdienst] %s bereit · BrickLink=%s · Ollama=%s (%s)"
          % (VERSION, "ja" if bl_enabled() else "NEIN",
             bildmodul.ollama_url() or "NEIN", bildmodul.ollama_bild_modell()),
          flush=True)


@app.get("/api/health")
def health():
    """Ohne Token – damit sich von außen prüfen lässt, ob er überhaupt läuft."""
    return {"ok": True, "dienst": "brickfolio-katalog", "version": VERSION}


# ------------------------------------------------------------------ Stand


@app.get("/api/status")
def status(_=Depends(admin)):
    with db() as conn:
        z = conn.execute(
            "SELECT COUNT(*) AS gesamt,"
            " SUM(CASE WHEN merkmale = '' THEN 1 ELSE 0 END) AS offen,"
            " SUM(CASE WHEN merkmale NOT IN ('', '–') THEN 1 ELSE 0 END)"
            " AS beschrieben FROM katalog_index").fetchone()
        themen = [dict(r) for r in conn.execute(
            "SELECT * FROM katalog_lauf ORDER BY fertig_at IS NOT NULL,"
            " praefix")]
    return {
        "zeilen": {"gesamt": z["gesamt"] or 0, "offen": z["offen"] or 0,
                   "beschrieben": z["beschrieben"] or 0},
        "themen": themen,
        "bricklink": bl_enabled(),
        "ollama": bildmodul.ollama_url(),
        "modell": bildmodul.ollama_bild_modell(),
        # `offen` wird hier **frisch gezählt**, nicht aus dem Laufzustand
        # genommen. Als Feld im Speicher war es nach jedem Neustart 0, und
        # die Oberfläche meldete „alle Bilder angesehen", während 8.328
        # Figuren offen waren (22.08.2026).
        "abzug": {k: laeufe._katalog_lauf[k] for k in
                  ("aktiv", "praefix", "nummer", "gefunden", "neu", "fehler",
                   "warteschlange")},
        "bilder": {k: laeufe._farb_lauf[k] for k in
                   ("aktiv", "getan", "gefunden", "fehler")},
    }


# ------------------------------------------------------------------ Themen


class ThemaBody(BaseModel):
    praefix: str = Field(default="", max_length=6)


def _praefix(roh):
    p = (roh or "").strip().lower()
    if not re.fullmatch(r"[a-z]{2,6}", p):
        raise HTTPException(400, "Nur zwei bis sechs Buchstaben")
    return p


@app.post("/api/themen")
def thema_dazu(body: ThemaBody, _=Depends(admin)):
    p = _praefix(body.praefix)
    with db() as conn:
        conn.execute("INSERT INTO katalog_lauf (praefix) VALUES (?) "
                     "ON CONFLICT(praefix) DO UPDATE SET aktiv = 1, "
                     "fertig_at = NULL, luecke = 0", (p,))
    return {"ok": True, "praefix": p}


@app.delete("/api/themen/{praefix}")
def thema_ruhen(praefix: str, _=Depends(admin)):
    with db() as conn:
        conn.execute("UPDATE katalog_lauf SET aktiv = 0 WHERE praefix = ?",
                     (_praefix(praefix),))
    return {"ok": True}


@app.get("/api/pruefen")
def pruefen(praefix: str = "", _=Depends(admin)):
    """Gibt es das Thema – und mit wie vielen Ziffern?

    Ohne diese Auskunft trägt man ein Thema ein und merkt erst Stunden
    später, wenn der Lauf dort ankommt, dass es ein Tippfehler war.
    """
    p = _praefix(praefix)
    if not bl_enabled():
        raise HTTPException(400, "BrickLink ist nicht eingerichtet")
    breite = laeufe._katalog_breite(p)
    # `_katalog_breite` gibt im Zweifel 4 zurück – das heißt „nicht
    # entschieden", nicht „gefunden". Deshalb hier wirklich nachsehen, sonst
    # meldete der Knopf jedes Fantasiepräfix als gültig.
    for n in (1, 2, 3, 5, 10):
        nr = "%s%0*d" % (p, breite, n)
        try:
            d = katalog.bricklink_item("minifig", nr)
        except Exception:
            continue
        if d:
            return {"praefix": p, "gibt_es": True, "breite": breite,
                    "beispiel": nr, "name": (d.get("name") or "")}
    return {"praefix": p, "gibt_es": False, "breite": breite}


# ------------------------------------------------------------------ Läufe


class LaufBody(BaseModel):
    themen: str = Field(default="", max_length=200)


@app.post("/api/abzug/start")
def abzug_start(body: LaufBody | None = None, _=Depends(admin)):
    if not bl_enabled():
        raise HTTPException(400, "BrickLink ist nicht eingerichtet")
    if laeufe._katalog_lauf["aktiv"]:
        return {"ok": True, "info": "läuft bereits"}
    if body and body.themen.strip():
        praefixe = [_praefix(x) for x in body.themen.split(",") if x.strip()]
    else:
        with db() as conn:
            praefixe = [r["praefix"] for r in conn.execute(
                "SELECT praefix FROM katalog_lauf WHERE aktiv = 1 "
                "ORDER BY fertig_at IS NOT NULL, praefix")]
    if not praefixe:
        raise HTTPException(400, "Kein Thema aktiv")
    laeufe._katalog_lauf["stop"] = False
    laeufe._katalog_lauf["fehler"] = ""
    threading.Thread(target=laeufe._katalog_reihe, args=(praefixe,),
                     daemon=True).start()
    return {"ok": True, "themen": praefixe}


@app.post("/api/abzug/stop")
def abzug_stop(_=Depends(admin)):
    laeufe._katalog_lauf["stop"] = True
    return {"ok": True}


@app.post("/api/bilder/start")
def bilder_start(_=Depends(admin)):
    if not bildmodul.ollama_enabled():
        raise HTTPException(400, "Keine lokale KI eingerichtet")
    if laeufe._farb_lauf["aktiv"]:
        return {"ok": True, "info": "läuft bereits"}
    threading.Thread(target=laeufe._katalog_farben, daemon=True).start()
    return {"ok": True}


@app.post("/api/bilder/stop")
def bilder_stop(_=Depends(admin)):
    laeufe._farb_lauf["stop"] = True
    return {"ok": True}


@app.post("/api/probe")
def probe(item_no: str = "", _=Depends(admin)):
    """Die rohe Modellantwort zu einer Figur – **ohne sie zu schreiben**.

    Ein schwaches Modell schreibt Unsinn in den Suchtext, ohne dass es
    jemand merkt. Nach einem Wechsel will man vorher sehen, was es liefert.
    """
    with db() as conn:
        r = conn.execute("SELECT item_no, img_url, name FROM katalog_index "
                         "WHERE item_no = ?", (item_no.strip(),)).fetchone()
    if not r:
        raise HTTPException(404, "Figur nicht im Abzug")
    try:
        roh = bildmodul.bild_holen(r["img_url"])
        klein = bildmodul.bild_vorbereiten(roh, 512)
    except Exception as e:
        raise HTTPException(502, "Bild nicht ladbar: %s" % e)
    # Hier den Fehler **nicht** verschlucken: Das ist ein Diagnosewerkzeug,
    # und der Grund ist genau das, wonach man sucht.
    m = bildmodul.bild_merkmale(klein)
    return {"item_no": r["item_no"], "name": r["name"],
            "modell": bildmodul.ollama_bild_modell(),
            "bytes": len(klein), "ergebnis": m}


# ---------------------------------------------------------- Veröffentlichen


@app.post("/api/veroeffentlichen")
def veroeffentlichen_jetzt(_=Depends(admin)):
    """Den Index nach GitHub schieben – **nur Nummer und unsere Beschreibung**.

    Name, Jahr, Kategorie und Bildadresse bleiben hier. Das ist BrickLinks
    Inhalt; was hinausgeht, ist eine Kennung und ein Text, den unser
    Sehmodell über ein Foto geschrieben hat.
    """
    if not veroeffentlichung.bereit():
        raise HTTPException(400, "GITHUB_REPO oder GITHUB_TOKEN fehlt")
    try:
        return veroeffentlichung.veroeffentlichen()
    except Exception as e:
        raise HTTPException(502, str(e)[:300])


@app.get("/api/veroeffentlichen/vorschau")
def veroeffentlichen_vorschau(_=Depends(admin)):
    """Was hinausginge – die ersten Zeilen und die Größe.

    Vor dem ersten Mal will man sehen, was da wirklich veröffentlicht wird.
    Ein Blick auf drei Zeilen beantwortet das besser als jede Zusicherung.
    """
    text, anzahl = veroeffentlichung.index_bauen()
    return {"zeilen": anzahl, "bytes": len(text.encode("utf-8")),
            "felder": list(veroeffentlichung.OEFFENTLICH),
            "repo": veroeffentlichung.repo(),
            "bereit": veroeffentlichung.bereit(),
            "probe": text.split("\n")[:3]}


# ------------------------------------------------- Ausliefern an Instanzen


@app.get("/api/index")
def index_abholen(seit: int = 0, limit: int = 1000, token: str = "",
                  authorization: str = Header(default="")):
    """Den fertigen Abzug abholen – seitenweise, nach Änderungszeit.

    Eigener Token (`LESE_TOKEN`), nicht der Admin-Token: Eine Instanz soll
    lesen dürfen, ohne den Abzug steuern zu können. Er darf auch in der
    Adresse stehen – Instanzen holen server-zu-server, und ein Kopf ist dort
    manchmal umständlicher als ein Parameter.
    """
    erwartet = (os.environ.get("LESE_TOKEN") or "").strip()
    if not erwartet:
        raise HTTPException(503, "Kein LESE_TOKEN gesetzt")
    gegeben = (token or authorization.removeprefix("Bearer ")).strip()
    if gegeben != erwartet:
        raise HTTPException(401, "Token fehlt oder stimmt nicht")
    limit = max(1, min(int(limit), 2000))
    with db() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT item_no, item_type, name, such, category_id, jahr,"
            " img_url, farben, art, merkmale, updated_at FROM katalog_index"
            " WHERE updated_at > ? ORDER BY updated_at, item_no LIMIT ?",
            (int(seit), limit))]
        gesamt = conn.execute(
            "SELECT COUNT(*) AS n FROM katalog_index").fetchone()["n"]
    # `stand` ist der Zeitstempel der letzten gelieferten Zeile, nicht die
    # Uhrzeit: Sonst übersähe der nächste Abruf alles, was zwischen Abfrage
    # und Antwort geschrieben wurde.
    stand = rows[-1]["updated_at"] if rows else int(seit)
    return JSONResponse({"zeilen": rows, "stand": stand, "gesamt": gesamt,
                         "mehr": len(rows) == limit})
