"""Opslag van alle noteringen in sqlite.

De database is de enige bron voor de Excel-bouwer. Opnieuw ophalen is nooit nodig
om de bestanden opnieuw te genereren.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Iterator

from .config import DATA_DIR, DB_PATH
from .datums import vrijdag_van
from .models import Notering

SCHEMA = """
-- De primaire sleutel is een simpele rijteller, met opzet.
--
-- Positie mag er niet in zitten. Hitlijsten kennen gedeelde posities: in de
-- Tipparade van 2004 week 39 staan twee nummers op 27. En in de jaren zestig
-- stonden er meerdere artiesten met hetzelfde nummer op een en dezelfde
-- positie -- dan helpt zelfs (positie, sleutel) niet meer, want die rijen
-- kunnen op elk veld gelijk zijn.
--
-- Een rijteller maakt geen enkele aanname over wat uniek is. Dubbele rijen
-- worden niet door de database tegengehouden maar door bewaar_week(), dat een
-- week eerst volledig wist en daarna in een savepoint opnieuw wegschrijft.
CREATE TABLE IF NOT EXISTS noteringen (
    id               INTEGER PRIMARY KEY,
    lijst            TEXT    NOT NULL,
    jaar             INTEGER NOT NULL,
    week             INTEGER NOT NULL,
    positie          INTEGER NOT NULL,
    titel            TEXT    NOT NULL,
    artiest          TEXT    NOT NULL,
    label            TEXT,
    weken_genoteerd  INTEGER,
    vorige_positie   INTEGER,
    site_status      TEXT    NOT NULL,
    sleutel          TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_noteringen_sleutel
    ON noteringen (lijst, jaar, sleutel);
CREATE INDEX IF NOT EXISTS idx_noteringen_week
    ON noteringen (lijst, jaar, week);

CREATE TABLE IF NOT EXISTS opgehaald (
    lijst        TEXT    NOT NULL,
    jaar         INTEGER NOT NULL,
    week         INTEGER NOT NULL,
    aantal       INTEGER NOT NULL,
    opgehaald_op TEXT    NOT NULL,
    PRIMARY KEY (lijst, jaar, week)
);

-- Nummers die onder twee sleutels binnenkomen en samengevoegd moeten worden.
-- Ketens mogen: a->b en b->c laat a, b en c allemaal op c uitkomen.
CREATE TABLE IF NOT EXISTS aliases (
    van        TEXT PRIMARY KEY,
    naar       TEXT NOT NULL,
    opmerking  TEXT,
    aangemaakt TEXT
);

-- Het omgekeerde: paren die op elkaar lijken en dicht op elkaar noteerden,
-- maar aantoonbaar losse nummers zijn. Zonder deze lijst stelt `controle` ze
-- elke keer opnieuw voor.
CREATE TABLE IF NOT EXISTS niet_samenvoegen (
    sleutel_a  TEXT NOT NULL,
    sleutel_b  TEXT NOT NULL,
    reden      TEXT,
    aangemaakt TEXT,
    PRIMARY KEY (sleutel_a, sleutel_b)
);

-- Elke handmatige wijziging via de webapplicatie. Zonder dit logboek zou een
-- correctie niet te onderscheiden zijn van wat de bron zelf leverde, en dat is
-- precies wat je later wilt kunnen nazoeken.
CREATE TABLE IF NOT EXISTS wijzigingen (
    id        INTEGER PRIMARY KEY,
    tijdstip  TEXT NOT NULL,
    soort     TEXT NOT NULL,   -- notering | alias | niet_samenvoegen
    verwijst  TEXT,            -- welke rij of sleutel
    veld      TEXT,
    oud       TEXT,
    nieuw     TEXT,
    reden     TEXT
);

-- Weken die aantoonbaar niet bestaan: week 53 in een jaar met 52 weken, of een
-- lijst die een week oversloeg (Sterren NL had geen week 52 in 2025). Zonder
-- deze administratie probeert de wekelijkse run ze eeuwig opnieuw en meldt hij
-- elke keer een mislukking die geen mislukking is.
CREATE TABLE IF NOT EXISTS bestaat_niet (
    lijst         TEXT    NOT NULL,
    jaar          INTEGER NOT NULL,
    week          INTEGER NOT NULL,
    reden         TEXT    NOT NULL,
    vastgesteld   TEXT    NOT NULL,
    PRIMARY KEY (lijst, jaar, week)
);
"""


def _migreer_primaire_sleutel(con: sqlite3.Connection) -> None:
    """Bouw `noteringen` om naar de rijteller als dat nog niet gebeurd is.

    Eerdere versies gebruikten (lijst, jaar, week, positie) en daarna
    (lijst, jaar, week, positie, sleutel) als primaire sleutel. Allebei leggen
    ze een uniciteit op die hitlijsten niet kennen. sqlite kan een primaire
    sleutel niet wijzigen, dus de tabel wordt hernoemd, opnieuw aangemaakt en
    overgekopieerd.
    """
    rij = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='noteringen'"
    ).fetchone()
    if rij is None or "id               INTEGER PRIMARY KEY" in rij[0]:
        return  # nog geen tabel, of al gemigreerd

    con.executescript(
        """
        ALTER TABLE noteringen RENAME TO noteringen_oud;
        DROP INDEX IF EXISTS idx_noteringen_sleutel;
        DROP INDEX IF EXISTS idx_noteringen_week;
        """
    )
    con.executescript(SCHEMA)
    con.execute(
        "INSERT INTO noteringen (lijst, jaar, week, positie, titel, artiest, label,"
        " weken_genoteerd, vorige_positie, site_status, sleutel)"
        " SELECT lijst, jaar, week, positie, titel, artiest, label,"
        " weken_genoteerd, vorige_positie, site_status, sleutel FROM noteringen_oud"
    )
    con.execute("DROP TABLE noteringen_oud")
    con.commit()


@contextmanager
def verbinding() -> Iterator[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(SCHEMA)
        _migreer_primaire_sleutel(con)
        yield con
        con.commit()
    finally:
        con.close()


def bewaar_week(
    con: sqlite3.Connection, lijst: str, jaar: int, week: int, noteringen: Iterable[Notering]
) -> int:
    """Schrijf één week weg; vervangt wat er al stond voor die week."""
    from .normalize import sleutel_van

    rijen = [
        (
            n.lijst, n.jaar, n.week, n.positie, n.titel, n.artiest, n.label,
            n.weken_genoteerd, n.vorige_positie, n.site_status,
            sleutel_van(n.artiest, n.titel),
        )
        for n in noteringen
    ]
    # Alles of niets: gaat er halverwege iets mis, dan mag er geen halve week
    # blijven staan. Die zou daarna als "al opgehaald" gelden en stil verkeerde
    # punten opleveren.
    con.execute("SAVEPOINT week")
    try:
        con.execute(
            "DELETE FROM noteringen WHERE lijst=? AND jaar=? AND week=?",
            (lijst, jaar, week),
        )
        con.executemany(
            "INSERT INTO noteringen (lijst, jaar, week, positie, titel, artiest, label,"
            " weken_genoteerd, vorige_positie, site_status, sleutel)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            rijen,
        )
        con.execute(
            "INSERT OR REPLACE INTO opgehaald (lijst, jaar, week, aantal, opgehaald_op)"
            " VALUES (?,?,?,?,?)",
            (lijst, jaar, week, len(rijen), datetime.now().isoformat(timespec="seconds")),
        )
    except Exception:
        con.execute("ROLLBACK TO SAVEPOINT week")
        raise
    finally:
        con.execute("RELEASE SAVEPOINT week")
    return len(rijen)


def markeer_bestaat_niet(
    con: sqlite3.Connection, lijst: str, jaar: int, week: int, reden: str
) -> None:
    """Leg vast dat een week aantoonbaar niet bestaat, zodat we hem loslaten."""
    con.execute(
        "INSERT OR REPLACE INTO bestaat_niet (lijst, jaar, week, reden, vastgesteld)"
        " VALUES (?,?,?,?,?)",
        (lijst, jaar, week, reden, datetime.now().isoformat(timespec="seconds")),
    )


def onbestaande_weken(con: sqlite3.Connection, lijst: str, jaar: int) -> set[int]:
    return {
        r["week"]
        for r in con.execute(
            "SELECT week FROM bestaat_niet WHERE lijst=? AND jaar=?", (lijst, jaar)
        )
    }


def bekende_weken(con: sqlite3.Connection, lijst: str, jaar: int) -> set[int]:
    return {
        r["week"]
        for r in con.execute(
            "SELECT week FROM opgehaald WHERE lijst=? AND jaar=?", (lijst, jaar)
        )
    }


def noteringen_van_jaar(con: sqlite3.Connection, lijst: str, jaar: int) -> list[sqlite3.Row]:
    return list(
        con.execute(
            "SELECT * FROM noteringen WHERE lijst=? AND jaar=?"
            " ORDER BY week, positie",
            (lijst, jaar),
        )
    )


# Hoever we voor en na het jaar meekijken om een doorlopende notering te volgen.
# Twee jaar is ruim: de langst genoteerde nummers halen geen honderd aaneen-
# gesloten weken, en de lus stopt zodra er een week ontbreekt.
BUURJAREN = 2


@dataclass(frozen=True)
class Looptijd:
    """De echte begin- en einddatum van een notering rond een jaargrens.

    ``begin`` en ``eind`` zijn de uitzendvrijdagen van de eerste en de laatste
    week van de aaneengesloten reeks waar dit jaar deel van uitmaakt -- die kan
    dus in december van het vorige jaar beginnen of in januari van het volgende
    jaar aflopen. ``begon_eerder`` en ``loopt_door`` zeggen of dat het geval is,
    zodat een overzicht dat kan tonen.
    """

    begin: date
    eind: date
    begon_eerder: bool
    loopt_door: bool


def looptijden(
    con: sqlite3.Connection, lijst: str, jaar: int
) -> dict[str, Looptijd]:
    """Per sleutel van dit jaar de werkelijke eerste en laatste uitzenddatum.

    Een nummer dat in week 50 binnenkomt en tot week 6 blijft staan, staat in
    twee jaargangen met een afgekapte reeks. Door de weken van de buurjaren als
    datums naast elkaar te leggen en van de eigen reeks af terug en vooruit te
    lopen, komt de hele periode boven water. De lus stopt bij het eerste gat,
    zodat een re-entry in maart niet aan december wordt geplakt.

    Belangrijk: de stap gaat naar de vorige of volgende week die daadwerkelijk
    is uitgezonden, niet botweg zeven dagen terug. De Top 40 slaat de laatste
    week van december meestal over voor een jaaroverzicht -- bij negentien van
    de tweeenzestig jaargangen. Zou de lus zeven dagen eisen, dan brak hij juist
    op de jaargrens waar het hier om begonnen is.
    """
    per_sleutel: dict[str, set[date]] = {}
    uitgezonden: set[date] = set()
    for sleutel, rij_jaar, week in con.execute(
        "SELECT sleutel, jaar, week FROM noteringen"
        " WHERE lijst=? AND jaar BETWEEN ? AND ?",
        (lijst, jaar - BUURJAREN, jaar + BUURJAREN),
    ):
        datum = vrijdag_van(rij_jaar, week)
        per_sleutel.setdefault(sleutel, set()).add(datum)
        uitgezonden.add(datum)

    eigen: dict[str, set[date]] = {}
    for sleutel, week in con.execute(
        "SELECT sleutel, week FROM noteringen WHERE lijst=? AND jaar=?",
        (lijst, jaar),
    ):
        eigen.setdefault(sleutel, set()).add(vrijdag_van(jaar, week))

    kalender = sorted(uitgezonden)
    volgnummer = {datum: nr for nr, datum in enumerate(kalender)}

    uitkomst: dict[str, Looptijd] = {}
    for sleutel, dit_jaar in eigen.items():
        alle = per_sleutel.get(sleutel, dit_jaar)
        eerste, laatste = min(dit_jaar), max(dit_jaar)
        vroeg, laat = volgnummer[eerste], volgnummer[laatste]
        while vroeg > 0 and kalender[vroeg - 1] in alle:
            vroeg -= 1
        while laat + 1 < len(kalender) and kalender[laat + 1] in alle:
            laat += 1
        uitkomst[sleutel] = Looptijd(
            begin=kalender[vroeg],
            eind=kalender[laat],
            begon_eerder=kalender[vroeg] < eerste,
            loopt_door=kalender[laat] > laatste,
        )
    return uitkomst
