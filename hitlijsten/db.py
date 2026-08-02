"""Opslag van alle noteringen in sqlite.

De database is de enige bron voor de Excel-bouwer. Opnieuw ophalen is nooit nodig
om de bestanden opnieuw te genereren.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Iterator, Optional

from .config import DATA_DIR, DB_PATH
from .datums import als_tekst, vrijdag_van
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
    sleutel          TEXT    NOT NULL,
    -- Alleen de Top 2000 vult dit: het jaar waarin het nummer uitkwam. De
    -- weeklijsten kennen dat gegeven niet en laten het leeg.
    uitjaar          INTEGER
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

-- De vastgestelde schrijfwijze van een artiest, per artiestsleutel. Nodig
-- omdat de bronnen het oneens zijn: "Beatles" tegen "The Beatles", "coldplay"
-- tegen "Coldplay". Zonder deze tabel zou zo'n correctie bij de volgende
-- vrijdagrun weer ongedaan gemaakt worden door de bron zelf.
CREATE TABLE IF NOT EXISTS artiestnamen (
    sleutel    TEXT PRIMARY KEY,   -- de artiestsleutel, zonder titel
    naam       TEXT NOT NULL,      -- zo hoort hij te staan
    bron       TEXT,               -- musicbrainz | meerderheid | hand
    aangemaakt TEXT
);

-- Hetzelfde voor de titel, per volledige sleutel. Nodig om dezelfde reden:
-- "Beggin" in de Top 40 en "Beggin'" in de Top 4000 is een nummer, en dan hoort
-- er ook een schrijfwijze te staan.
CREATE TABLE IF NOT EXISTS titelnamen (
    sleutel    TEXT PRIMARY KEY,   -- de volledige sleutel, artiest en titel
    naam       TEXT NOT NULL,
    bron       TEXT,
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


def _voeg_uitjaar_toe(con: sqlite3.Connection) -> None:
    """Voeg de kolom `uitjaar` toe aan een database die hem nog niet heeft."""
    kolommen = {r[1] for r in con.execute("PRAGMA table_info(noteringen)")}
    if kolommen and "uitjaar" not in kolommen:
        con.execute("ALTER TABLE noteringen ADD COLUMN uitjaar INTEGER")
        con.commit()


@contextmanager
def verbinding() -> Iterator[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(SCHEMA)
        _migreer_primaire_sleutel(con)
        _voeg_uitjaar_toe(con)
        yield con
        con.commit()
    finally:
        con.close()


def bewaar_week(
    con: sqlite3.Connection, lijst: str, jaar: int, week: int, noteringen: Iterable[Notering]
) -> int:
    """Schrijf één week weg; vervangt wat er al stond voor die week."""
    from .normalize import sleutel_van
    from .opschonen import schoon_tekst, splits_kanten

    # Leestekens hier rechtzetten en niet in de parsers: dan geldt het voor elke
    # bron, ook voor een bron die er later bij komt. Hetzelfde geldt voor de
    # dubbele A-kant: top40.nl levert "No Reply ; Rock And Roll Music" als een
    # regel, en dat worden hier twee noteringen op dezelfde positie.
    rijen = [
        (
            n.lijst, n.jaar, n.week, n.positie, schoon_tekst(titel),
            schoon_tekst(artiest), n.label,
            n.weken_genoteerd, n.vorige_positie, n.site_status,
            sleutel_van(artiest, titel),
        )
        for n in noteringen
        for artiest, titel in splits_kanten(n.artiest, n.titel)
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


def _kalender(
    con: sqlite3.Connection, lijst: str, jaar: int
) -> tuple[list[date], dict[date, tuple[int, int]], dict[date, int]]:
    """Alle uitgezonden weken rond dit jaar, op datum.

    Geeft drie dingen terug: de datums op volgorde, per datum de (jaar, week)
    waar hij bij hoort, en per datum de lengte van de lijst die week. Die lengte
    is het hoogste positienummer dat er die week in staat -- de Tipparade telde
    ooit twintig noteringen en later dertig.
    """
    volgorde: dict[date, tuple[int, int]] = {}
    lengte: dict[date, int] = {}
    for rij_jaar, week, hoogste in con.execute(
        "SELECT jaar, week, MAX(positie) FROM noteringen"
        " WHERE lijst=? AND jaar BETWEEN ? AND ? GROUP BY jaar, week",
        (lijst, jaar - BUURJAREN, jaar + BUURJAREN),
    ):
        datum = vrijdag_van(rij_jaar, week)
        volgorde[datum] = (rij_jaar, week)
        lengte[datum] = hoogste
    return sorted(volgorde), volgorde, lengte


def reeks_van(
    con: sqlite3.Connection, lijst: str, sleutel: str, jaar: int
) -> Optional[dict]:
    """De volledige aaneengesloten notering waar dit jaar deel van uitmaakt.

    Anders dan de jaarmatrix stopt deze niet bij 1 januari: een nummer dat in
    november binnenkwam en in juni uit de lijst viel, komt hier in zijn geheel
    uit, met de weken uit beide jaargangen achter elkaar. Weken waarin het
    nummer tussentijds niet noteerde staan er met ``positie: None`` in, zodat de
    grafiek het gat op de juiste plek in de tijd kan tonen.
    """
    kalender, volgorde, lengtes = _kalender(con, lijst, jaar)
    if not kalender:
        return None

    posities: dict[date, int] = {}
    dit_jaar: list[date] = []
    for rij_jaar, week, positie in con.execute(
        "SELECT jaar, week, MIN(positie) FROM noteringen"
        " WHERE lijst=? AND sleutel=? AND jaar BETWEEN ? AND ?"
        " GROUP BY jaar, week",
        (lijst, sleutel, jaar - BUURJAREN, jaar + BUURJAREN),
    ):
        datum = vrijdag_van(rij_jaar, week)
        posities[datum] = positie
        if rij_jaar == jaar:
            dit_jaar.append(datum)
    if not dit_jaar:
        return None

    volgnummer = {datum: nr for nr, datum in enumerate(kalender)}
    vroeg, laat = volgnummer[min(dit_jaar)], volgnummer[max(dit_jaar)]
    while vroeg > 0 and kalender[vroeg - 1] in posities:
        vroeg -= 1
    while laat + 1 < len(kalender) and kalender[laat + 1] in posities:
        laat += 1

    punten = 0
    weken = 0
    reeks = []
    for datum in kalender[vroeg : laat + 1]:
        rij_jaar, week = volgorde[datum]
        positie = posities.get(datum)
        if positie is not None:
            weken += 1
            punten += lengtes[datum] - positie + 1
        reeks.append({
            "jaar": rij_jaar, "week": week, "datum": als_tekst(datum),
            "positie": positie,
        })

    genoteerd = [n["positie"] for n in reeks if n["positie"] is not None]
    return {
        "reeks": reeks,
        # De schaal loopt tot de langste lijst in dit venster, zodat de grafiek
        # even hoog blijft als de lijst halverwege van lengte veranderde.
        "lengte": max(lengtes[d] for d in kalender[vroeg : laat + 1]),
        "hoogste": min(genoteerd),
        "weken": weken,
        "punten": punten,
        "van": reeks[0]["datum"],
        "tot": reeks[-1]["datum"],
    }


def decennium_totalen(
    con: sqlite3.Connection, lijst: str, decennium: int
) -> list[dict]:
    """Alle nummers uit tien jaargangen, met hun totaal over dat decennium."""
    return totalen_over(con, lijst, decennium, decennium + 9)


def alle_jaren(con: sqlite3.Connection, lijst: str) -> tuple[int, int]:
    """Eerste en laatste jaargang die van deze lijst in de database staat."""
    rij = con.execute(
        "SELECT MIN(jaar), MAX(jaar) FROM noteringen WHERE lijst=?", (lijst,)
    ).fetchone()
    return (rij[0], rij[1]) if rij and rij[0] is not None else (0, -1)


def totalen_over(
    con: sqlite3.Connection, lijst: str, van: int, tot: int
) -> list[dict]:
    """Alle nummers uit de jaargangen `van` t/m `tot`, met hun totaal.

    De punten worden per jaargang gerekend en daarna opgeteld, niet in één keer
    over de hele periode. Dat lijkt omslachtig maar houdt de lijst gelijk aan de
    som van de jaaroverzichten: waar een jaartotaal van michajans.nl wordt
    aangehouden (tabel `correcties`), telt hier hetzelfde cijfer mee.

    Punten zijn alleen binnen een lijst vergelijkbaar, en binnen een lijst alleen
    als die al die jaren even lang was. De Top 40 is dat (altijd veertig); de
    Tipparade telde ooit twintig noteringen en later dertig, dus daar levert een
    eerste plaats in verschillende jaren een ander aantal punten op.
    """
    rijen = list(con.execute(
        "SELECT jaar, week, positie, titel, artiest, label, sleutel FROM noteringen"
        " WHERE lijst=? AND jaar BETWEEN ? AND ? ORDER BY jaar, week, positie",
        (lijst, van, tot),
    ))
    if not rijen:
        return []

    lengte: dict[tuple[int, int], int] = {}
    for r in rijen:
        sleutel = (r["jaar"], r["week"])
        lengte[sleutel] = max(lengte.get(sleutel, 0), r["positie"])

    # Per nummer per jaargang de beste notering van elke week; een sleutel hoort
    # maar een keer per week voor te komen, maar bij gedeelde posities in de
    # jaren zestig staat hij er soms twee keer.
    per_jaar: dict[str, dict[int, dict[int, int]]] = {}
    naam: dict[str, tuple[str, str, Optional[str]]] = {}
    for r in rijen:
        weken = per_jaar.setdefault(r["sleutel"], {}).setdefault(r["jaar"], {})
        beste = weken.get(r["week"])
        if beste is None or r["positie"] < beste:
            weken[r["week"]] = r["positie"]
        # Laatste schrijfwijze wint; de rijen komen op volgorde binnen.
        naam[r["sleutel"]] = (r["artiest"], r["titel"], r["label"])

    correcties: dict[int, dict[str, dict]] = {}
    try:
        from .kruiscontrole import correcties_voor

        for jaar in range(van, tot + 1):
            correcties[jaar] = correcties_voor(jaar, lijst, con)
    except Exception:
        correcties = {}

    # Alleen de randjaren kunnen buiten de periode doorlopen.
    rand = {
        van: looptijden(con, lijst, van),
        tot: looptijden(con, lijst, tot),
    }

    uitkomst = []
    for sleutel, jaargangen in per_jaar.items():
        punten = weken_totaal = 0
        hoogste = None
        gecorrigeerd = False
        for jaar, weken in jaargangen.items():
            correctie = correcties.get(jaar, {}).get(sleutel)
            if correctie:
                gecorrigeerd = True
                punten += correctie["punten"]
                weken_totaal += correctie["weken"]
                jaar_hoogste = correctie["hoogste"]
            else:
                punten += sum(lengte[(jaar, w)] - p + 1 for w, p in weken.items())
                weken_totaal += len(weken)
                jaar_hoogste = min(weken.values())
            hoogste = jaar_hoogste if hoogste is None else min(hoogste, jaar_hoogste)

        eerste_jaar, laatste_jaar = min(jaargangen), max(jaargangen)
        eerste_week = min(jaargangen[eerste_jaar])
        laatste_week = max(jaargangen[laatste_jaar])
        begin = vrijdag_van(eerste_jaar, eerste_week)
        eind = vrijdag_van(laatste_jaar, laatste_week)

        # Loopt de notering buiten het decennium door? Dat kan alleen aan de
        # randen, en dan weet looptijden() van dat jaar het al.
        loop_begin = rand.get(eerste_jaar, {}).get(sleutel)
        loop_eind = rand.get(laatste_jaar, {}).get(sleutel)
        artiest, titel, label = naam[sleutel]

        # Het jaar waarin het nummer de meeste punten haalde: daar hoort het
        # thuis als je doorklikt naar een jaaroverzicht.
        beste_jaar = max(
            jaargangen,
            key=lambda j: sum(lengte[(j, w)] - p + 1 for w, p in jaargangen[j].items()),
        )

        uitkomst.append({
            "sleutel": sleutel, "artiest": artiest, "titel": titel, "label": label,
            "punten": punten, "hoogste": hoogste, "weken": weken_totaal,
            "jaren": sorted(jaargangen), "beste_jaar": beste_jaar,
            "eerste": als_tekst(begin), "laatste": als_tekst(eind),
            "eerste_sorteer": begin.isoformat(), "laatste_sorteer": eind.isoformat(),
            "begon_eerder": bool(loop_begin and loop_begin.begon_eerder
                                 and eerste_jaar == van),
            "loopt_door": bool(loop_eind and loop_eind.loopt_door
                               and laatste_jaar == tot),
            "gecorrigeerd": gecorrigeerd,
        })

    uitkomst.sort(key=lambda n: (-n["punten"], n["hoogste"], n["eerste_sorteer"]))
    return uitkomst


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


# --- jaarlijkse lijsten (de Top 2000) --------------------------------------
#
# Een lijst met een editie per jaar past wel in het schema, maar niet in de
# presentatie van de weeklijsten: binnen een jaargang is er maar een meting, dus
# "positie per week" levert een tabel van een kolom. De zinvolle matrix is hier
# nummer x editie, en dat is precies wat deze twee functies opleveren.


def editie_klassement(
    con: sqlite3.Connection, lijst: str, jaar: int
) -> list[dict]:
    """De noteringen van een editie, op positie, met de historie erbij.

    Per nummer: de positie van dit jaar, die van de vorige editie, in hoeveel
    edities het stond en wat de beste positie ooit was. Dat laatste kost een
    tweede query over alle jaargangen, maar zonder die cijfers is een editie
    alleen een lijst namen.
    """
    dit_jaar = list(con.execute(
        "SELECT positie, artiest, titel, sleutel, uitjaar FROM noteringen"
        " WHERE lijst=? AND jaar=? ORDER BY positie", (lijst, jaar)))
    if not dit_jaar:
        return []

    historie: dict[str, dict[int, int]] = {}
    for sleutel, rij_jaar, positie in con.execute(
            "SELECT sleutel, jaar, MIN(positie) FROM noteringen WHERE lijst=?"
            " GROUP BY sleutel, jaar", (lijst,)):
        historie.setdefault(sleutel, {})[rij_jaar] = positie

    uit = []
    for rij in dit_jaar:
        alles = historie.get(rij["sleutel"], {})
        # Stond het er vorig jaar niet in, dan is het OF een binnenkomer OF een
        # terugkeer. Dat verschil is groot -- in 2025 waren van de 127 nummers
        # zonder vorige notering er 74 nieuw en 53 terug -- en zonder `eerder`
        # zou de pagina ze allemaal "nieuw" noemen.
        eerder = [j for j in alles if j < jaar]
        uit.append({
            "positie": rij["positie"],
            "artiest": rij["artiest"],
            "titel": rij["titel"],
            "sleutel": rij["sleutel"],
            "uitjaar": rij["uitjaar"],
            "vorige": alles.get(jaar - 1),
            "eerder": max(eerder) if eerder else None,
            "edities": len(alles),
            "hoogste": min(alles.values()) if alles else rij["positie"],
            "posities": alles,
        })
    return uit


def edities_van(con: sqlite3.Connection, lijst: str) -> list[int]:
    """Alle jaargangen waarvan we een editie hebben, oplopend."""
    return [r[0] for r in con.execute(
        "SELECT DISTINCT jaar FROM noteringen WHERE lijst=? ORDER BY jaar",
        (lijst,))]


def editie_reeks(
    con: sqlite3.Connection, lijst: str, sleutel: str
) -> Optional[dict]:
    """Het verloop van één nummer over alle edities van een jaarlijkse lijst.

    De tegenhanger van `reeks_van()` voor de weeklijsten: daar loopt de as over
    weken, hier over jaren. Edities waarin het nummer niet stond blijven als
    lege kolom staan, zodat een gat op de juiste plek in de tijd valt.
    """
    edities = edities_van(con, lijst)
    if not edities:
        return None
    eigen = {jaar: positie for jaar, positie in con.execute(
        "SELECT jaar, MIN(positie) FROM noteringen WHERE lijst=? AND sleutel=?"
        " GROUP BY jaar", (lijst, sleutel))}
    if not eigen:
        return None

    # Alleen het venster van de eerste tot de laatste editie waarin het stond;
    # de jaren ervoor en erna zeggen niets.
    van, tot = min(eigen), max(eigen)
    binnen = [j for j in edities if van <= j <= tot]
    reeks = [{"jaar": j, "week": None, "datum": str(j),
              "positie": eigen.get(j)} for j in binnen]
    genoteerd = list(eigen.values())
    return {
        "as": "editie",
        "reeks": reeks,
        "lengte": max(
            (r[0] for r in con.execute(
                "SELECT MAX(positie) FROM noteringen WHERE lijst=?", (lijst,))),
            default=max(genoteerd)) or max(genoteerd),
        "hoogste": min(genoteerd),
        "weken": len(genoteerd),
        "punten": 0,
        "van": str(van),
        "tot": str(tot),
    }
