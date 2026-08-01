"""Alarmschijven en Dancesmashes van michajans.nl bij onze nummers zetten.

Een Alarmschijf is de wekelijkse aanbeveling van de Top 40-redactie, een
Dancesmash dezelfde soort aanduiding voor dancenummers. Ze staan niet op
top40.nl, alleen in het archief van de Werkgroep Hitlijsten.

Hun pagina's zijn per decennium en geven: volgnummer, datum, hoogste positie,
aantal weken en "Titel - Artiest". Die laatste is niet betrouwbaar te splitsen
-- een titel mag zelf " - " bevatten -- dus koppelen we op woordoverlap met de
nummers die in datzelfde jaar bij ons noteerden. Dat is nauwkeurig genoeg omdat
er per jaar maar een paar honderd kandidaten zijn.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .config import CACHE_DIR
from .db import verbinding
from .kruiscontrole import decodeer
from .normalize import normaliseer

BASIS = "https://www.michajans.nl"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

PAGINAS = {
    "alarmschijf": [
        "alarmschijven-60.htm", "alarmschijven-70.htm", "alarmschijven-80.htm",
        "alarmschijven-90.htm", "alarmschijven-00.htm", "alarmschijven-10.htm",
        "alarmschijven-20.htm",
    ],
    "dancesmash": [
        "dancesmash-90.htm", "dancesmash-00.htm", "dancesmash-10.htm",
    ],
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS onderscheidingen (
    id        INTEGER PRIMARY KEY,
    soort     TEXT    NOT NULL,   -- alarmschijf | dancesmash
    datum     TEXT    NOT NULL,   -- ISO, de week waarin toegekend
    jaar      INTEGER NOT NULL,
    naam      TEXT    NOT NULL,   -- "Titel - Artiest" zoals zij het schrijven
    sleutel   TEXT,               -- ons nummer, NULL als niet gekoppeld
    volgnr    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_onderscheiding_sleutel ON onderscheidingen (sleutel);
"""


@dataclass
class Onderscheiding:
    soort: str
    datum: str
    jaar: int
    naam: str
    volgnr: Optional[int] = None
    sleutel: Optional[str] = None


def _haal(pad: str, *, forceer: bool = False) -> Optional[str]:
    cache = CACHE_DIR / "michajans" / pad
    if cache.exists() and not forceer:
        return cache.read_text(encoding="utf-8")
    respons = requests.get(f"{BASIS}/{pad}", headers={"User-Agent": UA}, timeout=30)
    time.sleep(1.0)
    if respons.status_code != 200:
        return None
    tekst = decodeer(respons.content)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(tekst, encoding="utf-8")
    return tekst


def _lees_pagina(soort: str, pad: str) -> list[Onderscheiding]:
    html = _haal(pad)
    if not html:
        return []
    tabel = BeautifulSoup(html, "lxml").find("table")
    if tabel is None:
        return []

    uit: list[Onderscheiding] = []
    for tr in tabel.find_all("tr"):
        cellen = [
            " ".join(td.get_text(" ", strip=True).split())
            for td in tr.find_all(["td", "th"])
        ]
        if len(cellen) < 5 or not cellen[0].isdigit():
            continue
        datum_tekst = cellen[1]
        naam = cellen[4].strip()
        if not naam:
            continue  # lege staartregel
        try:
            datum = datetime.strptime(datum_tekst, "%d-%m-%Y").date()
        except ValueError:
            continue
        uit.append(
            Onderscheiding(
                soort=soort,
                datum=datum.isoformat(),
                jaar=datum.year,
                naam=naam,
                volgnr=int(cellen[0]),
            )
        )
    return uit


def haal_alles(*, forceer: bool = False) -> list[Onderscheiding]:
    alles: list[Onderscheiding] = []
    for soort, paden in PAGINAS.items():
        for pad in paden:
            if forceer:
                _haal(pad, forceer=True)
            alles += _lees_pagina(soort, pad)
    return alles


def _woorden(tekst: str) -> set[str]:
    """Woorden voor het koppelen. De & telt niet mee als teken.

    michajans schrijft "Head&heart" waar top40.nl "Head & Heart" heeft. Zonder
    de & los te weken is dat een heel ander woord en ketst de koppeling af.
    """
    return {
        w for w in normaliseer(tekst.replace("&", " "), samenwerking=False).split()
        if w != "&"
    }


# Ondertitels: "Austin (Boots Stop Workin')" of "Cruel Man - Thema Uit De Film"
# bij top40.nl, tegenover kaal "Austin" en "Cruel man" bij michajans. Precies
# het soort verschil dat een koppeling onterecht laat afketsen.
_ONDERTITEL = re.compile(r"[\(\[].*?[\)\]]")


def _plat(tekst: str) -> str:
    """Alle woorden gesorteerd aan elkaar geplakt, herhalingen behouden.

    Sorteren maakt het onafhankelijk van de volgorde -- zij schrijven
    "Titel - Artiest", wij hebben ze los. Herhalingen moeten blijven staan:
    "Mi mi mi" mag niet tot "mi" worden samengeknepen, want dan valt de
    overeenkomst met "Mimimi" juist weg.
    """
    woorden = normaliseer(tekst.replace("&", " "), samenwerking=False).split()
    return "".join(sorted(w for w in woorden if w != "&"))


def _kerntitel(titel: str) -> set[str]:
    kaal = _ONDERTITEL.sub(" ", titel)
    kaal = kaal.split(" - ")[0]          # ondertitel achter een streepje
    return _woorden(kaal) or _woorden(titel)


def koppel_aan_onze_nummers(
    onderscheidingen: list[Onderscheiding], drempel: float = 0.6
) -> tuple[int, int]:
    """Zoek bij elke onderscheiding ons nummer. Geeft (gekoppeld, niet) terug.

    De titel weegt zwaarder dan de artiest, want juist de artiestnaam wordt door
    de twee sites verschillend geschreven: "Mirrors - JT" tegenover
    "Mirrors - Justin Timberlake", "VanVelzen" tegenover "Van Velzen",
    "Maroon 5 feat." tegenover "Maroon5 featuring". Op woordoverlap van de hele
    regel vallen die af; op de titel niet.
    """
    with verbinding() as con:
        per_jaar: dict[int, list[tuple[str, set[str], set[str]]]] = {}
        for r in con.execute(
            "SELECT DISTINCT jaar, sleutel, titel, artiest FROM noteringen"
            " WHERE lijst='top40'"
        ):
            per_jaar.setdefault(r["jaar"], []).append(
                (r["sleutel"], _woorden(r["titel"]), _kerntitel(r["titel"]),
                 _woorden(r["artiest"]), _plat(f"{r['titel']} {r['artiest']}"))
            )

    gekoppeld = 0
    for o in onderscheidingen:
        hun_woorden = _woorden(o.naam)
        hun_plat = _plat(o.naam)
        # Een onderscheiding valt soms net voor de eerste notering: kijk ook in
        # het jaar erna, anders missen we de decembergevallen.
        kandidaten = per_jaar.get(o.jaar, []) + per_jaar.get(o.jaar + 1, [])
        beste, hoogste = None, 0.0
        for sleutel, titelwoorden, kernwoorden, artiestwoorden, plat in kandidaten:
            if not titelwoorden:
                continue
            # De beste van de volledige titel en de titel zonder ondertitel.
            titel_score = max(
                len(titelwoorden & hun_woorden) / len(titelwoorden),
                len(kernwoorden & hun_woorden) / len(kernwoorden),
            )
            artiest_score = (
                len(artiestwoorden & hun_woorden) / len(artiestwoorden)
                if artiestwoorden else 0.0
            )
            score = 0.7 * titel_score + 0.3 * artiest_score

            # Vangnet voor spatieverschillen, die geen enkele woordvergelijking
            # ziet: "Mimimi" tegenover "Mi mi mi", "Maroon5" tegenover
            # "Maroon 5", "VanVelzen" tegenover "Van Velzen". Vergelijk daarom
            # ook de kale tekenreeks zonder spaties.
            if score < drempel:
                gelijk = SequenceMatcher(None, plat, hun_plat).ratio()
                if gelijk >= 0.85:
                    score = max(score, gelijk)

            if score > hoogste:
                beste, hoogste = sleutel, score
        if beste is not None and hoogste >= drempel:
            o.sleutel = beste
            gekoppeld += 1
    return gekoppeld, len(onderscheidingen) - gekoppeld


def bewaar(onderscheidingen: list[Onderscheiding]) -> int:
    with verbinding() as con:
        con.executescript(SCHEMA)
        con.execute("DELETE FROM onderscheidingen")
        con.executemany(
            "INSERT INTO onderscheidingen (soort, datum, jaar, naam, sleutel, volgnr)"
            " VALUES (?,?,?,?,?,?)",
            [(o.soort, o.datum, o.jaar, o.naam, o.sleutel, o.volgnr)
             for o in onderscheidingen],
        )
        con.commit()
    return len(onderscheidingen)


def per_sleutel(jaar: int, con=None) -> dict[str, dict[str, str]]:
    """{sleutel: {"alarmschijf": datum, "dancesmash": datum}} voor een jaargang.

    Geef `con` mee om op een bestaande verbinding te werken. Zonder dat opent
    deze functie de standaarddatabase -- wat in een test met een tijdelijke
    database de verkeerde zou zijn.
    """
    if con is not None:
        return _per_sleutel(con, jaar)
    with verbinding() as eigen:
        return _per_sleutel(eigen, jaar)


def _per_sleutel(con, jaar: int) -> dict[str, dict[str, str]]:
    con.executescript(SCHEMA)
    uit: dict[str, dict[str, str]] = {}
    for r in con.execute(
        "SELECT sleutel, soort, datum FROM onderscheidingen"
        " WHERE sleutel IS NOT NULL AND jaar IN (?, ?)",
        (jaar, jaar - 1),
    ):
        uit.setdefault(r["sleutel"], {})[r["soort"]] = r["datum"]
    return uit
