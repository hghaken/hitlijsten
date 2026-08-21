"""Zelftest voor de top40.nl-parser.

Draait volledig op de gecachete HTML in .cache\\ -- geen netwerk. Start met:

    C:\\Python313\\python.exe tests\\test_top40nl.py

Er is geen pytest nodig; het zijn gewone asserts. Exitcode 0 = alles goed.

De verwachte waarden hieronder zijn met de hand nagelopen tegen de echte
pagina's op top40.nl (zie het aria-label/alt-attribuut in de HTML).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Zorg dat het pakket gevonden wordt zonder installatie.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Niet elke console is UTF-8; zonder dit klapt een print met "Bløf" eruit.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):  # pragma: no cover
    pass

import veilig  # noqa: F401  -- moet vóór hitlijsten, zie veilig.py
from hitlijsten.config import LIJSTEN  # noqa: E402
from hitlijsten.fetch import cache_pad, in_cache  # noqa: E402
from hitlijsten.models import ParseFout, controleer_lijst  # noqa: E402
from hitlijsten.parsers import top40nl  # noqa: E402

JAAR = 2026
LIJSTNAMEN = ["top40", "tipparade", "sterrennl"]
WEKEN = [1, 12, 22, 29, 30]

# De Tipparade staat in config.py op lengte=None (variabel). In alle
# onderzochte weken is hij echter precies 30 lang; dat pinnen we hier vast,
# zodat we het merken als dat ooit verandert.
VERWACHTE_LENGTE = {"top40": 40, "tipparade": 30, "sterrennl": 25}

_fouten: list[str] = []
_gedaan = 0


def check(voorwaarde: bool, omschrijving: str) -> None:
    global _gedaan
    _gedaan += 1
    if not voorwaarde:
        _fouten.append(omschrijving)
        print(f"  FAAL: {omschrijving}")


def gelijk(gekregen, verwacht, omschrijving: str) -> None:
    check(
        gekregen == verwacht,
        f"{omschrijving}: verwacht {verwacht!r}, kreeg {gekregen!r}",
    )


def lees(lijst: str, week: int) -> str:
    return cache_pad(lijst, JAAR, week).read_text(encoding="utf-8")


def parse(lijst: str, week: int):
    return top40nl.parse(lees(lijst, week), lijst, JAAR, week)


def notering(noteringen, positie: int):
    for n in noteringen:
        if n.positie == positie:
            return n
    raise AssertionError(f"positie {positie} ontbreekt")


# --------------------------------------------------------------------------
def test_structuur_alle_weken() -> None:
    """Elke gecachete week is compleet en aaneengesloten genummerd."""
    print("\n[1] structuurcontrole per lijst/week")
    for lijst in LIJSTNAMEN:
        for week in WEKEN:
            if not in_cache(lijst, JAAR, week):
                print(f"  overslaan (niet in cache): {lijst} w{week}")
                continue
            noteringen = parse(lijst, week)
            resultaat = controleer_lijst(noteringen, VERWACHTE_LENGTE[lijst])
            check(
                resultaat.ok,
                f"{lijst} w{week}: {resultaat.meldingen}",
            )
            gelijk(len(noteringen), VERWACHTE_LENGTE[lijst], f"{lijst} w{week} lengte")
            for n in noteringen:
                gelijk(n.lijst, lijst, f"{lijst} w{week} pos{n.positie} lijst")
                gelijk(n.jaar, JAAR, f"{lijst} w{week} pos{n.positie} jaar")
                gelijk(n.week, week, f"{lijst} w{week} pos{n.positie} week")
                # top40.nl toont geen platenlabel.
                gelijk(n.label, None, f"{lijst} w{week} pos{n.positie} label")
                check(
                    n.weken_genoteerd is not None and n.weken_genoteerd >= 1,
                    f"{lijst} w{week} pos{n.positie}: weken_genoteerd ontbreekt",
                )
            print(f"  ok {lijst:10s} w{week:<2d} n={len(noteringen)}")


def test_concrete_waarden_top40_week1() -> None:
    """Top 40, week 1: regel voor regel tegen de pagina nagelopen."""
    print("\n[2] concrete waarden top40 week 1")
    n = parse("top40", 1)

    # nr 1: staat stil (rank-cel toont een enkel getal met 'underline')
    eerste = notering(n, 1)
    gelijk(eerste.titel, "The Fate Of Ophelia", "pos1 titel")
    gelijk(eerste.artiest, "Taylor Swift", "pos1 artiest")
    gelijk(eerste.weken_genoteerd, 13, "pos1 weken")
    gelijk(eerste.vorige_positie, 1, "pos1 vorige")
    gelijk(eerste.site_status, "gelijk", "pos1 status")

    # stijger: rank-cel "6 -> 5" met groen pijltje
    vijf = notering(n, 5)
    gelijk(vijf.titel, "12 To 12", "pos5 titel")
    gelijk(vijf.artiest, "Sombr", "pos5 artiest")
    gelijk(vijf.vorige_positie, 6, "pos5 vorige")
    gelijk(vijf.site_status, "stijger", "pos5 status")

    # daler: rank-cel "5 -> 6" met rood pijltje
    zes = notering(n, 6)
    gelijk(zes.titel, "Golden", "pos6 titel")
    gelijk(zes.artiest, "Huntr/x", "pos6 artiest")
    gelijk(zes.vorige_positie, 5, "pos6 vorige")
    gelijk(zes.site_status, "daler", "pos6 status")

    # binnenkomer: geen vorige positie, anders klaagt controleer_lijst()
    nieuw = notering(n, 37)
    gelijk(nieuw.titel, "Chanel", "pos37 titel")
    gelijk(nieuw.artiest, "Tyla", "pos37 artiest")
    gelijk(nieuw.site_status, "nieuw", "pos37 status")
    gelijk(nieuw.vorige_positie, None, "pos37 vorige")
    gelijk(nieuw.weken_genoteerd, 1, "pos37 weken")

    # &amp; moet ontdaan zijn tot een echte &
    gelijk(notering(n, 19).artiest, "Suzan & Freek", "pos19 artiest (&amp;)")
    # titel met haakjes blijft heel
    gelijk(notering(n, 12).titel, "So Easy (To Fall In Love)", "pos12 titel (haakjes)")
    gelijk(notering(n, 20).titel, "Stay (If You Wanna Dance)", "pos20 titel (haakjes)")
    # 'ft.' hoort bij de artiest, niet bij de titel
    gelijk(notering(n, 15).artiest, "Haven. ft. Kaitlin Aragon", "pos15 artiest (ft.)")
    gelijk(notering(n, 15).titel, "I Run", "pos15 titel (ft.)")
    gelijk(
        notering(n, 31).artiest,
        "Damiano David feat. Tyla & Nile Rodgers",
        "pos31 artiest (feat. + &)",
    )


def test_concrete_waarden_sterrennl_week12() -> None:
    """Sterren NL Top 25, week 12: tweede week, regel voor regel."""
    print("\n[3] concrete waarden sterrennl week 12")
    n = parse("sterrennl", 12)

    een = notering(n, 1)
    gelijk(een.titel, "Uitslover", "pos1 titel")
    gelijk(een.artiest, "Samuel Welten & Bankzitters", "pos1 artiest")
    gelijk(een.vorige_positie, 8, "pos1 vorige")
    gelijk(een.site_status, "stijger", "pos1 status")
    gelijk(een.weken_genoteerd, 3, "pos1 weken")

    twee = notering(n, 2)
    # Diakriet moet ongeschonden door de utf-8-cache komen.
    gelijk(twee.titel, "Mo\u00ebt Dat Nou", "pos2 titel (trema)")
    gelijk(twee.artiest, "Robert Van Hemert & Donnie", "pos2 artiest")
    gelijk(twee.vorige_positie, 1, "pos2 vorige")
    gelijk(twee.site_status, "daler", "pos2 status")

    drie = notering(n, 3)
    gelijk(drie.titel, "Al Heb Je Niets", "pos3 titel")
    gelijk(drie.artiest, "Ammar", "pos3 artiest")
    gelijk(drie.vorige_positie, 3, "pos3 vorige")
    gelijk(drie.site_status, "gelijk", "pos3 status")

    vier = notering(n, 4)
    gelijk(vier.titel, "Meisje", "pos4 titel")
    # De site kapt deze naam zichtbaar af op "... Jeffrey Hees.."; de parser
    # hoort hem uit het aria-label te herstellen.
    gelijk(
        vier.artiest,
        "Afro Bros x Billy Dans x Brace x Jeffrey Heesen",
        "pos4 artiest (afkapping hersteld)",
    )

    vijf = notering(n, 5)
    gelijk(vijf.titel, "Droom Jij Over Mij Vannacht", "pos5 titel")
    gelijk(vijf.artiest, "Yves Berendse", "pos5 artiest")
    gelijk(vijf.vorige_positie, 4, "pos5 vorige")


def test_afkapping_hersteld() -> None:
    """Geen enkel veld mag nog op '..' eindigen."""
    print("\n[4] afgekapte namen hersteld")
    aantal = 0
    for lijst in LIJSTNAMEN:
        for week in WEKEN:
            if not in_cache(lijst, JAAR, week):
                continue
            for n in parse(lijst, week):
                check(
                    not n.artiest.endswith(".."),
                    f"{lijst} w{week} pos{n.positie}: artiest nog afgekapt ({n.artiest!r})",
                )
                check(
                    not n.titel.endswith(".."),
                    f"{lijst} w{week} pos{n.positie}: titel nog afgekapt ({n.titel!r})",
                )
                aantal += 1
    print(f"  {aantal} regels gecontroleerd")


def test_uitgevallen_nummers_overgeslagen() -> None:
    """De 'no-longer-listed'-regels onder de lijst horen er niet bij."""
    print("\n[5] uitgevallen nummers overgeslagen")
    # top40 week 1 heeft 42 .top40-list__item's, waarvan 2 uitgevallen.
    n = parse("top40", 1)
    gelijk(len(n), 40, "top40 w1 na filteren")
    check(
        all(x.titel != "Glas" for x in n),
        "uitgevallen nummer 'Glas' (Bl\u00f8f & Racoon) zit ten onrechte in de lijst",
    )
    # tipparade week 12: 37 items, waarvan 7 uitgevallen.
    gelijk(len(parse("tipparade", 12)), 30, "tipparade w12 na filteren")


def test_vorige_positie_tegen_vorige_week() -> None:
    """Onafhankelijke controle: vorige_positie in w30 == positie in w29."""
    print("\n[6] vorige_positie kruiscontrole w29 -> w30")
    for lijst in LIJSTNAMEN:
        if not (in_cache(lijst, JAAR, 29) and in_cache(lijst, JAAR, 30)):
            print(f"  overslaan: {lijst}")
            continue
        vorig = {(n.titel, n.artiest): n.positie for n in parse(lijst, 29)}
        raak = 0
        for n in parse(lijst, 30):
            if n.vorige_positie is None:
                # Binnenkomer: mag juist NIET in week 29 gestaan hebben.
                check(
                    (n.titel, n.artiest) not in vorig,
                    f"{lijst} w30 pos{n.positie}: 'nieuw' maar stond in w29",
                )
                continue
            sleutel = (n.titel, n.artiest)
            check(sleutel in vorig, f"{lijst} w30 pos{n.positie}: niet gevonden in w29")
            if sleutel in vorig:
                gelijk(
                    n.vorige_positie,
                    vorig[sleutel],
                    f"{lijst} w30 pos{n.positie} vorige_positie",
                )
                raak += 1
        print(f"  ok {lijst:10s} {raak} vorige posities kloppen met week 29")


def test_status_consistentie() -> None:
    """site_status mag nooit met vorige_positie in tegenspraak zijn."""
    print("\n[7] status-consistentie")
    for lijst in LIJSTNAMEN:
        for week in WEKEN:
            if not in_cache(lijst, JAAR, week):
                continue
            for n in parse(lijst, week):
                waar = f"{lijst} w{week} pos{n.positie}"
                if n.site_status == "nieuw":
                    gelijk(n.vorige_positie, None, f"{waar}: nieuw zonder vorige")
                elif n.site_status == "stijger":
                    check(
                        n.vorige_positie is not None and n.vorige_positie > n.positie,
                        f"{waar}: stijger maar vorige={n.vorige_positie}",
                    )
                elif n.site_status == "daler":
                    check(
                        n.vorige_positie is not None and n.vorige_positie < n.positie,
                        f"{waar}: daler maar vorige={n.vorige_positie}",
                    )
                elif n.site_status == "gelijk":
                    gelijk(n.vorige_positie, n.positie, f"{waar}: gelijk")
                else:
                    _fouten.append(f"{waar}: onverwachte status {n.site_status!r}")
    print("  ok")


def test_parsefout_bij_rommel() -> None:
    """Liever hard falen dan stil een lege lijst opleveren."""
    print("\n[8] ParseFout bij onbruikbare HTML")
    for omschrijving, html in [
        ("lege string", ""),
        ("pagina zonder lijst", "<html><body><h1>Onderhoud</h1></body></html>"),
        ("container zonder regels", "<div class='list__list'></div>"),
        (
            "alleen uitgevallen nummers",
            "<div class='list__list'><div class='top40-list__item "
            "no-longer-listed'></div></div>",
        ),
    ]:
        try:
            top40nl.parse(html, "top40", JAAR, 1)
        except ParseFout:
            print(f"  ok ParseFout bij {omschrijving}")
        except Exception as exc:  # noqa: BLE001
            _fouten.append(f"{omschrijving}: {type(exc).__name__} i.p.v. ParseFout")
            print(f"  FAAL: {omschrijving} gaf {type(exc).__name__}: {exc}")
        else:
            _fouten.append(f"{omschrijving}: geen ParseFout")
            print(f"  FAAL: {omschrijving} leverde stilzwijgend een lijst op")


def test_config_aansluiting() -> None:
    """De parser hoort de drie top40.nl-lijsten uit config.py te bedienen."""
    print("\n[9] aansluiting op config.LIJSTEN")
    top40nl_lijsten = [k for k, v in LIJSTEN.items() if v["site"] == "top40nl"]
    gelijk(sorted(top40nl_lijsten), sorted(LIJSTNAMEN), "lijsten met site=top40nl")
    for lijst in LIJSTNAMEN:
        check(
            LIJSTEN[lijst]["heeft_label"] is False,
            f"{lijst}: heeft_label zou False moeten zijn",
        )


def main() -> int:
    ontbreekt = [
        f"{l} w{w}"
        for l in LIJSTNAMEN
        for w in WEKEN
        if not in_cache(l, JAAR, w)
    ]
    if len(ontbreekt) == len(LIJSTNAMEN) * len(WEKEN):
        print("GEEN gecachete pagina's gevonden in .cache\\ -- test kan niets doen.")
        return 1
    if ontbreekt:
        print(f"Let op, niet in cache (worden overgeslagen): {ontbreekt}")

    for functie in [
        test_structuur_alle_weken,
        test_concrete_waarden_top40_week1,
        test_concrete_waarden_sterrennl_week12,
        test_afkapping_hersteld,
        test_uitgevallen_nummers_overgeslagen,
        test_vorige_positie_tegen_vorige_week,
        test_status_consistentie,
        test_parsefout_bij_rommel,
        test_config_aansluiting,
    ]:
        functie()

    print("\n" + "=" * 60)
    if _fouten:
        print(f"MISLUKT: {len(_fouten)} van de {_gedaan} controles faalden")
        for f in _fouten[:40]:
            print(f"  - {f}")
        return 1
    print(f"GESLAAGD: alle {_gedaan} controles ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
