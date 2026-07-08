# Brickfolio – Benutzerhandbuch

Dieses Handbuch erklärt alle Funktionen der App, sortiert nach den Tabs in
der unteren Leiste. Was du siehst, hängt von deiner Rolle ab:

- **Standard**: Sammlung verwalten – bewusst einfach gehalten.
- **Sammlerprofi** 💼: zusätzlich Kaufpreise, Gewinn, Einkaufs- und
  Verkaufslisten. Die Rolle vergibt der Admin (Mehr → Benutzer → „Profi").
- **Admin** 🔧: Benutzerverwaltung, API-Schlüssel, Sicherung.

---

## 📷 Scannen

1. **Foto aufnehmen** (Figur oder Set) oder unten **per Name/Nummer suchen**.
   Reine Nummern (z. B. `75154` oder `sw0815`) werden automatisch als Set
   *und* als Figur nachgeschlagen.
2. Aus der Kandidatenliste den richtigen Treffer wählen. Jede Karte zeigt
   Bild, BrickLink-Nummer, Jahr, Ø-Preise und – falls vorhanden – in welchen
   eurer Sets die Figur steckt.
3. Aktionen je Kandidat:
   - **＋ Zur Sammlung** – mit Zustandsabfrage (Gebraucht/Neu)
   - **☆ Merken** – auf die Wunschliste
   - **🛒 Liste** *(nur Profi)* – auf eine Einkaufsliste
4. **✏️ Manuell erfassen** für alles, was die Erkennung nicht kennt
   (eigene Nummern wie `manuell-…` sind erlaubt, bekommen aber keine Preise).

## 🗂 Sammlung

- **Suchen, sortieren, filtern** (Alle/Figuren/Sets); die Widgets oben zeigen
  Stückzahl und Gesamtwert des aktuellen Filters.
- Karte antippen für Details: Menge, Zustand, Notizen, **Preisverlauf** als
  Chart, „Preisverlauf ↗"-Link zu BrickLink.
- **Sets**: „👥 3/4" in der Infozeile zeigt, wie viele der enthaltenen
  Figuren ihr besitzt (✔ = komplett). In den Details listet
  „👥 Enthaltene Figuren" alle auf – mit Besitz-Badges und einem Knopf,
  der **alle fehlenden auf die Wunschliste** setzt.
- **Figuren** zeigen umgekehrt „📦 aus euren Sets" mit Sprung zur Set-Karte.
- *Profi:* Zeile **„Bezahlt [Betrag] € ⚙️/✏️"** – der Kaufpreis.
  ⚙️ = automatisch (BrickLink-Ø vom Erfassungstag), ✏️ = manuell.
  Darunter die Gewinnzeile: „Bezahlt … · Wert … · **±Differenz**".

## ⭐ Wünsche

- Gemerkte Artikel mit Ø-Preisen; Widgets zeigen die geschätzten
  Anschaffungskosten (gebraucht/neu).
- **✔ Gekauft!** fragt den Zustand ab (Profis können den echten Kaufpreis
  eintragen, leer = BrickLink-Ø) und verschiebt den Artikel in die Sammlung.
- Falsche Nummer? In den Details korrigieren („Setzen" / „🔍 Auto") –
  Preise werden danach automatisch neu geholt.

## 🛒 Listen *(Einkaufslisten)*

Der Tab erscheint für Standard-Benutzer nur, wenn eine aktive Liste
existiert. **Der typische Flohmarkt-Ablauf:**

1. *Profi:* Liste anlegen („Flohmarkt 12.7.").
2. Am Stand die Kiste durchscannen und per **🛒 Liste** befüllen – die
   Kopfzeile zeigt laufend den **Marktwert** (zustandsgerecht) und eure
   bisherigen Einkaufspreise. Zustand je Artikel per gelbem Umschalter.
3. Preis verhandeln: **💰 Gesamtangebot** zeigt den Ø-Marktwert und einen
   roten **Preisvorschlag** (60 % des Marktwerts, antippen übernimmt ihn).
   „Verteilen" legt den Gesamtpreis **anteilig nach Marktwert** auf die
   Artikel um – beliebig oft wiederholbar, einzelne Preise bleiben per Hand
   korrigierbar.
4. Zu Hause: **Jeder** (auch ohne Profi-Rolle) kann angekommene Artikel mit
   **„✔ Da! In die Sammlung"** verbuchen. Ist der Artikel schon vorhanden,
   fragt die App: **＋ Zusätzlich** (Menge erhöht, Einkaufspreis wird aus
   altem und neuem Preis gemittelt) oder **Überschreiben** (ersetzt den
   Eintrag komplett). Verbuchte Artikel werden ausgegraut.
5. Sind alle Artikel verbucht, wandert die Liste **automatisch ins Archiv** –
   nur Profis sehen es (📦-Umschalter) und können Verbuchungen rückgängig
   machen oder Listen von Hand archivieren/löschen.

**📋 Verkaufsliste (Doppelte)** *(nur Profi)*: erzeugt auf Knopfdruck die
Liste aller mehrfach vorhandenen Artikel – **„1 Exemplar bleibt immer,
Set-Figuren bleiben reserviert"** (wer 2× ein Set hat, dessen Figuren werden
2× zurückgehalten). Mit Ø-Stückpreis, Verkaufswert, CSV-Export und
Druckansicht als Preisliste für den eigenen Stand.

## 📊 Statistik

Für alle sichtbar: Kennzahlen (Stück, verschieden, Ø je Stück, Gesamtwert),
die **Wertentwicklung** der Sammlung (aus der täglichen Preisaufzeichnung –
die Kurve wächst mit der Zeit), Aufteilung nach Typ und Zustand, **Wert nach
Erscheinungsjahr** und die Top 10 nach Wert. *Profis* sehen zusätzlich
„bezahlt gesamt", „Gewinn" und die besten Wertsteigerungen.

## ⚙️ Mehr

- **Profil**: eigenes Passwort und Anzeigename ändern.
- **Export & Druck**: Sammlung und Wunschliste als CSV (Excel-tauglich,
  deutsche Zahlenformate) oder als aufgeräumte Druckliste.
- **Benutzer verwalten** *(Admin)*: anlegen, entfernen, Passwort
  zurücksetzen, **„Profi"-Rolle** per Knopf vergeben/entziehen
  (grün = aktiv, wirkt sofort).
- **API-Schlüssel** *(Admin)*: BrickLink- und Rebrickable-Keys.
- **Sicherung** *(Admin)*: 💾 lädt eine JSON-Datei mit *allem* herunter
  (Benutzer, Sammlung, Wünsche, Listen, Preisverläufe, Einstellungen);
  📥 spielt sie wieder ein – **ersetzt alle Daten** nach Rückfrage.
  Ideal vor Updates und für den Umzug auf einen neuen Server.

---

## Symbole auf einen Blick

| Symbol | Bedeutung |
|---|---|
| ⚙️ / ✏️ | Kaufpreis automatisch (BrickLink-Ø, Datum im Tooltip) / manuell |
| 👥 3/4 ✔ | 3 von 4 Set-Figuren vorhanden (✔ = komplett) |
| 📦 | „steckt in euren Sets" bzw. Archiv |
| ⭐ | steht auf der Wunschliste |
| ✔ (ausgegraut) | Listen-Artikel wurde in die Sammlung verbucht |

## Häufige Fragen

**Warum fehlen bei manchen Artikeln die Preise?** Manuelle Nummern
(`manuell-…`, `fig-…`) haben keine BrickLink-Entsprechung. Alles andere holt
die App im Hintergrund nach – einfach später wieder reinschauen.

**Ein Update ist eingespielt, aber nichts ändert sich?** Container neu
gebaut? (`docker compose up -d --build`). Danach reicht normales Neuladen –
die App verhindert veraltete Browser-Caches selbst.

**Wo liegt die Datenbank?** Im `data/`-Ordner neben der
`docker-compose.yml` (`brickfolio.db`). Datei kopieren = Backup.

**Kann Finn versehentlich etwas kaputt machen?** Ohne Profi-/Admin-Rolle
sieht er weder Kaufpreise noch Listen-Verwaltung noch Archiv – er kann
sammeln, wünschen und angekommene Artikel verbuchen. Und selbst dann gibt es
die Sicherung. 🙂
