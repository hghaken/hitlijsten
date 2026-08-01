"""HTML ophalen met een schijfcache.

De cache is het belangrijkste onderdeel: eenmaal opgehaalde weken veranderen niet
meer, dus tijdens het bouwen en debuggen van parsers gaat er geen enkel verzoek
meer naar de sites.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import requests

from .config import CACHE_DIR, LIJSTEN, ROOT, url_voor

# www.top40.nl levert een incomplete certificaatketen: het stuurt het verkeerde
# Sectigo-tussencertificaat mee, waardoor het servercertificaat niet te
# verifieren is. Browsers halen het ontbrekende certificaat zelf op (AIA);
# Python doet dat niet en faalt met CERTIFICATE_VERIFY_FAILED. certifi lost dit
# nooit op, hoe je het ook instelt. oranjetop30.nl heeft dit probleem niet.
#
# Op de NAS -- waar dit draait -- kent geen enkele systeemstore dat certificaat,
# dus leveren we het zelf mee in certificaten/sectigo-dv-r36.pem en plakken het
# achter de certifi-bundel.
#
# De truststore-tak hieronder is een overblijfsel uit de tijd dat dit op een
# Windows-pc draaide: daar zit het ontbrekende tussencertificaat wel in de
# systeemstore. Hij blijft staan omdat hij niets kost en het project daarmee ook
# op een werkstation te draaien is.
#
# In beide gevallen blijft de certificaatcontrole gewoon aan staan.
EIGEN_BUNDEL: Path | None = None


def _stel_certificaten_in() -> None:
    global EIGEN_BUNDEL
    try:
        import truststore

        truststore.inject_into_ssl()
        return
    except ImportError:
        pass

    aanvulling = ROOT / "certificaten" / "sectigo-dv-r36.pem"
    if not aanvulling.exists():
        return

    import certifi

    bundel = CACHE_DIR / "ca-bundel.pem"
    bundel.parent.mkdir(parents=True, exist_ok=True)
    if not bundel.exists() or bundel.stat().st_mtime < aanvulling.stat().st_mtime:
        bundel.write_bytes(
            Path(certifi.where()).read_bytes() + b"\n" + aanvulling.read_bytes()
        )
    EIGEN_BUNDEL = bundel


_stel_certificaten_in()

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
PAUZE_SECONDEN = 2.0
TIMEOUT = 30

_laatste_verzoek = 0.0


def cache_pad(lijst: str, jaar: int, week: int) -> Path:
    return CACHE_DIR / lijst / f"{jaar}-w{week:02d}.html"


def haal_html(
    lijst: str, jaar: int, week: int, *, forceer: bool = False, pauze: float | None = None
) -> str:
    """Geef de HTML van één lijstpagina; uit cache tenzij `forceer`."""
    global _laatste_verzoek

    pad = cache_pad(lijst, jaar, week)
    if pad.exists() and not forceer:
        return pad.read_text(encoding="utf-8")

    wacht = PAUZE_SECONDEN if pauze is None else pauze
    verstreken = time.time() - _laatste_verzoek
    if verstreken < wacht:
        time.sleep(wacht - verstreken)

    url = url_voor(lijst, jaar, week)
    respons = requests.get(
        url, headers={"User-Agent": UA}, timeout=TIMEOUT,
        **({"verify": str(EIGEN_BUNDEL)} if EIGEN_BUNDEL else {}),
    )
    _laatste_verzoek = time.time()
    respons.raise_for_status()

    # Beide sites zijn utf-8; requests raadt soms iso-8859-1 bij een vage header.
    if not respons.encoding or respons.encoding.lower() == "iso-8859-1":
        respons.encoding = "utf-8"
    html = respons.text

    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_text(html, encoding="utf-8")
    return html


def in_cache(lijst: str, jaar: int, week: int) -> bool:
    return cache_pad(lijst, jaar, week).exists()


def gooi_cache_weg(lijst: str, jaar: int, week: int) -> None:
    """Verwijder een gecachete pagina, zodat een volgende run hem opnieuw haalt."""
    cache_pad(lijst, jaar, week).unlink(missing_ok=True)


# Beide sites zetten de laatst gepubliceerde week in de paginatitel:
#   top40.nl        <title>Top 40-lijst van week 30, 2026</title>
#   oranjetop30.nl  <title>Oranje Top 30 - Week 30 - Jaargang 2026</title>
# Dat is betrouwbaarder dan zelf het ISO-weeknummer uitrekenen: de lijsten lopen
# een week achter op de kalender, en die achterstand is niet gegarandeerd vast.
_WEEK_IN_TITEL = (
    re.compile(r"van\s+week\s+(\d{1,2}),\s*(\d{4})", re.I),
    re.compile(r"Week\s+(\d{1,2})\s*-\s*Jaargang\s+(\d{4})", re.I),
)


def week_uit_titel(html: str) -> tuple[int, int] | None:
    """Lees (jaar, week) uit de paginatitel; None als het er niet in staat."""
    titel_match = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    if not titel_match:
        return None
    for patroon in _WEEK_IN_TITEL:
        m = patroon.search(titel_match.group(1))
        if m:
            return int(m.group(2)), int(m.group(1))
    return None


def controleer_gevraagde_week(html: str, jaar: int, week: int) -> None:
    """Sla alarm als de site een andere week teruggaf dan gevraagd.

    Vraag je een jaargang op die een site niet heeft, dan geeft hij geen 404
    maar stilletjes een andere lijst: oranjetop30.nl levert de nieuwste week,
    top40.nl levert bij sterren-nl-top25 de oudste die ze hebben. Zonder deze
    controle schrijven we die als echte historie weg.
    """
    gevonden = week_uit_titel(html)
    if gevonden is None:
        return  # geen titel om op te varen; de structuurcontrole moet het doen
    if gevonden != (jaar, week):
        raise WekenKomenNietOvereen(
            f"gevraagd {jaar} week {week}, maar de pagina is van "
            f"{gevonden[0]} week {gevonden[1]}"
        )


class WekenKomenNietOvereen(Exception):
    """De site gaf een andere week terug dan gevraagd."""


def laatst_gepubliceerd(lijst: str) -> tuple[int, int]:
    """Geef (jaar, week) van de nieuwste lijst volgens de site zelf."""
    cfg = LIJSTEN[lijst]
    if cfg["site"] == "top40nl":
        url = f"https://www.top40.nl/{cfg['slug']}"
    else:
        url = "https://www.oranjetop30.nl/"

    respons = requests.get(
        url, headers={"User-Agent": UA}, timeout=TIMEOUT,
        **({"verify": str(EIGEN_BUNDEL)} if EIGEN_BUNDEL else {}),
    )
    respons.raise_for_status()
    if not respons.encoding or respons.encoding.lower() == "iso-8859-1":
        respons.encoding = "utf-8"

    titel_match = re.search(r"<title>(.*?)</title>", respons.text, re.S | re.I)
    titel = titel_match.group(1) if titel_match else ""
    for patroon in _WEEK_IN_TITEL:
        m = patroon.search(titel)
        if m:
            return int(m.group(2)), int(m.group(1))
    raise RuntimeError(
        f"kon het weeknummer niet uit de titel van {url} halen: {titel.strip()!r}"
    )
