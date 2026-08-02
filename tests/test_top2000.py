"""Tests voor het inlezen van de Top 2000 (hitlijsten/top2000.py).

    cd /volume1/Hitlijsten/app && . ./omgeving.sh
    ./venv/bin/python tests/test_top2000.py

De bron is een matrix in plaats van een lijst per week, en dat is precies waar
het mis kan gaan: een kolom die verschuift, een lege cel die als positie 0 wordt
gelezen, of een editie die stilletjes maar 1900 nummers blijkt te hebben. Die
gevallen staan hier vast.
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hitlijsten import db, top2000  # noqa: E402
from hitlijsten.config import LIJSTEN, is_jaarlijks, wordt_opgehaald  # noqa: E402
from hitlijsten.normalize import sleutel_van  # noqa: E402

MAP = Path(tempfile.mkdtemp(prefix="hitlijsten-top2000-"))


def _csv(regels, edities=(2024, 2025), kop=None, codering="windows-1252") -> Path:
    """Schrijf een CSV in de vorm van Music Datastats."""
    kop = kop or ["TotaalPositie", "Artiest", "Titel", "Uitjaar", *map(str, edities)]
    tekst = ";".join(kop) + "\n"
    for nr, (artiest, titel, uitjaar, *posities) in enumerate(regels, 1):
        tekst += ";".join([str(nr), artiest, titel, str(uitjaar or ""),
                           *(str(p) for p in posities)]) + "\n"
    pad = MAP / f"proef-{len(list(MAP.glob('*.csv')))}.csv"
    pad.write_bytes(tekst.encode(codering))
    return pad


def _volle_editie(edities=(2024, 2025), lengte=None):
    """Genoeg vulnummers om elke editie compleet te maken."""
    lengte = lengte or LIJSTEN["top2000"]["lengte"]
    return [(f"Artiest {p}", f"Lied {p}", 1980, *([p] * len(edities)))
            for p in range(1, lengte + 1)]


def _database():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(db.SCHEMA)
    return con


# --- de lijstdefinitie ------------------------------------------------------


def test_de_top2000_wordt_niet_opgehaald():
    """Er is geen site; de wekelijkse run moet hem met rust laten."""
    assert is_jaarlijks("top2000") and not wordt_opgehaald("top2000")
    for lijst in ("top40", "tipparade", "sterrennl", "oranje"):
        assert wordt_opgehaald(lijst) and not is_jaarlijks(lijst), lijst


# --- inlezen ----------------------------------------------------------------


def test_matrix_wordt_per_editie_uit_elkaar_getrokken():
    pad = _csv([("Queen", "Bohemian Rhapsody", 1975, 1, 2),
                ("Eagles", "Hotel California", 1977, 2, 1)] + _volle_editie()[2:])
    edities, regels = top2000.lees_csv(pad)
    assert edities == [2024, 2025]
    queen = next(r for r in regels if r.artiest == "Queen")
    assert queen.posities == {2024: 1, 2025: 2}
    assert queen.uitjaar == 1975


def test_nul_betekent_niet_genoteerd():
    rijen = _volle_editie()
    rijen.append(("Eendagsvlieg", "Alleen In 2025", 2025, 0, 1500))
    _, regels = top2000.lees_csv(_csv(rijen))
    vlieg = next(r for r in regels if r.artiest == "Eendagsvlieg")
    assert vlieg.posities == {2025: 1500}, "0 is geen positie maar een gat"


def test_nummer_zonder_enkele_notering_valt_weg():
    rijen = _volle_editie()
    rijen.append(("Nooit", "Genoteerd", 1999, 0, 0))
    _, regels = top2000.lees_csv(_csv(rijen))
    assert not any(r.artiest == "Nooit" for r in regels)


def test_sleutel_is_dezelfde_als_bij_de_weeklijsten():
    """De brug naar de Top 40: gelijke artiest en titel geeft gelijke sleutel."""
    _, regels = top2000.lees_csv(_csv(
        [("Golden Earring", "Radar Love", 1973, 1, 1)] + _volle_editie()[1:]))
    aarde = next(r for r in regels if r.artiest == "Golden Earring")
    assert aarde.sleutel == sleutel_van("Golden Earring", "Radar Love")


def test_utf8_wordt_ook_gelezen():
    pad = _csv([("Bløf", "Aan De Kust", 2001, 1, 1)] + _volle_editie()[1:],
               codering="utf-8")
    _, regels = top2000.lees_csv(pad)
    assert any(r.artiest == "Bløf" for r in regels)


# --- structuurcontrole ------------------------------------------------------


def test_onvolledige_editie_wordt_geweigerd():
    """Een editie hoort 2000 posities te hebben, geen 1999."""
    rijen = _volle_editie()[:-1]      # eentje te weinig
    edities, regels = top2000.lees_csv(_csv(rijen))
    klachten = top2000.controleer(edities, regels)
    assert klachten and "ontbreken" in klachten[0], klachten


def test_dubbele_positie_wordt_geweigerd():
    rijen = _volle_editie()
    rijen[1] = (rijen[1][0], rijen[1][1], 1980, 1, 1)   # ook op 1
    edities, regels = top2000.lees_csv(_csv(rijen))
    assert any("dubbele" in k for k in top2000.controleer(edities, regels))


def test_verkeerde_kop_wordt_geweigerd():
    pad = _csv(_volle_editie(), kop=["Positie", "Naam", "Titel", "Jaar", "2024", "2025"])
    try:
        top2000.lees_csv(pad)
    except ValueError as fout:
        assert "eerste kolommen" in str(fout)
    else:
        raise AssertionError("een andere kolomkop hoort een fout te geven")


def test_import_slaat_niets_op_als_de_csv_niet_klopt():
    con = _database()
    pad = _csv(_volle_editie()[:-1])          # onvolledige editie
    try:
        top2000.importeer(con, pad)
    except ValueError:
        pass
    else:
        raise AssertionError("een kapotte CSV hoort te stuiten")
    aantal = con.execute("SELECT COUNT(*) FROM noteringen").fetchone()[0]
    assert aantal == 0, "er mag niets half weggeschreven zijn"


# --- wegschrijven -----------------------------------------------------------


def test_import_schrijft_elke_editie_als_jaargang():
    con = _database()
    uitkomst = top2000.importeer(con, _csv(_volle_editie()))
    assert uitkomst["geschreven"] == {2024: 2000, 2025: 2000}
    week = LIJSTEN["top2000"]["editie_week"]
    for jaar in (2024, 2025):
        rij = con.execute(
            "SELECT COUNT(*), MIN(week), MAX(week) FROM noteringen"
            " WHERE lijst='top2000' AND jaar=?", (jaar,)).fetchone()
        assert tuple(rij) == (2000, week, week), tuple(rij)


def test_opnieuw_importeren_vervangt_in_plaats_van_verdubbelt():
    con = _database()
    pad = _csv(_volle_editie())
    top2000.importeer(con, pad)
    top2000.importeer(con, pad)
    assert con.execute("SELECT COUNT(*) FROM noteringen").fetchone()[0] == 4000


def test_een_editie_apart_importeren():
    con = _database()
    top2000.importeer(con, _csv(_volle_editie()), alleen_jaar=2025)
    jaren = [r[0] for r in con.execute(
        "SELECT DISTINCT jaar FROM noteringen ORDER BY jaar")]
    assert jaren == [2025]


def test_vorige_positie_en_aantal_edities_worden_meegeschreven():
    # Queen klimt van 3 naar 1; de vulling die 3 had ruilt om, zodat elke editie
    # nog steeds precies de posities 1..2000 bevat.
    rijen = _volle_editie()
    rijen[0] = ("Queen", "Bohemian Rhapsody", 1975, 3, 1)
    rijen[2] = (rijen[2][0], rijen[2][1], 1980, 1, 3)
    con = _database()
    top2000.importeer(con, _csv(rijen))
    rij = con.execute(
        "SELECT vorige_positie, weken_genoteerd, uitjaar FROM noteringen"
        " WHERE lijst='top2000' AND jaar=2025 AND positie=1").fetchone()
    assert tuple(rij) == (3, 2, 1975), tuple(rij)


def test_kruisverwijzing_telt_wat_we_al_kennen():
    con = _database()
    con.execute(
        "INSERT INTO noteringen (lijst, jaar, week, positie, titel, artiest,"
        " site_status, sleutel) VALUES ('top40',1975,1,1,'Radar Love',"
        "'Golden Earring','nieuw',?)", (sleutel_van("Golden Earring", "Radar Love"),))
    rijen = [("Golden Earring", "Radar Love", 1973, 1, 1),
             ("Onbekend", "Nooit Gehoord", 2020, 2, 2)] + _volle_editie()[2:]
    uitkomst = top2000.importeer(con, _csv(rijen))
    kruis = uitkomst["kruisverwijzing"]
    assert kruis["raak"] == 1 and kruis["per_lijst"] == {"top40": 1}


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
        except Exception as fout:
            # Een onverwachte fout mag de rest van de reeks niet meeslepen.
            mislukt += 1
            print(f"FOUT     {test.__name__}: {type(fout).__name__}: {fout}")
    print(f"\n{len(tests) - mislukt}/{len(tests)} geslaagd")
    return 1 if mislukt else 0


if __name__ == "__main__":
    sys.exit(main())
