"""Den Index nach GitHub schieben – **nur, was uns gehört**.

Veröffentlicht werden die BrickLink-**Nummer** und unsere eigene
Bildbeschreibung. Nicht veröffentlicht werden Name, Jahr, Kategorie und
Bildadresse: Das ist BrickLinks Inhalt, und dessen Weitergabe an Dritte
untersagen deren Nutzungsbedingungen ausdrücklich (nachgelesen 21.08.2026:
„not to distribute, disclose, upload, or transfer to any third party any
content or data you receive from or which is displayed on the Site").

Was übrig bleibt, ist etwas anderes: eine Nummer als Kennung und ein Text,
den ein Sehmodell bei uns über ein Foto geschrieben hat. Den Namen holt sich
jede Installation über ihren **eigenen** BrickLink-Token – ohne den tut eine
Brickfolio-Installation ohnehin nichts.

Format: NDJSON, eine Zeile je Figur, nach Nummer sortiert. Nicht aus
Schönheit, sondern wegen der Diffs: Bei einer einzigen Datei mit 9.741
Einträgen zeigt ein Commit dann genau die Zeilen, die sich geändert haben –
und nicht die ganze Datei. Git komprimiert den Rest selbst.
"""
import base64
import json
import os

import requests

from katalog import db, konfig

USER_AGENT = "Brickfolio-Katalogdienst"

# Was hinaus darf. Diese Liste ist die eigentliche Zusicherung dieser Datei –
# wer sie erweitert, muss vorher wissen, wem das Feld gehört.
OEFFENTLICH = ("item_no", "art", "farben", "merkmale", "modell")


def repo():
    return (konfig("GITHUB_REPO") or "").strip()


def bereit():
    return bool(repo() and konfig("GITHUB_TOKEN"))


def index_bauen():
    """Die zu veröffentlichende Datei als Text – und wie viele Zeilen.

    Figuren ohne Beschreibung bleiben draußen: Eine Zeile, die nur aus einer
    Nummer besteht, hilft niemandem beim Suchen und bläht die Datei auf.
    """
    zeilen = []
    with db() as conn:
        for r in conn.execute(
                "SELECT item_no, art, farben, merkmale, modell"
                " FROM katalog_index"
                " WHERE merkmale NOT IN ('', '–')"
                " ORDER BY item_no"):
            d = {k: r[k] for k in OEFFENTLICH if r[k]}
            # `ensure_ascii=False`, damit Umlaute lesbar bleiben; die Datei
            # soll man im Browser aufmachen und verstehen können.
            zeilen.append(json.dumps(d, ensure_ascii=False, sort_keys=True))
    return "\n".join(zeilen) + "\n", len(zeilen)


def repo_abfragen():
    """Gibt es das Repo, und dürfen wir hinein? Für die Verbindungsprüfung.

    Eigene Funktion, weil `_github` einen Pfad anhängt – mit leerem Pfad
    entstünde `.../repos/x/y/` mit Schrägstrich am Ende, und darauf
    antwortet GitHub mit 404, auch wenn es das Repo gibt.
    """
    return requests.get(
        "https://api.github.com/repos/%s" % repo(),
        headers={"Authorization": "Bearer " + konfig("GITHUB_TOKEN"),
                 "Accept": "application/vnd.github+json",
                 "User-Agent": USER_AGENT}, timeout=30)


def _github(methode, pfad, **kw):
    r = requests.request(
        methode, "https://api.github.com/repos/%s/%s" % (repo(), pfad),
        headers={"Authorization": "Bearer " + konfig("GITHUB_TOKEN"),
                 "Accept": "application/vnd.github+json",
                 "User-Agent": USER_AGENT},
        timeout=60, **kw)
    return r


def veroeffentlichen(nachricht=""):
    """Die Datei hochladen. Gibt zurück, was passiert ist."""
    if not bereit():
        raise RuntimeError("GITHUB_REPO oder GITHUB_TOKEN fehlt")
    pfad = (konfig("GITHUB_PFAD") or "index.ndjson").strip("/")
    zweig = (konfig("GITHUB_BRANCH") or "main").strip()

    text, anzahl = index_bauen()
    if not anzahl:
        return {"geschrieben": 0, "grund": "nichts zu veröffentlichen"}

    # Den bisherigen Stand holen – GitHub verlangt beim Überschreiben den
    # `sha` der Datei, und ohne Vergleich schöben wir bei jedem Lauf einen
    # leeren Commit hoch.
    alt = _github("GET", "contents/%s?ref=%s" % (pfad, zweig))
    sha = None
    if alt.status_code == 200:
        d = alt.json()
        sha = d.get("sha")
        try:
            vorher = base64.b64decode(d.get("content") or "").decode("utf-8")
            if vorher == text:
                return {"geschrieben": 0, "zeilen": anzahl,
                        "grund": "unverändert"}
        except Exception:
            pass                     # nicht entscheidbar – dann eben schreiben
    elif alt.status_code != 404:
        raise RuntimeError("GitHub antwortet mit %s" % alt.status_code)

    body = {
        "message": nachricht or ("Katalog-Index: %d Figuren" % anzahl),
        "content": base64.b64encode(text.encode("utf-8")).decode(),
        "branch": zweig,
    }
    if sha:
        body["sha"] = sha
    r = _github("PUT", "contents/%s" % pfad, json=body)
    if r.status_code not in (200, 201):
        raise RuntimeError("GitHub antwortet mit %s: %s"
                           % (r.status_code, r.text[:200]))
    d = r.json()
    return {"geschrieben": anzahl, "zeilen": anzahl,
            "bytes": len(text.encode("utf-8")),
            "commit": (d.get("commit") or {}).get("sha", "")[:8],
            "url": "https://raw.githubusercontent.com/%s/%s/%s"
                   % (repo(), zweig, pfad)}
