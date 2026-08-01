"""HTML -> lijst van Notering, per bronsite.

Elke parser biedt:

    parse(html: str, lijst: str, jaar: int, week: int) -> list[Notering]

en gooit models.ParseFout als de HTML er niet uitziet zoals verwacht.
"""
from __future__ import annotations

from ..config import LIJSTEN
from ..models import Notering


def parse(html: str, lijst: str, jaar: int, week: int) -> list[Notering]:
    """Kies de juiste parser op basis van de bronsite van de lijst."""
    site = LIJSTEN[lijst]["site"]
    if site == "top40nl":
        from . import top40nl

        return top40nl.parse(html, lijst, jaar, week)
    if site == "oranjetop30":
        from . import oranje

        return oranje.parse(html, lijst, jaar, week)
    raise ValueError(f"geen parser voor site {site!r}")
