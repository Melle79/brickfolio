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
    "mar": "Marvel",
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
