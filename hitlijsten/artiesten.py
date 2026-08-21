"""Het artiestenklassement: één regel per artiest, over alle lijsten heen.

WAAROM PUNTEN EN NIET NOTERINGEN
--------------------------------
Wie het meest genoteerd stond is niet wie het grootst was. Een 2000e plek in de
Top 2000 telt bij het tellen van noteringen even zwaar als een nummer 1 in de
Top 40, en dan wint wie de meeste platen maakte in plaats van wie de beste
maakte.

Daarom staat er een puntenkolom naast, met dezelfde normalisatie die de
Jaarlijsten-totaallijst al gebruikt: een notering is `(lengte − positie + 1) /
lengte` waard, dus **de nummer 1 van élke lijst is precies één punt** en de
laatste plek bijna nul. De lengte komt per uitzending uit de gegevens zelf --
de Top 40 was niet altijd veertig lang en de Tipparade wisselde ook.

Dat corrigeert de ranglijst zichtbaar: op noteringen staan de Rolling Stones
tweede en Queen derde, op punten is dat andersom. Queen heeft minder platen
maar stond hoger.

`op_1` telt alleen de **weeklijsten**. Een eerste plek in de Top 2000 is een
mooie prestatie, maar het is iets anders dan een week lang de bestverkochte
plaat van het land zijn, en op één hoop leest het als het tweede.

Het rekenwerk kost enkele seconden over ruim een half miljoen noteringen, dus
de webapplicatie houdt de uitkomst vast tot de gegevens veranderen -- net als
bij de records.
"""
from __future__ import annotations

import sqlite3

from .taal import nederlandstalige_sleutels

__all__ = ["verzamel", "WEEKLIJSTEN", "NL_AANDEEL"]

# Los van config.is_jaarlijks(), want dit is een vaste afspraak over wat "op 1
# staan" betekent en geen afgeleide van de lijstdefinitie.
WEEKLIJSTEN = ("top40", "tipparade", "oranje", "sterrennl")

# Vanaf welk aandeel Nederlandstalige nummers een artiest in het
# NL-filter meetelt. Zie de opmerking bij de berekening.
NL_AANDEEL = 0.25


def verzamel(con: sqlite3.Connection) -> list[dict]:
    """Een regel per artiest, gesorteerd op naam.

    De artiestsleutel is het deel van de sleutel vóór de streep; daarmee sluit
    deze lijst aan op `/artiest/<sleutel>` zonder aparte tabel.
    """
    # De lengte van elke afzonderlijke uitzending. Dit is dezelfde aanpak als
    # in db.jaarlijkse_totalen: de hoogste positie die er voorkomt.
    lengte: dict[tuple, int] = {}
    for lijst, jaar, week, hoogste in con.execute(
            "SELECT lijst, jaar, week, MAX(positie) FROM noteringen"
            " GROUP BY lijst, jaar, week"):
        lengte[(lijst, jaar, week)] = hoogste or 1

    artiesten: dict[str, dict] = {}
    for sleutel, lijst, jaar, week, positie in con.execute(
            "SELECT sleutel, lijst, jaar, week, positie FROM noteringen"):
        streep = sleutel.find("|")
        if streep < 1:
            continue
        kant = sleutel[:streep]
        rij = artiesten.get(kant)
        if rij is None:
            rij = artiesten[kant] = {
                "sleutel": kant, "naam": kant, "nummers": set(),
                "alle_sleutels": set(),
                "noteringen": 0, "op_1": 0, "punten": 0.0,
                "lijsten": set(), "van": jaar, "tot": jaar,
            }
        rij["nummers"].add(sleutel)
        rij["alle_sleutels"].add(sleutel)
        rij["noteringen"] += 1
        rij["lijsten"].add(lijst)
        if jaar < rij["van"]:
            rij["van"] = jaar
        if jaar > rij["tot"]:
            rij["tot"] = jaar
        if positie == 1 and lijst in WEEKLIJSTEN:
            rij["op_1"] += 1
        deler = lengte[(lijst, jaar, week)]
        rij["punten"] += (deler - positie + 1) / deler

    # De vastgestelde schrijfwijze, met als terugval de meest gebruikte vorm
    # uit de noteringen zelf -- dezelfde volgorde als op de artiestpagina.
    namen = {s: n for s, n in con.execute(
        "SELECT sleutel, naam FROM artiestnamen")}
    for kant, artiest in con.execute(
            "SELECT substr(sleutel, 1, instr(sleutel, '|') - 1) kant, artiest"
            " FROM noteringen GROUP BY kant, artiest ORDER BY COUNT(*)"):
        # Oplopend gesorteerd, dus de laatste toewijzing is de vaakst
        # voorkomende schrijfwijze.
        if kant in artiesten:
            artiesten[kant]["naam"] = namen.get(kant) or artiest

    # Het aandeel Nederlandstalig werk. Een artiest is Nederlandstalig als hij
    # in het Nederlands zingt, niet als hij hier geboren is -- en ook niet als
    # er ooit een keer een Nederlandstalige plaat tussen zat. Anouk heeft er
    # een van de negenveertig (Dominique), en dan hoort ze niet in een filter
    # dat Nederlandstalige artiesten toont.
    nederlands = nederlandstalige_sleutels(con)

    uit = []
    for rij in artiesten.values():
        rij["nl_nummers"] = sum(1 for s in rij["alle_sleutels"]
                                if s in nederlands)
        rij["nl_deel"] = rij["nl_nummers"] / len(rij["alle_sleutels"])
        del rij["alle_sleutels"]
        rij["nummers"] = len(rij["nummers"])
        rij["lijsten"] = len(rij["lijsten"])
        rij["punten"] = round(rij["punten"], 1)
        uit.append(rij)

    _markeer_nevencredits(uit)
    uit.sort(key=lambda r: r["naam"].lower())
    return uit


# Waar een credit kan afsplitsen van de hoofdnaam.
_SCHEIDERS = (" & ", " with ", " and ", " - ", " (")


def _markeer_nevencredits(rijen: list[dict]) -> None:
    """Zet `neven` op de credits die bij een grotere artiest horen.

    Michael Jackson staat veertien keer in het archief: een keer op eigen naam
    met 52 nummers, en dertien keer in een duet met precies een plaat. Dat
    laatste is ruis in een artiestenlijst.

    **Niet op de ampersand filteren.** Die zit net zo goed in echte bandnamen
    -- Nick & Simon, Earth, Wind & Fire, Kool & The Gang, Simon & Garfunkel,
    Bob Marley & The Wailers -- en daarop filteren zou precies de verkeerde
    regels weghalen.

    De regel hier is smaller: een credit is een nevencredit als hij begint met
    de **volledige naam van een andere artiest in deze lijst** en die artiest
    meer nummers heeft. "Michael Jackson & Paul McCartney" valt dan onder
    "Michael Jackson"; "Nick & Simon" niet, want er is geen artiest die "Nick"
    heet.

    Perfect is het niet: Bruce Springsteen & The E Street Band en Prince & The
    Revolution zijn echte bandnamen en vallen wel af. Vandaar dat dit een
    vinkje is en geen automatisme -- uit staat alles er gewoon.
    """
    op_sleutel = {r["sleutel"]: r for r in rijen}
    for rij in rijen:
        rij["neven"] = None
        for scheider in _SCHEIDERS:
            if scheider not in rij["sleutel"]:
                continue
            kop = rij["sleutel"].split(scheider)[0]
            ander = op_sleutel.get(kop)
            if ander is not None and ander["nummers"] > rij["nummers"]:
                rij["neven"] = ander["naam"]
                break
