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
           "bouw_m3u8", "TeGroot", "NIVEAUS"]

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

# --- grenzen aan wat een upload mag kosten ---------------------------------
#
# De bezoeker levert het bestand aan, dus de server moet zich verweren tegen
# twee klassieke trucs:
#
#   zip-bom            een paar kilobyte comprimeert naar gigabytes. Gemeten:
#                      83 KB werd 23,8 MB (factor 294). Daarom telt de lezer
#                      de UITGEPAKTE bytes, niet de bestandsgrootte.
#   entiteit-explosie  een DTD met geneste entiteiten blaast in het geheugen
#                      op ("billion laughs"): 400 bytes werden een miljoen
#                      tekens. Een DTD heeft in een muziekdatabase niets te
#                      zoeken, dus die weigeren we botweg -- dat sluit de
#                      hele klasse af, ook XXE.
#
# De ruimte is royaal genoeg voor een echte bibliotheek: Heyes database.xml
# is 209 MB en zijn backup-zip bevat 113.411 nummers.
MAX_UITGEPAKT = 512 * 1024 * 1024      # per bestand in de upload
MAX_NUMMERS = 2_000_000                # bovengrens aan de bibliotheek


class TeGroot(ValueError):
    """De upload overschrijdt een grens; de route toont dit aan de bezoeker."""


class _Bewaakt:
    """Leesbare stroom die de uitgepakte omvang telt en DTD's weigert.

    Zip-bestanden geven hun inhoud pas al lezend prijs, dus de grens moet
    tijdens het lezen gelden en niet achteraf: bij het plafond stopt het
    parsen meteen, met hooguit één brok extra in het geheugen.
    """

    # Een DTD kan net over de rand van twee brokken vallen; bewaar daarom de
    # staart van de vorige brok en zoek over de naad heen.
    _NAAD = len(b"<!DOCTYPE")

    def __init__(self, stroom, plafond: int = MAX_UITGEPAKT):
        self._stroom = stroom
        self._over = plafond
        self._staart = b""

    def read(self, aantal: int = -1) -> bytes:
        brok = self._stroom.read(aantal)
        if not brok:
            return brok
        self._over -= len(brok)
        if self._over < 0:
            raise TeGroot("het bestand is na uitpakken groter dan "
                          f"{MAX_UITGEPAKT // (1024 * 1024)} MB")
        kijk = self._staart + brok
        if b"<!DOCTYPE" in kijk or b"<!doctype" in kijk:
            raise TeGroot("dit bestand bevat een DTD; dat staan we niet toe")
        self._staart = brok[-self._NAAD:]
        return brok


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
    for _, el in ET.iterparse(_Bewaakt(bron), events=("end",)):
        if len(uit) > MAX_NUMMERS:
            raise TeGroot(f"meer dan {MAX_NUMMERS:,} nummers in één bestand"
                          .replace(",", "."))
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


def lees_rekordbox(bron) -> list[Bestand]:
    """Een rekordbox-export (Bestand -> Exporteer collectie in xml-formaat).

    Zelfde uitkomst als lees_database, andere structuur: TRACK-elementen
    met de metadata als attributen en het pad als file://-URL. Alles is
    lokaal -- rekordbox exporteert geen streaming-catalogus.
    """
    from urllib.parse import unquote, urlparse

    uit: list[Bestand] = []
    for _, el in ET.iterparse(_Bewaakt(bron), events=("end",)):
        if len(uit) > MAX_NUMMERS:
            raise TeGroot(f"meer dan {MAX_NUMMERS:,} nummers in één bestand"
                          .replace(",", "."))
        if el.tag != "TRACK":
            continue
        plek = el.get("Location", "")
        if plek:
            # file://localhost/C:/Muziek/A%20B.mp3 -> C:/Muziek/A B.mp3
            pad = unquote(urlparse(plek).path)
            if len(pad) > 2 and pad[0] == "/" and pad[2] == ":":
                pad = pad[1:]           # Windows: /C:/... -> C:/...
            artiest = (el.get("Artist") or "").strip()
            titel = (el.get("Name") or "").strip()
            if artiest and titel and pad.lower().endswith(_AUDIO):
                try:
                    bitrate = int(el.get("BitRate") or 0)
                except ValueError:
                    bitrate = 0
                uit.append(Bestand(pad=pad, artiest=artiest, titel=titel,
                                   bitrate=bitrate,
                                   video=pad.lower().endswith(_BEELD)))
        el.clear()

    for b in uit:
        b.sleutel = sleutel_van(b.artiest, b.titel)
        b.kern = _kernsleutel(b.artiest, b.titel)
    return uit


def lees_upload(stroom, naam: str) -> tuple[list[Bestand], str]:
    """Een upload lezen: een kale database.xml, een rekordbox-export of de
    backup-zip van VirtualDJ (Instellingen -> Backup) -- daar zit de
    database in, samen met de history en de playlists. We vissen elke
    database.xml eruit. Een rekordbox-bestand verraadt zich door zijn
    DJ_PLAYLISTS-wortel.

    Geeft (bestanden, soort) terug -- soort is "vdj" of "rekordbox", want
    de bron bepaalt welk playlistformaat de bezoeker straks krijgt.
    """
    import zipfile

    kop = stroom.read(4096)
    stroom.seek(0)
    if kop[:4] != b"PK\x03\x04":
        if b"DJ_PLAYLISTS" in kop:
            return lees_rekordbox(stroom), "rekordbox"
        return lees_database(stroom), "vdj"
    uit: list[Bestand] = []
    with zipfile.ZipFile(stroom) as zak:
        for info in zak.infolist():
            if not info.filename.lower().endswith("database.xml"):
                continue
            # De opgegeven maat staat in de zip zelf en is te vervalsen, dus
            # hij dient alleen om overduidelijke bommen vroeg te weigeren;
            # het echte plafond bewaakt _Bewaakt tijdens het lezen.
            if info.file_size > MAX_UITGEPAKT:
                raise TeGroot("een database.xml in deze zip is na uitpakken "
                              f"groter dan {MAX_UITGEPAKT // (1024 * 1024)} MB")
            with zak.open(info) as binnen:
                uit += lees_database(binnen)
            if len(uit) > MAX_NUMMERS:
                raise TeGroot(f"meer dan {MAX_NUMMERS:,} nummers in deze zip"
                              .replace(",", "."))
    if not uit:
        raise ValueError(f"{naam}: geen database.xml in de zip gevonden")
    return uit, "vdj"


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


def bouw_m3u8(koppels: list[dict]) -> str:
    """Dezelfde playlist als platte M3U8: voor rekordbox, Engine DJ,
    Traktor, Serato en zo'n beetje elke mediaspeler. De duur kennen we
    niet (-1); artiest en titel komen uit de lijst zelf."""
    regels = ["#EXTM3U"]
    for k in koppels:
        if k["bestand"]:
            regels.append(f"#EXTINF:-1,{k['artiest']} - {k['titel']}")
            regels.append(k["bestand"].pad)
    return "\n".join(regels) + "\n"


def bouw_vdjfolder(paden: list[str]) -> str:
    """Een .vdjfolder zoals VirtualDJ hem zelf schrijft: paden, op volgorde."""
    regels = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<VirtualFolder noDuplicates="no">']
    regels += [f" <song path={quoteattr(pad)} idx=\"{nr}\" />"
               for nr, pad in enumerate(paden)]
    regels.append("</VirtualFolder>")
    return "\n".join(regels)
