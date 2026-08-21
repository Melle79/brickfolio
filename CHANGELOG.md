# Changelog

## 2.35.0 – August 2026

### Neu
- 🎨 **Auch die Art der Figur kommt jetzt aus dem Bild**, nicht nur die
  Farbe. „Soldat", „Droide", „Alien" – vieles davon steht in keinem Namen:
  `R-3PO Protocol Droid` nennt keine Farbe, `Wicket (Ewok)` keine Art. Erst
  mit beidem findet „roter Droide", was gemeint ist.

  **Das ist eine Rücknahme.** 2.34.0 fragte bewusst nur nach Farben, weil
  `minicpm-v` die Art in zwei von drei Proben verfehlte und Darth Vader für
  einen Droiden hielt. Diese Messung stammte aus einer Zeit, in der es das
  beste verfügbare Modell war. Mit `qwen3-vl` sieht es anders aus: an zehn
  echten Figuren aus dem Abzug **zehn Treffer** – Stormtrooper → Soldat,
  Wookiee → Alien, R2-D2 → Droide, Luke im Fluganzug → Pilot, Yoda → Alien,
  Leia → Mensch.

  Die Einschränkung hing also am Modell, nicht an der Aufgabe. Wer ein
  schwächeres einstellt, bekommt entsprechend schwächere Antworten – die
  landen dann als Rauschen im Suchtext. Das ist der Preis der freien Wahl
  und steht so im Handbuch.

  Art und Farbe stehen in getrennten Spalten, damit sich eines verwerfen
  lässt, ohne das andere zu verlieren.

## 2.34.1 – August 2026

### Behoben
- 🧠 **Denkmodelle antworten woanders hin.** `qwen3-vl` legt seine Antwort
  in `thinking` ab; `content` bleibt leer, und `think: false` ändert daran
  nichts. Für die App sah das aus, als liefere das Modell gar nichts –
  ausgerechnet das beste Bildmodell im Haus wirkte kaputt, obwohl die
  richtige Antwort dastand, nur im falschen Feld.

  Ist `content` leer, wird jetzt `thinking` gelesen. Wo beides steht, zählt
  weiter `content`: Das Denkfeld ist der Notnagel, nicht die Quelle.

  Gemessen am 21.08.2026 gegen dieselben drei Figuren – `qwen3-vl` erkennt
  R-3PO als Droiden, den AT-AT-Fahrer als Soldaten und Darth Vader
  **namentlich**, bei richtigen Farben in allen drei Fällen. `gemma3:12b`
  liegt knapp dahinter, `qwen2.5vl:7b` und `minicpm-v` deutlicher.

## 2.34.0 – August 2026

### Neu
- 🎨 **Farben aus den Katalogbildern.** Zweiter Durchgang nach dem Abzug:
  Die lokale KI sieht sich die Bilder an und schreibt die Farben dazu. Viele
  BrickLink-Namen nennen keine – „R-3PO Protocol Droid" sagt nirgends „rot".
  Danach findet „roter Protokolldroide" beides: die Art aus dem Namen, die
  Farbe aus dem Bild.

  **Nur Farben, mit Absicht.** Nach der Art der Figur gefragt, lag
  `minicpm-v` in keiner von drei Proben richtig, `gemma3:12b` in zwei –
  und die Art steht ohnehin schon im Namen. Sie hier noch einmal raten zu
  lassen brächte nur Fehler hinein.

  Auch ein leeres Ergebnis wird festgehalten, sonst versuchte der nächste
  Lauf dieselbe Figur wieder und käme nie ans Ende.

- 🖼 **Das Modell fürs Bilderansehen ist getrennt einstellbar.** Übersetzen
  und Bilder ansehen sind verschiedene Aufgaben, und die besten Modelle
  dafür sind verschiedene.

  In beiden Listen stehen nur noch **sinnvolle** Modelle: Code-Modelle
  fallen raus. Für Bilder stehen die bildfähigen oben und tragen ein 👁.
  **Sortiert, nicht gefiltert** – `gemma3:12b` meldet Ollama gegenüber gar
  keine Bildfähigkeit und ist trotzdem das beste im Haus. Wer hart nach dem
  Merkmal filtert, versteckt den Sieger.

### Behoben
- 📚 **Der Abzug speicherte keine Bildadresse.** Treffer aus dem eigenen
  Abzug wären ohne Bild geblieben, obwohl BrickLink sie in derselben
  Antwort mitliefert. Bestehende Zeilen werden beim Start nachgetragen –
  ohne einen einzigen zusätzlichen Abruf, denn die Adresse folgt der Nummer
  (und der Bildserver unterscheidet nicht zwischen Groß- und
  Kleinschreibung). Fehlt sie in der Antwort, wird sie ebenso gebildet.

## 2.33.1 – August 2026

### Behoben
- 📚 **Die Karte des Katalog-Abzugs sprach noch von Star Wars.** Sie hieß
  „Katalog-Abzug (Star Wars)" und versprach „rund 25 Minuten" – beides war
  seit 2.33.0 falsch: Sie kann alle Themen, und die 25 Minuten stammten aus
  einer Schätzung mit 0,5 s je Abruf.

  Gemessen sind es **0,38 Abrufe je Sekunde** – BrickLink antwortet unter
  Dauerlast langsamer als bei Einzelabfragen. Das heißt rund **eine Stunde
  je 1.500 Nummern**, für alle sieben Themen zusammen etwa fünf. Handbuch
  und Oberfläche nennen jetzt diese Zahl.

## 2.33.0 – August 2026

### Neu
- 📚 **Der Katalog-Abzug kann mehrere Themen.** Bisher stand `sw` fest im
  Knopf. Jetzt trägt man sie mit Komma ein – `sw, cty, njo` – und sie laufen
  **nacheinander** ab, mit Fortschritt und Warteschlange in der Anzeige.

  Nacheinander, nicht nebeneinander: Alle Läufe teilen sich denselben
  BrickLink-Zugang. Zwei gleichzeitig hieße doppelter Takt – die Drosselung
  wäre ausgehebelt, für die es hier gute Gründe gibt.

  Bricht ein Lauf mit einem Kontingentfehler ab (`429`), bleiben auch die
  folgenden Themen stehen. Der Zugang ist derselbe; weiterzumachen würde das
  Problem nur verlängern.

  Als Präfix sind nur Buchstaben zugelassen – es wandert in eine Adresse,
  und `../` hätte dort nichts zu suchen.

  Gemessene Größenordnungen: `cty` über 2.000 Nummern, `njo` und `sh` je
  1.000–2.000, `cas`, `hp` und `col` je unter 500. Beim gemessenen Takt von
  0,38 Abrufen je Sekunde sind das für alle zusammen rund fünf Stunden –
  abbrechbar und fortsetzbar, also gut über mehrere Abende zu verteilen.

## 2.32.0 – August 2026

### Neu
- 📚 **Ein eigener Abzug des BrickLink-Katalogs (Star Wars).** Damit findet
  die Suche endlich, was man nur beschreiben kann: „Protokolldroide" führt
  zu `R-3PO Protocol Droid`. Über den gewöhnlichen Katalog ging das nicht –
  Rebrickable nennt dieselbe Figur schlicht `R-3PO`, ohne ein einziges Wort
  zum Suchen. Kein Modell muss dafür etwas wissen; gesucht wird in eigenem
  Text.

  Der Abzug läuft die Nummern der Reihe nach ab (`sw0002`, `sw0003`, …).
  Eine Auflistung einer Kategorie bietet BrickLink nicht an – geprüft: dort
  gibt es nur das Nachschlagen einer einzelnen Nummer. Gemessen liegen die
  Nummern dicht: Von `sw0002` bis etwa `sw1500` fehlt praktisch keine.

  **Gedrosselt auf einen Abruf je Sekunde**, rund 25 Minuten. Das ist keine
  Höflichkeit gegenüber BrickLink, sondern Selbstschutz: Es ist derselbe
  Zugang, über den die Preise laufen. Ein Durchlauf mit Vollgas könnte das
  Tageskontingent aufbrauchen – und dann stünde der Scanner ohne Preise da.

  Jederzeit anhaltbar, der Fortschritt bleibt: Zwanzig Minuten Arbeit dürfen
  nicht verfallen, nur weil jemand gestoppt hat. Lücken in der Nummerierung
  beenden den Lauf nicht (25 am Stück gelten als Ende), ein anderer Fehler
  als „gibt es nicht" dagegen sofort – `429` heißt Kontingent erschöpft, und
  stur weiterzulaufen machte das schlimmer.

  Findet der eigene Abzug etwas, wird Rebrickable gar nicht mehr gefragt.

### Behoben
- Der Vorfilter der Abzugssuche benutzte den rohen Namen, der Vergleich
  danach die satzzeichenfreie Form – „c3 po" fand `C-3PO` deshalb nicht,
  weil `LIKE '%c3%'` am Bindestrich scheitert. Beide benutzen jetzt dieselbe
  Elle.

## 2.31.1 – August 2026

### Geändert
- 📖 **Die gelernten Begriffe haben ein eigenes Fenster.** In den
  Einstellungen stand die vollständige Liste – bei ein paar Zeilen ging das,
  aber sie wächst mit jedem Suchlauf, und ein geplanter Durchlauf über die
  BrickLink-Nummern brächte Tausende auf einen Schlag. Die Einstellungen
  wären damit unbrauchbar geworden.

  Dort steht jetzt nur die Bilanz („38 Begriffe gelernt, davon 12 eigene").
  **Ansehen und pflegen** öffnet die Liste mit Suchfeld, seitenweise zu 25.
  Gesucht wird in beiden Richtungen: „ritter" über den deutschen Begriff,
  „Knight" über das, was dabei herauskommt – wer eine Zeile korrigieren
  will, weiß mal das eine und mal das andere.

  Die Bilanz gilt dabei immer für alles, nie für die gefilterte Sicht: Sonst
  sagte „12 eigene" plötzlich etwas anderes, nur weil jemand etwas ins
  Suchfeld getippt hat.

  Die Liste trägt jetzt dieselbe Laufnummer gegen überholte Antworten wie
  die Katalogsuche. Wer sofort nach dem Öffnen tippt, löst eine zweite
  Abfrage aus, während der Erstaufbau noch läuft – käme der später zurück,
  überschriebe er das gefilterte Ergebnis.

## 2.31.0 – August 2026

### Neu
- 📖 **Die Suche lernt – und du kannst ihr etwas beibringen.** Die Zuordnung
  „deutscher Begriff → englische Katalogbegriffe" lag bisher nur im
  Arbeitsspeicher: nach jedem Neustart weg, nur vom Modell beschrieben, für
  niemanden einsehbar. Wer „roter c3po" tippte, bekam für immer
  C-3PO-Varianten – obwohl die gesuchte Figur „R-3PO Protocol Droid" heißt.

  Unter **Mehr → 🤖 Lokale KI** steht die Liste jetzt offen da. Jede
  erfolgreiche Übersetzung wandert automatisch hinein, eigene Zeilen trägst
  du selbst ein:

      Gesucht wird nach: roter c3po
      Finden soll er:    R-3PO

  Drei Entscheidungen stecken darin:

  - **Das Gelernte hängt an der App, nicht am Modell.** Ein Wechsel des
    Modells oder des Rechners nimmt den Wissensstand mit; ein
    nachtrainiertes Modell täte das nicht. Deshalb gelten eigene Zeilen auch
    dann, wenn gar keine KI eingerichtet ist.
  - **Die KI überschreibt eine eigene Zeile nicht.** Sonst wäre das
    Beigebrachte beim nächsten Suchlauf wieder weg.
  - **Fehlschläge werden nicht gelernt.** Ein leeres Ergebnis ist kein
    Wissen; dauerhaft gespeichert stellte es den Begriff für immer tot.

  Nebenbei wird die Suche deutlich schneller: Ein bekannter Begriff kostet
  **4 Millisekunden statt 1,6 Sekunden**, weil das Modell gar nicht erst
  gefragt wird.

### Geändert
- Ein Wechsel der KI-Adresse leert weiterhin den Zwischenspeicher, fragt das
  Modell aber nicht erneut nach bereits Gelerntem – das steht ja in der
  Liste. Taugt eine Zeile nichts, löscht man sie sichtbar, statt sie stumm
  neu raten zu lassen.

## 2.30.1 – August 2026

### Behoben
- 🔇 **Die Katalogsuche endete stumm.** Wer beim manuellen Erfassen einen
  Begriff eintippte, der nichts fand, bekam **gar keine Meldung** – nicht
  einmal „Nichts gefunden". Man wusste nicht, ob noch gesucht wird, ob die
  KI dran ist oder ob etwas kaputt ist.

  Die Ursache stand schon länger im Code: `renderSuggestions` setzt bei
  leerer Liste selbst „Nichts gefunden …", und eine Zeile später löschte ein
  pauschales `hint.hidden = true` die Meldung wieder – ohne Ansehen des
  Ergebnisses. Jetzt wird der Hinweis nur weggenommen, wenn es Treffer gibt.

  Zwei weitere stumme Ausgänge kamen mit 2.29.0 dazu: Fand die KI nichts
  oder fiel sie aus, blendete der Zweig den Hinweis ebenfalls aus. Beide
  hinterlassen jetzt wieder die „Nichts gefunden"-Meldung.

  Und ohne eingerichtete Katalogsuche steht endlich da, warum nichts
  passiert, statt dass man tippt und ins Leere schaut.

  Geprüft am laufenden Programm, alle vier Wege: kein Katalog, KI ohne
  Treffer, KI ausgefallen, KI erfolgreich.

## 2.30.0 – August 2026

### Neu
- 📋 **Das KI-Modell wird ausgesucht, nicht abgetippt.** Der Name musste
  exakt so eingetragen werden, wie Ollama ihn führt – `qwen2.5:14b`, nicht
  `qwen2.5-14b` und nicht `qwen 2.5`. Ein Tippfehler sah dabei aus wie ein
  kaputter Dienst: Die Verbindung stand, nur das Modell gab es nicht. Auf
  dem Server im Haushalt liegen 14 Stück, darunter `qwen2.5:14b` **und**
  `qwen2.5:14b-instruct` – die Verwechslung ist keine Theorie.

  Steht die Adresse, holt die App jetzt die Liste der installierten Modelle
  und stellt sie zur Wahl. **Modelle laden** holt sie erneut, etwa nach
  einem `ollama pull`.

  **Kein `datalist`.** Der wäre der kürzere Weg gewesen, aber iOS zeigt ihn
  bis heute nicht an – und dort wird die App am meisten benutzt. Also eine
  echte Auswahlliste.

  **Das Textfeld bleibt.** Schweigt der Dienst oder ist die Adresse noch
  nicht gespeichert, übernimmt es wie bisher; die Auswahl ist eine
  Bequemlichkeit, kein Zugangsweg. Auch abfragen lässt sich eine noch nicht
  gespeicherte Adresse – sonst müsste man erst eine ungeprüfte Einstellung
  sichern, um zu sehen, was dort zur Wahl steht.

  Ein bereits gespeichertes Modell bleibt wählbar, auch wenn es nicht mehr
  auf dem Server liegt – sonst überschriebe ein Speichern still eine noch
  gültige Einstellung.

## 2.29.0 – August 2026

### Neu
- 🤖 **Die KI-Suche gilt jetzt auch für den Katalog.** 2.28.0 hat die
  Übersetzung an die Sammlungssuche gehängt. Ausprobiert wird sie aber
  zuerst dort, wo man beim Erfassen tippt: im Feld **Name** unter
  „✏️ Manuell erfassen". Das sucht im Katalog, und dort gab es die
  Übersetzung nicht – „Roter c3po" blieb leer, und von außen sah das aus,
  als funktioniere die KI nicht.

  Dabei ist der Katalog der Ort, an dem sie am meisten hilft: In der eigenen
  Sammlung kann man notfalls blättern, im Katalog sucht man etwas
  Unbekanntes. Ohne Treffer hat man gar nichts.

  Findet der Katalog nichts, übersetzt die App und fragt noch einmal nach –
  wie in der Sammlung mit dem genauesten Begriff zuerst, sortiert nach
  Wortzahl und ausdrücklich nicht nach Länge (daran hing 2.28.1). Über den
  Treffern steht, wonach zusätzlich gesucht wurde.

  **Höchstens zwei Versuche.** In der Sammlung kostet ein Begriff mehr fast
  nichts, die Einträge liegen im Speicher. Hier ist jeder Versuch eine
  eigene Anfrage an Rebrickable – mehr Wartezeit beim Tippen und mehr Last
  auf einem fremden Kontingent. Zwei decken den Anlassfall ab („roter c3 po"
  → `C-3PO`, dann `C-3PO red`), ohne aus einer Suche fünf zu machen.

  Unverändert gilt: Das Modell liefert **Suchbegriffe, niemals Ergebnisse**.
  Jede Zeile kommt weiter von Rebrickable, ein erfundener Begriff findet
  dort nichts. Antwortet der Katalog beim Zusatzversuch nicht, bleibt es bei
  der leeren Liste – ein Fehlschlag der Zugabe ist kein Fehler der Suche.

## 2.28.1 – August 2026

### Behoben
- 🎭 **Greedo stand unter den Rittern.** Beim ersten Einsatz an einer echten
  Sammlung (888 Figuren) zeigte die neue KI-Suche für „Ritter" neun Treffer –
  darunter Greedo und Obi-Wan. Für „Zauberer" kam ein kampfbeschädigter
  Anakin Skywalker. Zwei Ursachen, beide in der Testsammlung unsichtbar, weil
  dort schlicht nichts so hieß:

  **Die Länge war das falsche Maß für Genauigkeit.** Das Modell liefert für
  „Ritter" die Begriffe `Knight, Minifigure, Hero, Character`. Sortiert wurde
  nach Wortzahl *und Länge* – damit lief `Minifigure` (10 Zeichen) vor
  `Knight` (6) und griff sich als Erstes alles, was „Minifigure" im Namen
  trägt. Innerhalb gleicher Wortzahl bleibt jetzt die Reihenfolge des Modells
  stehen; es nennt den Eigennamen zuerst.

  **„Mage" steckt in „Damaged".** Damit „c3 po" den Artikel „C-3PO" findet,
  wirft der Vergleich Satzzeichen weg – und verlor dabei die Wortgrenze. Ein
  Begriff muss jetzt dort stehen, wo auch ein Wort anfängt. Bindestrichnamen
  bleiben trotzdem auffindbar.

## 2.28.0 – August 2026

### Neu
- 🤖 **„Ritter" fand nichts, obwohl die Figuren im Regal lagen.** Die
  Oberfläche ist deutsch, die Namen in der Sammlung kommen von BrickLink und
  sind **englisch**. Die Suche war ein reines `LIKE '%…%'` auf Name und
  Nummer – wer „Ritter" eintippte, bekam eine leere Liste, obwohl die Figur
  als „Castle Knight" in der eigenen Datenbank steht. Das war kein Randfall,
  sondern die naheliegendste Suche eines deutschen Nutzers. Dasselbe galt für
  „Kopf" (Head), „Schwert" (Sword) und „Piraten" (Pirate).

  Findet die Suche nichts, fragt die App jetzt eine **optionale** lokale KI
  nach englischen Begriffen und sucht damit erneut. Über den Treffern steht,
  wonach zusätzlich gesucht wurde – gemeldet werden nur Begriffe, die
  wirklich etwas gefunden haben.

  **Die KI liefert Suchbegriffe, niemals Ergebnisse.** Jede angezeigte Zeile
  kommt weiter aus der eigenen Datenbank; ein erfundener Begriff findet
  schlicht nichts. Deshalb genügt hier ein kleines Modell auf dem eigenen
  Rechner, und deshalb kann die Funktion nichts erfinden, was es nicht gibt.

  Einzurichten unter **Einstellungen → Lokale KI für die Suche** mit der
  Adresse eines [Ollama](https://ollama.com) und einem Modellnamen
  (Vorgabe `qwen2.5:14b`), wahlweise über `OLLAMA_URL` und `OLLAMA_MODEL` aus
  der `docker-compose.yml`. **Ohne Adresse ist alles wie vorher** – nicht
  jeder betreibt eine lokale KI. Antwortet der Dienst nicht innerhalb von
  acht Sekunden, bleibt es beim gewohnten Hinweis „Nichts gefunden".

  Die Adresse wird wie ein API-Schlüssel aus Fehlerberichten entfernt: Sie
  verrät den Aufbau des Heimnetzes und kann Zugangsdaten enthalten, und ein
  Fehlerbericht kann als öffentliches Issue enden.

  **Satzzeichen zählen nicht mit.** BrickLink schreibt die bekanntesten
  Figuren mit Bindestrich – `C-3PO`, `R2-D2` –, getippt wird „c3 po" oder
  „r2d2". Der Vergleich lässt deshalb alles außer Buchstaben und Ziffern weg.
  Aus mehreren Wörtern müssen **alle** vorkommen, sonst zöge ein erfundener
  Begriff wie „Knight Hunter" jeden Ritter herein.

  **Der genaueste Begriff zuerst.** „roter c3 po" ergibt `C-3PO (red)` und
  `C-3PO`. In der Reihenfolge des Modells sammelte der breite Begriff alle
  C-3POs ein, und die Farbvariante kam auf null neue Treffer – die Eingrenzung
  verpuffte. Jetzt steht der rote oben, die übrigen darunter als Rückfall.

  Gleiche Frage, gleiche Antwort: Ein Zwischenspeicher verhindert, dass beim
  Tippen alle 300 ms ein Modellaufruf losläuft. **Ein Fehlschlag verfällt nach
  einer Minute** – die erste Fassung merkte ihn sich dauerhaft, sodass ein
  einziger Aussetzer (etwa während Ollama das Modell lud) genau diesen
  Suchbegriff bis zum Neustart tot bleiben ließ. Damit das seltener vorkommt,
  bittet die App Ollama, das Modell 30 Minuten geladen zu lassen.

## 2.27.0 – August 2026

### Behoben
- 💤 **Die Absturzerkennung zählte das Betriebssystem mit.** Wirft iOS eine
  App im Hintergrund aus dem Speicher, läuft `pagehide` nicht – für die
  Erkennung sah das aus wie ein Abbruch. Das war nicht bloß unsauber, es hat
  zwei Wochen Suche in die falsche Richtung geschickt.

  Von 23 Abbrüchen im Archiv lagen **15** nach einer Pause von einer bis
  achtunddreißig Stunden. Aus einem davon – 15.351 Elemente am 15.08., danach
  8,7 Stunden Lücke – entstand die These, die Sammlung sei zu groß. Sie war
  es nicht: Am 19.08. hat ein iPhone die Sammlung mit 664 Bildern
  durchgescrollt und lief weiter, ein Mac mit 886 Bildern ebenso. Von den
  acht verbleibenden echten Abbrüchen kamen sieben in Sitzungen vor, die nie
  über 2.000 Elemente hinauskamen.

  Die App merkt sich jetzt beim Wechsel in den Hintergrund einen Vermerk und
  löscht ihn beim Zurückkommen. Fehlt der Abschied und liegt der Vermerk noch
  da, heißt es „im Hintergrund weggeräumt" und zählt in einer eigenen Zeile –
  mitsamt der Liegezeit. Die Fälle verschwinden also nicht, sie stehen nur
  nicht mehr in derselben Spalte wie die echten Abstürze.

  **Ohne Zeitvergleich**, anders als beim Abschiedszettel: Auf dem
  Schreibtisch misst ein verborgener Tab gedrosselt weiter, sein letzter
  Messwert ist dann jünger als der Vermerk. Auch die Auswertung „wie lange
  lief eine Sitzung vor dem Abbruch" lässt diese Fälle jetzt aus – 38 Stunden
  im Hintergrund verzerren dort jede Aussage.

## 2.26.3 – August 2026

### Behoben
- 🔍 **Ein Hub-Ausfall hinterließ keine Spur.** Am 13.08.2026 um 10:03 meldete
  eine Instanz einen 502 bei `POST /api/hub/trades/sync`. Im Fehlerbericht
  stand davon nur „Fehler 502" und der Anfang einer Cloudflare-Fehlerseite.

  Die App hatte ihre Erklärung durchaus dabei – „Hub: …" oder „Hub nicht
  erreichbar" –, aber der Rumpf ihrer Antwort wurde zwischen Instanz und
  Browser durch jene Fehlerseite ersetzt. Der Hub wiederum antwortet nach
  außen grundsätzlich nur mit „interner Fehler", damit kein Innenleben nach
  draußen geht, und seine eigenen Protokolle wurden nicht aufbewahrt.

  Beide Seiten kannten den Grund, keine behielt ihn. Nicht einmal die Frage,
  ob der Worker überhaupt zu Wort gekommen war oder etwas davor geantwortet
  hatte, ließ sich nachträglich klären – und genau daran hängt, wo man
  weitersucht.

  Die Instanz schreibt eine Störung des Hubs jetzt selbst ins Protokoll:
  Status, Grund und – wenn keine JSON-Antwort kam – den Anfang dessen, was
  stattdessen kam. Bei einer Zeitüberschreitung steht dort die Art
  (`ConnectTimeout` heißt „nie erreicht", `ReadTimeout` heißt „angenommen und
  dann nichts mehr") samt Zeitgrenze. Abgelehnte Anfragen bleiben still: Ein
  401 bei falschem Token ist eine Antwort, kein Ausfall. Der Instanz-Token
  steht nie in der Zeile.

  Im Hub ist zusätzlich die Aufbewahrung der Worker-Protokolle eingeschaltet
  (`[observability]`). Ohne sie sah `console.error` nur, wer zufällig gerade
  `wrangler tail` laufen ließ.

## 2.26.2 – August 2026

### Behoben
- 🔐 **CSP-Meldungen schleppten ein Access-JWT mit.** Aus Pauls Instanz kam
  zweimal „Vom Browser blockiert: img-src →
  flat-leaf-5175.cloudflareaccess.com". Kein Defekt: Die Instanz steht hinter
  Cloudflare Access, und ist dessen Sitzung abgelaufen, antwortet Access auf
  jede Anfrage – hier das Symbol der Web-App – mit einer Umleitung auf seine
  Anmeldeseite. Die liegt auf einem anderen Host, und den erlaubt `img-src`
  nicht.

  In der Meldung stand bisher die vollständige Adresse samt einem JWT von
  rund 1,5 kB. Das ist kein Zugangsschlüssel (ein `meta`-Token mit
  `auth_status: NONE`, fünf Minuten gültig), es gehört aber weder ins
  Fehlerprotokoll noch in einen Bericht an den Hub. Gespeichert wird jetzt
  nur noch Herkunft und Pfad, ein `?…` zeigt an, dass gekürzt wurde.

  Außerdem steht bei dieser einen Umleitung dabei, was sie bedeutet:
  „(Access-Anmeldung abgelaufen)". Ohne den Hinweis sucht man den Fehler in
  der App, obwohl niemand etwas zu reparieren hat.

## 2.26.1 – August 2026

### Behoben
- 🔍 **Die Fremdsuche meldete die eigene Zieh-Anzeige.** In Finns Berichten
  vom 10.08.2026 stand in **jeder** Zeile `FREMD: <div.ptr>` – und das war
  die App selbst: die Anzeige für „nach unten ziehen = neu laden", die es
  nur beim Start vom Startbildschirm gibt.

  Der Grund ist eine Reihenfolge. Beim Laden merkt sich die App, was unter
  `<body>` steht; alles, was später dazukommt, gilt als fremd. Die
  Zieh-Anzeige entsteht danach und bleibt stehen.

  Der Fehler ist nicht die falsche Zeile, sondern was sie verdeckt: Das Feld
  soll die seit Wochen offene Frage beantworten, welcher fremde Code im
  Renderer sitzt, wenn der Tab stirbt. Solange es in jeder Zeile dasselbe
  meldet, liefert es null Information – und sieht dabei aus wie eine
  Bestätigung.

  Betroffen war nicht nur `div.ptr`: Dialoge, der Kopier-Notausgang und die
  Download-Verweise hängen ebenfalls nachträglich an `<body>` und hätten
  während einer Messung genauso im Bericht gestanden. Die bisherige Ausnahme
  galt nur für das Artikel-Popup und hätte mit jedem neuen Overlay wachsen
  müssen. Stattdessen kennzeichnet die App jetzt am Element selbst, was von
  ihr stammt – ein Test hält fest, dass keine Stelle das vergisst.

## 2.26.0 – August 2026

### Neu
- 🐞 **Fehlerbericht an den Hub senden.** Der Speicher-Verlauf liegt im
  Browser und nirgends sonst – für die Absturzsuche fehlte damit genau das
  Stück, das die Frage entscheidet: Stürzt es nur bei **einem** ab (dann
  liegt es an dessen Gerät) oder bei **allen** (dann an der App)?

  Der Knopf erscheint **nur nach einem erkannten Absturz**. Vor dem Senden
  bekommt man wortwörtlich zu sehen, was rausgeht – derselbe Text wie bei
  „Verlauf kopieren", aus derselben Funktion. Darin stehen Zeitpunkte,
  Speicher, Elemente, Bilder, Version, Design, Ansicht, Gerät und die Namen
  fremder Erweiterungen im Fenster; **keine** Artikel, Namen oder Preise.
  Nach dem Senden wird der Verlauf auf dem Gerät geleert, damit derselbe
  Absturz nicht dreimal ankommt.

  **Eigener Token, nicht der des Tausch-Netzwerks.** Das ist keine
  Ordnungsliebe: Von vier Instanzen im Haushalt sind zwei Mitglied im
  Netzwerk. Hinge der Kanal am Mitgliedskonto, bliebe die Hälfte stumm – und
  zwar ausgerechnet die, deren Berichte am meisten erklären würden.
  Umgekehrt gibt niemand mit einem Bericht etwas über sein Tauschen preis,
  und der Kanal lässt sich einzeln zurückziehen.

  **Ohne hinterlegten Token** bietet derselbe Knopf den Bericht zum
  Kopieren an, statt stumm zu bleiben.

### Hub (1.5.0)
- Neue Tabellen `report_tokens` und `crash_reports`, der Endpunkt
  `POST /v1/crash` **vor** der Mitglieder-Anmeldung, und in der
  Admin-Konsole eine Übersicht, die mehrere Berichte nebeneinanderlegt –
  samt Auszählung, auf welchen Ansichten sich Abstürze häufen.

## 2.25.0 – August 2026

### Neu
- 🔎 **Der Speicher-Verlauf notiert die geöffnete Ansicht** an jedem
  Messwert (`▸ scan`), und die Zusammenfassung sagt, wo die App bei einem
  Absturz zuletzt stand: „↳ zuletzt offen war dabei: scan (2×)". Gezählt
  wird die Ansicht des **letzten Messwerts davor** – der Starteintrag nennt
  die nach dem Neustart und damit die falsche.

  Anlass sind zwei bestätigte Abstürze (08. und 09.08.), die beide auf der
  Scan-Ansicht passierten, bei identischem Zustand: 7 MB, 1007 Elemente,
  6 Bilder. Ob das ein Muster ist oder Zufall, war nicht zu beantworten –
  die Ansicht stand nur in der **Spur**, und die behält zwanzig Einträge und
  ist nach einem Neustart weg. Jetzt zeigt der dritte und vierte Absturz es
  von selbst.

## 2.24.0 – August 2026

### Neu
- 📉 **Größte Wertverluste** in der Statistik, als Gegenstück zu den besten
  Wertsteigerungen: die fünf Stücke, bei denen der Kaufpreis am weitesten
  über dem heutigen Wert liegt. Ein Tipp auf eine Zeile öffnet den
  Steckbrief.

### Geändert
- 📈 **Verluste stehen nicht mehr unter „Beste Wertsteigerungen".** Dort
  landeten sie bisher nur dann, wenn es **weniger als fünf Gewinner** gab –
  ausgerechnet in einer gewachsenen Sammlung sah man sie also nie, und wenn
  doch, dann unter einer Überschrift, die das Gegenteil versprach. Die
  Steigerungen zeigen jetzt nur noch Gewinne, die Verluste stehen daneben

## 2.23.0 – August 2026

Vier Funde aus dem vollständigen Funktionstest, die lange liegen geblieben
sind. Keiner davon hat je jemanden umgebracht – gemeinsam ist ihnen, dass
sie **still** danebengehen.

### Behoben
- 👤 **„  " war ein gültiger Benutzername.** Die Längenprüfung zählte die
  rohe Eingabe, abgeschnitten wurde erst danach – zwei Leerzeichen kamen
  damit durch und landeten als **leerer** Name in der Datenbank. Anmelden
  konnte sich damit niemand mehr, und in der Benutzerverwaltung stand eine
  namenlose Zeile. Auch Steuerzeichen sind jetzt draußen: Ein Name mit
  Zeilenumbruch zerlegt jede Liste, in der er auftaucht. Anlegen, Umbenennen
  und Einrichten prüfen ab sofort **gleich** – vorher hatte jede Stelle ihre
  eigene, halbe Fassung
- 🖼️ **Gelöschte Artikel ließen ihre Fotos liegen** – die Einträge *und* die
  Dateien. Sichtbar war das nirgends, erreichbar auch nicht: Ohne Artikel
  gibt es keine Galerie, in der sie auftauchen könnten. Nur der Platz auf
  der Platte wuchs. Aufgeräumt wird jetzt, sobald der Artikel **überall**
  weg ist – Sammlung, Wunschliste, Einkaufslisten. Eine Aufnahme, die an
  mehreren Artikeln hängt, bleibt liegen, solange einer sie noch braucht
- 🔗 **Die Galerie zeigte Bilder, die es nicht gibt.** Findet die
  BrickLink-API kein Bild, baut die App eine Adresse aus Typ und Nummer
  zusammen – das ist eine Vermutung. Stimmte sie nicht, stand ein leerer
  Rahmen zum Durchblättern in der Galerie. Jetzt wird nachgefragt, aber die
  Beweislast liegt beim Weglassen: Nur ein klares „gibt es nicht" (404)
  wirft die Adresse raus. Zeitüberschreitung oder gar kein Netz heißen
  *unbekannt* – dann bleibt die Vermutung stehen, denn eine leere Galerie
  wäre schlimmer als ein Bild, das vielleicht lädt

### Geändert
- 💼 **Wer die Instanz einrichtet, ist jetzt auch Sammlerprofi.** Vorher
  bekam das erste Konto nur Admin-Rechte und sah damit weder Kaufpreise noch
  Einkaufslisten oder Verkaufsliste – freischalten musste man sich in der
  Benutzerverwaltung selbst. Ein Einrichtungsassistent, nach dem man sich
  erst selbst freischaltet, ist keiner. Alle weiteren Benutzer starten
  unverändert als Standard-Konto

## 2.22.0 – August 2026

### Behoben
- 🧮 **Der Speicher-Verlauf erfand Abstürze.** Ein zweiter Tab wurde als
  „OHNE ABSCHIED" eingetragen – also als Absturz. Der Abschiedszettel liegt
  im localStorage, und der gehört **allen** Tabs derselben Adresse
  gemeinsam: Ein frisch geöffneter Tab fand darin keinen frischen Abschied,
  während der erste munter weiterlief, und trug sich selbst als Absturz ein.
  Im Verlauf vom 06.08. um 23:31:40 stand genau das, und drei Sekunden
  später maßen **zwei** Reihen im Abstand von 30 Sekunden weiter. Der alte
  Notbehelf (ein Aufruf mehr als 90 Sekunden nach dem letzten Messwert zählt
  nicht) griff dort nicht – es waren 27 Sekunden.

  Das ist der schlimmste Fehler, den eine Messung haben kann: Sie erfand die
  Ereignisse, die sie erklären sollte. Jeder Tab hat jetzt eine eigene
  Kennung und meldet ein Lebenszeichen; beim Start wird nachgesehen, ob ein
  *anderer* gerade läuft. Dann steht dort **„weiterer Tab"** statt eines
  Absturzes. Echte Abstürze werden unverändert erkannt.

### Neu
- 🪟 **Der Verlauf sagt, wenn mehrere Tabs offen sind** („2 Tabs offen").
  Alle schreiben in dieselbe Liste, ihre Messwerte wechseln sich also ab –
  ohne diese Angabe sah das nach wilden Sprüngen bei Speicher und Elementen
  aus. Genau danach hatten wir gesucht.

### Geändert
- 🔍 Der **allererste Eintrag** eines Verlaufs wird nicht mehr bewertet. Er
  hat keinen Vorgänger, über dessen Ende sich etwas sagen ließe – stand aber
  trotzdem als „OHNE ABSCHIED" da. Die Zählung überspringt ihn längst, die
  Anzeige tat es nicht

## 2.21.3 – August 2026

### Behoben
- 🐳 **`sudo bash update.sh` scheiterte auf Synology – nach getaner Arbeit.**
  `sudo` bringt einen eigenen, kurzen Suchpfad mit, und dort fehlt
  `/usr/local/bin`, wo auf der Synology `docker` liegt. Das Skript lief
  deshalb bis zum letzten Schritt durch, legte den Datenbank-Schnappschuss
  an, **tauschte den Quellstand auf der Platte aus** – und brach erst dann
  mit `docker: command not found` ab. Zurück blieb der schlechteste
  Zustand: auf der Platte der neue Stand, im Betrieb der alte Container,
  und eine Ausgabe, die bis zur vorletzten Zeile nach Erfolg aussah. Das
  Skript ergänzt den Suchpfad jetzt selbst und prüft **vor** dem ersten
  Schreiben, ob es `docker` überhaupt gibt – fehlt es, bleibt die Instanz
  unangetastet. Über den Aufgabenplaner fiel das nie auf, weil der einen
  längeren Suchpfad mitbringt; betroffen war nur der Weg von Hand, den die
  App selbst anzeigt

## 2.21.2 – August 2026

### Behoben
- 🪟 **Der Steckbrief ging hinter der Karte auf, aus der er kam.** Die
  Figurenliste eines Sets steht im Detail-Fenster einer Sammlungs-Karte
  (Ebene 70) – der Steckbrief lag auf der Grundebene der Popups (60) und
  damit dahinter. Man sah nur, dass irgendwo etwas aufging. Er liegt jetzt
  auf 80: über der Karte, unter der Großansicht, damit ein Tipp auf sein
  Bild die Galerie weiterhin davor öffnet
- ⌨️ **Escape schloss beides auf einmal.** Die Detail-Karte bringt einen
  eigenen Escape-Empfänger mit. Jetzt schließt jeder Druck nur das oberste
  Fenster
- 🔤 **Die Schrift im Steckbrief passte nicht zum Rest.** Die Artikelnummer
  stand mit 16 px in voller Textfarbe da statt mit 12,5 px gedämpft wie
  überall sonst – fast so laut wie der Name darüber. Grund: `.sub` hat keine
  Grundregel, sondern wird immer im Zusammenhang gesetzt, und der Steckbrief
  stand außerhalb. Auch die Abschnitte („Marktpreis", „Steckt in diesen
  Sets") hatten eigene Größen; sie benutzen jetzt dieselben Klassen wie der
  Detailblock einer Karte. Der Name selbst hatte die Browser-Vorgabe für
  Überschriften (18,7 px) – bei „Snowtrooper – Male, Printed Legs, White
  Hands" eine Wand, jetzt 16 px

## 2.21.1 – August 2026

### Behoben
- 👓 **Das Update-Banner war in Galaxie und Nova nicht zu lesen.** Seine
  Fläche ist die Akzentfarbe – in Galaxie ein helles Gelb, in Nova ein
  helles Blau –, die Schrift blieb aber die helle des dunklen Designs.
  Gemessen waren das **1,22 : 1** (Galaxie) und **1,66 : 1** (Nova); lesbar
  wären 4,5 : 1. Ausgerechnet die Meldung, die auffallen soll, war damit
  unsichtbar. Jetzt steht dunkle Schrift darauf: 13,2 : 1 und 8,8 : 1
- 🔗 **„Release-Notes ansehen" nahm die Browser-Vorgabe für Verweise.** Auf
  der hellen Fläche kaum zu sehen, und einmal besucht vollends weg – im
  Bildschirmfoto ein dunkles Rot auf Hellblau. Der Verweis erbt jetzt die
  Schriftfarbe des Banners und bleibt über die Unterstreichung als Verweis
  erkennbar

## 2.21.0 – August 2026

### Neu
- 👤 **Figuren-Steckbrief: ein Tipp auf die Zeile, und alles steht da.**
  Überall, wo eine Figur bisher nur als Zeile auftauchte – unter einem Set in
  eurer Sammlung, in der Teileliste, bei den fehlenden Set-Figuren, auf den
  Einkaufslisten, auf der Wunschliste, in der Statistik und bei den Doppelten
  –, öffnet ein Tipp jetzt den **Steckbrief**: Bild, Nummer, Jahr,
  Marktpreise, ob ihr sie habt (Sammlung / Einkaufsliste / Wunschliste), in
  welchen eurer Sets sie steckt, dazu ＋ Sammlung, ☆ Merken und BrickLink.
  Schließt beim Tippen daneben, mit ✕ oder Escape. Das Bild behält seine
  Aufgabe: ein Tipp darauf öffnet weiterhin die Bildergalerie – jetzt auch
  aus dem Steckbrief heraus, und Escape schließt erst das Bild, dann den
  Steckbrief

### Geändert
- 🛒 **„Auf einer Einkaufsliste" ist jetzt blau statt gelb.** Bisher sah die
  Marke genauso aus wie „auf der Wunschliste" – dabei bedeuten die beiden das
  Gegenteil voneinander: im Korb gegen fehlt euch. Gleiche Farbe hieß damit
  gar nichts. Grün heißt *habt ihr*, blau *ist unterwegs*, gelb *wollt ihr*

### Behoben
- 📷 **„Nur Foto dazu" stand auch da, wenn es den Artikel gar nicht gab.**
  Der Knopf hängt ein Foto an einen vorhandenen Artikel – ohne Artikel gibt
  es nichts, woran es hängen könnte. Er erscheint jetzt nur noch, wenn das
  Stück in eurer Sammlung oder auf einer Einkaufsliste steht. Die
  Wunschliste zählt bewusst nicht: Was man sich wünscht, hat man gerade nicht

## 2.20.1 – August 2026

### Behoben
- 🌍 **„30 Artikel haben noch Preise aus einem anderen Gebiet" – obwohl nie
  ein Gebiet umgestellt wurde.** Der Zähler füllte sich selbst nach. Kaufte
  man einen Wunsch („✔ Gekauft!") oder verbuchte einen angekommenen Posten
  von einer Einkaufsliste, wanderten Preis, Zeitstempel und Rohdaten mit in
  die Sammlung – **Gebiet und Währung aber nicht**. Der Artikel galt damit
  sofort als „fremdes Gebiet", obwohl sein Preis aus genau dem eingestellten
  stammte. Nachrechnen half bis zum nächsten Kauf und kostete dabei zwei
  BrickLink-Abrufe je Artikel für nichts. Beide Wege reichen Gebiet und
  Währung jetzt mit durch; ein Preis, der wirklich aus den USA stammt, wird
  weiterhin gemeldet

## 2.20.0 – August 2026

### Neu
- 🛒 **Die Wunschliste sagt jetzt, was schon unterwegs ist.** Steht ein Wunsch
  bereits auf einer offenen Einkaufsliste, trägt seine Karte einen blauen
  Vermerk „🛒 auf Einkaufsliste: Flohmarkt". Bei mehreren Listen stehen alle
  da, mit der zusammengezählten Stückzahl. Abgehakte Posten und archivierte
  Listen zählen nicht mit – abgehakt heißt gekauft, archiviert heißt vorbei.
  Zusammen mit dem grünen „✔ in eurer Sammlung" beantwortet die Wunschliste
  damit auf einen Blick die Frage, die man vor dem Kauf hat: *haben wir das
  schon, oder holt es gerade jemand anders?*

## 2.19.2 – August 2026

### Behoben
- 🐞 **„Ein Fehler wurde aufgezeichnet" – und der Bericht war leer.** Wer den
  Fehlerbericht leerte, ließ den Zettel dazu stehen. Er zeigte danach auf
  einen Fehler, den es nicht mehr gab. Das Leeren räumt die Zettel jetzt mit
  weg
- 🔕 **Ein verwaister Zettel machte die App stumm.** Gemeldet wird nur, wenn
  kein Zettel offen ist – damit ein Problem nicht zehn Karten übereinander
  stapelt. Zeigte der offene aber ins Leere, kam **nie wieder** eine
  Meldung. Jetzt blockiert nur noch ein Zettel, dessen Fehler wirklich
  existiert; verwaiste werden dabei abgeräumt

> Gefunden auf einer laufenden Instanz: drei Benachrichtigungen vom Typ
> `error`, null Zeilen im Fehlerbericht. Der jüngste Zettel war offen – und
> hätte jede weitere Fehlermeldung verschluckt.

## 2.19.1 – August 2026

### Behoben
- 🔎 **Die Suche nach fremdem Code lief zum falschen Zeitpunkt.** Sie stand
  nur in der Startzeile – und die entsteht beim **Laden** der Seite, also
  bevor eine Erweiterung ihre Sachen einhängt. Das leere Ergebnis war
  deshalb kein Ergebnis, sondern ein Messfehler. Jetzt wird bei jeder
  Messung nachgesehen; geschrieben wird nur, wenn etwas da ist

## 2.19.0 – August 2026

### Neu
- 🔎 **Der Bericht nennt jetzt, wer sonst noch in der Seite sitzt.** Bisher
  stand dort „Script error." – der Satz, auf den der Browser jeden Fehler
  aus **fremden Skripten** zusammenkürzt. Er sagt, *dass* fremder Code lief,
  nicht *welcher*. Jetzt stehen die Erweiterungs-Adressen und die
  nachträglich eingehängten Elemente daneben, im Fehlereintrag **und** in
  jeder Startzeile des Speicher-Verlaufs

> **Warum das jetzt zählt.** Vier ausgewertete Abstürze, vier verschiedene
> Situationen: Listen offen mit 5094 Elementen, zweimal Leerlauf im
> Hintergrund, zuletzt die **leere Scan-Ansicht mit 970 Elementen und 4
> Bildern**. Derselbe Tab hat vorher 14.585 Elemente mit 822 Bildern
> getragen. Kein Maß der App erklärt das – aber fremder Code läuft im
> **selben Renderer-Prozess**, und stürzt der ab, nimmt er die Seite mit,
> ganz gleich wie klein sie ist.
>
> Gemeldet wird nur, nie geblockt: Es ist euer Browser, und eine
> Passwort-Ausfüllhilfe hat dort gute Gründe zu sein.

## 2.18.0 – August 2026

Gefunden beim vollständigen Durchlauf einer frisch aufgesetzten Instanz –
von der Installation bis zur Wiederherstellung.

### Behoben
- 💾 **Das Kaufbuch fehlte in der Sicherung.** `purchases` stand nicht in
  `BACKUP_TABLES`. Nach einer Wiederherstellung war es leer, während der
  aufsummierte Kaufpreis an der Zeile stehen blieb: Man sah, **dass** etwas
  bezahlt wurde, aber nicht mehr wann, wo und wie oft
- 🖼 **Artikel ohne Bildadresse bekamen nie eins.** „🖼 Bilder jetzt holen"
  spiegelte nur schon bekannte Adressen auf die Instanz – wer per CSV
  importiert, legt aber Zeilen ganz ohne an. Der Lauf meldete „nichts zu
  tun", während jede Karte den Platzhalter zeigte. Jetzt schlägt er die
  fehlende Adresse erst im Katalog nach
- 💶 **„Preislose erneut abrufen" übersprang die nie versuchten.** In der
  Bedingung stand `price_updated_at IS NOT NULL` – gedacht als „schon
  versucht, nichts gefunden". Damit blieben ausgerechnet die Artikel außen
  vor, die noch nie an der Reihe waren
- 🗂 **CSV: `item_type` galt nicht als Typspalte.** `item_id` zählte als
  Nummer, das Gegenstück aber nicht – ein Set landete still als Minifigur,
  und Preise, Themen und Filter stimmten danach nie wieder
- 🐞 **Gleichartige Fehler wurden nicht zusammengefasst.** Die Kennung nahm
  den **Detailtext** und ließ den **Ort** weg – genau verkehrt herum. Bei
  „Script error." steht im Detail die Spur der letzten Schritte, die jedes
  Mal anders aussieht: Jedes Auftreten erzeugte einen neuen Eintrag

> **Warum das lange nicht auffiel.** Der übliche Weg führt über Scannen und
> Suchen, und dort kommt schon eine Bildadresse mit, wird schon ein Preis
> geholt, steht schon ein Typ fest. Hineingelaufen ist nur, wer importiert
> oder wiederhergestellt hat.

## 2.17.0 – August 2026

### Behoben
- 🧹 **Die Listen-Ansicht blieb für immer im Dokument stehen.** Ein Blick in
  die Einkaufslisten legte bei 310 Artikeln rund **4600 Elemente und 310
  Bilder** ab – und die blieben dort, auch wenn längst Sammlung, Statistik
  oder Einstellungen offen waren. Für die Sammlung wird seit 2.9 beim
  Verlassen geräumt; für die Listen fehlte es
- 📦 **Eine eingeklappte Liste baute ihre Zeilen trotzdem auf.** Sie standen
  nur auf `display: none` – unsichtbar, aber vollständig im Dokument. Jetzt
  entstehen sie erst beim Aufklappen und verschwinden beim Zuklappen

> Gemessen an 310 Listenposten:
>
> | | vorher | nachher |
> |---|---|---|
> | Listen-Tab, eingeklappt | 4631 Elemente · 310 Bilder | **973 · 4** |
> | nach dem Weiterklicken | 4631 Elemente · 310 Bilder | **973 · 4** |
>
> Aufgeklappt sind es weiterhin rund 5900 Elemente – das ist die Liste, die
> man gerade ansieht.

## 2.16.0 – August 2026

### Behoben
- 🖼 **Neun Stellen holten weiterhin Bilder in voller Größe.** 2.11.0 hat den
  Daumennagel eingeführt, aber nur die Sammlungskarten umgestellt. Listen,
  Statistik, Doppelte, fehlende Set-Figuren, die Set-Figuren-Dialoge und die
  Hub-Angebote luden weiter 400 px – und die zugehörige Prüfung sah es nicht,
  weil sie `class="card-img"` **wörtlich** verlangte und diese Stellen
  `class="card-img fig-img"` heißen

> **Aus einem eingeschickten Verlauf.** Der Tab stand drei Stunden ruhig bei
> 1784 Elementen und 32 Bildern. Dann ging die Listen-Ansicht auf: **5094
> Elemente, 336 Bilder** – 90 Sekunden später war der Renderer tot, bei 7 MB
> JS-Speicher.
>
> | | vorher | nachher |
> |---|---|---|
> | 336 Bilder, entpackt | 215 MB | 34 MB |
>
> Entpackte Bilder liegen **außerhalb** des JS-Speichers. Deshalb blieb die
> Kurve flach, während der Tab starb – und deshalb war die Ursache so lange
> nicht zu sehen.

- 🧪 **Die Prüfung dazu prüft jetzt den Anfang der Klassenliste.** Sonst
  rutscht dieselbe Sorte Stelle beim nächsten Mal wieder durch

## 2.15.0 – August 2026

Gefunden beim Durchtesten an einer laufenden Instanz.

### Behoben
- ⬆️ **Auch nach einer eigenen Änderung sprang die Liste nach oben.**
  2.12.0 hat das fürs automatische Auffrischen erledigt – löschen, Nummer
  richtigstellen, Thema setzen, Benachrichtigung übernehmen und die
  Sammelaktionen unter „Mehr" luden aber weiter schlicht neu. Elf Stellen,
  jetzt alle über denselben Weg
- 🪟 **Ein Thema zu setzen räumte das Popup weg.** Bei Sortierung nach Thema
  wechselt der Eintrag die Gruppe, die Liste muss also neu – aber nicht in
  dem Moment, in dem man gerade „Setzen" gedrückt hat. Jetzt wartet es, bis
  das Popup zu ist
- ✍️ **Der Text beim Bildabruf sprach von Preisen.** „BrickLink führt zu
  dieser Nummer keine verkauften Artikel" klang, als wäre nur gerade nichts
  verkauft worden – beim Bild fehlt aber der **Eintrag**, nicht der Verkauf

> **Sortierung, Suche und Filter landen weiter am Anfang.** Dort steht
> danach etwas anderes in der Liste; die alte Stelle zu halten wäre kein
> Dienst, sondern ein neuer Fehler.

## 2.14.0 – August 2026

### Geändert
- 🏷 **Das Themenfeld steht nur noch da, wenn keins gefunden wurde.** Als es
  kam (1.90.0), standen Teile reihenweise unter „Ohne Thema" – BrickLink
  sortiert sie nach **Form** („Brick, Modified"), nicht nach Thema. Seit das
  Thema über die Zweitnummer gefunden wird, ist der Normalfall erledigt, und
  Eingabefeld samt Knopf standen für etwas da, das längst richtig ausgefüllt
  war. Jetzt steht bei einem gefundenen Thema nur noch das Thema

> Ganz weg ist es nicht: Der Stift daneben holt das Feld zurück. Falsch
> zugeordnet wird auch mal etwas, und ohne einen Weg dahin bliebe es falsch.
> Wer das Thema leert, bekommt das Feld wieder offen – dann steht der
> Eintrag ja wirklich ohne.

## 2.13.0 – August 2026

### Behoben
- 🖼 **Das ↻ neben dem Bild holte bei bedruckten Teilen nichts.** Dieselbe
  Verwechslung wie beim Preis: Die Rebrickable-Nummer ging unverändert an
  BrickLink. Jetzt nimmt auch der Bildabruf die BrickLink-Nummer, wenn die
  eigene nichts ergibt
- 🚦 **Ein 404 wurde als „BrickLink nicht erreichbar" gemeldet.**
  `requests.HTTPError` ist eine Unterklasse von `RequestException` – stand
  kein eigener Zweig davor, fiel „kennt die Nummer nicht" in den Ast für
  Ausfälle. Betroffen waren der Bildabruf und die Teileliste einer Figur
- 📋 **Fehlgeschlagene Aufrufe standen in keinem Bericht.** Aufgezeichnet
  wurde nur, was niemand auffing. Fast jeder Knopf fängt seinen Fehler aber
  ab und schreibt ihn in eine Kurzmeldung – auf dem Bildschirm stand „Fehler
  502", und der Bericht meldete „keine Fehler"

> Jetzt landet jede Antwort ab Status 500 im Protokoll, mit Weg und dem
> **Anfang der Antwort**. Genau daran hängt die Frage, die zählt: Kommt der
> Fehler aus der App, steht dort ihr JSON mit `detail`; kommt er von etwas
> davor – Zwischenserver, Tunnel, Zugangsschutz –, steht dort dessen
> HTML-Seite. Ohne diesen Unterschied sucht man an der falschen Stelle.
>
> Ein 404 („kennt BrickLink nicht") und ein 400 („Eingabe nicht gültig")
> bleiben draußen: gewöhnlicher Betrieb, der das Protokoll nur zumüllt.

## 2.12.0 – August 2026

### Behoben
- 💶 **Bedruckte Teile bekamen keine Preise.** Rebrickable nennt den
  Gungan-Schild `2586pr0028`, BrickLink nennt ihn `2586ps1`; beim
  Karbonitblock stehen `87561pr0001` und `87561pb01` nebeneinander. Fürs
  Thema wurde diese Übersetzung längst gemacht, beim Preis nicht – dort ging
  die Rebrickable-Nummer unverändert an BrickLink und kam als „kennt die
  Nummer nicht" zurück. Jetzt wird bei einem Teil die BrickLink-Nummer
  nachgeschlagen und der Preis noch einmal darunter geholt

> Gefragt wird erst, wenn die eigene Nummer nichts ergeben hat, und die
> Antwort bleibt gespeichert – auch eine leere, sonst ginge dieselbe
> vergebliche Frage bei jedem Aufklappen erneut nach draußen. Stammt der
> Preis von der Zweitnummer, steht sie im Popup dabei: Sonst sucht man ihn
> auf BrickLink unter der eigenen Nummer vergebens.

- ✍️ **Der Hinweis dazu stimmte nicht.** Er schob es pauschal auf eine
  Rebrickable-Figurennummer und riet zu „BrickLink-Nr. setzen" – ein Feld,
  das die Oberfläche bei einem Teil gar nicht anbietet. Bei einem Teil steht
  dort jetzt, was wirklich los ist
- ⬆️ **Die Liste sprang beim Auffrischen an den Anfang.** Sie baut sich
  blockweise auf, und ein Neuaufbau fängt wieder bei den ersten 60 Karten an
  – die Seite wird kurz sehr kurz, und der Browser setzt das Fenster nach
  oben. Wer bei Nummer 300 stand, sah danach den Anfang. Jetzt werden Platz
  und Kartenzahl gemerkt und danach wieder eingenommen

> Ausgelöst wurde das nicht nur, wenn jemand etwas anlegt: auch beim bloßen
> Zurückkommen aus einem anderen Fenster und nach jedem Preisabruf, der
> einen Kaufpreis nachträgt – dessen Summe steckt im Fingerabdruck, an dem
> die App Änderungen erkennt.

- 🪟 **Ein offenes Popup wurde vom Auffrischen weggeräumt.** Wer darin gerade
  etwas eintrug, verlor es mitten im Satz. Jetzt wartet das Auffrischen, bis
  das Popup zu ist, und holt es dann nach

## 2.11.0 – August 2026

### Behoben
- 🖼 **Karten holten Bilder in sechsfacher Größe.** Katalogbilder liegen mit
  400 px auf der Instanz, angezeigt werden sie in den Karten mit **72**. Der
  Browser entpackt aber immer die volle Größe – 0,6 MB je Bild, und zwar
  **außerhalb** des JS-Speichers, wo keine Messung hinschaut. Jetzt gibt es
  eine Daumennagel-Fassung mit 160 px; die Großansicht bekommt weiter das
  volle Bild

> **Warum das kein Schönheitsfehler ist.** In einem eingeschickten Verlauf
> standen **839 Bilder** in einer Ansicht, bei 8 MB JS-Speicher. Entpackt
> sind das rund **500 MB**, die in keiner Kurve auftauchen – und wenige
> Sekunden später brach der Tab ab. Mit 160 px bleiben davon 85 MB.
>
> | Ansicht | vorher | nachher |
> |---|---|---|
> | 130 Bilder | 79 MB | 13 MB |
> | 839 Bilder | 512 MB | 85 MB |
>
> Erzeugt wird die kleine Fassung einmal und liegt dann neben dem Original.
> Freie Größen bedient der Server nicht – sonst könnte man ihn mit 500
> Anfragen 500 Dateien schreiben lassen.

## 2.10.1 – August 2026

### Behoben
- 🔁 **Jeder Ansichtswechsel lud die Ansicht ein zweites Mal.** Der neue
  Änderungs-Fühler verglich mit `letzterStand && letzterStand[name]` – das
  ergibt **`null`**, wenn noch nichts gemerkt ist, und `null !== undefined`
  ist wahr. Damit galt der erste Blick nach jedem Wechsel als Änderung, und
  die gerade frisch geladene Ansicht lud sofort erneut. Bei einer Sammlung
  mit hundert Bildern ist das kein Schönheitsfehler

> Im eingeschickten Verlauf war es gut zu sehen: `10:45:35 Ansicht: lists`,
> zwei Sekunden später „lade neu"; `10:45:48 Ansicht: collection`, fünf
> Sekunden später wieder. Jetzt: drei Wechsel, kein einziger Ladevorgang –
> und eine echte Änderung von außen kommt weiterhin an.

## 2.10.0 – August 2026

### Neu
- 📡 **Die Ansicht hält sich von selbst aktuell – ohne Fensterwechsel.**
  2.9.0 frischte beim Zurückkommen auf; wer die App aber **neben** einem
  anderen Fenster liegen hat, will gar nicht erst wechseln müssen. Jetzt
  fragt Brickfolio alle fünf Sekunden nach einem **Fingerabdruck** der Daten
  – eine Handvoll Zahlen, kein Datenbestand – und lädt die offene Ansicht
  nur dann neu, wenn er sich geändert hat

> **Gemessen:** Einkaufsliste offen und aufgeklappt, von außen eine vierte
> Figur dazugelegt, den Browser **nicht angefasst** – acht Sekunden später
> stand sie da. Die Liste blieb dabei offen, und es wurde genau **einmal**
> geladen.
>
> Der Fingerabdruck zählt nicht nur Zeilen: Menge, Haken und Preis gehen
> mit ein, sonst fiele das Ändern einer bestehenden Zeile nicht auf. Ein Tab
> im Hintergrund fragt gar nicht, und der Scannen-Tab wird nie aufgefrischt.

## 2.9.0 – August 2026

### Neu
- 🔄 **Die Ansicht frischt sich auf, wenn ihr zum Tab zurückkommt.** Bisher
  wurde beim Zurückkehren nur das Tausch-Netzwerk abgefragt – Sammlung,
  Listen und Statistik blieben auf dem Stand von vorhin. Das fällt auf,
  sobald **mehr als ein Weg** in die Daten führt: ein Familienmitglied am
  Handy, ein zweiter Tab, oder ein Werkzeug an der Schnittstelle. Man sah
  dann eine Liste, die es so nicht mehr gab

> **Zwei Einschränkungen mit Absicht:** Der **Scannen-Tab** bleibt
> unberührt – dort steht womöglich ein Foto samt Treffern, und das darf ein
> Fensterwechsel nicht wegräumen. Und wer nur kurz hin- und herklickt, löst
> nichts aus; erst ab vier Sekunden Abwesenheit wird geladen.
>
> Gemessen: Liste mit 1 Artikel offen, von außen ein zweiter dazu, Fenster
> gewechselt – danach **2 Artikel, Einkauf 13,00 €**. Und bei 0,3 Sekunden
> Wegklicken: kein einziger Ladevorgang.

## 2.8.4 – August 2026

### Behoben
- 🖼 **Zwei Bilder im README wurden gar nicht angezeigt.** Die
  Alternativtexte enthielten typografische Anführungszeichen („…"), womit
  GitHub die `<img>`-Auszeichnung nicht mehr las – statt der Bilder stand
  dort der nackte Quelltext. Die Alternativtexte sind jetzt schlicht

### Geändert
- 📸 **Kein fremdes Bildmaterial mehr in den Abzügen.** Die neuen
  Bildschirmabzüge zeigten Katalogbilder von BrickLink. Die vorhandenen
  Abzüge kommen seit jeher ohne aus – sie zeigen den Platzhalter der App.
  Neu erzeugt, jetzt genauso; die Fotos in der Galerie sind selbst erzeugte
  Beispielbilder

## 2.8.3 – August 2026

### Neu
- 🐢 **Der Speicher-Verlauf sagt jetzt, ob der schonende Bildmodus lief.**
  Jede Messzeile trägt bei eingeschaltetem Modus ein `🐢 schonend`. Ohne
  diese Angabe ließe sich hinterher nicht sagen, welcher der beiden Wege in
  einer Sitzung aktiv war – und der Vergleich, wofür der Modus gebaut wurde,
  wäre wertlos

## 2.8.2 – August 2026

### Behoben
- 🔢 **„1 Bilder, 24 KB".** In der Sicherungskarte stand die Mehrzahl auch bei
  einem einzigen Bild. Beim Erstellen der neuen README-Bilder aufgefallen –
  wer Abzüge macht, liest die Oberfläche eben zum ersten Mal wieder genau

### Dokumentation
- 📸 **Neue Bildschirmabzüge im README**: Scan-Treffer mit dem Kästchen fürs
  eigene Foto und dem Knopf „Nur Foto dazu", die Galerie mit Katalogbild und
  eigenem Foto nebeneinander, sowie die Sicherung mit „Eigene Bilder
  mitsichern". Der alte Scan-Abzug zeigte den Stand von Mitte Juli
- 📖 Die Funktionsliste nennt die eigenen Fotos und die Bilder in der Sicherung

## 2.8.1 – August 2026

### Aufgeräumt
- 🧹 **Totes Feld `letzteBoxen`** entfernt – wurde nie gelesen und stand
  verwirrend neben `scanBoxen`, das dasselbe hält und tatsächlich benutzt wird
- 🧹 **Vier CSS-Regeln** für den Anzahl-Block, den es seit 2.1.0 nicht mehr
  gibt
- 🏷 **Klasse `eigenbild-wahl` → `wahl-kasten`.** Sie gilt längst für drei
  Kästchen – Scan-Foto, Sicherung, schonender Modus – und der alte Name
  behauptete etwas anderes

### Dokumentation
- 📖 **„Browser aktualisieren" allein reicht nicht.** Das Handbuch legte das
  nahe; tatsächlich war nach dem Edge-Update die alte Bucket-ID verschwunden
  und sofort eine **neue** da – gleiche Art Fehler, andere Stelle. Steht
  jetzt so drin, samt einer Reihenfolge, was zu tun bleibt

## 2.8.0 – August 2026

### Neu
- 🐢 **Schonender Bildmodus** (*Mehr → Fehlerbericht*, standardmäßig aus).
  Diese App entpackt Fotos, malt sie auf Zeichenflächen, liest Bildpunkte
  aus und kodiert wieder – Arbeit, die der Browser gern auf die
  **Grafikeinheit** schiebt und die kaum eine andere Seite ihm gibt. Der
  Modus geht denselben Weg zu Fuß, im Hauptspeicher: Entpacken über ein
  gewöhnliches Bildelement statt `createImageBitmap`, Zeichenflächen mit
  `willReadFrequently`. Etwas langsamer, sonst gleich

> **Wofür das gut ist:** Bricht der Tab beim Scannen ab, während die
> Speicherkurve flach bleibt, lässt sich damit prüfen, ob es an diesem Weg
> liegt. Gemessen liefern beide Modi dasselbe Ergebnis (3000×2000 → Vorschau
> 1200×800, gleicher Treffer, gleiche Dauer).
>
> Ehrlicherweise: Ein Absturz **ohne jeden Scan** zeigt, dass es nicht nur
> daran liegen kann. Der Modus ist ein Werkzeug zum Eingrenzen, kein Heilmittel.

### Behoben
- ⏳ **`img.decode()` blieb an einem losen Bild hängen.** Beim Bauen des
  schonenden Modus aufgefallen: Ein Bild, das nicht im Dokument hängt, gibt
  das Versprechen unter Umständen nie zurück – der ganze Scan blieb stehen.
  `onload` genügt für das Weiterzeichnen

## 2.7.1 – August 2026

### Behoben
- 🧹 **Das entpackte Foto blieb nach „Foto dazu" liegen.** Um den Ausschnitt
  zu schneiden, entpackt die App das Original in Arbeitsgröße – bis zu
  2400 px, gemessen **16 MB**. Alle anderen Wege gaben es danach wieder frei,
  der neue Foto-Weg aus 2.5.0 als einziger nicht: Es lag bis zum nächsten
  Foto herum. Jetzt geht es acht Sekunden nach dem letzten Gebrauch weg, und
  beim Verlassen des Scan-Tabs sofort

> **Warum das in keiner Kurve zu sehen war:** Eine entpackte Bitmap liegt
> **außerhalb** des JS-Speichers. Der Verlauf unter *Mehr → Fehlerbericht*
> zeigte weiter flache 6 MB – im Browser lagen die 16 MB trotzdem. Genau
> solche unsichtbaren Brocken sind es, die einen Tab umbringen, während die
> Kurve nichts anzeigt.
>
> Ein Test wacht darüber, dass **jede** Stelle, die einen Ausschnitt
> schneidet, das Arbeitsbild auch wieder loslässt.

## 2.7.0 – August 2026

### Neu
- 📷 **„Nur Foto dazu" auf der Trefferkarte.** Steht die Figur längst in der
  Sammlung und man will bloß ein Bild davon hinterlegen, genügt jetzt ein
  Tipp. Der Knopf hängt das Foto an den Artikel und rührt sonst nichts an –
  keine zweite Zeile, keine erhöhte Menge, kein Listeneintrag

> Er wirkt **unabhängig vom Kästchen** oben: Das gilt fürs Anlegen, hier ist
> das Foto der ganze Zweck. Bei mehreren erkannten Figuren nimmt auch dieser
> Weg den Ausschnitt, in dem die jeweilige gefunden wurde.

## 2.6.1 – August 2026

### Behoben
- 🪟 **„Mein Foto entfernen?" ging hinter der Großansicht auf.** Die Rückfrage
  lag auf Ebene 80, die Großansicht auf 100 – man sah die Frage nur
  abgedunkelt durchschimmern und die Aktion schien zu hängen. Rückfragen
  liegen jetzt über allem außer dem Toast

> Ein Test hält die Reihenfolge fest: Rückfrage über Großansicht, Toast über
> allem. Sonst rutscht das beim nächsten Umbau wieder durcheinander.

## 2.6.0 – August 2026

### Geändert
- 📷 **Das eigene Foto kommt jetzt *neben* das Katalogbild, nicht an seine
  Stelle.** In 2.5.0 hat es das Katalogbild ersetzt – das war nicht gemeint.
  Gedacht ist es wie die Bilder, die Käufer bei BrickLink beisteuern: Das
  Katalogbild bleibt das erste, was man sieht, das eigene Foto kommt daneben

### Neu
- 🖼 **Galerie mit den eigenen Fotos.** Tippt auf das Bild eines Artikels und
  blättert: Erst das Katalogbild, dann eure Fotos. Bei einem eigenen steht
  oben **„mein Foto"**, und unten erscheint **🗑 Mein Foto entfernen**
- 💾 **Eigene Bilder gehen in die Sicherung mit.** Sie sind Dateien, keine
  Datenbankzeilen – bisher trug die Sicherung nur den Verweis, und nach einem
  Umzug zeigten die Artikel ins Leere. Jetzt steht in der Sicherungs-Karte
  ein Kästchen mit Anzahl und Größe; die Bilder wandern als Teil derselben
  JSON-Datei mit und werden beim Einspielen unter ihren alten Namen wieder
  angelegt. Gilt auch für die Sicherung beim allerersten Start

> **Die Fotos hängen am Artikel, nicht an der Sammlungszeile.** Wer dieselbe
> Figur zweimal hat – einmal neu, einmal gebraucht –, sieht bei beiden
> dieselben Fotos. Es ist ja dieselbe Figur.
>
> Ab etwa 150 MB Bildern verweigert die App das Mitsichern und sagt es auch;
> dann gehört `data/uploads/` ins normale Backup.

## 2.5.0 – August 2026

### Neu
- 📷 **Das eigene Scan-Foto als Bild des Artikels.** Über den Treffern steht
  ein Kästchen: **„Mein Foto statt des Katalogbilds"**. Ist es angehakt,
  bekommt alles, was aus diesem Scan angelegt wird – Sammlung, Wunschliste
  **und** Einkaufsliste – das eigene Bild
- 🧩 **Bei mehreren Figuren jeweils der eigene Ausschnitt.** Nicht einmal das
  ganze Regalfoto für alle, sondern genau der Rahmen, in dem die Figur
  gefunden wurde – gleich, ob er aus der Reihum-Suche stammt, von einem
  gemerkten Rahmen oder von einem selbst gezogenen

> **Standardmäßig aus**, denn ein Katalogbild ist meist das sauberere; die
> Entscheidung merkt sich die App auf dem Gerät. Hochgeladen wird erst beim
> Anlegen – wer nur schaut oder abbricht, lädt nichts hoch.

### Dokumentation
- ⚠️ **Was die Sicherung nicht enthält.** Eigene Bilder sind Dateien in
  `data/uploads/`, keine Datenbankeinträge. Die JSON-Sicherung trägt den
  **Verweis** darauf, nicht die Datei. Beim Umzug gehört `data/uploads/`
  also mit kopiert – das galt immer schon für eigene Figuren, stand aber
  nirgends. Jetzt steht es in beiden Handbüchern

## 2.4.4 – August 2026

### Behoben
- 📋 **Kopieren scheiterte trotz Rückfallweg.** Die Reihenfolge war falsch
  herum. `navigator.clipboard.writeText` liefert ein Versprechen – wer darauf
  wartet, gibt die **Benutzergeste** des Klicks aus der Hand, und genau die
  verlangt der Rückfallweg `execCommand`. Schlug die moderne Schnittstelle
  fehl, kam der Rückfall zu spät: Er half nur, wenn er gar nicht nötig war.
  Jetzt läuft erst der **synchrone** Weg, das Versprechen danach

### Neu
- 🆘 **Und wenn beides nichts wird, ist der Text trotzdem da.** Statt einer
  Absage legt die App ihn in einem Fenster **fertig markiert** hin –
  Strg/Cmd+C genügt
- 🔍 **Die Absage nennt jetzt den Grund.** In Klammern hinter der Meldung, und
  zusätzlich im Verlauf unter *Speicher-Verlauf*. „Geht nicht" allein war als
  Auskunft wertlos

## 2.4.3 – August 2026

### Geändert
- 🧩 **„Script error." sieht nicht mehr nach einem Defekt aus.** Der Eintrag
  stand ohne Datei und Zeile zwischen echten Fehlern. Er kommt aber gar nicht
  aus der App: Fehler aus **fremden Skripten** kürzt der Browser aus
  Sicherheitsgründen auf genau diesen Satz zusammen – in Frage kommen
  Erweiterungen, Inhaltsblocker und was der Browser selbst einspritzt. Solche
  Einträge sind jetzt als **🧩 Kein Fehler der App** beschriftet, auch die
  schon gespeicherten
- 🔎 **Und sie tragen jetzt etwas bei.** Wo der Browser Datei und Zeile
  verschweigt, hängt die App die **letzten Schritte vor dem Fehler** an. Damit
  lässt sich wenigstens sehen, wobei es passiert

> Die Aussage steht auf einem prüfbaren Fundament: Die Seite lädt zwei eigene
> Skripte und bindet keine Rahmen ein. Ein Test wacht darüber – käme je ein
> fremdes Skript dazu, wäre die Beschriftung eine Lüge und der Test rot.

## 2.4.2 – August 2026

### Behoben
- 🙈 **Benutzernamen auf dem Anmeldebogen.** Nach dem Einspielen einer
  Sicherung (2.4.0) stand dort „Jetzt anmelden als: Sven, nerdfan" – gedacht
  als Hilfe, tatsächlich aber eine Liste aller Admin-Namen auf einer Seite,
  an der noch niemand angemeldet ist. Der Hinweis nennt jetzt keine Namen
  mehr, und auch das Namensfeld bleibt leer

> Der Endpunkt gibt die Namen gar nicht erst heraus – nicht nur die Anzeige
> ist weg, sondern die Quelle. Wer die Sicherung eingespielt hat, kennt seine
> Zugangsdaten ohnehin.

## 2.4.1 – August 2026

### Neu
- 🔢 **Version steht auf dem Startbildschirm.** Klein und grau unter der
  Anmeldekarte („Brickfolio 2.4.1"). Wer mehrere Instanzen betreibt, sieht
  jetzt ohne Anmeldung, welche er gerade vor sich hat – und wer einen Fehler
  meldet, muss die Version nicht erst suchen

> Verraten wird damit nichts Neues: Die Version stand auf dieser Seite
> ohnehin schon, nur unsichtbar – an den Versionsmarken der Dateien
> (`style.css?v=…`), die jeder Seitenquelltext zeigt.

## 2.4.0 – August 2026

### Neu
- 📥 **Sicherung gleich beim ersten Start einspielen.** Wer umzieht, hatte
  bisher einen unnötigen Umweg: erst ein Admin-Konto anlegen, das die
  Sicherung gleich darauf wieder überschreibt. Jetzt steht im Willkommens-
  Bogen unter dem Anlegen-Knopf **„📥 Sicherung einspielen"** – der ganze
  alte Stand kommt herüber, samt Konten. Danach meldet man sich mit den
  **bisherigen Zugangsdaten** an

> **Ohne Anmeldung – ist das in Ordnung?** Ja, denn es geht nur, solange die
> Instanz **leer** ist. Wer sie in diesem Zustand erreicht, könnte ohnehin
> das erste Admin-Konto anlegen und wäre damit Herr über alles; der Weg gibt
> also nichts preis, was nicht schon offenstünde. Sobald ein Benutzer
> existiert, antwortet er nur noch mit einer Absage.

## 2.3.1 – August 2026

### Behoben
- 👥 **Fehler 500 beim Entfernen eines Benutzers.** Freigeräumt wurde nur die
  Sammlung. Auf den Benutzer zeigen aber noch vier weitere Stellen – Wünsche,
  angelegte Listen, abgehakte Listeneinträge und die Push-Anmeldung –, und die
  Datenbank ließ das Löschen deshalb nicht zu. Wer also irgendetwas davon
  hinterlassen hatte, war nicht zu entfernen

> **Was jetzt mit seinen Sachen passiert:** Sammlung, Wünsche, Listen und
> Haken bleiben – sie gehören der Instanz, nicht der Person; nur der Name
> dahinter verschwindet. Mit gelöscht wird allein die Push-Anmeldung, damit
> sein Gerät keine Meldungen dieser Instanz mehr bekommt.

## 2.3.0 – August 2026

### Behoben
- 📋 **„Kopieren nicht möglich" im Heimnetz.** Die Knöpfe zum Kopieren –
  Fehlerbericht, Wiederherstellungscode, Cloudflare-Befehl, Diagnose – gingen
  nur über `https://` oder `localhost`. Ruft man die App über die IP-Adresse
  im Heimnetz auf, ist das kein *sicherer Kontext*, und der Browser rückt die
  Zwischenablage nicht heraus. Jetzt gibt es einen Rückfallweg über ein
  unsichtbares Textfeld, der auch dort kopiert

> Der Rückfallweg braucht einen echten Klick – das ist der Grund, warum er
> nicht überall greifen kann, sondern nur an den Kopier-Knöpfen selbst.
> Geprüft mit ausgeblendeter Zwischenablage: echter Klick, echter Text.

### Geändert
- 🔤 **Gleicher Name überall.** Fenstertitel und der Name der installierten
  App schrieben `Svens Brickfolio`, die Überschrift in der App dagegen
  `Sven's Brickfolio`. Jetzt steht überall dasselbe

## 2.2.0 – August 2026

### Behoben
- 📱 **„Finn's Brickfolio" auf jedem Handy.** Legte man die App auf den
  Startbildschirm, stand dort der fest eingebaute Name – auch auf einer
  Instanz, die längst anders heißt. Manifest, Fenstertitel und der Name für
  iOS kommen jetzt aus dem **Anzeigenamen** unter *Mehr → Anzeigename*
- 🖼 **Und „FINN" stand im Symbol.** Das App-Symbol wird jetzt erzeugt: die
  bekannte Zeichnung, darüber der Anzeigename der Instanz. Die Schriftgröße
  richtet sich nach der Länge, damit auch längere Namen hineinpassen

> Gebraucht wird dafür keine mitgelieferte Schriftdatei – Pillow bringt eine
> skalierbare Standardschrift mit, die auch im schlanken Docker-Abbild
> vorhanden ist. Erzeugt wird je Name und Größe einmal, danach kommt das
> Symbol aus dem Zwischenspeicher.

## 2.1.1 – August 2026

### Behoben
- 🧭 **„Reihum-Suche fertig (–)" statt der Zahl.** Endete die Suche endgültig,
  war der Suchstand beim Schreiben der Protokollzeile schon freigegeben – im
  Verlauf stand dann ein Strich statt der Zahl der gefundenen Figuren. Jetzt
  steht dort, was wirklich gefunden wurde

> **Was der Verlauf vom 2.8. sonst zeigt:** Die Wiederherstellung aus 2.0.0
> hat gegriffen – nach dem Absturz um 00:16:19 setzte die App bei „Listen"
> wieder auf, also genau dort, wo die Sitzung aufgehört hatte. Und das
> Weitersuchen aus 2.1.0 lief: 10 Figuren, dann eine elfte.

## 2.1.0 – August 2026

### Neu
- 🔎 **Weitersuchen statt Wand.** Die Reihum-Suche hört nach 10 Figuren auf –
  das ist keine technische Grenze, sondern Rücksicht auf einen kostenlos
  bereitgestellten Dienst. Sind noch Figuren da, erscheint jetzt
  **🔎 Weitersuchen**: Die App macht dort weiter, wo sie aufgehört hat, und
  die neuen Funde kommen zu den bisherigen dazu
- 🧠 **Der Suchstand bleibt liegen**, solange weitergesucht werden kann – und
  wird freigegeben, sobald die Suche zu Ende ist oder ein neues Foto kommt.
  So kostet das Weitersuchen keine zweite Runde durch das ganze Bild

> **Gemessen an einem Bild mit 14 Figuren:** erster Durchgang 10, dann
> „Weitersuchen" → insgesamt 13 (die vierzehnte Anfrage ging an den
> Einzelscan beim Fotografieren). Rahmen und Karten stimmen nach beiden
> Durchgängen überein, der Knopf verschwindet, sobald nichts mehr kommt.

## 2.0.0 – August 2026

### Neu
- 💾 **Ein Abbruch kostet nichts mehr.** Verhindern lässt sich der
  Edge-Absturz nicht (siehe 1.99.0) – aber die App kommt jetzt zurück: Sie
  merkt sich die **offene Ansicht** und die **angefangene Eingabe** im
  Formular „Manuell erfassen". Nach einem Abbruch steht beides wieder da
- 🎯 **Nur nach einem Abbruch.** Bei einem normalen Start öffnet die App wie
  immer den Scan-Tab – niemand will nach dem Öffnen in den Einstellungen
  landen, nur weil er dort zuletzt etwas nachgesehen hat. Unterschieden wird
  am Abschiedszettel, der beim gewollten Ende geschrieben wird und beim
  Abwürgen eben nicht

> **Was nicht gerettet wird:** ein ausgewähltes Foto. Das ließe sich nur mit
> erheblichem Aufwand ablegen, und der Schaden ist gering – neu fotografieren
> dauert Sekunden. Ein halb ausgefülltes Formular mit Preis und Notiz ist das,
> was wirklich wehtut.

## 1.99.0 – August 2026

### Neu
- 🔎 **Der Absturz ist gefunden – und er liegt nicht in der App.** Die
  Absturzliste von Edge zeigt 17 Abstürze über vier Tage, **alle unter
  derselben Bucket-ID** und an derselben Stelle im Programm: `P6 = renderer`
  (der Tab selbst), `P3 = Microsoft_Edge_Framework` (Edges eigener Code),
  `P7 = 0x6` (auf macOS SIGABRT). Drei davon treffen sekundengenau die
  „OHNE ABSCHIED"-Einträge unseres Speicher-Verlaufs – die übrigen vierzehn
  hat die App nie gesehen, weil sie gar nicht offen war
- 💡 **Der Weg dorthin steht jetzt in der App.** Beim Speicher-Verlauf hängt
  ein Hinweis: Bleibt die Kurve flach und der Tab stirbt trotzdem, steht der
  echte Grund in `edge://crashes` – und gleiche Bucket-ID heißt gleicher
  Fehler des Browsers

> **Was das für die Diagnose bedeutet.** Sieben Versionen lang habe ich in der
> App gesucht: Hintergrundbilder, Glasflächen im Nova-Design, entpackte Fotos,
> die Sammlungsansicht. Jede These war messbar falsch, weil der Tab immer bei
> 6 bis 8 Megabyte starb – zuletzt im **Vordergrund**, auf einem Mac mit
> 16 GB. Die Zahlen haben die App früh entlastet; was fehlte, war der Blick in
> die Absturzliste des Browsers. Der steht jetzt dort, wo man ihn sucht.

## 1.98.0 – August 2026

### Behoben
- 🧭 **Die Reihum-Suche stand nicht in der Spur.** Sie kam in 1.97.0 dazu,
  schrieb aber nichts mit – und ausgerechnet in die 46 Sekunden davor fiel ein
  Absturz. Jetzt steht jede Runde einzeln drin: Start, jede gefundene Figur
  mit Nummer und Sicherheit, Ende
- 🧹 **Halber Speicherbedarf beim Suchen.** Bitmap und Zeichenfläche hielten
  dieselbe Bildfläche doppelt, bis die Schleife fertig war. Die Bitmap wird
  jetzt sofort nach dem ersten Zeichnen freigegeben; die Zeichenfläche wird
  auch bei einem Fehler zuverlässig geleert
- 🔁 **Abbruch bei doppeltem Fund.** Liefert der Dienst zweimal denselben
  Bereich, hört die Suche auf, statt bis zum Anschlag weiterzufragen

> **Gemessen:** fünf vollständige Durchläufe hintereinander, JS-Speicher
> 2,4 → 2,9 MB. Ein halbes Megabyte auf fünf Läufe ist kein Leck, das einen
> Tab umbringt – der Verdacht gegen den neuen Ablauf ist damit **nicht**
> bestätigt, aber auch nicht widerlegt. Dafür sagt es beim nächsten Mal die
> Spur.

## 1.97.0 – August 2026

### Neu
- 🔎 **Die App sucht die Figuren nicht mehr selbst – der Erkennungsdienst
  sucht.** Jede Antwort von Brickognize bringt einen Rahmen mit; er sagt also
  immer mit, *wo* er hingeschaut hat. „Alle Figuren erkennen" nutzt das jetzt
  reihum: erkennen, den gefundenen Bereich in **Hintergrundfarbe** ausblenden,
  erneut fragen – bis nichts mehr kommt
- 🎯 **Kommt mit Anordnungen zurecht, an denen alles bisherige scheiterte:**
  Figuren, die sich **berühren**, **mehrere Reihen**, kreuz und quer Liegendes.
  Gemessen an vier Klonkriegern dicht nebeneinander: **4 von 4 Figuren, 72–91 %
  sicher, in 1,2 Sekunden** – das alte Verfahren fand an derselben Aufnahme
  **gar nichts**
- 🧹 **206 Zeilen weniger.** Spaltenanalyse, Kantenberechnung, Talsuche, der
  Regler für die Streifenzahl und die Reihen-Warnung aus 1.93.0 sind
  ersatzlos entfallen – es gibt nichts mehr einzustellen und nichts mehr zu
  warnen

> **Warum es vorher nicht ging.** Das alte Verfahren maß die Struktur je
> Bildspalte und schnitt in den Lücken. Bei Figuren, die sich berühren, gibt es
> keine Lücke – deshalb kam bei Svens Foto in **keinem** Streifen etwas an.
> Der Dienst kann dagegen lokalisieren; das war die ganze Zeit da und wurde nur
> einmal statt mehrfach genutzt.

> **Gemessen, nicht vermutet.** Die Maskenfarbe entscheidet: Mit einer fest
> gewählten Farbe blieben nach drei Figuren harte Rechteckkanten stehen, die
> der Dienst für ein Objekt hielt – die vierte fand er nicht mehr. Mit der aus
> den Bildecken gemittelten Hintergrundfarbe: alle vier.

## 1.96.0 – August 2026

### Neu
- 🛡 **Bremse vor dem Erkennungsdienst.** Brickognize stellt seine Erkennung
  kostenlos bereit; jeder Ausschnitt ist eine eigene Anfrage. Der Server lässt
  jetzt **40 Erkennungen je Minute** für die ganze Instanz durch und weist
  darüber hinaus mit einer verständlichen Meldung ab. Die Grenze sitzt
  bewusst im Server – sie gilt damit für alle Benutzer und auch dann, wenn
  jemand an der Oberfläche vorbei anfragt
- 🔢 **Auch von Hand gemerkte Rahmen sind gedeckelt.** Die automatische
  Trennung hörte seit jeher bei 10 auf, die gemerkten Rahmen waren
  unbegrenzt. Jetzt gilt dieselbe Zahl für beide Wege

> **Geprüft und wieder verworfen:** Brickognize hat einen eigenen Endpunkt für
> Minifiguren (`/predict/figs/`). Zweimal gegen `/predict/` gemessen – einmal
> mit einem sauberen Figurenbild, einmal mit einem Ausschnitt samt
> Tischplatte und angeschnittenen Nachbarfiguren: **beide Male dasselbe
> Ergebnis, 89 % bzw. 90 %.** Kein Gewinn, dafür der Nachteil, dass man dann
> kein Set mehr einrahmen könnte. Bleibt also bei `/predict/`.

## 1.95.0 – August 2026

### Behoben
- 🟩 **Fünf Rahmen, unter denen „nichts erkannt" stand.** Die nummerierten
  Rahmen blieben stehen, egal was die Abfrage ergab – das Bild behauptete
  fünf gefundene Figuren, während darunter „Keine Übereinstimmung gefunden"
  zu lesen war. Jetzt bleiben **nur die Streifen stehen, in denen wirklich
  etwas erkannt wurde**; ergab keiner etwas, verschwinden alle und es steht
  dran, dass sich dieses Bild so nicht zerlegen lässt
- 🏷 **„Geteilt in: 5 Streifen" statt „Gefunden: 5 Figuren".** Vor der
  Abfrage weiß die App nur, wo sie geschnitten hat – nicht, was dort steht.
  Die Beschriftung sagt das jetzt

> **Warum die Warnung aus 1.93.0 hier nicht kam:** Sie misst die Figur, die
> der Erkennungsdienst beim ersten Scan gefunden hat, an der Bildhöhe. Findet
> er **gar nichts**, gibt es nichts zu messen. Für diesen Fall greift jetzt
> das Ergebnis selbst: Keine Treffer, keine Rahmen.

## 1.94.0 – August 2026

### Behoben
- 🔢 **Die geklärte BrickLink-Nummer galt nur halb.** Seit 1.92.0 fragt die
  App bei Rebrickable nach der BrickLink-Entsprechung (`2586pr0028` →
  `2586ps1`) – benutzt hat sie sie aber nur für die Zweitnummer. Die
  **Kategorie** wurde weiter mit der Nummer abgefragt, die BrickLink gar nicht
  kennt, und lief deshalb ins Leere. Jetzt wird die Nummer **einmal** geklärt
  und für beide Wege verwendet
- 🗂️ **Damit greift auch der Katalogpfad.** Teile ohne Zweitnummer bekommen
  ihre Kategorie als Thema: Aus *Catalog: Parts: Minifigure, Shield* wird
  **„Minifigure, Shield"** statt „Ohne Thema"
- ⚡ Die Kategorie-ID kommt jetzt mit dem Katalogeintrag mit – eine Abfrage
  weniger je Teil

> **Was das für die beiden Teile heißt.** Der Karbonitblock hat eine
> Zweitnummer (`sw0978`) und landet unter **Star Wars**. Der Gungan-Schild
> steht bei BrickLink ohne Zweitnummer, dort bleibt nur der Pfad: **Minifigure,
> Shield**. Das ist eine Form und kein Thema – wem das nicht passt, setzt auf
> der Karte von Hand „Star Wars".

## 1.93.0 – August 2026

### Behoben
- 🚫 **Vier Rahmen, die nichts bedeuteten.** Bei einem Regalfoto mit mehreren
  Reihen schnitt „🔎 Alle Figuren erkennen" das Bild in senkrechte Streifen –
  in jedem standen dann fünf Figuren übereinander. Angezeigt wurden vier
  nummerierte Rahmen, als wären es vier Figuren. Das ist schlimmer als kein
  Ergebnis
- ❓ **Jetzt fragt die App vorher.** Füllt die Figur, die der Erkennungsdienst
  beim ersten Scan gefunden hat, **weniger als ein Drittel der Bildhöhe**,
  steckt mehr als eine Reihe im Bild. Dann kommt ein Hinweis samt dem Weg
  über gemerkte Rahmen – „Trotzdem versuchen" bleibt möglich

> **Woher die App das weiß, ohne zu raten:** Der Erkennungsdienst liefert
> beim ersten Scan seinen eigenen Rahmen mit („hier geschaut"). Wie groß der
> im Verhältnis zum Bild ist, ist eine gemessene Zahl – keine Schätzung. Bei
> einem einreihigen Foto füllt die Figur 60 bis 90 % der Höhe, beim Regalfoto
> 15 %.

## 1.92.0 – August 2026

### Neu
- 🗂️ **Teile bekommen ihr Thema doch – über die Zweitnummer.** BrickLink
  führt Teile nach Form („Minifigure, Utensil, Decorated"), aber bedruckte
  Teile tragen im Katalog die Nummer der Figur, zu der sie gehören: Beim
  Karbonitblock mit Han Solo steht **`sw0978`** daneben – und `sw…` heißt
  Star Wars. „🔄 Themen nachladen" liest das jetzt aus
- 🔁 **Zwei Kataloge, zwei Nummern.** Rebrickable nennt dasselbe Teil
  `87561pr0001`, BrickLink `87561pb01`. Führt die eigene Nummer zu nichts,
  wird die Entsprechung bei Rebrickable erfragt und der Abruf wiederholt
- ✅ Ein echtes Thema hat Vorrang vor der Formkategorie

> **Korrektur zu 1.90.0.** Dort stand, für Teile ließe sich grundsätzlich
> nichts abrufen. Das stimmte nicht: Die *Kategorie* eines Teils sagt nichts
> über das Thema – die *Zweitnummer* sehr wohl. Der Hinweis bei „Ohne Thema"
> ist entsprechend richtiggestellt.

## 1.91.0 – August 2026

### Behoben
- 🔍 **Ausschnitte kamen aus der Vorschau statt aus dem Foto.** Zugeschnitten
  wurde bisher aus der auf 1200 Pixel verkleinerten Fassung – bei vielen
  Figuren im Bild blieb einer einzelnen damit kaum mehr als ein Daumennagel,
  und genau der ging zur Erkennung. Jetzt wird aus einer **Arbeitskopie mit
  2400 Pixeln** geschnitten: gemessen an einem 12-MP-Foto **238×334 statt
  120×168 Pixel – die vierfache Fläche**
- 💬 **Ein Hinweis statt Rätselraten.** Bleibt ein einzelner Treffer unter
  60 %, steht jetzt darüber, woran es liegt: Die Erkennung sucht **ein**
  Objekt je Anfrage – bei vielen Figuren im Bild hilft ein Rahmen oder ein
  Foto aus der Nähe

> **Warum nicht direkt aus dem Original geschnitten wird.** Gemessen: Ein
> Ausschnitt per Quellrechteck aus der 12-MP-Datei kostet rund 50 ms – **je
> Ausschnitt**, weil dabei jedes Mal das ganze Bild entpackt wird. Bei vierzig
> Figuren wären das vierzig volle Entpackvorgänge; daran ist der Tab schon
> gestorben. Einmal auf 2400 entpacken kostet dieselben ~300 ms **insgesamt**
> und hält rund 17 MB, deren Lebensdauer bekannt ist.

## 1.90.0 – August 2026

### Neu
- 🗂️ **Thema von Hand setzen.** Auf jeder Karte steht jetzt ein Feld
  **Thema** – mit Vorschlagsliste aus den Themen, die in der Sammlung schon
  vorkommen, damit nicht „Star wars" neben „Star Wars" entsteht. Leeren setzt
  den Eintrag zurück auf „Ohne Thema"
- 🔒 Ein von Hand gesetztes Thema **bleibt stehen**: Die Automatik rührt ein
  vorhandenes nie an

> **Warum das nötig ist.** Für **Teile** kann die Automatik grundsätzlich
> nichts liefern: BrickLink führt sie nach **Form** („Brick, Modified"), nicht
> nach Thema – da ist nichts abzurufen, was hier stehen könnte. Bei Minifiguren
> steckt das Thema in der Nummer (`sw…`), bei Sets in der Kategorie; bei Teilen
> gibt es diesen Weg nicht. „🔄 Themen nachladen" hilft dort also nie, und
> genau das steht jetzt auch bei der Gruppe „Ohne Thema".

## 1.89.0 – August 2026

### Neu
- 📱 **Welches Gerät?** Der Verlauf hält beim Sitzungsbeginn fest, worauf die
  App läuft: System, Browser, **als App oder im Browser**, Arbeitsspeicher des
  Geräts und Bildschirmgröße. Nach vier Abstürzen stand das in den Daten
  bisher nirgends
- ⏱ **„Abgestürzt nach … Minuten Laufzeit."** Die Zusammenfassung rechnet aus,
  wie lange eine Sitzung lief, bevor sie abbrach. Zweimal dieselbe Dauer wäre
  ein Muster und kein Zufall
- 🔄 **Der Update-Vorgang steht jetzt in der Spur**: nach Update gesucht,
  Update angefordert, Update-Sperre sichtbar, Server nicht erreichbar, Server
  wieder da, Server neu gestartet

> **Warum genau das.** Die beiden Abstürze vom 1.8. um 16:41 und 16:51 fielen
> beide in den Update-Vorgang – und die Sitzungen liefen **8:27** bzw. **9:14**
> Minuten, bevor der Tab starb. Der zweite lag außerdem **nicht** in der
> Scan-Ansicht, womit meine Vermutung von vorhin („beide beim Fotografieren")
> widerlegt ist. Beide Male: 7 MB von 4096 MB Grenze.

## 1.88.0 – August 2026

### Neu
- 🧭 **Eine Spur neben dem Speicher-Verlauf.** Zwischen zwei Messwerten
  liegen 30 Sekunden – ein Absturz wartet darauf nicht. Deshalb wird jetzt
  **sofort** festgehalten, was passiert: Foto aufgenommen (mit
  **Megapixeln und Dateigröße**), verkleinert auf …, Erkennung läuft/fertig,
  Ansicht gewechselt, **in den Hintergrund / wieder da**
- 📋 Die Spur steht unter der Kurve und geht beim Kopieren mit

> **Warum das nötig war.** Der Verlauf vom 1.8. zeigt zwei Stunden zwischen
> 5 und 9 MB, ohne jedes Wachstum – und trotzdem starb der Tab um 16:41 bei
> **7 MB und 981 Elementen**. Damit ist der JavaScript-Speicher als Ursache
> erledigt. Beide bisher auswertbaren Abstürze fielen in dieselbe Lage: die
> Scan-Ansicht bei rund 980 Elementen. Was dort groß ist, steht außerhalb
> jeder Messung – das Foto selbst und die Kamera-App daneben. Ob die Seite in
> dem Moment im Hintergrund war, sagt ab jetzt die Spur.

## 1.87.0 – August 2026

### Behoben
- 🗂️ **„LEGO Ideas &#40;CUUSOO&#41;" statt „LEGO Ideas (CUUSOO)".** BrickLink
  liefert Kategorienamen HTML-maskiert; bei Artikelnamen wurde das längst
  umgewandelt, bei den Themen nicht. Da die Oberfläche beim Anzeigen ein
  zweites Mal maskiert, stand die Maskierung selbst auf dem Bildschirm.
  Betrifft alle Themen mit Klammern oder Sonderzeichen im Namen
- 🔧 **Bestehende Einträge werden beim Start geradegezogen** – auch die schon
  gespeicherte Kategorieliste, ohne neuen Abruf. Nichts nachzuladen, das
  Update genügt

## 1.86.0 – August 2026

### Neu
- 📤 **Gegenstück zum Übernehmen: austragen.** Fragt jemand nach einem
  deiner Artikel und du nimmst an, geht das Stück ja weg. Dafür steht im
  Gespräch jetzt **📤 Aus der Sammlung austragen** – in Rot, damit es nicht
  mit dem grünen Übernehmen zu verwechseln ist
- ❓ **Neu oder gebraucht? Wird gefragt, nicht geraten.** Steht dieselbe
  Nummer zweimal in der Sammlung, fragt das Fenster **„Welches Stück?"**.
  Ohne Antwort passiert nichts – ein geratener Zustand wäre ein verlorenes
  Exemplar
- ⏳ **„noch nicht ausgetragen"** an angenommenen eingehenden Vorgängen,
  passend zum „noch nicht verbucht" der anderen Richtung

Ausgetragen wird ausschließlich nach Bestätigung im App-Fenster: Artikel,
Gegenüber und der Bestand stehen darin, dazu die Anzahl. Bleibt nichts übrig,
verschwindet die Zeile samt Kaufbuch – wie beim Austragen über die Karte.

## 1.85.0 – August 2026

### Behoben
- 🤝 **„Annehmen" tat sichtbar nichts.** Der Vorgang wurde zwar auf
  *angenommen* gesetzt, aber bei einem schon angenommenen Tausch änderte sich
  nichts auf dem Bildschirm – und vor allem: Der Artikel selbst blieb außen
  vor und musste von Hand nachgetragen werden. Jetzt bestätigt eine Meldung
  die Zusage, und es geht direkt das Fenster **Tausch übernehmen** auf

### Neu
- 📥 **Angenommene Tausche verbuchen.** Wohin (Sammlung oder eine
  Einkaufsliste), Anzahl, Zustand, bezahlter Preis – der Eintrag entsteht wie
  ein normaler: gleiche Nummer erhöht die Anzahl, der Preis landet im
  Kaufbuch, in den Notizen steht „Tausch mit …". Der Knopf steht im Gespräch
  unter dem Verlauf, solange der Tausch angenommen ist und der Artikel zu mir
  kommt
- ⏳ **„noch nicht verbucht"** an angenommenen Vorgängen in der Liste – bis
  der Artikel wirklich eingetragen ist. Gebucht wird nur auf Knopfdruck:
  Zwischen Zusage und Karton in der Hand liegen beim Tauschen gern ein paar
  Tage, und der Preis steht oft erst dann fest
- 🏷 **Art, Bild und Zustand reisen mit der Anfrage mit.** Gespeichert waren
  bisher nur Nummer und Name; damit ließ sich ein Tausch nicht sauber
  übernehmen. Ältere Vorgänge raten die Art aus der Nummer (reine Ziffern =
  Set)

## 1.84.0 – Juli 2026

### Behoben
- 📷 **Ein Handyfoto wurde vollständig entpackt, bevor es verkleinert
  wurde.** Bei 12 Megapixeln sind das **46 MB in einem Stück**, bei einem
  50-MP-Handy rund 200 MB – außerhalb des JS-Speichers, wo keine Messung
  etwas sieht. Jetzt wird schon **beim Entpacken** verkleinert: gemessen
  **46 MB → 4 MB, 91 % weniger**
- 🔁 **Jeder Ausschnitt entpackte das Foto neu.** Bei fünf Figuren fünfmal
  gut 20 MB, zeitweise nebeneinander. Jetzt wird einmal entpackt und für
  alle Ausschnitte wiederverwendet – gemessen **1 statt 5**

> **Warum das jetzt kommt.** Der Absturz vom 31.7. um 21:58 trug „OHNE
> ABSCHIED", geschah im **klassischen** Design – die Glasflächen aus 1.77.0
> waren es also nicht – und zwar bei **980 Elementen und 6 Bildern**, während
> fotografiert wurde. Die Seite war winzig, der JS-Speicher bei 6 MB. Was in
> diesem Moment groß ist, ist das entpackte Foto.

## 1.83.0 – Juli 2026

### Neu
- 🖐 **Mehrere Rahmen sammeln.** Die automatische Trennung sucht senkrechte
  Lücken – sie ist für Figuren gemacht, die **nebeneinander** stehen. Liegen
  sie kreuz und quer oder versetzt hintereinander, gibt es keine Lücke, an
  der sich schneiden ließe. Deshalb jetzt: Rahmen ziehen, **➕ Rahmen
  merken**, für jede weitere Figur wiederholen, **🔎 Alle erkennen**. Das
  funktioniert bei jeder Anordnung, weil die Grenzen von Hand kommen

### Behoben
- 🟩 **Zwei grüne Rahmen mit zwei Bedeutungen.** Der Rahmen des
  Erkennungsdienstes stand neben den nummerierten und sah aus wie eine
  weitere Figur. Er trägt jetzt die Beschriftung **„hier geschaut"** und
  verschwindet, sobald nummerierte Rahmen da sind

> **Was ich versucht und wieder verworfen habe.** Eine Trennung in Flächen
> statt Streifen, damit auch kreuz und quer liegende Figuren automatisch
> gefunden werden. In vier Anläufen kippte das Ergebnis jedes Mal: mal fehlten
> Figuren, mal wurde ein Lichtreflex mitgezählt. Jede Stellschraube half
> einem Fall und schadete einem anderen. Statt weiter an Schwellwerten zu
> drehen, bleibt die Automatik bei dem, was sie nachweislich kann – Figuren
> nebeneinander – und für alles andere gibt es den Weg von Hand, der immer
> stimmt.

## 1.82.0 – Juli 2026

### Neu
- ➕ **Die BrickLink-Endung kommt beim Erfassen von selbst dazu.** Wer bei
  einem Set `21306` eintippt – die Zahl von der Packung –, bekommt `21306-1`
  und landet damit sofort in derselben Zeile wie ein gescanntes Exemplar.
  Vorbeugen statt hinterher zusammenführen. Gilt auch für Wunschliste und
  CSV-Import
- 🏷 **Der Katalogname hat Vorrang.** Sind die BrickLink-Schlüssel hinterlegt,
  wird beim Ergänzen der Nummer gleich der offizielle Name übernommen –
  „Yellow Submarine" statt „gelbes U-Boot vom Flohmarkt". Ohne Schlüssel
  bleibt der eingetippte stehen, und eine Erfassung scheitert nie daran,
  dass der Katalog gerade nicht antwortet
- Beim Zusammenführen zweier Zeilen gilt derselbe Grundsatz: Es bleibt die
  BrickLink-Zeile **samt ihres Namens**

> **Angefasst wird nur, was eindeutig ist:** eine reine Zahl bei einem
> **Set**. Figurennummern, Teilenummern, eigene Nummern und alles mit
> vorhandener Endung bleiben unverändert.

## 1.81.0 – Juli 2026

### Neu
- 🔗 **Dieselbe Nummer, zweimal erfasst.** Auf der Packung steht `21306`,
  BrickLink führt dasselbe Set als `21306-1`. Wer eines von Hand einträgt und
  das andere scannt, hatte zwei Zeilen für ein Set – und die Sammlung zählte
  es doppelt. Die App erkennt solche Paare jetzt und fragt auf der Scan-Seite
  nach, mit **zwei** Antworten statt einer:
  - **Ein Exemplar** – derselbe Kasten, zweimal erfasst. Eine Zeile bleibt,
    das Kaufbuch der aufgegebenen fällt weg (sonst stünde der Betrag doppelt
    drin)
  - **Zwei Exemplare** – ihr besitzt wirklich zwei. Stückzahlen werden
    addiert, beide Käufe bleiben im Kaufbuch
- Bleiben darf die Zeile mit der **BrickLink-Nummer** – sie hat Preise,
  Set-Inhalte und passt zum Katalog

> **Wo die App sich heraushält:** Bei zwei echten Varianten wie `21306-1` und
> `21306-2` kommt kein Hinweis. Das sind zwei verschiedene Ausgaben, und
> welche gemeint ist, weiß nur der Mensch davor. Aus demselben Grund führt
> die App auch nichts von allein zusammen.

## 1.80.0 – Juli 2026

### Behoben
- 📷 **Figurentrennung, die auch in der Vitrine funktioniert.** Der erste
  Anlauf (1.79.0) verglich jeden Bildpunkt mit einer aus dem Bildrand
  geschätzten Hintergrundfarbe. Auf weißem Papier geht das – in einer
  Vitrine nicht: Das Glas spiegelt, der Regalboden ist hell, die Rückwand
  blaugrau und die Figuren sind genau so blaugrau. Es gibt keine Farbe, von
  der sie sich abheben
- Jetzt zählt **Struktur statt Farbe**: Wo eine Figur steht, wechseln
  Helligkeiten dicht an dicht – Helm, Arme, Gürtel; die Lücke daneben ist
  ruhig. Geschnitten wird in den Tälern dieser Kantendichte, und zwar dort,
  wo sie **ausgeprägt** sind: Gemessen lagen echte Lücken bei einer
  Ausprägung von 58, Rauschen bei 17 bis 22
- 🔢 **Die Zahl lässt sich nachbessern.** Unter dem Bild steht, wie viele
  Figuren gefunden wurden, mit **−** und **＋**. Wer die Zahl ändert, bekommt
  das Bild gleichmäßig geteilt und alles erneut abgefragt – das hilft bei
  Figuren, die sich berühren, wo es keine Lücke zum Schneiden gibt
- ✂️ **Der Ausschnitt geht über die volle Bildhöhe.** Vorher endete er dort,
  wo die Kantendichte nachließ – und das ist bei einer Figur der Helm:
  rund, ruhig, kaum Kanten. Gemessen fehlte er im Ausschnitt

## 1.79.0 – Juli 2026

### Neu
- 🔎 **Alle Figuren auf einem Bild erkennen.** Der Dienst kann nur **ein**
  Objekt je Anfrage – also trennt die App die Figuren jetzt selbst: Sie
  schätzt aus dem Bildrand die Hintergrundfarbe, sucht die abweichenden
  Flecken, fasst Kopf, Körper und Beine einer Figur zusammen und schickt
  jeden Bereich einzeln zur Erkennung. Die Figuren werden nummeriert
  eingerahmt, darunter steht für jede eine eigene Karte
- Ein Foto von vier Figuren statt vier Fotos

> **Bedingung:** einfarbiger Hintergrund und etwas Abstand zwischen den
> Figuren – dieselben Bedingungen, die der Erkennung ohnehin guttun. Findet
> die Trennung nur eine Figur, sagt die App das; dann hilft der Rahmen von
> Hand aus 1.78.0.

## 1.78.0 – Juli 2026

### Neu
- 🔍 **Mehrere Figuren auf einem Bild.** Die Erkennung sucht **ein** Objekt je
  Anfrage – so ist der Dienst gebaut, seine Antwort enthält genau einen
  Rahmen. Bisher hieß das: Bei fünf Figuren auf dem Tisch riet sie über eine
  davon, und niemand sah, über welche.
- Jetzt umrahmt die Vorschau die erkannte Figur **grün**, und für die
  übrigen zieht man einfach einen **eigenen Rahmen** und tippt auf
  **🔍 Diesen Ausschnitt erkennen**. Zugeschnitten wird im Browser, zum
  Server geht nur der Ausschnitt – bei fünf Figuren fünf Rahmen statt fünf
  Fotos

## 1.77.0 – Juli 2026

### Neu
- 🪟 **Eigene Fenster statt Browser-Abfragen.** Sechs Stellen benutzten das
  graue `prompt()` des Browsers – eigene Schrift, eigene Farben, und für
  zwei Angaben zwei Fenster hintereinander. Jetzt fragt ein Fenster im Stil
  der App alles auf einmal: weiterer Kauf, neue Liste, mehr Einladungen,
  Passwort setzen. Mit Enter bestätigen, mit Esc abbrechen

### Verbessert
- 🧊 **Nova: weniger Glasflächen.** „Glas" heißt, dass der Browser den
  Hintergrund in Echtzeit weichzeichnet – jede solche Fläche kostet ihn eine
  eigene Zeichenfläche im Grafikspeicher, und **den sieht keine Messung**.
  Auf den Einstellungen lagen so **19 davon gleichzeitig**, und die Karte im
  Popup zeichnete weich, was die Überlagerung darunter schon weichgezeichnet
  hatte. Mehrfach vorkommende Flächen tragen jetzt eine durchscheinende
  Farbe – kaum zu sehen, aber statt rund zwanzig Zeichenflächen sind es drei
- 🔍 **Das Design steht jetzt im Speicher-Verlauf.** Nur so lässt sich
  überhaupt feststellen, ob Abstürze an Nova hängen

> **Warum das jetzt kommt.** Der Absturz vom 31.7. um 20:36 trug „OHNE
> ABSCHIED" – ein echter also – und passierte bei **2.005 Elementen und 64
> Bildern**. Die Seite war winzig. Damit ist klar, dass die Bilder nicht die
> Ursache waren; die Kosten liegen woanders, und Echtzeit-Weichzeichner sind
> der nächste Ort, an dem sie außerhalb jeder Messung anfallen.

## 1.76.1 – Juli 2026

### Verbessert
- 🧹 **Die Kaufpreis-Ecke der Karte aufgeräumt.** „Bezahlt" stand zweimal
  untereinander – einmal als Feld, einmal am Anfang der Gewinnzeile. Jetzt
  steht der Betrag einmal, das **＋ für einen weiteren Kauf** sitzt am Ende
  derselben Zeile statt als eigener Knopf in der Fläche, und die Gewinnzeile
  beginnt mit dem Wert. Ohne Marktpreis fällt sie ganz weg, statt nur den
  Betrag von oben zu wiederholen

## 1.76.0 – Juli 2026

### Neu
- 🧾 **Kaufbuch: mehrere Käufe zum selben Artikel.** Dasselbe Set einmal bei
  LEGO für 39,99 € und einmal im Markt für 34,99 € – in der Sammlung war das
  **eine** Zeile mit Stückzahl 2, und danach ließ sich nicht mehr sagen,
  welcher Kauf welcher war. Jetzt steht unter der Gewinnzeile die
  Aufstellung: Stückzahl, Preis, Quelle, Datum. **＋ Weiterer Kauf** trägt
  einen Posten ein (die Stückzahl wächst mit), **✕** nimmt ihn zurück
- Gilt für **Sets und Figuren** gleichermaßen – der Kauf hängt am Eintrag,
  nicht am Typ
- Der bisherige Bestand wird **übernommen**: Was heute als Kaufpreis
  dasteht, wird beim ersten Start ein Posten im Buch

> **Was sich nicht ändert.** Oben steht weiterhin die Summe, und mit ihr
> rechnen Statistik, Gewinn und die Einkaufslisten. Damit Summe und
> Aufstellung nicht auseinanderlaufen können, gehen alle sechs Stellen, die
> bisher einen Kaufpreis geschrieben haben – Anlegen, Zusammenführen,
> CSV-Import, Zustandswechsel, Bearbeiten, Verbuchen aus der Liste – jetzt
> durch denselben Weg.

## 1.75.0 – Juli 2026

### Neu
- 💬 **Ungelesene Nachrichten sieht man sofort.** Bisher stand der Zähler nur
  am Unter-Reiter im Tausch-Bereich – wer woanders war oder die App gerade
  erst geöffnet hatte, merkte von einer neuen Nachricht nichts. Jetzt sitzt
  ein Zeichen mit der Zahl **oben in der Kopfzeile**, von jedem Tab aus
  sichtbar. Ein Tipp führt direkt zu *Tausch → Meine Vorgänge*
- Ist nichts offen, ist auch **kein Zeichen** da – die Kopfzeile bleibt so
  ruhig wie vorher
- Beim Öffnen der App wird **einmal beim Hub nachgefragt**, statt nur den
  zuletzt bekannten Stand zu zeigen. Sonst stünde die Zahl bis zum nächsten
  Takt auf dem Wert von gestern

## 1.74.1 – Juli 2026

### Behoben
- 💬 **„Anfrage senden" ging gar nicht.** Der Wegweiser für
  `POST /api/hub/trades` stand seit dem 29. Juli über der falschen Funktion:
  Beim Einbau der Schlüsselprüfung landete eine interne Hilfsfunktion
  zwischen dem Wegweiser und dem Vorgang, der dort hingehört. Seitdem
  beantwortete diese Hilfsfunktion die Anfrage – und verlangte eine Angabe,
  die die App gar nicht schickt. Ein Test prüft jetzt, dass **keine** Route
  auf eine Hilfsfunktion zeigt
- 🇩🇪 **Halb deutsch, halb englisch.** Die Eingabeprüfung im Server schreibt
  englisch („Field required"), und das stand ungefiltert mitten im deutschen
  Satz. Jetzt wird daraus ein ganzer Satz in der eingestellten Sprache:
  „Eingabe nicht gültig: Da fehlt eine Angabe" bzw. „Invalid input:
  Something is missing here"

## 1.74.0 – Juli 2026

### Verbessert
- 🧱 **Die Sammlung kommt blockweise.** Bisher entstanden beim Öffnen alle
  Karten auf einen Schlag – bei 815 Einträgen **14.697 Elemente und 837
  Bilder** in einem Rutsch. Jetzt sind es die ersten 60; der Rest kommt beim
  Scrollen nach. Gemessen mit denselben 815 Einträgen: **1.952 Elemente,
  64 Bilder, 28 Bilder vom Server** beim Öffnen
- 👁 **Was weit außerhalb des Fensters liegt, wird nicht mehr gezeichnet.**
  Selbst wenn man sich durch die ganze Sammlung scrollt und am Ende alle
  815 Karten im Dokument stehen, hat der Browser nur **82 Bilder** geholt
  und 60 entpackt – der Rest wird übersprungen und darf wieder weg
- 🗂 **Zugeklappte Themen kosten nichts mehr.** Nach Thema gruppiert wurden
  bisher auch die zugeklappten Gruppen mit allen Karten aufgebaut. Jetzt
  füllt sich eine Gruppe erst, wenn man sie sieht: **163 statt 815 Karten**
  beim Öffnen

> **Warum das der Punkt war.** Der JS-Speicher blieb bei allen Abstürzen
> flach – entpackte Bilder liegen außerhalb und tauchen dort nicht auf.
> 837 Bilder auf einmal sind entpackt ein halbes Gigabyte, und das war die
> letzte Stelle, an der die App das noch tat.

## 1.73.1 – Juli 2026

### Behoben
- 🪧 **Der Abschiedszettel lag am falschen Ort und wurde falsch gelesen.**
  Zwei Fehler, beide beim ersten Einsatz aufgefallen: Er lag im
  `sessionStorage`, und der verschwindet ausgerechnet dann, wenn die App
  geschlossen wird – also im häufigsten *sauberen* Fall. Und verglichen
  wurde mit der Uhr (10 Sekunden), nicht mit dem letzten Messwert. Wer die
  App zumachte und später wieder aufmachte, wäre als Absturz gezählt worden.
  Jetzt liegt der Zettel im `localStorage` und gilt, wenn er **nach** dem
  letzten Messwert geschrieben wurde – egal wie lange das her ist
- ⏱ **Die 90-Sekunden-Frist ist weg.** Sie war der Notbehelf, solange es den
  Zettel nicht gab. Ein Absturz um 21:08, bemerkt beim Wiederöffnen um 21:16,
  fiel damit durchs Raster – der Eintrag trug „OHNE ABSCHIED", die
  Zusammenfassung meldete trotzdem nichts
- 🔐 **Antwort ohne JSON wird nicht mehr verschluckt.** Sitzt zwischen App und
  Instanz ein Zugangsschutz (Cloudflare Access) oder ein Zwischenserver, kommt
  dessen Anmeldeseite zurück – als HTML, mit Status 200. Daraus wurde
  stillschweigend ein leeres Objekt, die Oberfläche baute darauf weiter und
  fiel erst viel später über ein fehlendes Element. Jetzt sagt sie sofort,
  was los ist

## 1.73.0 – Juli 2026

### Verbessert
- 🪧 **Der Abschiedszettel.** Bisher blieb ein Rest Rätselraten: Ein Neuladen
  von Hand sah im Verlauf genauso aus wie ein Absturz. Jetzt hinterlässt die
  Seite beim Verlassen eine Notiz – das passiert bei jedem gewollten Ende
  (neu laden, weiterklicken, schließen) und ausgerechnet **nicht**, wenn der
  Browser sie abwürgt. Fehlt die Notiz, war es wirklich ein Absturz.
  Der Verlauf sagt das jetzt im Klartext: „ohne sich zu verabschieden – das
  ist ein echter Absturz" gegen „von Hand neu geladen – kein Absturz"
- 🗂 **Ein zweiter Tab zählt nicht mehr als Absturz.** Wer die App noch einmal
  öffnet, während die erste Sitzung läuft, hat weder Notiz noch Vorgeschichte
  – das sah aus wie ein Abbruch und war keiner

## 1.72.0 – Juli 2026

Aus einem Belastungstest: 132 Endpunkte, bis zu 5.041 Einträge, alle Tabs.
Angemeldet, Rechte, Einschleusung, XSS, Pfad-Ausbruch – alles dicht. Was
nicht gehalten hat, steht hier.

### Behoben
- 🇬🇧 **Der Export war deutsch, auch auf Englisch.** Druckausgabe und CSV
  hatten ihre Überschriften fest im Code: „Nummer, Name, Jahr, Anz., Zustand".
  Jetzt laufen Titel, Spalten, Dateinamen und Zahlenformat über die
  Übersetzung – und die Geldspalten tragen die **eingestellte Währung** statt
  eines festen „(EUR)"
- 💥 **CSV-Import stürzte ab statt zu meckern.** Ein einzelnes
  Anführungszeichen ohne Gegenstück macht aus dem Rest der Datei ein Feld; ab
  128 KB gab Python auf und der Server antwortete mit einem nackten
  „Internal Server Error". Jetzt kommt der Satz, der weiterhilft
- 🔀 **Zwei Leute, derselbe Artikel, im selben Moment.** Beide Anfragen sahen
  „gibt es noch nicht", eine legte an, die andere lief in die eindeutige
  Bedingung – Serverfehler, und ihr Stück war weg. Jetzt wird daraus
  nachträglich das Zusammenführen
- 🧾 **„… in 3 von 12 Setsvon 12 Sets"** – in der Druckausgabe der fehlenden
  Set-Figuren stand die Zahl doppelt
- 🔎 **Suche ohne Treffer zeigte eine leere Fläche.** Kein Hinweis, kein
  Ladezeichen – man wusste nicht, ob nichts passt oder noch geladen wird.
  Jetzt steht „Nichts gefunden" da, mit einem Knopf, der die Filter räumt
- 🔌 **„Failed to fetch".** Ist die Instanz nicht erreichbar (NAS schläft,
  VPN weg, Update läuft), stand diese englische Browser-Meldung als ganzer
  Inhalt in der Statistik. Jetzt: „Keine Verbindung zur Instanz. Läuft der
  Server, und ist das Gerät im richtigen Netz?"

### Verbessert
- 🧹 **Die Sammlung gibt den Platz frei, wenn man sie verlässt.** Bisher
  blieben alle Karten im Dokument stehen, auch in der Statistik – gemessen
  bei 400 Einträgen: **5.731 → 988 Elemente**, bei 815 sind es rund 13.800
  weniger. Die Daten bleiben im Speicher, beim Zurückkommen ist die Liste
  sofort wieder da
- 🔒 **`item_type` wird geprüft** – bisher landete „raumschiff" klaglos in
  der Datenbank und tauchte danach in Adressen und Auswertungen wieder auf.
  Und **Bildadressen** nehmen nur noch die eigene Instanz oder http(s);
  `javascript:` und `data:` sind raus (ausgeführt wurde davon nie etwas, die
  CSP hat es abgefangen – in der Datenbank hatte es trotzdem nichts verloren)

## 1.71.0 – Juli 2026

### Neu
- ↓ **Nach unten ziehen lädt neu.** Vom Startbildschirm gestartet fehlt die
  Adressleiste – und damit der Knopf zum Neuladen; auf iOS gibt es dort auch
  keine Geste dafür. Jetzt kommt ein Stein von oben mit dem Finger herunter,
  färbt sich grün, sobald es reicht, und beim Loslassen lädt die Seite neu.
  Nur in der App: Im Browser bringt die Adressleiste das schon mit, zwei
  Anzeigen übereinander wären keine Verbesserung

> Der Zug greift nur ganz oben und nur, wenn kein Popup offen ist – und er
> fängt weder das Scrollen noch das Wischen zur Seite ab. Das Neuladen trägt
> sich als **„Nach unten gezogen"** in den Speicher-Verlauf ein, damit es
> dort nicht als Absturz erscheint.

## 1.70.1 – Juli 2026

### Verbessert
- 🔍 **Der Verlauf sagt jetzt, *warum* eine Sitzung neu begann.** Bisher galt
  jeder Start kurz nach dem letzten Messwert als Absturz – auch dann, wenn die
  App sich selbst neu geladen hatte. Genau das passiert nach jedem
  Server-Neustart, damit niemand mit veraltetem Code weiterarbeitet. Im
  Verlauf vom 30.7. steht der Beweis: Der „Absturz" um 09:19:44 war das Update
  auf 1.70.0, eine halbe Minute später lief die neue Version. Jetzt trägt
  jedes gewollte Neuladen seinen Grund, und die Zusammenfassung zählt getrennt:
  „ohne erkennbaren Grund", „vom Browser weggeräumt", „App selbst neu geladen"
- 🖥 **Die Startzeit des Servers steht in jedem Messwert.** Springt sie, ist der
  Container neu gestartet – das ist im Verlauf jetzt direkt zu sehen, statt es
  aus einem Neustart der Seite erraten zu müssen
- 🧹 **Der Browser verrät, wenn er den Tab weggeräumt hat** (`wasDiscarded`).
  Das tut er bei Speichermangel – es ist der einzige Hinweis auf Speicher, den
  er einer Seite gibt, und damit der erste belastbare statt eines vermuteten

## 1.70.0 – Juli 2026

### Behoben
- 💥 **Der abstürzende Tab.** Der Speicher-Verlauf aus 1.69.0 hat die Stelle
  gezeigt: 6 MB JS-Speicher, flach über elf Minuten, 14.680 Elemente,
  815 Bilder – und dann weg. Die Kurve blieb flach, also lag es woanders.
  Es lag am **weichen Hintergrundbild der Sammlungskarten**: Jede Karte trug
  ein zweites Bild, und für CSS-Hintergründe gibt es kein `loading="lazy"`.
  Mit 815 Einträgen nachgestellt – identisch bis auf 100 Elemente genau –
  holte das Öffnen der Sammlung **815 Bilder auf einmal**, ohne eine Zeile zu
  scrollen. Entpackt ist das ein halbes Gigabyte, und das steht nirgends im
  JS-Speicher. Jetzt bekommt eine Karte ihr Hintergrundbild erst, wenn sie in
  die Nähe des Fensters kommt, und gibt es wieder her, wenn sie weit weg ist:
  gemessen **54 statt 815** Bilder beim Öffnen, und beim Weiterscrollen
  wandert ein Fenster von rund 40 Karten mit

### Verbessert
- 🔒 **Auch die Hintergrundbilder laufen jetzt über die eigene Instanz.**
  Sie hingen als einzige noch am Original bei BrickLink – damit verriet jede
  angezeigte Karte, was hier steht, und geladen wurde die unverkleinerte
  Fassung. Jetzt gilt für sie derselbe Weg wie für die Kartenbilder

## 1.69.0 – Juli 2026

### Neu
- 🩺 **Speicher-Verlauf im Fehlerbericht.** Ein abgestürzter Tab hinterlässt
  normalerweise nichts – keine Konsole, kein Protokoll. Deshalb misst die App
  jetzt alle 30 Sekunden JS-Speicher, Zahl der Elemente und Zahl der Bilder
  und legt das **im Browser** ab, wo es einen Abbruch übersteht. Nach dem
  nächsten Start steht da, was in den zwei Stunden davor passiert ist, samt
  Kurve
- ⚠️ **Abstürze werden erkannt und gezählt.** Folgt der Beginn einer Sitzung
  unmittelbar auf einen Messwert, ohne dass jemand neu geladen hat, war es
  ein Abbruch. Senkrechte Linien in der Kurve zeigen, wo
- 📋 Der Verlauf lässt sich als Text kopieren; er bleibt auf dem Gerät

> **Was die Zahl aussagt – und was nicht.** Gemessen wird der
> JavaScript-Speicher. Entpackte Bilder und der Seitenaufbau stecken da nicht
> drin. Wächst die Kurve, liegt es an der App. Bleibt sie flach, während der
> Tab trotzdem stirbt, liegt es sehr wahrscheinlich woanders. Auch das ist
> ein Ergebnis.

## 1.68.5 – Juli 2026

### Verbessert
- 🖼 **Bilder werden vor Anzeige und Versand verkleinert.** Ein
  Bildschirmfoto in 4K belegt entpackt **32 MB** im Browser – obwohl die
  Vorschau es auf 300 Pixel Höhe zeigt und der Server es ohnehin auf 1200
  Pixel bringt, bevor er es zur Erkennung weiterreicht. Jetzt passiert das
  gleich im Browser: aus 32 MB werden 3 MB, und statt 10 MB gehen 250 KB
  durch die Leitung. Für die Erkennung ändert sich nichts – der Server hat
  auch vorher nur die verkleinerte Fassung gesehen
- 🧹 **Der Zwischenspeicher der Übersetzung mistet aus.** Er hält Verweise auf
  Elemente, um beim Sprachwechsel zurücksetzen zu können. Neu gezeichnete
  Listen ließen die alten darin zurück – bei tausend Karten summiert sich
  das. Betraf nur die englische Fassung

## 1.68.4 – Juli 2026

### Behoben
- 🧠 **Jedes hineingezogene Bild blieb für immer im Speicher.** Die
  Scan-Vorschau erzeugt für das gewählte Foto eine Objekt-Adresse – und die
  hält die Datei bis zum Neuladen der Seite fest, auch wenn längst ein
  anderes Bild angezeigt wird. Drei andere Stellen in der App geben ihre
  Adressen ordentlich frei, ausgerechnet diese nicht. Wer nacheinander
  Bildschirmfotos in die Erkennung zieht, sammelte sie also alle an: ein
  2560×1440-Foto belegt entpackt rund **14 MB**. Nach ein paar Dutzend
  beendet der Browser den Tab – bei Edge mit „Auf dieser Seite gibt es ein
  Problem". Jetzt wird die vorherige Vorschau freigegeben, sobald die
  nächste kommt
- 🧪 Ein Test zählt `createObjectURL` gegen `revokeObjectURL` in `app.js` –
  wer künftig eine Adresse erzeugt, ohne sie freizugeben, fällt auf

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
