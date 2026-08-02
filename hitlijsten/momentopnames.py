"""Momentopnames van de database, zodat een fout terug te draaien is.

WAAROM DIT NAAST `wijzigingen` BESTAAT
--------------------------------------
De tabel `wijzigingen` schrijft op wát er is veranderd, van wat naar wat en
waarom. Dat is een logboek en geen terugdraaiknop: bij een samenvoeging van
duizenden noteringen staat er één regel met een samenvatting, en daar bouw je de
oude toestand niet uit terug. Voor "even terug naar hoe het vanmorgen was" heb
je het hele bestand nodig.

HOE DE KOPIE WORDT GEMAAKT
--------------------------
Met `VACUUM INTO` en niet met `cp`. Een sqlite-bestand kopiëren terwijl de
webapplicatie erin leest levert een halve transactie op als het toevallig net
misgaat; `VACUUM INTO` maakt binnen één transactie een compleet, opgeruimd
bestand. Dat kan gewoon terwijl alles doordraait.

Daarna gaat het door gzip. Een database van 91 MB komt op ongeveer een kwart
uit, en dan kost twintig momentopnames minder dan een halve gigabyte.

WAT ER WORDT BEWAARD
--------------------
De laatste `RECENT` stuks, plus van elke dag de oudste (dus de toestand van vóór
de eerste wijziging die dag) tot `DAGEN` terug. Zo heb je de kleine stapjes van
vandaag én de grote sprongen van de afgelopen weken, zonder dat het aantal
oneindig groeit.

DIT IS GEEN BACK-UP
-------------------
Het staat op dezelfde schijf als het origineel. Tegen een verkeerde opdracht
helpt het, tegen een kapot volume niet. Daarvoor is er het snapshotschema van de
NAS (sinds 2 augustus 2026 ook op deze share) en Hyper Backup. Die twee vullen
elkaar aan: een snapshot bewaart de hele share en overleeft een verwijderde map,
deze kopieën zitten er juist in en zijn met een knop terug te zetten.
"""
from __future__ import annotations

import gzip
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from . import db

__all__ = ["maak", "lijst", "opruimen", "terugzetten", "MAP"]

MAP = db.DB_PATH.parent / "momentopnames"
RECENT = 12          # altijd de laatste twaalf bewaren
DAGEN = 30           # en per dag de oudste, tot dertig dagen terug
ACHTERVOEGSEL = ".sqlite.gz"


def _naam(reden: str, moment: datetime) -> str:
    veilig = "".join(c if c.isalnum() or c in "-_" else "-" for c in reden)[:40]
    return f"{moment.strftime('%Y%m%d-%H%M%S')}-{veilig}{ACHTERVOEGSEL}"


def maak(reden: str = "handmatig") -> Path:
    """Een momentopname van de database. Geeft het pad terug.

    `reden` komt in de bestandsnaam terecht, zodat je in de map kunt zien
    waarom hij er staat -- "voor-opschonen" leest nu eenmaal prettiger dan een
    tijdstempel alleen.
    """
    MAP.mkdir(parents=True, exist_ok=True)
    doel = MAP / _naam(reden, datetime.now())

    with tempfile.TemporaryDirectory() as tijdelijk:
        kaal = Path(tijdelijk) / "kopie.sqlite"
        # VACUUM INTO in plaats van kopiëren: dat werkt binnen één transactie,
        # dus ook terwijl de webapplicatie in de database leest.
        con = sqlite3.connect(db.DB_PATH)
        try:
            con.execute("VACUUM INTO ?", (str(kaal),))
        finally:
            con.close()
        with open(kaal, "rb") as bron, gzip.open(doel, "wb", compresslevel=6) as uit:
            shutil.copyfileobj(bron, uit, length=1024 * 1024)
    return doel


def lijst() -> list[Path]:
    """Alle momentopnames, nieuwste eerst."""
    if not MAP.exists():
        return []
    return sorted(MAP.glob(f"*{ACHTERVOEGSEL}"), reverse=True)


def _dag(pad: Path) -> str:
    return pad.name[:8]


def opruimen() -> list[Path]:
    """Verwijder wat buiten het bewaarbeleid valt. Geeft terug wat er weg is.

    De laatste `RECENT` blijven altijd staan. Van elke dag daarvoor blijft de
    oudste over -- dat is de toestand van vóór de eerste ingreep van die dag, en
    dus precies het punt waar je naar terug wilt.
    """
    alles = lijst()
    houden = set(alles[:RECENT])
    grens = (datetime.now() - timedelta(days=DAGEN)).strftime("%Y%m%d")
    per_dag: dict[str, Path] = {}
    for pad in alles:
        if _dag(pad) >= grens:
            per_dag[_dag(pad)] = pad          # aflopend gesorteerd -> de oudste wint
    houden |= set(per_dag.values())

    weg = [p for p in alles if p not in houden]
    for pad in weg:
        pad.unlink()
    return weg


def terugzetten(pad: Path | str) -> Path:
    """Zet een momentopname terug. De huidige database wordt eerst bewaard.

    Die volgorde is geen beleefdheid maar noodzaak: teruggaan naar gisteren is
    zelf ook een ingreep, en die wil je net zo goed kunnen terugdraaien als
    blijkt dat je de verkeerde hebt gekozen.
    """
    pad = Path(pad)
    if not pad.exists():
        pad = MAP / pad.name
    if not pad.exists():
        raise FileNotFoundError(f"geen momentopname: {pad}")

    veiligheid = maak("voor-terugzetten")
    with tempfile.NamedTemporaryFile(dir=str(db.DB_PATH.parent), delete=False,
                                     suffix=".sqlite") as tijdelijk:
        nieuw = Path(tijdelijk.name)
    with gzip.open(pad, "rb") as bron, open(nieuw, "wb") as uit:
        shutil.copyfileobj(bron, uit, length=1024 * 1024)
    # Controleer dat het uitgepakte bestand echt een database is voordat de
    # huidige eraan gaat.
    con = sqlite3.connect(nieuw)
    try:
        aantal = con.execute("SELECT COUNT(*) FROM noteringen").fetchone()[0]
    finally:
        con.close()
    if not aantal:
        nieuw.unlink()
        raise ValueError(f"{pad.name} bevat geen noteringen -- niet teruggezet")
    nieuw.replace(db.DB_PATH)
    return veiligheid
