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
    uitjaar          INTEGER,
    -- Het belletje van top40.nl: dit nummer is (ooit) Alarmschijf geweest.
    -- Per notering vastgelegd zoals de bron het toont; een nummer is
    -- Alarmschijf zodra één van zijn noteringen de vlag draagt.
    alarmschijf      INTEGER NOT NULL DEFAULT 0,
    -- De stipnotering van de Top 40: 0 = geen, 1 = stip, 2 = superstip.
    -- Anders dan de alarmschijf hoort dit bij de wéék, niet bij de plaat.
    stip             INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_noteringen_sleutel
    ON noteringen (lijst, jaar, sleutel);
CREATE INDEX IF NOT EXISTS idx_noteringen_week
    ON noteringen (lijst, jaar, week);
-- Voor de artiestpagina: alles van één artiest is een prefix-zoektocht op de
-- sleutel (artiest|titel), en die wil je niet over een half miljoen rijen
-- laten schuiven.
CREATE INDEX IF NOT EXISTS idx_noteringen_sleutel_prefix
    ON noteringen (sleutel);

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

-- Verhuisde sleutels: waar een oude sleutel tegenwoordig te vinden is. Puur
-- voor de webadressen -- de sleutel staat in de URL van een nummerpagina, dus
-- verandert de normalisatie, dan breken alle bewaarde en gedeelde links. Deze
-- tabel laat de site doorverwijzen in plaats van 404 geven.
--
-- Bewust NIET de tabel `aliases`: die bevat gecureerde beslissingen ("dit is
-- dezelfde plaat", nagekeken tegen MusicBrainz), telt mee bij het berekenen
-- van sleutels, en wordt elke run naar CSV geexporteerd. Een verhuisbericht is
-- iets anders: mechanisch, bij duizenden tegelijk, en het mag nooit invloed
-- hebben op wat een sleutel wordt.
CREATE TABLE IF NOT EXISTS oude_sleutels (
    oud        TEXT PRIMARY KEY,
    nieuw      TEXT NOT NULL,
    reden      TEXT,
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

-- De taak die op dit moment draait, of als laatste heeft gedraaid. Eén rij.
--
-- Stond vroeger in het geheugen van de webapplicatie, en dat gaf twee keer een
-- verkeerd beeld: na een herstart was de voortgang weg, en werk dat vanaf de
-- opdrachtregel liep was er helemaal niet in te zien. Dan staat er "niets aan
-- de gang" terwijl er een half uur aan bestanden wordt gebouwd.
CREATE TABLE IF NOT EXISTS taak (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    naam       TEXT NOT NULL,
    gestart    TEXT NOT NULL,
    bijgewerkt TEXT NOT NULL,
    proces     INTEGER,          -- om te zien of hij nog leeft
    klaar      INTEGER NOT NULL DEFAULT 0,
    gelukt     INTEGER,
    fout       TEXT,
    regels     TEXT,             -- de laatste meldingen, één per regel
    -- Waar hij is, zodat de pagina balken kan tekenen in plaats van alleen
    -- tekst. `stap` telt de fasen ("3 van 5: Excel bouwen"), `deel` telt binnen
    -- een fase ("jaargang 40 van 62").
    stap       INTEGER,
    stappen    INTEGER,
    stap_naam  TEXT,
    deel       INTEGER,
    deel_van   INTEGER
);

-- Welke (lijst, jaargang) opnieuw gebouwd moet worden. Zonder deze tabel is
-- "verouderd" niet per jaargang te bepalen en maakt elke wijziging alle 883
-- bestanden verdacht -- een half uur bouwen voor een alias die drie jaargangen
-- raakt. Wordt geleegd zodra het bestand er staat.
CREATE TABLE IF NOT EXISTS te_bouwen (
    lijst      TEXT NOT NULL,
    jaar       INTEGER NOT NULL,
    reden      TEXT,
    aangemaakt TEXT,
    PRIMARY KEY (lijst, jaar)
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

-- Berichten van bezoekers: opmerkingen, tips, bugs en aanvullingen. Alles
-- komt privé binnen (status "nieuw"); wat de beheerder publiceert verschijnt
-- in het gastenboek. Spam wordt verwijderd en laat dus geen rij achter.
CREATE TABLE IF NOT EXISTS berichten (
    id           INTEGER PRIMARY KEY,
    tijdstip     TEXT NOT NULL,
    soort        TEXT NOT NULL,             -- opmerking | tip | bug | aanvulling
    naam         TEXT,
    email        TEXT,
    tekst        TEXT NOT NULL,
    pagina       TEXT,                      -- waar de melder stond
    mag_openbaar INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'nieuw',  -- nieuw | gepubliceerd | prive
    antwoord     TEXT,                      -- korte reactie van de beheerder
    ip           TEXT                       -- voor de per-IP-limiet
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


def _voeg_alarmschijf_toe(con: sqlite3.Connection) -> None:
    """Voeg de kolom `alarmschijf` toe aan een database die hem nog mist."""
    kolommen = {r[1] for r in con.execute("PRAGMA table_info(noteringen)")}
    if kolommen and "alarmschijf" not in kolommen:
        con.execute("ALTER TABLE noteringen ADD COLUMN alarmschijf INTEGER"
                    " NOT NULL DEFAULT 0")
        con.commit()


def _voeg_stip_toe(con: sqlite3.Connection) -> None:
    """Voeg de kolom `stip` toe aan een database die hem nog mist."""
    kolommen = {r[1] for r in con.execute("PRAGMA table_info(noteringen)")}
    if kolommen and "stip" not in kolommen:
        con.execute("ALTER TABLE noteringen ADD COLUMN stip INTEGER"
                    " NOT NULL DEFAULT 0")
        con.commit()


def _stel_in(con: sqlite3.Connection) -> None:
    """De instellingen die gelijktijdig gebruik mogelijk maken.

    Dit ging een keer mis en het foutbeeld was raadselachtig: een taak die
    zeven jaargangen lang sleutels bijwerkte viel om met "database is locked",
    terwijl er alleen maar iemand door de website klikte.

    Twee oorzaken, allebei hier opgelost:

    * **Journaalmodus.** In de standaardmodus (`delete`) blokkeert een lezer een
      schrijver: zolang iemand een pagina opvraagt kan de achtergrondtaak niet
      wegschrijven. Met **WAL** gaan lezers en schrijvers langs elkaar heen.
      Het staat in het bestand zelf, dus één keer instellen is genoeg -- maar
      het staat hier zodat een verse database het meteen goed heeft.
    * **Geduld.** Standaard wacht sqlite vijf seconden op een slot en geeft het
      dan op. Bij het bouwen van een jaargang is dat aan de krappe kant; dertig
      seconden kost niets en scheelt een afgebroken taak.

    `synchronous=NORMAL` hoort bij WAL: bij een stroomstoring kan de laatste
    transactie verloren gaan, maar de database raakt niet beschadigd. Voor een
    hitlijstenarchief is dat de goede afweging -- en er staat een momentopname
    naast.
    """
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("PRAGMA synchronous=NORMAL")


@contextmanager
def verbinding() -> Iterator[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    _stel_in(con)
    try:
        con.executescript(SCHEMA)
        _migreer_primaire_sleutel(con)
        _voeg_uitjaar_toe(con)
        _voeg_alarmschijf_toe(con)
        _voeg_stip_toe(con)
        yield con
        con.commit()
    finally:
        con.close()


def markeer_te_bouwen(con: sqlite3.Connection, *, sleutels=None,
                      lijst: str | None = None, jaar: int | None = None,
                      reden: str = "") -> int:
    """Onthoud welke jaargangen opnieuw gebouwd moeten worden.

    Met `sleutels` wordt opgezocht in welke (lijst, jaargang) die nummers
    voorkomen -- dat is precies wat een alias of een hernoeming raakt, en meestal
    zijn dat er drie en niet zeshonderd.
    """
    paren = set()
    if lijst and jaar:
        paren.add((lijst, jaar))
    for sleutel in list(sleutels or []):
        paren |= {(r[0], r[1]) for r in con.execute(
            "SELECT DISTINCT lijst, jaar FROM noteringen WHERE sleutel=?",
            (sleutel,))}
    if not paren:
        return 0
    con.executemany(
        "INSERT OR REPLACE INTO te_bouwen (lijst, jaar, reden, aangemaakt)"
        " VALUES (?,?,?,?)",
        [(l, j, reden, datetime.now().isoformat(timespec="seconds"))
         for l, j in paren])
    return len(paren)


def te_bouwen(con: sqlite3.Connection) -> list[tuple[str, int]]:
    """Wat er nog gebouwd moet worden, oudste markering eerst."""
    return [(r[0], r[1]) for r in con.execute(
        "SELECT lijst, jaar FROM te_bouwen ORDER BY aangemaakt, jaar")]


def onthoud_verhuizing(con: sqlite3.Connection, oud: str, nieuw: str,
                       reden: str = "") -> None:
    """Leg vast waar een sleutel naartoe is gegaan, voor de doorverwijzing."""
    if oud == nieuw:
        return
    con.execute(
        "INSERT OR REPLACE INTO oude_sleutels (oud, nieuw, reden, aangemaakt)"
        " VALUES (?,?,?,?)",
        (oud, nieuw, reden, datetime.now().isoformat(timespec="seconds")))


def volg_verhuizing(con: sqlite3.Connection, sleutel: str,
                    stappen: int = 10) -> str | None:
    """Waar is deze sleutel nu? Volgt een keten a->b->c, of None.

    Een keten ontstaat vanzelf als de normalisatie twee keer verandert; zonder
    doorvolgen zou de eerste verhuizing naar een adres wijzen dat zelf ook al
    verhuisd is.
    """
    gezien = {sleutel}
    for _ in range(stappen):
        rij = con.execute(
            "SELECT nieuw FROM oude_sleutels WHERE oud=?", (sleutel,)).fetchone()
        if rij is None:
            return None if sleutel in gezien and len(gezien) == 1 else sleutel
        sleutel = rij[0]
        if sleutel in gezien:          # cyclus: hier houdt het op
            return sleutel
        gezien.add(sleutel)
    return sleutel


def gebouwd(con: sqlite3.Connection, lijst: str, jaar: int) -> None:
    """Haal een jaargang van de lijst af; het bestand staat er weer."""
    con.execute("DELETE FROM te_bouwen WHERE lijst=? AND jaar=?", (lijst, jaar))


def bewaar_week(
    con: sqlite3.Connection, lijst: str, jaar: int, week: int, noteringen: Iterable[Notering]
) -> int:
    """Schrijf één week weg; vervangt wat er al stond voor die week."""
    from .normalize import sleutel_van
    from .opschonen import (eenduidige_credit, gast_uit_titel,
                            komma_is_samenwerking, met_is_samenwerking,
                            ondertitel_tussen_haken, schoon_tekst,
                            splits_kanten, x_is_samenwerking)

    # Leestekens hier rechtzetten en niet in de parsers: dan geldt het voor elke
    # bron, ook voor een bron die er later bij komt. Hetzelfde geldt voor de
    # dubbele A-kant: top40.nl levert "No Reply ; Rock And Roll Music" als een
    # regel, en dat worden hier twee noteringen op dezelfde positie.
    rijen = []
    for n in noteringen:
        for ruwe_artiest, ruwe_titel in splits_kanten(n.artiest, n.titel):
            artiest, titel = gast_uit_titel(schoon_tekst(ruwe_artiest),
                                            schoon_tekst(ruwe_titel))
            titel = ondertitel_tussen_haken(titel)
            artiest = met_is_samenwerking(komma_is_samenwerking(
                x_is_samenwerking(eenduidige_credit(artiest))))
            rijen.append((
                n.lijst, n.jaar, n.week, n.positie, titel, artiest, n.label,
                n.weken_genoteerd, n.vorige_positie, n.site_status,
                sleutel_van(artiest, titel), 1 if n.alarmschijf else 0,
                n.stip,
            ))
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
            " weken_genoteerd, vorige_positie, site_status, sleutel, alarmschijf,"
            " stip) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
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


def jaarlijkse_totalen(con: sqlite3.Connection) -> list[dict]:
    """Alle nummers uit de jaarlijkse lijsten samen, eerlijk geteld.

    De lijsten zijn niet zomaar optelbaar: een nummer 1 in de Top 4000 zou
    4.000 punten waard zijn en een nummer 1 in de Rock Top 500 maar 500,
    terwijl het dezelfde prestatie is. Daarom wordt er per editie
    **genormaliseerd**: een notering telt (lengte − positie + 1) / lengte
    punten, dus de nummer 1 van élke lijst is precies één punt waard en de
    laatste plek bijna nul. De lengte komt per editie uit de gegevens zelf,
    want die wisselt (de Veronica Top 1000 was ooit drieduizend).

    Wat overblijft weegt hoogte én trouw: wie hoog staat verdient veel per
    editie, wie er elk jaar in staat stapelt edities. Het maximum is dus het
    aantal edities dat er ooit was.
    """
    from .config import LIJSTEN, is_jaarlijks

    jaarlijks = [naam for naam in LIJSTEN if is_jaarlijks(naam)]
    plek = ",".join("?" for _ in jaarlijks)
    rijen = list(con.execute(
        f"SELECT lijst, jaar, positie, artiest, titel, sleutel FROM noteringen"
        f" WHERE lijst IN ({plek})", jaarlijks))

    lengte: dict[tuple, int] = {}
    for r in rijen:
        paar = (r["lijst"], r["jaar"])
        lengte[paar] = max(lengte.get(paar, 0), r["positie"])

    nummers: dict[str, dict] = {}
    for r in rijen:
        n = nummers.setdefault(r["sleutel"], {
            "sleutel": r["sleutel"], "artiest": r["artiest"],
            "titel": r["titel"], "punten": 0.0, "edities": 0,
            "lijsten": set(), "hoogste": None, "hoogste_lijst": None,
            "hoogste_jaar": None,
        })
        n["artiest"], n["titel"] = r["artiest"], r["titel"]
        deler = lengte[(r["lijst"], r["jaar"])]
        n["punten"] += (deler - r["positie"] + 1) / deler
        n["edities"] += 1
        n["lijsten"].add(r["lijst"])
        if n["hoogste"] is None or r["positie"] < n["hoogste"]:
            n["hoogste"] = r["positie"]
            n["hoogste_lijst"] = r["lijst"]
            n["hoogste_jaar"] = r["jaar"]

    uit = sorted(nummers.values(),
                 key=lambda n: (-n["punten"], n["hoogste"]))
    for n in uit:
        n["punten"] = round(n["punten"], 1)
        n["lijsten"] = len(n["lijsten"])
    return uit


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
