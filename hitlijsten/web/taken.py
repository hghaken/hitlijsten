"""Langlopend werk, met voortgang die iedereen kan opvragen.

Ophalen en Excel bouwen duren minuten. Die in een verzoek afhandelen betekent
een browser die staat te wachten en, erger, een verbinding die halverwege
afbreekt terwijl het werk doorloopt. Daarom draait zulk werk in een aparte draad
en vraagt de pagina de stand op.

WAAROM DE STAND IN DE DATABASE STAAT EN NIET IN HET GEHEUGEN
------------------------------------------------------------
Hij stond eerst in een variabele van de webapplicatie, en dat gaf twee keer een
verkeerd beeld:

* **Na een herstart was de voortgang weg.** Precies wanneer je hem nodig hebt --
  er was net iets misgegaan -- staat er "niets aan de gang".
* **Werk buiten de webapplicatie was onzichtbaar.** Draait er een opdracht op de
  opdrachtregel, dan bouwt die een half uur lang bestanden terwijl de pagina
  volhoudt dat er niets gebeurt.

Nu staat de stand in de tabel `taak` (één rij) en schrijft ook `cli.log()` erin.
Elk proces ziet dus hetzelfde. Of een taak nog echt leeft blijkt uit het
procesnummer: staat de rij op "bezig" terwijl dat proces niet meer bestaat, dan
is hij ergens onderweg omgevallen -- door een herstart bijvoorbeeld -- en dat
zeggen is eerlijker dan eeuwig "bezig" blijven tonen.

Er draait er bewust maar een tegelijk: twee ophaalrondes tegelijk zouden
dezelfde weken dubbel halen, en twee Excel-bouwen tegelijk vechten om dezelfde
bestanden.
"""
from __future__ import annotations

import os
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

REGELS_BEWAARD = 300


@dataclass
class Taak:
    """Een lopende taak. Elke melding gaat meteen naar de database."""

    naam: str
    gestart: str
    regels: list[str] = field(default_factory=list)
    klaar: bool = False
    gelukt: Optional[bool] = None
    fout: Optional[str] = None
    # Waar hij is. Zonder deze velden kan de pagina alleen tekst laten zien, en
    # bij een half uur bouwen wil je een balk zien lopen.
    stap: int = 0
    stappen: int = 0
    stap_naam: str = ""
    deel: int = 0
    deel_van: int = 0

    def fase(self, nummer: int, van: int, naam: str) -> None:
        """Begin aan stap `nummer` van `van`. Zet de deelteller terug op nul."""
        self.stap, self.stappen, self.stap_naam = nummer, van, naam
        self.deel = self.deel_van = 0
        self.meld(f"stap {nummer}/{van}: {naam}")

    def tel(self, gedaan: int, van: int) -> None:
        """Hoe ver binnen deze stap. Schrijft alleen weg als er iets verandert."""
        if (gedaan, van) == (self.deel, self.deel_van):
            return
        self.deel, self.deel_van = gedaan, van
        bewaar(self)

    def meld(self, regel: str) -> None:
        stempel = datetime.now().strftime("%H:%M:%S")
        self.regels.append(f"[{stempel}] {regel}")
        # Niet onbeperkt laten groeien: een backfill van een decennium levert
        # honderden regels op en de pagina hoeft alleen het recente deel.
        if len(self.regels) > REGELS_BEWAARD + 100:
            del self.regels[:-REGELS_BEWAARD]
        bewaar(self)


def _leeft(proces: Optional[int]) -> bool:
    """Bestaat dat procesnummer nog?"""
    if not proces:
        return False
    try:
        os.kill(proces, 0)
    except OSError:
        return False
    return True


def bewaar(taak: Taak) -> None:
    """Schrijf de stand weg. Een fout hierin mag het werk nooit stoppen."""
    from .. import db

    try:
        with db.verbinding() as con:
            con.execute(
                "INSERT OR REPLACE INTO taak (id, naam, gestart, bijgewerkt,"
                " proces, klaar, gelukt, fout, regels, stap, stappen,"
                " stap_naam, deel, deel_van)"
                " VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (taak.naam, taak.gestart,
                 datetime.now().isoformat(timespec="seconds"), os.getpid(),
                 int(taak.klaar),
                 None if taak.gelukt is None else int(taak.gelukt),
                 taak.fout, "\n".join(taak.regels[-REGELS_BEWAARD:]),
                 taak.stap, taak.stappen, taak.stap_naam,
                 taak.deel, taak.deel_van))
    except Exception:
        pass


def huidige() -> Optional[Taak]:
    """De laatst bekende stand, van welk proces hij ook komt."""
    from .. import db

    try:
        with db.verbinding() as con:
            rij = con.execute(
                "SELECT naam, gestart, klaar, gelukt, fout, regels, proces,"
                " stap, stappen, stap_naam, deel, deel_van, bijgewerkt"
                " FROM taak WHERE id=1").fetchone()
    except Exception:
        return None
    if not rij:
        return None

    klaar = bool(rij["klaar"])
    # Staat hij op "bezig" terwijl het proces weg is, dan is hij afgebroken.
    afgebroken = not klaar and not _leeft(rij["proces"])
    # Een taak die voorbij is blijft nog even zichtbaar -- je wilt de uitkomst
    # kunnen lezen -- maar niet eeuwig. Zonder deze grens bleef een afgebroken
    # taak van uren geleden als MISLUKT op de pagina staan, herstart na
    # herstart, tot er toevallig een nieuwe taak overheen kwam.
    if klaar or afgebroken:
        try:
            oud = (datetime.now()
                   - datetime.fromisoformat(rij["bijgewerkt"])).total_seconds()
        except (TypeError, ValueError):
            oud = 0
        if oud > 15 * 60:
            return None
    taak = Taak(naam=rij["naam"], gestart=rij["gestart"],
                regels=(rij["regels"] or "").splitlines(),
                klaar=klaar or afgebroken,
                gelukt=None if rij["gelukt"] is None else bool(rij["gelukt"]),
                fout=rij["fout"],
                stap=rij["stap"] or 0, stappen=rij["stappen"] or 0,
                stap_naam=rij["stap_naam"] or "",
                deel=rij["deel"] or 0, deel_van=rij["deel_van"] or 0)
    if afgebroken:
        taak.gelukt = False
        taak.fout = (taak.fout or "") + (
            "\n\nHet proces bestaat niet meer. Waarschijnlijk is de dienst "
            "herstart terwijl deze taak liep.")
    return taak


_slot = threading.Lock()


def bezig() -> bool:
    taak = huidige()
    return taak is not None and not taak.klaar


def start(naam: str, werk: Callable[[Taak], None]) -> tuple[bool, str]:
    """Start werk in de achtergrond. Geeft (gestart, melding)."""
    with _slot:
        lopend = huidige()
        if lopend is not None and not lopend.klaar:
            return False, f"Er loopt al iets: {lopend.naam}"
        taak = Taak(naam=naam,
                    gestart=datetime.now().strftime("%d-%m-%Y %H:%M:%S"))
        bewaar(taak)

    def draaier() -> None:
        try:
            werk(taak)
            taak.gelukt = True
        except Exception:
            taak.gelukt = False
            taak.fout = traceback.format_exc()
            taak.meld("MISLUKT -- zie de foutmelding onderaan")
        finally:
            taak.klaar = True
            bewaar(taak)

    threading.Thread(target=draaier, name=f"taak:{naam}", daemon=True).start()
    return True, f"'{naam}' gestart"
