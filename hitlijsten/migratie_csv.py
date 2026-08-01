"""Eenmalig: aliases.csv en niet-samenvoegen.csv naar de database.

De twee bestanden waren de laatste losse afhankelijkheid naast de database.
Ze zaten vol met de onderbouwing van elke beslissing -- welk jaar, welke lijst,
waarom -- en die commentaarregels gaan mee als `opmerking`, zodat er niets
verloren gaat bij de verhuizing.

Na afloop zijn de CSV's overbodig. Ze worden niet automatisch weggegooid; dat
blijft een bewuste stap.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .config import ALIASES_PATH, NIET_SAMENVOEGEN_PATH
from .db import verbinding


def _lees_met_commentaar(pad: Path) -> list[tuple[str, str, str]]:
    """Geef (links, rechts, opmerking) per regel.

    De opmerking is het commentaarblok dat er direct boven staat. Dat is precies
    de onderbouwing die we niet kwijt willen.
    """
    if not pad.exists():
        return []

    uit: list[tuple[str, str, str]] = []
    commentaar: list[str] = []
    with pad.open(encoding="utf-8-sig", newline="") as fh:
        for ruwe_regel in fh:
            regel = ruwe_regel.rstrip("\n")
            kaal = regel.strip()
            if not kaal:
                # Een lege regel breekt het verband: de kop van het bestand
                # hoort niet bij de eerste aliasregel die erop volgt.
                commentaar.clear()
                continue
            if kaal.startswith("#"):
                tekst = kaal.lstrip("#").strip()
                # Scheidingslijnen en de kop van het bestand zijn geen
                # onderbouwing van een specifieke regel.
                if tekst and not set(tekst) <= {"-"}:
                    commentaar.append(tekst)
                continue
            velden = next(csv.reader([regel], delimiter=";"), [])
            if len(velden) < 2:
                commentaar.clear()
                continue
            links, rechts = velden[0].strip(), velden[1].strip()
            if links and rechts:
                uit.append((links, rechts, " ".join(commentaar)))
            commentaar.clear()
    return uit


def migreer() -> tuple[int, int]:
    """Zet beide bestanden in de database. Geeft (aliases, niet-samenvoegen)."""
    nu = datetime.now().isoformat(timespec="seconds")
    aliases = _lees_met_commentaar(ALIASES_PATH)
    paren = _lees_met_commentaar(NIET_SAMENVOEGEN_PATH)

    with verbinding() as con:
        con.executemany(
            "INSERT OR REPLACE INTO aliases (van, naar, opmerking, aangemaakt)"
            " VALUES (?,?,?,?)",
            [(van, naar, opmerking or None, nu) for van, naar, opmerking in aliases],
        )
        con.executemany(
            "INSERT OR REPLACE INTO niet_samenvoegen"
            " (sleutel_a, sleutel_b, reden, aangemaakt) VALUES (?,?,?,?)",
            [(a, b, reden or None, nu) for a, b, reden in paren],
        )
        con.commit()
    return len(aliases), len(paren)


def exporteer(map_: Path | None = None) -> tuple[Path, Path]:
    """Schrijf beide tabellen terug naar CSV, als reservekopie of om te delen."""
    doel = map_ or ALIASES_PATH.parent
    alias_pad = doel / "aliases-export.csv"
    paren_pad = doel / "niet-samenvoegen-export.csv"

    with verbinding() as con:
        with alias_pad.open("w", encoding="utf-8", newline="") as fh:
            fh.write("# Export uit de database. Formaat: van;naar;opmerking\n")
            schrijver = csv.writer(fh, delimiter=";")
            for r in con.execute("SELECT van, naar, opmerking FROM aliases ORDER BY van"):
                schrijver.writerow([r["van"], r["naar"], r["opmerking"] or ""])
        with paren_pad.open("w", encoding="utf-8", newline="") as fh:
            fh.write("# Export uit de database. Formaat: sleutel_a;sleutel_b;reden\n")
            schrijver = csv.writer(fh, delimiter=";")
            for r in con.execute(
                "SELECT sleutel_a, sleutel_b, reden FROM niet_samenvoegen"
                " ORDER BY sleutel_a"
            ):
                schrijver.writerow([r["sleutel_a"], r["sleutel_b"], r["reden"] or ""])
    return alias_pad, paren_pad
