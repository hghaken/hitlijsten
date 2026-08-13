"""VirtualDJ-koppeling: van een database.xml naar een .vdjfolder-playlist.

De bezoeker (of de beheerder) uploadt zijn VirtualDJ-database, kiest een
jaaroverzicht, en krijgt een playlist terug met de nummers die hij zélf in
zijn bibliotheek heeft -- in klassementvolgorde -- plus het lijstje van wat
er ontbreekt. De matching gebruikt dezelfde sleutel-normalisatie als de
lijsten zelf (lidwoorden, feat./&, leestekens, aliassen), dus "The Beatles"
in VirtualDJ matcht "Beatles" in de Top 40 vanzelf.

STRENGHEID
----------
Vier niveaus, elk niveau omvat de vorige:

1. **zeer strak** -- exact dezelfde sleutel.
2. **strak** -- ook een match als de haakjes-delen van de titel verschillen:
   "Venus" tegen "Venus (Remastered)".
3. **soepel** -- kerntitel gelijk, artiest mag afwijken zolang hij duidelijk
   lijkt (gedeelde woorden of kleine spelverschillen).
4. **zeer soepel** -- ook de titel mag kleine spelverschillen hebben; hier
   sluipen valse treffers binnen, en daarom heten deze matches in het
   rapport "twijfel".
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Optional
from xml.sax.saxutils import quoteattr

from .normalize import sleutel_van

__all__ = ["lees_database", "lees_upload", "match", "bouw_vdjfolder",
           "NIVEAUS"]

NIVEAUS = {
    1: "zeer strak",
    2: "strak",
    3: "soepel",
    4: "zeer soepel",
}

# Wat we als draaibaar bestand beschouwen; de rest (netsearch-verwijzingen,
# video-overlays, html) blijft buiten de playlist.
_GELUID = (".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".aif",
           ".aiff", ".wma")
_BEELD = (".mp4", ".mkv", ".avi", ".vob", ".webm", ".mov")
_AUDIO = _GELUID + _BEELD

_HAAKJES = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")


@dataclass
class Bestand:
    """Eén draaibaar nummer uit de VirtualDJ-database.

    `streaming` betekent een netsearch-verwijzing: geen bestand op schijf,
    maar VirtualDJ speelt hem gewoon af (met abonnement). Bij dubbelen wint
    een lokaal bestand altijd van streaming.
    """

    pad: str
    artiest: str
    titel: str
    bitrate: int
    streaming: bool = False
    video: bool = False
    sleutel: str = ""
    kern: str = ""          # sleutel met de haakjes-delen uit de titel


def _kernsleutel(artiest: str, titel: str) -> str:
    return sleutel_van(artiest, _HAAKJES.sub("", titel))


def lees_database(bron) -> list[Bestand]:
    """Lees een database.xml (pad of bestandsobject) tot een bestandenlijst.

    Stromend geparsed: een grote bibliotheek is honderden megabytes en de
    boom hoeft nooit in zijn geheel in het geheugen. Per pad wint het
    bestand met de hoogste bitrate -- het antwoord op dubbelen komt later,
    bij de matching, waar per sléutel de beste wint.
    """
    uit: list[Bestand] = []
    for _, el in ET.iterparse(bron, events=("end",)):
        if el.tag != "Song":
            continue
        pad = el.get("FilePath", "")
        lokaal = pad.lower().endswith(_AUDIO) and "://" not in pad
        streaming = pad.startswith("netsearch://")
        if lokaal or streaming:
            tags = el.find("Tags")
            artiest = (tags.get("Author", "") if tags is not None else "").strip()
            titel = (tags.get("Title", "") if tags is not None else "").strip()
            if artiest and titel:
                infos = el.find("Infos")
                try:
                    bitrate = int(infos.get("Bitrate", 0)) if infos is not None else 0
                except ValueError:
                    bitrate = 0
                # netsearch://tdv... is de videocatalogus, td... audio.
                video = (pad.lower().endswith(_BEELD)
                         or pad.startswith("netsearch://tdv"))
                uit.append(Bestand(pad=pad, artiest=artiest, titel=titel,
                                   bitrate=bitrate, streaming=streaming,
                                   video=video))
        el.clear()

    for b in uit:
        b.sleutel = sleutel_van(b.artiest, b.titel)
        b.kern = _kernsleutel(b.artiest, b.titel)
    return uit


def lees_upload(stroom, naam: str) -> list[Bestand]:
    """Een upload lezen: een kale database.xml of de backup-zip van
    VirtualDJ (Instellingen -> Backup) -- daar zit de database in, samen
    met de history en de playlists. We vissen elke database.xml eruit."""
    import zipfile

    kop = stroom.read(4)
    stroom.seek(0)
    if kop != b"PK\x03\x04":
        return lees_database(stroom)
    uit: list[Bestand] = []
    with zipfile.ZipFile(stroom) as zak:
        for info in zak.infolist():
            if info.filename.lower().endswith("database.xml"):
                with zak.open(info) as binnen:
                    uit += lees_database(binnen)
    if not uit:
        raise ValueError(f"{naam}: geen database.xml in de zip gevonden")
    return uit


def _beste(kandidaten: Iterable[Bestand]) -> Bestand:
    # Lokaal boven streaming, en dan de hoogste bitrate.
    return max(kandidaten, key=lambda b: (not b.streaming, b.bitrate))


def _lijkt(a: str, b: str, grens: float) -> bool:
    if a == b:
        return True
    return SequenceMatcher(None, a, b).ratio() >= grens


def match(regels: list[dict], bestanden: list[Bestand],
          niveau: int = 2) -> list[dict]:
    """Koppel klassementregels ({artiest, titel, sleutel, ...}) aan bestanden.

    Geeft per regel dezelfde dict terug plus `bestand` (of None) en
    `niveau` (op welk niveau de match viel). De zwaardere niveaus draaien
    alleen voor wat de lichtere lieten liggen.
    """
    op_sleutel: dict[str, list[Bestand]] = {}
    op_kern: dict[str, list[Bestand]] = {}
    op_kerntitel: dict[str, list[Bestand]] = {}
    for b in bestanden:
        op_sleutel.setdefault(b.sleutel, []).append(b)
        op_kern.setdefault(b.kern, []).append(b)
        op_kerntitel.setdefault(b.kern.split("|", 1)[-1], []).append(b)

    # Voor niveau 4: kandidaten zoeken via gedeelde titelwoorden, anders is
    # fuzzy vergelijken over de hele bibliotheek onbetaalbaar.
    op_woord: dict[str, set[str]] = {}
    if niveau >= 4:
        for kerntitel in op_kerntitel:
            for woord in kerntitel.split():
                if len(woord) >= 3:
                    op_woord.setdefault(woord, set()).add(kerntitel)

    uit = []
    for regel in regels:
        sleutel = regel["sleutel"]
        artiestdeel, titeldeel = sleutel.split("|", 1)
        kern = artiestdeel + "|" + _HAAKJES.sub("", titeldeel).strip()
        kerntitel = kern.split("|", 1)[-1]

        bestand = None
        trap = None
        if sleutel in op_sleutel:
            bestand, trap = _beste(op_sleutel[sleutel]), 1
        elif niveau >= 2 and kern in op_kern:
            bestand, trap = _beste(op_kern[kern]), 2
        elif niveau >= 2 and kerntitel in op_kerntitel:
            # Het duet-geval: de lijst crediteert "Meat Loaf & Ellen Foley",
            # het bestand is getagd als "Meat Loaf". Is de ene artiest een
            # deelverzameling van de andere (gesplitst op &), dan is dat
            # dezelfde plaat -- geen gok, dus dit hoort bij "strak".
            delen = set(artiestdeel.split(" & "))
            past = [b for b in op_kerntitel[kerntitel]
                    if (lambda d: d and (d <= delen or delen <= d))(
                        set(b.kern.split("|", 1)[0].split(" & ")))]
            if past:
                bestand, trap = _beste(past), 2
        if bestand is None and niveau >= 3 and kerntitel in op_kerntitel:
            past = [b for b in op_kerntitel[kerntitel]
                    if _lijkt(b.kern.split("|", 1)[0], artiestdeel, 0.6)
                    or set(b.kern.split("|", 1)[0].split())
                    & set(artiestdeel.split())]
            if past:
                bestand, trap = _beste(past), 3
        if bestand is None and niveau >= 4:
            kandidaten: set[str] = set()
            for woord in kerntitel.split():
                kandidaten |= op_woord.get(woord, set())
            past = []
            for kt in kandidaten:
                if _lijkt(kt, kerntitel, 0.85):
                    past += [b for b in op_kerntitel[kt]
                             if _lijkt(b.kern.split("|", 1)[0],
                                       artiestdeel, 0.5)]
            if past:
                bestand, trap = _beste(past), 4

        rij = dict(regel)
        rij["bestand"] = bestand
        rij["niveau"] = trap
        uit.append(rij)
    return uit


def bouw_vdjfolder(paden: list[str]) -> str:
    """Een .vdjfolder zoals VirtualDJ hem zelf schrijft: paden, op volgorde."""
    regels = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<VirtualFolder noDuplicates="no">']
    regels += [f" <song path={quoteattr(pad)} idx=\"{nr}\" />"
               for nr, pad in enumerate(paden)]
    regels.append("</VirtualFolder>")
    return "\n".join(regels)
