"""Het zoeken: bevat, exact, jokers, spaties en de fuzzy-variant.

    python tests/test_zoeken.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import veilig  # noqa: F401  -- moet vóór hitlijsten, zie veilig.py
from hitlijsten import zoeken                                   # noqa: E402
from hitlijsten.web.app import zoekpatroon                      # noqa: E402


# --- het patroon voor LIKE --------------------------------------------------


def test_zonder_joker_is_het_bevat():
    assert zoekpatroon("beatles") == "%beatles%"


def test_een_sterretje_bepaalt_waar_het_woord_staat():
    assert zoekpatroon("beatles*") == "beatles%"
    assert zoekpatroon("*beatles") == "%beatles"
    assert zoekpatroon("*beat*") == "%beat%"


def test_exact_zet_er_niets_omheen():
    """Anders vindt "fame" ook "Hall Of Fame", en dat is niet exact."""
    assert zoekpatroon("fame", "exact") == "fame"


def test_exact_laat_een_joker_wel_staan():
    """Een sterretje is een uitspraak over begin of eind; die blijft zinnig."""
    assert zoekpatroon("fame*", "exact") == "fame%"


def test_een_ingetypt_procentteken_is_geen_joker():
    """Wie "50%" zoekt bedoelt vijftig procent, niet alles."""
    assert zoekpatroon("50%") == "%50" + chr(92) + "%%"


def test_spaties_aan_de_rand_blijven_staan():
    """De hele reden dat deze functie niet meer stript.

    Zonder dit kun je niet zoeken op " y " -- spatie, y, spatie -- en dat is
    hoe je "Digno Garcia y Sus Carios" vindt zonder elk woord met een y erin
    binnen te halen.
    """
    assert zoekpatroon(" y ") == "% y %"
    assert zoekpatroon(" y ") != zoekpatroon("y")


def test_lege_term_geeft_geen_patroon():
    assert zoekpatroon("") == ""
    assert zoekpatroon(None) == ""


# --- fuzzy ------------------------------------------------------------------


ARCHIEF = zoeken.bereid_voor([
    ("queen|bohemian rhapsody", "Queen", "Bohemian Rhapsody"),
    ("chubby checker|the twist", "Chubby Checker", "The Twist"),
    ("abba|waterloo", "ABBA", "Waterloo"),
    ("doe maar|is dit alles", "Doe Maar", "Is Dit Alles"),
    ("beyonce|halo", "Beyoncé", "Halo"),
    ("golden earring|radar love", "Golden Earring", "Radar Love"),
])


def _sleutels(term, waar="beide"):
    return [s for s, _ in zoeken.treffers(term, ARCHIEF, waar)]


def test_een_tikfout_vindt_het_nummer_nog():
    assert _sleutels("bohemian rapsody")[0] == "queen|bohemian rhapsody"


def test_een_verkeerd_gespelde_artiest_ook():
    assert _sleutels("chubby chequer")[0] == "chubby checker|the twist"


def test_artiest_en_titel_samen_gezocht():
    """"queen bohemian" staat in geen van beide velden zo."""
    assert _sleutels("queen bohemian")[0] == "queen|bohemian rhapsody"


def test_een_letterlijke_treffer_staat_bovenaan():
    treffers = zoeken.treffers("waterloo", ARCHIEF)
    assert treffers[0] == ("abba|waterloo", 1.0), treffers[:2]


def test_accenten_maken_niet_uit():
    assert "beyonce|halo" in _sleutels("beyoncé")
    assert "beyonce|halo" in _sleutels("beyonce")


def test_waar_beperkt_waar_gekeken_wordt():
    assert _sleutels("waterloo", "artiest") == []
    assert _sleutels("waterloo", "titel") == ["abba|waterloo"]


def test_iets_wat_nergens_op_lijkt_geeft_niets():
    assert _sleutels("xylofoonconcert") == []


def test_te_korte_term_geeft_niets():
    """Op twee tekens lijkt alles op alles; dan komt het hele archief terug."""
    assert zoeken.treffers("ab", ARCHIEF) == []


def test_de_beste_treffer_staat_voorop():
    """De volgorde is bij fuzzy het halve antwoord."""
    treffers = zoeken.treffers("radar love", ARCHIEF)
    assert treffers[0][0] == "golden earring|radar love"
    assert treffers[0][1] >= treffers[-1][1]


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
