"""De Nederlandstalig-herkenning: titelroute, lijstbewijs, artiestroute, hand."""
from __future__ import annotations

import os
import sys
import tempfile

os.environ.setdefault("HITLIJSTEN_DATA", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hitlijsten import db  # noqa: E402
from hitlijsten.taal import (herken_alles, nederlandstalige_sleutels,  # noqa: E402
                             titel_lijkt_nederlands, titel_lijkt_vreemd,
                             zet_hand)


def test_titel_herkent_duidelijk_nederlands():
    for titel in ("Zij Gelooft In Mij", "Het Is Een Nacht", "Mijn Gebed",
                  "Vluchten Kan Niet Meer", "Dromen Zijn Bedrog",
                  "Kleine Jongen", "Iedereen Is Van De Wereld"):
        assert titel_lijkt_nederlands(titel), titel


def test_titel_gokt_niet_bij_twijfel():
    # Korte of anderstalige titels krijgen géén vlag op titel alleen.
    for titel in ("Marian", "Fernando", "Venus", "My Way", "Waterloo",
                  "Una Paloma Blanca", "Du", "C'est La Vie", "Avond"):
        assert not titel_lijkt_nederlands(titel), titel


def test_vreemde_titel_blokkeert():
    assert titel_lijkt_vreemd("My Way")
    assert titel_lijkt_vreemd("Ich Liebe Dich")
    assert not titel_lijkt_vreemd("Avond")


def _vul(con, rijen):
    con.executemany(
        "INSERT INTO noteringen (lijst, jaar, week, positie, titel, artiest,"
        " sleutel, site_status) VALUES (?,?,?,?,?,?,?,'ok')", rijen)
    con.commit()


def test_drietrap_en_hand():
    from hitlijsten.taal import SCHEMA

    with db.verbinding() as con:
        con.executescript(SCHEMA)
        con.execute("DELETE FROM noteringen")
        con.execute("DELETE FROM taal")
        _vul(con, [
            # lijstbewijs: staat in de oranje top 30
            ("oranje", 2020, 1, 1, "Kort", "Zanger A", "zanger a|kort"),
            ("top40", 2020, 1, 1, "Kort", "Zanger A", "zanger a|kort"),
            ("oranje", 2020, 2, 1, "Blijf", "Zanger A", "zanger a|blijf"),
            ("oranje", 2020, 3, 1, "Dans", "Zanger A", "zanger a|dans"),
            # dezelfde artiest, onbeslisbare titel -> artiestroute (nl >= 2)
            ("top40", 2020, 2, 1, "Hetzelfde Liedje Voor Jou", "Zanger A",
             "zanger a|hetzelfde liedje voor jou"),
            ("top40", 2020, 3, 1, "Woord", "Zanger A", "zanger a|woord"),
            # maar een duidelijk anderstalige titel blijft ongemarkeerd
            ("top40", 2020, 4, 1, "My English Song", "Zanger A",
             "zanger a|my english song"),
            # titelroute
            ("top40", 2020, 5, 1, "Zij Gelooft In Mij", "Ander",
             "ander|zij gelooft in mij"),
            # niets: engelstalig
            ("top40", 2020, 6, 1, "Yesterday", "Beatles", "beatles|yesterday"),
        ])
        telling = herken_alles(con)
        nlset = nederlandstalige_sleutels(con)

        assert "zanger a|kort" in nlset                       # lijst
        assert "zanger a|woord" in nlset                      # artiest
        assert "zanger a|my english song" not in nlset        # geblokkeerd
        assert "ander|zij gelooft in mij" in nlset            # titel
        assert "beatles|yesterday" not in nlset
        assert telling["lijst"] == 3

        # hand wint van de automatiek, ook na een nieuwe run
        zet_hand(con, "beatles|yesterday", True)
        herken_alles(con)
        r = con.execute("SELECT nederlandstalig, bron FROM taal"
                        " WHERE sleutel='beatles|yesterday'").fetchone()
        assert r["nederlandstalig"] == 1 and r["bron"] == "hand"


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
