"""Tests voor het decenniumklassement (db.decennium_totalen).

    cd /volume1/Hitlijsten/app && . ./omgeving.sh
    ./venv/bin/python tests/test_decennium.py

De kern is dat dit klassement de som van de jaaroverzichten moet zijn -- niet
iets wat er ongeveer op lijkt. Daarom wordt er per jaargang gerekend en pas
daarna opgeteld, en telt een correctie van michajans.nl hier net zo mee als in
het jaarbestand.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hitlijsten.datums import vrijdag_tekst, vrijdag_van  # noqa: E402
from hitlijsten.db import decennium_totalen  # noqa: E402
from hitlijsten.excel import bouw_decennium_werkboek  # noqa: E402


def _database(noteringen, correcties=()):
    """Kale database. Noteringen zijn (jaar, week, positie, artiest, titel)."""
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute(
        "CREATE TABLE noteringen (id INTEGER PRIMARY KEY, lijst TEXT, jaar INT,"
        " week INT, positie INT, titel TEXT, artiest TEXT, label TEXT, sleutel TEXT)"
    )
    con.execute(
        "CREATE TABLE correcties (jaar INT, lijst TEXT, sleutel TEXT, punten INT,"
        " hoogste INT, weken INT, bron TEXT)"
    )
    con.executemany(
        "INSERT INTO noteringen (lijst, jaar, week, positie, titel, artiest, label,"
        " sleutel) VALUES ('top40',?,?,?,?,?,NULL,?)",
        [(j, w, p, titel, artiest, f"{artiest.lower()}|{titel.lower()}")
         for j, w, p, artiest, titel in noteringen],
    )
    con.executemany(
        "INSERT INTO correcties (jaar, lijst, sleutel, punten, hoogste, weken, bron)"
        " VALUES (?,'top40',?,?,?,?,'michajans')",
        correcties,
    )
    return con


def _vullen(jaar, weken, tot=40):
    """Vulnummers zodat de lijst die weken echt `tot` lang is."""
    return [(jaar, w, p, f"Vul {p}", "Lied") for w in weken for p in range(1, tot + 1)]


# --- punten -----------------------------------------------------------------


def test_punten_zijn_de_som_over_de_jaargangen():
    # Week 1 van 2021 op 1, week 1 van 2022 op 5, lijst is 40 lang.
    rijen = [(2021, 1, 1, "A", "B"), (2022, 1, 5, "A", "B")]
    rijen += _vullen(2021, [1]) + _vullen(2022, [1])
    n = next(x for x in decennium_totalen(_database(rijen), "top40", 2020)
             if x["sleutel"] == "a|b")
    assert n["punten"] == (40 - 1 + 1) + (40 - 5 + 1) == 76
    assert n["weken"] == 2
    assert n["hoogste"] == 1, "de beste notering uit beide jaargangen"
    assert n["jaren"] == [2021, 2022]


def test_lijstlengte_wordt_per_week_bepaald():
    """Een kortere lijst levert minder punten voor dezelfde positie."""
    rijen = [(2021, 1, 1, "A", "B"), (2021, 2, 1, "A", "B")]
    rijen += _vullen(2021, [1], tot=40) + _vullen(2021, [2], tot=20)
    n = decennium_totalen(_database(rijen), "top40", 2020)[0]
    assert n["punten"] == 40 + 20


def test_correctie_van_michajans_telt_mee_zoals_in_het_jaarbestand():
    rijen = [(2021, 1, 1, "A", "B"), (2022, 1, 5, "A", "B")]
    rijen += _vullen(2021, [1]) + _vullen(2022, [1])
    # Voor 2021 geldt zijn cijfer: 100 punten, hoogste 2, 7 weken.
    con = _database(rijen, correcties=[(2021, "a|b", 100, 2, 7)])
    n = next(x for x in decennium_totalen(con, "top40", 2020) if x["sleutel"] == "a|b")
    assert n["punten"] == 100 + 36, "2021 gecorrigeerd, 2022 zelf gerekend"
    assert n["weken"] == 7 + 1
    assert n["hoogste"] == 2
    assert n["gecorrigeerd"] is True


def test_gedeelde_positie_telt_de_week_een_keer():
    """In de jaren zestig stonden er soms twee artiesten op dezelfde positie."""
    rijen = [(1965, 1, 7, "A", "B"), (1965, 1, 7, "A", "B")]
    rijen += _vullen(1965, [1])
    n = next(x for x in decennium_totalen(_database(rijen), "top40", 1960)
             if x["sleutel"] == "a|b")
    assert n["weken"] == 1 and n["punten"] == 34


# --- volgorde en herkomst ---------------------------------------------------


def test_aflopend_op_punten():
    rijen = [(2021, 1, 1, "Beste", "X"), (2021, 1, 30, "Slechtste", "Y"),
             (2021, 1, 10, "Midden", "Z")]
    rijen += _vullen(2021, [1])
    uit = decennium_totalen(_database(rijen), "top40", 2020)
    punten = [n["punten"] for n in uit]
    assert punten == sorted(punten, reverse=True)
    assert uit[0]["artiest"] == "Beste"


def test_beste_jaar_is_waar_de_meeste_punten_vielen():
    # 2021: één week op 30 (11 punten). 2023: twee weken op 1 (80 punten).
    rijen = [(2021, 1, 30, "A", "B"), (2023, 1, 1, "A", "B"), (2023, 2, 1, "A", "B")]
    rijen += _vullen(2021, [1]) + _vullen(2023, [1, 2])
    n = next(x for x in decennium_totalen(_database(rijen), "top40", 2020)
             if x["sleutel"] == "a|b")
    assert n["beste_jaar"] == 2023


def test_laatste_schrijfwijze_wint():
    rijen = [(2021, 1, 5, "Antoon ft. Sef", "Zomer"),
             (2022, 1, 5, "Antoon ft. Sef", "Zomer")]
    rijen += _vullen(2021, [1]) + _vullen(2022, [1])
    # Dezelfde sleutel, latere jaargang met een andere schrijfwijze.
    con = _database(rijen)
    con.execute(
        "UPDATE noteringen SET artiest='Antoon feat. Sef'"
        " WHERE jaar=2022 AND sleutel='antoon ft. sef|zomer'")
    n = next(x for x in decennium_totalen(con, "top40", 2020)
             if x["sleutel"] == "antoon ft. sef|zomer")
    assert n["artiest"] == "Antoon feat. Sef"


# --- de randen van het decennium --------------------------------------------


def test_datums_zijn_de_uitzendvrijdagen_binnen_het_decennium():
    rijen = [(2021, 3, 5, "A", "B"), (2022, 7, 9, "A", "B")]
    rijen += _vullen(2021, [3]) + _vullen(2022, [7])
    n = next(x for x in decennium_totalen(_database(rijen), "top40", 2020)
             if x["sleutel"] == "a|b")
    assert n["eerste"] == vrijdag_tekst(2021, 3)
    assert n["laatste"] == vrijdag_tekst(2022, 7)


def test_notering_die_voor_het_decennium_begon_krijgt_een_pijl_terug():
    # Loopt van week 51 van 2019 (vorig decennium) tot week 2 van 2020.
    rijen = [(2019, 51, 4, "A", "B"), (2019, 52, 3, "A", "B"),
             (2020, 1, 2, "A", "B"), (2020, 2, 6, "A", "B")]
    rijen += _vullen(2019, [51, 52]) + _vullen(2020, [1, 2])
    n = next(x for x in decennium_totalen(_database(rijen), "top40", 2020)
             if x["sleutel"] == "a|b")
    assert n["begon_eerder"] is True and n["loopt_door"] is False
    # De datums blijven binnen het decennium; de pijl zegt dat er meer is.
    assert n["eerste"] == vrijdag_tekst(2020, 1)
    # En de punten van 2019 tellen niet mee in dit decennium.
    assert n["punten"] == (40 - 2 + 1) + (40 - 6 + 1)
    assert n["jaren"] == [2020]


def test_pijl_alleen_aan_de_rand_van_het_decennium():
    """Een notering over de jaarwisseling midden in het decennium telt niet."""
    rijen = [(2024, 52, 3, "A", "B"), (2025, 1, 2, "A", "B")]
    rijen += _vullen(2024, [52]) + _vullen(2025, [1])
    n = next(x for x in decennium_totalen(_database(rijen), "top40", 2020)
             if x["sleutel"] == "a|b")
    assert n["begon_eerder"] is False and n["loopt_door"] is False
    assert n["jaren"] == [2024, 2025]


def test_leeg_decennium_geeft_niets():
    assert decennium_totalen(_database(_vullen(2021, [1])), "top40", 1980) == []


# --- het werkboek -----------------------------------------------------------


def _werkblad(con, decennium=2020):
    """Bouw het werkboek in het geheugen en geef koppen + rijen terug."""
    wb = bouw_decennium_werkboek(con, "top40", decennium)
    if wb is None:
        return None, None, None
    ws = wb[wb.sheetnames[0]]
    koppen = [c.value for c in ws[2]]          # rij 1 is de toelichting
    rijen = [dict(zip(koppen, r))
             for r in ws.iter_rows(min_row=3, values_only=True)]
    return wb, koppen, rijen


def test_werkboek_heeft_een_tab_met_het_klassement():
    rijen = [(2021, 1, 1, "A", "B"), (2021, 1, 9, "C", "D")]
    rijen += _vullen(2021, [1])
    wb, koppen, uit = _werkblad(_database(rijen))
    assert wb.sheetnames == ["Klassement 2020-2029"]
    assert koppen == [
        "Artiest", "Titel", "Punten", "Hoogste positie", "Aantal weken genoteerd",
        "Jaargangen", "Binnenkomst", "Laatste notering",
        "Loopt buiten het decennium", "Sleutel",
    ]
    assert [r["Punten"] for r in uit] == sorted(
        (r["Punten"] for r in uit), reverse=True)


def test_werkboek_schrijft_echte_datums():
    rijen = [(2021, 3, 5, "A", "B")] + _vullen(2021, [3])
    _, _, uit = _werkblad(_database(rijen))
    n = next(r for r in uit if r["Sleutel"] == "a|b")
    assert isinstance(n["Binnenkomst"], (date, datetime))
    dag = n["Binnenkomst"].date() if isinstance(n["Binnenkomst"], datetime)         else n["Binnenkomst"]
    assert dag == vrijdag_van(2021, 3)


def test_werkboek_noemt_een_jaargangbereik():
    rijen = [(2021, 1, 5, "A", "B"), (2023, 1, 5, "A", "B"), (2024, 1, 5, "C", "D")]
    rijen += _vullen(2021, [1]) + _vullen(2023, [1]) + _vullen(2024, [1])
    _, _, uit = _werkblad(_database(rijen))
    assert next(r for r in uit if r["Sleutel"] == "a|b")["Jaargangen"] == "2021-2023"
    assert next(r for r in uit if r["Sleutel"] == "c|d")["Jaargangen"] == "2024"


def test_werkboek_meldt_wie_buiten_het_decennium_doorloopt():
    rijen = [(2019, 52, 3, "A", "B"), (2020, 1, 2, "A", "B")]
    rijen += _vullen(2019, [52]) + _vullen(2020, [1])
    _, _, uit = _werkblad(_database(rijen))
    n = next(r for r in uit if r["Sleutel"] == "a|b")
    assert n["Loopt buiten het decennium"] == "begon vorig decennium"


def test_werkboek_toont_de_bronkolom_alleen_als_er_gecorrigeerd_is():
    rijen = [(2021, 1, 1, "A", "B")] + _vullen(2021, [1])
    _, koppen, _ = _werkblad(_database(rijen))
    assert "Bron" not in koppen

    con = _database(rijen, correcties=[(2021, "a|b", 100, 2, 7)])
    _, koppen, uit = _werkblad(con)
    assert "Bron" in koppen
    assert next(r for r in uit if r["Sleutel"] == "a|b")["Bron"] == "michajans.nl"


def test_werkboek_van_een_leeg_decennium_is_niets():
    wb, _, _ = _werkblad(_database(_vullen(2021, [1])), decennium=1980)
    assert wb is None


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
