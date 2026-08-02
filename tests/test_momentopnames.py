"""Tests voor de momentopnames (hitlijsten/momentopnames.py).

    python tests/test_momentopnames.py

Het bewaarbeleid is het enige hier dat een oordeel bevat, en het is precies het
soort ding dat stil verkeerd gaat: te veel weggooien merk je pas op het moment
dat je iets terug wilt. Vandaar dat de regels hier vastliggen met verzonnen
bestandsnamen, zonder dat er een database aan te pas komt.
"""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hitlijsten import momentopnames                          # noqa: E402


def _met_map(namen):
    """Zet een tijdelijke map met deze bestandsnamen als momentopnamemap."""
    tijdelijk = tempfile.TemporaryDirectory()
    map_ = Path(tijdelijk.name)
    for naam in namen:
        (map_ / naam).write_bytes(b"x")
    momentopnames.MAP = map_
    return tijdelijk


def _naam(dagen_terug: int, uur: int, reden: str = "run") -> str:
    moment = datetime.now() - timedelta(days=dagen_terug)
    return f"{moment.strftime('%Y%m%d')}-{uur:02d}0000-{reden}.sqlite.gz"


def test_naam_bevat_moment_en_reden():
    naam = momentopnames._naam("voor-opschonen", datetime(2026, 8, 2, 15, 4, 5))
    assert naam == "20260802-150405-voor-opschonen.sqlite.gz", naam


def test_rare_tekens_in_de_reden_worden_onschadelijk():
    naam = momentopnames._naam("voor / opschonen: alles!", datetime(2026, 1, 1))
    assert "/" not in naam and ":" not in naam


def test_de_laatste_twaalf_blijven_altijd_staan():
    namen = [_naam(0, uur) for uur in range(20)]
    houder = _met_map(namen)
    try:
        weg = momentopnames.opruimen()
        over = {p.name for p in momentopnames.lijst()}
        # Twaalf recente, plus de oudste van vandaag (die valt onder de
        # dagregel) -- de rest gaat weg.
        assert len(over) == 13, sorted(over)
        assert _naam(0, 19) in over and _naam(0, 0) in over
        assert len(weg) == 7
    finally:
        houder.cleanup()


def test_per_oudere_dag_blijft_de_oudste_over():
    """De oudste van een dag is de toestand van vóór de eerste ingreep."""
    namen = [_naam(dag, uur) for dag in range(1, 6) for uur in (8, 12, 20)]
    houder = _met_map(namen)
    try:
        momentopnames.opruimen()
        over = {p.name for p in momentopnames.lijst()}
        # Vijftien bestanden, twaalf zijn "recent" -- maar van elke dag hoort
        # in elk geval de oudste erbij te zitten.
        for dag in range(1, 6):
            assert _naam(dag, 8) in over, f"dag {dag} mist zijn oudste"
    finally:
        houder.cleanup()


def test_oud_en_niet_recent_gaat_weg():
    namen = [_naam(0, uur) for uur in range(12)]          # twaalf van vandaag
    namen += [_naam(momentopnames.DAGEN + 5, 9)]          # en een heel oude
    houder = _met_map(namen)
    try:
        weg = momentopnames.opruimen()
        assert [p.name for p in weg] == [_naam(momentopnames.DAGEN + 5, 9)]
    finally:
        houder.cleanup()


def test_lege_map_geeft_lege_lijst():
    houder = _met_map([])
    try:
        assert momentopnames.lijst() == []
        assert momentopnames.opruimen() == []
    finally:
        houder.cleanup()


def main() -> int:
    origineel = momentopnames.MAP
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
    momentopnames.MAP = origineel
    print(f"\n{len(tests) - mislukt}/{len(tests)} geslaagd")
    return 1 if mislukt else 0


if __name__ == "__main__":
    sys.exit(main())
