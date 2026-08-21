"""Het artiestenklassement: punten, weeklijst-enen, nevencredits, NL-aandeel."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import veilig  # noqa: F401  -- moet vóór hitlijsten, zie veilig.py
from hitlijsten import db  # noqa: E402
from hitlijsten.artiesten import NL_AANDEEL, verzamel  # noqa: E402
from hitlijsten.taal import SCHEMA as TAALSCHEMA, zet_hand  # noqa: E402


def _archief(noteringen, nederlands=()):
    """Een verse database met precies deze noteringen.

    `noteringen` is een rij tupels (lijst, jaar, week, positie, artiest,
    titel); `nederlands` de sleutels die de vlag met de hand krijgen.
    """
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(db.SCHEMA)
    con.executescript(TAALSCHEMA)
    for lijst, jaar, week, positie, artiest, titel in noteringen:
        con.execute(
            "INSERT INTO noteringen (lijst, jaar, week, positie, titel,"
            " artiest, site_status, sleutel) VALUES (?,?,?,?,?,?,'ok',?)",
            (lijst, jaar, week, positie, titel, artiest,
             f"{artiest.lower()}|{titel.lower()}"))
    for sleutel in nederlands:
        zet_hand(con, sleutel, True)
    con.commit()
    return con


def _op_naam(rijen):
    return {r["naam"]: r for r in rijen}


def test_nummer_1_van_elke_lijst_is_een_punt():
    """De normalisatie: hoogte telt, lijstlengte niet.

    Zonder deze weging zou een 2000e plek in de Top 2000 even zwaar tellen
    als een nummer 1 in de Top 40, en dan wint wie de meeste platen maakte.
    """
    con = _archief([("top40", 2000, 1, 1, "A", "x"),
                    ("top40", 2000, 1, 40, "B", "y"),
                    ("top2000", 2000, 52, 1, "C", "z"),
                    ("top2000", 2000, 52, 2000, "D", "w")])
    rijen = _op_naam(verzamel(con))
    assert rijen["A"]["punten"] == 1.0, rijen["A"]["punten"]
    assert rijen["C"]["punten"] == 1.0, rijen["C"]["punten"]
    # De laatste plek is bijna niets waard, in beide lijsten.
    assert rijen["B"]["punten"] < 0.1 and rijen["D"]["punten"] < 0.1


def test_op_1_telt_alleen_de_weeklijsten():
    """Een week de bestverkochte plaat van het land is iets anders dan de
    eerste plek in een jaarlijkse verzoeklijst."""
    con = _archief([("top40", 2000, 1, 1, "A", "x"),
                    ("top40", 2000, 2, 1, "A", "x"),
                    ("top2000", 2000, 52, 1, "A", "x")])
    rij = _op_naam(verzamel(con))["A"]
    assert rij["op_1"] == 2, rij["op_1"]
    assert rij["noteringen"] == 3 and rij["nummers"] == 1


def test_nevencredit_valt_onder_de_grotere_artiest():
    con = _archief([("top40", 2000, 1, 1, "Michael Jackson", "a"),
                    ("top40", 2000, 2, 1, "Michael Jackson", "b"),
                    ("top40", 2000, 3, 1, "Michael Jackson & Paul McCartney",
                     "c")])
    rijen = _op_naam(verzamel(con))
    assert rijen["Michael Jackson & Paul McCartney"]["neven"] \
        == "Michael Jackson"
    assert rijen["Michael Jackson"]["neven"] is None


def test_echte_bandnaam_met_ampersand_blijft_staan():
    """Nick & Simon, Earth, Wind & Fire, Kool & The Gang: op de ampersand
    filteren zou precies de verkeerde regels weghalen."""
    con = _archief([("top40", 2000, 1, 1, "Nick & Simon", "a"),
                    ("top40", 2000, 2, 1, "Kool & The Gang", "b")])
    for rij in verzamel(con):
        assert rij["neven"] is None, rij["naam"]


def test_nl_aandeel_scheidt_zanger_van_uitschieter():
    """Een Nederlandstalige plaat maakt nog geen Nederlandstalige artiest.

    Anouk heeft er een van de negenveertig; die hoort niet in een filter dat
    Nederlandstalige artiesten toont. Wie de helft in het Nederlands zingt
    wel.
    """
    con = _archief(
        [("top40", 2000, w, 1, "Anouk", f"lied {w}") for w in range(1, 11)]
        + [("top40", 2001, w, 1, "Tweetalig", f"lied {w}")
           for w in range(1, 5)],
        nederlands=["anouk|lied 1", "tweetalig|lied 1", "tweetalig|lied 2"])
    rijen = _op_naam(verzamel(con))
    assert rijen["Anouk"]["nl_deel"] == 0.1
    assert rijen["Anouk"]["nl_deel"] < NL_AANDEEL
    assert rijen["Tweetalig"]["nl_deel"] == 0.5
    assert rijen["Tweetalig"]["nl_deel"] >= NL_AANDEEL


def test_zonder_vlaggen_is_het_aandeel_nul():
    con = _archief([("top40", 2000, 1, 1, "A", "x")])
    assert _op_naam(verzamel(con))["A"]["nl_deel"] == 0.0


def main() -> int:
    fouten = 0
    for naam, functie in sorted(globals().items()):
        if not naam.startswith("test_"):
            continue
        try:
            functie()
            print(f"ok       {naam}")
        except AssertionError as fout:
            fouten += 1
            print(f"MISLUKT  {naam}: {fout}")
        except Exception as fout:
            fouten += 1
            print(f"KAPOT    {naam}: {type(fout).__name__}: {fout}")
    totaal = sum(1 for n in globals() if n.startswith("test_"))
    print(f"{totaal - fouten}/{totaal} geslaagd")
    return 1 if fouten else 0


if __name__ == "__main__":
    raise SystemExit(main())
