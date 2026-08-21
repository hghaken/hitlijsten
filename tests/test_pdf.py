"""Tests voor het jaaroverzicht als PDF (hitlijsten/pdf.py).

    python tests/test_pdf.py

Een PDF ziet er in een test altijd goed uit — je kunt hem niet bekijken. Wat
hier vastligt is dus niet de opmaak maar wat er misgaat als je niet oplet: het
aantal regels per pagina, tekens die het ingebouwde lettertype niet kent, en de
vraag of een bewaard bestand nog klopt.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TIJDELIJK = tempfile.mkdtemp(prefix="hitlijsten-pdf-")
os.environ.setdefault("HITLIJSTEN_EXCEL", _TIJDELIJK)

import veilig  # noqa: F401  -- moet vóór hitlijsten, zie veilig.py
from hitlijsten import db, pdf  # noqa: E402

MAP = Path(_TIJDELIJK)


def _database(noteringen):
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(db.SCHEMA)
    con.executemany(
        "INSERT INTO noteringen (lijst, jaar, week, positie, titel, artiest,"
        " label, weken_genoteerd, vorige_positie, site_status, sleutel)"
        " VALUES ('top40',?,?,?,?,?,NULL,NULL,NULL,'nieuw',?)",
        [(j, w, p, titel, artiest, f"{artiest.lower()}|{titel.lower()}")
         for j, w, p, artiest, titel in noteringen],
    )
    return con


def _vullen(jaar, weken, tot=40):
    return [(jaar, w, p, f"Vul {p}", "Lied") for w in weken for p in range(1, tot + 1)]


def _paginas(gegevens: bytes) -> int:
    """Tel de pagina's zonder een pdf-bibliotheek: /Type /Page telt ze."""
    return gegevens.count(b"/Type /Page") - gegevens.count(b"/Type /Pages")


# --- opbouw -----------------------------------------------------------------


def test_veertig_regels_per_pagina():
    assert pdf.REGELS_PER_PAGINA == 40
    # 40 nummers op één pagina, 41 op twee.
    for aantal, verwacht in ((40, 1), (41, 2), (80, 2), (81, 3)):
        rijen = [(2020, 1, p, f"Artiest {p}", f"Lied {p}") for p in range(1, aantal + 1)]
        gegevens = pdf.bouw_jaaroverzicht(_database(rijen), "top40", 2020)
        assert _paginas(gegevens) == verwacht, f"{aantal} nummers -> {verwacht} pagina's"


def test_lege_jaargang_geeft_niets():
    assert pdf.bouw_jaaroverzicht(_database(_vullen(2020, [1])), "top40", 1999) is None


def test_namen_met_bijzondere_tekens_overleven():
    """Deze namen vallen om op het ingebouwde lettertype; daarom DejaVu."""
    lastig = [
        ("Orchestral Manœuvres In The Dark", "Souvenir"),
        ("Tone Lōc", "Wild Thing"),
        ("Givēon", "Heartbreak Anniversary"),
        ("Tarkan", "Şıkıdım"),
        ("Axwell ∧ Ingrosso", "Dreamer"),
        ("Mart Hoogkamer", "Ik Spaar Geen C€nten"),
    ]
    rijen = [(2020, 1, i, a, t) for i, (a, t) in enumerate(lastig, 1)]
    rijen += _vullen(2020, [1])
    # Zonder een ingesloten lettertype gooit fpdf2 hier een fout; komt hij er
    # doorheen, dan staan de namen er ongeschonden in.
    gegevens = pdf.bouw_jaaroverzicht(_database(rijen), "top40", 2020)
    assert gegevens.startswith(b"%PDF")
    assert len(gegevens) > 20_000, "een ingesloten lettertype maakt het bestand groter"


def test_pad_ligt_naast_de_excel_van_dat_jaar():
    pad = pdf.pad_van("top40", 1975)
    assert pad.name == "Top40_1975.pdf"
    assert pad.parent.name == "1975" and pad.parent.parent.name == "1970-1979"


# --- bewaren en verversen ---------------------------------------------------


def test_bewaard_bestand_wordt_hergebruikt():
    con = _database(_vullen(2020, [1]))
    con.execute("INSERT INTO opgehaald (lijst, jaar, week, aantal, opgehaald_op)"
                " VALUES ('top40',2020,1,40,?)",
                ((datetime.now() - timedelta(days=1)).isoformat(timespec="seconds"),))

    pad = pdf.schrijf_jaaroverzicht(con, "top40", 2020, MAP)
    assert pad.exists()
    eerste = pad.stat().st_mtime_ns
    assert pdf.is_actueel(con, pad, "top40", 2020)

    time.sleep(0.01)
    pdf.schrijf_jaaroverzicht(con, "top40", 2020, MAP)
    assert pad.stat().st_mtime_ns == eerste, "actueel bestand niet opnieuw bouwen"

    pdf.schrijf_jaaroverzicht(con, "top40", 2020, MAP, altijd=True)
    assert pad.stat().st_mtime_ns != eerste, "met altijd=True wel"


def test_nieuwe_week_maakt_het_bestand_verouderd():
    con = _database(_vullen(2020, [1]))
    pad = pdf.schrijf_jaaroverzicht(con, "top40", 2020, MAP, altijd=True)
    con.execute("INSERT INTO opgehaald (lijst, jaar, week, aantal, opgehaald_op)"
                " VALUES ('top40',2020,2,40,?)",
                ((datetime.now() + timedelta(minutes=1)).isoformat(timespec="seconds"),))
    assert not pdf.is_actueel(con, pad, "top40", 2020)


def test_alleen_de_geraakte_jaargang_veroudert():
    """Een alias verschuift de punten -- maar niet van elke jaargang.

    Vroeger keek dit naar de laatste regel in `wijzigingen`, en dat gold voor
    alles tegelijk: één alias maakte alle 883 bestanden verdacht, oftewel een
    half uur bouwen voor drie jaargangen werk. Nu staat er per (lijst, jaargang)
    in `te_bouwen` wat er is aangeraakt.
    """
    con = _database(_vullen(1975, [1]) + _vullen(1976, [1]))
    oud_bestand = pdf.schrijf_jaaroverzicht(con, "top40", 1975, MAP, altijd=True)
    ander = pdf.schrijf_jaaroverzicht(con, "top40", 1976, MAP, altijd=True)
    assert pdf.is_actueel(con, oud_bestand, "top40", 1975)

    db.markeer_te_bouwen(con, lijst="top40", jaar=1975, reden="alias")
    assert not pdf.is_actueel(con, oud_bestand, "top40", 1975)
    assert pdf.is_actueel(con, ander, "top40", 1976),         "een jaargang die er niets mee te maken heeft blijft actueel"

    db.gebouwd(con, "top40", 1975)
    pdf.schrijf_jaaroverzicht(con, "top40", 1975, MAP, altijd=True)
    assert pdf.is_actueel(con, oud_bestand, "top40", 1975)


def test_ontbrekend_bestand_is_nooit_actueel():
    con = _database(_vullen(2020, [1]))
    assert not pdf.is_actueel(con, MAP / "bestaat-niet.pdf", "top40", 2020)


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
            # Een test die omvalt op een kapotte opzet nam vroeger de rest van
            # de reeks mee, en dan zie je geen eindstand meer.
            mislukt += 1
            print(f"KAPOT    {test.__name__}: {type(fout).__name__}: {fout}")
    print(f"\n{len(tests) - mislukt}/{len(tests)} geslaagd")
    return 1 if mislukt else 0


if __name__ == "__main__":
    sys.exit(main())
