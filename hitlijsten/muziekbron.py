"""MusicBrainz vragen hoe een artiest of nummer echt heet.

WAAROM MUSICBRAINZ EN NIET WIKIPEDIA
------------------------------------
Wikipedia is geschreven voor mensen: de titel van een artikel is een
compromis tussen de juiste naam en wat leesbaar is in een zin, en er staat geen
veld in dat zegt "zo schrijft de artiest zich". MusicBrainz is een catalogus met
precies dat veld, met een open licentie en zonder sleutel. Voor de vraag "heet
het nu Dexys Midnight Runners of Dexy's Midnight Runners" is dat de betere bron.

Wikipedia blijft nuttig als tweede mening bij Nederlandse artiesten, die in
MusicBrainz soms mager staan; daarvoor is `wikipedia_bestaat()`.

DE SPELREGELS VAN DE BRON
-------------------------
MusicBrainz staat **een verzoek per seconde** toe en eist een User-Agent waarin
staat wie er klopt. Beide staan hieronder hard ingesteld -- niet als beleefdheid
maar omdat het anders na een paar honderd verzoeken op een blokkade uitloopt.
Alles wat binnenkomt gaat op schijf, zodat een tweede ronde over dezelfde namen
geen enkel verzoek kost. Dat is niet alleen sneller: het maakt het oordeel
herhaalbaar, want de bron kan morgen anders antwoorden.
"""
from __future__ import annotations

import hashlib
import json
import time
import unicodedata
import urllib.parse
from pathlib import Path
from typing import Optional

import requests

from .config import ROOT

__all__ = ["zoek_artiest", "canonieke_artiest", "zoek_opname",
           "wikipedia_bestaat", "zoek_uitgave"]

CACHE = ROOT / ".cache" / "muziekbron"
BASIS = "https://musicbrainz.org/ws/2"
# Wie er klopt. MusicBrainz weigert verzoeken zonder herkenbare afzender.
KOP = {"User-Agent": "hitlijsten/1.0 (https://hitlijsten.hhaken.nl; heye@hhaken.nl)"}
PAUZE = 1.2          # seconden tussen twee verzoeken; de bron staat er één toe
POGINGEN = 4         # bij een 503 opnieuw, met oplopende pauze
_laatste = 0.0


def _wacht() -> None:
    global _laatste
    rust = PAUZE - (time.monotonic() - _laatste)
    if rust > 0:
        time.sleep(rust)
    _laatste = time.monotonic()


def _vraag(adres: str, extra_kop: Optional[dict] = None) -> dict:
    """Eén adres ophalen, met geduld bij een 503.

    MusicBrainz antwoordt met 503 zodra je te snel gaat -- niet als storing maar
    als rem. Doorgaan alsof er niets aan de hand is levert dan een leeg
    antwoord op, en dat is erger dan wachten: het ziet eruit als "onbekende
    artiest" terwijl de bron hem gewoon kent. Vandaar opnieuw proberen met een
    oplopende pauze, en een mislukking NIET opslaan.
    """
    for poging in range(POGINGEN):
        _wacht()
        try:
            antwoord = requests.get(adres, headers={**KOP, **(extra_kop or {})},
                                    timeout=25)
            if antwoord.status_code in (429, 503):
                time.sleep(float(antwoord.headers.get("Retry-After", 0))
                           or 2 ** (poging + 1))
                continue
            antwoord.raise_for_status()
            return antwoord.json()
        except Exception:
            time.sleep(2 ** (poging + 1))
    return {}


def _haal(pad: str, parameters: dict) -> dict:
    """Eén verzoek, met schijfcache. Een mislukking komt niet in de cache."""
    adres = f"{BASIS}/{pad}?{urllib.parse.urlencode(parameters)}"
    naam = hashlib.sha1(adres.encode("utf-8")).hexdigest()[:16]
    bestand = CACHE / f"{naam}.json"
    if bestand.exists():
        return json.loads(bestand.read_text(encoding="utf-8"))
    uit = _vraag(adres)
    if uit:
        CACHE.mkdir(parents=True, exist_ok=True)
        bestand.write_text(json.dumps(uit, ensure_ascii=False), encoding="utf-8")
    return uit


def _plat(tekst: str) -> str:
    """Vergelijkbare vorm: zonder accenten, leestekens en hoofdletters."""
    tekst = unicodedata.normalize("NFKD", tekst or "")
    tekst = "".join(c for c in tekst if not unicodedata.combining(c)).lower()
    return "".join(c for c in tekst if c.isalnum() or c == " ").strip()


def zoek_artiest(naam: str, limiet: int = 12) -> list[dict]:
    """Wat kent MusicBrainz onder deze naam?"""
    antwoord = _haal("artist", {"query": naam, "fmt": "json", "limit": limiet})
    return antwoord.get("artists", [])


def canonieke_artiest(naam: str, minimum: int = 85) -> Optional[dict]:
    """De naam zoals MusicBrainz hem schrijft, of None als het onduidelijk is.

    "Onduidelijk" is hier een echt antwoord en geen mislukking. Twee artiesten
    die allebei goed scoren op dezelfde naam (er zijn drie bands die Nirvana
    heten) leveren geen oordeel op, en dat is beter dan een gok.
    """
    kaal = _plat(naam)
    zonder = kaal[4:] if kaal.startswith("the ") else kaal
    treffers = [
        a for a in zoek_artiest(naam)
        if a.get("score", 0) >= minimum
        and _plat(a.get("name", "")) in (kaal, zonder, f"the {zonder}")
    ]
    if not treffers:
        return None
    # Meerdere echte naamgenoten: geen oordeel. Verschillende schrijfwijzen van
    # dezelfde naam mogen wel, dan wint de hoogste score.
    namen = {_plat(a["name"]) for a in treffers}
    if len({n[4:] if n.startswith("the ") else n for n in namen}) > 1:
        return None
    beste = max(treffers, key=lambda a: a.get("score", 0))
    return {
        "naam": beste["name"],
        "score": beste.get("score"),
        "id": beste.get("id"),
        "land": beste.get("country"),
        "toelichting": beste.get("disambiguation", ""),
        "naamgenoten": len({a["id"] for a in treffers}),
    }


def zoek_opname(artiest: str, titel: str, limiet: int = 10) -> list[dict]:
    """Opnamen (nummers) van een artiest met een titel die erop lijkt."""
    vraag = f'artist:"{artiest}" AND recording:"{titel}"'
    antwoord = _haal("recording", {"query": vraag, "fmt": "json", "limit": limiet})
    return antwoord.get("recordings", [])


def canonieke_titel(artiest: str, titels: list[str],
                    minimum: int = 90) -> Optional[str]:
    """Welke van twee schrijfwijzen kent MusicBrainz?

    Geeft de titel terug zoals de bron hem schrijft, mits precies één van de
    aangeboden schrijfwijzen erop lijkt. Kent de bron ze allebei (of geen van
    beide), dan is er geen oordeel.
    """
    gevonden = {}
    for titel in titels:
        for opname in zoek_opname(artiest, titel):
            if opname.get("score", 0) < minimum:
                continue
            if _plat(opname.get("title", "")) == _plat(titel):
                gevonden[titel] = opname["title"]
                break
    return gevonden.get(titels[0]) if len(gevonden) == 1 and titels[0] in gevonden \
        else (list(gevonden.values())[0] if len(gevonden) == 1 else None)


# --- Discogs ---------------------------------------------------------------
#
# Waar MusicBrainz een catalogus van nummers is, is Discogs een catalogus van
# PLATEN. Dat verschil is hier precies het punt: een hitlijst noteert niet hoe
# een nummer heet maar wat er in de winkel lag, en dat kan per land verschillen.
# Georgie Fame stond in Nederland als "Yeah, Yeh, Yeh" op het label terwijl het
# nummer "Yeh, Yeh" heet. Discogs kent het land van uitgave; MusicBrainz geeft
# dat niet zo makkelijk prijs.
#
# Bijkomend voordeel: klein Nederlands repertoire uit de jaren zestig en
# zeventig staat er wél in. Gaby Dirne presents: The Valentino's, de Buddy's,
# Marijke Mulder -- alle drie onvindbaar bij MusicBrainz en gewoon aanwezig op
# Discogs, met hoes en al.
#
# De zoek-API werkt zonder sleutel zolang je je aan de rem houdt: 25 verzoeken
# per minuut voor wie zich niet aanmeldt, vandaar de ruime pauze hieronder.
DISCOGS = "https://api.discogs.com/database/search"
# Zonder sleutel staat Discogs 25 verzoeken per minuut toe, met sleutel 60.
DISCOGS_PAUZE_KAAL = 2.6
DISCOGS_PAUZE_SLEUTEL = 1.1
DISCOGS_INSTELLINGEN = ROOT / "discogs.ini"


def _discogs_sleutel() -> Optional[str]:
    """De persoonlijke sleutel uit discogs.ini, als die er is.

    Het bestand staat in .gitignore, net als webapp.ini en mail.ini: een sleutel
    hoort niet in een openbare repository. Zonder bestand werkt alles gewoon,
    alleen langzamer.

        [discogs]
        token = ...
    """
    if not DISCOGS_INSTELLINGEN.exists():
        return None
    import configparser

    parser = configparser.ConfigParser()
    parser.read(DISCOGS_INSTELLINGEN, encoding="utf-8")
    return parser.get("discogs", "token", fallback="").strip() or None


def zoek_uitgave(artiest: str, titel: str, land: str = "Netherlands",
                 limiet: int = 25) -> list[dict]:
    """Platen van deze artiest met deze titel. Nederlandse persingen eerst.

    Geeft per uitgave de credit zoals die op de plaat staat, het jaar en het
    land -- genoeg om te zien onder welke naam iets hier is uitgebracht.
    """
    global _laatste
    parameters = {"artist": artiest, "track": titel, "type": "release",
                  "per_page": str(limiet)}
    adres = f"{DISCOGS}?{urllib.parse.urlencode(parameters)}"
    naam = "discogs-" + hashlib.sha1(adres.encode("utf-8")).hexdigest()[:16]
    bestand = CACHE / f"{naam}.json"
    if bestand.exists():
        antwoord = json.loads(bestand.read_text(encoding="utf-8"))
    else:
        sleutel = _discogs_sleutel()
        pauze = DISCOGS_PAUZE_SLEUTEL if sleutel else DISCOGS_PAUZE_KAAL
        rust = pauze - (time.monotonic() - _laatste)
        if rust > 0:
            time.sleep(rust)
        _laatste = time.monotonic()
        antwoord = _vraag(adres, extra_kop=(
            {"Authorization": f"Discogs token={sleutel}"} if sleutel else None))
        if antwoord:
            CACHE.mkdir(parents=True, exist_ok=True)
            bestand.write_text(json.dumps(antwoord, ensure_ascii=False),
                               encoding="utf-8")

    uit = []
    for r in antwoord.get("results", []):
        heel = r.get("title") or ""          # Discogs levert "Artiest - Titel"
        credit, _, plaattitel = heel.partition(" - ")
        uit.append({"artiest": credit.strip(), "titel": plaattitel.strip(),
                    "jaar": r.get("year"), "land": r.get("country"),
                    "label": (r.get("label") or [None])[0]})
    # Nederlandse persingen eerst: die noteerden hier.
    uit.sort(key=lambda r: (r["land"] != land, r["jaar"] or "9999"))
    return uit


def wikipedia_bestaat(naam: str, taal: str = "nl") -> Optional[str]:
    """Heeft Wikipedia een artikel onder deze naam? Zo ja, de echte titel.

    Tweede mening voor Nederlandse artiesten, die in MusicBrainz mager staan.
    Een doorverwijzing telt mee: dat is juist het bewijs dat de ene schrijfwijze
    naar de andere leidt.
    """
    adres = (f"https://{taal}.wikipedia.org/w/api.php?action=query&redirects=1"
             f"&format=json&titles={urllib.parse.quote(naam)}")
    naam_bestand = hashlib.sha1(adres.encode("utf-8")).hexdigest()[:16]
    bestand = CACHE / f"wiki-{naam_bestand}.json"
    if bestand.exists():
        antwoord = json.loads(bestand.read_text(encoding="utf-8"))
    else:
        antwoord = _vraag(adres)
        if antwoord:
            CACHE.mkdir(parents=True, exist_ok=True)
            bestand.write_text(json.dumps(antwoord, ensure_ascii=False),
                               encoding="utf-8")

    paginas = antwoord.get("query", {}).get("pages", {})
    for nummer, pagina in paginas.items():
        if nummer != "-1" and "missing" not in pagina:
            return pagina.get("title")
    return None
