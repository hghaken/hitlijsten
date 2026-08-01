"""Toets de week-naar-vrijdag-omzetting tegen echte, gepubliceerde data.

De verwachte waarden komen uit de jaarlijsten van michajans.nl: hij vermeldt bij
elk nummer de datum van binnenkomst, altijd een zaterdag. Die staan hier vast,
zodat een toekomstige wijziging aan de regel meteen opvalt.

    C:\\Python313\\python.exe tests\\test_datums.py
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hitlijsten.datums import (  # noqa: E402
    eerste_zaterdag, vrijdag_tekst, vrijdag_van, zaterdag_van,
)
from hitlijsten.db import looptijden, reeks_van  # noqa: E402

# (jaar, week, zaterdag) -- overgenomen uit michajans.nl.
GEPUBLICEERD = [
    (1965, 1, date(1965, 1, 2)),
    (1965, 8, date(1965, 2, 20)),
    (1965, 52, date(1965, 12, 25)),
    (1975, 1, date(1975, 1, 4)),
    (1975, 12, date(1975, 3, 22)),
    (1975, 52, date(1975, 12, 27)),
    (1985, 1, date(1985, 1, 5)),
    (1995, 1, date(1995, 1, 7)),
    (2005, 52, date(2005, 12, 24)),
    (2005, 53, date(2005, 12, 31)),
    (2015, 1, date(2015, 1, 3)),
    (2020, 1, date(2020, 1, 4)),
    (2020, 52, date(2020, 12, 26)),
    (2024, 1, date(2024, 1, 6)),
    (2024, 52, date(2024, 12, 28)),
    (2025, 1, date(2025, 1, 4)),
    (2025, 52, date(2025, 12, 27)),
]

# Jaren waarin 1 januari op zaterdag valt: de vrijdag van week 1 ligt dan in
# december van het jaar ervoor. Dat is de eigenaardigheid waar dit om draait.
JAARGRENS = [1966, 1972, 1977, 1983, 1994, 2000, 2005, 2011, 2022]


def test_gepubliceerde_zaterdagen():
    for jaar, week, verwacht in GEPUBLICEERD:
        gekregen = zaterdag_van(jaar, week)
        assert gekregen == verwacht, f"{jaar} week {week}: {gekregen} != {verwacht}"


def test_altijd_zaterdag_en_vrijdag():
    for jaar in range(1965, 2027):
        for week in (1, 2, 26, 52):
            assert zaterdag_van(jaar, week).weekday() == 5, (jaar, week)
            assert vrijdag_van(jaar, week).weekday() == 4, (jaar, week)


def test_een_week_is_zeven_dagen():
    for jaar in (1965, 1999, 2000, 2024):
        for week in range(1, 52):
            verschil = zaterdag_van(jaar, week + 1) - zaterdag_van(jaar, week)
            assert verschil.days == 7, (jaar, week)


def test_vrijdag_is_de_dag_voor_de_zaterdag():
    for jaar, week, zaterdag in GEPUBLICEERD:
        assert (zaterdag - vrijdag_van(jaar, week)).days == 1


def test_jaargrens_week_1_valt_in_december():
    """In negen jaargangen ligt de vrijdag van week 1 in het vorige jaar."""
    gevonden = [j for j in range(1965, 2027) if vrijdag_van(j, 1).year != j]
    assert gevonden == JAARGRENS, gevonden
    # En dan is het steeds 31 december.
    for jaar in JAARGRENS:
        vr = vrijdag_van(jaar, 1)
        assert (vr.month, vr.day) == (12, 31), (jaar, vr)
        assert vr.year == jaar - 1


def test_eerste_zaterdag_ligt_in_de_eerste_week():
    for jaar in range(1965, 2027):
        eerste = eerste_zaterdag(jaar)
        assert eerste.year == jaar and eerste.day <= 7, (jaar, eerste)


def test_opmaak():
    assert vrijdag_tekst(1975, 1) == "03/01/1975"
    assert vrijdag_tekst(2022, 1) == "31/12/2021"


# --- reeksen over de jaargrens ---------------------------------------------


def _proefdatabase(rijen):
    """Kale database met alleen wat deze functies lezen.

    Rijen zijn (jaar, week, sleutel) of (jaar, week, sleutel, positie). Zonder
    positie krijgt alles positie 1; looptijden() kijkt er niet naar, reeks_van()
    wel.
    """
    con = sqlite3.connect(":memory:")
    con.execute(
        "CREATE TABLE noteringen (id INTEGER PRIMARY KEY, lijst TEXT, jaar INT,"
        " week INT, sleutel TEXT, positie INT)"
    )
    con.executemany(
        "INSERT INTO noteringen (lijst, jaar, week, sleutel, positie)"
        " VALUES ('top40',?,?,?,?)",
        [r if len(r) == 4 else (*r, 1) for r in rijen],
    )
    return con


def test_reeks_over_de_jaarwisseling_wordt_aaneengesmeed():
    # Loopt van week 50 van 2018 tot week 3 van 2019; 2018 heeft 52 weken.
    rijen = [(2018, w, "a") for w in (50, 51, 52)] + [(2019, w, "a") for w in (1, 2, 3)]
    lt = looptijden(_proefdatabase(rijen), "top40", 2019)
    assert lt["a"].begin == vrijdag_van(2018, 50)
    assert lt["a"].eind == vrijdag_van(2019, 3)
    assert lt["a"].begon_eerder and not lt["a"].loopt_door

    # Vanuit 2018 gezien is het precies andersom.
    lt = looptijden(_proefdatabase(rijen), "top40", 2018)
    assert lt["a"].eind == vrijdag_van(2019, 3)
    assert lt["a"].loopt_door and not lt["a"].begon_eerder


def test_overgeslagen_kerstweek_breekt_de_reeks_niet():
    """De Top 40 zendt in negentien jaargangen geen lijst uit in de laatste week.

    Zou de reeks zeven dagen eisen, dan brak hij juist op de jaargrens. De stap
    gaat daarom naar de volgende week die er werkelijk is.
    """
    rijen = [(1974, w, "a") for w in (50, 51)] + [(1975, w, "a") for w in (1, 2)]
    lt = looptijden(_proefdatabase(rijen), "top40", 1975)
    assert lt["a"].begin == vrijdag_van(1974, 50)
    assert lt["a"].begon_eerder
    # Er zit veertien dagen tussen, want week 52 van 1974 is nooit uitgezonden.
    assert (vrijdag_van(1975, 1) - vrijdag_van(1974, 51)).days == 14


def test_re_entry_wordt_niet_aan_vorig_jaar_geplakt():
    """Een gat waarin de lijst wel verscheen maar het nummer niet, telt wel."""
    rijen = [(2018, w, "a") for w in (40, 41)] + [(2019, w, "a") for w in (10, 11)]
    # Vul de tussenliggende weken met een ander nummer, zodat die weken bestaan.
    rijen += [(2018, w, "b") for w in range(40, 53)]
    rijen += [(2019, w, "b") for w in range(1, 12)]
    lt = looptijden(_proefdatabase(rijen), "top40", 2019)
    assert lt["a"].begin == vrijdag_van(2019, 10)
    assert not lt["a"].begon_eerder and not lt["a"].loopt_door


def test_zonder_buurjaar_blijft_alles_binnen_het_jaar():
    rijen = [(2019, w, "a") for w in (1, 2, 3)]
    lt = looptijden(_proefdatabase(rijen), "top40", 2019)
    assert lt["a"].begin == vrijdag_van(2019, 1)
    assert lt["a"].eind == vrijdag_van(2019, 3)
    assert not lt["a"].begon_eerder and not lt["a"].loopt_door


# --- de reeks achter de grafiek ---------------------------------------------


def test_reeks_loopt_door_in_het_vorige_jaar():
    """De grafiek stopt niet bij 1 januari, anders dan de jaarmatrix."""
    rijen = [(2022, 51, "a", 13), (2022, 52, "a", 5),
             (2023, 1, "a", 3), (2023, 2, "a", 2)]
    r = reeks_van(_proefdatabase(rijen), "top40", "a", 2023)
    assert [(n["jaar"], n["week"], n["positie"]) for n in r["reeks"]] == [
        (2022, 51, 13), (2022, 52, 5), (2023, 1, 3), (2023, 2, 2)]
    assert r["van"] == vrijdag_tekst(2022, 51)
    assert r["tot"] == vrijdag_tekst(2023, 2)
    assert r["hoogste"] == 2 and r["weken"] == 4


def test_reeks_houdt_gaten_op_hun_plek_in_de_tijd():
    """Een week zonder notering blijft als lege kolom staan."""
    rijen = [(2023, 1, "a", 10), (2023, 4, "a", 25)]
    # De weken 2 en 3 bestaan wel; er stond alleen een ander nummer in.
    rijen += [(2023, w, "b", 1) for w in (1, 2, 3, 4)]
    r = reeks_van(_proefdatabase(rijen), "top40", "a", 2023)
    assert [n["positie"] for n in r["reeks"]] == [10, None, None, 25]
    assert r["weken"] == 2, "een lege week telt niet mee"


def test_reeks_stopt_bij_een_week_die_nooit_is_uitgezonden():
    """Bestaat een week helemaal niet, dan is er geen gat om te tonen."""
    rijen = [(2023, 1, "a", 10), (2023, 4, "a", 25)]
    r = reeks_van(_proefdatabase(rijen), "top40", "a", 2023)
    assert [n["week"] for n in r["reeks"]] == [1, 4]


def test_reeks_neemt_de_lengte_van_de_lijst_over():
    rijen = [(2023, 1, "a", 3), (2023, 2, "a", 5)]
    rijen += [(2023, w, "vulling", 40) for w in (1, 2)]
    r = reeks_van(_proefdatabase(rijen), "top40", "a", 2023)
    assert r["lengte"] == 40
    # Punten = lijstlengte - positie + 1, per week gerekend.
    assert r["punten"] == (40 - 3 + 1) + (40 - 5 + 1)


def test_reeks_van_een_onbekend_nummer_is_niets():
    con = _proefdatabase([(2023, 1, "a", 1)])
    assert reeks_van(con, "top40", "bestaat|niet", 2023) is None
    assert reeks_van(con, "top40", "a", 1999) is None


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    mislukt = 0
    for test in tests:
        try:
            test()
            print(f"ok       {test.__name__}")
        except AssertionError as fout:
            mislukt += 1
            print(f"MISLUKT  {test.__name__}: {fout}")
    print(f"\n{len(tests) - mislukt}/{len(tests)} geslaagd")
    return 1 if mislukt else 0


if __name__ == "__main__":
    sys.exit(main())
