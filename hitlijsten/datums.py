"""Van weeknummer naar de vrijdag waarop de lijst werd uitgezonden.

DE REGEL
--------
Week N van jaar J is de **N-de zaterdag van dat jaar**; dat is de datum waaronder
de lijst gepubliceerd wordt. De uitzending was de vrijdag ervoor.

Die regel is niet bedacht maar gemeten. Micha Jans vermeldt bij elk nummer de
datum van binnenkomst; door die te koppelen aan de week waarin het bij ons voor
het eerst noteerde ontstonden 3798 koppels van (jaar, week) en datum, verspreid
over vijftien jaargangen tussen 1965 en 2025. Daarvan volgt 99,9% deze regel.
De twee afwijkers zijn foute naamkoppelingen, geen kalenderafwijkingen.

WAAROM NIET DE ISO-WEEK
-----------------------
Voor de hand liggend, maar fout: op dezelfde 3798 koppels klopt de ISO-week
maar in 65% van de gevallen. In 1965 loopt de nummering een week voor op ISO
(week 8 is daar ISO-week 7), en rond elke jaarwisseling schuift het.

DE JAARGRENS
------------
Begint een jaar op zaterdag, dan is de vrijdag van week 1 de 31e december van
het jaar ervoor. Dat is geen fout maar de echte uitzenddatum. Het gebeurt in
negen jaargangen: 1966, 1972, 1977, 1983, 1994, 2000, 2005, 2011 en 2022.
"""
from __future__ import annotations

from datetime import date, timedelta

ZATERDAG = 5   # date.weekday(): maandag = 0


def eerste_zaterdag(jaar: int) -> date:
    eerste = date(jaar, 1, 1)
    return eerste + timedelta(days=(ZATERDAG - eerste.weekday()) % 7)


def zaterdag_van(jaar: int, week: int) -> date:
    """De publicatiedatum van week N: de N-de zaterdag van dat jaar."""
    return eerste_zaterdag(jaar) + timedelta(weeks=week - 1)


def vrijdag_van(jaar: int, week: int) -> date:
    """De uitzenddatum van week N: de vrijdag voor de publicatiezaterdag."""
    return zaterdag_van(jaar, week) - timedelta(days=1)


def als_tekst(datum: date | None) -> str:
    return datum.strftime("%d/%m/%Y") if datum else ""


def vrijdag_tekst(jaar: int, week: int) -> str:
    return als_tekst(vrijdag_van(jaar, week))
