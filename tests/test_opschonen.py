"""Tests voor het opschonen (hitlijsten/opschonen.py en de sleutelregels).

    python tests/test_opschonen.py

Deze tests leggen vooral de *grenzen* vast. Opschonen dat te ver gaat is erger
dan opschonen dat te weinig doet: een verkeerd samengevoegd nummer valt niet op,
want het ziet er precies zo uit als een goed samengevoegd nummer. Vandaar dat
hier net zo veel staat over wat er NIET mag gebeuren.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hitlijsten.normalize import normaliseer, artiestsleutel   # noqa: E402
from hitlijsten.opschonen import (_kaal, _UITGAVE,              # noqa: E402
                                  meerderheidsnaam, naamvarianten,
                                  schoon_tekst, splits_kanten)


def _database(noteringen):
    """(lijst, artiest, titel, sleutel) -> database met die noteringen."""
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute(
        "CREATE TABLE noteringen (id INTEGER PRIMARY KEY, lijst TEXT, jaar INT,"
        " week INT, positie INT, titel TEXT, artiest TEXT, sleutel TEXT)")
    con.executemany(
        "INSERT INTO noteringen (lijst, jaar, week, positie, artiest, titel,"
        " sleutel) VALUES (?,2020,1,1,?,?,?)", noteringen)
    return con


# --- leestekens -------------------------------------------------------------


def test_backtick_wordt_apostrof():
    assert schoon_tekst("I`m Not In Love") == "I'm Not In Love"
    assert schoon_tekst("Rock `n` Roll") == "Rock 'n' Roll"


def test_vraagteken_en_hoofdletters_blijven():
    """Niet alles wat opvalt is fout."""
    assert schoon_tekst("Wat is geluk?") == "Wat is geluk?"
    assert schoon_tekst("T.N.T.") == "T.N.T."
    assert schoon_tekst("SEEIN' STARS") == "SEEIN' STARS"


def test_witruimte_en_onzichtbare_tekens():
    assert schoon_tekst("dubbele  spatie") == "dubbele spatie"
    assert schoon_tekst("  rand  ") == "rand"
    assert schoon_tekst("harde spatie") == "harde spatie"


def test_lege_tekst_blijft_leeg():
    assert schoon_tekst("") == ""
    assert schoon_tekst(None) is None


# --- de sleutelregels -------------------------------------------------------


def test_lidwoord_telt_niet_mee_bij_de_artiest():
    assert artiestsleutel("The Beatles") == artiestsleutel("Beatles")
    assert artiestsleutel("De Zangeres Zonder Naam") == \
        artiestsleutel("Zangeres Zonder Naam")


def test_lidwoord_in_een_titel_blijft_staan():
    """"The Wall" is niet "Wall" -- daar draagt het lidwoord betekenis."""
    assert normaliseer("The Wall", samenwerking=False) == "the wall"


def test_lidwoord_alleen_vooraan():
    assert artiestsleutel("Simon & The Sunsets") == "simon & the sunsets"


def test_bijzondere_letters_worden_vertaald_niet_weggegooid():
    """De o van Bløf werd vroeger geschrapt; dan werd "bløf" ineens "bl f"."""
    assert normaliseer("Bløf") == "blof" == normaliseer("Blof")
    assert normaliseer("Motörhead") == "motorhead"
    assert normaliseer("Sigur Rós") == "sigur ros"


# --- de juiste schrijfwijze kiezen ------------------------------------------


def test_accent_wint_altijd_van_de_meerderheid():
    """Een accent raakt kwijt onderweg; hij komt er nooit bij."""
    assert meerderheidsnaam({"Xander De Buisonje": 25,
                             "Xander De Buisonjé": 5}) == "Xander De Buisonjé"
    assert meerderheidsnaam({"Blof": 400, "Bløf": 13}) == "Bløf"


def test_hoofdletters_winnen_van_alles_klein():
    assert meerderheidsnaam({"coldplay": 1726, "Coldplay": 23}) == "Coldplay"


def test_anders_beslist_gewoon_het_aantal():
    """Over een tussenvoegsel valt te twisten; dan telt de gewoonte."""
    assert meerderheidsnaam({"Rob de Nijs": 503, "Rob De Nijs": 299}) == \
        "Rob de Nijs"


def test_kaal_ziet_bloef_en_blof_als_dezelfde_naam():
    assert _kaal("Bløf") == _kaal("Blof") == _kaal("BLOF")
    assert _kaal("André") == _kaal("Andre")


# --- de varianten indelen ---------------------------------------------------


def test_varianten_worden_naar_soort_gescheiden():
    con = _database([
        ("top40", "Coldplay", "Yellow", "coldplay|yellow"),
        ("top2000", "coldplay", "Yellow", "coldplay|yellow"),
        ("top40", "The Beatles", "Hey Jude", "beatles|hey jude"),
        ("top2000", "Beatles", "Hey Jude", "beatles|hey jude"),
        ("top40", "Frans Duijts", "Zeg Maar Niets Meer", "frans duijts|zeg"),
        ("top2000", "Frans Duyts", "Zeg Maar Niets Meer", "frans duijts|zeg"),
    ])
    bakken = naamvarianten(con)
    assert [c for c, _ in bakken["tekens"]] == ["coldplay"]
    assert [c for c, _ in bakken["lidwoord"]] == ["beatles"]
    assert [c for c, _ in bakken["anders"]] == ["frans duijts"]


def test_een_artiest_met_een_schrijfwijze_valt_nergens_in():
    con = _database([("top40", "Doe Maar", "Is Dit Alles", "doe maar|is dit")])
    assert all(not groepen for groepen in naamvarianten(con).values())


# --- dubbele A-kanten -------------------------------------------------------


def test_dubbele_a_kant_wordt_twee_nummers():
    assert splits_kanten("The Beatles", "No Reply ; Rock And Roll Music") == [
        ("The Beatles", "No Reply"), ("The Beatles", "Rock And Roll Music")]


def test_twee_artiesten_horen_bij_twee_kanten():
    assert splits_kanten("De Dijk ; The Scene",
                         "Iedereen Is Van De Wereld ; Nieuwe Laarzen") == [
        ("De Dijk", "Iedereen Is Van De Wereld"),
        ("The Scene", "Nieuwe Laarzen")]


def test_ongelijk_aantal_geeft_beide_kanten_de_hele_naam():
    """Drie artiesten bij twee titels is een samenwerking, geen tweede kant."""
    assert splits_kanten("A ; B ; C", "X ; Y") == [("A ; B ; C", "X"),
                                                   ("A ; B ; C", "Y")]


def test_zonder_puntkomma_verandert_er_niets():
    assert splits_kanten("Simon & Garfunkel", "The Boxer") == [
        ("Simon & Garfunkel", "The Boxer")]


# --- de uitgave voor het nummer ---------------------------------------------


def test_uitgave_gaat_van_de_titel_af():
    assert _UITGAVE.sub("", ">Abort, Retry, Fail?_ : Your Woman", count=1) ==         "Your Woman"
    assert _UITGAVE.sub("", "Live! : Roll Over Lay Down", count=1) ==         "Roll Over Lay Down"


def test_dubbelepunt_zonder_spaties_blijft_staan():
    """"Titel: ondertitel" is een andere vorm en geen uitgave."""
    assert _UITGAVE.sub("", "Titel: ondertitel", count=1) == "Titel: ondertitel"


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
