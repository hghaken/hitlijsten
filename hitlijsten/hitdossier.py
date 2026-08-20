"""Een jaarlijkse lijst ophalen bij hitdossier-online.nl.

WAAROM EEN TWEEDE BRON
----------------------
De jaarlijkse lijsten komen als matrix van Music Datastats. Eén lijst staat
daar niet in: de 80's-lijst van Radio Veronica. Die loopt sinds 2005 en heeft
in die tijd vier namen en vier lengtes gehad -- 80's Top 880 (2005-2013),
Top 750 (2014-2016), Top 500 (2017-2019) en sinds 2024 de Top 1000 van de 80s.
hitdossier-online.nl heeft alle edities compleet, met per notering ook het
uitgavejaar.

Het archief voert ze als één reeks (`veronica80s`). Dat is de hele winst: van
*Purple Rain* zie je zo één geschiedenis van achttien edities -- van 24 in 2005
naar 1 in 2026 -- in plaats van vier losse van drie.

DE PAGINA LEZEN
---------------
Elke notering staat in twee `<tr>`'s: de eerste met positie, artiest en jaar,
de tweede met de titel. Twee valkuilen:

* De **positiecel heeft geen vaste klasse** -- hij is gekleurd naar de
  beweging (`_zwart`, `_stip`, `_superstip`, `_re` voor een terugkeer, `_nw`
  voor een nieuwkomer). Er wordt daarom geknipt op de artiestencel, en de
  positie is de eerste `th` die geen "vorige" (`_vw`) of "aantal" (`_aw`) is.
* De **eerste editie van elke naam** (2005, 2014, 2017, 2024) mist die twee
  kolommen helemaal, en een nieuwkomer heeft ze leeg.

Welke edities er zijn wordt niet vastgelegd maar van de overzichtspagina
gelezen. Zo komt de editie van volgend januari er vanzelf bij.

DE SCHRIJFWIJZE IS DE ECHTE KLUS
--------------------------------
Hitdossier voert een eigen huisstijl: het lidwoord gaat eraf (*Cure*, en ook
Nederlands -- *Dijk* is De Dijk), namen krijgen kapitalen (*Chris De Burgh*) en
leestekens wijken af (*10cc*, *Salt-n-Pepa*). Sluit dat niet aan op het
archief, dan krijgt hetzelfde nummer twee sleutels en loopt de historie niet
door. `vertaaltabel()` lost dat in drie lagen op -- lidwoord, losse vorm, en
tot slot `MET_DE_HAND` voor de credits die geen van beide vindt.
"""
from __future__ import annotations

import csv
import re
import sqlite3
import time
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from html import unescape
from pathlib import Path

from .config import CACHE_DIR, DATA_DIR
from .normalize import sleutel_van
from .opschonen import (eenduidige_credit, komma_is_samenwerking,
                        met_is_samenwerking, ondertitel_tussen_haken,
                        schoon_tekst, x_is_samenwerking)

__all__ = ["BASIS", "edities", "haal_editie", "alle_edities", "vertaaltabel",
           "schrijf_matrix"]

BASIS = "https://www.hitdossier-online.nl"
# Onder welke namen een lijst daar staat. De volgorde doet er niet toe; welke
# jaren er per naam zijn wordt van de site zelf gelezen.
#
# Vijf namen voor één reeks. Wat er wel en niet bij hoort is niet op de naam
# beslist maar op de inhoud: elke notering draagt zijn uitgavejaar, dus je kunt
# tellen.
#
# De **Back To The 80s Top 880 (2020)** is de Top 880 onder een andere naam:
# 880 noteringen, voor 96% jaren 80, en Purple Rain / Thriller / Under Pressure
# bovenaan. Die hoort er dus in.
#
# Twee lijsten uit dezelfde jaren staan er bewust NIET in:
#
# * **De 80s & 90s Top 890 (2020, 2021)** is een andere lijst. Maar 57% jaren
#   80, 355 noteringen uit de jaren 90, en Thunderstruck op 1. Het bewijs zit
#   in 2020 zelf: toen zond Veronica ze allebei uit, de 890 in juni en de 880
#   in augustus.
# * De **80s Top 100 (2022, 2023)** is inhoudelijk wél deze lijst (97 en 99%
#   jaren 80), maar met honderd noteringen te kort om als editie mee te tellen
#   naast lijsten van 500 tot 1000: de editieteller en het verloop per nummer
#   zouden er alleen maar schever van worden.
#
# 2021, 2022 en 2023 blijven daardoor leeg in deze reeks.
SLUGS = {
    "veronica80s": (
        "radio-veronica-80s-top-880",
        "radio-veronica-80s-top-750",
        "radio-veronica-80s-top-500",
        "radio-veronica-back-to-the-80s-top-880",
        "radio-veronica-top-1000-van-de-80s",
    ),
}
# Credits die het archief onder een andere naam voert en die geen enkele
# automatische vergelijking vindt. Elk geval is nagelopen door de titel in het
# archief op te zoeken; gekozen is de credit met de meeste noteringen, zodat de
# historie op de langste reeks aansluit. Twee ervan verraadden een ligatuur die
# het archief wel gebruikt en hitdossier niet.
MET_DE_HAND = {
    "veronica80s": {
        "Orchestral Manoeuvres In The Dark": "Orchestral Manœuvres In The Dark",
        "George Michael": "George Michæl",
        "Scorpions": "Scorpions (du)",
        "David Bowie & The Pat Metheny Group": "David Bowie & Pat Metheny Group",
        "Philip Bailey & Phil Collins": "Phil Collins & Philip Bailey",
        "Communards & Sarah Jane Morris": "Communards with Sarah Jane Morris",
        "Cliff Richard, The Young Ones & Hank Marvin":
            "Cliff Richard & The Young Ones",
        "Elvis Costello & The Attractions": "Elvis Costello",
        "John Lennon & Yoko Ono": "John Lennon",
        "Zucchero": "Zucchero Sugar Fornaciari",
        "Buster Poindexter & His Banshees Of Blue": "Buster Poindexter",
        "Eric Clapton & Tina Turner": "Eric Clapton with Tina Turner",
        "Stevie Nicks, Tom Petty & The Heartbreakers":
            "Stevie Nicks with Tom Petty and The Heartbreakers",
    },
}
# Twee platen van dezelfde band staan in het archief onder twee credits, dus
# hier is de titel nodig om te weten welke.
MET_DE_HAND_PER_TITEL = {
    "veronica80s": {
        ("Wax", "Building A Bridge To Your Heart"): "Wax (1986)",
        ("Wax", "Right Between The Eyes"): "Wax (en)",
    },
}
# Titels die de losse vergelijking niet vindt omdat de bron er iets aan
# vastplakt. Hazes' plaat uit 1981 heet bij hitdossier "Zij Gelooft In Mij
# '81"; dat jaartal is hun manier om hem aan te duiden, geen andere opname --
# het archief kent hem ruim honderd keer als "Zij Gelooft In Mij".
MET_DE_HAND_TITELS = {
    "veronica80s": {
        ("André Hazes", "Zij Gelooft In Mij '81"): "Zij Gelooft In Mij",
    },
}

_JAARLINK = re.compile(r'href="(?P<slug>[a-z0-9-]+)-(?P<jaar>20[0-9]{2})"')
_ARTIEST = re.compile(r'<td class="_artiesten">')
# Alles behalve de twee kolommen die geen positie zijn.
_POSITIE = re.compile(r'<th class="(_(?!vw|aw)[a-z]+)"[^>]*>\s*([0-9]+)\s*</th>')


def _tekst(rauw: str) -> str:
    """De Spotify- en YouTube-links eraf; de naam blijft over."""
    return unescape(re.sub(r"<[^>]+>", " ", rauw)).strip()


def _cel(blok: str, klasse: str) -> str:
    m = re.search(rf'<(?:td|th) class="{klasse}"[^>]*>(.*?)</(?:td|th)>',
                  blok, re.S)
    return _tekst(m.group(1)) if m else ""


def _haal(pad_op_de_site: str, *, verversen: bool = False) -> str:
    """Haal een pagina op, met een kopie in de cache.

    Een editie van tien jaar terug verandert niet meer, en achttien pagina's
    van een halve megabyte hoef je niet elke keer opnieuw op te vragen.
    """
    kopie = CACHE_DIR / "hitdossier" / f"{pad_op_de_site}.html"
    if not verversen and kopie.exists() and kopie.stat().st_size > 20_000:
        return kopie.read_text(encoding="utf-8", errors="replace")
    verzoek = urllib.request.Request(f"{BASIS}/{pad_op_de_site}",
                                     headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(verzoek, timeout=45) as antwoord:
        h = antwoord.read().decode("utf-8", errors="replace")
    kopie.parent.mkdir(parents=True, exist_ok=True)
    kopie.write_text(h, encoding="utf-8")
    time.sleep(1.5)          # niet harder dan een bezoeker
    return h


def edities(lijst: str, *, verversen: bool = False) -> dict[int, str]:
    """Welke edities er zijn, als {jaar: pad op de site}.

    Niet vastgelegd maar van de overzichtspagina gelezen, zodat de editie van
    volgend januari er vanzelf bij komt. Het pad is meestal `slug-jaar`, maar
    een naam die maar één editie kende (Back To The 80s Top 880) heeft geen
    jaartal in de URL: dan is het de kale slug.
    """
    gevonden: dict[int, str] = {}
    for slug in SLUGS[lijst]:
        h = _haal(slug, verversen=verversen)
        for m in _JAARLINK.finditer(h):
            if m["slug"] == slug:
                gevonden[int(m["jaar"])] = f"{slug}-{m['jaar']}"
        # De overzichtspagina toont de editie die hij zelf is niet altijd in
        # zijn jaarlijst; het jaar in de titel vult dat aan.
        titel = re.search(r"<title>[^<]*editie (20[0-9]{2})", h)
        if titel:
            gevonden.setdefault(int(titel.group(1)), slug)
    return dict(sorted(gevonden.items()))


def haal_editie(pad_op_de_site: str, *,
                verversen: bool = False) -> list[dict]:
    """Eén editie: een regel per notering, in de volgorde van de pagina."""
    h = _haal(pad_op_de_site, verversen=verversen)
    grenzen = [m.start() for m in _ARTIEST.finditer(h)]
    rijen = []
    for i, start in enumerate(grenzen):
        # Terug tot het begin van de rij, want daar staat de positie.
        blok = h[h.rfind("<tr", 0, start):
                 grenzen[i + 1] if i + 1 < len(grenzen) else len(h)]
        m = _POSITIE.search(blok)
        if not m:
            continue
        rijen.append({
            "positie": int(m.group(2)),
            "beweging": m.group(1),
            "artiest": _cel(blok, "_artiesten"),
            "titel": _cel(blok, "_titel"),
            "uitjaar": _cel(blok, "_jaar"),
        })
    return rijen


def alle_edities(lijst: str, *, jaren: list[int] | None = None,
                 verversen: bool = False) -> dict[int, list[dict]]:
    """Alle edities van een lijst, of alleen de gevraagde jaren."""
    beschikbaar = edities(lijst, verversen=verversen)
    if jaren:
        ontbreekt = [j for j in jaren if j not in beschikbaar]
        if ontbreekt:
            raise ValueError(f"hitdossier heeft geen editie {ontbreekt} van "
                             f"{lijst}; beschikbaar: "
                             f"{sorted(beschikbaar)}")
        beschikbaar = {j: s for j, s in beschikbaar.items() if j in jaren}
    return {j: haal_editie(p, verversen=verversen)
            for j, p in beschikbaar.items()}


def controleer(per_jaar: dict[int, list[dict]]) -> list[str]:
    """Is elke editie een aaneengesloten 1..N zonder lege velden?"""
    klachten = []
    for jaar, rijen in per_jaar.items():
        if not rijen:
            klachten.append(f"{jaar}: geen enkele notering gelezen")
            continue
        posities = [r["positie"] for r in rijen]
        ontbreekt = sorted(set(range(1, max(posities) + 1)) - set(posities))
        if ontbreekt:
            klachten.append(f"{jaar}: {len(ontbreekt)} positie(s) ontbreken "
                            f"(o.a. {ontbreekt[:5]})")
        leeg = [r["positie"] for r in rijen
                if not r["artiest"] or not r["titel"]]
        if leeg:
            klachten.append(f"{jaar}: lege artiest of titel op {leeg[:5]}")
    return klachten


def _poets(artiest: str, titel: str) -> tuple[str, str]:
    """Dezelfde poets als de importeur, om de sleutel vooraf te kennen."""
    a = met_is_samenwerking(komma_is_samenwerking(
        x_is_samenwerking(eenduidige_credit(schoon_tekst(artiest)))))
    return a, ondertitel_tussen_haken(schoon_tekst(titel))


def _los(naam: str) -> str:
    """Alles weg wat alleen schrijfwijze is: kapitalen, leestekens, accenten."""
    plat = unicodedata.normalize("NFKD", naam.lower())
    plat = "".join(c for c in plat if not unicodedata.combining(c))
    for ligatuur, uit in (("æ", "ae"), ("œ", "oe"), ("ø", "o")):
        plat = plat.replace(ligatuur, uit)
    return re.sub(r"[^a-z0-9]", "", plat)


def vertaaltabel(con: sqlite3.Connection, lijst: str,
                 per_jaar: dict[int, list[dict]]) -> tuple[dict, dict]:
    """De brug tussen hitdossier en de archiefschrijfwijze.

    Geeft (artiesten, titels) terug: de eerste per naam, de tweede per
    (naam, titel). Bij de titels wordt bewust veel minder vertaald -- zie
    hieronder.
    """
    archief: Counter[str] = Counter()
    for a, n in con.execute("SELECT artiest, COUNT(*) FROM noteringen"
                            " GROUP BY artiest"):
        archief[a] = n
    # Een losse vorm kan meerdere archiefschrijfwijzen hebben; de meest
    # gebruikte wint, dat is de vastgestelde vorm.
    losse: dict[str, str] = {}
    for a, _ in archief.most_common():
        losse.setdefault(_los(a), a)

    met_de_hand = MET_DE_HAND.get(lijst, {})
    per_titel = MET_DE_HAND_PER_TITEL.get(lijst, {})
    artiesten: dict[str, str] = {}
    for naam in {r["artiest"] for rijen in per_jaar.values() for r in rijen}:
        if naam in met_de_hand:
            artiesten[naam] = met_de_hand[naam]
            continue
        kaal = _poets(naam, "x")[0]
        if archief.get(kaal):
            if kaal != naam:
                artiesten[naam] = kaal
            continue
        # Het weggelaten lidwoord is niet altijd Engels.
        for kandidaat in (f"The {kaal}", f"De {kaal}", f"Het {kaal}"):
            if archief.get(kandidaat):
                artiesten[naam] = kandidaat
                break
        else:
            artiesten[naam] = (losse.get(_los(kaal))
                               or losse.get(_los(f"The {kaal}")) or kaal)

    # De sleutel negeert hoofdletters en leestekens al: "Word Up" en "Word Up!"
    # komen vanzelf samen. Overnemen heeft dus alleen zin waar de sleutel écht
    # uiteenloopt -- meestal een spatie die er wel of niet staat, zoals
    # "Papa's Got A Brand New Pigbag" tegenover "Pig Bag". Een titel die
    # inhoudelijk verschilt ((Live), (Remix), (Part 2)) blijft staan zoals de
    # bron hem noemt: samenvoegen is een keuze voor de aliaslijst, niet voor
    # een script.
    bekend: dict[str, dict[str, str]] = defaultdict(dict)
    sleutels = set()
    for a, t in con.execute("SELECT DISTINCT artiest, titel FROM noteringen"):
        bekend[a].setdefault(_los(t), t)
        sleutels.add(sleutel_van(a, t))
    titels: dict[tuple[str, str], str] = {}
    for naam_ruw, titel_ruw in {(r["artiest"], r["titel"])
                                for rijen in per_jaar.values() for r in rijen}:
        naam = per_titel.get((naam_ruw, titel_ruw)) \
            or artiesten.get(naam_ruw, naam_ruw)
        a, t = _poets(naam, titel_ruw)
        if sleutel_van(a, t) in sleutels:
            continue
        anders = bekend.get(a, {}).get(_los(t))
        if anders and sleutel_van(a, _poets(naam, anders)[1]) in sleutels:
            titels[(naam, titel_ruw)] = anders
    titels.update(MET_DE_HAND_TITELS.get(lijst, {}))
    return artiesten, titels


def schrijf_matrix(con: sqlite3.Connection, lijst: str,
                   per_jaar: dict[int, list[dict]],
                   pad: Path | None = None) -> tuple[Path, dict]:
    """Zet de edities om in de matrix-CSV die `jaarlijks.importeer` leest.

    Het **uitgavejaar** komt uit het archief waar dat een waarde heeft. De
    bron noemt vaak het jaar van de plaat en het archief dat van de
    Nederlandse uitgave -- *Billie Jean* is bij Veronica 1982 (album
    *Thriller*) en hier 1983 -- en het archief is daar kritisch op nagelopen.
    Het jaar van de bron vult alleen aan wat het archief nog niet kent.
    """
    pad = pad or DATA_DIR / f"{lijst}.csv"
    jaren = sorted(per_jaar)
    artiesten, titels = vertaaltabel(con, lijst, per_jaar)
    per_titel = MET_DE_HAND_PER_TITEL.get(lijst, {})

    nummers: dict[str, dict] = {}
    botsingen = []
    for jaar in jaren:
        for r in per_jaar[jaar]:
            naam = per_titel.get((r["artiest"], r["titel"])) \
                or artiesten.get(r["artiest"], r["artiest"])
            titel = titels.get((naam, r["titel"]), r["titel"])
            a, t = _poets(naam, titel)
            sleutel = sleutel_van(a, t)
            n = nummers.setdefault(sleutel, {
                "artiest": naam, "titel": titel, "posities": {},
                "bronjaar": r["uitjaar"]})
            if jaar in n["posities"]:
                botsingen.append(f"{jaar}: {naam} — {titel} staat tweemaal "
                                 f"(#{n['posities'][jaar]} en #{r['positie']})")
            n["posities"][jaar] = int(r["positie"])

    eigen: dict[str, int] = {}
    for s, u in con.execute(
            "SELECT sleutel, uitjaar FROM noteringen WHERE uitjaar IS NOT NULL"
            " GROUP BY sleutel ORDER BY COUNT(*) DESC"):
        eigen.setdefault(s, u)
    uit_archief = 0
    for sleutel, n in nummers.items():
        if sleutel in eigen:
            n["uitjaar"] = eigen[sleutel]
            uit_archief += 1
        else:
            n["uitjaar"] = n["bronjaar"]

    bekende = {s for (s,) in con.execute(
        "SELECT DISTINCT sleutel FROM noteringen")}
    op_volgorde = sorted(nummers.values(),
                         key=lambda n: (min(n["posities"].values()),
                                        -len(n["posities"])))
    pad.parent.mkdir(parents=True, exist_ok=True)
    with pad.open("w", encoding="utf-8", newline="") as bestand:
        schrijver = csv.writer(bestand, delimiter=";")
        schrijver.writerow(["TotaalPositie", "Artiest", "Titel", "Uitjaar"]
                           + [str(j) for j in jaren])
        for i, n in enumerate(op_volgorde, start=1):
            schrijver.writerow([i, n["artiest"], n["titel"], n["uitjaar"]]
                               + [n["posities"].get(j, 0) for j in jaren])

    return pad, {
        "edities": jaren,
        "noteringen": sum(len(r) for r in per_jaar.values()),
        "nummers": len(nummers),
        "nieuw": sorted(
            (min(n["posities"].values()), n["artiest"], n["titel"])
            for s, n in nummers.items() if s not in bekende),
        "artiesten_vertaald": len(artiesten),
        "titels_vertaald": len(titels),
        "uitjaar_uit_archief": uit_archief,
        "botsingen": botsingen,
    }
