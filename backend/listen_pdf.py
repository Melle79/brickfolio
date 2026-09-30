"""Eine Einkaufsliste als PDF – als Einkaufs- oder als Verkaufsliste.

**Warum auf dem Server und nicht über den Druckdialog.** Bis 3.2.0 druckte
die Oberfläche die Liste über `window.print()`. Am Rechner ging das, am
iPhone nicht gut: Safari kennt kein „Als PDF sichern“, man musste über die
Druckvorschau teilen, und die Seite rechnete Ränder und Skalierung selbst.
Ein fertiges PDF vom Server sieht überall gleich aus und lässt sich am
Telefon direkt teilen oder in Dateien sichern.

Zwei Fassungen:

- **Einkaufsliste** – alle Artikel mit Ø-Preis je Zustand, Summe,
  eingetragenem Einkaufspreis und einem Kästchen zum Abhaken.
- **Verkaufsliste** – für den, der kauft: nur die offenen Artikel, ein
  Preis je Stück (auf Wunsch ein Anteil vom Marktwert) und die Summe.
  **Nie mit Einkaufspreisen** – was man selbst bezahlt hat, geht den
  Käufer nichts an.

Die Schrift ist Nunito wie in der App, als feste Schnitte unter
`backend/fonts/` (aus den variablen woff2-Dateien der Oberfläche erzeugt;
SIL Open Font License, siehe `fonts/OFL.txt`).
"""
import os
import time

from fpdf import FPDF

SCHRIFTEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

TINTE = (29, 29, 27)
GEDAEMPFT = (107, 111, 118)
LINIE = (227, 229, 233)
STREIFEN = (246, 247, 249)
GELB = (255, 207, 0)
ROT = (208, 16, 18)
BLAU = (0, 85, 191)
GRUEN = (0, 133, 43)
GRAU_SCHILD = (233, 235, 239)

WAEHRUNG = {"EUR": "€", "USD": "$", "GBP": "£", "CHF": "CHF", "SEK": "kr",
            "DKK": "kr", "NOK": "kr", "PLN": "zł", "CZK": "Kč", "CAD": "CA$",
            "AUD": "A$", "JPY": "¥"}

TEXTE = {
    "de": {
        "einkauf": "Einkaufsliste", "verkauf": "Verkaufsliste",
        "artikel": "Artikel", "stueck": "Stück", "zustand": "Zustand",
        "menge": "Menge", "preis": "Preis", "ø_preis": "Ø Preis",
        "summe": "Summe", "einkauf_sp": "Einkauf", "gesamt": "Gesamt",
        "neu": "Neu", "gebraucht": "Gebraucht", "set": "Set",
        "figur": "Figur", "teil": "Teil",
        "k_wert": "Marktwert je Zustand", "k_preis": "Preis gesamt",
        "k_einkauf": "Einkauf eingetragen", "seite": "Seite {n} von {m}",
        "fuss_ek": "Ø Preis: durchschnittlicher BrickLink-Verkaufspreis der "
                   "letzten 6 Monate für den angegebenen Zustand, Stand {d}.",
        "fuss_vk": "Preise: durchschnittlicher BrickLink-Verkaufspreis der "
                   "letzten 6 Monate für den angegebenen Zustand, Stand {d}.",
        "fuss_vk_p": "Preise: {p} % des durchschnittlichen BrickLink-"
                     "Verkaufspreises der letzten 6 Monate für den "
                     "angegebenen Zustand, Stand {d}.",
    },
    "en": {
        "einkauf": "Shopping list", "verkauf": "Sales list",
        "artikel": "Items", "stueck": "Pieces", "zustand": "Condition",
        "menge": "Qty", "preis": "Price", "ø_preis": "Avg. price",
        "summe": "Total", "einkauf_sp": "Purchase", "gesamt": "Total",
        "neu": "New", "gebraucht": "Used", "set": "Set",
        "figur": "Minifigure", "teil": "Part",
        "k_wert": "Market value by condition", "k_preis": "Total price",
        "k_einkauf": "Purchase entered", "seite": "Page {n} of {m}",
        "fuss_ek": "Avg. price: average BrickLink sale price of the last "
                   "6 months for the stated condition, as of {d}.",
        "fuss_vk": "Prices: average BrickLink sale price of the last 6 "
                   "months for the stated condition, as of {d}.",
        "fuss_vk_p": "Prices: {p} % of the average BrickLink sale price of "
                     "the last 6 months for the stated condition, as of {d}.",
    },
}


def wert(item: dict) -> float:
    """Ø des eingetragenen Zustands, fehlt er, der andere – wie beim
    Gesamtangebot in der Oberfläche."""
    if item.get("condition") == "new":
        return item.get("price_new") or item.get("price_used") or 0
    return item.get("price_used") or item.get("price_new") or 0


def geld(betrag: float, waehrung: str, sprache: str) -> str:
    zeichen = WAEHRUNG.get(waehrung, waehrung)
    if sprache == "de":
        zahl = f"{betrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{zahl} {zeichen}"
    return f"{zeichen}{betrag:,.2f}" if len(zeichen) <= 2 else f"{betrag:,.2f} {zeichen}"


def dateiname(liste_name: str, art: str, sprache: str) -> str:
    """„Verkaufsliste AA Olli.pdf“ – ohne Zeichen, die ein Dateisystem stören."""
    sauber = "".join(c for c in liste_name if c not in '\\/:*?"<>|').strip() or "Liste"
    return f"{TEXTE[sprache][art]} {sauber}.pdf"


class _Pdf(FPDF):
    fusszeile = ""

    def footer(self):
        self.set_y(-11)
        self.set_font("Nunito", "", 7.5)
        self.set_text_color(*GEDAEMPFT)
        self.cell(0, 5, self.fusszeile.format(n=self.page_no(), m="{nb}"),
                  align="R")


def _schriften(pdf: FPDF) -> None:
    for stil, w in (("", "600"), ("B", "800"), ("I", "900")):
        # „I“ steht hier für den schwersten Schnitt: fpdf kennt nur R/B/I/BI,
        # kursiv braucht die Liste nicht.
        pdf.add_font("Nunito", stil, os.path.join(SCHRIFTEN, f"nunito-latin-{w}.ttf"))
        pdf.add_font("NunitoX", stil, os.path.join(SCHRIFTEN, f"nunito-latin-ext-{w}.ttf"))
    pdf.set_fallback_fonts(["NunitoX"], exact_match=False)


def _wortmarke(pdf: FPDF, x: float, y: float, groesse: float) -> None:
    """Nupp + Steinturm + o – wie in der App, der Turm aus vier Rechtecken."""
    pdf.set_font("Nunito", "I", groesse)
    pdf.set_text_color(*TINTE)
    em = groesse * 0.3528  # Punkt → mm
    grund = y + em * 0.78  # Grundlinie
    pdf.text(x, grund, "Nupp")
    x += pdf.get_string_width("Nupp") + em * 0.045
    breite, hoehe, luft = em * 0.48, em * 0.72, em * 0.022
    stein = (hoehe - 3 * luft) / 4
    oben = grund - hoehe
    for i, farbe in enumerate((GELB, ROT, BLAU, GRUEN)):
        pdf.set_fill_color(*farbe)
        pdf.rect(x, oben + i * (stein + luft), breite, stein, style="F",
                 round_corners=True, corner_radius=stein * 0.18)
    x += breite + em * 0.035
    pdf.text(x, grund, "o")


def erzeugen(liste: dict, items: list, art: str = "einkauf", prozent: float = 100,
             sprache: str = "de", waehrung: str = "EUR", absender: str = "",
             bild_fuer=None, profi: bool = True) -> bytes:
    """Das PDF als Bytes. `bild_fuer(item)` liefert einen Dateipfad zum
    Artikelbild oder None; `profi` entscheidet, ob Einkaufspreise
    überhaupt in Frage kommen."""
    T = TEXTE.get(sprache, TEXTE["de"])
    sprache = sprache if sprache in TEXTE else "de"
    verkauf = art == "verkauf"
    anteil = max(1.0, min(1000.0, float(prozent or 100))) / 100
    zeilen = [i for i in items if not (verkauf and i.get("done"))]
    zeige_ek = profi and not verkauf

    pdf = _Pdf(format="A4", unit="mm")
    pdf.set_title(f"{T[art]} {liste.get('name', '')}")
    pdf.set_creator("Nupplo SE")
    pdf.fusszeile = T["seite"]
    pdf.alias_nb_pages()
    _schriften(pdf)
    pdf.set_margins(12, 14, 12)
    pdf.set_auto_page_break(False)
    pdf.add_page()
    breite = pdf.w - 24
    links = 12

    # ---- Kopf
    _wortmarke(pdf, links, 13, 26)
    pdf.set_font("Nunito", "I", 17)
    pdf.set_text_color(*TINTE)
    pdf.set_xy(links + 60, 13)
    pdf.cell(breite - 60, 8, liste.get("name", ""), align="R")
    heute = time.strftime("%d.%m.%Y") if sprache == "de" else time.strftime("%Y-%m-%d")
    unter = " · ".join(t for t in (T[art], absender, heute) if t)
    pdf.set_font("Nunito", "", 8.5)
    pdf.set_text_color(*GEDAEMPFT)
    pdf.set_xy(links + 60, 21)
    pdf.cell(breite - 60, 5, unter, align="R")
    pdf.set_fill_color(*GELB)
    pdf.rect(links, 28, breite, 1, style="F")

    # ---- Beträge
    def stueckpreis(i):
        w = wert(i)
        return round(w * anteil, 2) if verkauf else w

    summe = sum(stueckpreis(i) * (i.get("qty") or 1) for i in zeilen)
    stueck = sum(i.get("qty") or 1 for i in zeilen)
    eingekauft = sum(i.get("paid_price") or 0 for i in zeilen) if zeige_ek else 0

    # ---- Kacheln
    kacheln = [(str(len(zeilen)), T["artikel"]), (str(stueck), T["stueck"]),
               (geld(summe, waehrung, sprache), T["k_preis"] if verkauf else T["k_wert"])]
    if zeige_ek:
        kacheln.append((geld(eingekauft, waehrung, sprache) if eingekauft else "–",
                        T["k_einkauf"]))
    luft = 3
    kb = (breite - luft * (len(kacheln) - 1)) / len(kacheln)
    for n, (zahl, text) in enumerate(kacheln):
        x = links + n * (kb + luft)
        pdf.set_draw_color(*TINTE)
        pdf.set_line_width(0.45)
        pdf.rect(x, 33, kb, 15, style="D", round_corners=True, corner_radius=3)
        pdf.set_xy(x, 34.5)
        pdf.set_font("Nunito", "I", 13)
        pdf.set_text_color(*TINTE)
        pdf.cell(kb, 7, zahl, align="C")
        pdf.set_xy(x, 41.5)
        pdf.set_font("Nunito", "", 7.5)
        pdf.set_text_color(*GEDAEMPFT)
        pdf.cell(kb, 4, text, align="C")

    # ---- Tabelle
    sp = {"nr": 7, "bild": 13, "zust": 20, "menge": 12, "preis": 19,
          "summe": 21, "ek": 18 if zeige_ek else 0, "haken": 7 if not verkauf else 0}
    sp["name"] = breite - sum(sp.values())
    reihe = ["nr", "bild", "name", "zust", "menge", "preis", "summe"]
    if zeige_ek:
        reihe.append("ek")
    if not verkauf:
        reihe.append("haken")
    kopf = {"nr": "#", "bild": "", "name": T["artikel"], "zust": T["zustand"],
            "menge": T["menge"], "preis": T["preis"] if verkauf else T["ø_preis"],
            "summe": T["summe"], "ek": T["einkauf_sp"], "haken": ""}
    rechts = {"nr", "menge", "preis", "summe", "ek"}

    def spalte_x(name):
        x = links
        for s in reihe:
            if s == name:
                return x
            x += sp[s]
        return x

    def tabellenkopf(y):
        pdf.set_font("Nunito", "B", 7)
        pdf.set_text_color(*GEDAEMPFT)
        for s in reihe:
            pdf.set_xy(spalte_x(s) + (0.5 if s not in rechts else 0), y)
            pdf.cell(sp[s] - 1, 5, kopf[s].upper(), align="R" if s in rechts else "L")
        pdf.set_draw_color(*TINTE)
        pdf.set_line_width(0.4)
        pdf.line(links, y + 6, links + breite, y + 6)
        return y + 7

    y = tabellenkopf(52)
    unten = pdf.h - 18
    for n, i in enumerate(zeilen, 1):
        pdf.set_font("Nunito", "B", 9)
        name_zeilen = pdf.multi_cell(sp["name"] - 2, 4.2, i.get("name") or "",
                                     dry_run=True, output="LINES")
        hoehe = max(13, 4.2 * len(name_zeilen) + 6.5)
        if y + hoehe > unten:
            pdf.add_page()
            y = tabellenkopf(14)
        if n % 2 == 0:
            pdf.set_fill_color(*STREIFEN)
            pdf.rect(links, y, breite, hoehe, style="F")
        mitte = y + hoehe / 2
        q = i.get("qty") or 1
        preis = stueckpreis(i)
        erledigt = bool(i.get("done")) and not verkauf
        # Nummer
        pdf.set_font("Nunito", "", 7.5)
        pdf.set_text_color(*GEDAEMPFT)
        pdf.set_xy(spalte_x("nr"), mitte - 2.5)
        pdf.cell(sp["nr"] - 1.5, 5, str(n), align="R")
        # Bild
        pfad = bild_fuer(i) if bild_fuer else None
        if pfad:
            try:
                pdf.image(pfad, x=spalte_x("bild") + 1, y=mitte - 5.25, w=10.5, h=10.5,
                          keep_aspect_ratio=True)
            except Exception:
                pass
        # Name und Nummer
        pdf.set_font("Nunito", "B", 9)
        pdf.set_text_color(*(GEDAEMPFT if erledigt else TINTE))
        ny = mitte - (4.2 * len(name_zeilen) + 3.8) / 2
        for k, zeile in enumerate(name_zeilen):
            pdf.set_xy(spalte_x("name") + 0.5, ny + k * 4.2)
            pdf.cell(sp["name"] - 2, 4.2, zeile)
            if erledigt:
                w = pdf.get_string_width(zeile)
                pdf.set_draw_color(*GEDAEMPFT)
                pdf.set_line_width(0.25)
                pdf.line(spalte_x("name") + 1.5, ny + k * 4.2 + 2.2,
                         spalte_x("name") + 1.5 + w, ny + k * 4.2 + 2.2)
        typ = {"set": T["set"], "minifig": T["figur"]}.get(i.get("item_type"), T["teil"])
        pdf.set_font("Nunito", "", 7.5)
        pdf.set_text_color(*GEDAEMPFT)
        pdf.set_xy(spalte_x("name") + 0.5, ny + 4.2 * len(name_zeilen))
        pdf.cell(sp["name"] - 2, 3.8, f"{i.get('item_id', '')} · {typ}")
        # Zustand als Schild
        neu = i.get("condition") == "new"
        text = T["neu"] if neu else T["gebraucht"]
        pdf.set_font("Nunito", "B", 7)
        sw = pdf.get_string_width(text) + 4
        pdf.set_fill_color(*(GELB if neu else GRAU_SCHILD))
        pdf.rect(spalte_x("zust") + 0.5, mitte - 2.2, sw, 4.4, style="F",
                 round_corners=True, corner_radius=2.2)
        pdf.set_text_color(*TINTE)
        pdf.set_xy(spalte_x("zust") + 0.5, mitte - 2.2)
        pdf.cell(sw, 4.4, text, align="C")
        # Zahlen
        pdf.set_font("Nunito", "", 8.5)
        pdf.set_text_color(*TINTE)
        for s, t in (("menge", f"{q}×"),
                     ("preis", geld(preis, waehrung, sprache) if preis else "–")):
            pdf.set_xy(spalte_x(s), mitte - 2.5)
            pdf.cell(sp[s] - 1.5, 5, t, align="R")
        pdf.set_font("Nunito", "I", 8.5)
        pdf.set_xy(spalte_x("summe"), mitte - 2.5)
        pdf.cell(sp["summe"] - 1.5, 5, geld(preis * q, waehrung, sprache) if preis else "–",
                 align="R")
        if zeige_ek:
            pdf.set_font("Nunito", "", 8.5)
            pdf.set_xy(spalte_x("ek"), mitte - 2.5)
            bezahlt = i.get("paid_price")
            pdf.cell(sp["ek"] - 1.5, 5, geld(bezahlt, waehrung, sprache)
                     if bezahlt is not None else "", align="R")
        if not verkauf:
            hx, hk = spalte_x("haken") + 1.5, 3.6
            pdf.set_draw_color(*TINTE)
            pdf.set_line_width(0.35)
            pdf.rect(hx, mitte - hk / 2, hk, hk, style="D", round_corners=True,
                     corner_radius=0.8)
            if i.get("done"):
                pdf.set_line_width(0.5)
                pdf.line(hx + 0.7, mitte, hx + 1.5, mitte + 0.9)
                pdf.line(hx + 1.5, mitte + 0.9, hx + 3.0, mitte - 1.0)
        pdf.set_draw_color(*LINIE)
        pdf.set_line_width(0.2)
        pdf.line(links, y + hoehe, links + breite, y + hoehe)
        y += hoehe

    # ---- Summe
    if y + 16 > unten:
        pdf.add_page()
        y = 14
    pdf.set_draw_color(*TINTE)
    pdf.set_line_width(0.4)
    pdf.line(links, y, links + breite, y)
    pdf.set_font("Nunito", "I", 9.5)
    pdf.set_text_color(*TINTE)
    pdf.set_xy(spalte_x("name") + 0.5, y + 1.5)
    pdf.cell(sp["name"], 6, T["gesamt"])
    pdf.set_xy(spalte_x("menge"), y + 1.5)
    pdf.cell(sp["menge"] - 1.5, 6, f"{stueck}×", align="R")
    pdf.set_xy(spalte_x("summe"), y + 1.5)
    pdf.cell(sp["summe"] - 1.5, 6, geld(summe, waehrung, sprache), align="R")
    if zeige_ek and eingekauft:
        pdf.set_xy(spalte_x("ek"), y + 1.5)
        pdf.cell(sp["ek"] - 1.5, 6, geld(eingekauft, waehrung, sprache), align="R")

    # ---- Woher die Preise kommen
    if verkauf and round(anteil * 100) != 100:
        fuss = T["fuss_vk_p"].format(p=round(anteil * 100), d=heute)
    else:
        fuss = T["fuss_vk" if verkauf else "fuss_ek"].format(d=heute)
    pdf.set_font("Nunito", "", 7.5)
    pdf.set_text_color(*GEDAEMPFT)
    pdf.set_xy(links, y + 10)
    pdf.multi_cell(breite, 3.6, fuss)
    return bytes(pdf.output())
