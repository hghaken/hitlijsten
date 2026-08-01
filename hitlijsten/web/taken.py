"""Langlopend werk in de achtergrond, met voortgang die de browser kan opvragen.

Ophalen en Excel bouwen duren minuten. Die in een verzoek afhandelen betekent
een browser die staat te wachten en, erger, een verbinding die halverwege
afbreekt terwijl het werk doorloopt. Daarom draait zulk werk in een aparte draad
en vraagt de pagina de stand op.

Er draait er bewust maar een tegelijk: twee ophaalrondes tegelijk zouden
dezelfde weken dubbel halen, en twee Excel-bouwen tegelijk vechten om dezelfde
bestanden.
"""
from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional


@dataclass
class Taak:
    naam: str
    gestart: str
    regels: list[str] = field(default_factory=list)
    klaar: bool = False
    gelukt: Optional[bool] = None
    fout: Optional[str] = None

    def meld(self, regel: str) -> None:
        stempel = datetime.now().strftime("%H:%M:%S")
        self.regels.append(f"[{stempel}] {regel}")
        # Niet onbeperkt laten groeien: een backfill van een decennium levert
        # honderden regels op en de pagina hoeft alleen het recente deel.
        if len(self.regels) > 400:
            del self.regels[:-300]


_slot = threading.Lock()
_huidige: Optional[Taak] = None


def huidige() -> Optional[Taak]:
    return _huidige


def bezig() -> bool:
    return _huidige is not None and not _huidige.klaar


def start(naam: str, werk: Callable[[Taak], None]) -> tuple[bool, str]:
    """Start werk in de achtergrond. Geeft (gestart, melding)."""
    global _huidige
    with _slot:
        if bezig():
            return False, f"Er loopt al iets: {_huidige.naam}"
        taak = Taak(naam=naam, gestart=datetime.now().strftime("%d-%m-%Y %H:%M:%S"))
        _huidige = taak

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

    threading.Thread(target=draaier, name=f"taak:{naam}", daemon=True).start()
    return True, f"'{naam}' gestart"
