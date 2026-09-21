"""Deutsch → Englisch für die Suche, ohne KI.

**Warum es das gibt.** Die Katalognamen sind englisch. Wer „roter Ritter"
tippt, findet ohne Übersetzung nichts – bisher half dabei nur ein lokales
Sprachmodell, und das hat längst nicht jeder. Diese Liste tut dieselbe
Arbeit für den weitaus größten Teil der Fälle, sofort und überall.

**Warum eine Liste reicht.** Gemessen am 21.09.2026 an 19.267 Figurennamen:
169.591 Wortvorkommen, 7.016 verschiedene Wörter – aber die häufigsten 300
decken 77 % aller Vorkommen, die häufigsten 500 decken 83 %. Und ganz oben
stehen `legs, dark, blue, black, hair, helmet, gray, jacket, torso, cap`:
Farben, Kleidung, Körperteile. **Alltagswörter.** Der Rest sind Eigennamen –
Windu, Chewbacca, Weasley –, und die tippt man ohnehin, wie sie geschrieben
werden. Übersetzt werden muss also ein kleiner, allgemeiner Teil.

**Was hier drinsteht und was nicht.** Nur einzelne Wörter des allgemeinen
Sprachgebrauchs. **Keine Katalogtexte, keine Titel, keine Beschreibungen** –
die Grenze aus `katalogdienst/veroeffentlichen.py` gilt hier genauso. Die
Liste ist aus der Worthäufigkeit entstanden, nicht aus Einträgen; sie darf
deshalb mitreisen. Sven hat das am 21.09.2026 ausdrücklich so entschieden.

**Wie sie benutzt wird.** Nicht als Übersetzung ganzer Namen, sondern zur
Erweiterung der *Anfrage*: Aus „roter protokolldroide" wird „red protocol
droid", und danach sucht dieselbe Suche wie immer. Unbekannte Wörter bleiben
stehen – sie sind meist Eigennamen und stehen so schon im Katalog.
"""

import re

import core

# Deutsch → englische Begriffe. Mehrere Ziele sind erlaubt und erwünscht:
# „grau" heißt bei BrickLink mal `gray`, mal `bluish gray`.
WOERTERBUCH: dict[str, tuple[str, ...]] = {
    # ── Farben ────────────────────────────────────────────────────────
    # Der häufigste Griff überhaupt. `dark`, `light`, `medium` und
    # `bluish` stehen in fast jedem zweiten Namen.
    "schwarz": ("black",),
    "weiss": ("white",), "weiß": ("white",),
    "rot": ("red",), "rote": ("red",), "roter": ("red",), "rotes": ("red",),
    "blau": ("blue",), "blaue": ("blue",), "blauer": ("blue",),
    "gruen": ("green",), "grün": ("green",), "grüne": ("green",),
    "gelb": ("yellow",), "gelbe": ("yellow",),
    "braun": ("brown",), "braune": ("brown",),
    "grau": ("gray", "bluish gray"), "graue": ("gray",),
    "orange": ("orange",),
    "rosa": ("pink",), "pink": ("pink",),
    "lila": ("purple", "lavender"), "violett": ("purple",),
    "tuerkis": ("turquoise",), "türkis": ("turquoise",),
    "beige": ("tan",), "sandfarben": ("sand", "tan"),
    "gold": ("gold", "golden"), "golden": ("golden", "gold"),
    "silber": ("silver",), "silbern": ("silver",),
    "bronze": ("bronze",), "kupfer": ("copper",),
    "dunkel": ("dark",), "dunkle": ("dark",), "dunkler": ("dark",),
    "hell": ("light", "bright"), "helle": ("light",), "heller": ("light",),
    "mittel": ("medium",),
    "durchsichtig": ("trans", "clear"), "transparent": ("trans", "clear"),
    "klar": ("clear",),
    "blaeulich": ("bluish",), "bläulich": ("bluish",),
    "roetlich": ("reddish",), "rötlich": ("reddish",),
    "gelblich": ("yellowish",),
    "oliv": ("olive",), "olivgruen": ("olive",), "olivgrün": ("olive",),
    "azur": ("azure",), "azurblau": ("azure",),
    "koralle": ("coral",), "korallenrot": ("coral",),
    "magenta": ("magenta",), "neon": ("neon",),
    "perle": ("pearl",), "perlmutt": ("pearl",),
    "metallisch": ("metallic",), "limette": ("lime",), "limone": ("lime",),
    "lavendel": ("lavender",), "aqua": ("aqua",),
    "hautfarben": ("nougat",), "fleischfarben": ("nougat",),
    "bunt": ("bright",), "leuchtend": ("bright",),

    # ── Kleidung ──────────────────────────────────────────────────────
    "hemd": ("shirt",), "tshirt": ("shirt",), "oberteil": ("top", "shirt"),
    "jacke": ("jacket",), "mantel": ("coat",), "jacket": ("jacket",),
    "hose": ("pants", "trousers"), "hosen": ("pants", "trousers"),
    "shorts": ("shorts",), "kurzehose": ("shorts",),
    "rock": ("skirt",), "kleid": ("dress",),
    "weste": ("vest",), "pullover": ("sweater",), "pulli": ("sweater",),
    "kapuzenpullover": ("hoodie",), "hoodie": ("hoodie",),
    "umhang": ("cape",), "cape": ("cape",),
    "robe": ("robe",), "gewand": ("robe",), "kutte": ("robe",),
    "anzug": ("suit",), "uniform": ("uniform",),
    "overall": ("overalls", "jumpsuit"), "latzhose": ("overalls",),
    "schuhe": ("shoes",), "stiefel": ("boots",), "sandalen": ("sandals",),
    "muetze": ("cap", "beanie"), "mütze": ("cap", "beanie"),
    "kappe": ("cap",), "hut": ("hat",), "zylinder": ("hat",),
    "helm": ("helmet",), "guertel": ("belt",), "gürtel": ("belt",),
    "krawatte": ("tie",), "schal": ("scarf",), "tuch": ("bandana",),
    "handschuhe": ("gloves",), "tasche": ("pocket",),
    "taschen": ("pockets",), "rucksack": ("backpack",),
    "brille": ("glasses",), "sonnenbrille": ("sunglasses",),
    "schutzbrille": ("goggles",), "maske": ("mask",), "visier": ("visor",),
    "kragen": ("collar",), "schuerze": ("apron",), "schürze": ("apron",),
    "badeanzug": ("swimsuit",), "taucheranzug": ("wetsuit",),
    "raumanzug": ("spacesuit",), "ruestung": ("armor",), "rüstung": ("armor",),
    "brustpanzer": ("breastplate",), "kopfhoerer": ("headphones",),
    "kopfhörer": ("headphones",), "stirnband": ("bandana",),
    "reissverschluss": ("zipper",), "reißverschluss": ("zipper",),
    "knopf": ("button",), "knoepfe": ("buttons",), "knöpfe": ("buttons",),
    "streifen": ("stripes", "striped"), "gestreift": ("striped",),
    "kariert": ("plaid",), "muster": ("pattern",),
    "gemustert": ("pattern",), "bedruckt": ("printed",),
    "aermellos": ("sleeveless",), "ärmellos": ("sleeveless",),
    "aermel": ("sleeves",), "ärmel": ("sleeves",),
    "kapuze": ("hood",), "guertelschnalle": ("buckle",),
    "schnalle": ("buckle",), "abzeichen": ("badge",), "wappen": ("logo",),
    "hosentraeger": ("suspenders",), "hosenträger": ("suspenders",),
    "guertelzeug": ("utility belt",), "krone": ("crown",),
    "kette": ("necklace",), "halskette": ("necklace",),
    "flossen": ("flippers",), "schwimmflossen": ("flippers",),
}

# ── Körper, Gesicht, Haare ────────────────────────────────────────────
WOERTERBUCH.update({
    "haare": ("hair",), "haar": ("hair",), "frisur": ("hair",),
    "bart": ("beard",), "vollbart": ("beard",),
    "schnurrbart": ("moustache",), "stoppeln": ("stubble",),
    "augen": ("eyes",), "auge": ("eye",),
    "augenbrauen": ("eyebrows",), "mund": ("mouth",),
    "zaehne": ("teeth",), "zähne": ("teeth",),
    "lippen": ("lips",), "nase": ("nose",),
    "kopf": ("head",), "gesicht": ("face",),
    "arme": ("arms",), "arm": ("arm",),
    "haende": ("hands",), "hände": ("hands",), "hand": ("hand",),
    "beine": ("legs",), "bein": ("leg",),
    "huefte": ("hips",), "hüfte": ("hips",),
    "brust": ("chest",), "schulter": ("shoulder",),
    "hals": ("neck",), "kinn": ("chin",), "wange": ("cheek",),
    "sommersprossen": ("freckles",), "laecheln": ("smile",),
    "lächeln": ("smile",), "grinsen": ("grin",),
    "pferdeschwanz": ("ponytail",), "zopf": ("braided", "ponytail"),
    "zoepfe": ("pigtails",), "zöpfe": ("pigtails",),
    "dutt": ("bun",), "locken": ("wavy",), "gelockt": ("wavy",),
    "glatze": ("bald",), "haut": ("skin",), "fell": ("fur",),
    "feder": ("feather",), "schwanz": ("tail",), "fluegel": ("wings",),
    "flügel": ("wings",), "knochen": ("skeleton",),
})

# ── Rollen und Berufe ─────────────────────────────────────────────────
# Der Teil, der beim Suchen am meisten bringt: „Ritter" trifft 285
# Namen auf einen Schlag.
WOERTERBUCH.update({
    "ritter": ("knight",), "pirat": ("pirate",), "piraten": ("pirate",),
    "polizist": ("police",), "polizei": ("police",),
    "feuerwehrmann": ("fireman", "fire"), "feuerwehr": ("fire",),
    "arzt": ("doctor",), "aerztin": ("doctor",), "ärztin": ("doctor",),
    "doktor": ("doctor",), "sanitaeter": ("medic", "emt"),
    "sanitäter": ("medic", "emt"), "krankenschwester": ("nurse",),
    "bauer": ("farmer",), "koch": ("chef",), "koechin": ("chef",),
    "taucher": ("diver", "scuba"), "pilot": ("pilot",),
    "fahrer": ("driver",), "astronaut": ("astronaut",),
    "soldat": ("soldier",), "waechter": ("guard",), "wächter": ("guard",),
    "wache": ("guard",), "offizier": ("officer",),
    "kapitaen": ("captain",), "kapitän": ("captain",),
    "general": ("general",), "kommandant": ("commander",),
    "koenig": ("king",), "könig": ("king",),
    "koenigin": ("queen",), "königin": ("queen",),
    "prinz": ("prince",), "prinzessin": ("princess",),
    "zauberer": ("wizard",), "hexe": ("witch",),
    "elf": ("elf",), "zwerg": ("dwarf",), "kobold": ("goblin",),
    "skelett": ("skeleton",), "zombie": ("zombie",),
    "geist": ("ghost",), "gespenst": ("ghost",),
    "roboter": ("robot",), "droide": ("droid",), "droiden": ("droid",),
    "ninja": ("ninja",), "krieger": ("warrior",),
    "jaeger": ("hunter",), "jäger": ("hunter",),
    "kopfgeldjaeger": ("bounty hunter",), "kopfgeldjäger": ("bounty hunter",),
    "dieb": ("crook", "bandit"), "raeuber": ("bandit",),
    "räuber": ("bandit",), "verbrecher": ("crook",),
    "gefangener": ("prisoner",), "haeftling": ("prisoner",),
    "häftling": ("prisoner",),
    "ingenieur": ("engineer",), "mechaniker": ("mechanic",),
    "arbeiter": ("worker",), "bauarbeiter": ("construction",),
    "bergmann": ("miner",), "verkaeufer": ("vendor",),
    "verkäufer": ("vendor",), "kunde": ("customer",),
    "sheriff": ("sheriff",), "cowboy": ("cowboy",),
    "wikinger": ("viking",), "held": ("hero",), "agent": ("agent",),
    "forscher": ("explorer", "scientist"),
    "wissenschaftler": ("scientist",), "professor": ("professor",),
    "lehrer": ("teacher",), "schueler": ("student",), "schüler": ("student",),
    "kind": ("child", "kid"), "junge": ("boy",), "maedchen": ("girl",),
    "mädchen": ("girl",), "mann": ("male", "man"),
    "frau": ("female", "woman"), "baby": ("baby",),
    "spieler": ("player",), "torwart": ("goalie",),
    "rennfahrer": ("racer",), "mechanikerin": ("mechanic",),
    "musiker": ("musician",), "sekretaerin": ("secretary",),
})

# ── Dinge, Tiere, Orte, Themen ────────────────────────────────────────
WOERTERBUCH.update({
    "stern": ("star",), "sterne": ("stars",),
    "weltraum": ("space",), "raumschiff": ("spaceship",),
    "burg": ("castle",), "schloss": ("castle",), "turm": ("tower",),
    "drache": ("dragon",), "drachen": ("dragon",),
    "spinne": ("spider",), "loewe": ("lion",), "löwe": ("lion",),
    "pferd": ("horse",), "hund": ("dog",), "katze": ("cat",),
    "affe": ("monkey",), "maus": ("mouse",), "schwein": ("pig",),
    "meerjungfrau": ("mermaid",), "einhorn": ("unicorn",),
    "auto": ("car",), "lastwagen": ("truck",), "lkw": ("truck",),
    "zug": ("train",), "boot": ("boat",), "schiff": ("ship",),
    "flugzeug": ("jet", "plane"), "hubschrauber": ("helicopter",),
    "rakete": ("rocket",), "fahrrad": ("bicycle",),
    "schild": ("shield",), "schwert": ("sword",), "axt": ("axe",),
    "bogen": ("bow",), "koecher": ("quiver",), "köcher": ("quiver",),
    "herz": ("heart",), "blume": ("flower",), "blumen": ("flowers",),
    "feuer": ("fire",), "eis": ("ice",), "stein": ("stone", "brick"),
    "wald": ("forest",), "berg": ("mountain",), "meer": ("sea",),
    "dschungel": ("jungle",), "wueste": ("desert",), "wüste": ("desert",),
    "gefaengnis": ("prison", "jail"), "gefängnis": ("prison", "jail"),
    "flughafen": ("airport",), "stadt": ("city", "town"),
    "bauernhof": ("farm",), "krankenhaus": ("hospital",),
    "sport": ("sports",), "fussball": ("soccer",), "fußball": ("soccer",),
    "rennen": ("race", "racing"), "mannschaft": ("team",),
    "trophaee": ("trophy",), "trophäe": ("trophy",), "pokal": ("trophy",),
    "fahne": ("flag",), "flagge": ("flag",), "leiter": ("ladder",),
    "werkzeug": ("tools",), "funkgeraet": ("radio",),
    "funkgerät": ("radio",), "fernglas": ("binoculars",),
    "sauerstoff": ("breathing",), "tank": ("tank",), "tanks": ("tanks",),
    "figur": ("figure", "minifigure"), "minifigur": ("minifigure",),
    "puppe": ("doll",), "statue": ("statue",), "sockel": ("stand", "base"),
    "aufkleber": ("sticker",), "abziehbild": ("sticker",),
})

# ── Eigenschaften und kleine Wörter ───────────────────────────────────
# `mit` und `ohne` stehen in 6.215 bzw. 940 Namen – sie tragen also
# echte Bedeutung („mit Umhang", „ohne Beine").
WOERTERBUCH.update({
    "mit": ("with",), "ohne": ("without",), "und": ("and",),
    "lang": ("long",), "lange": ("long",), "kurz": ("short",),
    "kurze": ("short",), "gross": ("large",), "groß": ("large",),
    "grosse": ("large",), "große": ("large",),
    "klein": ("small", "mini"), "kleine": ("small",),
    "breit": ("broad", "wide"), "schmal": ("thin",), "duenn": ("thin",),
    "dünn": ("thin",), "dick": ("heavy",),
    "rund": ("round",), "oval": ("oval",), "flach": ("flat",),
    "offen": ("open",), "geschlossen": ("closed",),
    "alt": ("old",), "jung": ("young",), "neu": ("new",),
    "glatt": ("smooth",), "spitz": ("spiked",),
    "gerade": ("straight",), "schraeg": ("sideways",),
    "schräg": ("sideways",), "seitlich": ("side",),
    "vorne": ("front",), "hinten": ("back",),
    "links": ("left",), "rechts": ("right",),
    "oben": ("top", "up"), "unten": ("bottom",),
    "erster": ("first",), "erste": ("first",),
    "boese": ("evil",), "böse": ("evil",), "wuetend": ("angry",),
    "wütend": ("angry",), "froehlich": ("smile",), "fröhlich": ("smile",),
    "erschrocken": ("scared",), "ernst": ("frown",),
    "klassisch": ("classic",), "gewoehnlich": ("plain",),
    "gewöhnlich": ("plain",), "schlicht": ("plain",),
    "koeniglich": ("royal",), "königlich": ("royal",),
    "kaiserlich": ("imperial",), "aufblasbar": ("inflatable",),
    "reflektierend": ("reflective",), "gepanzert": ("armor",),
    "gepunktet": ("dots",), "gestickt": ("print",),
})

# ── Bausteine zusammengesetzter Wörter ────────────────────────────────
# Diese stehen selten allein, aber ständig als erste Hälfte: Ohne
# „Protokoll" findet die Zerlegung „Protokolldroide" nicht. Gesammelt im
# Trainingslauf vom 21.09.2026, wo genau diese Wörter durchfielen.
WOERTERBUCH.update({
    "blond": ("blond",), "blonde": ("blond",), "blondes": ("blond",),
    "augenklappe": ("eye patch",), "klappe": ("patch",),
    "protokoll": ("protocol",), "klon": ("clone",), "klone": ("clone",),
    "sturm": ("storm",), "truppler": ("trooper",), "truppe": ("trooper",),
    "trupp": ("trooper",),
    "weihnacht": ("santa", "holiday"), "weihnachten": ("santa", "holiday"),
    "ball": ("ball",), "fuss": ("soccer",), "fuß": ("soccer",),
    "arbeit": ("work",), "raum": ("space",), "welt": ("world",),
    "kampf": ("battle",), "krieg": ("war",), "wasser": ("water",),
    "luft": ("air",), "berg": ("mountain",), "eisen": ("iron",),
    "leder": ("leather",), "stoff": ("fabric",), "metall": ("metal",),
    "renn": ("racing",), "renner": ("racer",), "spiel": ("play",),
    "haus": ("house",), "schnee": ("snow",), "sonne": ("sun",),
    "mond": ("lunar", "moon"), "nacht": ("night",), "tag": ("day",),
    "kopf": ("head",), "kopfgeld": ("bounty",), "geld": ("money",),
    "hoch": ("high",), "tief": ("deep",), "ober": ("top",),
    "unter": ("under",), "vor": ("front",), "haupt": ("main",),
    "gross": ("large",), "mini": ("mini",), "micro": ("micro",),
    "rad": ("wheel",), "motor": ("motor",), "maschine": ("machine",),
    "fahr": ("driving",), "flug": ("flight", "air"), "see": ("sea",),
})

# ── Nachgetragen aus der Deckungsmessung ──────────────────────────────
# Am 21.09.2026 gegen die 800 häufigsten Katalogwörter gemessen: Diese
# kamen dort oft vor, waren aber von keinem deutschen Wort aus
# erreichbar. Eigennamen (Batman, Weasley, Ninjago) fehlen bewusst – die
# tippt man ohnehin, wie sie geschrieben werden.
WOERTERBUCH.update({
    "torso": ("torso",), "oberkoerper": ("torso",), "oberkörper": ("torso",),
    "rumpf": ("torso",),
    "zubehoer": ("accessories",), "zubehör": ("accessories",),
    "nur": ("only",), "ueber": ("over",), "über": ("over",),
    "sicherheit": ("safety",), "warnweste": ("safety vest",),
    "rettungsweste": ("life jacket",), "leben": ("life",),
    "kleidung": ("outfit",), "aufzug": ("outfit",),
    "zerzaust": ("tousled",), "strubbelig": ("tousled",),
    "nummer": ("number",), "zahl": ("number",),
    "linien": ("lines",), "linie": ("line",),
    "strick": ("knit",), "gestrickt": ("knit",),
    "film": ("movie",), "schutz": ("protector",),
    "schirm": ("bill", "brim"), "aera": ("era",), "ära": ("era",),
    "epoche": ("era",), "fantasie": ("fantasy",),
    "halterung": ("bracket",), "typ": ("type",), "art": ("type",),
    "gestuft": ("layered",), "geschichtet": ("layered",),
    "schmunzeln": ("smirk",), "schief": ("lopsided",),
    "erwachsener": ("adult",), "erwachsene": ("adult",),
    "phase": ("phase",), "super": ("super",), "loch": ("hole",),
    "kueste": ("coast",), "küste": ("coast",),
    "kettenhemd": ("chain mail",), "post": ("mail",),
    "rebell": ("rebel",), "rebellen": ("rebel",),
    "flieger": ("aviator",), "park": ("park",),
    "packung": ("pack",), "riemen": ("strap",), "gurt": ("strap",),
    "schuppen": ("scale",), "massstab": ("scale",),
    "koerper": ("body",), "körper": ("body",),
    "totenkopf": ("skull",), "schaedel": ("skull",), "schädel": ("skull",),
    "federbusch": ("plume",), "tunika": ("tunic",),
    "finster": ("scowl",), "kostuem": ("costume",), "kostüm": ("costume",),
    "ausserirdischer": ("alien",), "außerirdischer": ("alien",),
    "besatzung": ("crew",), "lord": ("lord",), "herr": ("lord",),
    "ziegenbart": ("goatee",), "kinnbart": ("goatee",),
    "waagerecht": ("horizontal",), "senkrecht": ("vertical",),
    "arktis": ("arctic",), "polar": ("arctic",),
    "gepolstert": ("pads",), "schulterklappen": ("epaulettes",),
    "schleife": ("bow",), "guertelschlaufe": ("belt loop",),
    "taucherbrille": ("goggles",), "atemgeraet": ("breathing",),
    "stethoskop": ("stethoscope",), "werkzeuggurt": ("utility belt",),
    "schwimmweste": ("life jacket",), "kapitaensmuetze": ("captain cap",),
    "sandalen": ("sandals",), "turnschuhe": ("sneakers",),
    "jeans": ("jeans",), "karohemd": ("plaid shirt",),
    "trikot": ("jersey",), "helmvisier": ("helmet visor",),
})

# ── Zweite Runde der Deckungsmessung ──────────────────────────────────
WOERTERBUCH.update({
    "kurzgeschnitten": ("cropped",), "zurueckgekaemmt": ("swept",),
    "zurückgekämmt": ("swept",), "gescheitelt": ("swept",),
    "wickel": ("wrap",), "charakter": ("character",),
    "doppelt": ("dual",), "laenge": ("length",), "länge": ("length",),
    "besatz": ("trim",), "schmutz": ("dirt",), "dreckig": ("dirt",),
    "passagier": ("passenger",), "beifahrer": ("passenger",),
    "kerl": ("guy",), "geschirr": ("harness",), "gurtzeug": ("harness",),
    "turnier": ("tournament",), "glocke": ("bell",),
    "kraft": ("power",), "meister": ("master",),
    "flanell": ("flannel",), "fleck": ("stains", "mark"),
    "flecken": ("stains",), "reitend": ("riding",), "reiter": ("rider",),
    "platte": ("plate",), "haeuptling": ("chief",), "häuptling": ("chief",),
    "chef": ("chief",), "mitte": ("center",), "monster": ("monster",),
    "filzhut": ("fedora",), "scheide": ("scabbard",), "bluse": ("blouse",),
    "falke": ("falcon",), "schatten": ("shadow",), "klammer": ("clip",),
    "ausruestung": ("gear",), "ausrüstung": ("gear",),
    "pony": ("bangs",), "kaempfer": ("fighter",), "kämpfer": ("fighter",),
    "fransen": ("fringe",), "gitter": ("grille",), "anker": ("anchor",),
    "schaerpe": ("sash",), "schärpe": ("sash",), "grube": ("pit",),
    "angestellter": ("employee",), "oel": ("oil",), "öl": ("oil",),
    "streifenmuster": ("stripe",), "welle": ("wave",),
    "schlange": ("snake",), "spinnennetz": ("web",),
    "blitz": ("lightning",), "wolke": ("cloud",), "regen": ("rain",),
    "stiefeletten": ("boots",), "guertelt": ("belted",),
    "kurzarm": ("short sleeves",), "langarm": ("long sleeves",),
    "rollkragen": ("turtleneck",), "kragenlos": ("collarless",),
})

# ── Aus dem Trainingslauf vom 21.09.2026, zweiter Satz ────────────────
# Alles Wörter, die in echten Anfragen vorkamen und ins Leere liefen.
WOERTERBUCH.update({
    # Figurenarten
    "samurai": ("samurai",), "indianer": ("native american", "indian"),
    "aegypter": ("egyptian",), "ägypter": ("egyptian",),
    "mumie": ("mummy",), "vampir": ("vampire",), "clown": ("clown",),
    "skifahrer": ("skier", "ski"), "surfer": ("surfer",),
    "pinguin": ("penguin",), "papagei": ("parrot",),
    "yeti": ("yeti",), "werwolf": ("werewolf",), "gespenster": ("ghost",),
    "engel": ("angel",), "teufel": ("devil",), "narr": ("jester",),
    "baecker": ("baker",), "bäcker": ("baker",), "metzger": ("butcher",),
    "gaertner": ("gardener",), "gärtner": ("gardener",),
    "briefträger": ("mailman",), "brieftraeger": ("mailman",),
    "fotograf": ("photographer",), "reporter": ("reporter",),
    "richter": ("judge",), "buergermeister": ("mayor",),
    "bürgermeister": ("mayor",), "moench": ("monk",), "mönch": ("monk",),
    "nonne": ("nun",), "priester": ("priest",),
    # Ausrüstung und Kleinteile
    "markierung": ("markings",), "markierungen": ("markings",),
    "abzeichen": ("badge", "insignia"), "aufdruck": ("print", "printing"),
    "holzbein": ("peg leg",), "augenklappe": ("eye patch",),
    "sauerstoffflasche": ("air tanks", "tanks"),
    "flasche": ("bottle",), "strohhut": ("straw hat",),
    "haube": ("bonnet", "cap"), "besen": ("broom",),
    "antenne": ("antenna",), "gitarre": ("guitar",),
    "hoernerhelm": ("horned helmet",), "hörnerhelm": ("horned helmet",),
    "hoerner": ("horns",), "hörner": ("horns",),
    "kopftuch": ("bandana",), "sternenhut": ("wizard hat",),
    "zauberhut": ("wizard hat",), "spitzhut": ("pointed hat",),
    "brustpanzerung": ("breastplate",), "kettenrüstung": ("chain mail",),
    "lanze": ("lance",), "speer": ("spear",), "hammer": ("hammer",),
    "peitsche": ("whip",), "pfeil": ("arrow",), "fackel": ("torch",),
    "laterne": ("lantern",), "schluessel": ("key",), "schlüssel": ("key",),
    "tasse": ("cup",), "teller": ("plate",), "buch": ("book",),
    "zauberstab": ("wand",), "stab": ("staff",),
    "lichtschwert": ("lightsaber",), "blaster": ("blaster",),
    "funkgeraet": ("radio",), "kamera": ("camera",),
    "schlitten": ("sled",), "ski": ("ski",), "surfbrett": ("surfboard",),
    "skateboard": ("skateboard",), "rollschuhe": ("roller skates",),
    "schwimmreifen": ("swim ring",), "eimer": ("bucket",),
})

# ── Aus dem Wortschatz der Bildbeschreibungen ─────────────────────────
#
# **Woher das kommt.** Die Beschreibungen des Sehmodells sind englisch und
# werden nirgends angezeigt – sie sind reiner Suchindex. Sie auf Deutsch
# *zusätzlich* abzulegen hätte 19.267 Übersetzungen gebraucht: gemessen am
# 21.09.2026 mit `qwen3.5:9b` 3,4 s je Figur, also **18 Stunden** auf dem
# Mac mini, der nebenher den Sprachassistenten bedient.
#
# Die Beschreibungen bestehen aber nur aus **2.782 verschiedenen Wörtern**,
# 1.321 davon kommen mindestens fünfmal vor. Übersetzt wurde deshalb der
# **Wortschatz**, nicht der Text: 969 offene Wörter in 5 Minuten, davon 820
# brauchbar. Gespeichert wird dadurch nichts Neues, veröffentlicht auch
# nicht – die Paare wirken hier, auf der Anfrageseite.
#
# **Maschinell erzeugt, deshalb nachrangig.** Was weiter oben von Hand
# steht, wird nicht überschrieben. Ein schiefes Wort („furrowed" →
# „gegrunzt") ist totes Gewicht: Es tippt nur niemand. Wer eines findet,
# korrigiert es hier.
WOERTERBUCH.update({
    "abdeckungen": ("covers",),
    "aber": ("but",),
    "abgerundet": ("rounded",),
    "abschnitt": ("section",),
    "abschnitte": ("sections",),
    "abstrakt": ("abstract",),
    "adler": ("eagle", "eagles"),
    "ahorn": ("maple",),
    "akzente": ("accents",),
    "alle": ("all",),
    "alternativ": ("alternate",),
    "anderer": ("other",),
    "angebracht": ("attached",),
    "anhänger": ("pendant",),
    "antennen": ("antennae",),
    "anzeiger": ("gauges",),
    "apfel": ("apple",),
    "armreif": ("armband",),
    "artikel": ("items",),
    "ast": ("branch",),
    "aufgerissen": ("flared", "frayed"),
    "augenbraue": ("eyebrow",),
    "augenschatten": ("eyeshadow",),
    "augenstift": ("eyeliner",),
    "ausdruck": ("expression",),
    "ausgerichtet": ("aligned",),
    "ausruf": ("exclamation",),
    "ausschnitt": ("cutout",),
    "ausschnitte": ("cutouts",),
    "aussehen": ("appearance",),
    "ausstellung": ("display",),
    "außer": ("except",),
    "banane": ("banana",),
    "band": ("ribbon",),
    "barcodes": ("barcode",),
    "barten": ("sideburns",),
    "bartstreifen": ("whiskers",),
    "basisplatte": ("baseplate",),
    "bauch": ("belly", "abdomen"),
    "baum": ("tree",),
    "becher": ("cups",),
    "bedeckt": ("covered",),
    "befleckt": ("stained",),
    "beide": ("both",),
    "belgisch": ("belgian",),
    "bereich": ("area",),
    "bernstein": ("amber",),
    "besaumt": ("fringed",),
    "besorgt": ("worried",),
    "biene": ("bee",),
    "bild": ("image",),
    "bildend": ("forming",),
    "bildschirm": ("screen",),
    "blasen": ("bubbles",),
    "blatt": ("leaf",),
    "bleistift": ("pencil",),
    "blinzeln": ("winking",),
    "blockig": ("blocky",),
    "blumig": ("floral",),
    "blut": ("blood",),
    "blätter": ("leaves", "petals"),
    "blöcke": ("blocks",),
    "blüte": ("blossom",),
    "bolzen": ("bolt", "bolts"),
    "bowlerhut": ("bowler",),
    "boxen": ("boxing",),
    "braunlich": ("brownish",),
    "brausend": ("frowning",),
    "brett": ("board",),
    "brief": ("letter",),
    "brustbehaftet": ("breasted",),
    "buchsen": ("sockets",),
    "buchstaben": ("letters",),
    "busch": ("tuft",),
    "bälle": ("poms",),
    "bänder": ("bands",),
    "bär": ("bear",),
    "bäume": ("trees",),
    "bögen": ("bows",),
    "bündel": ("bundle",),
    "bürste": ("brush",),
    "chinesisch": ("chinese",),
    "creme": ("cream",),
    "dalmatiner": ("dalmatian",),
    "darstellend": ("depicting",),
    "darunter": ("underneath",),
    "dekorationen": ("decorations",),
    "dekorativ": ("decorative",),
    "delfin": ("dolphin",),
    "detailierung": ("detailing",),
    "detailliert": ("detailed",),
    "deutsch": ("german",),
    "dezent": ("subtle",),
    "diamant": ("diamond",),
    "diamanten": ("diamonds",),
    "dolch": ("dagger",),
    "drei": ("three",),
    "dreieck": ("triangle",),
    "dreiecke": ("triangles",),
    "dreieckig": ("triangular", "tricorn"),
    "dreizack": ("trident",),
    "drucke": ("prints",),
    "durch": ("through",),
    "durchscheinend": ("translucent",),
    "dämon": ("demon",),
    "dänisch": ("danish",),
    "düse": ("nozzle",),
    "eckig": ("angular",),
    "edelstein": ("gem",),
    "edelsteine": ("gemstones",),
    "eichel": ("acorn",),
    "eindrücke": ("indentations",),
    "einfach": ("simple",),
    "einige": ("some",),
    "eins": ("one",),
    "einzelner": ("single",),
    "einäugler": ("monocle",),
    "elefant": ("elephant",),
    "elemente": ("elements",),
    "ende": ("end",),
    "enden": ("ends",),
    "ente": ("duck",),
    "enthaltend": ("containing",),
    "erbsen": ("pea",),
    "erdbeere": ("strawberry",),
    "ernte": ("crop",),
    "etikett": ("tag", "label"),
    "eule": ("owl",),
    "falten": ("wrinkles", "folds", "pleats"),
    "fangzähne": ("fangs",),
    "farbe": ("color", "paint", "tint"),
    "farben": ("colors",),
    "farbig": ("colored",),
    "faust": ("fist",),
    "federn": ("feathers", "springs"),
    "feier": ("party",),
    "fest": ("solid",),
    "figuren": ("characters",),
    "finger": ("fingers",),
    "fisch": ("fish",),
    "flamme": ("flame",),
    "flammen": ("flames",),
    "flaschen": ("bottles",),
    "flauschig": ("fluffy", "fuzzy"),
    "fleckig": ("speckles",),
    "fledermaus": ("bat",),
    "fleisch": ("flesh",),
    "flosse": ("fin",),
    "form": ("shape",),
    "formen": ("shapes",),
    "foto": ("photo",),
    "frachtgut": ("cargo",),
    "frage": ("question",),
    "friseur": ("haircut",),
    "frosch": ("frog",),
    "fuchs": ("fox", "raccoon"),
    "funkeln": ("sparkles",),
    "funkelnd": ("glittery",),
    "futter": ("lining",),
    "fußspuren": ("footprints",),
    "füllen": ("fill",),
    "fünf": ("five",),
    "füße": ("feet",),
    "gabel": ("fork",),
    "galoppierend": ("prancing",),
    "gebogen": ("arched",),
    "gebrochen": ("cracked",),
    "gebunden": ("tied",),
    "gefiedert": ("feathered",),
    "gefleckt": ("speckled",),
    "geflügelte": ("winged",),
    "geformt": ("shaped", "molded"),
    "gefärbt": ("tinted",),
    "gegrunzt": ("furrowed",),
    "gehalten": ("held",),
    "gehoben": ("raised",),
    "geklebt": ("sleeved",),
    "geknittert": ("wrinkled",),
    "gekrümmt": ("curved", "hooked"),
    "gelenke": ("joints", "wrists"),
    "gemacht": ("made",),
    "genäht": ("stitched",),
    "geometrisch": ("geometric",),
    "gepard": ("leopard",),
    "gerandet": ("rimmed",),
    "gerippt": ("ribbed", "ridged"),
    "gerollt": ("coiled", "rolled"),
    "gerät": ("device",),
    "geräte": ("devices",),
    "gerüscht": ("ruffled",),
    "geschnitten": ("cut",),
    "gesichter": ("faces",),
    "gesichtsbereich": ("facial",),
    "gesichtspartie": ("faceplate",),
    "gestapelt": ("stacked",),
    "gestrichelt": ("dashed",),
    "gestylt": ("styled",),
    "gesägt": ("jagged",),
    "getrennt": ("separate",),
    "getränk": ("drink",),
    "gezeigt": ("shown",),
    "gift": ("venom",),
    "glas": ("glass",),
    "glasur": ("icing",),
    "gleiche": ("same",),
    "glitzer": ("glitter",),
    "glitzernd": ("sparkly",),
    "glocken": ("bells",),
    "glänzend": ("shiny", "glossy"),
    "grafik": ("graphic",),
    "gras": ("grass",),
    "griechisch": ("greek",),
    "griff": ("hilt",),
    "griffe": ("holds", "handles"),
    "grünlich": ("greenish",),
    "gürtelbund": ("waistband",),
    "gürteltasche": ("holster",),
    "haarband": ("hairband",),
    "haarlinie": ("hairline",),
    "hahn": ("rooster",),
    "hai": ("shark",),
    "haken": ("hook",),
    "halb": ("half",),
    "halsausschnitt": ("neckline",),
    "halsketten": ("necklaces",),
    "haltend": ("holding",),
    "handabdruck": ("handprint",),
    "handfläche": ("palm",),
    "handschellen": ("handcuffs",),
    "handschuh": ("glove",),
    "handy": ("walkie", "talkie"),
    "hart": ("hard",),
    "herabhängend": ("draped",),
    "hervorhebungen": ("highlights",),
    "herzen": ("hearts",),
    "himmel": ("sky",),
    "hintergrund": ("background",),
    "hirn": ("brain",),
    "hirschgeweih": ("antler", "antlers"),
    "hohl": ("hollow",),
    "huhn": ("chicken",),
    "hängend": ("hanging",),
    "inklusive": ("including",),
    "innen": ("inside", "inner"),
    "innenraum": ("interior",),
    "insekt": ("insect",),
    "insel": ("island",),
    "irgendein": ("any",),
    "iris": ("irises",),
    "italienisch": ("italian",),
    "japanisch": ("japanese",),
    "jeansstoff": ("denim",),
    "jeder": ("each",),
    "kaffee": ("coffee",),
    "kakteen": ("cactus",),
    "kalb": ("calves",),
    "kamm": ("crest", "ridge"),
    "kanadisch": ("canadian",),
    "kaninchen": ("rabbit", "bunny"),
    "kanone": ("cannon",),
    "kante": ("edge",),
    "kanten": ("edges",),
    "karotte": ("carrot",),
    "karte": ("card",),
    "kegel": ("cone",),
    "kegelig": ("conical",),
    "keltisch": ("celtic",),
    "kerne": ("kernels", "seeds"),
    "ketten": ("chains",),
    "kettenpanzerung": ("chainmail",),
    "kirsche": ("cherry",),
    "kiste": ("box",),
    "klappen": ("flaps",),
    "klappstift": ("clipboard",),
    "klaue": ("claw", "claws"),
    "klebend": ("sticking",),
    "kleiner": ("smaller",),
    "klingen": ("blades",),
    "klub": ("club",),
    "knaufe": ("knobs",),
    "knisternd": ("crackled",),
    "knoten": ("knot",),
    "knöchel": ("knees", "knee", "ankles"),
    "knöpft": ("buttoned",),
    "kompass": ("compass",),
    "komplex": ("intricate",),
    "konstruktion": ("structure",),
    "konzentrisch": ("concentric",),
    "kopfband": ("headband",),
    "kopfbedeckung": ("headgear",),
    "kopflampe": ("headlamp",),
    "kopfschmuck": ("headdress",),
    "kopfstück": ("headpiece",),
    "korsett": ("corset",),
    "kran": ("crane",),
    "kratzer": ("scratch", "scratches"),
    "kreis": ("circle",),
    "kreise": ("circles",),
    "kreuz": ("cross",),
    "kreuzweise": ("crisscross",),
    "kriege": ("wars",),
    "kristall": ("crystal",),
    "kristalle": ("crystals",),
    "krokodil": ("crocodile",),
    "kugel": ("sphere",),
    "kugelförmig": ("spherical",),
    "kugeln": ("balls",),
    "kuh": ("cow",),
    "kuppel": ("dome",),
    "kuppelförmig": ("domed",),
    "köpfe": ("heads",),
    "labor": ("lab",),
    "laden": ("store",),
    "laubig": ("leafy",),
    "laufend": ("running",),
    "leer": ("blank",),
    "leicht": ("slight",),
    "lichter": ("lights",),
    "lid": ("eyelids",),
    "lilie": ("lis",),
    "linse": ("lens",),
    "linsen": ("lenses",),
    "lockig": ("curly",),
    "lutschertasche": ("pacifier",),
    "lächelnd": ("smiling",),
    "löcher": ("holes",),
    "löscher": ("extinguisher",),
    "lüfter": ("fan",),
    "lüftungsschlitze": ("vents",),
    "mais": ("corn",),
    "marke": ("marking",),
    "marken": ("marks",),
    "maschen": ("mesh",),
    "matrose": ("sailor",),
    "maul": ("muzzle",),
    "mechanisch": ("mechanical",),
    "medaille": ("medal", "medallion"),
    "medizinisch": ("medical",),
    "mehrere": ("multiple",),
    "mehrteilig": ("multi",),
    "messer": ("knife",),
    "messgerät": ("gauge",),
    "mikrofon": ("microphone",),
    "militärisch": ("military",),
    "mit kapuze": ("hooded",),
    "mit krempe": ("brimmed",),
    "mode": ("fashion",),
    "mops": ("pug",),
    "motive": ("motifs",),
    "moustache": ("mustache",),
    "mundstück": ("mouthpiece",),
    "munition": ("ammunition",),
    "muschel": ("seashell",),
    "musik": ("music",),
    "musikalisches": ("musical",),
    "muskeln": ("muscles",),
    "muskulatur": ("muscle",),
    "muskulös": ("muscular",),
    "mähne": ("mane",),
    "nach unten": ("down",),
    "nahe": ("near",),
    "narbe": ("scar",),
    "nasenlöcher": ("nostrils",),
    "nichts": ("nothing",),
    "nieten": ("rivets",),
    "noppen": ("studs",),
    "noten": ("notes",),
    "notiz": ("note",),
    "nummern": ("numbers",),
    "näht": ("stitch",),
    "nähte": ("stitching", "seams"),
    "oberer": ("upper",),
    "oberfläche": ("surface", "finish"),
    "oberschenkel": ("thighs", "thigh"),
    "objekt": ("object",),
    "objekte": ("objects",),
    "obst": ("fruit",),
    "ohr": ("ear",),
    "ohren": ("ears",),
    "ohrentragend": ("eared",),
    "ohrhörer": ("earpiece",),
    "ohrschalen": ("earpieces",),
    "oktopus": ("octopus",),
    "ordentlich": ("neat", "neatly"),
    "paneel": ("panel",),
    "paneele": ("panels",),
    "pantzer": ("panther",),
    "papier": ("paper",),
    "passend": ("matching",),
    "perlen": ("beads", "pearls"),
    "perlenbesetzt": ("beaded",),
    "perücke": ("wig",),
    "pfeife": ("whistle",),
    "pfeile": ("arrows",),
    "pfeilspitze": ("arrowhead",),
    "pfirsich": ("peach",),
    "pflanze": ("plant",),
    "pfote": ("paw",),
    "pixelig": ("pixelated",),
    "plastik": ("plastic",),
    "platten": ("plates",),
    "plattform": ("platform",),
    "polare": ("polar",),
    "pompon": ("pom",),
    "presse": ("press",),
    "punkt": ("dot",),
    "punkte": ("points",),
    "punktiert": ("dotted",),
    "pupille": ("pupil",),
    "pupillen": ("pupils",),
    "purpur": ("maroon",),
    "quadrate": ("squares",),
    "quadratisch": ("square",),
    "quasten": ("tassels",),
    "rahmen": ("frame", "frames"),
    "rahmung": ("piping",),
    "rand": ("border", "rim"),
    "rasen": ("rush",),
    "reaktor": ("reactor",),
    "rechtecke": ("rectangles",),
    "rechteckig": ("rectangular", "rectangle"),
    "regenbogen": ("rainbow",),
    "reihen": ("rows",),
    "reißverschlüsse": ("zippers",),
    "rentier": ("reindeer",),
    "reptilienartig": ("reptilian",),
    "rettung": ("rescue",),
    "revers": ("lapels",),
    "rillen": ("ridges",),
    "ringe": ("rings",),
    "rippen": ("ribs",),
    "rippenkorb": ("ribcage",),
    "riss": ("crack",),
    "risse": ("cracks",),
    "roben": ("robes",),
    "rohr": ("pipe",),
    "rohre": ("tubes",),
    "rolle": ("scroll",),
    "rosen": ("roses",),
    "rost": ("rust",),
    "rucksäcke": ("backpacks",),
    "räder": ("wheels",),
    "ränder": ("borders",),
    "röhre": ("tube",),
    "rösig": ("rosy",),
    "röte": ("blush",),
    "rückenwirbel": ("spine",),
    "sanduhr": ("hourglass",),
    "saum": ("hem",),
    "schachbrettartig": ("checkered",),
    "schafe": ("sheep",),
    "schale": ("shell",),
    "schallplatte": ("record",),
    "schaltung": ("circuit",),
    "scharf": ("sharp",),
    "schattierung": ("shading",),
    "scheibe": ("slice",),
    "scheinwerfer": ("headlights",),
    "schere": ("scissors",),
    "schienbeine": ("shins",),
    "schilder": ("signs",),
    "schlamm": ("mud",),
    "schlauch": ("tubing",),
    "schleim": ("slime",),
    "schlieren": ("smudges",),
    "schlitze": ("slits",),
    "schläfen": ("temples",),
    "schläuche": ("hoses",),
    "schlüsselanhänger": ("keychain",),
    "schmetterling": ("butterfly",),
    "schmetterlinge": ("butterflies",),
    "schnabel": ("beak",),
    "schnallen": ("buckles",),
    "schnauze": ("snout",),
    "schneeflocke": ("snowflake",),
    "schneeflocken": ("snowflakes",),
    "schneemann": ("snowman",),
    "schnorchel": ("snorkel",),
    "schnürsenkel": ("laces",),
    "schnürung": ("lacing",),
    "schokolade": ("chocolate",),
    "schraubendreher": ("screwdriver",),
    "schreibtisch": ("desk",),
    "schuh": ("shoe",),
    "schule": ("school",),
    "schultern": ("shoulders",),
    "schweiß": ("sweat",),
    "schwerter": ("swords",),
    "schützer": ("guards",),
    "sechs": ("six",),
    "sechseck": ("hexagon",),
    "sechsecke": ("hexagons",),
    "sechseckig": ("hexagonal",),
    "seestern": ("starfish",),
    "segel": ("sail",),
    "segelboot": ("sailboat",),
    "segmente": ("segments",),
    "segmentiert": ("segmented",),
    "seil": ("rope", "tow"),
    "seile": ("ropes",),
    "seilzug": ("drawstring",),
    "seiten": ("sides",),
    "selbst": ("itself",),
    "sichel": ("crescent",),
    "sichtbar": ("visible",),
    "sichtbarkeit": ("visibility",),
    "sieben": ("seven",),
    "siegel": ("seal",),
    "skelettartig": ("skeletal",),
    "skorpion": ("scorpion",),
    "socken": ("socks",),
    "sohle": ("sole",),
    "sohlen": ("soles",),
    "sommerfleck": ("freckle",),
    "sonnenblume": ("sunflower",),
    "sonnenschutzbrille": ("shades",),
    "sonnenstrahl": ("sunburst",),
    "sonnenuntergang": ("sunset",),
    "spalt": ("split",),
    "spangen": ("chevrons",),
    "spiralförmig": ("spiral",),
    "spitze": ("tip", "lace"),
    "spitzen": ("tips",),
    "spritze": ("syringe",),
    "spritzer": ("splatters", "splatter"),
    "spröde": ("crackle",),
    "spur": ("trail",),
    "stachelig": ("spiky",),
    "stacheln": ("spikes",),
    "steine": ("gems",),
    "sternexplosion": ("starburst",),
    "sternmöhre": ("holly",),
    "steuerung": ("control",),
    "stickerei": ("embroidery",),
    "stiel": ("stem",),
    "stiele": ("stems",),
    "stier": ("bull",),
    "stift": ("pen",),
    "stil": ("style",),
    "stilisiert": ("stylized",),
    "stirn": ("forehead",),
    "stock": ("cane",),
    "stoßzähne": ("tusks",),
    "strahlen": ("rays",),
    "strahlend": ("radiating",),
    "streusel": ("sprinkles",),
    "strich": ("streak",),
    "striche": ("streaks",),
    "strickjacke": ("cardigan",),
    "strukturiert": ("textured",),
    "strähnen": ("strands",),
    "stäbe": ("bars",),
    "stämmisch": ("tribal",),
    "stöße": ("bumps",),
    "symbol": ("icon",),
    "symbole": ("symbols", "icons"),
    "szene": ("scene",),
    "säulen": ("columns",),
    "süßigkeiten": ("candy",),
    "taillengürtel": ("waist",),
    "taktisch": ("tactical",),
    "tarnung": ("camouflage",),
    "taschenlampe": ("flashlight",),
    "tausch": ("swap",),
    "tauschbar": ("interchangeable",),
    "teil": ("part", "piece"),
    "teile": ("pieces", "parts"),
    "telefon": ("phone",),
    "tentakel": ("tentacles", "tentacle"),
    "textur": ("texture",),
    "thematisiert": ("themed",),
    "tier": ("animal",),
    "tiergarten": ("zoo",),
    "ton": ("tone",),
    "topf": ("pot",),
    "traditionell": ("traditional",),
    "tragend": ("wearing",),
    "trageriemen": ("lanyard",),
    "trank": ("potion",),
    "traurig": ("sad",),
    "trichter": ("funnel",),
    "tropfen": ("drops", "drop"),
    "tropfend": ("dripping",),
    "träne": ("tear",),
    "tränen": ("tears",),
    "tränentropfen": ("teardrop",),
    "tröpfchen": ("droplets", "drips"),
    "tätowierung": ("tattoo",),
    "tätowierungen": ("tattoos",),
    "töne": ("tones",),
    "uhr": ("clock", "watch"),
    "umgeben": ("surrounded",),
    "umhängetasche": ("crossbody",),
    "umriss": ("outline",),
    "umrisse": ("outlines",),
    "umschlag": ("envelope",),
    "unordentlich": ("messy",),
    "unterarm": ("forearms",),
    "unterer": ("lower",),
    "unterhalb": ("below",),
    "unterhemd": ("undershirt",),
    "unterscheidbar": ("distinct",),
    "unterwäsche": ("underwear",),
    "vene": ("vein",),
    "verband": ("bandages", "bandage"),
    "verdreht": ("twisted",),
    "verkleidung": ("plating",),
    "verkreuzt": ("crossed",),
    "verlauf": ("gradient",),
    "verlängerungen": ("extensions",),
    "verpackt": ("wrapped",),
    "verschiedene": ("various",),
    "versteckt": ("hidden",),
    "verziert": ("ornate",),
    "vier": ("four",),
    "vogel": ("bird",),
    "voll": ("full",),
    "voluminös": ("voluminous",),
    "vorrichtung": ("apparatus",),
    "vorsprünge": ("protrusions",),
    "vögel": ("birds",),
    "waffe": ("weapon", "gun"),
    "waffen": ("weapons",),
    "wangen": ("cheeks",),
    "warnung": ("warning",),
    "was": ("what",),
    "weise": ("manner",),
    "weizen": ("wheat",),
    "wellen": ("waves",),
    "wellig": ("scalloped", "bumpy"),
    "wesen": ("creature",),
    "wimpern": ("eyelashes",),
    "wirbel": ("swirls", "swirl"),
    "wirbelnd": ("swirling",),
    "witterungsbedingt": ("weathering",),
    "wolken": ("clouds", "puffs"),
    "wolle": ("wool",),
    "wort": ("word",),
    "wurzeln": ("roots",),
    "würfel": ("cube",),
    "zahn": ("tooth",),
    "zehen": ("toes",),
    "zeichen": ("sign",),
    "zeichentrick": ("cartoon",),
    "zeichnung": ("drawing",),
    "zeigend": ("pointing",),
    "zelt": ("tent",),
    "zentral": ("central",),
    "zentriert": ("centered",),
    "zerreißbar": ("torn",),
    "zickzack": ("zigzag", "zigzags"),
    "ziel": ("target", "aim"),
    "zottelig": ("shaggy",),
    "zubehörteile": ("attachments",),
    "zugseile": ("drawstrings",),
    "zukunftsweisend": ("futuristic",),
    "zunge": ("tongue",),
    "zusätzlich": ("additional",),
    "zwei": ("two",),
    "zwischen": ("between",),
    "zylindrisch": ("cylindrical",),
    "zündgerät": ("lighter",),
    "ähnlich": ("resembling",),
    "ärmelbündchen": ("cuffs",),
    "äste": ("branches",),
    "äxte": ("axes",),
    "öffnung": ("opening",),
    "überrascht": ("surprised",),
    "überziehend": ("covering",),
})
# ══════════════════════════════════════════════════════════════════════
# Nachschlagen
#
# Deutsch klebt Wörter zusammen und beugt sie. Eine Liste allein findet
# deshalb „Protokolldroide" nicht, obwohl „Protokoll" und „Droide"
# beide darin stehen. Drei Schritte, in dieser Reihenfolge:
#
#   1. **Direkt** – das Wort steht in der Liste.
#   2. **Endung ab** – „Ritters", „Droiden", „rote" auf ihren Stamm.
#   3. **Zerlegen** – am Wörterbuch entlang in zwei oder drei Teile.
#
# Kein Modell, kein Zufall: Dieselbe Eingabe ergibt immer dasselbe.

# Endungen, die im Deutschen an fast jedes Wort treten. Bewusst kurz
# gehalten und **nach Länge sortiert**: „Droiden" soll zu „Droide"
# werden, nicht zu „Droid".
ENDUNGEN = ("innen", "chen", "lein", "ern", "est", "end", "es", "en",
            "em", "er", "el", "n", "e", "s")

# Die Faltung von Umlauten steht in `core` – dieselbe Regel gilt für den
# gespeicherten Suchtext, sonst messen Anfrage und Index verschieden.

# Kürzer als das zerlegen wir nicht: Sonst wird aus „Rot" ein „Ro"+"t".
MINDESTTEIL = 3
MAX_VARIANTEN = 4


def _falten(wort: str) -> str:
    return core.falten(wort)


def _direkt(wort: str) -> tuple:
    """Stufe 1 und 2: die Liste, notfalls ohne Endung."""
    for kandidat in (wort, _falten(wort)):
        treffer = WOERTERBUCH.get(kandidat)
        if treffer:
            return treffer
    for kandidat in (wort, _falten(wort)):
        for endung in ENDUNGEN:
            if len(kandidat) > len(endung) + 2 and kandidat.endswith(endung):
                treffer = WOERTERBUCH.get(kandidat[:-len(endung)])
                if treffer:
                    return treffer
    return ()


def _zerlegen(wort: str, tiefe: int = 0) -> tuple:
    """Stufe 3: zusammengesetzte Wörter aufteilen.

    Der **längste** linke Teil zuerst – sonst zerfällt „Feuerwehrmann" in
    „Feuer" + „Wehrmann", statt am eigenen Eintrag stehenzubleiben. Das
    Fugen-s („Arbeitshose") wird mitgedacht.
    """
    if tiefe > 1 or len(wort) < 2 * MINDESTTEIL:
        return ()
    for schnitt in range(len(wort) - MINDESTTEIL, MINDESTTEIL - 1, -1):
        links = _direkt(wort[:schnitt])
        if not links:
            continue
        rest = wort[schnitt:]
        for kandidat in ((rest, rest[1:]) if rest.startswith("s") else (rest,)):
            if len(kandidat) < MINDESTTEIL:
                continue
            rechts = _direkt(kandidat) or _zerlegen(kandidat, tiefe + 1)
            if rechts:
                # Reihenfolge wie im Deutschen: „Protokoll" vor „Droide".
                return (links[0], rechts[0])
    return ()


def nachschlagen(wort: str) -> tuple:
    """Alle englischen Entsprechungen zu einem deutschen Wort."""
    wort = (wort or "").strip().lower()
    if not wort:
        return ()
    return _direkt(wort) or _zerlegen(wort)


# Wörter, die aus der Anfrage **verschwinden**, statt übersetzt zu werden.
#
# „Jedi mit gelbem Kopf und braunem Umhang" – „mit" und „und" tragen hier
# nichts bei, würden aber als Suchwörter mitverlangt. `with` steht in
# 18.049 von 19.267 Einträgen, `and` in 14.364: Wer sie fordert, schließt
# jede Figur aus, die ohne sie benannt ist, und gewinnt dafür nichts.
#
# `ohne` bleibt drin – „ohne Beine" ist eine echte Einschränkung, und
# `without` steht in gerade einmal 940 Namen.
FUELLWOERTER = {"mit", "und", "der", "die", "das", "den", "dem", "des",
                "ein", "eine", "einem", "einen", "einer", "eines",
                "im", "am", "an", "auf", "bei", "von", "vom", "zum", "zur",
                "als", "auch", "noch", "sowie"}


def anfrage_teilen(q: str) -> list:
    """Eine Anfrage in dieselben Wörter zerlegen, die die Suche benutzt."""
    return [w for w in re.split(r"[^a-z0-9]+", core.falten(q))
            if len(w) >= 2 and w not in FUELLWOERTER]


def uebersetzen(q, nur_ganz: bool = False) -> list:
    """Aus einer deutschen Anfrage englische Suchanfragen bauen.

    **Unbekanntes bleibt stehen.** Was nicht in der Liste ist, ist meist
    ein Eigenname – „Windu", „Weasley", „Hoth" – und steht genau so schon
    im Katalog. Es herauszuwerfen würde die Suche verschlechtern.

    Gibt eine leere Liste zurück, wenn **kein** Wort übersetzt wurde:
    Dann ist nichts gewonnen, und der Aufrufer kann es mit dem Modell
    versuchen.
    """
    woerter = anfrage_teilen(q) if isinstance(q, str) else list(q)
    if not woerter:
        return []
    teile, getroffen, luecken = [], False, 0
    for w in woerter:
        treffer = nachschlagen(w)
        if treffer:
            getroffen = True
            teile.append(list(treffer))
        else:
            luecken += 1
            teile.append([w])
    if not getroffen:
        return []
    # **Halbwissen tritt nicht vor das Modell.** Kennt die Liste nur einen
    # Teil der Anfrage, ist „pirate with augenklappe" das Ergebnis – und
    # das findet nichts. Dann soll das Modell ran, das den ganzen Satz
    # sieht. Erst wenn es nichts liefert, ist die halbe Übersetzung immer
    # noch besser als gar keine (siehe `integrations.suchbegriffe`).
    if nur_ganz and luecken:
        return []
    # Die erste Fassung nimmt überall die naheliegendste Entsprechung.
    fassungen = [" ".join(t[0] for t in teile)]
    # Dann je Wort mit mehreren Entsprechungen **eine** Abwandlung: „grau"
    # ist bei BrickLink mal `gray`, mal `bluish gray`, und beides soll eine
    # Chance bekommen. Alle Kombinationen wären ein Vielfaches an Abfragen.
    for i, t in enumerate(teile):
        for weitere in t[1:]:
            fassung = " ".join(
                weitere if j == i else anderes[0]
                for j, anderes in enumerate(teile))
            if fassung not in fassungen:
                fassungen.append(fassung)
            if len(fassungen) >= MAX_VARIANTEN:
                return fassungen
    return fassungen
