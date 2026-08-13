"""Nederlandstalig of niet, per nummer.

DE DRIETRAP
-----------
Uit de titel alleen is de zangtaal niet met zekerheid op te maken: "Marian"
zegt niets, "Una Paloma Blanca" heeft een Spaanse titel maar is Engelstalig
gezongen. Daarom drie bewijzen, van hard naar zacht:

1. **De lijst zelf** ("lijst"). De Oranje Top 30 en de Sterren NL Top 25 zijn
   per definitie Nederlandstalig. Elk nummer dat daar ooit in stond, is
   bewezen Nederlandstalig -- de hardste grond die er is.

2. **De artiest** ("artiest"). Wie vrijwel alleen Nederlandstalig werk in de
   database heeft staan (Frans Bauer, Marianne Weber), zingt zijn overige
   nummers vrijwel zeker ook in het Nederlands. De doorslag geven we alleen
   als de titel niet duidelijk anderstalig is.

3. **De titel** ("titel"). Voor de rest telt een woordenlijst-score: typisch
   Nederlandse functiewoorden en lettergrepen tegen Engelse, Duitse en Franse
   markeerwoorden. Alleen bij overtuigend Nederlands wordt er gemarkeerd --
   een gemiste vlag is minder erg dan een onterechte.

De uitslag staat in de tabel `taal`, los van `noteringen`: de vrijdagrun
schrijft weekrijen opnieuw en zou een kolom daar stilletjes wissen. Met
`bron = "hand"` wint een handmatige correctie het altijd van de automatiek.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime

__all__ = ["herken_alles", "nederlandstalige_sleutels", "zet_hand"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS taal (
    sleutel         TEXT PRIMARY KEY,
    nederlandstalig INTEGER NOT NULL,
    bron            TEXT NOT NULL,      -- lijst | artiest | titel | hand
    aangemaakt      TEXT
);
"""

# De lijsten die alleen Nederlandstalig werk toelaten.
NL_LIJSTEN = ("oranje", "sterrennl")

# Functiewoorden die vrijwel alleen in het Nederlands voorkomen. Bewust geen
# woorden die ook Engels, Duits of Fries zijn ("in", "is", "man", "water").
_NL_WOORDEN = {
    "de", "het", "een", "ik", "jij", "je", "jou", "jouw", "mij", "mijn",
    "wij", "zij", "ons", "onze", "niet", "niets", "geen", "naar", "voor",
    "met", "van", "bij", "uit", "aan", "ben", "bent", "heb", "hebt", "heeft",
    "wil", "kan", "kun", "zal", "zou", "moet", "mag", "laat", "kom", "ga",
    "gaat", "doe", "doet", "zie", "ziet", "weet", "denk", "voel", "hou",
    "houd", "blijf", "altijd", "nooit", "weer", "meer", "alles", "iedereen",
    "niemand", "iets", "ergens", "nergens", "samen", "alleen", "liefde",
    "hart", "leven", "wereld", "nacht", "morgen", "vandaag", "gisteren",
    "zomer", "winter", "mooi", "mooie", "klein", "kleine", "groot", "grote",
    "lief", "lieve", "echte", "eigen", "terug", "weg", "thuis", "huis",
    "ogen", "handen", "dromen", "droom", "zonder", "tegen", "tussen",
    "omdat", "want", "maar", "toch", "als", "dan", "dat", "dit", "deze",
    "die", "er", "hier", "daar", "waarom", "hoe", "wat", "wie", "jullie",
    "meisje", "jongen", "vrouw", "kerst", "sinterklaas", "oranje", "holland",
    "nederland", "amsterdam", "rotterdam", "verliefd", "vergeet", "kus",
    "dans", "zing", "lach", "huil", "bloemen", "sterren", "hemel", "zon",
    "avond", "meneer", "mevrouw", "verdriet", "tranen", "vriend", "vriendin",
    "moeder", "vader", "kind", "kinderen", "jaren", "jaar", "laatste",
    "eerste", "nieuwe", "oude", "rode", "witte", "blauwe", "stad", "straat",
    "regen", "wolken", "afscheid", "voorbij", "dichtbij", "overal", "ooit",
    "zeg", "vraag", "geef", "neem", "wacht", "spring", "vlieg", "veel",
}
# Duidelijk anderstalige markeerwoorden; een treffer hiervan blokkeert de
# titel- en artiestroute (de lijstroute niet: die is bewijs, geen gok).
_VREEMD_WOORDEN = {
    # engels
    "the", "you", "your", "my", "love", "i'm", "it's", "don't", "can't",
    "baby", "girl", "boy", "night", "heart", "never", "always", "want",
    "need", "feel", "know", "why", "when", "where", "what's", "gonna",
    "wanna", "one", "two", "time", "life", "world", "away", "down", "up",
    "back", "again", "together", "forever", "tonight", "everybody", "and",
    "with", "without", "this", "that", "there", "here", "she", "he", "we",
    "are", "was", "were", "have", "has", "had", "will", "would", "could",
    "should", "make", "made", "take", "give", "come", "go", "going", "get",
    "got", "let", "say", "said", "tell", "told", "song", "dance", "dancing",
    # duits
    "der", "die", "das", "ich", "du", "dich", "dir", "mich", "mir", "und",
    "nicht", "ein", "eine", "immer", "wieder", "liebe", "herz", "schön",
    "weiss", "klein", "gross", "nacht", "traum", "träume", "wenn", "dann",
    # frans
    "le", "la", "les", "je", "tu", "moi", "toi", "mon", "ma", "amour",
    "c'est", "n'est", "pour", "avec", "sans", "toujours", "jamais", "rien",
    # spaans/italiaans
    "el", "los", "las", "yo", "mi", "tu", "te", "amor", "corazon", "vida",
    "bella", "bello", "una", "uno", "sole", "cuore", "amore", "ti", "io",
}
# Nederlands blijft Nederlands, ook als "klein" en "nacht" ook Duits zijn.
_VREEMD_WOORDEN -= _NL_WOORDEN

# Lettergrepen en uitgangen die sterk op Nederlands wijzen.
_NL_PATRONEN = (
    re.compile(r"ij"), re.compile(r"sch"), re.compile(r"(?:^|\s)ge\w{3,}"),
    re.compile(r"\w(?:tje|dje|pje|kje)(?:\s|$)"), re.compile(r"\wheid(?:\s|$)"),
    re.compile(r"\wlijk(?:e|s)?(?:\s|$)"), re.compile(r"eeuw"),
    re.compile(r"\woekoe"), re.compile(r"uw(?:\s|$)"),
)


def _woorden(tekst: str) -> list[str]:
    return re.findall(r"[a-zà-ÿ']+", (tekst or "").lower())


def titel_lijkt_nederlands(titel: str) -> bool:
    """Overtuigend Nederlands, alleen op de titel afgegaan."""
    woorden = _woorden(titel)
    if not woorden:
        return False
    if any(w in _VREEMD_WOORDEN for w in woorden):
        return False
    nl = sum(1 for w in woorden if w in _NL_WOORDEN)
    plat = " ".join(woorden)
    patronen = sum(1 for p in _NL_PATRONEN if p.search(plat))
    # Twee onafhankelijke aanwijzingen, of een heel sterke enkele.
    return nl >= 2 or (nl >= 1 and patronen >= 1) or patronen >= 2


def titel_lijkt_vreemd(titel: str) -> bool:
    """Duidelijk anderstalig; blokkeert de artiestroute."""
    woorden = _woorden(titel)
    return sum(1 for w in woorden if w in _VREEMD_WOORDEN) >= 1


def _artiest_van(sleutel: str) -> str:
    return sleutel.split("|", 1)[0]


def herken_alles(con: sqlite3.Connection) -> dict:
    """Deel alle nummers in. Geeft de telling per bron terug.

    Handmatige beslissingen (bron "hand") blijven onaangeroerd; al het
    andere wordt opnieuw bepaald, zodat nieuw bewijs (een nummer dat alsnog
    de Oranje Top 30 haalt) meteen doorwerkt.
    """
    con.executescript(SCHEMA)
    nu = datetime.now().isoformat(timespec="seconds")

    hand = {r[0] for r in con.execute(
        "SELECT sleutel FROM taal WHERE bron='hand'")}

    alle = {}   # sleutel -> titel (een willekeurige schrijfwijze volstaat)
    for r in con.execute("SELECT DISTINCT sleutel, titel FROM noteringen"):
        alle.setdefault(r[0], r[1])

    plek = ",".join("?" for _ in NL_LIJSTEN)
    uit_lijst = {r[0] for r in con.execute(
        f"SELECT DISTINCT sleutel FROM noteringen WHERE lijst IN ({plek})",
        NL_LIJSTEN)}

    beslist: dict[str, str] = {}          # sleutel -> bron
    for sleutel in uit_lijst:
        if sleutel in alle:
            beslist[sleutel] = "lijst"

    # Titelroute voor alles wat nog open staat.
    for sleutel, titel in alle.items():
        if sleutel in beslist or sleutel in hand:
            continue
        if titel_lijkt_nederlands(titel):
            beslist[sleutel] = "titel"

    # Artiestroute, twee rondes: eerst op hard lijstbewijs, daarna nogmaals
    # met de titeluitslagen erbij -- zo krijgen ook artiesten van voor 2008
    # (geen Oranje/Sterren) hun overige nummers mee. De maat is niet het
    # aandeel gemarkeerde nummers (korte Nederlandse titels als "De Vlieger"
    # of "Avond" zijn per titel onbeslisbaar en zouden de teller drukken),
    # maar de verhouding tussen bewezen Nederlands en duidelijk anderstalig:
    # wie twee keer bewezen Nederlands zong en hooguit sporadisch een
    # anderstalige titel voerde, krijgt ook zijn korte titels mee.
    for _ in range(2):
        per_artiest: dict[str, list[int]] = {}
        for sleutel, titel in alle.items():
            a = _artiest_van(sleutel)
            per_artiest.setdefault(a, [0, 0])
            if sleutel in beslist:
                per_artiest[a][0] += 1
            elif titel_lijkt_vreemd(titel):
                per_artiest[a][1] += 1
        zeker = {a for a, (nl, vreemd) in per_artiest.items()
                 if nl >= 2 and nl / (nl + vreemd) >= 0.8}
        for sleutel, titel in alle.items():
            if sleutel in beslist or sleutel in hand:
                continue
            if _artiest_van(sleutel) in zeker and not titel_lijkt_vreemd(titel):
                beslist[sleutel] = "artiest"

    con.execute("DELETE FROM taal WHERE bron<>'hand'")
    con.executemany(
        "INSERT OR IGNORE INTO taal (sleutel, nederlandstalig, bron,"
        " aangemaakt) VALUES (?,1,?,?)",
        [(sleutel, bron, nu) for sleutel, bron in beslist.items()])
    con.commit()

    telling = {"lijst": 0, "artiest": 0, "titel": 0}
    for bron in beslist.values():
        telling[bron] += 1
    telling["hand"] = len(hand)
    telling["totaal_nummers"] = len(alle)
    return telling


def nederlandstalige_sleutels(con: sqlite3.Connection) -> set[str]:
    """Alle sleutels met de vlag, voor de webpagina's en de filters."""
    con.executescript(SCHEMA)
    return {r[0] for r in con.execute(
        "SELECT sleutel FROM taal WHERE nederlandstalig=1")}


def zet_hand(con: sqlite3.Connection, sleutel: str,
             nederlandstalig: bool) -> None:
    """Een handmatige beslissing; wint het van elke latere automatiek."""
    con.execute(
        "INSERT OR REPLACE INTO taal (sleutel, nederlandstalig, bron,"
        " aangemaakt) VALUES (?,?,'hand',?)",
        (sleutel, 1 if nederlandstalig else 0,
         datetime.now().isoformat(timespec="seconds")))
    con.commit()
