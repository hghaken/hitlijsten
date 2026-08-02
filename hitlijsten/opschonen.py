"""Typo's en schrijffouten uit de database halen.

WAT HIER WEL EN NIET GEBEURT
----------------------------
De bronnen zijn niet schoon. Music Datastats levert een backtick waar een
apostrof hoort (`I`m Not In Love`), top40.nl schrijft "The Beatles" waar
Datastats "Beatles" schrijft, en af en toe staat er gewoon een typefout in een
naam ("Diggy Des" in plaats van "Diggy Dex"). Dit bestand spoort dat op.

Drie soorten, met een oplopend risico:

1. **Tekens** -- een backtick is nooit bedoeld, een dubbele spatie ook niet.
   Machinaal te herstellen, geen oordeel nodig, geen gevolgen voor de sleutel
   (die gooit leestekens toch al weg).
2. **Het lidwoord** -- "The Beatles" en "Beatles" zijn dezelfde band, maar
   leveren verschillende sleutels op en dus twee gescheiden geschiedenissen.
   Machinaal op te sporen, maar de keuze wat de juiste naam is hoort bij een
   bron buiten deze database.
3. **Typefouten in namen en titels** -- alleen te herkennen aan het feit dat de
   ene schrijfwijze vaak voorkomt en de andere twee keer. Wat de goede is,
   weten wij niet; MusicBrainz weet het meestal wel.

Alles wat wordt aangepast gaat door `wijzigingen`, zodat elke correctie
terug te vinden en terug te draaien is. Niets wordt stilzwijgend rechtgezet.

WAAROM NIET GEWOON ALLES SAMENVOEGEN WAT EROP LIJKT
---------------------------------------------------
Omdat lijken niet hetzelfde is als zijn. "Vader Abraham Showorkest" en "Vader
Abraham Show Orkest" is een spelfout; "Sweet Dreams" van Eurythmics en van La
Bouche is dat niet. Deze module stelt daarom voor en voert alleen uit wat
bevestigd is -- door een externe bron of door de hand van de gebruiker.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from typing import Callable, Iterable, Optional

__all__ = ["schoon_tekst", "tekstfouten", "herstel_tekst", "Voorstel",
           "lidwoordparen", "naamparen", "titelparen", "naamvarianten",
           "meerderheidsnaam", "pas_namen_toe", "migreer_lidwoord"]

# Wat er in de bronnen misgaat met leestekens. Bewust kort: elk teken hier is
# er een waarvan is vastgesteld dat het in de data staat en nooit bedoeld is.
_TEKENS = {
    "`": "'",   # backtick -- Music Datastats, 32.000 noteringen
    "´": "'",   # accent aigu als apostrof
    "‘": "'", "’": "'", "‚": "'",
    "“": '"', "”": '"', "„": '"',
    "–": "-", "—": "-", "−": "-", "‐": "-", "‑": "-",
    " ": " ",   # harde spatie
    "​": "",    # nulbreedtespatie
    "�": "",    # vervangingsteken: kapotte codering, beter weg dan fout
}
_MEERVOUDIGE_SPATIE = re.compile(r"\s{2,}")


def schoon_tekst(tekst: str) -> str:
    """Haal leestekens recht die niemand zo bedoeld heeft.

    Laat de betekenis met rust: hoofdletters blijven hoofdletters, een
    vraagteken blijft staan ("Wat is geluk?" is echt de titel) en er wordt
    niets afgekort of uitgeschreven.
    """
    if not tekst:
        return tekst
    for van, naar in _TEKENS.items():
        tekst = tekst.replace(van, naar)
    return _MEERVOUDIGE_SPATIE.sub(" ", tekst).strip()


# --- 1. tekens -------------------------------------------------------------


def tekstfouten(con: sqlite3.Connection) -> list[dict]:
    """Alle noteringen waarvan de tekst niet schoon is."""
    uit = []
    for r in con.execute(
            "SELECT lijst, artiest, titel, COUNT(*) n FROM noteringen"
            " GROUP BY lijst, artiest, titel"):
        artiest, titel = schoon_tekst(r["artiest"]), schoon_tekst(r["titel"])
        if (artiest, titel) != (r["artiest"], r["titel"]):
            uit.append({"lijst": r["lijst"], "oud": (r["artiest"], r["titel"]),
                        "nieuw": (artiest, titel), "aantal": r["n"]})
    return uit


def herstel_tekst(con: sqlite3.Connection, fouten: Iterable[dict],
                  reden: str = "leestekens rechtgezet") -> int:
    """Schrijf de schone tekst weg. Raakt de sleutel niet.

    De sleutel gooit leestekens toch al weg, dus hier verandert alleen wat de
    bezoeker ziet. Dat maakt dit de veiligste van de drie soorten: geen enkele
    notering verhuist naar een ander nummer.
    """
    geraakt = 0
    for fout in fouten:
        oud_a, oud_t = fout["oud"]
        nieuw_a, nieuw_t = fout["nieuw"]
        cursor = con.execute(
            "UPDATE noteringen SET artiest=?, titel=? WHERE lijst=? AND"
            " artiest=? AND titel=?",
            (nieuw_a, nieuw_t, fout["lijst"], oud_a, oud_t))
        if not cursor.rowcount:
            continue
        geraakt += cursor.rowcount
        con.execute(
            "INSERT INTO wijzigingen (tijdstip, soort, verwijst, veld, oud,"
            " nieuw, reden) VALUES (?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), "tekst",
             f"{fout['lijst']}: {oud_a} - {oud_t}", "artiest+titel",
             f"{oud_a} - {oud_t}", f"{nieuw_a} - {nieuw_t}",
             f"{reden} ({cursor.rowcount} noteringen)"))
    con.commit()
    return geraakt


# --- 2. het lidwoord: de sleutels opnieuw berekenen ------------------------


def _hernormaliseer(sleutel: str) -> str:
    """Een al berekende sleutel bijwerken naar de huidige regels.

    Nodig voor `aliases` en `niet_samenvoegen`: daar staan sleutels in en geen
    namen, dus die kunnen niet opnieuw uit de bron worden afgeleid. Twee
    ingrepen: het lidwoord vooraan de artiest weg, en de bijzondere letters
    vertalen (de ø van Bløf werd vroeger weggegooid).
    """
    from .normalize import _LETTERS, _LIDWOORD

    artiest, streep, titel = sleutel.partition("|")
    artiest = _LIDWOORD.sub("", artiest)
    for van, naar in _LETTERS.items():
        artiest = artiest.replace(van.lower(), naar.lower())
        titel = titel.replace(van.lower(), naar.lower())
    return f"{artiest}{streep}{titel}"


def migreer_lidwoord(con: sqlite3.Connection) -> dict:
    """Bereken alle sleutels opnieuw nadat de lidwoordregel is ingevoerd.

    De volgorde doet ertoe. Eerst de tabellen `aliases` en `niet_samenvoegen`,
    want die staan vol sleutels die met de oude regel zijn gemaakt -- laat je
    die staan, dan wijzen ze naar iets wat niet meer bestaat en werken honderd
    met de hand gemaakte koppelingen stil niet meer. Pas daarna de noteringen,
    die de aliassen weer volgen.
    """
    from .normalize import vergeet_aliases

    verslag = {"aliases": 0, "niet_samenvoegen": 0, "noteringen": 0,
               "samengevoegd": 0, "botsingen": []}

    # 1. aliases
    rijen = list(con.execute("SELECT van, naar, opmerking, aangemaakt FROM aliases"))
    nieuw_paren = {}
    for r in rijen:
        van, naar = _hernormaliseer(r["van"]), _hernormaliseer(r["naar"])
        if van == naar:
            continue                     # de alias ging juist over het lidwoord
        if van in nieuw_paren and nieuw_paren[van][0] != naar:
            verslag["botsingen"].append((van, nieuw_paren[van][0], naar))
            continue
        nieuw_paren[van] = (naar, r["opmerking"], r["aangemaakt"])
    if nieuw_paren != {r["van"]: (r["naar"], r["opmerking"], r["aangemaakt"])
                       for r in rijen}:
        con.execute("DELETE FROM aliases")
        con.executemany(
            "INSERT INTO aliases (van, naar, opmerking, aangemaakt)"
            " VALUES (?,?,?,?)",
            [(van, naar, opmerking, aangemaakt)
             for van, (naar, opmerking, aangemaakt) in nieuw_paren.items()])
    verslag["aliases"] = len(nieuw_paren)

    # 2. niet-samenvoegen
    paren = list(con.execute(
        "SELECT sleutel_a, sleutel_b, reden, aangemaakt FROM niet_samenvoegen"))
    nieuw_niet = {}
    for r in paren:
        a, b = _hernormaliseer(r["sleutel_a"]), _hernormaliseer(r["sleutel_b"])
        if a != b:
            nieuw_niet[(a, b)] = (r["reden"], r["aangemaakt"])
    con.execute("DELETE FROM niet_samenvoegen")
    con.executemany(
        "INSERT INTO niet_samenvoegen (sleutel_a, sleutel_b, reden, aangemaakt)"
        " VALUES (?,?,?,?)",
        [(a, b, reden, aangemaakt) for (a, b), (reden, aangemaakt)
         in nieuw_niet.items()])
    verslag["niet_samenvoegen"] = len(nieuw_niet)

    vergeet_aliases()

    # 3. de noteringen
    from .normalize import sleutel_van

    oude_artiesten = {
        r[0] for r in con.execute(
            "SELECT DISTINCT substr(sleutel, 1, instr(sleutel, '|') - 1)"
            " FROM noteringen")}
    for r in list(con.execute("SELECT id, artiest, titel, sleutel FROM noteringen")):
        nieuw = sleutel_van(r["artiest"], r["titel"])
        if nieuw != r["sleutel"]:
            con.execute("UPDATE noteringen SET sleutel=? WHERE id=?",
                        (nieuw, r["id"]))
            verslag["noteringen"] += 1
    nieuwe_artiesten = {
        r[0] for r in con.execute(
            "SELECT DISTINCT substr(sleutel, 1, instr(sleutel, '|') - 1)"
            " FROM noteringen")}
    verslag["samengevoegd"] = len(oude_artiesten) - len(nieuwe_artiesten)

    con.execute(
        "INSERT INTO wijzigingen (tijdstip, soort, verwijst, veld, oud, nieuw,"
        " reden) VALUES (?,?,?,?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"), "sleutel",
         "alle lijsten", "sleutel", f"{len(oude_artiesten)} artiestsleutels",
         f"{len(nieuwe_artiesten)} artiestsleutels",
         "lidwoord (the/de/het) telt niet meer mee in de artiestsleutel; "
         f"{verslag['noteringen']} noteringen herberekend"))
    con.commit()
    return verslag


# --- 2b. één schrijfwijze per artiest --------------------------------------


def _kaal(tekst: str) -> str:
    """Zonder accenten en hoofdletters -- om varianten te kunnen indelen.

    Ook de bijzondere letters, anders belanden "Bløf" en "Blof" in de bak
    "echt andere schrijfwijze" terwijl het puur een tekenkwestie is.
    """
    from .normalize import _LETTERS

    for van, naar in _LETTERS.items():
        tekst = (tekst or "").replace(van, naar)
    tekst = unicodedata.normalize("NFKD", tekst)
    return "".join(c for c in tekst if not unicodedata.combining(c)).lower().strip()


# Twee dingen die de bronnen aan een naam plakken en die geen naam zijn:
#   "Ed Sheeran / Ed Sheeran feat. Googoosh"  -- top40.nl, als een notering
#       halverwege wordt hernoemd; beide namen blijven dan in het veld staan.
#   "Wesley ((Klein))"                        -- Music Datastats, om twee
#       artiesten met dezelfde naam uit elkaar te houden.
# De streep moet spaties om zich heen hebben: zonder die eis wordt "AC/DC"
# afgekapt tot "AC", en dat is precies de fout die dit hoort te repareren.
_SCHUIN = re.compile(r"\s+/\s+.*$")
_DUBBELE_HAAK = re.compile(r"\s*\(\(.*?\)\)")


def _zonder_bronrommel(naam: str) -> str:
    return _SCHUIN.sub("", _DUBBELE_HAAK.sub(" ", naam or "")).strip()


def naamvarianten(con: sqlite3.Connection) -> dict[str, list]:
    """Artiesten die in de database onder meer dan één naam staan.

    Ingedeeld naar wat er verschilt, want dat bepaalt wie de knoop doorhakt:

    - **hoofdletters** ("coldplay" tegen "Coldplay") en **accenten** ("Andre"
      tegen "André"): de database spreekt zichzelf tegen over iets waar geen
      twee meningen over bestaan. De meerderheid beslist, zonder bron.
    - **lidwoord** ("Beatles" tegen "The Beatles"): daar bestaan wel twee
      meningen over, en dan is een catalogus beter dan een telling.
    - **anders**: alles wat overblijft. Daar zit van alles tussen -- echte
      typefouten, samenwerkingen die de ene bron wel en de andere niet noemt --
      en dat leent zich niet voor een regel.
    """
    per_sleutel: dict[str, dict[str, int]] = {}
    for r in con.execute("SELECT sleutel, artiest, COUNT(*) n FROM noteringen"
                         " GROUP BY sleutel, artiest"):
        code = r["sleutel"].split("|", 1)[0]
        namen = per_sleutel.setdefault(code, {})
        namen[r["artiest"]] = namen.get(r["artiest"], 0) + r["n"]

    from .normalize import _LIDWOORD

    bakken: dict[str, list] = {"tekens": [], "lidwoord": [], "anders": []}
    for code, namen in per_sleutel.items():
        if len(namen) < 2:
            continue
        kale = {_kaal(n) for n in namen}
        if len(kale) == 1 or len({_kaal(_zonder_bronrommel(n))
                                  for n in namen}) == 1:
            soort = "tekens"
        elif len({_LIDWOORD.sub("", k) for k in kale}) == 1:
            soort = "lidwoord"
        else:
            soort = "anders"
        bakken[soort].append((code, dict(
            sorted(namen.items(), key=lambda p: -p[1]))))
    return bakken


def _accenten(naam: str) -> int:
    """Hoeveel bijzondere letters staan erin?

    Niet alleen accenten: de ø van Bløf en de å van Håkan zijn eigen letters en
    geen a met een tekentje, maar ze raken net zo goed kwijt onderweg. Alleen
    letters tellen mee -- leestekens en kapotte codering horen hier niet in het
    voordeel te werken.
    """
    return sum(1 for teken in naam if ord(teken) > 127 and teken.isalpha())


def meerderheidsnaam(namen: dict[str, int]) -> str:
    """De juiste schrijfwijze kiezen uit varianten van dezelfde naam.

    Niet simpelweg de meerderheid, want die heeft twee keer aantoonbaar
    ongelijk:

    1. **Een accent raakt kwijt, hij komt er niet bij.** Niemand typt per
       ongeluk "Buisonjé"; wél laat de ene bron na de andere het streepje weg.
       Van "Xander De Buisonje" (25 keer) en "Xander De Buisonjé" (5 keer) is de
       zeldzame dus de goede. Dit weegt het zwaarst.
    2. **Alles in kleine letters is geen schrijfwijze maar een slordigheid.**
       "coldplay" verliest van "Coldplay", ook als drie lijsten hem overnemen.

    Blijft er daarna meer dan één over -- "Rob de Nijs" tegen "Rob De Nijs" --
    dan telt wél gewoon wie vaker voorkomt. Over een tussenvoegsel valt te
    twisten en dan is de gewoonte van de bronnen zo goed als elk ander oordeel.
    """
    def rangschik(paar):
        naam, aantal = paar
        return (_accenten(naam), naam != naam.lower(), aantal)

    return max(namen.items(), key=rangschik)[0]


def bewaar_artiestnaam(con: sqlite3.Connection, sleutel: str, naam: str,
                       bron: str) -> None:
    con.execute(
        "INSERT OR REPLACE INTO artiestnamen (sleutel, naam, bron, aangemaakt)"
        " VALUES (?,?,?,?)",
        (sleutel, naam, bron, datetime.now().isoformat(timespec="seconds")))


def artiestnamen(con: sqlite3.Connection) -> dict[str, str]:
    """De vastgestelde naam per artiestsleutel."""
    return {r["sleutel"]: r["naam"]
            for r in con.execute("SELECT sleutel, naam FROM artiestnamen")}


def pas_namen_toe(con: sqlite3.Connection) -> dict:
    """Schrijf de vastgestelde naam naar alle noteringen die afwijken."""
    tabel = artiestnamen(con)
    if not tabel:
        return {"artiesten": 0, "noteringen": 0}

    verslag = {"artiesten": 0, "noteringen": 0}
    for r in list(con.execute(
            "SELECT sleutel, artiest, COUNT(*) n FROM noteringen"
            " GROUP BY sleutel, artiest")):
        code = r["sleutel"].split("|", 1)[0]
        goed = tabel.get(code)
        if not goed or goed == r["artiest"]:
            continue
        cursor = con.execute(
            "UPDATE noteringen SET artiest=? WHERE sleutel=? AND artiest=?",
            (goed, r["sleutel"], r["artiest"]))
        verslag["noteringen"] += cursor.rowcount
        verslag["artiesten"] += 1
        con.execute(
            "INSERT INTO wijzigingen (tijdstip, soort, verwijst, veld, oud,"
            " nieuw, reden) VALUES (?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), "artiestnaam",
             code, "artiest", r["artiest"], goed,
             f"eenduidige schrijfwijze ({cursor.rowcount} noteringen)"))
    con.commit()
    return verslag


# --- 3: kandidaten ---------------------------------------------------------


@dataclass
class Voorstel:
    """Twee schrijfwijzen die volgens ons hetzelfde zijn.

    `vaak` en `zelden` zeggen niets over welke de juiste is -- dat oordeel komt
    van buiten. Ze zeggen alleen hoe de database er nu uitziet.
    """

    soort: str                  # "lidwoord" | "artiest" | "titel"
    vaak: str                   # de veelvoorkomende schrijfwijze
    zelden: str                 # de zeldzame
    vaak_sleutel: str
    zelden_sleutel: str
    noteringen_vaak: int
    noteringen_zelden: int
    gelijkenis: float = 1.0
    lijsten_vaak: set = field(default_factory=set)
    lijsten_zelden: set = field(default_factory=set)
    oordeel: Optional[str] = None      # wat de externe bron zegt
    bron: str = ""

    @property
    def dezelfde_lijst(self) -> bool:
        """Staan beide schrijfwijzen in dezelfde lijst?

        Zo ja, dan is het bijna zeker een typefout: één lijst schrijft een naam
        niet twee keer anders. Staan ze in verschillende lijsten, dan kan het
        ook gewoon huisstijl zijn -- en dan is samenvoegen een keuze, geen
        correctie.
        """
        return bool(self.lijsten_vaak & self.lijsten_zelden)


def _artiesten(con: sqlite3.Connection) -> tuple[dict, dict, dict]:
    """(noteringen per artiestsleutel, naam per sleutel, lijsten per sleutel)."""
    aantal: dict[str, int] = {}
    naam: dict[str, str] = {}
    lijsten: dict[str, set] = {}
    for r in con.execute(
            "SELECT lijst, artiest, sleutel, COUNT(*) n FROM noteringen"
            " GROUP BY lijst, artiest, sleutel"):
        code = r["sleutel"].split("|", 1)[0]
        aantal[code] = aantal.get(code, 0) + r["n"]
        lijsten.setdefault(code, set()).add(r["lijst"])
        # De meest gebruikte schrijfwijze wint als weergave.
        if naam.get(code) is None or r["n"] > aantal.get(f"~{code}", 0):
            naam[code] = r["artiest"]
            aantal[f"~{code}"] = r["n"]
    return ({k: v for k, v in aantal.items() if not k.startswith("~")},
            naam, lijsten)


def lidwoordparen(con: sqlite3.Connection) -> list[Voorstel]:
    """Artiesten die er zowel met als zonder "The" in staan.

    Geen gelijkenis-gegok: het lidwoord is het enige verschil, verder is de
    sleutel teken voor teken gelijk.
    """
    aantal, naam, lijsten = _artiesten(con)
    per_kaal: dict[str, list[str]] = {}
    for code in aantal:
        kaal = code[4:] if code.startswith("the ") else code
        per_kaal.setdefault(kaal, []).append(code)

    uit = []
    for kaal, codes in per_kaal.items():
        if len(codes) < 2 or not any(c.startswith("the ") for c in codes):
            continue
        met = next(c for c in codes if c.startswith("the "))
        zonder = next(c for c in codes if not c.startswith("the "))
        paar = sorted((met, zonder), key=lambda c: -aantal[c])
        uit.append(Voorstel(
            "lidwoord", naam[paar[0]], naam[paar[1]], paar[0], paar[1],
            aantal[paar[0]], aantal[paar[1]],
            lijsten_vaak=lijsten[paar[0]], lijsten_zelden=lijsten[paar[1]]))
    return sorted(uit, key=lambda v: -(v.noteringen_vaak + v.noteringen_zelden))


def _lijkende_paren(namen: list[str], drempel: float,
                    lengteverschil: int = 3) -> Iterable[tuple[float, str, str]]:
    """Paren die op elkaar lijken, zonder n-kwadraat over alles.

    Groeperen op de eerste twee tekens scheelt een factor duizend en kost
    alleen de paren die al in het eerste teken verschillen -- en dat is bij een
    typefout in een naam zelden waar.
    """
    groepen: dict[str, list[str]] = {}
    for naam in namen:
        groepen.setdefault(naam[:2], []).append(naam)
    for groep in groepen.values():
        for i, a in enumerate(sorted(groep)):
            for b in sorted(groep)[i + 1:]:
                if abs(len(a) - len(b)) > lengteverschil:
                    continue
                score = SequenceMatcher(None, a, b).ratio()
                if score >= drempel:
                    yield score, a, b


def naamparen(con: sqlite3.Connection, drempel: float = 0.90,
              scheefheid: int = 8) -> list[Voorstel]:
    """Artiestnamen die verdacht veel op elkaar lijken.

    `scheefheid` is het filter dat dit bruikbaar maakt: een typefout komt een
    paar keer voor, de juiste schrijfwijze tientallen keren. Twee namen die
    allebei vaak voorkomen zijn meestal echt twee artiesten.
    """
    aantal, naam, lijsten = _artiesten(con)
    uit = []
    for score, a, b in _lijkende_paren(list(aantal), drempel):
        # "The X" tegen "X" is klasse 2, niet deze.
        if a.startswith("the ") != b.startswith("the "):
            continue
        weinig, veel = sorted((a, b), key=lambda c: aantal[c])
        if not (aantal[weinig] <= scheefheid <= aantal[veel]):
            continue
        uit.append(Voorstel(
            "artiest", naam[veel], naam[weinig], veel, weinig,
            aantal[veel], aantal[weinig], round(score, 3),
            lijsten[veel], lijsten[weinig]))
    return sorted(uit, key=lambda v: -v.gelijkenis)


def titelparen(con: sqlite3.Connection, drempel: float = 0.92) -> list[Voorstel]:
    """Twee titels bij dezelfde artiest die bijna gelijk zijn.

    Hier is de artiest al gelijk, dus de kans op toeval is klein: "Raindrops
    Keep Fallin' On My Head" en "...Falling..." is één nummer.
    """
    aantal: dict[tuple[str, str], int] = {}
    weergave: dict[tuple[str, str], str] = {}
    lijsten: dict[tuple[str, str], set] = {}
    artiestnaam: dict[str, str] = {}
    for r in con.execute(
            "SELECT lijst, artiest, titel, sleutel, COUNT(*) n FROM noteringen"
            " GROUP BY lijst, artiest, titel, sleutel"):
        code, _, titel = r["sleutel"].partition("|")
        sleutel = (code, titel)
        aantal[sleutel] = aantal.get(sleutel, 0) + r["n"]
        lijsten.setdefault(sleutel, set()).add(r["lijst"])
        weergave.setdefault(sleutel, r["titel"])
        artiestnaam.setdefault(code, r["artiest"])

    per_artiest: dict[str, list[str]] = {}
    for code, titel in aantal:
        per_artiest.setdefault(code, []).append(titel)

    uit = []
    for code, titels in per_artiest.items():
        if len(titels) < 2:
            continue
        for score, a, b in _lijkende_paren(titels, drempel):
            weinig, veel = sorted((a, b), key=lambda t: aantal[(code, t)])
            uit.append(Voorstel(
                "titel", f"{artiestnaam[code]} — {weergave[(code, veel)]}",
                f"{artiestnaam[code]} — {weergave[(code, weinig)]}",
                f"{code}|{veel}", f"{code}|{weinig}",
                aantal[(code, veel)], aantal[(code, weinig)], round(score, 3),
                lijsten[(code, veel)], lijsten[(code, weinig)]))
    return sorted(uit, key=lambda v: -v.gelijkenis)
