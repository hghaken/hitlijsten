"""Zelftest voor de Oranje Top 30-parser.

Draait volledig op de HTML in .cache\\oranje -- geen netwerkverkeer. Werkt zowel
onder pytest als met `python tests\\test_oranje.py`.

    cd H:\\HitLijsten_Verzamelen
    python tests\\test_oranje.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hitlijsten.fetch import cache_pad                       # noqa: E402
from hitlijsten.models import ParseFout, controleer_lijst    # noqa: E402
from hitlijsten.parsers import oranje                        # noqa: E402

JAAR = 2026
WEKEN = (1, 2, 10, 20, 29, 30)


def _html(week: int) -> str:
    """Lees uitsluitend uit de cache; ontbreekt die, dan faalt de test luid."""
    pad = cache_pad("oranje", JAAR, week)
    if not pad.exists():
        raise AssertionError(
            f"cache ontbreekt: {pad}\n"
            f"Vul hem eerst: python -c \"from hitlijsten.fetch import haal_html; "
            f"haal_html('oranje', {JAAR}, {week})\""
        )
    return pad.read_text(encoding="utf-8")


def _parse(week: int):
    return oranje.parse(_html(week), "oranje", JAAR, week)


def _op(noteringen, positie):
    for n in noteringen:
        if n.positie == positie:
            return n
    raise AssertionError(f"positie {positie} niet gevonden")


# --------------------------------------------------------------------------
# structuur
# --------------------------------------------------------------------------
def test_structuur_alle_weken():
    for week in WEKEN:
        noteringen = _parse(week)
        assert len(noteringen) == 30, f"week {week}: {len(noteringen)} noteringen"

        resultaat = controleer_lijst(noteringen, 30)
        assert resultaat.ok, f"week {week}: {resultaat.meldingen}"

        for n in noteringen:
            assert n.lijst == "oranje" and n.jaar == JAAR and n.week == week
            assert n.titel and n.artiest
            assert n.weken_genoteerd is not None and n.weken_genoteerd >= 1
            # Binnenkomer/re-entry <-> vorige positie moeten consistent zijn.
            if n.site_status in ("nieuw", "terug"):
                assert n.vorige_positie is None, f"week {week} pos {n.positie}"
            else:
                assert n.vorige_positie is not None, f"week {week} pos {n.positie}"


def test_bewegingsaanduiding_klopt_met_positieverschil():
    for week in WEKEN:
        for n in _parse(week):
            if n.vorige_positie is None:
                continue
            if n.vorige_positie == n.positie:
                verwacht = "gelijk"
            elif n.vorige_positie > n.positie:
                verwacht = "stijger"
            else:
                verwacht = "daler"
            assert n.site_status == verwacht, (
                f"week {week} pos {n.positie}: status {n.site_status} maar vorige week "
                f"{n.vorige_positie}"
            )


def test_label_altijd_gevuld_en_zonder_haakjes():
    for week in WEKEN:
        for n in _parse(week):
            assert n.label, f"week {week} pos {n.positie}: geen label"
            assert "(" not in n.label and ")" not in n.label, n.label


# --------------------------------------------------------------------------
# concrete waarden
# --------------------------------------------------------------------------
def test_week30_nummer_1():
    n = _op(_parse(30), 1)
    assert n.titel == "Cheerio"
    assert n.artiest == "Justen de Wildt"
    assert n.label == "cornelis music"
    assert n.weken_genoteerd == 20
    assert n.vorige_positie == 1
    assert n.site_status == "gelijk"


def test_week30_stijger():
    n = _op(_parse(30), 3)
    assert n.titel == "Jong & dom"          # ampersand in de titel
    assert n.artiest == "Tino Martin"
    assert n.label == "studio one records"
    assert n.vorige_positie == 7
    assert n.site_status == "stijger"


def test_titel_met_haakjes_wordt_niet_als_label_gelezen():
    n = _op(_parse(29), 4)
    assert n.titel == "Er hangt iets in de lucht (Amore)"
    assert n.artiest == "Corry Konings"
    assert n.label == "goldfinger music"    # niet "Amore"

    n = _op(_parse(1), 24)
    assert n.titel == "Unchained melody (Christmas edition)"
    assert n.label == "triple-a-music"


def test_binnenkomer():
    n = _op(_parse(30), 30)
    assert n.titel == "Veel te lange nacht"
    assert n.artiest == "Jeffrey Kuipers"
    assert n.label == "dmm"
    assert n.weken_genoteerd == 1
    assert n.vorige_positie is None
    assert n.site_status == "nieuw"


def test_re_entry_krijgt_status_terug():
    # Zelfde new.png-icoon als een binnenkomer, maar 92 weken genoteerd.
    n = _op(_parse(2), 27)
    assert n.titel == "Engelbewaarder"
    assert n.artiest == "Marco Schuitmaker"
    assert n.weken_genoteerd == 92
    assert n.vorige_positie is None
    assert n.site_status == "terug"


def test_artiest_met_ampersand_blijft_heel():
    treffers = [
        n
        for week in WEKEN
        for n in _parse(week)
        if n.artiest == "Suzan & Freek"
    ]
    assert treffers, "verwachtte 'Suzan & Freek' ergens in de geteste weken"
    assert treffers[0].label == "suzan & freek"   # ampersand ook in het label


# --------------------------------------------------------------------------
# foutafhandeling: nooit stil een lege lijst
# --------------------------------------------------------------------------
def test_parsefout_bij_onbruikbare_html():
    for rommel in ("<html><body>niks</body></html>", "", "<div id='list'></div>"):
        try:
            oranje.parse(rommel, "oranje", JAAR, 30)
        except ParseFout:
            pass
        else:
            raise AssertionError(f"verwachtte ParseFout voor {rommel!r}")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    mislukt = 0
    for test in tests:
        try:
            test()
        except Exception as fout:  # noqa: BLE001
            mislukt += 1
            print(f"FAIL {test.__name__}: {fout}")
        else:
            print(f"ok   {test.__name__}")
    print(f"\n{len(tests) - mislukt}/{len(tests)} geslaagd")
    return 1 if mislukt else 0


if __name__ == "__main__":
    raise SystemExit(main())
