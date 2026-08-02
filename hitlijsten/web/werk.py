"""Wat de knoppen op de beheerpagina doen, als achtergrondwerk.

Elke functie krijgt de taak mee en meldt daarin zijn voortgang, zodat de pagina
kan laten zien waar hij is. De opdrachtregelversies schrijven naar het
logbestand; hier gaat het naar het scherm.
"""
from __future__ import annotations

import io
import re
from contextlib import redirect_stdout
from typing import Callable, Optional

from .taken import Taak

_STEMPEL = re.compile(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\s*")


def _met_uitvoer(taak: Taak, functie, *args, **kwargs):
    """Draai iets en zet wat het print door naar de voortgangsmelding."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        resultaat = functie(*args, **kwargs)
    for regel in buffer.getvalue().splitlines():
        # De opdrachtregelversie zet er zelf al een tijdstempel voor, en `meld`
        # doet dat nog eens: "[17:14:16] [2026-08-02 17:14:16] ...". Eentje is
        # genoeg.
        regel = _STEMPEL.sub("", regel.strip())
        if regel:
            taak.meld(regel)
    return resultaat


def bouw_werk(wat: str, jaar: str | None,
              bestand: str | None = None
              ) -> tuple[str, Optional[Callable[[Taak], None]]]:
    """Vertaal een knop naar (naam, werkfunctie). Werkfunctie None = foutmelding."""
    from .. import cli

    jaartal: Optional[int] = None
    if jaar and jaar != "alle":
        try:
            jaartal = int(jaar)
        except ValueError:
            return "Ongeldig jaar", None

    if wat == "excel":
        if jaartal:
            def werk(taak: Taak) -> None:
                taak.meld(f"Excel bouwen voor {jaartal}")
                paden = _met_uitvoer(taak, cli.opdracht_excel, jaartal)
                taak.meld(f"klaar: {len(paden)} bestanden")
            return f"Excel bouwen {jaartal}", werk

        def werk(taak: Taak) -> None:
            jaren = cli._jaren_in_database()
            taak.meld(f"Excel bouwen voor {len(jaren)} jaargangen")
            totaal = 0
            for j in jaren:
                paden = _met_uitvoer(taak, cli.opdracht_excel, j)
                totaal += len(paden)
                taak.meld(f"{j}: {len(paden)} bestanden")
            taak.meld(f"klaar: {totaal} bestanden")
        return "Excel bouwen (alles)", werk

    if wat == "bijwerken":
        def werk(taak: Taak) -> None:
            taak.meld("ontbrekende weken ophalen")
            nieuw, mislukt = cli.opdracht_bijwerken(None)
            for (lijst, j), weken in sorted(nieuw.items()):
                taak.meld(f"{lijst} {j}: week {', '.join(map(str, weken))}")
            if not nieuw:
                taak.meld("niets nieuws")
            for m in mislukt:
                taak.meld(f"MISLUKT: {m}")
        return "Ontbrekende weken ophalen", werk

    if wat == "hersleutel":
        def werk(taak: Taak) -> None:
            from ..normalize import vergeet_aliases

            vergeet_aliases()
            jaren = [jaartal] if jaartal else cli._jaren_in_database()
            taak.meld(f"sleutels herberekenen voor {len(jaren)} jaargangen")
            for j in jaren:
                _met_uitvoer(taak, cli.opdracht_hersleutel, j)
            taak.meld("klaar -- bouw daarna de Excel-bestanden opnieuw")
        return "Sleutels herberekenen", werk

    if wat == "controle":
        def werk(taak: Taak) -> None:
            taak.meld("dubbelingencontrole over alle jaargangen")
            _met_uitvoer(taak, cli.opdracht_controle, None, alle_jaren=True)
        return "Dubbelingencontrole", werk

    if wat == "kruiscontrole":
        def werk(taak: Taak) -> None:
            taak.meld("vergelijken met michajans.nl")
            if jaartal:
                _met_uitvoer(taak, cli.opdracht_kruiscontrole, jaartal)
            else:
                _met_uitvoer(taak, cli.opdracht_kruiscontrole, None, alle_jaren=True)
        return "Kruiscontrole michajans.nl", werk

    if wat == "bijwerken-wijziging":
        # Wat "Alles bijwerken" doet, maar dan alleen voor de jaargangen die
        # daadwerkelijk zijn aangeraakt. Een alias voor een artiest die in drie
        # jaargangen staat kost zo tien seconden in plaats van een half uur.
        def werk(taak: Taak) -> None:
            from .. import db
            from ..normalize import vergeet_aliases

            vergeet_aliases()
            taak.fase(1, 3, "sleutels herberekenen")
            with db.verbinding() as con:
                jaren = [r[0] for r in con.execute(
                    "SELECT DISTINCT jaar FROM noteringen ORDER BY jaar")]
            for nr, j in enumerate(jaren, 1):
                taak.tel(nr, len(jaren))
                _met_uitvoer(taak, cli.opdracht_hersleutel, j)

            taak.fase(2, 3, "opschonen en toepassen")
            _met_uitvoer(taak, cli.opdracht_opschonen, toepassen=True)

            with db.verbinding() as con:
                open_staand = db.te_bouwen(con)
            if not open_staand:
                taak.fase(3, 3, "niets aangeraakt, er valt niets te bouwen")
                return

            per_jaar = sorted({j for _, j in open_staand})
            taak.fase(3, 3, f"bouwen: {len(per_jaar)} jaargangen")
            for nr, j in enumerate(per_jaar, 1):
                taak.tel(nr, len(per_jaar))
                _met_uitvoer(taak, cli.opdracht_excel, j)
                _met_uitvoer(taak, cli.opdracht_pdf, j, altijd=True)
                # Per jaargang afvinken en niet aan het eind in een keer.
                # Anders blijft de teller op de beginstand staan en weet je
                # halverwege niet hoever hij is -- en bij een afgebroken taak
                # zou al het gedane werk opnieuw moeten.
                with db.verbinding() as con:
                    for lijst_naam, jaargang in open_staand:
                        if jaargang == j:
                            db.gebouwd(con, lijst_naam, jaargang)
                    con.commit()
            _met_uitvoer(taak, cli.opdracht_decennium, None)
            taak.meld("klaar -- alleen wat nodig was")
        return "Bijwerken wat veranderd is", werk

    if wat == "versies":
        def werk(taak: Taak) -> None:
            from .. import db, momentopnames
            from ..opschonen import splits_versies, versies_op_een_plek

            doel = jaar if jaar and jaar != "alle" else "top40"
            with db.verbinding() as con:
                gevallen = versies_op_een_plek(con, doel)
            if not gevallen:
                taak.meld(f"{doel}: geen gedeelde plekken met twee versies")
                return
            taak.meld(f"{doel}: {len(gevallen)} noteringen waarin artiesten een "
                      f"plek delen")
            taak.meld(f"momentopname vooraf: "
                      f"{momentopnames.maak('voor-versies').name}")
            with db.verbinding() as con:
                verslag = splits_versies(con, doel)
            taak.meld(f"{verslag['nieuw']} noteringen erbij over "
                      f"{verslag['nummers']} nummers")
            taak.meld("druk hierna op 'Bijwerken wat veranderd is'")
        return "Versies op één plek splitsen", werk

    if wat == "volledig":
        # Na een wijziging in de aliassen moet er altijd hetzelfde rijtje
        # gebeuren, in deze volgorde: eerst de sleutels (die laten de alias
        # gelden), dan de namen (die kiezen de juiste schrijfwijze), en pas
        # daarna de bestanden -- die horen bij de toestand van dat moment.
        # Als knop, want er draait er maar een tegelijk: vijf knoppen achter
        # elkaar indrukken gaat niet, de tweede wordt geweigerd.
        def werk(taak: Taak) -> None:
            from ..normalize import vergeet_aliases

            vergeet_aliases()
            jaren = cli._jaren_in_database()

            taak.fase(1, 5, "sleutels herberekenen")
            for nr, j in enumerate(jaren, 1):
                taak.tel(nr, len(jaren))
                _met_uitvoer(taak, cli.opdracht_hersleutel, j)

            taak.fase(2, 5, "opschonen en toepassen")
            _met_uitvoer(taak, cli.opdracht_opschonen, toepassen=True)

            taak.fase(3, 5, "Excel bouwen")
            totaal = 0
            for nr, j in enumerate(jaren, 1):
                taak.tel(nr, len(jaren))
                totaal += len(_met_uitvoer(taak, cli.opdracht_excel, j))
            taak.meld(f"{totaal} Excel-bestanden")

            taak.fase(4, 5, "decenniumlijsten")
            _met_uitvoer(taak, cli.opdracht_decennium, None)

            taak.fase(5, 5, "PDF-jaaroverzichten")
            paden = _met_uitvoer(taak, cli.opdracht_pdf, None, altijd=True)
            taak.meld(f"{len(paden)} PDF-bestanden")
            taak.meld("klaar -- alles staat weer gelijk")
        return "Alles bijwerken", werk

    if wat == "pdf":
        def werk(taak: Taak) -> None:
            taak.meld("PDF-jaaroverzichten bouwen"
                      + (f" voor {jaartal}" if jaartal else " voor alle jaargangen"))
            paden = _met_uitvoer(taak, cli.opdracht_pdf, jaartal, altijd=True)
            taak.meld(f"klaar: {len(paden)} bestanden")
        return f"PDF bouwen {jaartal or '(alles)'}", werk

    if wat == "decennium":
        def werk(taak: Taak) -> None:
            taak.meld("decenniumklassementen bouwen")
            paden = _met_uitvoer(taak, cli.opdracht_decennium, None)
            taak.meld(f"klaar: {len(paden)} bestanden")
        return "Decenniumlijsten bouwen", werk

    if wat in ("opschonen", "opschonen-toepassen"):
        toepassen = wat.endswith("toepassen")

        def werk(taak: Taak) -> None:
            taak.meld("opschonen" + (" en toepassen" if toepassen
                                     else " -- alleen nakijken"))
            _met_uitvoer(taak, cli.opdracht_opschonen, toepassen=toepassen)
            taak.meld("bouw hierna Excel en PDF opnieuw" if toepassen else
                      "er is niets gewijzigd -- gebruik de knop 'Opschonen en "
                      "toepassen' om het door te voeren")
        return ("Opschonen en toepassen" if toepassen else "Opschonen nakijken"), werk

    if wat == "momentopname":
        def werk(taak: Taak) -> None:
            from .. import momentopnames

            taak.meld("kopie van de database maken")
            pad = momentopnames.maak("via het beheerscherm")
            taak.meld(f"{pad.name} ({pad.stat().st_size / 1024 / 1024:.0f} MB)")
            weg = momentopnames.opruimen()
            if weg:
                taak.meld(f"{len(weg)} oude opgeruimd volgens het bewaarbeleid")
        return "Momentopname maken", werk

    if wat == "terugzetten":
        # Het gevaarlijkste knopje van de pagina: hier verdwijnt alles wat er na
        # die momentopname is gebeurd. De naam moet daarom echt meegestuurd
        # worden -- er is met opzet geen "de nieuwste" of een lege standaard.
        if not bestand:
            return "Kies eerst een momentopname", None

        def werk(taak: Taak) -> None:
            from .. import momentopnames

            taak.meld(f"terugzetten naar {bestand}")
            veiligheid = momentopnames.terugzetten(bestand)
            taak.meld(f"gelukt -- de database van zojuist staat als {veiligheid.name}")
            taak.meld("bouw hierna Excel en PDF opnieuw: die horen bij de oude toestand")
        return f"Terugzetten naar {bestand}", werk

    if wat == "onderscheidingen":
        def werk(taak: Taak) -> None:
            taak.meld("Alarmschijven en Dancesmashes ophalen")
            _met_uitvoer(taak, cli.opdracht_onderscheidingen)
        return "Onderscheidingen ophalen", werk

    return f"Onbekende opdracht: {wat}", None
