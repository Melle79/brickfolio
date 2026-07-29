# Changelog

## 1.68.3 – Juli 2026

### Behoben
- 📷 **Das eigene Foto war in der Vorschau nie zu sehen.** Sie zeigt das
  gerade aufgenommene oder hereingezogene Bild als `blob:` aus dem
  Arbeitsspeicher, noch bevor es hochgeladen ist – und genau dieses Schema
  fehlte in den Sicherheits-Regeln. Der Browser blockierte also ausgerechnet
  das Bild, das man selbst ausgewählt hatte, und es blieb beim Platzhalter.
  Aufgefallen ist es, weil der Fehlerbericht seit 1.60.2 blockierte Inhalte
  meldet: „Vom Browser blockiert: img-src → blob"

### Vorbeugend
- 🧪 **Ein Test leitet aus dem Quelltext ab, welche Schemata die Oberfläche
  benutzt**, und prüft, ob die Regeln dazu passen – statt eine feste Liste
  abzuhaken. Das ist der vierte Fall dieser Art (Katalogbilder, Bild-Ersatz,
  Design-Setzen, jetzt die Vorschau); eine Liste, die jemand pflegen muss,
  hätte ihn wieder nicht gefunden

## 1.68.2 – Juli 2026

### Behoben
- 🎨 **Der Scan-Knopf war in Nova die Warnfarbe.** Er nutzt `--red` – im
  hellen Design das LEGO-Rot, und dort sieht er auch genau richtig aus. In
  Nova ist Rot aber die Farbe für Löschen und Verlust. Der wichtigste Knopf
  der App stand damit als große pinke Fläche da und las sich wie eine
  Fehlermeldung. Jetzt in der Akzentfarbe des Designs, mit dunkler Schrift
  wie auf allen anderen hellen Flächen dort, einem leichten Verlauf und
  passenden Noppen. Klassisch und Galaxie bleiben unverändert rot

## 1.68.1 – Juli 2026

### Verbessert
- 🏷 **Der Hub sagt jetzt, welcher Stand läuft.** Bisher hatte der Worker
  keine Versionsnummer – nach einem Deploy war nirgends abzulesen, ob der
  neue Code tatsächlich oben ist. Die Zahl in der Admin-Konsole ist deren
  **eigene** und steht nur zufällig neben „Hub-Admin", was leicht zu
  verwechseln ist. `/v1/health` und `/v1/me` nennen den Hub-Stand jetzt
  ausdrücklich (`version` bzw. `hub_version`), beginnend bei **1.4.0**

## 1.68.0 – Juli 2026

Zweiter Teil der Durchsicht: der Hub und der Weg dorthin. Ein struktureller
Fund, zwei kleinere.

### Sicherheit
- 🔐 **Der Hub verteilt die Verschlüsselungs-Schlüssel – und konnte damit
  dazwischengehen.** Die Nachrichten sind Ende-zu-Ende verschlüsselt, aber
  verschlüsselt wird mit dem Schlüssel, den der Hub liefert. Wer ihn
  kontrolliert, hätte statt des echten einen eigenen ausliefern und
  mitlesen können, ohne dass es auffällt. Keine Hintertür im Programm, aber
  die Stelle, an der man dem Hub vertrauen musste. Dagegen jetzt:
  - **Die Instanz merkt sich jeden Schlüssel beim ersten Mal.** Taucht später
    ein anderer auf, wird **nichts verschickt**, sondern abgebrochen. Ein
    Wechsel kann harmlos sein – unterscheiden lässt es sich nur durch
    Nachfragen; danach bestätigt ein Admin den neuen Schlüssel
  - **Sicherheitsnummer zum Vergleichen** im Gespräch: zwei kurze Zahlenreihen,
    einmal am Telefon vorgelesen. Stimmen sie, ist niemand dazwischen
- 🎟 **Ein Einladungscode konnte doppelt eingelöst werden.** Prüfen und
  Einlösen waren zwei Schritte – zwei gleichzeitige Anmeldungen mit demselben
  Code kamen beide durch. Jetzt ein einziger Schritt, und wer verliert, wird
  gar nicht erst angelegt
- 🤐 **Der Hub verriet bei einem internen Fehler dessen Wortlaut.** Solche
  Texte können Tabellennamen oder Abfragen enthalten. Sie stehen jetzt nur
  noch im Worker-Protokoll, das der Hub-Admin sieht

### Geprüft und in Ordnung
- **Zugriff auf fremde Vorgänge**: Jeder Nachrichten- und Löschzugriff prüft,
  ob man überhaupt beteiligt ist
- **Token** sind 192 Bit Zufall und liegen nur als SHA-256 im Hub
- **SQL im Worker** läuft durchgehend über gebundene Parameter
- **Keine Rechte-Erhöhung**: Der Endpunkt zum Ändern des eigenen Profils fasst
  nur den Anzeigenamen an – „Admin" lässt sich nicht mitschicken
- **Was der Hub überhaupt sieht**: veröffentlichte Angebote (Nummer, Name,
  Zustand, Menge, Vorschaubild) und Vorgangsdaten. Sammlung, Preise, Notizen
  und Einkaufslisten bleiben zu Hause

### Offen
- **Keine Ratenbremse im Hub.** Für ein Netzwerk unter Bekannten mit
  Einladungspflicht vertretbar; wächst es, gehört das nachgezogen

## 1.67.0 – Juli 2026

Ergebnis einer systematischen Durchsicht: alle 129 Endpunkte und ihre Rechte,
SQL, Dateipfade, XSS (mit vergifteten Daten in jedem Feld), der Update-Weg,
die Sitzungslogik. Zwei echte Lücken, beide behoben.

### Sicherheit
- 🔐 **Ein Passwortwechsel beendet jetzt alle bisherigen Sitzungen.** Bisher
  blieb ein einmal ausgestelltes Token **90 Tage** gültig – auch nach einem
  Passwortwechsel. Wer sein Passwort änderte, weil ein Gerät abhandengekommen
  war, sperrte es damit *nicht* aus. Jetzt zählt jeder Wechsel einen Stand
  hoch, den jedes Token mitführt; das eigene Gerät bekommt eine frische
  Sitzung und bleibt drin. Dasselbe beim Zurücksetzen durch einen Admin und
  beim Abnehmen des zweiten Faktors – gerade dort ist es der Sinn der Sache
- 🤐 **Fehlermeldungen kannten nur die Hälfte der Geheimnisse.** Entfernt
  wurden bisher nur die API-Schlüssel und der GitHub-Token. **Hub-Zugang,
  privater Hub-Schlüssel und Push-Schlüssel wären stehen geblieben** – und
  eine Fehlermeldung kann per Knopfdruck ein **öffentliches** GitHub-Issue
  werden. Jetzt gibt es eine Liste, und ein Test schlägt an, sobald eine neue
  Einstellung dazukommt, die niemand eingeordnet hat
- 🧪 12 neue Tests dafür, unter anderem: alte Token ohne Zählerstand bleiben
  gültig (niemand wird durch das Update ausgeloggt)

### Geprüft und in Ordnung
- **Rechte** kommen bei jeder Anfrage frisch aus der Datenbank – Entzug und
  Löschen wirken sofort, nicht erst mit Ablauf der Sitzung
- **SQL**: Werte laufen ausnahmslos über Platzhalter; wo Tabellennamen
  eingesetzt werden, stammen sie aus festen Listen im Code
- **Dateipfade**: Uploads über eine strenge Namensprüfung, Sicherungen gegen
  eine Positivliste, Katalogbilder über einen Hash – kein Weg nach oben
- **XSS**: mit Schadcode in Artikelnamen, Notizen, Listennamen, Benutzernamen,
  Fehlermeldungen und Hinweisen durchgespielt und in allen Ansichten
  nachgemessen – nichts wurde ausgeführt, nichts als Markup eingeschleust
- **Der Update-Helfer** liest aus der Markierungsdatei nur eine Zahl und führt
  ein festes Skript aus. Selbst wer die Datei schreiben könnte, bekäme keinen
  eigenen Befehl ausgeführt
- **Keine CORS-Freigabe**, Sitzung im Header statt im Cookie – damit ist die
  klassische Cross-Site-Anfrage kein Thema

## 1.66.2 – Juli 2026

### Behoben
- 🎨 **Die Themenkarten hatten in Galaxy und Nova einen dicken hellen Rahmen.**
  Sie fehlten in der Liste der Flächen, die in den dunklen Designs anders
  aussehen – und griffen deshalb auf die 2px-Kante des hellen Designs zurück,
  die dort aus der Textfarbe gebildet wird und damit fast weiß ist. Jetzt
  gleichen sie den Kacheln darüber
- 📕 **Die zugeklappte Karte „Fehlerbericht" zeigte die Benachrichtigung
  trotzdem.** Der Kasten trug `display:block` als Inline-Stil, und der schlägt
  jede Regel aus dem Stylesheet – auch die fürs Zuklappen. Als Klasse verliert
  er diesen Wettstreit und verschwindet mit

## 1.66.1 – Juli 2026

### Behoben
- 🏷 **Neue Sets und Teile bekommen ihr Thema jetzt von selbst** ([#13]).
  Bisher blieb es leer, bis jemand *Themen nachladen* drückte – wer das nicht
  wusste, sammelte nach und nach Einträge unter „Ohne Thema". Der Abruf läuft
  im Hintergrund, hält also das Erfassen nicht auf. Bei Sets zusätzlich noch
  einmal, sobald die Set-Inhalte da sind: Erst dann kann der Rückfall über
  die Figuren greifen. Ein von Hand gesetztes Thema wird nie überschrieben
- 🖼 **Ein Aussetzer beim CDN wird einmal nachgefasst** ([#12]). Ein einzelner
  Netzhänger ließ das Vorschaubild sonst als Platzhalter stehen, bis jemand
  die Seite neu lud
- 🔕 **Ein Bild, das nicht lädt, ist kein Fehler mehr.** Als die Bilder noch
  direkt vom CDN kamen, war die Meldung berechtigt. Seit sie über die eigene
  Instanz laufen, heißt ein Fehlschlag nur: Das CDN hat gerade nicht
  geantwortet. Gemeldet wurde es trotzdem – bis hin zu einem GitHub-Issue und
  einer Meldung aufs Handy, für ein einziges hakeliges Vorschaubild. Vom
  Browser **blockierte** Inhalte werden weiterhin gemeldet

[#12]: https://github.com/Melle79/brickfolio/issues/12
[#13]: https://github.com/Melle79/brickfolio/issues/13

## 1.66.0 – Juli 2026

### Neu
- 🔔 **Benachrichtigung aufs Gerät bei neuen Fehlern.** Web-Push **von der
  eigenen Instanz** – einzuschalten je Gerät unter *Mehr → Wartung →
  Fehlerbericht*. Damit erfährt man von einem Fehler auch, wenn Brickfolio
  gerade zu ist
- 🧪 **Probemeldung senden**, damit sich eine klemmende Zustellung nicht erst
  beim echten Fehler zeigt

### Bewusst so gebaut
- 🔑 **Die Schlüssel entstehen auf eurem Server** und bleiben dort; der
  private Teil verlässt ihn nie. Ein Test wacht darüber, dass er in keiner
  Antwort auftaucht
- 🤐 **Die Meldung sagt nur, *dass* etwas war** – kein Fehlertext, keine
  Nummer, nichts aus der Sammlung. Zustellen muss der Push-Dienst des
  Browser-Herstellers, anders geht Web-Push nicht; der Inhalt ist dabei
  verschlüsselt, aber was gar nicht drinsteht, kann auch nicht auffallen
- 🚫 **Der Tausch-Hub ist nicht beteiligt.** Fehler sind Sache dieser
  Instanz. Sie an einen Dienst zu schicken, den jemand anderes betreibt,
  wäre genau die Telemetrie, die es hier nicht geben soll
- 🧹 Abonnements, die ins Leere zeigen (App neu installiert), räumt der
  Server beim nächsten Versand selbst weg – ein Aussetzer beim Push-Dienst
  trägt dagegen **kein** Gerät aus

### Voraussetzungen
- **https** (Cloudflare-Tunnel oder eigenes Zertifikat) – über `http` im
  Heimnetz erlauben Browser keine Benachrichtigungen
- Auf dem iPhone die **auf dem Startbildschirm installierte** App
- Neue Abhängigkeit `pywebpush`; fehlt sie, bleibt die Karte einfach aus

## 1.65.0 – Juli 2026

### Neu
- 🔔 **Ein neuer Fehler hinterlässt einen Zettel auf der Startseite.** Bisher
  füllte sich das Protokoll still – man musste von sich aus nachsehen. Jetzt
  steht dort, dass etwas aufgezeichnet wurde, mitsamt der Meldung und einem
  Knopf **Fehlerbericht öffnen**, der direkt zur passenden Karte springt und
  sie aufklappt
- 🙈 **Höchstens ein Zettel gleichzeitig.** Ein Problem löst oft mehrere
  verschiedene Fehler aus; zehn Karten übereinander helfen niemandem. Ist der
  eine weggeklickt, meldet sich der nächste **neue** Fehler wieder –
  derselbe zum zweiten Mal nicht
- 👑 **Nur Admins sehen ihn.** Der Fehlerbericht liegt in einer Admin-Karte,
  ein Zettel dorthin wäre für alle anderen eine Sackgasse

## 1.64.2 – Juli 2026

### Verbessert
- 🔑 **Liegt ein Token, verschwindet das Eingabefeld.** Es stand sonst leer da
  und lud dazu ein, aus Versehen zu überschreiben. Stattdessen stehen dort
  jetzt drei Knöpfe: **Token prüfen**, **Ersetzen** (holt das Feld zurück,
  ohne den alten zu löschen) und **Token entfernen**
- ⚠️ Das Entfernen fragt nach – GitHub zeigt einen Token **kein zweites Mal**,
  wer ihn hier löscht, braucht sonst einen neuen

## 1.64.1 – Juli 2026

### Verbessert
- 🔑 **Beim GitHub-Token sieht man jetzt, ob einer liegt.** Bisher war das nur
  daran zu erkennen, dass der Melden-Knopf an einem Fehler auftauchte – und
  der taucht erst auf, wenn es überhaupt einen Fehler gibt. Jetzt steht über
  dem Feld „Gespeichert: …9999" oder „Kein Token hinterlegt"
- ✅ **Neuer Knopf „Token prüfen".** Er fragt GitHub, ob der Token gültig ist
  und das Repository sehen darf, und sagt beim Scheitern, *woran* es liegt:
  abgelaufen, oder gültig aber Repository nicht freigegeben. Ob er auch
  schreiben darf, prüft GitHub erst beim Schreiben – das sagt die Antwort
  ausdrücklich, statt eine Sicherheit vorzugeben, die sie nicht hat

## 1.64.0 – Juli 2026

### Verbessert
- ⚙️ **Der Mehr-Tab ist sortiert.** 17 Karten lagen in einer flachen Liste,
  und die Sortierung der Sammlung saß mitten zwischen Admin-Sachen. Jetzt
  stehen sie in vier Gruppen, geordnet danach, **wen es angeht**:
  🙋 Für dich · 🏠 Diese Instanz · 🌐 Nach außen · 🛠 Wartung. Quellen &
  Rechtliches bleibt ohne Gruppe ganz unten
- 🙈 **Leere Gruppen verschwinden mitsamt ihrer Überschrift.** Ein normaler
  Benutzer sieht damit nur „Für dich" und die Quellen – statt dreier
  Zwischenzeilen ohne Inhalt darunter

## 1.63.2 – Juli 2026

### Behoben
- 🔎 **Ein klemmendes Katalogbild meldete die falsche Adresse.** Seit die
  Bilder über die eigene Instanz laufen, stand im Fehlerbericht deren Name –
  als wäre der eigene Server kaputt. Gemeldet wird jetzt der Host dahinter,
  also der, der wirklich nicht antwortet

## 1.63.1 – Juli 2026

### Behoben
- 🏷 **Der Rückfall über die Figuren lief nur mit BrickLink-Schlüsseln.** Er
  stand innerhalb der Schlüssel-Prüfung – dabei braucht er gar keinen Abruf:
  Die Set-Inhalte liegen längst in der eigenen Datenbank. Fehlten oder
  versagten die Schlüssel, blieb ein Set also ohne Thema, obwohl die Antwort
  die ganze Zeit im Haus war

### Verbessert
- 🔎 **Der Knopf „Themen nachladen" steht jetzt auch dort, wo die Lücke
  auffällt** – direkt in der Gruppe „Ohne Thema" in der Sammlung. Bisher lag
  er unter *Mehr → Sortierung*, also weit weg vom Problem
- 🔎 Bleibt danach etwas übrig, **nennt die App die Nummern**, statt nur „lässt
  sich nicht bestimmen" zu melden. Die Rückmeldung kommt zusätzlich als
  Meldung, damit sie auch aus der Sammlung heraus zu sehen ist

## 1.63.0 – Juli 2026

### Behoben
- 🏷 **Einzelne Sets standen unter „Ohne Thema", obwohl BrickLink sie eindeutig
  führt.** Das Thema eines Sets kommt aus der BrickLink-Kategorie – und deren
  ID taucht nicht immer in BrickLinks eigener Kategorieliste auf. Dann bleibt
  die Kette gleich am ersten Glied stehen. Jetzt fragt die App in diesem Fall
  die **Figuren im Set**: Stecken dort `sw…`-Nummern drin, ist es Star Wars.
  Es zählt, was am häufigsten vorkommt
- 🔎 Das Nachziehen sagt jetzt auch, **welche** Nummern sich weigern. Vorher
  stand dort auf Dauer „1 Eintrag offen", ohne dass jemand erfuhr, welcher

### Verbessert
- 📈 **Die Diagramme sind gewachsen.** Bisher standen Blau und Grün fest im
  Code – in den dunklen Designs sahen die Kurven deshalb aus wie
  hineinkopiert. Jetzt gehören sie zum Design: In Nova zeichnen sie in Cyan
  und Mint, in Galaxy in dessen Blau und Grün, im hellen wie gehabt. Dazu
  weiche Flächen unter den Kurven, runde Linienenden, eine zurückhaltende
  Hilfslinie auf halber Höhe statt eines harten Rahmens und Punkte mit einem
  Ring in der Flächenfarbe
- ✨ **Das Popup in Nova hat Tiefe bekommen.** Drei Schichten statt einer
  flachen Fläche: eine tiefe Grundfarbe, ein Lichtschimmer an der oberen
  Kante und ein leiser Farbhauch im Akzent. Der Hintergrund dahinter tritt
  stärker zurück (mehr Unschärfe), damit das Fenster wirklich vorne steht
  statt nur obenauf zu liegen

## 1.62.0 – Juli 2026

### Verbessert
- 🗂 **Wünsche und Listen liegen jetzt in einem Tab.** Es waren zwei Einträge
  in der Leiste für dieselbe Frage – *was will ich noch, was nehme ich mit?*
  Der Tab **Listen** führt beides zusammen, mit drei Reitern darüber:
  ⭐ Wünsche · 🛒 Einkaufen · 📦 Archiv. Dasselbe Muster wie im
  Tausch-Netzwerk
- 📦 **Das Archiv ist ein eigener Bereich statt eines Knopfes.** Vorher zeigte
  „Archiv anzeigen" dieselben Karten mit einem anderen Symbol davor – als
  Unterschied zu leise. Jetzt ein eigener Reiter, und archivierte Listen sind
  zusätzlich gedämpft dargestellt, mit einer Kante am linken Rand
- 🧭 **Die Hauptleiste hat einen Eintrag weniger** und wackelt nicht mehr: Der
  Listen-Tab war bisher versteckt, solange es keine Liste gab, und tauchte
  dann auf. Jetzt ist er immer da – die Wünsche gibt es ja immer –, und nur
  die beiden hinteren Reiter erscheinen, wenn es dort etwas zu sehen gibt

## 1.61.1 – Juli 2026

### Behoben
- 🎨 **Das Design wurde vor dem ersten Zeichnen nicht mehr gesetzt.** Dafür gab
  es ein paar Zeilen direkt im Dokument – und genau das verbieten die
  Sicherheits-Regeln seit 1.57.0 (`script-src 'self'`). Der Browser blockierte
  sie still; wer ein dunkles Design nutzt, sah bei jedem Laden kurz das helle
  aufblitzen. Die Zeilen stehen jetzt in `theme-boot.js`, und ein Test wacht
  darüber, dass kein Skript zurück ins Dokument wandert
- 📱 `mobile-web-app-capable` ergänzt. Die Apple-Schreibweise allein ist
  abgekündigt und wurde von neueren Browsern angemahnt; beide stehen jetzt
  nebeneinander, bis iOS nachzieht

### Nicht behoben, weil kein Fehler
- Die Konsolenzeile „Banner not shown: beforeinstallpromptevent
  .preventDefault() called" ist Absicht: Brickfolio unterdrückt das Angebot
  des Browsers, um es an passender Stelle selbst zu zeigen – als Karte auf der
  Scan-Seite, mit eigener Anleitung für iPhones

## 1.61.0 – Juli 2026

### Neu
- 🖼 **Katalogbilder liegen jetzt auf der Instanz.** Bisher stand in der
  Datenbank nur die *Adresse* eines Bildes – geholt hat es der Browser direkt
  bei BrickLink, Rebrickable oder Brickognize. Aus der Sammlung ging dabei
  nichts nach außen, aber die Bildadresse nennt die Teilenummer, und bei jedem
  Blättern lief so ein Abruf. Jetzt holt der Server das Bild **einmal**,
  verkleinert es auf 400 Pixel und legt es unter `data/catalog/` ab. Danach
  fragt der Browser nur noch die eigene Instanz
- 🔄 **Neue Artikel bringen ihr Bild von selbst mit**; den Bestand aus der Zeit
  davor holt **Mehr → 🖼 Bilder auf der Instanz** in Häppchen nach und zeigt
  dabei, wie viele noch fehlen

### Sicherheit
- Der Abruf kann **ausschließlich** zu den vier Katalog-Hosts gehen. Er läuft
  auf dem Server, ein offener Weg dorthin wäre ein Werkzeug, um von innen
  beliebige Adressen anzufragen – fünf Tests prüfen genau das, von
  `127.0.0.1` bis zur Metadaten-Adresse einer Cloud
- Der Dateiname entsteht aus der Bildadresse **und dem Schlüssel der
  Instanz**. Ohne ihn lässt sich aus einer Teilenummer nicht ausrechnen, ob
  dieses Bild hier liegt – sonst verriete der Speicher, was die Sammlung
  enthält
- Ein Fehlschlag beim CDN wird **nicht** gemerkt: Ein Aussetzer darf ein Bild
  nicht dauerhaft verschwinden lassen

### Gut zu wissen
- Grob 10–25 KB je Artikel, 1000 Artikel also 15–25 MB. In der
  JSON-Sicherung stecken die Bilder **nicht** – die bleibt klein, und
  verlorene Bilder holt der Knopf jederzeit neu
- 16 neue Tests in `tests/test_catalog_images.py` (323 gesamt)

## 1.60.2 – Juli 2026

### Behoben
- 🔎 **Das Fehlerprotokoll bekam von all dem nichts mit.** Blockiert der
  Browser etwas wegen der Sicherheits-Regeln, ist das kein Programmfehler –
  `window.onerror` sieht davon nichts, und ein Bild, das nicht lädt, meldet
  sich nur am Element selbst. Deshalb stand dort „Keine Fehler aufgezeichnet",
  während die Konsole voll war. Beides wird jetzt gemeldet, je Regel und Host
  einmal statt je Bild

### Dokumentation
- 🔍 **Klargestellt, was beim Anzeigen von Bildern nach außen geht.** Brickfolio
  speichert zu jedem Artikel nur die *Adresse* des Katalogbildes; geholt wird es
  vom Browser direkt bei BrickLink, Rebrickable oder – für Gescanntes –
  Brickognize (dessen Vorschaubilder liegen bei `storage.googleapis.com`).
  Dorthin geht die Bildadresse, die IP-Adresse und die Browserkennung –
  **nichts aus der Sammlung**, und ausdrücklich kein Referrer. Das stand so
  bisher nirgends; README und beide Handbücher sagen es jetzt

## 1.60.1 – Juli 2026

### Behoben
- 🖼 **Gescannte Artikel hatten kein Bild mehr.** Brickognize legt seine
  Vorschaubilder in einem Google-Storage-Bucket ab – dieser Host fehlte in den
  Sicherheits-Regeln von 1.57.0. Der Browser blockierte die Bilder still; zu
  sehen war das nur in der Konsole. Katalogbilder von BrickLink und
  Rebrickable waren nie betroffen, deshalb fehlten immer nur *manche* Bilder
- 🖼 **Der Ersatz für ein kaputtes Bild wurde nie eingesetzt.** Er hing an
  einem `onerror`-Attribut, und genau das verbieten dieselben Regeln
  (`script-src 'self'`). Statt des Platzhalters stand ein zerbrochenes Symbol
  da. Jetzt erledigt das ein einziger Lauscher am Dokument – für *alle*
  Bilder, nicht nur die sieben, die das Attribut hatten. Ein Test wacht
  darüber, dass kein Skript zurück in ein Attribut wandert
- ⚙️ **Der Service Worker machte aus einem stockenden Abruf einen harten
  Fehler.** Er griff auch nach fremden Hosts, und schlug der Abruf fehl, gab
  er `undefined` als Antwort zurück – der Browser meldete einen kaputten
  Worker. Fremde Hosts lässt er jetzt ganz in Ruhe, und im Offline-Fall kommt
  eine echte Antwort statt keiner
- 📲 **Hinter einem Zugangsschutz galt die App als nicht installierbar.** Der
  Abruf der Manifest-Datei schickte die Sitzung nicht mit und landete auf der
  Anmeldeseite von Cloudflare Access. Jetzt geht er mit Zugangsdaten raus

## 1.60.0 – Juli 2026

### Neu
- 🌍 **21 Länder und sieben Regionen als Preisgebiet.** Bisher gab es nur den
  deutschsprachigen Raum plus Europa und weltweit. Jetzt sind Großbritannien,
  USA, Kanada, Australien, Neuseeland und die übrigen europäischen Märkte
  dabei, dazu Nordamerika, Südamerika, Asien, Ozeanien, Afrika und Naher Osten
- 💱 **Währung wählbar** – Euro, Britisches Pfund, US-Dollar, Schweizer
  Franken, Kanadischer und Australischer Dollar, Neuseeland-Dollar,
  Schwedische, Dänische und Norwegische Krone, Złoty, Tschechische Krone.
  Umgerechnet wird bei **BrickLink**: Die App schickt den Währungscode mit und
  speichert, was zurückkommt – keine eigenen Kurse, nichts, was veralten kann
- 🧭 **Der Einrichtungsassistent fragt beides beim ersten Start ab** (neuer
  Schritt 2) und **schlägt vor, was zu den Spracheinstellungen des Browsers
  passt**: `en-GB` → Großbritannien und Pfund, `en-US` → USA und Dollar,
  `de-DE` → Deutschland und Euro. Wer das Land wechselt, bekommt die passende
  Währung mitgezogen – eine danach von Hand gewählte bleibt stehen

### Verbessert
- 🎯 **Der Rückfall folgt jetzt dem Land.** Findet BrickLink im gewählten Land
  keine Verkäufe, kam bisher immer Europa als zweite Stufe – auch für die USA.
  Jetzt ist es die zugehörige Region: Nordamerika für die USA und Kanada,
  Ozeanien für Australien und Neuseeland, Europa für Europa
- 💶 **Beträge stehen überall in der eingestellten Währung**, auch die Zeichen
  neben den Eingabefeldern („Bezahlt £")
- 🔄 **Ein Wechsel der Währung macht die Preise genauso fällig wie ein Wechsel
  des Gebiets.** Sonst stünden alte Beträge unter neuem Zeichen – falsch, und
  von außen nicht erkennbar. Bestände aus älteren Versionen gelten als Euro
  und bleiben dadurch unangetastet

### Behoben
- 🌐 **Deutsche Reste in der englischen Oberfläche.** Rund 90 Textstellen, die
  erst mit echten Daten sichtbar werden – Themen-Gruppen, Preiskarte,
  Einkaufslisten, Verkaufsliste, fehlende Set-Figuren, Einladungen, der
  Cloudflare-Block und die Rückfragen vor dem Löschen. Ebenfalls übersetzt:
  Datums- und Uhrzeitangaben, die fest auf `de-DE` standen
- 🌐 Attribute, die erst zur Laufzeit gesetzt werden (Tooltips am Mengenknopf,
  am Design-Stern, am Umbenennen-Stift), wurden vom Übersetzer nicht erfasst –
  sie blieben deutsch, egal welche Sprache eingestellt war
- 🌐 Sätze, die in der Vorlage über zwei Zeilen laufen, fanden ihren
  Katalogeintrag nicht mehr

### Für Entwickler
- 🏷 Der Release-Ablauf unterscheidet jetzt Release und Vorabversion. Eine als
  Prerelease veröffentlichte Beta nahm bisher die Marke `latest` mit und wäre
  damit bei allen gelandet, die schlicht `latest` ziehen. Betas tragen die
  eigene Marke `beta`
- Neue Spalte `price_currency` in `collection`, `wanted` und `shopping_items`
  (Migration läuft von selbst). `NULL` gilt als Euro
- `/api/settings/price_region` liefert zusätzlich `currency`, `currencies` und
  `suggested` (Land → Währung) und nimmt `currency` entgegen
- `/api/config` nennt `currency` und `price_region`
- 17 neue Tests in `tests/test_currency.py` (306 gesamt)

## 1.58.2 – Juli 2026

### Neu
- 🔐 **Zwei-Faktor-Anmeldung – freiwillig, je Benutzer.** Einmalcode aus einer Authenticator-App (TOTP nach RFC 6238), einzurichten im Profil: Passwort, QR-Code scannen, Code bestätigen. Eingeschaltet wird erst, wenn ein Code aus der App stimmt – so kann sich niemand mit einem falsch übertragenen Schlüssel aussperren
- 🆘 **Acht Rettungscodes** für den Fall, dass das Telefon weg ist. Sie erscheinen genau einmal; in der Datenbank liegen nur ihre Prüfsummen. Jeder gilt einmal, die App zählt mit
- 🔧 **Notausgang für den Admin**: Ist auch der letzte Rettungscode weg, nimmt ein Admin den zweiten Faktor in der Benutzerverwaltung ab. Ohne das wäre ein verlorenes Gerät ein verlorenes Konto
- 📖 Neuer Abschnitt 3.1 in beiden Handbüchern

### Behoben
- 🐞 **Ein Tippfehler im Einmalcode warf einen aus dem ganzen Anmeldevorgang.** Die App behandelte jede Absage mit „401" als abgelaufene Sitzung und meldete ab – auch das „Code stimmt nicht". Jetzt bleibt man im Schritt und kann es nochmal versuchen
- 🐞 **Nach dem Abmelden standen kurz zwei Anmeldekästen übereinander.** Eine nebenher laufende Abfrage legte den Passwort-Bogen wieder über den Code-Schritt

### Sicherheit
- Die Zwischenmarke aus dem ersten Anmeldeschritt ist **keine Sitzung** – mit halb erledigter Anmeldung kommt man an keine Daten. Ein Test wacht darüber
- Ein Einmalcode gilt **nur einmal**; auch der zweite Schritt ist gegen Raten gebremst

## 1.57.0 – Juli 2026

### Neu
- 🛡 **Passwortraten wird gebremst.** Bisher konnte man beliebig oft raten – im Heimnetz verschmerzbar, bei einer Portfreigabe nicht. Jetzt: zehn Fehlversuche je Konto **und** je Herkunft, danach 15 Minuten Pause. Gezählt wird je Konto, damit ein Adresswechsel nichts bringt; eine geglückte Anmeldung setzt die Zähler zurück, damit sich eine Familie hinter einer Adresse nicht selbst aussperrt. Bewusst **kein** hartes Kontosperren – sonst könnte ein Fremder jeden mit Absicht aussperren
- 🔒 **Schutz-Header** für den Browser: kein Einbetten in fremde Rahmen, kein Raten von Dateitypen, Skripte nur aus der App selbst. Die Regeln lassen Katalogbilder von BrickLink und Rebrickable ausdrücklich zu

### Verbessert
- 🔑 **Passwörter brauchen jetzt acht statt vier Zeichen.** Betrifft nur neu gesetzte Passwörter; bestehende Anmeldungen laufen weiter
- 📖 Neuer Abschnitt **„Wie die App abgesichert ist – und wofür sie nicht gebaut ist"** in beiden Handbüchern: was greift, was fehlt (vor allem: die App spricht `http`, über eine Portfreigabe ginge das Passwort im Klartext durchs Netz) und warum der Cloudflare-Tunnel die Empfehlung bleibt

## 1.56.0 – Juli 2026

### Neu
- 📖 **Das Handbuch gibt es auf Englisch** ([`docs/MANUAL.md`](docs/MANUAL.md)) – alle 16 Kapitel, rund 60 kB, von der Installation über den Flohmarkt-Ablauf bis zur Preis-Automatik. Beide Fassungen verlinken einander, und die Hilfe in der App zeigt je nach Sprache das passende
- Damit ist die Übersetzung rund: Oberfläche, Hilfe, Fehlermeldungen des Servers, READMEs und Handbuch

### Behoben
- 🔢 Im deutschen Handbuch stimmten **acht Unterkapitel-Nummern** nicht mehr mit ihrem Kapitel überein (12.1 unter Kapitel 13, 15.1 unter Kapitel 16 …) – Reste der Umnummerierung, als das Tausch-Kapitel dazukam

## 1.55.2 – Juli 2026

*Nur Doku – an der App ändert sich nichts.*

### Behoben
- 📄 **Der Update-Weg für Image-Installationen war falsch beschrieben.** README und Handbuch verwiesen auf `sudo bash update.sh` – das Skript gehört aber zum Quellcode und liegt weder im Image noch im Ordner, wenn man nur die `docker-compose.yml` geholt hat. Jetzt steht getrennt da, was für welche Installationsart gilt, inklusive des Hinweises, dass man den **Schnappschuss dann selbst** machen sollte (*Mehr → Sicherung*)
- 📄 Dasselbe für den **Update-Knopf in der App**: Er braucht `update-watch.sh` auf dem Server. Ohne das Skript erscheint er gar nicht erst – das steht jetzt dort, samt der beiden `curl`-Zeilen zum Nachrüsten

## 1.55.1 – Juli 2026

### Neu
- 🌐 **Sprachwahl schon beim allerersten Start.** Über den Feldern für das Admin-Konto stehen jetzt Deutsch und English – dort, wo man die Entscheidung ohnehin trifft. Die Wahl landet direkt im Profil des frisch angelegten Admins, gilt also gleich auf allen Geräten
- 🔁 **Umschalten ohne Neuladen.** Die App merkt sich, was vor dem Übersetzen dastand, und kann zurückwechseln. Damit gehen beim Umschalten **keine Eingaben mehr verloren** – wer schon Benutzername und Passwort getippt hat, behält beides

### Verbessert
- 🈯 40 weitere Textstellen übersetzt, die per `textContent` gesetzt werden (Ladehinweise, Prüfmeldungen der Formulare, Aufklapp-Knöpfe für Teile und Set-Figuren). Sie blieben bisher deutsch, weil sie erst nach dem Zeichnen entstehen

## 1.54.1 – Juli 2026

### Neu
- 🌐 **Auch die Fehlermeldungen des Servers sind übersetzt** – 68 Meldungen von „Eintrag nicht gefunden" bis „Sicherung enthält keinen Admin". Am Backend musste dafür nichts geändert werden: Die Meldung kommt als deutscher Satz an, und der ist der Schlüssel. Übersetzt wird zentral dort, wo der Fehler entsteht – nicht an den gut einem Dutzend Stellen, die ihn anzeigen

### Behoben
- 🐞 **Bei Eingabefehlern stand `[object Object]` in der Meldung.** Prüft der Server die Eingabe, schickt er eine Liste von Einzelfehlern statt eines Satzes – ungeprüft landete das als Objekt in der Anzeige. Jetzt steht dort der Grund im Klartext
- 🐳 **Der Release-Lauf meldete stillschweigend Erfolg**, obwohl das Setzen der Docker-Hub-Beschreibung mit „Forbidden" scheiterte. Der Schritt ist entfernt: Docker Hub verlangt dafür einen Token mit *read/write/delete* – der dürfte also auch Images löschen, und das gehört für eine Textseite nicht in die CI. Der Text liegt in `docs/DOCKERHUB.md` und wird bei Bedarf von Hand eingefügt

## 1.53.1 – Juli 2026

### Neu
- 🌐 **Die Oberfläche ist vollständig auf Englisch.** Gemessen an einer Instanz mit Demodaten, über alle sieben Ansichten und die komplette Hilfe: **0 von 349** bzw. **0 von 149** Textstellen noch deutsch. Umschalten unter *Mehr → Sprache*; die Wahl liegt im Profil
- 📖 Auch die langen Erklärtexte sind übersetzt – die Hilfe, „Wie der Wert berechnet wird", die Rollen-Übersicht, der Cloudflare-Assistent, die Quellen- und Rechtliches-Angaben

### Behoben
- 🔤 **Sätze mit Auszeichnung blieben deutsch**, wenn ein Wort darin hervorgehoben war: Das innere `<b>` wurde zuerst übersetzt, danach passte der ganze Satz nicht mehr auf seinen Eintrag. Jetzt gewinnt der äußere Treffer – ein einzelnes englisches Wort in einem deutschen Absatz kann nicht mehr entstehen
- 🧾 Preis- und Mengenzeilen („2× · Gebraucht · Ø gebr. 8,00 €", „1 Artikel · 1 offen · Marktwert ca. …") tragen jetzt Platzhalter statt fester Wortstellung

### Für Deutsch ändert sich nichts
Die Quellsprache braucht keinen Katalog: Bei Deutsch werden **null** Einträge geladen, es gibt keine zusätzliche Anfrage und kein Aufblitzen. Nachgeprüft.

## 1.52.2 – Juli 2026

### Verbessert
- 🈯 **Zweite Stufe der Übersetzung: alles, was die App zur Laufzeit zeichnet.** Kartenbeschriftungen, Kennzahlen, leere Zustände und die rund 200 Kurzmeldungen sind jetzt auf Englisch. Gemessen an einer Instanz mit Demodaten: **Wünsche 0, Sammlung 1, Scannen 1, Listen 2, Tausch 2, Statistik 4** noch deutsche Textstellen – der Rest sitzt im Mehr-Tab (36), wo die langen Erklärtexte stehen
- 🔢 Meldungen mit eingesetzten Werten tragen jetzt **Platzhalter** statt zusammengeklebter Bruchstücke („{n} Artikel übernommen"), damit die Wortstellung übersetzbar bleibt

### Behoben
- 🐞 **Die Statistik brach mit „t is not a function" ab.** Die Übersetzungsfunktion hieß `t` – genauso wie eine lokale Variable in der Statistik-Ansicht, die sie verdeckte. Sie heißt jetzt `tr`; in einer Datei dieser Größe ist ein einzelner Buchstabe als globaler Name eine Falle
- 🧭 Zwei Katalogeinträge waren **datenabhängig** („Top 5 nach Wert") und hätten nur bei genau diesem Wert gegriffen – jetzt mit Platzhalter

## 1.52.0 – Juli 2026

### Neu
- 🌐 **Die App spricht Englisch.** Unter *Mehr → Sprache* lässt sich zwischen Deutsch und English wählen; die Wahl liegt im Profil und gilt auf allen Geräten. Ohne eigene Wahl folgt die App der Sprache des Browsers – wer Englisch eingestellt hat, landet direkt dort
- 🈯 **Erste Stufe: die feste Oberfläche.** Navigation, Knöpfe, Formulare, Einrichtungsassistent, Hilfe-Überschriften und alle Platzhalter sind übersetzt (251 Textstellen). **Noch deutsch bleiben** die langen Hilfetexte und alles, was JavaScript zur Laufzeit baut – Kartenbeschriftungen, Meldungen, Fehlertexte. Das folgt in weiteren Schritten

### Technisch
- Der **deutsche Text ist der Schlüssel** (wie bei gettext): Deutsch braucht keinen Katalog und keine zusätzliche Anfrage, und eine fehlende Übersetzung zeigt den deutschen Satz statt einer Lücke oder eines nackten Schlüssels
- Tests wachen darüber, dass kein Katalogeintrag ins Leere zeigt, dass Platzhalter und Auszeichnungen erhalten bleiben und dass keine Übersetzung leer ist

## 1.51.1 – Juli 2026

### Verbessert
- 🤝 **Höflicher gegenüber Brickognize.** Die Bilderkennung stellt jemand kostenlos bereit. Brickfolio meldete sich dort bisher als „Brickfolio/1.0" – jetzt mit der echten Version und einem Link zum Projekt, damit man uns erreichen kann, statt bei Auffälligkeiten nur sperren zu können
- 🐳 **Die Docker-Hub-Seite war leer.** Wer dort landete, sah ein Image ohne jede Erklärung. Sie bekommt jetzt bei jedem Release automatisch Kurzbeschreibung und eine eigene Übersichtsseite

## 1.51.0 – Juli 2026

### Verbessert
- ⚡ **Der zweite Start geht deutlich flotter.** Versionierte Dateien und die Schriften (228 kB) darf der Browser jetzt dauerhaft behalten, statt sie bei jedem Öffnen neu beim Server zu erfragen. Das spart rund zehn Rückfragen pro Start – am Handy und über den Tunnel der spürbare Teil, im Heimnetz kaum messbar
- 🏷️ **Die Versionsmarke setzt die App selbst ein.** `?v=` an den Adressen von `app.js`, `style.css` und `fonts.css` kommt jetzt aus der Versionsnummer der Instanz. Eine neue Version erneuert damit automatisch alle Adressen – vorher war das eine Zahl, die von Hand hochgesetzt werden musste. Genau darauf beruht das dauerhafte Cachen: Vergessen kann man es nicht mehr

## 1.50.1 – Juli 2026

### Verbessert
- 🗜️ **Antworten werden komprimiert – das ändert für große Sammlungen alles.** Bisher ging jede Antwort unkomprimiert über die Leitung. Gemessen an 2150 Artikeln: die Sammlung schrumpft von **1978 kB auf 29 kB**, `app.js` von 250 auf 64 kB, `style.css` von 57 auf 14 kB. Spürbar vor allem im Heimnetz und über Mobilfunk – hinter dem Cloudflare-Tunnel hatte Cloudflare das bisher aufgefangen, direkt am NAS niemand
- ⚡ Die Aufstellung, welche Figuren in eigenen Sets stecken, wurde beim Laden der Sammlung **zweimal** berechnet – jetzt einmal

## 1.50.0 – Juli 2026

### Neu
- 📲 **„Auf den Startbildschirm" auf der Scan-Seite.** Die App erkennt, ob sie vom Startbildschirm oder aus dem Browser läuft, und bietet das Hinzufügen nur dort an, wo es fehlt – auf Android und anderen Chromium-Browsern mit einem Knopf, der die Installation direkt auslöst. Sobald sie liegt, verschwindet die Karte von selbst
- 🍎 **Auf dem iPhone mit Anleitung**, weil Safari keinen Knopf dafür kennt: Teilen → „Zum Home-Bildschirm", in zwei Sätzen erklärt
- 🔒 **Und wenn es gar nicht geht, steht warum da**: Über eine reine `http`-Adresse im Heimnetz erlauben Browser das Hinzufügen nicht. Statt eines toten Knopfes gibt es den Hinweis auf *Mehr → Externer Zugriff*
- 🙈 „Nicht mehr anzeigen" merkt sich das Gerät dauerhaft

## 1.49.3 – Juli 2026

*Nur Doku – an der App ändert sich nichts.*

### Behoben
- 📄 **„Ohne Internet vollständig nutzbar" stimmte nicht.** Der Satz stand im Absatz über die lokal ausgelieferte Schrift und war dort gemeint, las sich aber als Aussage über die ganze App. Ohne Internet fallen Scannen, Namenssuche, Preise, Set-Inhalte, Katalogbilder, Update-Prüfung und Tausch-Netzwerk aus. Beide READMEs sagen jetzt aufgeschlüsselt, was geht und was nicht
- 📄 **„Ohne Konto bei Dritten" stimmte auch nicht** – für Preise und Namenssuche braucht es eigene Zugänge bei BrickLink und Rebrickable, was das Handbuch zwei Kapitel später selbst beschreibt. Präzisiert: Es gibt keinen Brickfolio-Dienst, bei dem man sich anmelden müsste

## 1.49.2 – Juli 2026

*An der App ändert sich nichts – die Doku holt auf.*

### Verbessert
- 📖 **Handbuch auf Stand.** Es beschrieb noch v1.20.1. Neu: ein ganzes Kapitel zum **Tausch-Netzwerk** (was wo liegt, beitreten, anbieten mit Menge, Gespräche, Melden, gesperrter Zugang), der **Einrichtungsassistent**, **eigene Figuren (Custom)**, **Themenkarten** und die gemerkte Sortierung, die **Detailansicht mit Teileliste**, das Statistik-Feld **„Einkauf auf Listen"** samt „inventarisiert"
- 📦 **Installation und Updates neu beschrieben** – fertiges Image statt Quellcode bauen, Container-Oberfläche statt SSH, `update.sh` erkennt die Betriebsart selbst
- 🇬🇧 **Englisches README nachgezogen**: Schnellstart, Assistent, Tausch-Netzwerk, Tabelle für andere NAS-Hersteller

## 1.49.1 – Juli 2026

*An der App selbst ändert sich nichts – nur daran, wie man sie bekommt.*

### Neu
- 🐳 **Das Image liegt jetzt auch auf Docker Hub** (`melle79/brickfolio`), zusätzlich zur GitHub-Registry. Damit findet Synologys Container Manager es über die eingebaute Suche – die GitHub-Registry lässt sich nicht durchsuchen
- 📘 **Synology-Anleitung ohne Konsole** ([`docs/SYNOLOGY.md`](docs/SYNOLOGY.md)): Container Manager → Projekt → YAML einfügen, dazu Aktualisieren und die üblichen Stolpersteine (belegter Port, Rechte auf `data`, ARM-Modelle)

## 1.49.0 – Juli 2026

### Neu
- 📦 **Fertiges Docker-Image.** Kein Klonen, kein Bauen: `docker compose up -d` zieht `ghcr.io/melle79/brickfolio:latest` – für amd64 (Synology, Intel-NAS, PC) und arm64 (Raspberry Pi, ARM-NAS). Aus „Quellcode holen, minutenlang bauen" wird ein Download. `latest` entsteht nur aus Releases, `main` folgt dem Entwicklungsstand
- 🧭 **Einrichtungsassistent beim allerersten Start.** Nach dem Admin-Konto führen sechs Schritte durch Anzeigename, Rebrickable-Schlüssel, BrickLink-Zugang, einen echten Verbindungstest und – falls vorhanden – die Einladung ins Tausch-Netzwerk. Jeder Schritt ist überspringbar; ohne Schlüssel funktioniert das Scannen ohnehin
- 🔁 **`update.sh` erkennt die Betriebsart selbst**: fertiges Image nachziehen oder wie bisher aus dem Quellcode bauen. Bestehende Installationen ändern nichts

### Verbessert
- 🔑 **Unvollständige BrickLink-Schlüssel werden benannt.** Der Verbindungstest sagte „Keine Schlüssel hinterlegt", auch wenn schon zwei der vier Werte eingetragen waren. Jetzt steht dort, welche fehlen

## 1.48.2 – Juli 2026

### Behoben
- 📐 **Auf dem Rechner waren die Kacheln beim Scannen verschieden breit.** Kamera-Fläche und Erfassen-Formular waren enger gehalten als Ergebnis und Knöpfe, dadurch sprangen die Kanten von Block zu Block. Jetzt stehen alle auf der breiteren Spur bündig untereinander; am Handy ändert sich nichts

## 1.48.1 – Juli 2026

### Verbessert
- 🙈 **Die Instanz-Kennung steht nicht mehr in der App.** Dort ist sie nur eine Nummer ohne Zusammenhang – gebraucht wird sie in der Admin-Konsole, und dort steht sie auch. Gemerkt und beim Beitritt mitgeschickt wird sie unverändert

## 1.48.0 – Juli 2026

### Neu
- 🏠 **Jede Instanz hat jetzt eine Kennung.** Bei der Erstanmeldung vergibt der Hub eine ablesbare Nummer im Format `BF-4K7P-2M9X-C` – mit Prüfzeichen, damit ein Zahlendreher beim Abtippen auffällt statt still danebenzugreifen. Sie liegt still in den Einstellungen und damit in der Sicherung: Nach einer Neuinstallation samt Rücksicherung ist es für den Hub wieder dieselbe Instanz
- 📜 **Der Hub kennt die Vorgeschichte einer Installation.** In der Admin-Konsole steht unter „Instanzen", unter welchem Namen sich eine Instanz erstmals angemeldet hat und welche Konten seither dazugehörten. Wer den Zugang verliert, lässt sich damit sicher zuordnen und freischalten
- 🚫 **Eine Sperre gilt der Installation, nicht nur dem Namen.** Bisher genügten eine neue Einladung und ein anderer Name, um zurückzukommen. Meldet sich dieselbe Instanz erneut an, wird sie erkannt und abgewiesen – mit Angabe ihrer Kennung, damit klar ist, worüber der Hub-Admin entscheidet. Freischalten geht per Kennung, auch abgetippt

## 1.47.0 – Juli 2026

### Verbessert
- 🚫 **Eine Sperre sieht jetzt aus wie eine Sperre.** Wer vom Hub-Admin aus dem Netzwerk genommen wurde, bekam bisher bei jeder Aktion „Token fehlt oder ungültig" – das klang nach einem kaputten Zugang und legte nahe, die Verbindung zu trennen und neu zu verbinden, was gar nicht klappen kann. Der Hub unterscheidet nun zwischen gesperrt und unbekannt, und die Tausch-Ansicht erklärt die Lage: bisherige Unterhaltungen bleiben lesbar, und nach einer Freischaltung geht es ohne Neuverbinden weiter

### Behoben
- 🧹 **Beim Löschen eines Mitglieds blieben leere Unterhaltungen zurück.** Angebote und Nachrichten wurden entfernt, die Gespräche selbst nicht – beim Gegenüber stand danach eine Unterhaltung ohne Gesprächspartner. Sie gehen jetzt mit
- 🔑 **Nach einem Neubeitritt kam der Schlüssel nicht beim Hub an.** Die Instanz hielt sich für schon gemeldet und war für neue Nachrichten unerreichbar. Beim Verbinden und beim Trennen wird der Stand jetzt zurückgesetzt

## 1.46.1 – Juli 2026

### Behoben
- ⚑ **Das Meldefenster verschwand hinter dem Gespräch.** Beide Fenster lagen auf derselben Ebene, also gewann das später im Dokument stehende – das Meldefenster ging auf, war aber nicht zu sehen. Jetzt tritt das Gespräch zur Seite, das Meldefenster steht allein da, und nach dem Absenden oder Abbrechen ist das Gespräch wieder da
- 💬 **Rückmeldungen waren in Fenstern unsichtbar.** Kurzhinweise („Gemeldet – ein Hub-Admin schaut sich das an") lagen unter den Fenstern und damit ausgerechnet dort verborgen, wo sie ausgelöst wurden

## 1.46.0 – Juli 2026

### Neu
- 🔢 **Menge je Angebot wählbar.** Bei mehrfach vorhandenen Figuren lässt sich in „Meine Auswahl" einstellen, wie viele davon ins Netzwerk gehen – die übrigen bleiben unsichtbar. Ohne Angabe wie bisher alle *(Hub-Issue #10)*
- 🗑 **Unterhaltungen löschen.** Im Gespräch gibt es einen Löschen-Knopf; der Vorgang verschwindet hier und im Hub, samt der Umschläge beim Gegenüber *(Hub-Issue #7)*

### Verbessert
- 📤 **Man sieht, was schon veröffentlicht ist.** Jeder Artikel in der Auswahl trägt jetzt „veröffentlicht" oder „noch nicht veröffentlicht", die Kopfzeile zählt beides. Angebote, die im Hub stehen, hier aber nicht mehr ausgewählt sind, werden oben angezeigt – sie fallen beim nächsten Veröffentlichen weg *(Hub-Issue #9)*
- 🚫 **Zurückgezogene Angebote sind erkennbar.** Nimmt das Gegenüber einen Artikel aus dem Netzwerk, steht das an der Vorgangsliste und über dem Gesprächsverlauf, statt still weiterzulaufen *(Hub-Issue #8)*

### Behoben
- ✖ Nach „Ablehnen" blieb das Gesprächsfenster offen stehen; es schließt sich jetzt *(Hub-Issue #6)*

## 1.45.1 – Juli 2026

### Behoben
- 💶 **Werte der Themenkarten stimmen wieder.** Die Karten zählten Figuren voll mit, die in eigenen Sets stecken – dadurch lagen sie über der Gesamtsumme im Kopf (die diese Figuren zu Recht herausrechnet). Der Wert je Eintrag kommt jetzt vom Server und folgt überall derselben Regel; Karten und Kopfsumme passen zusammen *(Issue #11)*

## 1.45.0 – Juli 2026

### Neu
- 🖼️ **Eigene Figuren zeigen ihr Bild im Netzwerk.** Bisher blieb bei Custom-Artikeln beim Gegenüber nur ein Platzhalter – ihr Bild liegt ja auf der eigenen Instanz. Jetzt reist ein verkleinertes Vorschaubild mit dem Angebot mit. Für BrickLink-Artikel ändert sich nichts, die haben ohnehin eine öffentliche Adresse
- 🔎 **Suche im Tausch-Netzwerk.** Über den Angeboten steht ein Suchfeld – es findet über Name und Nummer, auch bei eigenen Figuren

### Verbessert
- 💬 **Angefragt steht an der Karte.** Läuft zu einem Angebot schon ein Gespräch, zeigt die Karte das direkt an („angefragt · offen", samt ungelesenen Nachrichten) und der Knopf heißt „Gespräch öffnen" – man muss nicht erst hineinklicken

### Behoben
- 🔄 Beim Zurückwechseln auf „Angebote" blieb der alte Stand stehen; inzwischen gestartete Gespräche fehlten dort

## 1.44.0 – Juli 2026

### Verbessert
- 💬 **Angebot antippen genügt.** Ein Tipp auf die Karte öffnet direkt das Anfrage-Fenster – die vorgeschlagene Nachricht steht dort in einem richtigen Textfeld und lässt sich vor dem Senden anpassen. Keine Browser-Abfragen mehr
- ↩️ **Bestehende Gespräche gehen sofort auf.** Hast du zu einem Angebot schon Interesse bekundet, landest du beim Antippen gleich im Chat statt in einer neuen Anfrage
- ⚑ **Melden mit eigenem Fenster.** Begründung und der Haken „Verlauf mitschicken" stehen jetzt zusammen in einem Dialog – vorher waren es zwei Browser-Abfragen hintereinander

## 1.43.0 – Juli 2026

### Verbessert
- 🔄 **Nachrichten kommen von selbst an.** Kein „Abrufen" mehr nötig: Im offenen Gespräch lädt die App alle 8 Sekunden nach, in der Vorgangsliste alle 20, sonst einmal pro Minute für den Zähler am Tausch-Tab. Kommt etwas an, während du woanders bist, meldet ein kurzer Hinweis das. Im Hintergrund (anderes Fenster, Bildschirm aus) pausiert alles und läuft beim Zurückkommen sofort wieder an
- ⚡ **Sparsamer Abgleich.** Geholt wird nur, wo der Hub Post gemeldet hat – nicht mehr für jeden Vorgang einzeln. Das hält das automatische Nachladen auch bei vielen Vorgängen günstig

## 1.42.0 – Juli 2026

### Neu
- 💬 **Tauschen mit Nachrichten.** An jedem fremden Angebot steht jetzt „Interesse" – daraus wird ein Gespräch. Der neue Bereich **Meine Vorgänge** zeigt alle Anfragen mit ungelesen-Zähler; im Gespräch lässt sich schreiben, annehmen, ablehnen und melden. **Nachrichten sind Ende-zu-Ende verschlüsselt**: Der Hub kann sie nicht lesen und löscht sie, sobald beide Seiten sie haben – der Verlauf bleibt auf den Instanzen *(Hub-Issue #2)*
- 🎯 **Selbst auswählen, was in die Börse kommt.** Statt automatisch der ganzen Abgabeliste bestimmst du pro Artikel: Karte in der Sammlung öffnen → „🤝 In der Tauschbörse anbieten". Unter **Tausch → Meine Auswahl** siehst du alles Ausgewählte, kannst die Abgabeliste mit einem Klick übernehmen und dann veröffentlichen
- ⚑ **Melden.** Läuft etwas schief, lässt sich das Gegenüber melden. Der Nachrichtenverlauf geht **nur mit, wenn du zustimmst** – deine Instanz entschlüsselt ihn dafür selbst. Ohne Zustimmung sieht der Hub-Admin nur deine Begründung

## 1.41.0 – Juli 2026

### Neu
- ✉️ **Einladungen mit Kontingent.** Jeder darf **3 Einladungen** aussprechen; im Tausch-Tab steht, wie viele noch frei sind. Ist das Kontingent aufgebraucht, lässt sich direkt **mehr anfragen** – ein Hub-Admin genehmigt oder lehnt das in der Konsole ab, bei Genehmigung wächst das Kontingent *(Hub-Issue #4)*
- 🙋 **Namen im Netzwerk sind eindeutig.** Beim Beitreten wird geprüft, ob der Anzeigename schon vergeben ist (Groß-/Kleinschreibung egal), und er braucht mindestens **4 Zeichen**. Gilt auch beim Umbenennen *(Hub-Issue #4)*

## 1.40.3 – Juli 2026

### Behoben
- ↕️ **Sortierung merkt sich die letzte Auswahl.** Bisher wurde nur gespeichert, was man unter **Mehr → Sortierung** einstellte – die Auswahl direkt in der Sammlung war nach dem Neuladen wieder weg. Jetzt landet jede Umstellung im Profil, und beide Stellen zeigen immer dasselbe

## 1.40.2 – Juli 2026

### Behoben
- 🎨 **Eigene Figuren stehen jetzt unter „Custom".** Sie landeten bisher unter „Ohne Thema", obwohl sie ein eigenes Thema haben. Bestehende Einträge werden beim Update zugeordnet

## 1.40.1 – Juli 2026

### Behoben
- 🗂️ **Themen fehlten nach dem Update.** Bestehende Einträge hatten noch kein Thema, sodass die ganze Sammlung unter „Ohne Thema" stand. Beim Update ordnet die App vorhandene Minifiguren jetzt automatisch zu (das Thema steckt in der Nummer). Sets und Teile holt man weiterhin per „Themen nachladen" unter **Mehr → Sortierung**

## 1.40.0 – Juli 2026

### Verbessert
- 🗂️ **Themen als aufklappbare Karten.** Bei der Sortierung „Thema" wird die Sammlung jetzt nicht nur sortiert, sondern in **Themenkarten gruppiert**: je Thema eine Karte mit Anzahl und Wert, die sich zuklappen lässt. Welche Themen zugeklappt sind, merkt sich die App. Am Rechner stehen die Karten innerhalb eines Themas weiterhin mehrspaltig

## 1.39.0 – Juli 2026

### Neu
- 🗂️ **Sortierung nach Thema.** Die Sammlung lässt sich jetzt nach Thema sortieren (Star Wars, City, Ninjago …). Bei Minifiguren erkennt die App das Thema direkt an der Nummer (`sw…` → Star Wars) – ohne jeden Abruf. Für Sets und Teile kommt es aus der BrickLink-Kategorie; unter **Mehr → Sortierung** lassen sich fehlende Themen per Knopf nachladen. Einträge ohne erkennbares Thema stehen am Ende *(Issue #10)*
- ↕️ **Standard-Sortierung im Profil.** Unter **Mehr → Sortierung der Sammlung** wählt jeder für sich, womit die Sammlung standardmäßig sortiert wird – gespeichert im eigenen Profil, gilt auf allen Geräten *(Issue #10)*

### Verbessert
- 🛒 **Set-Figuren zeigen Einkaufslisten.** Beim Blick auf die Figuren eines Sets (Suche, Scan, Sammlung) steht jetzt an jeder Figur, wenn sie schon auf einer offenen Liste liegt – zusätzlich zu „vorhanden" bzw. „auf der Wunschliste" *(Issue #9)*

## 1.38.0 – Juli 2026

### Neu
- 📷 **Scan-Foto für eigene Figuren nutzen.** Wird beim Scannen nichts erkannt – bei Eigenbauten der Normalfall –, steht darunter jetzt „🎨 Eigene Figur mit diesem Foto". Ein Klick öffnet das Formular im Custom-Modus, übernimmt das eben gemachte Foto als Bild und vergibt die nächste Nummer; es bleibt nur noch der Name zu tippen. Im Custom-Bereich gibt es zusätzlich „📷 Foto vom Scan verwenden", falls man das Bild später doch noch möchte

## 1.37.0 – Juli 2026

### Neu
- 🛒 **Aus dem Erfassen direkt auf eine Liste.** Das manuelle Formular hat jetzt „Auf eine Liste" – Liste auswählen oder gleich eine neue anlegen. Das gilt auch für **eigene Figuren**, die es in keinem Katalog gibt (z. B. „noch zu bauen"). Anzahl und Zustand kommen aus dem Formular; ein bereits vorhandener Eintrag wird zusammengefasst. Nur für Sammlerprofis sichtbar

## 1.36.0 – Juli 2026

### Verbessert
- 🔢 **Custom-Nummern vergibt die App.** Beim Einschalten von „Eigene Figur" steht die nächste freie Nummer schon im Feld (`custom-001`, `-002` …) – überschreibbar, falls du ein eigenes Schema führst. Nach dem Speichern liegt die nächste sofort bereit, praktisch beim Erfassen mehrerer Figuren am Stück. Gezählt wird über Sammlung, Wunschliste und Einkaufslisten hinweg; Lücken werden nicht neu vergeben, damit eine Nummer eindeutig bleibt

## 1.35.0 – Juli 2026

### Neu
- 🎨 **Eigene Figuren (Custom).** Im manuellen Erfassen gibt es jetzt den Schalter „Eigene Figur": eine **eigene interne Nummer** vergeben und ein **eigenes Bild hochladen**. Das Bild wird verkleinert und neben der Datenbank gespeichert (landet damit in der Sicherung); EXIF-Daten wie GPS fallen dabei weg. Custom-Artikel werden nicht bei BrickLink gesucht – Preise und Katalogbilder gibt es dafür naturgemäß nicht *(Issue #3)*
- 👥 **Figuren im Set-Popup.** Tippt man in Suche oder Scan auf ein **Set**, lassen sich dort jetzt die enthaltenen Minifiguren anzeigen – inklusive „schon vorhanden"-Markierung und den gewohnten Knöpfen zum Übernehmen und Merken *(Issue #2)*

### Verbessert
- 🛒 **Fehlende Set-Figuren zeigen Einkaufslisten.** Steht eine fehlende Figur schon auf einer offenen Liste, steht das jetzt an der Karte („🛒 2× auf »Flohmarkt Juli«") – so kauft man sie nicht ein zweites Mal. Auch im CSV-Export enthalten *(Issue #8)*

### Behoben
- 🧩 Bei **eigenen und manuellen Sets** fragte die App nach den „enthaltenen Figuren", obwohl es dazu keinen Katalogeintrag geben kann. Die Abfrage entfällt jetzt

## 1.34.0 – Juli 2026

### Geändert
- 🧹 **Verwaltung raus aus der App.** Die Hub-Verwaltung wandert vollständig in die separate Admin-Konsole. In den Einstellungen bleibt nur noch das **Beitreten per Einladungscode** und das Trennen der Verbindung – das Eintragen eines Admin-Tokens und das Umbenennen sind entfallen. Einladungen erstellt weiterhin jeder im **Tausch**-Tab

## 1.33.0 – Juli 2026

### Neu
- 🛠️ **Admin-Endpunkte im Tausch-Hub.** Der Hub kann jetzt verwaltet werden: Mitglieder auflisten, umbenennen, Admin-Rechte vergeben/entziehen, deaktivieren/aktivieren und löschen (samt ihrer Angebote); Einladungen einsehen und zurückziehen; dazu eine Übersicht mit Kennzahlen. Schutzregeln: der **letzte Admin** kann nicht entrechtet, deaktiviert oder gelöscht werden, und niemand kann sich **selbst** löschen. Bedient wird das über die separate **Admin-Konsole** (eigenes, privates Projekt) – die Brickfolio-App bleibt davon unberührt

## 1.32.0 – Juli 2026

### Neu
- 🏷️ **Anzeigenamen im Tausch-Netzwerk ändern.** Unter **Mehr → Tausch-Netzwerk** gibt es jetzt ein Feld „Anzeigename ändern" – kein SQL mehr nötig. Zusätzlich frischt die App den Namen beim Öffnen **live vom Hub** auf, sodass Änderungen (auch am Hub selbst) ohne Neu-Verbinden ankommen

## 1.31.0 – Juli 2026

### Geändert
- 🤝 **Tausch-Netzwerk umgebaut.** Die Nutzung (Angebote der Freunde, Veröffentlichen, Einladen) hat jetzt einen **eigenen „Tausch"-Tab** – er erscheint, sobald die Instanz verbunden ist. Unter **Mehr → Einstellungen** bleibt nur noch die **Verbindung**. Die **Hub-Adresse ist fest hinterlegt** (kein Eingabefeld mehr) – neue Freunde brauchen nur ihren Einladungscode. **Einladungen kann jeder** angemeldete Nutzer erstellen (nicht mehr nur Admins); der **Token** wird weiterhin nur vom Admin unter Einstellungen eingetragen. Veröffentlichen bleibt Admin-Sache

## 1.30.0 – Juli 2026

### Neu
- 🤝 **Tausch-Netzwerk (Stufe 1).** Unter **Mehr → Tausch-Netzwerk** lässt sich die Instanz mit einem Brickfolio-Hub verbinden (per Token oder Einladungscode). Dann kann man den eigenen **abgebbaren** Bestand mit einem Klick **veröffentlichen**, die **Angebote der Freunde** ansehen und – als Hub-Admin – **Einladungen** erstellen. Es wird nur „Abgebbar" geteilt; der Zugangs-Token bleibt server-seitig und geht nie an den Browser. Der Hub selbst ist ein eigenes, schlankes Cloudflare-Projekt (`hub/`), das ohne die Instanzen erreichbar zu machen auskommt

## 1.29.0 – Juli 2026

### Verbessert
- ⚡ **Weniger BrickLink-Abrufe, schnellere Popups.** Drei Optimierungen sparen doppelte Anfragen: (1) Das Detail-Popup nutzt die schon in der Trefferliste geladenen Daten (Jahr, Preise, Sets) wieder, statt sie erneut zu holen. (2) Katalog-Preise werden kurz zwischengespeichert (20 Min) – dieselbe Figur in mehreren Suchen/Scans belastet BrickLink nur einmal. (3) Die per Bild gefundene BrickLink-Nummer wird gemerkt; ein erneutes Öffnen desselben Treffers kommt ohne neue Anfrage aus. Gespeicherte Preise (Sammlung/Wunschliste) holen beim „↻ Aktualisieren" weiterhin frisch

## 1.28.0 – Juli 2026

### Neu
- 📷 **Detail-Popup auch beim Scannen.** Ein Tipp auf ein Scan-Ergebnis öffnet jetzt dieselbe Detailansicht wie in der Suche – mit Jahr, Marktpreis, vorhanden/Wunschliste, Sets und den enthaltenen Teilen. Solange in der Karte ein Formular offen ist (Bezahlt/Zustand), bleibt das Popup zu

## 1.27.1 – Juli 2026

### Geändert
- 📊 **Übersichts-Feld wieder nur offene Listen.** Das Statistik-Feld „Einkauf auf Listen" zählt auf der Übersicht wieder nur die **offenen** Listen. Das Popup bleibt wie es ist: dort stehen alle Listen (auch archivierte) mit dem inventarisiert-Haken und einer eigenen Gesamtsumme

## 1.27.0 – Juli 2026

### Verbessert
- 📊 **Einkauf auf Listen: archivierte zählen mit + inventarisiert-Haken.** Das Statistik-Feld summiert jetzt den Einkauf über **alle** Listen (offen und archiviert). Ein Tipp auf das Feld öffnet ein Popup mit allen Listen einzeln – dort lässt sich jede Liste als **inventarisiert** abhaken. Abgehakte Listen fallen sofort aus der Summe (sie sind ja bereits erfasst); die Summe und das Feld aktualisieren sich direkt

## 1.26.0 – Juli 2026

### Neu
- 📊 **Einkauf auf Listen in der Statistik.** Ein neues Feld zeigt die Summe aller eingetragenen Einkaufspreise über alle offenen Einkaufslisten zusammen – so sieht man auf einen Blick, wie viel gerade auf den Listen gebunden ist. Archivierte Listen zählen nicht mit. Nur für Sammlerprofis sichtbar

## 1.25.2 – Juli 2026

### Behoben
- 🛒 **Listen-Ablauf in der Suche.** Wollte man einen Suchtreffer auf eine Liste setzen und den Preis eintippen, sprang das Detail-Popup auf. Ursache war der neue „Tipp auf die Karte öffnet Details"-Griff. Jetzt ignoriert er Eingabefelder und bleibt zu, solange in der Karte ein Formular (Preis, Listenauswahl) offen ist

## 1.25.1 – Juli 2026

### Behoben
- 🔎 **BrickLink-Daten schon bei der Namenssuche.** Bisher lieferte die Namenssuche nur Rebrickable-Nummern (fig-…), sodass im Detail-Popup weder Preise noch Sets oder Teile erschienen – die kamen erst nach „Übernehmen". Jetzt sucht das Popup selbst die passende BrickLink-Nummer über das Bild (mit Sicherheits-Angabe, z. B. „91 % sicher") und zeigt Preise, Sets und Teile sofort an. „Übernehmen" trägt gleich die gefundene Nummer ein

## 1.25.0 – Juli 2026

### Neu
- 🔎 **Detailansicht in der Suche.** Ein Tipp auf einen Suchtreffer öffnet jetzt ein Popup mit allem Wichtigen auf einen Blick: Jahr, Marktpreis (neu/gebraucht), ob die Figur schon in eurer Sammlung oder auf der Wunschliste ist, in welchen Sets sie vorkommt und – bei Minifiguren – die enthaltenen Teile. Übernehmen und Merken gehen direkt aus dem Popup. Die Aktionen an der Karte bleiben für den schnellen Griff erhalten

### Verbessert
- 🎨 **Teile mit Farbnamen.** Die Teileliste einer Minifigur zeigt jetzt zu jedem Teil den BrickLink-Farbnamen (z. B. „Black", „Light Nougat"). Die Farbtabelle wird einmalig von BrickLink geholt und 90 Tage zwischengespeichert

## 1.24.0 – Juli 2026

### Neu
- 🧩 **Teile einer Minifigur anzeigen.** Im Popup einer Minifigur gibt es jetzt „Enthaltene Teile anzeigen" – Torso, Kopf, Beine, Zubehör mit Farbe, Anzahl und Bild, jeweils mit Link zu BrickLink. Optional (nur auf Klick), spart Ladezeit und wird 30 Tage zwischengespeichert. Braucht einen BrickLink-Schlüssel und eine echte BrickLink-Nummer

## 1.23.4 – Juli 2026

### Behoben
- 🔎 **Suche zeigt beim ersten Tippen zuverlässig Treffer.** Bei schnellem Tippen konnte eine ältere, langsamere Such-Antwort eine neuere überholen und deren Ergebnisse überschreiben – dann blieb das Feld scheinbar leer oder zeigte zum halb getippten Wort passende Treffer. Jede Suche bekommt jetzt eine laufende Nummer; nur die jeweils **neueste** darf ihr Ergebnis anzeigen, ältere werden verworfen

## 1.23.3 – Juli 2026

### Behoben
- 🖼 **Doppelte Bilder jetzt wirklich weg.** BrickLink liefert dieselbe Figur über mehrere Endpunkte/Auflösungen (ItemImage, ML, das API-Bild) – die vorige Zusammenfassung erkannte nur den Protokoll-Unterschied. Jetzt gelten alle BrickLink-Bilder **derselben Nummer** als dasselbe Motiv; die Großansicht zeigt **ein** Bild und bevorzugt die (meist höher aufgelöste) API-Variante. Wirklich andere Quellen bleiben erhalten

## 1.23.2 – Juli 2026

### Verbessert
- ⭐ **Standard-Design kompakter.** Statt einer zweiten Knopfreihe markiert der Admin das Standard-Design jetzt mit einem **Stern** direkt am jeweiligen Design (⭐ = Standard, ☆ zum Umstellen). Die eigene Design-Wahl bleibt davon unberührt

## 1.23.1 – Juli 2026

### Verbessert
- 🖼 **Keine doppelten Bilder mehr in der Großansicht.** Die Katalogquellen liefern meist dasselbe Motiv unter leicht anderer URL – bisher tauchte es so zwei- bis dreimal in der Galerie auf. Gleiche Bilder werden jetzt zusammengefasst (Protokoll-unabhängig, ohne die redundante ML-Variante); es bleibt eins – mehrere nur, wenn sie sich wirklich unterscheiden

## 1.23.0 – Juli 2026

### Neu
- 🔢 **Sortierung nach BrickLink-Nummer** in der Sammlung (Sortier-Auswahl → „Nummer (A–Z)"). Praktisch, um Figuren/Sets in Nummernreihenfolge durchzugehen

## 1.22.0 – Juli 2026

### Neu
- 🎨 **Design pro Profil & Standard-Design der Instanz.**
  - Das gewählte Design wird jetzt **im Profil** gespeichert und gilt **auf allen Geräten**, auf denen man angemeldet ist – nicht mehr nur lokal im Browser
  - Der **Admin** kann unter Mehr → 🎨 Design ein **Standard-Design** festlegen: Es gilt für den Login-Bildschirm und für Benutzer, die noch keine eigene Wahl getroffen haben

## 1.21.2 – Juli 2026

### Behoben
- 🚪 Beim **Abmelden** blieb das Profil-Popup offen über dem Login stehen. Es wird jetzt zusammen mit der Abmeldung geschlossen (samt anderer offener Overlays), und der Login-Screen ist frei

## 1.21.1 – Juli 2026

### Behoben
- 🖱 **Nova/Galaxie:** Fuhr man in der linken Seitenleiste mit der Maus über den **aktiven** Menüpunkt, verschwand dessen Schrift. Der Hover-Schleier legte sich über den farbigen Hintergrund, sodass die (dunkle) Schrift nicht mehr zu sehen war. Der Hover überdeckt den aktiven Punkt jetzt nicht mehr – er bleibt lesbar

## 1.21.0 – Juli 2026

### Neu
- 📦 **Im Figur-Popup: alle Sets, in denen die Figur vorkommt** – nicht nur die eigenen. Unter „Kommt vor in:" stehen jetzt auch Sets, die man (noch) nicht besitzt, als BrickLink-Link; die eigenen bleiben als ✔-Badge mit Sprung in die Sammlung. Praktisch, um zu sehen, wo eine Figur sonst noch enthalten ist. Die Liste kommt von BrickLink (30-Tage-Cache), die eigenen Sets erscheinen sofort

## 1.20.2 – Juli 2026

### Verbessert
- 🧩 **Aufgeräumte Set-/Figuren-Karten:**
  - Bei **Sets** steht die Figuren-Vollständigkeit (👥 3/4) jetzt auf einer **eigenen Zeile**, statt dass das Icon am Zeilenende hängt und die Zahl darunter umbricht
  - Bei **Figuren** stehen die zugehörigen Sets („aus Set") nur noch im **Detail-Popup**, nicht mehr auf der Karte – das hält die Liste ruhiger

## 1.20.1 – Juli 2026

### Sonstiges
- 📖 **Handbuch und README aktualisiert.** README nennt jetzt die Preis-Herkunfts-Flagge (🇪🇺/🌍), dass Admins weitere Admins ernennen können und die moderne Darstellung (Detail-Popup, Produktbild als Kartenhintergrund). Im Handbuch sind die Rollen-Vergabe (Admin-/Profi-Knopf), das aufgeräumte Popup und ein Verweis auf das ↻ am Preisblock ergänzt

## 1.20.0 – Juli 2026

### Neu
- 👑 **Weitere Admins ernennen.** In der Benutzerverwaltung (Mehr → 👥 Benutzer verwalten) gibt es jetzt einen **Admin**-Knopf je Benutzer – so lässt sich jemand zum zweiten Admin machen oder die Rechte wieder entziehen. Bisher war nur der erste (bei der Ersteinrichtung angelegte) Benutzer Admin, ohne Möglichkeit, das zu ändern

  **Schutz:** Der **letzte** verbliebene Admin behält seine Rechte – so kann sich niemand versehentlich komplett aussperren

## 1.19.0 – Juli 2026

### Neu
- 🌐 **Externer Zugriff einrichten – direkt in der App** (Mehr → Externer Zugriff, Admin; Hinweis schon in der Ersteinrichtung). Trägt man seine Wunsch-Adresse und den **Cloudflare-Tunnel-Token** ein, baut die App daraus den fertigen `docker-compose`-Block zum Kopieren – so klappt der Zugriff von unterwegs **ohne Portfreigabe**

  **Sicher gedacht:** Die App startet den Tunnel *nicht* selbst (sie hat bewusst keinen Docker-Zugriff), sondern erzeugt nur die Konfiguration. Der Token **bleibt im Browser** und wird weder gespeichert noch verschickt. Details weiter im Handbuch, Kapitel 2.7

### Verbessert
- 🧩 In der Karten-Zeile „aus Set" (bzw. „fehlt zu eurem Set") steht das Label jetzt auf einer eigenen Zeile, die Set-Badges brechen sauber darunter um – gerade in den schmaleren, mehrspaltigen Kacheln liest sich das ruhiger

## 1.18.0 – Juli 2026

### Neu
- 🖼 **Produktbild als Karten-Hintergrund.** In der Sammlung schimmert das Bild jetzt als weich gezeichneter, dezenter Hintergrund von rechts in die Karte – zur Textseite ausgeblendet, damit alles gut lesbar bleibt. Gibt der Liste einen moderneren Look; Karten ohne Bild bleiben schlicht

### Verbessert
- 🧹 **Aufgeräumtes Artikel-Popup.** Deutlich weniger Knöpfe, klarere Aufteilung:
  - **Notizen speichern sich von selbst** – kurz nach dem Tippen und beim Schließen. Der „Notiz speichern"-Knopf entfällt, ein kurzes „✓ gespeichert" bestätigt
  - **Kaufpreis** speichert ebenso automatisch beim Verlassen des Feldes (oder mit Enter) – der „Speichern"-Knopf daneben entfällt
  - **Bild erneuern** ist jetzt ein kleines **↻-Symbol direkt am Bild** statt eines eigenen Knopfes
  - **Preise aktualisieren** sitzt als **↻ direkt am Preisblock** („Marktpreise") statt als großer Knopf
  - **Löschen nur noch an einer Stelle** – der Papierkorb bei der Anzahl. Der zusätzliche „Löschen"-Knopf unten ist weg
  - Übrig bleibt in der Aktionsleiste nur noch, was wirklich woanders hinführt (Preisverlauf, BrickLink)
- 🔀 **Ansichts-Umschalter klarer:** statt des kryptischen ▤/▦-Zeichens jetzt ein eindeutiges Symbol (Liste/Raster) samt Beschriftung auf breiten Schirmen; er zeigt, in welche Ansicht man wechselt
- 🧾 **Aufgeräumte Karten-Unterzeile:** Nummer und Jahr stehen jetzt in der oberen Zeile, Zustand und Ø-Preis (mit Herkunfts-Flagge) in der Zeile darunter. In den schmaleren, mehrspaltigen Kacheln liest sich das deutlich ruhiger als die bisherige lange Zeile

### Behoben
- 👓 **Lesbarkeit im Dunkeldesign:** Die kleinen „Neu"/„Gebraucht"-Preis-Badges hatten weiße Schrift auf gelbem Grund – jetzt dunkel und gut lesbar. Und die Beschriftung im Preisverlauf-Diagramm hatte einen weißen Rand, der auf dunklem Hintergrund „glühte" und die Zahlen verschwimmen ließ – der Rand ist im Dunkeldesign nun selbst dunkel, die Zahlen stehen klar

## 1.17.1 – Juli 2026

### Verbessert
- 🖥 In der **Listenansicht** der Sammlung standen auf breiten Bildschirmen die Kacheln einzeln über die volle Breite – mit viel Leerraum in der Mitte. Jetzt liegen sie nebeneinander (adaptiv zwei bis drei Spalten je nach Fensterbreite), sodass mehr auf einen Blick passt. Auf dem Handy unverändert einspaltig

## 1.17.0 – Juli 2026

### Neu
- ✨ **Drittes Design „Nova".** Neben „Klassisch" (hell) und „Galaxie" (dunkel, Sternenhimmel) gibt es jetzt ein **modernes Glas-Design**: tiefdunkler, blau schimmernder Hintergrund, durchscheinende Flächen mit weichem Licht, blauer Akzent und sanfte Schatten statt harter Kanten. Zu finden unter **Mehr → 🎨 Design**; die Wahl gilt wie gehabt pro Gerät

## 1.16.0 – Juli 2026

### Neu
- 🪟 **Artikel öffnen sich als Popup.** Tippt man in der Sammlung eine Karte an, erscheinen die Details jetzt in einem mittigen Fenster über der Liste, statt die Karte an Ort und Stelle aufzuklappen. Das ist gerade auf breiten Bildschirmen deutlich ruhiger – der Rest der Liste bleibt sichtbar, das Detail ist klar im Fokus

  Schließen per **✕**, Klick daneben oder **Esc**. Änderungen (Menge, Zustand, Notiz, Preis) werden beim Schließen direkt in die Liste übernommen. Auf dem Handy füllt das Popup nahezu den Bildschirm

## 1.15.0 – Juli 2026

### Neu
- 🇪🇺 **Flagge, wenn ein Preis nicht aus dem eingestellten Gebiet stammt.** Hat BrickLink im gewählten Land keine Verkäufe und die App ist auf **Europa** oder **weltweit** ausgewichen, steht jetzt eine kleine Flagge neben dem Ø-Preis: 🇪🇺 für Europa, 🌍 für weltweit. So sieht man auf einen Blick, welche Preise „echt deutsch" sind und welche aus einem breiteren Markt kommen

  Die Flagge erscheint sowohl in der Karten-Unterzeile als auch in der Detail-Preiskarte (dort mit Erklärung als Tooltip). Preise aus dem eingestellten Gebiet bleiben ohne Flagge

## 1.14.1 – Juli 2026

### Behoben
- 🖥 Auf dem Desktop lief eine **geöffnete Sammlungs-Karte** über die ganze Breite – Felder und Knöpfe wirkten riesig. Das Detailformular wird jetzt auf eine handliche Breite begrenzt und mittig gesetzt (beide Ansichten, Liste wie Raster). Am Handy unverändert

## 1.14.0 – Juli 2026

### Neu
- 🖥 **Desktop-Layout.** Auf breiten Bildschirmen (ab 960 px) wird aus der unteren Tab-Leiste eine **linke Seitenleiste** mit beschrifteten Symbolen, und der Inhalt nutzt die Fläche: Kennzahlen und Filter stehen nebeneinander, und die **Sammlung im Raster zeigt vier bis fünf Karten pro Reihe** statt zwei. Auf dem Handy bleibt alles unverändert – dieselbe Oberfläche, nur je nach Bildschirm anders verteilt (reines CSS, kein Umschalten, keine zweite App)

  Die Kamera-Fläche und das Erfassen-Formular bleiben angenehm schmal und mittig, damit sie nicht verloren über die ganze Breite laufen

## 1.13.0 – Juli 2026

### Behoben & Neu
- 💶 **Rückfall bei fehlenden Verkäufen jetzt zweistufig – und ein Preis-Bug behoben.** Gibt es im eingestellten Gebiet (z. B. Deutschland) keine Verkäufe, weitet die App den Preis erst auf **Europa** aus und erst dann auf **weltweit**. Bisher ging es direkt von Land auf weltweit

  **Der Bug dahinter:** BrickLink liefert bei „keine Verkäufe" den Durchschnitt als Text `0.0000` – also gerade *nicht* leer. Die App hielt das fälschlich für einen echten Preis und sprang gar nicht erst auf ein breiteres Gebiet. Ergebnis waren Artikel **ganz ohne Preis** (obwohl es woanders Verkäufe gab) und vereinzelte **0,00 €**. Beides ist behoben: geprüft wird jetzt der Zahlenwert

- 🔄 **„Preislose erneut abrufen"** (Mehr → Preisgebiet, Admin): holt für alle Artikel ohne Preis die Bewertung neu – mit dem neuen Rückfall Europa → weltweit. Läuft wie das Umrechnen in Häppchen mit Fortschritt. Artikel, die wirklich nirgends verkauft wurden, bleiben ehrlich als „ohne Preis" stehen, statt den Lauf endlos zu drehen

## 1.12.0 – Juli 2026

### Neu
- 🔔 **Hinweise auf dem Startbildschirm**: Ändert oder löscht BrickLink eine Nummer, die in eurer Sammlung steckt, steht das ab jetzt oben im Scannen-Tab – und bleibt dort stehen, bis es jemand wegklickt

  **Wie es auffällt:** Die App holt für jeden Artikel ohnehin alle 7 Tage Preise. Antwortet BrickLink für eine Nummer, die früher funktioniert hat, plötzlich mit „unbekannt", ist sie umbenannt oder gelöscht worden. Eine von Hand falsch eingetippte Nummer löst dagegen keinen Hinweis aus – die hat nie funktioniert

  **Neue Nummer finden:** Nur in diesem Fall schaut die App in den öffentlichen [BrickLink Catalog Change Log](https://www.bricklink.com/catalogLogs.asp) und sucht dort den Nummernwechsel oder die Zusammenlegung. Findet sie ihn, steht im Hinweis die neue Nummer und **„Nummer übernehmen"** trägt sie überall ein: Sammlung, Wunschliste, Einkaufslisten, Set-Verknüpfungen und Preisverlauf. Danach funktioniert der Preisabruf wieder

  **Findet der Log nichts**, bleibt der Hinweis trotzdem stehen – dann eben mit „Nummer gibt es nicht mehr" statt einer neuen Nummer. Der alte Preis bleibt erhalten, es geht nichts verloren

  Ein weggeklickter Hinweis kommt nicht wieder: Wer die Sache gesehen und entschieden hat, soll nicht bei jedem Preislauf erneut gefragt werden

## 1.11.0 – Juli 2026

### Neu
- 🐞 **Fehlerbericht** (Mehr → Fehlerbericht, Admin): Läuft in der App etwas schief, wird der Fehler automatisch im Hintergrund gemeldet und landet in dieser Liste – auch von den Geräten der anderen. Gleichartige Fehler werden zusammengefasst und gezählt, statt die Liste zu fluten. Niemand muss mehr beschreiben, „was da stand"

  **Issue auf Knopfdruck:** Ist ein GitHub-Token hinterlegt, legt ein Klick daraus ein Issue im Projekt an – mit Fehlertext, Stelle, App-Version und Browser. Ein zweiter Klick legt kein zweites Issue an, sondern öffnet das vorhandene

  **Sicherheit:** Der Token gehört ein *fine-grained* Token mit **Issues: Read and write** auf **nur diesem einen Repository** zu sein – mehr braucht die App nicht. API-Schlüssel und der GitHub-Token selbst werden aus jedem gemeldeten Text entfernt, bevor er die App verlässt

- 📋 **Bericht kopieren**: Die ganze Liste als Text in der Zwischenablage, falls man sie lieber woanders hinschickt

## 1.10.0 – Juli 2026

### Neu
- 🌍 **Preisgebiet wählbar** (Mehr → Preisgebiet, Admin): weltweit (wie bisher), **Deutschland**, **Österreich**, **Schweiz** oder **Europa**. Damit lassen sich die Ø-Preise am eigenen Markt orientieren statt am weltweiten Durchschnitt

  **Rückfall auf weltweit:** Gerade bei selteneren Figuren gibt es in einem einzelnen Land oft gar keine Verkäufe. Findet BrickLink dort nichts, nimmt die App automatisch den weltweiten Durchschnitt – so bleibt kein Artikel ohne Preis

  **Bestehende Sammlung umstellen:** Nach dem Wechsel zeigt die Karte, wie viele Artikel noch Preise aus dem alten Gebiet haben, und rechnet sie auf Knopfdruck um. Das läuft in Häppchen mit Fortschrittsanzeige, weil jeder Artikel zwei BrickLink-Abrufe kostet und BrickLink ein Tageskontingent hat – bei großen Sammlungen kann man es über mehrere Tage laufen lassen, der Stand bleibt erhalten

## 1.9.9 – Juli 2026

### Sonstiges
- 📖 **Handbuch und README aktualisiert**: Sie standen noch auf dem Stand von 1.6.9. Ergänzt sind jetzt fehlende Set-Figuren, die Kennzeichnung „fehlt zu eurem Set", Bild nachladen, Design-Auswahl (Klassisch/Galaxie), Quellen & Rechtliches, die Such-Verbesserungen (ab 3 Zeichen, 10 Treffer pro Seite, Lupe und ✕), die Kennzahl im Preis-Protokoll sowie das komplette Kapitel zum Update aus der App heraus samt Einrichtung des Helfers

## 1.9.8 – Juli 2026

### Verbessert
- 🧱 Der **drehende Klemmbaustein** erscheint jetzt auch beim Laden der **Statistik** und des **Preis-Protokolls** – vorher stand dort nur „Lade …"

## 1.9.7 – Juli 2026

### Behoben
- 🔄 Nach einem Update **lud sich die App nicht immer selbst neu** und blieb auf dem alten Stand. Der Neustart wurde nur erkannt, solange der Sperrbildschirm sichtbar war – lag der Tab während des Updates im Hintergrund oder war das Handy gesperrt, standen die Zeitgeber still, die Sperre erschien nie und beim Zurückkommen griff die Erkennung nicht mehr. Jetzt merkt sich jede Seite die Startzeit ihres Servers und lädt neu, sobald der Server sich seither neu gestartet hat – unabhängig von der Sperre

## 1.9.6 – Juli 2026

### Behoben
- 🔎 Der **Status des Update-Helfers** steckte im Block „Update verfügbar" und war damit unsichtbar, solange die App aktuell war – ausgerechnet dann, wenn man die Einrichtung prüfen will. Er steht jetzt **immer** in der Karte „Version & Updates": „✅ Update-Helfer läuft" bzw. der Hinweis, woran es hakt

## 1.9.5 – Juli 2026

### Sonstiges
- 📄 Anleitung für **mehrere Instanzen** korrigiert: Empfohlen ist jetzt **eine Aufgabe je Instanz**. Wer alles in eine Aufgabe schreibt, braucht `|| true` am Zeilenende – bricht die erste Zeile mit einem Fehler ab, führt der Aufgabenplaner die zweite sonst nicht mehr aus, und die zweite Instanz bekommt nie ein Lebenszeichen

## 1.9.4 – Juli 2026

### Behoben
- 🔑 Das Lebenszeichen des Update-Helfers wird jetzt ausdrücklich lesbar angelegt (`644`). Je nach Einstellung des Servers legte root es sonst als `600` an – dann hätte die App es nicht gelesen, sobald der Container einmal nicht als root läuft, und hätte fälschlich „Helfer nicht eingerichtet" gemeldet

## 1.9.3 – Juli 2026

### Behoben
- 🛠 Lief `update-watch.sh` ohne Root-Rechte, brach es mit einem nichtssagenden „Permission denied" ab. Jetzt erklärt es im Klartext, dass es als `root` laufen muss (von Hand mit `sudo`, im Aufgabenplaner unter „Allgemein"). Der `data`-Ordner gehört Docker und damit root – für `docker compose` braucht das Skript diese Rechte ohnehin

## 1.9.2 – Juli 2026

### Verbessert
- 🔎 Meldet sich der Update-Helfer nicht, sagt die App jetzt **woran es liegt**: entweder „hat sich noch **nie** gemeldet" (dann stimmt meist der Pfad im Skriptfeld nicht oder die Aufgabe läuft nicht als `root`) oder „lief zuletzt **vor X Stunden**" (dann ist sie eingerichtet, läuft aber nicht jede Minute – häufigster Grund: „Letzte Ausführungszeit" steht auf `00:59` statt `23:59`)

## 1.9.1 – Juli 2026

### Verbessert
- 🔒 **Schrift wird jetzt mitgeliefert** statt vom Google-CDN geladen. Damit werden beim Öffnen der App **keine Besucherdaten mehr an Dritte übertragen** – und die App funktioniert auch ohne Internet vollständig, denn bisher fehlte offline die Schrift (Nunito, SIL Open Font License 1.1)
- ℹ️ Neue Karte **Mehr → Quellen & Rechtliches**: woher Daten und Bilder stammen (Rebrickable, BrickLink, Brickognize), der Hinweis, dass beim Abfotografieren das Foto zur Erkennung übertragen wird, sowie Marken-, Schrift- und Lizenzangaben. Brickognize ist jetzt auch im README genannt

## 1.9.0 – Juli 2026

### Neu
- 🚀 **Update aus der App anstoßen** (Mehr → Version & Updates, nur Admin): sofort, in 1 oder in 5 Minuten. Alle angemeldeten Browser zeigen einen Countdown („bitte Eingaben abschließen"), danach einen Sperrbildschirm – und laden sich selbst neu, sobald der Server wieder da ist. Solange der Countdown läuft, lässt sich das Update abbrechen

  Die App führt das Update **nicht selbst** aus: Sie legt nur eine Markierung im Datenverzeichnis ab, die der neue Helfer `update-watch.sh` auf dem Server aufgreift. So braucht die App keinen Docker-Zugriff (das wäre faktisch Root auf dem Server)

  **Vollständig optional**: Ohne Einrichtung ändert sich nichts. Der Helfer hinterlässt bei jedem Lauf ein Lebenszeichen – nur wenn das frisch ist, bietet die App das Update überhaupt an. Sonst steht dort lediglich ein Hinweis, wie man es einrichten kann. Anleitung (auch für mehrere Instanzen) im README

## 1.8.4 – Juli 2026

### Verbessert
- ⚡ **Sammlung lädt deutlich schneller**: Ein fehlender Datenbank-Index sorgte dafür, dass die Zuordnung „steckt in diesen Sets" für jeden Eintrag die ganze Set-Tabelle durchsuchen musste. Gemessen bei 800 Figuren und 250 Sets: **49 ms → 3 ms**. Der Index wird beim nächsten Start automatisch angelegt

### Behoben
- 🔎 In den Suchergebnissen bekamen nur die **ersten 8 Treffer** ihre Kennzeichnung („✔ in Sammlung", „🧩 fehlt zu eurem Set"). Seit der Umstellung auf 10 Treffer pro Seite plus Nachladen fehlte sie damit ausgerechnet bei den späteren Treffern – jetzt werden alle angezeigten gekennzeichnet

### Sonstiges
- ✅ Testabdeckung von 28 auf **48 Fälle** erweitert: fehlende Set-Figuren, Katalogsuche mit Seiten, Kennzahl „Preisabruf älter als 7 Tage"

## 1.8.3 – Juli 2026

### Neu
- 🖼 **Bild nachladen** für Einträge in der Sammlung: Fehlt einem Eintrag das Bild (oder passt es nicht), holt ein Knopf im Detailbereich das aktuelle Katalogbild von BrickLink. Bisher ging das nur bei Einträgen ganz ohne BrickLink-Nummer

## 1.8.2 – Juli 2026

### Behoben
- 🖼 Der Knopf **„Namen & Bilder nachladen"** stand ganz am Ende der Liste und war bei vielen fehlenden Figuren praktisch unerreichbar – er steht jetzt **oben**, direkt unter der Überschrift
- 🔄 `app.js` wurde beim Ausliefern nie neu versioniert; Geräte konnten dadurch eine ältere Programmversion aus dem Zwischenspeicher behalten
- 🧱 Bilder, die sich nicht laden lassen, zeigen jetzt den Baustein-Platzhalter statt eines kaputten Symbols

## 1.8.1 – Juli 2026

### Behoben
- 🖼 In der Übersicht „Fehlende Set-Figuren" fehlten bei vielen Einträgen **Name und Bild** (nur die Nummer war zu sehen). Ursache: Diese Angaben kommen aus dem gespeicherten Set-Inhalt, der bei älteren Sammlungen noch ohne sie angelegt wurde. Statt sie still im Hintergrund und stark gedrosselt nachzuladen, zeigt die App jetzt offen an, bei wie vielen Sets Details fehlen – mit dem Knopf **„🔄 Namen & Bilder nachladen"**, der sie mit Fortschrittsanzeige holt

## 1.8.0 – Juli 2026

### Neu
- 🧩 **Übersicht „Fehlende Set-Figuren"** (Listen): zeigt über alle eigenen Sets hinweg, welche Minifiguren noch fehlen – mit Anzahl, zugehörigen Sets, geschätztem Nachkaufpreis und Aktionen (einzeln oder alle auf die Wunschliste, CSV, Drucken). Der Bedarf berücksichtigt, wie oft ihr ein Set besitzt
- 🔎 **Suchergebnisse markieren fehlende Set-Figuren**: Gehört eine gefundene Figur zu einem eurer Sets und fehlt dort noch, steht statt „in Sets" jetzt deutlich **„fehlt zu eurem Set"** – praktisch beim Stöbern auf dem Flohmarkt

### Sonstiges
- Set-Inhalte speichern jetzt auch Name und Bild der Figuren, damit die Übersicht ohne BrickLink-Abruf funktioniert (ältere Einträge werden im Hintergrund nachgezogen)

## 1.7.1 – Juli 2026

### Behoben
- 🖼 Im Design „Galaxie" wirkten die **Bildflächen unruhig**: Katalogfotos bringen meist einen weißen Hintergrund mit, der als heller Block auf der dunklen Kachel stand. Die Bildkachel ist dort jetzt weiß, sodass Foto und Fläche nahtlos verschmelzen

## 1.7.0 – Juli 2026

### Neu
- 🌌 **Zweites Design „Galaxie"**: ein dunkles, weltraum-inspiriertes Aussehen mit Sternenhimmel und leuchtenden Akzenten – umschaltbar unter **Mehr → Design**. „Klassisch" bleibt Standard, die Auswahl gilt pro Gerät und wird gemerkt

### Behoben
- 🖨 In den **Druckexporten** (Sammlung, Wunschliste, Verkaufsliste) stand in der Kopfzeile immer „Finn's Brickfolio" – jetzt erscheint dort der eingestellte Anzeigename

## 1.6.21 – Juli 2026

### Verbessert
- 🔍 Suchfelder mit **Lupen-Icon** statt „Suchen"-Text – der Platzhalter lautet jetzt kurz „Name oder Nummer" und wird nicht mehr abgeschnitten
- 🔍 Auch das Namensfeld beim **manuellen Erfassen** hat jetzt das Lupen-Icon
- ✕ **Löschen-Knopf** in beiden Suchfeldern: leert die Eingabe mit einem Tipp und stellt die vollständige Liste wieder her

## 1.6.20 – Juli 2026

### Verbessert
- 🔎 Katalogsuche: **10 Treffer pro Seite** (statt 20), „Weitere Ergebnisse laden" holt jeweils 10 nach
- 🏷 Beim manuellen Erfassen steht der **Typ (Minifigur/Teil/Set) jetzt direkt neben dem Namensfeld**

## 1.6.19 – Juli 2026

### Verbessert
- 🔎 Die **Katalogsuche** zeigt jetzt alle Treffer seitenweise: 20 pro Seite mit Anzeige „X von Y" und einem Knopf **„Weitere Ergebnisse laden"** (statt nur 8 fester Treffer)

## 1.6.18 – Juli 2026

### Verbessert
- 🔎 Die **Katalog-/Namenssuche** (neue Figuren/Sets) startet erst ab **3 Zeichen** – bei kürzerer Eingabe erscheint ein kurzer Hinweis. Das vermeidet unnötige Suchanfragen bei 1–2 Zeichen

## 1.6.17 – Juli 2026

### Verbessert
- 🕒 Das **Preis-Protokoll** (Mehr) zeigt jetzt an, bei wie vielen Artikeln in der Sammlung der Preisabruf älter als 7 Tage ist

## 1.6.16 – Juli 2026

### Neu
- 🧩 **Wunschliste zeigt fehlende Set-Figuren**: Steht eine Figur auf der Wunschliste, die zu einem Set in eurer Sammlung gehört und die ihr noch nicht habt, wird sie mit „fehlt zu eurem Set" gekennzeichnet – ein Tipp auf das Set springt direkt dorthin

## 1.6.15 – Juli 2026

### Behoben
- 📐 In der **Raster-Ansicht** sind zwei Karten einer Reihe jetzt immer gleich hoch (die kürzere dehnt sich auf die Höhe der höheren), statt unterschiedlich hoch zu stehen

## 1.6.14 – Juli 2026

### Verbessert
- 🧱 Die Lade-Anzeige der Sammlung zeigt jetzt einen **drehenden Klemmbaustein** statt eines Kreises

### Behoben
- 🎯 Die Lade-Anzeige ist in der **Raster-Ansicht** wieder mittig (war nach links versetzt)

## 1.6.13 – Juli 2026

### Verbessert
- ⚡ **Sammlung öffnet spürbar flüssiger**: Die Karten laden zunächst nur den Kopf; der Detailbereich einer Karte wird erst beim Aufklappen erzeugt. Dadurch entstehen bei großen Sammlungen rund **70 % weniger Seitenelemente**, und die Ansicht reagiert beim Öffnen (Antippen, Suchen) fast sofort statt erst nach ein paar Sekunden

## 1.6.12 – Juli 2026

### Verbessert
- ⏳ **Lade-Anzeige in der Sammlung**: Beim Öffnen des Sammlung-Tabs erscheint sofort ein Spinner „Sammlung wird geladen …", bis die Liste aufgebaut ist – kein irritierender Moment mehr, in dem die Ansicht wie eingefroren wirkt. Die Suchleiste ist dabei bereits nutzbar

## 1.6.11 – Juli 2026

### Behoben
- ✅ **Kein doppeltes Nachfragen des Zustands** beim Verbuchen aus einer Liste: „Da! Ab in die Sammlung" übernimmt jetzt direkt den bereits am Listeneintrag gewählten Zustand (neu/gebraucht). Sammlerprofis bestätigen nur noch den Einkaufspreis, alle anderen verbuchen mit einem Klick

## 1.6.10 – Juli 2026

### Sonstiges
- ✅ **Automatisierte Tests** für die fehleranfälligsten Bereiche (Ø-Preis-Fallback, Doppelzählung von Set-Figuren, anteilige Angebotsverteilung, Verbuchen/Rückgängig von Einkaufslisten) samt **CI**, die bei jedem Push und Pull Request läuft
- 🧹 Aufräumarbeiten im Backend (doppelte Setup-/Me-Routen entfernt, Rechenkern der Angebotsverteilung in eine testbare Funktion gelöst) – keine Änderung am Verhalten

## 1.6.9 – Juli 2026

### Neu
- 👥 **Figuren beim Set übernehmen**: Kommt ein Set in die Sammlung (Foto, Suche, Wunschliste, Einkaufsliste oder manuell), fragt die App, welche der enthaltenen Minifiguren dabei sind – alle, keine oder eine Auswahl, mit eigener Zustandswahl

### Geändert
- 💶 **Wertberechnung ohne Doppelzählung**: In eigenen Sets steckende Figuren sind im Set-Preis schon enthalten und zählen im Gesamtwert nicht mehr doppelt. Beim Filter „Figuren" (oder „Sets") erscheint weiterhin der volle Wert dieser Gruppe; Stückzahl, Top 10 und bezahlt/Gewinn bleiben unverändert
- ❓ Die Wertberechnung ist jetzt in der Hilfe und im Handbuch ausführlich erklärt; die Statistik weist den herausgerechneten Betrag offen aus

## 1.6.8 – Juli 2026

### Behoben
- 📊 Das Diagramm „Wert nach Erscheinungsjahr" reagiert jetzt auch auf **Antippen** (Touch): Jahr, Wert und Stückzahl erscheinen unter dem Diagramm, der gewählte Balken wird hervorgehoben

### Sonstiges
- 🇬🇧 Englisches README mit Sprach-Umschalter und aktualisierten Screenshots

## 1.6.7 – Juli 2026

### Neu
- 🗒 Beim Verbuchen von einer Liste wird der Listenname in die Notizen des Sammlungs-Eintrags übernommen (vorhandene Notiz bleibt erhalten)

### Behoben
- 📋 Verkaufsliste beschriftet zurückbehaltene Figuren jetzt korrekt: „für Sets reserviert" nur bei echtem Set-Bedarf, sonst „1 behalten"

## 1.6.6 – Juli 2026

### Neu
- 🏷 Konfigurierbarer Anzeigename in Logo und Fenstertitel (Mehr → Anzeigename, Admin); Standard bleibt „Finn"

## 1.6.5 – Juli 2026

### Neu
- 💶 Kaufpreis („Bezahlt") direkt beim Abfotografieren und manuellen Erfassen

## 1.6.4 – Juli 2026

### Neu
- 📇 Raster-Ansicht für die Sammlung (2 pro Reihe, Mengen-Badge, Auswahl wird gemerkt)
- 🔢 Im Raster steht beim Öffnen die Mengeneinstellung oben

## 1.6.3 – Juli 2026

### Neu
- 🖼 Scannen per Drag & Drop und Zwischenablage (Strg/Cmd+V)

### Verbessert
- 💶 Einkaufspreis direkt im 🛒-Dialog
- 📈 Manuelle Preisabrufe aktualisieren den jüngsten Verlaufspunkt

### Behoben
- Karten-Zahlen nach manuellem Preisabruf sofort aktuell (NaN-Fix)

## 1.6.2 – Juli 2026

### Verbessert
- 🕒 Uhrzeit an den automatischen Sicherungen in der Auswahlliste

## 1.6.1 – Juli 2026

### Verbessert
- 💶 Einkaufspreis direkt im 🛒-Dialog erfassbar
- 📈 Manuelle Preisabrufe aktualisieren den jüngsten Verlaufspunkt
- 🛡 Zustands-Migration gehärtet

### Behoben
- Karten-Zahlen nach manuellem Preisabruf sofort aktuell (NaN-Fix)

## 1.6.0 – Juli 2026

### Neu
- 🏷 Getrennte Sammlung-Einträge je Zustand (automatische Migration)
- ♻️ Zusammenführen beim Zustandswechsel auf einen vorhandenen Zustand
- 📦 Verkaufslisten-Reservierung je Figur über beide Zustände

## 1.5.1 – Juli 2026

### Verbessert
- 🛒 Einkaufslisten-Karten einklappbar (standardmäßig zu, Zustand wird gemerkt)

## 1.5.0 – Juli 2026

### Neu
- 💾 Automatische tägliche Sicherung nach data/backups/ (BACKUP_KEEP, Standard 14)
- ↩️ Tagesstände direkt in der App wiederherstellen (mit automatischer Sicherheitskopie)
- ⬇️ Tagesstände aus der App herunterladen

### Verbessert
- 🗂 Mehr-Tab-Karten aufklappbar (Zustand wird gemerkt)

## 1.4.6 – Juli 2026

### Verbessert
- 📸 README mit Screenshots
- 🔄 Update-Hinweis mit generischem Pfad

## 1.4.5 – Juli 2026

### Verbessert
- ✏️ Einkaufslisten umbenennen (Stift am Listennamen, Sammlerprofi)
- ✔ Verbuchen-Knopf heißt jetzt „Da! Ab in die Sammlung"

## 1.4.4 – Juli 2026

### Verbessert
- 🗂 Mehr-Tab aufgeräumt: klare Karten für Export, Sammlerprofi, API-Schlüssel, Benutzer, Sicherung und Version

## 1.4.2 – Juli 2026

### Verbessert
- 👤 **Profil als Popup**: Der Anmeldename oben rechts ist antippbar und öffnet Anzeigename ändern, Passwort ändern und Abmelden – der Mehr-Tab ist entsprechend aufgeräumt
- ❓ Hilfe-Knopf sitzt wieder rechts neben dem Namen

## 1.4.1 – Juli 2026

### Verbessert
- ❓ **Hilfe als Popup**: Über den ?-Knopf im Header von jedem Tab aus erreichbar – als Overlay mit allen Abschnitten; die bisherige Hilfe-Karte im Mehr-Tab entfällt

## 1.4.0 – Juli 2026

### Neu
- 🛒 **Listen-Hinweis beim Scannen**: Vorschläge zeigen ein Badge, wenn der Artikel bereits auf einer aktiven Einkaufsliste steht – Schutz vor Doppel-Einplanung am Stand
- 🏷 **Zustandswahl beim Drauflegen**: Im 🛒-Dialog lässt sich Gebraucht/Neu direkt wählen; gleiche Artikel in unterschiedlichem Zustand sind getrennte Listen-Zeilen mit korrekten Marktwerten

## 1.3.0 – Juli 2026

### Neu
- 🔄 **Update-Hinweis in der App**: „Version & Updates" im Mehr-Tab (Admin) prüft gegen GitHub-Releases und meldet neue Versionen – mit Release-Notes-Link und fertigem Update-Befehl
- 🛠 **update.sh**: Ein-Befehl-Update direkt von GitHub (ohne git), mit automatischem Datenbank-Schnappschuss
- ⚙️ **Angebots-Vorschlag einstellbar** (Mehr-Tab, Sammlerprofi): Prozentsatz vom Marktwert statt fester 60 %
- 🧱 Favicon ergänzt (kein 404 mehr in der Browser-Konsole)

## 1.2.1 – Juli 2026

### Behoben
- 🐳 `docker-compose.example.yml` war nach dem Auskommentieren der Admin-Variablen ungültig („environment must be a mapping")

## 1.2.0 – Juli 2026
## Neu
- 🚀 **Ersteinrichtung im Browser**: Beim allerersten Start (leere Datenbank) führt Brickfolio durch das Anlegen des Admin-Kontos – kein Default-Passwort, kein Editieren der docker-compose.yml mehr nötig. `ADMIN_USER`/`ADMIN_PASSWORD` bleiben als optionale Variablen für unbeaufsichtigte Setups erhalten.

## Verbessert
- 📖 README, Handbuch und docker-compose.example.yml an den neuen Erststart angepasst


## 1.1.0 – Juli 2026
## Neu
- 📥 **CSV-Import** für Sammlerprofis (Mehr → Export & Druck) – mit Beispiel-CSV, toleranter Spaltenerkennung und Fehlerbericht je Zeile; vorhandene Artikel werden zusammengeführt
- ❓ **In-App-Hilfe** im Mehr-Tab: Erste Schritte, Schritt-für-Schritt-Anleitung zum Beschaffen der BrickLink-/Rebrickable-API-Schlüssel (inkl. Shop-Pflicht und IP-Feldern), Rollen, Flohmarkt-Ablauf, Symbole
- 🛒 **Neue Einkaufsliste direkt aus dem Scan-Dialog** anlegen – mit vorausgefülltem Namen „Flohmarkt <Datum>"; die Listenauswahl erscheint jetzt immer, damit Funde nicht versehentlich auf der falschen Liste landen

## Verbessert
- 📊 Statistik auf Mobilgeräten: Kennzahlen-Chips brechen sauber um, Beträge skalieren, Chart-Beschriftungen mit weißem Halo

## Behoben
- Frontend-Crash durch fehlende Funktionen nach fehlerhaftem Update (betroffen war nur der Zwischenstand 81)


## 1.0.0 – Juli 2026

Erste veröffentlichte Version, entstanden aus 75 internen Updates.

- Scannen (Brickognize) & Suche (Rebrickable/BrickLink), Sets & Figuren
- Sammlung mit Mengen, Zustand, Notizen, Galerie, Preisverlauf pro Artikel
- Set-Vernetzung: Vollständigkeits-Anzeige, enthaltene Figuren,
  „fehlende auf die Wunschliste"
- Wunschliste mit Preis-Widgets und „Gekauft"-Übernahme
- Sammlerprofi-Modus: Kaufpreise (automatisch ⚙️ / manuell ✏️ mit Datum),
  Gewinn-Anzeige, Einkaufslisten mit Marktwert, Einzel-Einkaufspreisen,
  Gesamtangebot (anteilige Verteilung, 60-%-Vorschlag) und Auto-Archiv,
  Verkaufsliste (Doppelte) mit Set-Reservierung
- Statistik-Tab: Kennzahlen, Wertentwicklung, Aufteilung, Wert nach Jahr,
  Top 10, Profi-Wertsteigerungen
- Mehrbenutzer mit Rollen, JSON-Komplettsicherung, CSV-Export, Drucklisten,
  PWA mit sauberem Cache-Verhalten
