"""De Top 2000 inlezen uit de CSV van Music Datastats.

DE VREEMDE EEND IN DE BIJT
--------------------------
De andere vier lijsten komen wekelijks van een website. De Top 2000 is een
jaarlijkse uitzending tussen kerst en oud en nieuw, met tweeduizend noteringen
in een keer, en wij krijgen hem als een kant-en-klare matrix: een regel per
nummer, een kolom per editie, in de cel de positie (0 = dat jaar niet genoteerd).

Dat past met een kleine kunstgreep in hetzelfde schema: elke editie wordt
weggeschreven als jaargang met `week = 52`, de week waarin de uitzending valt.
Zo werken de jaaroverzichten, de sleutels en de Excel-bouwer zonder uitzondering
mee. Wat er NIET in past is de weekmatrix -- binnen een jaargang is er maar een
meting. Voor deze lijst is de zinvolle matrix nummer x editie, en die staat al
in de bron.

DE SLEUTEL IS DE BRUG
---------------------
De artiest en titel gaan door dezelfde `sleutel_van()` als de andere lijsten.
Daardoor krijgt "Golden Earring - Radar Love" in de Top 2000 exact dezelfde
sleutel als in de Top 40, en zie je in een oogopslag welke nummers in allebei
staan. Van de 4927 nummers in de editie van 2025 delen er 3043 een sleutel met
onze bestaande lijsten; de rest zijn vooral albumnummers die nooit als single
noteerden.
"""
from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Optional

from .config import LIJSTEN
from .normalize import sleutel_van

__all__ = ["Regel", "lees_csv", "importeer", "kruisverwijzing"]

LIJST = "top2000"
# Music Datastats levert windows-1252; UTF-8 wordt eerst geprobeerd omdat een
# latere versie dat best kan gaan doen.
CODERINGEN = ("utf-8-sig", "windows-1252")
SCHEIDING = ";"


@dataclass
class Regel:
    """Een nummer met zijn positie in elke editie waarin het stond."""

    artiest: str
    titel: str
    uitjaar: Optional[int]
    # editiejaar -> positie
    posities: dict[int, int] = field(default_factory=dict)

    @property
    def sleutel(self) -> str:
        return sleutel_van(self.artiest, self.titel)


def _lees_tekst(pad: Path) -> str:
    rauw = pad.read_bytes()
    for codering in CODERINGEN:
        try:
            return rauw.decode(codering)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"{pad.name}: geen bekende codering (geprobeerd: "
                     f"{', '.join(CODERINGEN)})")


def lees_csv(pad: Path | str) -> tuple[list[int], list[Regel]]:
    """Lees de matrix. Geeft de editiejaren en een regel per nummer terug.

    De structuurcontrole is streng met opzet: als de bron ooit van vorm
    verandert wil je dat weten voordat er halve data in de database staat.
    """
    pad = Path(pad)
    rijen = list(csv.reader(_lees_tekst(pad).splitlines(), delimiter=SCHEIDING))
    if not rijen:
        raise ValueError(f"{pad.name} is leeg")

    kop, rijen = rijen[0], [r for r in rijen[1:] if any(v.strip() for v in r)]
    verwacht = ["TotaalPositie", "Artiest", "Titel", "Uitjaar"]
    if kop[:4] != verwacht:
        raise ValueError(f"{pad.name}: eerste kolommen zijn {kop[:4]}, "
                         f"verwacht {verwacht}")
    try:
        edities = [int(j) for j in kop[4:]]
    except ValueError as fout:
        raise ValueError(f"{pad.name}: kolomkop is geen jaartal ({fout})") from fout
    if not edities:
        raise ValueError(f"{pad.name}: geen editiekolommen gevonden")

    uit: list[Regel] = []
    for nr, rij in enumerate(rijen, start=2):
        if len(rij) < 4:
            raise ValueError(f"{pad.name} regel {nr}: te weinig kolommen")
        artiest, titel = rij[1].strip(), rij[2].strip()
        if not artiest or not titel:
            raise ValueError(f"{pad.name} regel {nr}: artiest of titel ontbreekt")
        regel = Regel(artiest=artiest, titel=titel,
                      uitjaar=int(rij[3]) if rij[3].strip().isdigit() else None)
        for i, jaar in enumerate(edities):
            waarde = rij[4 + i].strip() if 4 + i < len(rij) else ""
            if waarde and waarde != "0":
                regel.posities[jaar] = int(waarde)
        if regel.posities:
            uit.append(regel)
    return edities, uit


def controleer(edities: list[int], regels: list[Regel]) -> list[str]:
    """Klopt elke editie? Geeft de klachten terug, leeg is goed.

    Een editie hoort de posities 1..2000 precies een keer te bevatten. Dat is
    strenger dan bij de weeklijsten, waar gedeelde posities voorkomen -- de
    Top 2000 kent die niet.
    """
    lengte = LIJSTEN[LIJST]["lengte"]
    klachten = []
    for jaar in edities:
        posities = [r.posities[jaar] for r in regels if jaar in r.posities]
        if not posities:
            klachten.append(f"{jaar}: geen enkele notering")
            continue
        dubbel = len(posities) - len(set(posities))
        ontbreekt = set(range(1, lengte + 1)) - set(posities)
        if dubbel:
            klachten.append(f"{jaar}: {dubbel} dubbele posities")
        if ontbreekt:
            kort = sorted(ontbreekt)[:5]
            klachten.append(f"{jaar}: {len(ontbreekt)} posities ontbreken "
                            f"(o.a. {kort})")
        if max(posities) > lengte:
            klachten.append(f"{jaar}: positie {max(posities)} ligt boven {lengte}")
    return klachten


def kruisverwijzing(con: sqlite3.Connection, regels: Iterable[Regel]) -> dict:
    """Hoeveel van deze nummers kennen we al uit de andere lijsten?

    De sleutel is de brug: dezelfde artiest en titel leveren dezelfde sleutel,
    ongeacht in welke lijst het nummer stond.
    """
    bekend: dict[str, set[str]] = {}
    for sleutel, lijst in con.execute(
            "SELECT DISTINCT sleutel, lijst FROM noteringen WHERE lijst<>?",
            (LIJST,)):
        bekend.setdefault(sleutel, set()).add(lijst)

    per_lijst: dict[str, int] = {}
    raak = 0
    for regel in regels:
        lijsten = bekend.get(regel.sleutel)
        if not lijsten:
            continue
        raak += 1
        for lijst in lijsten:
            per_lijst[lijst] = per_lijst.get(lijst, 0) + 1
    return {"raak": raak, "per_lijst": per_lijst}


def _noteringen(regels: list[Regel], jaar: int) -> Iterator[tuple]:
    week = LIJSTEN[LIJST].get("editie_week", 52)
    for regel in regels:
        positie = regel.posities.get(jaar)
        if positie is None:
            continue
        yield (LIJST, jaar, week, positie, regel.titel, regel.artiest,
               None, len(regel.posities), regel.posities.get(jaar - 1),
               "onbekend", regel.sleutel, regel.uitjaar)


def importeer(con: sqlite3.Connection, pad: Path | str, *,
              alleen_jaar: Optional[int] = None) -> dict:
    """Lees de CSV en schrijf elke editie weg. Vervangt wat er al stond.

    `weken_genoteerd` krijgt het aantal edities waarin het nummer stond en
    `vorige_positie` de plek van vorig jaar -- dezelfde betekenis als bij de
    weeklijsten, alleen een editie in plaats van een week verder terug.
    """
    from .db import bewaar_week

    edities, regels = lees_csv(pad)
    klachten = controleer(edities, regels)
    if klachten:
        raise ValueError("de CSV klopt niet:\n  " + "\n  ".join(klachten))

    con.execute("SAVEPOINT top2000")
    try:
        geschreven = {}
        for jaar in edities:
            if alleen_jaar is not None and jaar != alleen_jaar:
                continue
            rijen = list(_noteringen(regels, jaar))
            con.execute("DELETE FROM noteringen WHERE lijst=? AND jaar=?",
                        (LIJST, jaar))
            con.executemany(
                "INSERT INTO noteringen (lijst, jaar, week, positie, titel,"
                " artiest, label, weken_genoteerd, vorige_positie, site_status,"
                " sleutel, uitjaar) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rijen)
            con.execute(
                "INSERT OR REPLACE INTO opgehaald (lijst, jaar, week, aantal,"
                " opgehaald_op) VALUES (?,?,?,?,datetime('now'))",
                (LIJST, jaar, LIJSTEN[LIJST].get("editie_week", 52), len(rijen)))
            geschreven[jaar] = len(rijen)
    except Exception:
        con.execute("ROLLBACK TO SAVEPOINT top2000")
        raise
    finally:
        con.execute("RELEASE SAVEPOINT top2000")

    return {
        "edities": edities,
        "nummers": len(regels),
        "geschreven": geschreven,
        "kruisverwijzing": kruisverwijzing(con, regels),
    }
