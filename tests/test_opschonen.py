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


def test_dubbele_haken_worden_enkele():
    """De disambiguatie van Music Datastats blijft, de tweede haak niet."""
    assert schoon_tekst("The Scorpions ((GBR))") == "The Scorpions (GBR)"
    assert schoon_tekst("Snow ((Hey Oh))") == "Snow (Hey Oh)"
    assert schoon_tekst("Amber ((= Marie Claire Cremers))") ==         "Amber (= Marie Claire Cremers)"


def test_meer_dan_een_paar_haken_in_een_regel():
    assert schoon_tekst("Someday Child ((1966)) / Same Old Song ((1971))") ==         "Someday Child (1966) / Same Old Song (1971)"


def test_enkele_haken_blijven_met_rust():
    assert schoon_tekst("Sweet Dreams (Are Made Of This)") ==         "Sweet Dreams (Are Made Of This)"


def test_een_aanduiding_voor_een_samenwerking():
    """feat. / feat / ft. / ft / featuring worden allemaal &."""
    from hitlijsten.opschonen import eenduidige_credit

    assert eenduidige_credit("Calvin Harris feat. Rihanna") ==         "Calvin Harris & Rihanna"
    assert eenduidige_credit("Ali B ft. Diggy Dex") == "Ali B & Diggy Dex"
    assert eenduidige_credit("DJ Fresh Featuring Sian Evans") ==         "DJ Fresh & Sian Evans"


def test_die_woorden_binnen_een_naam_blijven_staan():
    """Blue Feather is geen samenwerking en Fat Boys ook niet."""
    from hitlijsten.opschonen import eenduidige_credit

    for naam in ("Blue Feather", "Fat Boys", "Kraftwerk", "Ftisk"):
        assert eenduidige_credit(naam) == naam, naam


def test_feat_en_ampersand_leveren_dezelfde_sleutel():
    """Anders zijn "A feat. B" en "A & B" twee artiesten, en dat is onzin."""
    assert artiestsleutel("Calvin Harris feat. Rihanna") ==         artiestsleutel("Calvin Harris & Rihanna")


def test_gastartiest_verhuist_van_de_titel_naar_de_artiest():
    from hitlijsten.opschonen import gast_uit_titel

    assert gast_uit_titel("Andrea Bocelli", "Vivere (feat. Gerardina Trovato)")         == ("Andrea Bocelli & Gerardina Trovato", "Vivere")
    assert gast_uit_titel("Dr. Dre", "Still D.R.E. (feat. Snoop Dogg)")         == ("Dr. Dre & Snoop Dogg", "Still D.R.E.")


def test_with_in_een_titel_is_gewoon_een_woord():
    """Zonder deze grens sneuvelt de halve Top 40."""
    from hitlijsten.opschonen import gast_uit_titel

    for artiest, titel in [("U2", "With Or Without You"),
                           ("Roberta Flack", "Killing Me Softly With His Song"),
                           ("Stealers Wheel", "Stuck In The Middle With You"),
                           ("Whitney Houston",
                            "I Wanna Dance With Somebody (Who Loves Me)")]:
        assert gast_uit_titel(artiest, titel) == (artiest, titel), titel


def test_gast_die_al_bij_de_artiest_staat_wordt_niet_verdubbeld():
    from hitlijsten.opschonen import gast_uit_titel

    assert gast_uit_titel("Eminem & Rihanna", "Love The Way You Lie (feat. Rihanna)")         == ("Eminem & Rihanna", "Love The Way You Lie")


def test_x_tussen_twee_artiesten_wordt_ampersand():
    from hitlijsten.opschonen import x_is_samenwerking

    assert x_is_samenwerking("Snelle x Maan") == "Snelle & Maan"
    assert x_is_samenwerking("ATB x Topic x A7S") == "ATB & Topic & A7S"


def test_de_x_in_een_naam_blijft_staan():
    """De valkuil: de x is ook gewoon een letter."""
    from hitlijsten.opschonen import x_is_samenwerking

    for naam in ("Lil Nas X & Billy Ray Cyrus", "Kygo & X Ambassadors",
                 "Machine Gun Kelly, X Ambassadors & Bebe Rexha",
                 "Dutch X Factor 2010", "Liberty X", "Cygnus X",
                 "X-Press 2 & David Byrne", "Richard-X vs Liberty-X"):
        assert x_is_samenwerking(naam) == naam, naam


def test_komma_tussen_twee_artiesten_wordt_ampersand():
    from hitlijsten.opschonen import komma_is_samenwerking

    assert komma_is_samenwerking("50 Cent, Dr. Dre & Alicia Keys") ==         "50 Cent & Dr. Dre & Alicia Keys"


def test_de_komma_in_een_bandnaam_blijft_staan():
    """Opgezocht en niet bedacht: MusicBrainz kent deze als één act."""
    from hitlijsten.opschonen import komma_is_samenwerking

    for naam in ("Earth, Wind & Fire", "Crosby, Stills, Nash & Young",
                 "Blood, Sweat & Tears", "Dave Dee, Dozy, Beaky, Mick & Tich",
                 "Grover Washington, Jr.", "Tyler, The Creator",
                 "Phats & Small & Earth, Wind & Fire",
                 "ELP [Emerson, Lake & Palmer]"):
        assert komma_is_samenwerking(naam) == naam, naam


def test_zoeken_zonder_jokerteken_is_bevat():
    """Wie "beatles" intypt wil ook "The Beatles" vinden."""
    from hitlijsten.web.app import zoekpatroon

    assert zoekpatroon("beatles") == "%beatles%"


def test_het_sterretje_bepaalt_waar_het_woord_staat():
    from hitlijsten.web.app import zoekpatroon

    assert zoekpatroon("beatles*") == "beatles%"      # begint ermee
    assert zoekpatroon("*beatles") == "%beatles"      # eindigt erop
    assert zoekpatroon("*beatles*") == "%beatles%"    # bevat
    assert zoekpatroon("rock*music") == "rock%music"  # ertussen


def test_een_ingetypt_procentteken_is_geen_joker():
    """Anders vindt "50%" ineens alles."""
    from hitlijsten.web.app import zoekpatroon

    assert zoekpatroon("50%") == "%50\%%"
    assert zoekpatroon("a_b") == "%a\_b%"


def test_met_tussen_twee_artiesten_wordt_ampersand():
    from hitlijsten.opschonen import met_is_samenwerking

    assert met_is_samenwerking("Wilma met Vader Abraham") ==         "Wilma & Vader Abraham"
    assert met_is_samenwerking("Paul De Leeuw - duet met Simone Kleinsma") ==         "Paul De Leeuw & Simone Kleinsma"
    assert met_is_samenwerking("Conny Vandenbos in duet met Janis Ian") ==         "Conny Vandenbos & Janis Ian"


def test_met_in_een_naam_of_zinsdeel_blijft_staan():
    from hitlijsten.opschonen import met_is_samenwerking

    for naam in ("Zondag Met Lubach & Fresku",
                 "Erik Hulzebosch with special guest: Fokko Met De Bordjes",
                 "Maggie MacNeal met dank aan Het Gewestelijk Orkest",
                 "Van Dik Hout met medewerking van Kirsten",
                 "Oh Sixteen-Oh Seven met zang van Thijs v.d. Molen",
                 "Metallica"):
        assert met_is_samenwerking(naam) == naam, naam


def test_met_en_ampersand_leveren_dezelfde_sleutel():
    assert artiestsleutel("Wilma met Vader Abraham") ==         artiestsleutel("Wilma & Vader Abraham")


def test_ondertitel_achter_een_streep_gaat_tussen_haken():
    from hitlijsten.opschonen import ondertitel_tussen_haken

    assert ondertitel_tussen_haken("Cheerleader - Felix Jaehn Remix") ==         "Cheerleader (Felix Jaehn Remix)"
    assert ondertitel_tussen_haken("Eye Of The Tiger - The Theme From Rocky III")         == "Eye Of The Tiger (The Theme From Rocky III)"
    assert ondertitel_tussen_haken("Another Brick In The Wall - Part II") ==         "Another Brick In The Wall (Part II)"


def test_medley_en_tweede_titel_blijven_met_streep():
    """"One Love - People Get Ready" is een medley, geen ondertitel."""
    from hitlijsten.opschonen import ondertitel_tussen_haken

    for t in ("One Love - People Get Ready", "Un Dia - One Day",
              "Buona Sera - Oh Marie", "De Storm - Geef Niet Op",
              "Savage Love (Laxed - Siren Beat)"):
        assert ondertitel_tussen_haken(t) == t, t


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


# --- wat je in het aliasscherm intypt ---------------------------------------


def test_aliasscherm_maakt_er_een_echte_sleutel_van():
    """Je typt wat je op de site ziet; dat moet ook werken.

    Een alias wordt opgezocht met de sleutel. Typ je "ABBA*Teens|Mamma Mia",
    dan wordt die regel nooit gevonden -- en het vervelendste is dat er geen
    foutmelding komt, want hij staat er keurig in.
    """
    from hitlijsten.web.app import _als_sleutel

    assert _als_sleutel("ABBA*Teens|Mamma Mia") == "abba teens|mamma mia"
    assert _als_sleutel("The Beatles|Hey Jude") == "beatles|hey jude"
    # Al goed ingetypt blijft ongemoeid.
    assert _als_sleutel("a teens|super trouper") == "a teens|super trouper"
    # En zonder streep valt er niets te normaliseren.
    assert _als_sleutel("losse tekst") == "losse tekst"


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


# --- de sleutel volgt de naam -----------------------------------------------


def test_hernoemen_mag_een_samenvoeging_niet_ongedaan_maken():
    """De valkuil waar dit een keer in is gelopen.

    De sleutel wordt uit de naam berekend. Stel je "ACDC" bij naar "AC/DC", dan
    levert die naam ineens de sleutel "ac dc" op in plaats van "acdc" -- en trok
    de eerstvolgende herberekening de zojuist samengevoegde artiest weer uit
    elkaar. Sinds `verzeker_aliassen` volgt de sleutel de naam, en dan is een
    herberekening onschadelijk hoe vaak je hem ook draait.
    """
    from hitlijsten.normalize import artiestsleutel

    assert artiestsleutel("ACDC") == "acdc"
    assert artiestsleutel("AC/DC") == "ac dc"
    # De twee zijn dus niet vanzelf gelijk: er moet een alias tussen, en die
    # wijst naar de sleutel die uit de vastgestelde naam volgt.
    assert artiestsleutel("AC/DC") != artiestsleutel("ACDC")


# --- alleen bouwen wat er veranderd is --------------------------------------


def _schone_database():
    from hitlijsten import db as dbmod

    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(dbmod.SCHEMA)
    con.executemany(
        "INSERT INTO noteringen (lijst, jaar, week, positie, artiest, titel,"
        " site_status, sleutel) VALUES (?,?,1,1,'A','B','nieuw',?)",
        [("top40", 1999, "a teens|mamma mia"),
         ("top40", 2000, "a teens|mamma mia"),
         ("tipparade", 2001, "a teens|mamma mia"),
         ("top40", 1975, "abba|waterloo")])
    return con


def test_markeren_vindt_alleen_de_geraakte_jaargangen():
    """Een artiest in drie jaargangen mag geen zeshonderd bestanden verdacht maken."""
    from hitlijsten import db as dbmod

    con = _schone_database()
    dbmod.markeer_te_bouwen(con, sleutels=["a teens|mamma mia"], reden="alias")
    assert sorted(dbmod.te_bouwen(con)) == [
        ("tipparade", 2001), ("top40", 1999), ("top40", 2000)]


def test_gebouwd_haalt_een_jaargang_van_de_lijst():
    from hitlijsten import db as dbmod

    con = _schone_database()
    dbmod.markeer_te_bouwen(con, sleutels=["a teens|mamma mia"])
    dbmod.gebouwd(con, "top40", 1999)
    assert ("top40", 1999) not in dbmod.te_bouwen(con)
    assert len(dbmod.te_bouwen(con)) == 2


def test_onbekende_sleutel_markeert_niets():
    from hitlijsten import db as dbmod

    con = _schone_database()
    assert dbmod.markeer_te_bouwen(con, sleutels=["bestaat|niet"]) == 0
    assert dbmod.te_bouwen(con) == []


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
            # Niet alleen AssertionError: een test die omvalt op een kapotte
            # opzet nam vroeger de rest van de reeks mee, en dan zie je geen
            # eindstand meer.
            mislukt += 1
            print(f"KAPOT    {test.__name__}: {type(fout).__name__}: {fout}")
    print(f"\n{len(tests) - mislukt}/{len(tests)} geslaagd")
    return 1 if mislukt else 0


if __name__ == "__main__":
    sys.exit(main())
