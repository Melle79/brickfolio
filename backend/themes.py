"""Themen (Star Wars, City …) für die Sortierung der Sammlung.

Minifiguren tragen ihr Thema in der BrickLink-Nummer: `sw1213` ist Star Wars,
`cty0123` City. Das lässt sich ohne jeden Abruf bestimmen und deckt den
Großteil einer Figurensammlung ab. Für Sets und Teile gibt es kein solches
Kürzel – deren Thema kommt aus der BrickLink-Kategorie (siehe main.py).
"""
import re

# BrickLink-Kürzel → Thema. Bewusst nach Länge sortiert ausgewertet, damit
# z. B. „njo" nicht als „nj" durchgeht.
MINIFIG_PREFIXES = {
    "adv": "Adventurers",
    "alp": "Alpha Team",
    "an": "Angry Birds",
    "aqu": "Aquazone",
    "atl": "Atlantis",
    "avt": "Avatar",
    "bat": "Batman",
    "bel": "Belville",
    "cas": "Castle",
    "cty": "City",
    "col": "Sammelfiguren",
    "cre": "Creator",
    "dim": "Dimensions",
    "din": "Dino",
    "dis": "Disney",
    "dp": "Disney Princess",
    "dr": "Dragons",
    "elf": "Elves",
    "exf": "Exo-Force",
    "fab": "Fabuland",
    "frnd": "Friends",
    "gen": "Allgemein",
    "hf": "Hero Factory",
    "hfw": "Hidden Side",
    "hol": "Feiertage",
    "hp": "Harry Potter",
    "hs": "Hidden Side",
    "idea": "Ideas",
    "iaj": "Indiana Jones",
    "jw": "Jurassic World",
    "loc": "Legends of Chima",
    "lom": "Lone Ranger",
    "lor": "Herr der Ringe",
    # **Nicht Marvel.** `mar001` ff. sind Boo, Bowser und Bowser Jr. –
    # das Kürzel gehört Super Mario. Marvel-Figuren laufen unter `sh`
    # (Super Heroes). Am 29.08.2026 an den Katalognamen geprüft.
    "mar": "Super Mario",
    "mk": "Monkie Kid",
    "min": "Minecraft",
    "nex": "Nexo Knights",
    "njo": "Ninjago",
    "ovr": "Overwatch",
    "pi": "Piraten",
    "pha": "Pharaoh's Quest",
    "poc": "Pirates of the Caribbean",
    "pm": "Power Miners",
    "prince": "Prince of Persia",
    "sh": "Super Heroes",
    "sp": "Space",
    "spd": "Speed Champions",
    "sw": "Star Wars",
    "tlm": "The LEGO Movie",
    "tnt": "Turtles",
    "toy": "Toy Story",
    "trn": "Eisenbahn",
    "twn": "Stadt (klassisch)",
    "uagt": "Ultra Agents",
    "vid": "Vidiyo",
    "wc": "Western",
    # ── Am 29.08.2026 aus den Katalognamen ergänzt ────────────────────
    # Der Index kennt 212 Kürzel, benannt waren 57. Der Rest stand als
    # Großbuchstaben-Kürzel in der Themenauswahl – „SOC" statt „Fußball".
    # Aufgenommen wurde nur, was die Namen selbst belegen; wo sie es nicht
    # taten (etwa `bdp`), bleibt das Kürzel stehen. Ein falscher Name ist
    # schlechter als gar keiner: Er sieht aus, als wüsste man es.
    "agt": "Agents",
    "air": "Flughafen",
    "ani": "Animal Crossing",
    "belvfemale": "Belville",
    "belvmale": "Belville",
    "bio": "Bionicle",
    "bob": "SpongeBob",
    "but": "Klassisch: Knopfhemd",
    "chef": "Koch",
    "colhp": "Sammelfiguren: Harry Potter",
    "coltlbm": "Sammelfiguren: Batman Movie",
    "cop": "Polizei (klassisch)",
    "crs": "Cars",
    "div": "Taucher",
    "doc": "Arzt",
    "drm": "DREAMZzz",
    "dupfig": "Duplo",
    "edu": "Education",
    "firec": "Feuerwehr (klassisch)",
    "fst": "FIRST LEGO League",
    "gb": "Ghostbusters",
    "hor": "Klassisch: Querstreifen",
    "js": "Jack Stone",
    "llp": "LEGOLAND",
    "mnn": "Minions",
    "nba": "Basketball (NBA)",
    "oct": "Octan",
    "old": "LEGOLAND (klassisch)",
    "op": "One Piece",
    "par": "Paradisa",
    "pln": "Ohne Aufdruck",
    "rac": "Racers",
    "sc": "Speed Champions",
    "shg": "DC Super Hero Girls",
    "sim": "Die Simpsons",
    "soc": "Fußball",
    "son": "Sonic",
    "tech": "Technic",
    "tls": "LEGO Store",
    "twt": "Trolls",
    "uni": "Unikitty",
    "vik": "Wikinger",
    "wck": "Wicked",
    "wr": "World Racers",
    # ── Zweiter Durchgang, 29.08.2026 ─────────────────────────────────
    # Beim ersten Mal hatte ich nur die 45 größten Gruppen angesehen und
    # den Rest liegen lassen – `fort` (Fortnite) fiel damit durch. Hier
    # sind alle 115 verbliebenen Kürzel durchgegangen; benannt ist, was
    # die Katalognamen selbst belegen.
    "ac": "Alien Conquest",
    "ang": "Angry Birds",
    "arc": "Arktis",
    "ava": "Avatar – Herr der Elemente",
    "baby": "Primo",
    "belvbaby": "Belville",
    "belvfairy": "Belville",
    "bk": "Blacktron",
    "blu": "Bluey",
    "bnk": "Bank",
    "boat": "Boote",
    "btb": "Bob der Baumeister",
    "btf": "Zurück in die Zukunft",
    "car": "Cargo",
    "cl": "Color Line",
    "clik": "Clikits",
    "coldnd": "Sammelfiguren: Dungeons & Dragons",
    "collt": "Sammelfiguren: Looney Tunes",
    "colmar": "Sammelfiguren: Marvel",
    "colsh": "Sammelfiguren: DC Super Heroes",
    "colspi": "Sammelfiguren: Spider-Man",
    "coltlnm": "Sammelfiguren: Ninjago Movie",
    "coltm": "Sammelfiguren: Muppets",
    "coluni": "Sammelfiguren: Unikitty",
    "con": "Bau (klassisch)",
    "dfb": "DFB",
    "dino": "Dino (2012)",
    "dun": "Dune",
    "dupclock": "Duplo",
    "dupmermaid": "Duplo",
    "dupsnowman": "Duplo",
    "edi": "Fußball-Stars",
    "env": "Küstenwache",
    "ext": "Extreme Team",
    "exx": "Exxon",
    "fire": "Feuerwehr",
    # Der Anlass für diesen zweiten Durchgang: `fort001` ist „Battalion
    # Brawler", und bei BrickLink steht darüber Catalog ▸ Minifigures ▸
    # Fortnite.
    "fort": "Fortnite",
    "fre": "FreeStyle",
    "ftv": "Friends (Fernsehserie)",
    "gdh": "Gabbys Puppenhaus",
    "gg": "Gravity Games",
    "gs": "Galaxy Squad",
    "hgh": "Klassisch: Highway",
    "hky": "Eishockey",
    "hrz": "Horizon",
    "incr": "Die Unglaublichen",
    "inf": "LEGO Island",
    "ixs": "Island Xtreme Stunts",
    "jail": "Polizei (Jailbreak Joe)",
    "jbl": "Klassisch: Blaue Jacke",
    "jbr": "Klassisch: Braune Jacke",
    "jred": "Klassisch: Rote Jacke",
    "jstr": "Klassisch: Jacke mit Sternen",
    "lea": "Klassisch: Lederjacke",
    "loz": "The Legend of Zelda",
    "mba": "Master Builder Academy",
    "mck": "Mickey Mouse",
    "mdf": "MD Foods",
    "mm": "Mars Mission",
    "moa": "Vaiana",
    "mof": "Monster Fighters",
    "msk": "Maersk",
    "ncklc": "Klassisch: Halskette",
    "nike": "Nike",
    "ow": "Overwatch",
    "pck": "Klassisch: Jacke mit Taschen",
    "phm": "Project Hail Mary",
    "pop": "Prince of Persia",
    "post": "Post",
    "ppg": "Powerpuff Girls",
    "qtr": "Quatro",
    "que": "Queer Eye",
    "rb": "Rock Band",
    "rck": "Rock Raiders",
    "rep": "Werkstatt",
    "res": "Küstenwache",
    "rsq": "Res-Q",
    "scafema": "Scala",
    "scafemy": "Scala",
    "scd": "Scooby-Doo",
    "shell": "Shell",
    "shr": "Shrek",
    "splc": "Launch Command",
    "spp": "Space Port",
    "sr": "Speed Racer",
    "st": "Stranger Things",
    "stu": "Studios",
    "tel": "Telekom",
    "tgb": "Team GB",
    "tim": "Time Cruisers",
    "tlr": "The Lone Ranger",
    "tms": "Thomas & seine Freunde",
    "tne": "Tine",
    "trc": "Trucker",
    "trek": "Star Trek",
    "tv": "Klassisch: TV-Logo",
    "vel": "Velux",
    "ver": "Klassisch: Längsstreifen",
    "wed": "Wednesday",
    "wtr": "Kellner",
    "ww": "Wild West",
    "x": "Scala",
    "zip": "Sonstige",
}

_PREFIXES_BY_LEN = sorted(MINIFIG_PREFIXES, key=len, reverse=True)

NO_THEME = None          # unbekannt – in der Sortierung ans Ende


def from_minifig_number(item_id: str) -> str | None:
    """Thema aus dem Nummern-Kürzel einer Minifigur, z. B. sw1213 → Star Wars."""
    if not item_id:
        return None
    m = re.match(r"^([a-z]+)\d", item_id.strip().lower())
    if not m:
        return None
    letters = m.group(1)
    for p in _PREFIXES_BY_LEN:
        if letters == p:
            return MINIFIG_PREFIXES[p]
    return None


CUSTOM_THEME = "Custom"


def for_item(item_id: str, item_type: str) -> str | None:
    """Thema, soweit es sich ohne Abruf bestimmen lässt."""
    # Eigene Figuren sind ihr eigenes Thema – sie stehen in keinem Katalog,
    # gehören aber trotzdem nicht unter „Ohne Thema".
    if (item_id or "").startswith("custom-"):
        return CUSTOM_THEME
    if (item_type or "").lower() == "minifig":
        return from_minifig_number(item_id)
    return None
