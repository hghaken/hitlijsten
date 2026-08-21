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

from . import db

__all__ = ["schoon_tekst", "eenduidige_credit", "gast_uit_titel",
           "x_is_samenwerking", "komma_is_samenwerking",
           "met_is_samenwerking", "ondertitel_tussen_haken", "tekstfouten", "herstel_tekst", "Voorstel",
           "lidwoordparen", "naamparen", "titelparen", "naamvarianten",
           "meerderheidsnaam", "pas_namen_toe", "migreer_lidwoord",
           "titelvarianten", "pas_titels_toe", "geleende_hoofdletters",
           "uitgave_en_nummer", "splits_kanten", "splits_dubbele_a_kanten",
           "spatievarianten", "verzeker_aliassen", "versies_op_een_plek",
           "zelfde_act", "splits_versies",
           "corrigeer_nummer", "splits_nummer"]

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
# Music Datastats zet dubbele haken om naamgenoten te scheiden: "Asia ((GBR))"
# naast "Asia ((NLD))", "Nirvana ((USA))" naast "Nirvana ((GBR))". Dat
# onderscheid is echt en blijft staan; alleen de tweede haak is nergens voor
# nodig en leest slecht.
_DUBBELE_HAKEN = re.compile(r"\(\((.+?)\)\)")


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
    tekst = _DUBBELE_HAKEN.sub(lambda m: f"({m.group(1)})", tekst)
    return _MEERVOUDIGE_SPATIE.sub(" ", tekst).strip()


# Eén aanduiding voor een samenwerking. De bronnen gebruiken feat., feat,
# ft., ft en featuring door elkaar -- vijf vormen voor hetzelfde -- en dat
# leest niet alleen rommelig, het splitst ook artiesten.
#
# Alleen bij de ARTIEST. In een titel kan zo'n woord bij de naam horen die
# op het label staat, en daar is het geen scheidingsteken maar tekst.
#
# "featuring" staat vooraan in de opsomming en dat is geen smaak: een regexp
# neemt de eerste tak die past, dus met "feat" ervoor werd "featuring" gelezen
# als "feat" plus een overgebleven "uring".
# "w/" staat er ook bij, en dat is geen inconsequentie tegenover de opmerking
# hierboven over "with". Voluit geschreven is "with" een gewoon Engels woord en
# dus geen veilig scheidingsteken; de afkorting "w/" is dat nooit -- die
# betekent in een credit altijd "samen met". top40.nl schrijft hem consequent
# bij Kygo ("Kygo w/ OneRepublic"), en zonder deze regel kreeg die een eigen
# sleutel: de schuine streep verdwijnt zonder spoor en er blijft een losse "w"
# staan, dus 'kygo w onerepublic' naast 'kygo & onerepublic'.
_CREDIT = re.compile(r"\s*\b(?:featuring|feat\b\.?|ft\b\.?|w/)\s*", re.I)


def eenduidige_credit(artiest: str) -> str:
    """feat. / feat / ft. / ft / featuring / w/ -> &"""
    if not artiest:
        return artiest
    return _MEERVOUDIGE_SPATIE.sub(" ", _CREDIT.sub(" & ", artiest)).strip()


# Soms staat de gastartiest in de titel in plaats van bij de artiest:
#   "Andrea Bocelli"  +  "Vivere (feat. Gerardina Trovato)"
# Dan hoort Gerardina Trovato in de artiestkolom en niet in de titel.
#
# Uitsluitend tussen haken, en uitsluitend feat/ft/featuring. Zonder die
# beperking sneuvelt de halve Top 40: "With Or Without You", "Killing Me
# Softly With His Song", "Stuck In The Middle With You" -- 292 titels waarin
# "with" gewoon een woord is en geen scheidingsteken.
_GAST_IN_TITEL = re.compile(r"\s*\((?:feat|ft|featuring)\b\.?\s*([^)]+)\)")


def gast_uit_titel(artiest: str, titel: str) -> tuple:
    """Haal een gastartiest uit de titel en zet hem bij de artiest.

    Geeft (artiest, titel) terug; zonder gast blijft alles zoals het was.
    Staat de gast al bij de artiest, dan wordt hij er niet nog eens bij
    gezet -- alleen uit de titel gehaald.
    """
    if not titel:
        return artiest, titel
    treffer = _GAST_IN_TITEL.search(titel)
    if not treffer:
        return artiest, titel
    gast = treffer.group(1).strip()
    kale_titel = _MEERVOUDIGE_SPATIE.sub(
        " ", _GAST_IN_TITEL.sub("", titel)).strip()
    if _kaal(gast) in _kaal(artiest or ""):
        return artiest, kale_titel
    return f"{artiest} & {gast}".strip(" &"), kale_titel


# De "x" tussen twee artiesten is sinds een jaar of tien de gewone manier
# om een samenwerking te schrijven: "Snelle x Maan", "Coldplay x BTS".
# Maar de x is ook gewoon een letter, en dan mag hij niet sneuvelen:
#
#   Lil Nas X & Billy Ray Cyrus      X hoort bij de naam, & is de scheiding
#   Kygo & X Ambassadors             idem, andersom
#   Dutch X Factor 2010              hier is X geen van beide
#
# De regel: een losse x is alleen een scheidingsteken als er aan geen van
# beide kanten al een scheidingsteken staat. Dat vangt de eerste twee. Voor
# namen waarin de X gewoon meedoet is er een lijst -- die zijn niet af te
# leiden, alleen op te sommen.
_X_TUSSEN = re.compile(r"(?<=[^&,/+(])\s+x\s+(?=[^&,/+)])", re.I)
_X_HOORT_ERBIJ = (
    "dutch x factor", "x factor",
)


def x_is_samenwerking(artiest: str) -> str:
    """"Snelle x Maan" -> "Snelle & Maan", maar Lil Nas X blijft heel."""
    if not artiest:
        return artiest
    plat = _kaal(artiest)
    if any(naam in plat for naam in _X_HOORT_ERBIJ):
        return artiest
    return _MEERVOUDIGE_SPATIE.sub(" ", _X_TUSSEN.sub(" & ", artiest)).strip()


# Een komma tussen twee artiesten is een scheidingsteken -- "50 Cent, Dr. Dre
# & Alicia Keys" zijn er drie -- maar in een bandnaam hoort hij erbij, en aan
# de vorm is dat niet te zien. Dit lijstje is daarom niet bedacht maar
# opgezocht: elk van de 401 artiestnamen met een komma is aan MusicBrainz
# voorgelegd met de vraag of de hele reeks één act is. Bij 26 was het antwoord
# ja.
#
# Een naam die één van deze bevat blijft in zijn geheel met rust. Dat is
# nodig voor "Phats & Small & Earth, Wind & Fire" en "ELP [Emerson, Lake &
# Palmer]": daar hoort de komma bij het stuk dat beschermd is.
_KOMMA_HOORT_ERBIJ = (
    "Ashton, Gardner & Dyke",
    "Blood, Sweat & Tears",
    "Cotton, Lloyd & Christian",
    "Crosby, Stills & Nash",
    "Crosby, Stills, Nash & Young",
    "Dave Dee, Dozy, Beaky, Mick & Tich",
    "Dutch, Rhythm, Steel & Show Band",
    "Earth, Wind & Fire",
    "Ecstasy, Passion & Pain",
    "Emerson, Lake & Palmer",
    "Faith, Hope & Charity",
    "Grover Washington, Jr.",
    "Hamilton, Joe Frank & Reynolds",
    "Julie Driscoll, Brian Auger & The Trinity",
    "Linda, Roos & Jessica",
    "Lipps, Inc.",
    "Los Angeles, The Voices",
    "Marilyn McCoo & Billy Davis, Jr.",
    "Marshall, Hain",
    "Marvin, Welch & Farrar",
    "McGuinn, Clark & Hillman",
    "Peter, Paul and Mary",
    "Portugal, The Man",
    "Ray, Goodman & Brown",
    "Tina, Toos & Tessa",
    "Tyler, The Creator",
)


def komma_is_samenwerking(artiest: str) -> str:
    """"50 Cent, Dr. Dre & Alicia Keys" -> "50 Cent & Dr. Dre & Alicia Keys"."""
    if not artiest or "," not in artiest:
        return artiest
    plat = _kaal(artiest)
    if any(_kaal(naam) in plat for naam in _KOMMA_HOORT_ERBIJ):
        return artiest
    samen = artiest.replace(",", " & ")
    return _MEERVOUDIGE_SPATIE.sub(" ", samen).replace(" & & ", " & ").strip()


# Het Nederlandse "met" tussen twee artiesten: "Wilma met Vader Abraham",
# "Doe Maar met Brainpower". Ook hier zijn de uitzonderingen het echte werk:
#
#   Zondag Met Lubach, Fokko Met De Bordjes   Met hoort bij de naam
#   "met dank aan", "met medewerking van",
#   "met zang van", "met begeleiding van"     een zinsdeel, geen scheiding
#
# "duet met", "in duet met" en "samen met" zijn juist wel scheidingen, en
# het voorafgaande woord gaat mee weg: "Paul De Leeuw - duet met Simone
# Kleinsma" wordt "Paul De Leeuw & Simone Kleinsma".
_MET_HOORT_ERBIJ = (
    "zondag met lubach", "fokko met de bordjes",
)
_MET_ZINSDEEL = re.compile(
    r"\bmet\s+(?:dank\s+aan|medewerking\s+van|zang\s+van|begeleiding\s+van)", re.I)
_DUET = re.compile(r"\s*(?:-\s*)?\b(?:in\s+)?duet\s+met\s+|\s+samen\s+met\s+", re.I)
_MET = re.compile(r"\s+met\s+", re.I)


def met_is_samenwerking(artiest: str) -> str:
    """"Wilma met Vader Abraham" -> "Wilma & Vader Abraham"."""
    if not artiest:
        return artiest
    plat = _kaal(artiest)
    if any(naam in plat for naam in _MET_HOORT_ERBIJ):
        return artiest
    if _MET_ZINSDEEL.search(artiest):
        return artiest
    artiest = _DUET.sub(" & ", artiest)
    artiest = _MET.sub(" & ", artiest)
    return _MEERVOUDIGE_SPATIE.sub(" ", artiest).strip()


# "Cheerleader - Felix Jaehn Remix", "Eye Of The Tiger - The Theme From
# Rocky III". Het deel achter het streepje is een ondertitel, en de
# huisstijl zet die tussen haken: "Cheerleader (Felix Jaehn Remix)".
#
# Alleen als dat deel zichzelf verraadt met een versie- of themawoord.
# Zonder die eis sneuvelen medleys ("One Love - People Get Ready") en
# tweetalige dubbeltitels ("Un Dia - One Day"), en dat zijn geen
# ondertitels maar tweede titels. De sleutel verandert nooit mee: die
# gooit leestekens toch al weg, dus dit is puur weergave.
_ONDERTITELWOORD = re.compile(
    r"\b(?:re-?mix(?:es)?|rmx|mix(?:es)?|live|version|versie|edit|akoestisch|acoustic|unplugged|instrumenta[al]*|demo|club|extended|radio|mono|stereo|deel [ivx0-9]+|part [ivx0-9]+|pt\.? [ivx0-9]+|theme|thema|titelsong|titeltrack|tune|anthem|tribute|g[eé]n[eé]rique|soundtrack|titelnummer)\b", re.I)


def ondertitel_tussen_haken(titel: str) -> str:
    """"Titel - Sub" -> "Titel (Sub)", alleen bij een echte ondertitel."""
    if not titel or " - " not in titel:
        return titel
    kop, _, staart = titel.partition(" - ")
    # Het streepje moet buiten haken staan; in "Savage Love (Laxed - Siren
    # Beat)" hoort het bij de haak en blijft alles zoals het is.
    if kop.count("(") != kop.count(")"):
        return titel
    if not kop.strip() or not _ONDERTITELWOORD.search(staart):
        return titel
    # Nog een streepje in de staart wordt een spatie: "DJ Fle - Minisiren
    # Remix" leest tussen haken als "DJ Fle Minisiren Remix".
    staart = staart.replace(" - ", " ").strip()
    if staart.startswith("(") and staart.endswith(")"):
        staart = staart[1:-1]
    return f"{kop.strip()} ({staart})"


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
        jaren = [r[0] for r in con.execute(
            "SELECT DISTINCT jaar FROM noteringen WHERE lijst=? AND artiest=?"
            " AND titel=?", (fout["lijst"], oud_a, oud_t))]
        cursor = con.execute(
            "UPDATE noteringen SET artiest=?, titel=? WHERE lijst=? AND"
            " artiest=? AND titel=?",
            (nieuw_a, nieuw_t, fout["lijst"], oud_a, oud_t))
        if not cursor.rowcount:
            continue
        for jaar in jaren:
            db.markeer_te_bouwen(con, lijst=fout["lijst"], jaar=jaar,
                                 reden="leestekens")
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


def _leestekens(naam: str) -> int:
    """Hoeveel leestekens staan erin?

    Alleen zinnig bij titels. Een weggelaten leesteken is een slordigheid --
    "Dont Speak", "Beggin", "Hello Goodbye", "Help Me Rhonda" -- terwijl een
    band zich wél bewust zonder kan schrijven: Shakespears Sister en Dexys
    Midnight Runners hebben er echt geen apostrof. Vandaar dat dit bij een
    artiestnaam niet meetelt en bij een titel wel.

    Alleen zinsleestekens: komma, apostrof, vraag- en uitroepteken. "Hello,
    Goodbye" en "Reach Out, I'll Be There" verloren hun komma eerst van de
    meerderheid, en dat waren de goede titels.

    Streepjes, haken en punten tellen NIET mee. Die zijn even vaak een
    bronversiering als een echt onderdeel -- "Paperback-Writer" heet gewoon
    "Paperback Writer" -- en daar is de meerderheid een beter oordeel dan een
    telling.
    """
    return sum(naam.count(teken) for teken in ",'?!")


def meerderheidsnaam(namen: dict[str, int], *, leestekens: bool = False) -> str:
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
    # Een naam die volledig uit kleine letters bestaat doet niet mee zolang er
    # een alternatief met hoofdletters is. Anders wint "where are we now?" van
    # "Where Are We Now" op het vraagteken, en dan ruil je de ene fout voor de
    # andere.
    keuzes = {n: a for n, a in namen.items() if n != n.lower()} or namen

    def rangschik(paar):
        naam, aantal = paar
        return (_accenten(naam), _leestekens(naam) if leestekens else 0,
                naam != naam.lower(), aantal)

    return max(keuzes.items(), key=rangschik)[0]


def bewaar_artiestnaam(con: sqlite3.Connection, sleutel: str, naam: str,
                       bron: str) -> None:
    con.execute(
        "INSERT OR REPLACE INTO artiestnamen (sleutel, naam, bron, aangemaakt)"
        " VALUES (?,?,?,?)",
        (sleutel, naam, bron, datetime.now().isoformat(timespec="seconds")))


def bewaar_titel(con: sqlite3.Connection, sleutel: str, naam: str,
                 bron: str) -> None:
    con.execute(
        "INSERT OR REPLACE INTO titelnamen (sleutel, naam, bron, aangemaakt)"
        " VALUES (?,?,?,?)",
        (sleutel, naam, bron, datetime.now().isoformat(timespec="seconds")))


def titelvarianten(con: sqlite3.Connection) -> dict[str, list]:
    """Nummers die onder meer dan één titel in de database staan.

    Dezelfde indeling als bij de artiesten. "Beggin" tegen "Beggin'" is een
    tekenkwestie; "Kronenburg Park (Ga Die Wereld Uit)" tegen "Kronenburg Park -
    Ga Die Wereld Uit" is dat niet, want daar verschilt de opbouw en niet alleen
    de spelling.
    """
    per_sleutel: dict[str, dict[str, int]] = {}
    for r in con.execute("SELECT sleutel, titel, COUNT(*) n FROM noteringen"
                         " GROUP BY sleutel, titel"):
        titels = per_sleutel.setdefault(r["sleutel"], {})
        titels[r["titel"]] = titels.get(r["titel"], 0) + r["n"]

    bakken: dict[str, list] = {"tekens": [], "anders": []}
    for sleutel, titels in per_sleutel.items():
        if len(titels) < 2:
            continue
        kale = {_kaal(_zonder_bronrommel(t)) for t in titels}
        soort = "tekens" if len(kale) == 1 else "anders"
        bakken[soort].append((sleutel, dict(
            sorted(titels.items(), key=lambda p: -p[1]))))
    return bakken


# top40.nl schrijft bij een EP of album met een leadtrack de uitgave voor het
# nummer, met een spatie-dubbelepunt-spatie ertussen:
#     ">Abort, Retry, Fail?_ : Your Woman"       (White Town, 1997)
#     "Ballad Of The Streets EP : Belfast Child" (Simple Minds, 1989)
#     "Live! : Roll Over Lay Down"               (Status Quo, 1975)
# De andere lijsten schrijven gewoon het nummer, en dan valt zo'n notering in
# tweeen: Your Woman stond tien keer onder de lange titel en twee keer onder de
# korte, met een aparte sleutel en verdeelde punten.
_UITGAVE = re.compile(r"^.+? : (?=.)")


def uitgave_en_nummer(con: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """Titels van de vorm "uitgave : nummer". Geeft (sleutel, oud, nummer).

    De dubbelepunt moet spaties om zich heen hebben; zonder die eis sneuvelt
    "Titel: ondertitel" en dat is een andere vorm.
    """
    uit = []
    for r in con.execute("SELECT DISTINCT sleutel, titel FROM noteringen"
                         " WHERE titel LIKE '% : %'"):
        kort = _UITGAVE.sub("", r["titel"], count=1)
        if kort and kort != r["titel"]:
            uit.append((r["sleutel"], r["titel"], kort))
    return uit


def spatievarianten(con: sqlite3.Connection) -> list[tuple[str, list, str]]:
    """Nummers die identiek zijn zodra je de spaties weglaat.

    "Rock And Rollmusic" (top40.nl) tegen "Rock And Roll Music" (de andere
    lijsten), "Toofunky" tegen "Too Funky", "Itsnogood" tegen "It's No Good".
    Dat zijn geen twee nummers maar twee schrijfwijzen, met twee sleutels en dus
    verdeelde punten.

    Hier wint niet de meerderheid maar **de variant met de meeste spaties**. Een
    spatie raakt weg bij het overtypen; er komt er zelden een bij. Geeft
    (doelsleutel, [andere sleutels], titel).
    """
    aantal: dict[str, int] = {}
    titel: dict[str, str] = {}
    for r in con.execute("SELECT sleutel, titel, COUNT(*) n FROM noteringen"
                         " GROUP BY sleutel"):
        aantal[r["sleutel"]] = r["n"]
        titel[r["sleutel"]] = r["titel"]

    zonder: dict[str, list[str]] = {}
    for sleutel in aantal:
        zonder.setdefault(sleutel.replace(" ", ""), []).append(sleutel)

    uit = []
    for leden in zonder.values():
        if len(leden) < 2:
            continue
        doel = max(leden, key=lambda s: (titel[s].count(" "), aantal[s]))
        uit.append((doel, [s for s in leden if s != doel], titel[doel]))
    return uit


# --- 4. dubbele A-kanten ---------------------------------------------------

_KANT = " ; "


def splits_kanten(artiest: str, titel: str) -> list[tuple[str, str]]:
    """Een dubbele A-kant uit elkaar halen. Geen puntkomma -> één paar terug.

    top40.nl zet de twee kanten van één single in één regel, gescheiden door een
    puntkomma: "No Reply ; Rock And Roll Music". Het zijn twee nummers die
    allebei gedraaid werden en allebei de lijst haalden, en voor een DJ zijn het
    dus ook twee nummers.

    Staat er ook in de artiest een puntkomma en zijn het er evenveel, dan horen
    ze bij elkaar: "De Dijk ; The Scene" met "Iedereen Is Van De Wereld ; Nieuwe
    Laarzen" levert De Dijk bij het eerste en The Scene bij het tweede. Klopt
    het aantal niet, dan krijgen beide kanten de hele artiestnaam -- dat is
    vaker een samenwerking dan een tweede uitvoerende.
    """
    if _KANT not in (titel or ""):
        return [(artiest, titel)]
    titels = [t.strip() for t in titel.split(_KANT)]
    artiesten = [a.strip() for a in (artiest or "").split(_KANT)]
    if len(artiesten) != len(titels):
        artiesten = [artiest] * len(titels)
    return [(a, t) for a, t in zip(artiesten, titels) if t]


# De schuine streep doet in deze gegevens twee dingen tegelijk, en ze zien er
# hetzelfde uit:
#
#   "Nini Rosso / Heinz Schachtner" + "Il Silenzio / Abschiedsmelodie"
#       Twee artiesten, twee versies van hetzelfde nummer, samen op een plek.
#       Dat was in de jaren zestig gewoon: een buitenlandse hit en de
#       Nederlandse cover noteerden samen. Dit hoort gesplitst te worden.
#
#   "Lil Nas X / Lil Nas X feat. Billy Ray Cyrus" + "Old Town Road / Old Town
#    Road - Remix"
#       Een notering die halverwege is hernoemd omdat de remix het overnam.
#       Een doorlopende notering, en splitsen zou er twee halve van maken.
#
# Het verschil: bij een hernoeming gaat het om dezelfde act, en dan delen de
# twee namen woorden. Insluiting ("zit de een in de ander") is niet genoeg --
# top40.nl kapt lange namen af, en "Alderliefste met Ramses Shaff.." bevat
# "Ramses Shaffy" dus niet.
_ONBEDUIDEND = {"the", "de", "het", "een", "en", "met", "and", "with", "&",
                "ft", "feat", "van", "der", "los", "las", "les"}


def _woorden(naam: str) -> set:
    from .normalize import normaliseer

    return {w for w in normaliseer(naam).split() if w not in _ONBEDUIDEND}


def zelfde_act(delen: list[str]) -> bool:
    """Gaat het om dezelfde artiest, anders geschreven?

    Zo ja, dan is de schuine streep een hernoeming en geen tweede versie.
    """
    woordsets = [_woorden(d) for d in delen]
    for i, eerste in enumerate(woordsets):
        for tweede in woordsets[i + 1:]:
            if eerste & tweede:
                return True
    return False


def versies_op_een_plek(con: sqlite3.Connection,
                        lijst: str = "top40") -> list[dict]:
    """Noteringen waarin twee artiesten met twee titels een plek delen.

    Alleen als artiest en titel evenveel delen hebben -- anders is niet te
    zeggen welke titel bij welke artiest hoort -- en alleen als het echt
    verschillende acts zijn.
    """
    uit = []
    for r in con.execute(
            "SELECT id, lijst, jaar, week, positie, artiest, titel, sleutel,"
            " label, weken_genoteerd, vorige_positie, site_status, uitjaar"
            " FROM noteringen WHERE lijst=? AND titel LIKE ? AND artiest LIKE ?",
            (lijst, "% / %", "% / %")):
        artiesten = [a.strip() for a in r["artiest"].split(" / ")]
        titels = [t.strip() for t in r["titel"].split(" / ")]
        if len(artiesten) != len(titels) or zelfde_act(artiesten):
            continue
        uit.append({"rij": dict(r),
                    "kanten": [(a, t) for a, t in zip(artiesten, titels)]})
    return uit


def dubbele_a_kanten(con: sqlite3.Connection) -> list[dict]:
    """Alle noteringen die uit twee nummers bestaan."""
    uit = []
    for r in con.execute(
            "SELECT id, lijst, jaar, week, positie, artiest, titel, sleutel,"
            " label, weken_genoteerd, vorige_positie, site_status, uitjaar"
            " FROM noteringen WHERE titel LIKE ?", (f"%{_KANT}%",)):
        kanten = splits_kanten(r["artiest"], r["titel"])
        if len(kanten) > 1:
            uit.append({"rij": dict(r), "kanten": kanten})
    return uit


def corrigeer_nummer(con: sqlite3.Connection, sleutel: str, *,
                     artiest: str | None = None, titel: str | None = None,
                     reden: str = "met de hand vastgesteld") -> dict:
    """Zet artiest en/of titel van één nummer goed, overal tegelijk.

    Het gereedschap voor een correctie die uit een bron komt in plaats van uit
    een regel. top40.nl zet met /// twee schrijfwijzen van dezelfde notering
    achter elkaar -- "Ella///Ella (TROS Tune)" -- en welke van de twee de goede
    is, is een vraag aan een catalogus.

    Doet meteen alles wat erbij hoort: de sleutel opnieuw berekenen, een alias
    van de oude naar de nieuwe zodat een herberekening het niet terugdraait, de
    naam vastleggen zodat de vrijdagrun het niet terugdraait, de jaargangen
    markeren voor de herbouw, en het geheel in `wijzigingen`.
    """
    from .normalize import sleutel_van

    huidig = con.execute(
        "SELECT artiest, titel FROM noteringen WHERE sleutel=? LIMIT 1",
        (sleutel,)).fetchone()
    if not huidig:
        raise LookupError(f"geen noteringen met sleutel {sleutel!r}")
    nieuwe_artiest = artiest if artiest is not None else huidig["artiest"]
    nieuwe_titel = titel if titel is not None else huidig["titel"]
    nieuwe_sleutel = sleutel_van(nieuwe_artiest, nieuwe_titel)

    db.markeer_te_bouwen(con, sleutels=[sleutel], reden="correctie")
    aantal = con.execute(
        "UPDATE noteringen SET artiest=?, titel=?, sleutel=? WHERE sleutel=?",
        (nieuwe_artiest, nieuwe_titel, nieuwe_sleutel, sleutel)).rowcount

    # De naamregels van de OUDE sleutel moeten weg. Laat je ze staan, dan
    # stempelt `pas_titels_toe` bij het eerstvolgende opschonen de oude naam
    # er weer overheen -- zo is een splitsing van 3JS een keer stilletjes
    # teruggedraaid door de eigen huishouding.
    con.execute("DELETE FROM titelnamen WHERE sleutel=?", (sleutel,))
    if nieuwe_sleutel != sleutel:
        con.execute(
            "INSERT OR REPLACE INTO aliases (van, naar, opmerking, aangemaakt)"
            " VALUES (?,?,?,?)",
            (sleutel, nieuwe_sleutel, reden,
             datetime.now().isoformat(timespec="seconds")))
    if artiest is not None:
        bewaar_artiestnaam(con, nieuwe_sleutel.split("|", 1)[0],
                           nieuwe_artiest, "hand")
    if titel is not None:
        bewaar_titel(con, nieuwe_sleutel, nieuwe_titel, "hand")
    con.execute(
        "INSERT INTO wijzigingen (tijdstip, soort, verwijst, veld, oud, nieuw,"
        " reden) VALUES (?,?,?,?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"), "correctie", sleutel,
         "artiest+titel", f"{huidig['artiest']} - {huidig['titel']}",
         f"{nieuwe_artiest} - {nieuwe_titel}", reden))
    con.commit()
    return {"noteringen": aantal, "sleutel": nieuwe_sleutel}


def splits_nummer(con: sqlite3.Connection, sleutel: str,
                  kanten: list[tuple[str, str]],
                  reden: str = "met de hand vastgesteld") -> dict:
    """Maak van één notering meerdere, elk met een eigen artiest en titel.

    Het handmatige tegenhangertje van `splits_versies`, voor de gevallen die
    geen regel halen. "Kom Naar Kaïro" stond in 1969 als
    "Marijke Mulder///Mien Smulders" in de Tipparade: twee zangeressen, dezelfde
    titel, één plek. Automatisch is dat niet te onderscheiden van een hernoemde
    notering -- "The Source///The Course" ziet er precies zo uit en is er wél
    een -- dus dat oordeel komt van buiten.

    Zelfde afspraak als altijd: de positie telt één keer, dus elke kant krijgt
    de punten van die plek.
    """
    from .normalize import sleutel_van

    rijen = list(con.execute(
        "SELECT id, lijst, jaar, week, positie, artiest, titel, label,"
        " weken_genoteerd, vorige_positie, site_status, uitjaar"
        " FROM noteringen WHERE sleutel=?", (sleutel,)))
    if not rijen:
        raise LookupError(f"geen noteringen met sleutel {sleutel!r}")

    db.markeer_te_bouwen(con, sleutels=[sleutel], reden="splitsing")
    con.execute("DELETE FROM titelnamen WHERE sleutel=?", (sleutel,))
    con.execute("DELETE FROM aliases WHERE naar=?", (sleutel,))
    eerste, rest = kanten[0], kanten[1:]
    nieuw_aantal = 0
    for rij in rijen:
        con.execute(
            "UPDATE noteringen SET artiest=?, titel=?, sleutel=?, dubbele_a=1"
            " WHERE id=?",
            (eerste[0], eerste[1], sleutel_van(*eerste), rij["id"]))
        for artiest, titel in rest:
            con.execute(
                "INSERT INTO noteringen (lijst, jaar, week, positie, titel,"
                " artiest, label, weken_genoteerd, vorige_positie, site_status,"
                " sleutel, uitjaar, dubbele_a)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)",
                (rij["lijst"], rij["jaar"], rij["week"], rij["positie"], titel,
                 artiest, rij["label"], rij["weken_genoteerd"],
                 rij["vorige_positie"], rij["site_status"],
                 sleutel_van(artiest, titel), rij["uitjaar"]))
            nieuw_aantal += 1
    con.execute(
        "INSERT INTO wijzigingen (tijdstip, soort, verwijst, veld, oud, nieuw,"
        " reden) VALUES (?,?,?,?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"), "versies", sleutel,
         "artiest+titel", f"{rijen[0]['artiest']} - {rijen[0]['titel']}",
         " + ".join(f"{a} - {t}" for a, t in kanten), reden))
    con.commit()
    return {"noteringen": len(rijen), "nieuw": nieuw_aantal}


def splits_versies(con: sqlite3.Connection, lijst: str = "top40") -> dict:
    """Maak van elke gedeelde plek net zo veel noteringen als er versies zijn.

    Zelfde afspraak als bij de dubbele A-kant: de positie telt een keer, dus
    elke versie krijgt de punten van die ene plek en daarmee hetzelfde totaal.

    Dit zit met opzet NIET in het schrijfpad. De vorm komt na 1972 niet meer
    voor als twee versies, maar wel als hernoemde notering ("Old Town Road /
    Old Town Road - Remix"), en die mag juist nooit gesplitst worden. Een regel
    die bij het ophalen meedraait zou dat vroeg of laat fout doen.
    """
    from .normalize import sleutel_van

    gevallen = versies_op_een_plek(con, lijst)
    verslag = {"noteringen": 0, "nieuw": 0, "nummers": set()}
    for geval in gevallen:
        rij, kanten = geval["rij"], geval["kanten"]
        verslag["nummers"].add(rij["sleutel"])
        con.execute("DELETE FROM titelnamen WHERE sleutel=?", (rij["sleutel"],))
        db.markeer_te_bouwen(con, lijst=rij["lijst"], jaar=rij["jaar"],
                             reden="versies op een plek")
        eerste, rest = kanten[0], kanten[1:]
        con.execute(
            "UPDATE noteringen SET artiest=?, titel=?, sleutel=?, dubbele_a=1"
            " WHERE id=?",
            (eerste[0], eerste[1], sleutel_van(*eerste), rij["id"]))
        verslag["noteringen"] += 1
        for artiest, titel in rest:
            con.execute(
                "INSERT INTO noteringen (lijst, jaar, week, positie, titel,"
                " artiest, label, weken_genoteerd, vorige_positie, site_status,"
                " sleutel, uitjaar, dubbele_a)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)",
                (rij["lijst"], rij["jaar"], rij["week"], rij["positie"], titel,
                 artiest, rij["label"], rij["weken_genoteerd"],
                 rij["vorige_positie"], rij["site_status"],
                 sleutel_van(artiest, titel), rij["uitjaar"]))
            verslag["nieuw"] += 1
        con.execute(
            "INSERT INTO wijzigingen (tijdstip, soort, verwijst, veld, oud,"
            " nieuw, reden) VALUES (?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), "versies",
             f"{rij['lijst']} {rij['jaar']} wk {rij['week']} #{rij['positie']}",
             "artiest+titel", f"{rij['artiest']} - {rij['titel']}",
             " + ".join(f"{a} - {t}" for a, t in kanten),
             "twee of meer versies op een plek, elk als eigen notering"))
    con.commit()
    verslag["nummers"] = len(verslag["nummers"])
    return verslag


def splits_dubbele_a_kanten(con: sqlite3.Connection) -> dict:
    """Maak van elke dubbele A-kant twee noteringen op dezelfde positie.

    De positie telt één keer: beide nummers krijgen de punten van die ene plek,
    en dus allebei hetzelfde totaal. Dat is precies wat de officiële jaarlijst
    de single toekent -- er staat er bij ons alleen twee keer een, op dezelfde
    hoogte, in plaats van één regel met een puntkomma.

    Het schema kan dit al aan: twee noteringen op dezelfde positie in dezelfde
    week bestonden al bij de Tipparade, die echte gedeelde posities kent.
    """
    from .normalize import sleutel_van

    gevallen = dubbele_a_kanten(con)
    verslag = {"noteringen": 0, "nieuw": 0}
    for geval in gevallen:
        rij, kanten = geval["rij"], geval["kanten"]
        eerste, rest = kanten[0], kanten[1:]
        db.markeer_te_bouwen(con, lijst=rij["lijst"], jaar=rij["jaar"],
                             reden="dubbele A-kant")
        con.execute(
            "UPDATE noteringen SET artiest=?, titel=?, sleutel=?, dubbele_a=1"
            " WHERE id=?",
            (eerste[0], eerste[1], sleutel_van(*eerste), rij["id"]))
        verslag["noteringen"] += 1
        for artiest, titel in rest:
            con.execute(
                "INSERT INTO noteringen (lijst, jaar, week, positie, titel,"
                " artiest, label, weken_genoteerd, vorige_positie, site_status,"
                " sleutel, uitjaar, dubbele_a)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)",
                (rij["lijst"], rij["jaar"], rij["week"], rij["positie"], titel,
                 artiest, rij["label"], rij["weken_genoteerd"],
                 rij["vorige_positie"], rij["site_status"],
                 sleutel_van(artiest, titel), rij["uitjaar"]))
            verslag["nieuw"] += 1
        con.execute(
            "INSERT INTO wijzigingen (tijdstip, soort, verwijst, veld, oud,"
            " nieuw, reden) VALUES (?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), "dubbele a-kant",
             f"{rij['lijst']} {rij['jaar']} wk {rij['week']} #{rij['positie']}",
             "titel", f"{rij['artiest']} - {rij['titel']}",
             " + ".join(f"{a} - {t}" for a, t in kanten),
             "twee nummers op een positie, elk als eigen notering"))
    con.commit()
    return verslag


def geleende_hoofdletters(con: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """Titels die helemaal klein zijn terwijl een ander nummer ze wél schrijft.

    Sandra van Nieuwland staat met "beggin'" in de Top 40 en verder niemand,
    dus binnen dat nummer valt er niets te kiezen. Maar Madcon, Maneskin, The
    Four Seasons en Timebox staan er allemaal met "Beggin'". Dan is de
    hoofdletter geen smaak maar een gegeven dat elders in dezelfde database
    staat.

    Alleen van klein naar groot, en alleen als de letters verder exact gelijk
    zijn. Geeft (sleutel, oud, nieuw).
    """
    met_hoofdletter: dict[str, dict[str, int]] = {}
    klein: dict[str, list[tuple[str, str]]] = {}
    for r in con.execute("SELECT sleutel, titel, COUNT(*) n FROM noteringen"
                         " GROUP BY sleutel, titel"):
        titel = r["titel"]
        if titel != titel.lower():
            vormen = met_hoofdletter.setdefault(titel.lower(), {})
            vormen[titel] = vormen.get(titel, 0) + r["n"]
        else:
            klein.setdefault(titel, []).append((r["sleutel"], titel))

    uit = []
    for kleine_titel, gevallen in klein.items():
        vormen = met_hoofdletter.get(kleine_titel)
        if not vormen:
            continue
        goed = max(vormen.items(), key=lambda p: p[1])[0]
        uit += [(sleutel, oud, goed) for sleutel, oud in gevallen]
    return uit


def pas_titels_toe(con: sqlite3.Connection) -> dict:
    """Schrijf de vastgestelde titel naar alle noteringen die afwijken."""
    tabel = {r["sleutel"]: r["naam"]
             for r in con.execute("SELECT sleutel, naam FROM titelnamen")}
    verslag = {"nummers": 0, "noteringen": 0}
    for r in list(con.execute(
            "SELECT sleutel, titel, COUNT(*) n FROM noteringen"
            " GROUP BY sleutel, titel")):
        goed = tabel.get(r["sleutel"])
        if not goed or goed == r["titel"]:
            continue
        db.markeer_te_bouwen(con, sleutels=[r["sleutel"]], reden="titel")
        cursor = con.execute(
            "UPDATE noteringen SET titel=? WHERE sleutel=? AND titel=?",
            (goed, r["sleutel"], r["titel"]))
        verslag["noteringen"] += cursor.rowcount
        verslag["nummers"] += 1
        con.execute(
            "INSERT INTO wijzigingen (tijdstip, soort, verwijst, veld, oud,"
            " nieuw, reden) VALUES (?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), "titelnaam",
             r["sleutel"], "titel", r["titel"], goed,
             f"eenduidige schrijfwijze ({cursor.rowcount} noteringen)"))
    con.commit()
    return verslag


def verzeker_aliassen(con: sqlite3.Connection) -> dict:
    """Zorg dat een hernoemde artiest zijn sleutel niet kwijtraakt.

    Hier zit een valkuil die pas opvalt als je hem al hebt getrapt. De sleutel
    wordt uit de naam berekend, en `artiestnamen` verandert die naam. "ACDC"
    werd "AC/DC", en de sleutel die je daaruit berekent is "ac dc" en niet
    "acdc" -- dus de eerstvolgende herberekening trok de zojuist samengevoegde
    artiest weer uit elkaar.

    De oplossing is een alias van de nieuwe berekende sleutel naar de
    vastgestelde. Daarmee is een herberekening onschadelijk: hij komt altijd op
    dezelfde sleutel uit, hoe vaak je hem ook draait.
    """
    from .normalize import artiestsleutel

    verslag = {"aliassen": 0, "hersteld": 0}
    for r in list(con.execute("SELECT sleutel, naam FROM artiestnamen")):
        doel = artiestsleutel(r["naam"])
        if doel == r["sleutel"]:
            continue
        # De sleutel volgt de naam, niet omgekeerd. De andere richting lijkt
        # ook te werken tot er een verouderde naamregel blijkt te staan: er
        # stond er een op "bl f", de kapotte sleutel van voor de letterregel,
        # en die trok Bløf daar zo weer naartoe.
        for (oud,) in list(con.execute(
                "SELECT DISTINCT sleutel FROM noteringen WHERE sleutel LIKE ?",
                (f"{r['sleutel']}|%",))):
            con.execute(
                "INSERT OR REPLACE INTO aliases (van, naar, opmerking,"
                " aangemaakt) VALUES (?,?,?,?)",
                (oud, f"{doel}|{oud.split('|', 1)[1]}",
                 "vastgestelde schrijfwijze levert een andere sleutel op",
                 datetime.now().isoformat(timespec="seconds")))
            verslag["aliassen"] += 1
        cursor = con.execute(
            "UPDATE noteringen SET sleutel = ? || substr(sleutel, ?)"
            " WHERE sleutel LIKE ?",
            (doel, len(r["sleutel"]) + 1, f"{r['sleutel']}|%"))
        verslag["hersteld"] += cursor.rowcount
        # En de naamregel zelf op de nieuwe sleutel zetten, anders doet hij het
        # de volgende keer opnieuw.
        con.execute("DELETE FROM artiestnamen WHERE sleutel=?", (r["sleutel"],))
        con.execute(
            "INSERT OR REPLACE INTO artiestnamen (sleutel, naam, bron,"
            " aangemaakt) VALUES (?,?,?,?)",
            (doel, r["naam"], "sleutel volgt de naam",
             datetime.now().isoformat(timespec="seconds")))
    con.commit()
    return verslag


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
        db.markeer_te_bouwen(con, sleutels=[r["sleutel"]],
                             reden="artiestnaam")
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
