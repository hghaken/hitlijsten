"""Wat de knoppen op de beheerpagina doen, als achtergrondwerk.

Elke functie krijgt de taak mee en meldt daarin zijn voortgang, zodat de pagina
kan laten zien waar hij is. De opdrachtregelversies schrijven naar het
logbestand; hier gaat het naar het scherm.
"""
from __future__ import annotations

import io
from contextlib import redirect_stdout
from typing import Callable, Optional

from .taken import Taak


def _met_uitvoer(taak: Taak, functie, *args, **kwargs):
    """Draai iets en zet wat het print door naar de voortgangsmelding."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        resultaat = functie(*args, **kwargs)
    for regel in buffer.getvalue().splitlines():
        if regel.strip():
            taak.meld(regel.strip())
    return resultaat


def bouw_werk(wat: str, jaar: str | None) -> tuple[str, Optional[Callable[[Taak], None]]]:
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

    if wat == "onderscheidingen":
        def werk(taak: Taak) -> None:
            taak.meld("Alarmschijven en Dancesmashes ophalen")
            _met_uitvoer(taak, cli.opdracht_onderscheidingen)
        return "Onderscheidingen ophalen", werk

    return f"Onbekende opdracht: {wat}", None
