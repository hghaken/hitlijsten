"""Tests voor de tien ranglijsten (hitlijsten/wetenswaardigheden.py).

    python tests/test_wetenswaardigheden.py

De cijfers zien er altijd plausibel uit, ook als ze fout zijn — een ranglijst
geeft nu eenmaal altijd een winnaar. Daarom staan hier de randgevallen vast:
gedeelde posities, terugkeer uit het niets, en het verschil tussen "twee weken
achter elkaar" en "twee losse periodes".
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hitlijsten.wetenswaardigheden import cijfers, verzamel  # noqa: E402


def _database(noteringen):
    """Kale database. Noteringen zijn (jaar, week, positie, artiest, titel)."""
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute(
        "CREATE TABLE noteringen (id INTEGER PRIMARY KEY, lijst TEXT, jaar INT,"
        " week INT, positie INT, titel TEXT, artiest TEXT, sleutel TEXT)"
    )
    con.executemany(
        "INSERT INTO noteringen (lijst, jaar, week, positie, titel, artiest,"
        " sleutel) VALUES ('top40',?,?,?,?,?,?)",
        [(j, w, p, titel, artiest, f"{artiest.lower()}|{titel.lower()}")
         for j, w, p, artiest, titel in noteringen],
    )
    return con


def _vullen(jaar, weken, tot=40):
    """Vulnummers zodat de lijst die weken echt `tot` lang is."""
    return [(jaar, w, p, f"Vul {p}", "Lied") for w in weken for p in range(1, tot + 1)]


def _blok(con, sleutel):
    return next(b for b in verzamel(con, "top40") if b.sleutel == sleutel)


def _regel(con, sleutel, naam):
    """De regel van één artiest of nummer uit een blok, of None."""
    return next((r for r in _blok(con, sleutel).rijen if naam in r["naam"]), None)


# --- de artiestenlijsten ----------------------------------------------------


def test_meeste_noteringen_telt_nummers_niet_weken():
    rijen = [(2020, w, 1, "Veelschrijver", f"Lied {i}")
             for i, w in enumerate(range(1, 6))]            # 5 nummers, 5 weken
    rijen += [(2020, w, 2, "Langzitter", "Eén Lied")
              for w in range(1, 21)]                        # 1 nummer, 20 weken
    rijen += _vullen(2020, range(1, 21))
    con = _database(rijen)
    assert _regel(con, "noteringen", "Veelschrijver")["waarde"] == "5"
    assert _regel(con, "noteringen", "Langzitter")["waarde"] == "1"
    # Omgekeerd bij de weken.
    assert _regel(con, "weken", "Langzitter")["waarde"] == "20"


def test_nummer1_telt_per_nummer_niet_per_week():
    """Vier weken op 1 met hetzelfde nummer blijft één nummer 1-hit."""
    rijen = [(2020, w, 1, "A", "Lang Op Een") for w in range(1, 5)]
    rijen += [(2020, 5, 1, "A", "Kort Op Een")]
    rijen += _vullen(2020, range(1, 6))
    assert _regel(_database(rijen), "nummer1s", "A")["waarde"] == "2"


def test_artiest_blijft_een_artiest_bij_een_andere_schrijfwijze():
    """De sleutel is genormaliseerd, dus ft. en feat. lopen samen."""
    rijen = [(2020, 1, 5, "Antoon ft. Sef", "Zomer"),
             (2020, 2, 4, "Antoon feat. Sef", "Zomer"),
             (2020, 3, 3, "Antoon feat. Sef", "Winter")]
    rijen += _vullen(2020, range(1, 4))
    con = _database(rijen)
    # Beide schrijfwijzen normaliseren naar dezelfde sleutel, dus één artiest...
    regel = _regel(con, "noteringen", "Antoon")
    assert regel["waarde"] == "2", "twee nummers, niet vier"
    # ...en de laatst geziene schrijfwijze wordt getoond.
    assert regel["naam"] == "Antoon feat. Sef"


# --- de nummerlijsten -------------------------------------------------------


def test_gedeelde_positie_telt_de_week_een_keer():
    """In de jaren zestig stond hetzelfde nummer soms twee keer in een week."""
    rijen = [(1965, 1, 7, "A", "B"), (1965, 1, 9, "A", "B"), (1965, 2, 5, "A", "B")]
    rijen += _vullen(1965, [1, 2])
    con = _database(rijen)
    assert _regel(con, "langst", "A — B")["waarde"] == "2 weken"


def test_langst_op_een_telt_alleen_de_eerste_plaats():
    rijen = [(2020, 1, 1, "A", "B"), (2020, 2, 1, "A", "B"), (2020, 3, 2, "A", "B")]
    rijen += _vullen(2020, range(1, 4))
    con = _database(rijen)
    assert _regel(con, "op-een", "A — B")["waarde"] == "2 weken"
    assert _regel(con, "op-een", "Vul 2") is None, "wie nooit op 1 stond hoort er niet in"


def test_notering_loopt_over_de_jaargrens_door():
    """Week 52 en week 1 erna zijn één periode, geen twee."""
    rijen = [(2018, 51, 5, "A", "B"), (2018, 52, 4, "A", "B"),
             (2019, 1, 3, "A", "B"), (2019, 2, 2, "A", "B")]
    rijen += _vullen(2018, [51, 52]) + _vullen(2019, [1, 2])
    con = _database(rijen)
    assert _regel(con, "langst", "A — B")["waarde"] == "4 weken"
    assert _regel(con, "terugkeer", "A — B") is None, "geen gat, dus geen terugkeer"


def test_eerste_week_van_de_hele_lijst_is_geen_binnenkomst():
    """In de allereerste week was alles nieuw; dat zegt niets."""
    rijen = [(1965, 1, 1, "Toen Al", "Er"), (1965, 2, 1, "Toen Al", "Er"),
             (1965, 2, 3, "Nieuw", "Binnen")]
    rijen += _vullen(1965, [1, 2])
    con = _database(rijen)
    assert _regel(con, "binnenkomers", "Toen Al") is None
    assert _regel(con, "binnenkomers", "Nieuw — Binnen")["waarde"] == "#3"


def test_sprong_alleen_tussen_twee_opeenvolgende_weken():
    """Een terugkeer uit het niets is geen stijging."""
    # Week 1 op 30, dan drie weken weg, dan week 5 op 2.
    rijen = [(2020, 1, 30, "Terug", "Uit Niets"), (2020, 5, 2, "Terug", "Uit Niets")]
    # En een echte klimmer: week 1 op 30, week 2 op 4.
    rijen += [(2020, 1, 29, "Klimmer", "Echt"), (2020, 2, 4, "Klimmer", "Echt")]
    rijen += _vullen(2020, range(1, 6))
    con = _database(rijen)
    assert _regel(con, "sprongen", "Terug") is None
    assert _regel(con, "sprongen", "Klimmer")["waarde"] == "#29 → #4 (+25)"


def test_weg_naar_de_eerste_plaats_slaat_directe_binnenkomers_over():
    rijen = [(2020, 2, 20, "Klimt", "Langzaam"), (2020, 3, 8, "Klimt", "Langzaam"),
             (2020, 4, 1, "Klimt", "Langzaam"),
             (2020, 2, 1, "Meteen", "Op Een")]
    rijen += _vullen(2020, range(1, 5))
    con = _database(rijen)
    assert _regel(con, "onderweg", "Klimt")["waarde"] == "2 weken"
    assert _regel(con, "onderweg", "Meteen") is None


def test_terugkeer_meet_het_gat_tussen_twee_periodes():
    # Week 1-2 in 1970, daarna pas week 1 van 1972 weer.
    rijen = [(1970, 1, 5, "A", "B"), (1970, 2, 6, "A", "B"), (1972, 1, 9, "A", "B")]
    rijen += _vullen(1970, [1, 2]) + _vullen(1971, range(1, 53)) + _vullen(1972, [1])
    con = _database(rijen)
    regel = _regel(con, "terugkeer", "A — B")
    # 1970 week 2 -> 1972 week 1 is 51 lege weken ertussen, dus 52 stappen.
    assert regel["waarde"] == "1 jaar"
    # En let op de datum: 1972 is een van de negen jaargangen waarvan week 1 op
    # 31 december van het jaar ervoor werd uitgezonden. Dat is geen fout.
    assert regel["bij"] == "09/01/1970 → 31/12/1971"


def test_lege_database_geeft_geen_blokken():
    assert verzamel(_database([]), "top40") == []


def test_cijfers_tellen_de_hele_lijst():
    rijen = [(2020, 1, 1, "A", "B"), (2020, 2, 1, "A", "B"), (2020, 1, 2, "C", "D")]
    c = cijfers(_database(rijen), "top40")
    assert c["noteringen"] == 3 and c["nummers"] == 2 and c["artiesten"] == 2
    assert (c["van"], c["tot"], c["weken"]) == (2020, 2020, 2)


# --- de jaarlijkse lijsten --------------------------------------------------
#
# Dezelfde tien vragen, andere eenheid: een editie in plaats van een week. De
# berekening verandert niet, de woorden wel -- en juist daar zit het risico,
# want "26 weken" bij een lijst die een keer per jaar wordt uitgezonden is geen
# afrondingsfout maar onzin.


def _jaarlijkse_database(noteringen, lijst="arrow"):
    """Zelfde vorm, maar alles in week 52 -- zo staat een editie in de database."""
    con = _database([])
    con.executemany(
        "INSERT INTO noteringen (lijst, jaar, week, positie, titel, artiest,"
        " sleutel) VALUES (?,?,52,?,?,?,?)",
        [(lijst, j, p, titel, artiest, f"{artiest.lower()}|{titel.lower()}")
         for j, p, artiest, titel in noteringen],
    )
    return con


def test_jaarlijkse_lijst_telt_edities_en_zegt_dat_ook():
    rijen = [(j, 1, "Pearl Jam", "Black") for j in range(2019, 2026)]
    rijen += [(j, 2, "Vul", "Lied") for j in range(2019, 2026)]
    blok = next(b for b in verzamel(_jaarlijkse_database(rijen), "arrow")
                if b.sleutel == "langst")
    assert blok.titel == "Vaakst in de lijst", blok.titel
    assert blok.kolommen == ["Nummer", "Edities", "Edities"], blok.kolommen
    assert blok.rijen[0]["waarde"] == "7 edities", blok.rijen[0]["waarde"]
    # Geen datum maar een jaartal: 26/12/2019 suggereert een precisie die er
    # niet is.
    assert blok.rijen[0]["bij"] == "2019 – 2025", blok.rijen[0]["bij"]


def test_afwezigheid_bij_een_jaarlijkse_lijst_telt_edities_geen_weken():
    # Twee edities weg (2021 en 2022) en dan terug. Als de weekregel meeliep
    # zou hier "2 weken" staan; het zijn twee edities, oftewel twee jaar.
    rijen = [(j, 1, "Terug", "Van Weggeweest") for j in (2019, 2020, 2023)]
    rijen += [(j, 2, "Vul", "Lied") for j in range(2019, 2024)]
    blok = next(b for b in verzamel(_jaarlijkse_database(rijen), "arrow")
                if b.sleutel == "terugkeer")
    assert blok.titel == "Langste afwezigheid", blok.titel
    regel = blok.rijen[0]
    assert regel["waarde"] == "3 edities", regel["waarde"]
    assert regel["bij"] == "2020 → 2023", regel["bij"]


def test_weeklijst_houdt_zijn_eigen_woorden():
    """De omschakeling mag de Top 40 niet raken."""
    rijen = [(2020, w, 1, "A", "B") for w in range(1, 4)]
    blok = _blok(_database(rijen + _vullen(2020, range(1, 4))), "langst")
    assert blok.titel == "Langst genoteerd"
    assert blok.kolommen == ["Nummer", "Weken", "Periode"], blok.kolommen
    assert blok.rijen[0]["waarde"].endswith("weken")


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
