"""Nummers over weken heen herkennen.

Een jaarmatrix valt uit elkaar als "Antoon ft. Sef" in week 3 en "Antoon feat.
Sef" in week 12 als twee verschillende nummers tellen. Deze module maakt van
(artiest, titel) een stabiele sleutel.

Uitgangspunt: liever te weinig samenvoegen dan te veel. Er wordt niets
weggegooid wat betekenis kan dragen (een remix blijft een ander nummer).
Twijfelgevallen worden gerapporteerd via `verdachte_paren` zodat ze handmatig in
aliases.csv gezet kunnen worden -- ze worden nooit automatisch samengevoegd.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Iterable

from .config import ALIASES_PATH, NIET_SAMENVOEGEN_PATH

# "feat.", "ft", "featuring", "with" en "&" worden allemaal " & ".
#
# Vroeger werd "feat." een eigen teken (" ft ") en "&" een ander, en dan
# zijn "Calvin Harris feat. Rihanna" en "Calvin Harris & Rihanna" twee
# artiesten. Dat is een verschil zonder betekenis: het gaat om dezelfde twee
# mensen op dezelfde plaat. 162 samenwerkingen stonden er los van elkaar door.
_FEAT = re.compile(r"\s*(?:\bfeat\b\.?|\bft\b\.?|\bfeaturing\b|\bwith\b)\s*", re.I)
# Samenwerkingstekens gelijktrekken: "x", "&", "+", "vs" -> "&".
_EN = re.compile(r"\s*(?:&|\+|\bx\b|\bvs\b\.?|\bversus\b)\s*", re.I)
_WITRUIMTE = re.compile(r"\s+")
# Alles behalve letters, cijfers, spatie en de betekenisdragende &.
# Let op: dit verwijdert ook de "|" -- dat is met opzet, want die scheidt in de
# sleutel de artiest van de titel en mag daar niet uit de tekst zelf komen.
_ROMMEL = re.compile(r"[^a-z0-9 &]")

# Een lidwoord vooraan de artiestnaam is geen naam maar een gewoonte, en de
# bronnen zijn het er niet over eens: top40.nl schrijft "The Beatles", Music
# Datastats schrijft "Beatles". Dat leverde 353 artiesten op met twee
# gescheiden geschiedenissen. Alleen vooraan, alleen bij de artiest -- in een
# titel draagt het lidwoord wel betekenis ("The Wall" is niet "Wall").
_LIDWOORD = re.compile(r"^(?:the|de|het) ")

# Letters die NFKD niet uit elkaar haalt. Een e met een accent valt vanzelf
# uiteen in "e" plus een tekentje, maar de o van Bløf is een eigen letter: die
# overleeft de ontleding en wordt daarna als "rommel" weggegooid. "Bløf" werd zo
# "bl f" en stond los van "Blof" -- de band viel in tweeen. Vandaar deze tabel.
_LETTERS = {
    "ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE",
    "ß": "ss", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ð": "d", "Ð": "D",
    "þ": "th", "Þ": "TH", "ı": "i", "ħ": "h", "ŧ": "t", "ĸ": "k",
}

_TYPOGRAFIE = {
    "‘": "'", "’": "'", "‚": "'",
    "“": '"', "”": '"', "„": '"',
    "–": "-", "—": "-", "−": "-",
    " ": " ", "​": "",
}


def normaliseer(tekst: str, *, samenwerking: bool = True) -> str:
    """Maak een tekst vergelijkbaar zonder de betekenis te verliezen.

    Met `samenwerking=False` blijven "x", "&" en "feat." staan zoals ze zijn.
    Dat is de juiste stand voor titels: in een artiestnaam betekent "x" een
    samenwerking, in een titel als "Malcolm X" is het gewoon een letter.
    """
    if not tekst:
        return ""
    for van, naar in _TYPOGRAFIE.items():
        tekst = tekst.replace(van, naar)
    for van, naar in _LETTERS.items():
        tekst = tekst.replace(van, naar)
    # Accenten weg: "Beyoncé" == "Beyonce".
    tekst = unicodedata.normalize("NFKD", tekst)
    tekst = "".join(c for c in tekst if not unicodedata.combining(c))
    tekst = tekst.lower()
    if samenwerking:
        tekst = _FEAT.sub(" & ", tekst)
        tekst = _EN.sub(" & ", tekst)
    tekst = _ROMMEL.sub(" ", tekst)
    return _WITRUIMTE.sub(" ", tekst).strip()


@lru_cache(maxsize=1)
def _aliases() -> dict[str, str]:
    """Handmatige koppelingen uit de tabel `aliases` in de database."""
    from .db import verbinding   # laat staan: db importeert normalize terug

    with verbinding() as con:
        return {r["van"]: r["naar"] for r in con.execute("SELECT van, naar FROM aliases")}


def vergeet_aliases() -> None:
    """Na het bewerken van aliases.csv binnen een draaiend proces."""
    _aliases.cache_clear()
    niet_samenvoegen.cache_clear()


@lru_cache(maxsize=1)
def niet_samenvoegen() -> set[frozenset[str]]:
    """Sleutelparen die er weliswaar op lijken, maar losse noteringen zijn.

    Zonder deze lijst stelt `controle` dezelfde afgewezen paren elke keer
    opnieuw voor -- bijvoorbeeld een kerst- of voetbalversie die vlak na het
    origineel verscheen en dus binnen de weekgrens valt, maar toch een eigen
    nummer is.
    """
    from .db import verbinding

    with verbinding() as con:
        return {
            frozenset((r["sleutel_a"], r["sleutel_b"]))
            for r in con.execute("SELECT sleutel_a, sleutel_b FROM niet_samenvoegen")
        }


def artiestsleutel(artiest: str) -> str:
    """De artiest, vergelijkbaar gemaakt: samenwerkingstekens gelijk, lidwoord weg.

    Bij de artiest betekent "x" een samenwerking en wordt hij gelijkgetrokken
    met "&"; bij de titel niet, want daar is het een letter ("Malcolm X").
    """
    return _LIDWOORD.sub("", normaliseer(artiest))


def sleutel_van(artiest: str, titel: str) -> str:
    """De sleutel waarop een nummer over weken heen wordt herkend."""
    ruw = f"{artiestsleutel(artiest)}|{normaliseer(titel, samenwerking=False)}"
    return _volg_alias(ruw)


def _volg_alias(sleutel: str) -> str:
    """Volg een aliasketen a->b->c helemaal door, met bescherming tegen cycli.

    Wie drie schrijfwijzen wil samenvoegen schrijft twee regels in aliases.csv;
    zonder doorvolgen belanden die juist in verschillende groepen -- het
    tegenovergestelde van de bedoeling. Bij een cyclus (a->b->a) stoppen we en
    geven we de laagste sleutel terug, zodat alle leden er in elk geval op
    dezelfde uitkomen.
    """
    tabel = _aliases()
    gezien = [sleutel]
    huidige = sleutel
    while huidige in tabel:
        volgende = tabel[huidige]
        if volgende in gezien:
            return min(gezien)  # cyclus: kies een vaste vertegenwoordiger
        gezien.append(volgende)
        huidige = volgende
    return huidige


def verdachte_paren(
    sleutels: Iterable[tuple[str, str, str]], drempel: float = 0.90
) -> list[tuple[str, str, float]]:
    """Zoek sleutelparen die verdacht veel op elkaar lijken.

    Invoer: (sleutel, artiest, titel). Uitvoer: paren met gelijkenis boven de
    drempel, als kandidaten voor aliases.csv. Voegt zelf niets samen.
    """
    uniek: dict[str, str] = {}
    for sleutel, artiest, titel in sleutels:
        uniek.setdefault(sleutel, f"{artiest} - {titel}")

    items = sorted(uniek.items())
    treffers: list[tuple[str, str, float]] = []
    for i, (sleutel_a, _) in enumerate(items):
        artiest_a, _, titel_a = sleutel_a.partition("|")
        for sleutel_b, _ in items[i + 1:]:
            artiest_b, _, titel_b = sleutel_b.partition("|")

            # Dubbele A-kanten: de site hernoemt "Cheerio" halverwege het jaar
            # naar "Cheerio / Cheerio - Remix". De sleutels verschillen dan sterk
            # in lengte, maar de een zit in de ander. Zulke paren zijn juist de
            # belangrijkste kandidaten -- ze splitsen een lopende notering in
            # tweeen en verdelen de punten.
            bevat = (
                (titel_a and titel_b and (titel_a in titel_b or titel_b in titel_a))
                and (artiest_a in artiest_b or artiest_b in artiest_a)
            )
            if bevat and sleutel_a != sleutel_b:
                treffers.append((sleutel_a, sleutel_b, 1.0))
                continue

            # Goedkope voorfilter: sterk verschillende lengtes slaan we over.
            if abs(len(sleutel_a) - len(sleutel_b)) > 12:
                continue
            score = SequenceMatcher(None, sleutel_a, sleutel_b).ratio()
            if score >= drempel:
                treffers.append((sleutel_a, sleutel_b, round(score, 3)))
    return sorted(treffers, key=lambda t: -t[2])
