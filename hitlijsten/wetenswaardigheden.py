"""Wetenswaardigheden: tien ranglijsten uit tweeënzestig jaargangen Top 40.

Alles komt uit één doorloop over de noteringen van één lijst. Dat is bewust:
de meeste vragen ("hoe vaak kwam dit nummer terug?", "wat was de grootste sprong
in een week?") hebben de reeks per nummer op volgorde nodig, en die bouw je maar
één keer op.

DRIE DINGEN OM TE WETEN BIJ HET LEZEN
-------------------------------------
1. **Een samenwerking telt als een eigen artiest.** "Lady Gaga & Bruno Mars" is
   hier niet Lady Gaga én Bruno Mars. Uit elkaar trekken lijkt aantrekkelijk,
   maar dan sneuvelen Simon & Garfunkel en Earth, Wind & Fire ook, en dat zijn
   geen samenwerkingen maar namen. Liever een cijfer dat klopt met wat er op de
   lijst stond dan een cijfer dat mooier oogt.
2. **Een notering loopt over de jaargrens door.** De weken worden geteld langs
   de kalender van uitgezonden lijsten, niet per jaargang, dus "Last Christmas"
   telt december en januari als één aaneengesloten periode.
3. **De allereerste week telt niet als binnenkomst.** In week 1 van 1965 was de
   hele lijst nieuw; dat zegt niets over hoe hoog een nummer binnenkwam.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from .datums import als_tekst, vrijdag_van

__all__ = ["Blok", "verzamel"]

TOP = 10   # hoeveel regels per ranglijst


@dataclass
class Blok:
    """Eén ranglijst, klaar om te tonen."""

    sleutel: str          # ankernaam in de pagina
    titel: str
    uitleg: str
    kolommen: list[str]
    rijen: list[dict] = field(default_factory=list)


@dataclass
class _Nummer:
    """Wat we per nummer bijhouden tijdens de doorloop."""

    sleutel: str
    artiest: str = ""
    titel: str = ""
    # index in de kalender van uitgezonden weken -> beste positie die week
    posities: dict[int, int] = field(default_factory=dict)
    punten: int = 0
    jaren: set[int] = field(default_factory=set)
    punten_per_jaar: dict[int, int] = field(default_factory=dict)


def _lees(con: sqlite3.Connection, lijst: str) -> tuple[list[date], dict[str, _Nummer]]:
    """Alle noteringen van één lijst, per nummer op de kalender gelegd."""
    rijen = list(con.execute(
        "SELECT jaar, week, positie, artiest, titel, sleutel FROM noteringen"
        " WHERE lijst=? ORDER BY jaar, week, positie",
        (lijst,),
    ))
    if not rijen:
        return [], {}

    # De lengte van de lijst per week bepaalt de punten; die wisselt bij sommige
    # lijsten per jaargang, dus per week uit de data zelf halen.
    lengte: dict[date, int] = {}
    for r in rijen:
        datum = vrijdag_van(r["jaar"], r["week"])
        lengte[datum] = max(lengte.get(datum, 0), r["positie"])

    kalender = sorted(lengte)
    volgnummer = {datum: nr for nr, datum in enumerate(kalender)}

    nummers: dict[str, _Nummer] = {}
    for r in rijen:
        datum = vrijdag_van(r["jaar"], r["week"])
        nr = volgnummer[datum]
        n = nummers.get(r["sleutel"])
        if n is None:
            n = nummers[r["sleutel"]] = _Nummer(sleutel=r["sleutel"])
        # Laatste schrijfwijze wint; de rijen komen op volgorde binnen.
        n.artiest, n.titel = r["artiest"], r["titel"]
        n.jaren.add(r["jaar"])
        # Gedeelde posities: hetzelfde nummer kan twee keer in een week staan.
        # Dan telt de beste notering, en de week telt één keer.
        eerder = n.posities.get(nr)
        if eerder is None or r["positie"] < eerder:
            if eerder is not None:
                n.punten -= lengte[datum] - eerder + 1
                n.punten_per_jaar[r["jaar"]] -= lengte[datum] - eerder + 1
            n.posities[nr] = r["positie"]
            gewonnen = lengte[datum] - r["positie"] + 1
            n.punten += gewonnen
            n.punten_per_jaar[r["jaar"]] = n.punten_per_jaar.get(r["jaar"], 0) + gewonnen
    return kalender, nummers


def _reeksen(posities: dict[int, int]) -> list[list[int]]:
    """Splits de weken van een nummer in aaneengesloten periodes."""
    reeksen: list[list[int]] = []
    for nr in sorted(posities):
        if reeksen and nr == reeksen[-1][-1] + 1:
            reeksen[-1].append(nr)
        else:
            reeksen.append([nr])
    return reeksen


def _jaren_en_weken(weken: int) -> str:
    """52 weken leest niet; "een jaar" wel."""
    jaren, rest = divmod(weken, 52)
    if not jaren:
        return f"{weken} weken"
    stuk = f"{jaren} jaar" if jaren > 1 else "1 jaar"
    return stuk if rest < 4 else f"{stuk} en {rest} weken"


def _beste_jaar(n: _Nummer) -> int:
    return max(n.punten_per_jaar, key=lambda j: n.punten_per_jaar[j])


def verzamel(con: sqlite3.Connection, lijst: str = "top40") -> list[Blok]:
    """De tien ranglijsten. Lege database -> lege lijst."""
    kalender, nummers = _lees(con, lijst)
    if not nummers:
        return []

    # --- per artiest optellen ----------------------------------------------
    # De sleutel is `artiest|titel` en al genormaliseerd, dus het deel voor de
    # streep is een stabiele artiestsleutel -- ook als de site de schrijfwijze
    # halverwege verandert.
    per_artiest: dict[str, dict] = {}
    for n in nummers.values():
        code = n.sleutel.split("|", 1)[0]
        a = per_artiest.setdefault(code, {
            "naam": n.artiest, "nummers": 0, "nummer1s": 0, "weken": 0,
            "punten": 0, "jaren": set(),
        })
        a["naam"] = n.artiest          # laatste schrijfwijze
        a["nummers"] += 1
        a["weken"] += len(n.posities)
        a["punten"] += n.punten
        a["jaren"] |= n.jaren
        if min(n.posities.values()) == 1:
            a["nummer1s"] += 1

    def van_artiest(sorteer, kolom: str, opmaak=str) -> list[dict]:
        besten = sorted(per_artiest.values(), key=sorteer, reverse=True)[:TOP]
        return [{"naam": a["naam"], "waarde": opmaak(a[kolom]),
                 "bij": _bij_artiest(a)} for a in besten]

    def _bij_artiest(a: dict) -> str:
        jaren = sorted(a["jaren"])
        reeks = f"{jaren[0]}" if len(jaren) == 1 else f"{jaren[0]}–{jaren[-1]}"
        return f"{a['nummers']} nummer{'s' if a['nummers'] != 1 else ''} · {reeks}"

    def van_nummer(gerangschikt, waarde, bij) -> list[dict]:
        return [{
            "naam": f"{n.artiest} — {n.titel}",
            "waarde": waarde(n, extra),
            "bij": bij(n, extra),
            "sleutel": n.sleutel,
            "jaar": _beste_jaar(n),
        } for n, extra in gerangschikt[:TOP]]

    def periode(n: _Nummer) -> str:
        weken = sorted(n.posities)
        return (f"{als_tekst(kalender[weken[0]])} – "
                f"{als_tekst(kalender[weken[-1]])}")

    blokken: list[Blok] = []

    # --- 1 t/m 4: de artiesten ---------------------------------------------

    blokken.append(Blok(
        "noteringen", "Meeste noteringen",
        "Het aantal verschillende nummers waarmee een artiest de lijst haalde. "
        "Een samenwerking telt als een eigen artiest.",
        ["Artiest", "Nummers", ""],
        van_artiest(lambda a: (a["nummers"], a["punten"]), "nummers"),
    ))

    blokken.append(Blok(
        "nummer1s", "Meeste nummer 1-hits",
        "Verschillende nummers die de eerste plaats haalden — hoe lang ze daar "
        "stonden telt hier niet mee.",
        ["Artiest", "Nummer 1-hits", ""],
        van_artiest(lambda a: (a["nummer1s"], a["punten"]), "nummer1s"),
    ))

    blokken.append(Blok(
        "weken", "Meeste weken in de lijst",
        "Alle weken van alle nummers bij elkaar opgeteld. Een artiest met drie "
        "lange hits staat hier hoger dan een met tien eendagsvliegen.",
        ["Artiest", "Weken", ""],
        van_artiest(lambda a: (a["weken"], a["punten"]), "weken"),
    ))

    blokken.append(Blok(
        "punten", "Meeste punten aller tijden",
        "Punten per notering = lijstlengte − positie + 1. Dit weegt hoogte én "
        "duur, en is dus de eerlijkste ranglijst van de vier hierboven.",
        ["Artiest", "Punten", ""],
        van_artiest(lambda a: (a["punten"],), "punten",
                    lambda p: f"{p:,}".replace(",", ".")),
    ))

    # --- 5 en 6: de langzitters --------------------------------------------

    langst = sorted(nummers.values(), key=lambda n: len(n.posities), reverse=True)
    blokken.append(Blok(
        "langst", "Langst genoteerd",
        "Het aantal weken dat een nummer in de lijst stond, over de jaargrens "
        "heen doorgeteld en re-entries meegerekend.",
        ["Nummer", "Weken", "Periode"],
        van_nummer([(n, None) for n in langst],
                   lambda n, _: f"{len(n.posities)} weken",
                   lambda n, _: periode(n)),
    ))

    op_een = [(n, som) for n, som in
              ((n, sum(1 for p in n.posities.values() if p == 1))
               for n in nummers.values()) if som]
    op_een.sort(key=lambda paar: paar[1], reverse=True)
    blokken.append(Blok(
        "op-een", "Langst op nummer 1",
        "Het aantal weken op de eerste plaats. Niet aaneengesloten geteld: een "
        "nummer dat de koppositie heroverde telt die weken gewoon mee.",
        ["Nummer", "Weken op 1", "Periode"],
        van_nummer(op_een, lambda n, w: f"{w} weken", lambda n, _: periode(n)),
    ))

    # --- 7 en 8: de uitschieters -------------------------------------------

    # Binnenkomst = de eerste week van een aaneengesloten periode. De allereerste
    # week van de hele lijst telt niet mee: toen was alles nieuw.
    binnenkomers = []
    for n in nummers.values():
        starts = [r[0] for r in _reeksen(n.posities) if r[0] > 0]
        if starts:
            beste = min(starts, key=lambda nr: n.posities[nr])
            binnenkomers.append((n, beste))
    binnenkomers.sort(key=lambda paar: (paar[0].posities[paar[1]], paar[1]))
    blokken.append(Blok(
        "binnenkomers", "Hoogste binnenkomers",
        "De positie waarop een nummer de lijst binnenkwam — de eerste week van "
        "een periode, dus ook een terugkeer telt.",
        ["Nummer", "Binnen op", "Datum"],
        van_nummer(binnenkomers,
                   lambda n, nr: f"#{n.posities[nr]}",
                   lambda n, nr: als_tekst(kalender[nr])),
    ))

    sprongen = []
    for n in nummers.values():
        weken = sorted(n.posities)
        beste = max(((n.posities[a] - n.posities[b], a, b)
                     for a, b in zip(weken, weken[1:]) if b == a + 1),
                    default=None)
        if beste and beste[0] > 0:
            sprongen.append((n, beste))
    sprongen.sort(key=lambda paar: paar[1][0], reverse=True)
    blokken.append(Blok(
        "sprongen", "Grootste sprong in één week",
        "Van welke positie naar welke, in twee opeenvolgende weken. Een "
        "terugkeer uit het niets telt niet mee: dat is geen stijging.",
        ["Nummer", "Sprong", "Wanneer"],
        van_nummer(sprongen,
                   lambda n, s: f"#{n.posities[s[1]]} → #{n.posities[s[2]]} (+{s[0]})",
                   lambda n, s: als_tekst(kalender[s[2]])),
    ))

    # --- 9 en 10: de late bloeiers -----------------------------------------

    # Hoeveel weken deed een nummer erover om de eerste plaats te bereiken?
    # Binnenkomers op 1 doen niet mee: die staan al bij de hoogste binnenkomers,
    # en "in nul weken" is geen prestatie maar een andere vraag.
    onderweg = []
    for n in nummers.values():
        weken = sorted(n.posities)
        eerste_een = next((nr for nr in weken if n.posities[nr] == 1), None)
        if eerste_een is None:
            continue
        reeks = next(r for r in _reeksen(n.posities) if eerste_een in r)
        stappen = reeks.index(eerste_een)
        if stappen > 0:
            onderweg.append((n, (stappen, reeks[0], eerste_een)))
    onderweg.sort(key=lambda paar: -paar[1][0])
    blokken.append(Blok(
        "onderweg", "Langste weg naar de eerste plaats",
        "Het aantal weken tussen binnenkomst en de eerste keer op 1. Nummers "
        "die meteen op 1 binnenkwamen staan hier niet bij — die vind je "
        "hierboven.",
        ["Nummer", "Weken onderweg", "Binnen op"],
        van_nummer(onderweg,
                   lambda n, o: f"{o[0]} weken",
                   lambda n, o: f"#{n.posities[o[1]]} op {als_tekst(kalender[o[1]])}"),
    ))

    # De Top 40 zet klassiekers zelden opnieuw op de lijst -- vandaar niet "hoe
    # vaak kwam het terug" (dat is bij vrijwel iedereen één keer) maar "hoe lang
    # bleef het weg". Daar zit wél spreiding in, tot vijfentwintig jaar aan toe.
    terugkeer = []
    for n in nummers.values():
        reeksen = _reeksen(n.posities)
        gat = max(((b[0] - a[-1], a[-1], b[0])
                   for a, b in zip(reeksen, reeksen[1:])), default=None)
        if gat:
            terugkeer.append((n, gat))
    terugkeer.sort(key=lambda paar: -paar[1][0])
    blokken.append(Blok(
        "terugkeer", "Langste terugkeer",
        "Nummers die uit de lijst verdwenen en er jaren later weer in stonden. "
        "Gemeten in weken tussen de laatste notering en de terugkeer.",
        ["Nummer", "Weg geweest", "Van – tot"],
        van_nummer(terugkeer,
                   lambda n, g: _jaren_en_weken(g[0]),
                   lambda n, g: (f"{als_tekst(kalender[g[1]])} → "
                                 f"{als_tekst(kalender[g[2]])}")),
    ))

    return blokken


def cijfers(con: sqlite3.Connection, lijst: str = "top40") -> dict:
    """Een paar totalen voor boven de pagina."""
    rij = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT sleutel), MIN(jaar), MAX(jaar),"
        " COUNT(DISTINCT jaar || '-' || week) FROM noteringen WHERE lijst=?",
        (lijst,),
    ).fetchone()
    artiesten = con.execute(
        "SELECT COUNT(DISTINCT substr(sleutel, 1, instr(sleutel, '|') - 1))"
        " FROM noteringen WHERE lijst=?", (lijst,),
    ).fetchone()[0]
    return {
        "noteringen": rij[0], "nummers": rij[1], "van": rij[2], "tot": rij[3],
        "weken": rij[4], "artiesten": artiesten,
    }
