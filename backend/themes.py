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
