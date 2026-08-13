"""De records: de klappers over alle lijsten en jaargangen heen.

De wetenswaardigheden rekenen per lijst; dit zijn de overkoepelende
uitersten. Elke ranglijst is een los blok met zijn eigen query -- geen
gedeelde tussenstructuur, want de vragen lijken niet op elkaar. De pagina
cachet het geheel op een stempel, dus de prijs van een blok telt één keer
per wijziging.
"""
from __future__ import annotations

import sqlite3

from .config import LIJSTEN, is_jaarlijks

__all__ = ["verzamel"]

AANTAL = 10          # regels per blok


def _weeklijsten() -> list[str]:
    return [naam for naam in LIJSTEN if not is_jaarlijks(naam)]


def _plek(namen) -> str:
    return ",".join("?" for _ in namen)


def verzamel(con: sqlite3.Connection) -> list[dict]:
    """Alle blokken: {titel, uitleg, kolommen, regels}."""
    week = _weeklijsten()
    blokken = []

    # 1. Meeste weken genoteerd (één nummer in één lijst)
    rijen = list(con.execute(
        f"SELECT sleutel, lijst, MAX(artiest) artiest, MAX(titel) titel,"
        f" COUNT(*) weken, MIN(jaar) van, MAX(jaar) tot"
        f" FROM noteringen WHERE lijst IN ({_plek(week)})"
        f" GROUP BY sleutel, lijst ORDER BY weken DESC LIMIT {AANTAL}", week))
    blokken.append({
        "titel": "Meeste weken genoteerd",
        "uitleg": "Eén nummer, één lijst, alle jaargangen bij elkaar.",
        "kolommen": ["Artiest", "Titel", "Lijst", "Weken", "Periode"],
        "regels": [[r["artiest"], (r["titel"], r["sleutel"]),
                    r["lijst"], r["weken"],
                    f"{r['van']}" + (f"–{r['tot']}" if r["tot"] != r["van"]
                                     else "")] for r in rijen],
    })

    # 2. Meeste weken op nummer 1 (Top 40)
    rijen = list(con.execute(
        f"SELECT sleutel, MAX(artiest) artiest, MAX(titel) titel,"
        f" COUNT(*) weken, MIN(jaar) jaar FROM noteringen"
        f" WHERE lijst='top40' AND positie=1"
        f" GROUP BY sleutel ORDER BY weken DESC LIMIT {AANTAL}"))
    blokken.append({
        "titel": "Meeste weken op nummer 1",
        "uitleg": "Alleen de Nederlandse Top 40.",
        "kolommen": ["Artiest", "Titel", "Weken op 1", "Jaar"],
        "regels": [[r["artiest"], (r["titel"], r["sleutel"]), r["weken"],
                    r["jaar"]] for r in rijen],
    })

    # 3 en 4. Grootste sprong en diepste val (Top 40, binnen een week)
    for titel, orde, uitleg in (
        ("Grootste sprong omhoog", "DESC",
         "Van de ene week op de andere, binnen de Nederlandse Top 40."),
        ("Diepste val", "ASC",
         "Wat er nog nét in bleef; uitvallers tellen niet mee."),
    ):
        rijen = list(con.execute(
            f"SELECT sleutel, artiest, titel, vorige_positie, positie, jaar,"
            f" week, vorige_positie - positie sprong FROM noteringen"
            f" WHERE lijst='top40' AND vorige_positie IS NOT NULL"
            f" ORDER BY sprong {orde} LIMIT {AANTAL}"))
        blokken.append({
            "titel": titel,
            "uitleg": uitleg,
            "kolommen": ["Artiest", "Titel", "Van", "Naar", "Week"],
            "regels": [[r["artiest"], (r["titel"], r["sleutel"]),
                        r["vorige_positie"], r["positie"],
                        f"wk {r['week']}, {r['jaar']}"] for r in rijen],
        })

    # 5. Langste terugkeer: jaren tussen twee noteringen van hetzelfde nummer
    per_nummer: dict[tuple, list[int]] = {}
    for r in con.execute(
            f"SELECT DISTINCT sleutel, lijst, jaar FROM noteringen"
            f" WHERE lijst IN ({_plek(week)}) ORDER BY sleutel, lijst, jaar",
            week):
        per_nummer.setdefault((r["sleutel"], r["lijst"]), []).append(r["jaar"])
    gaten = []
    for (sleutel, lijst), jaren in per_nummer.items():
        for a, b in zip(jaren, jaren[1:]):
            if b - a > 1:
                gaten.append((b - a, sleutel, lijst, a, b))
    gaten.sort(reverse=True)
    regels = []
    for gat, sleutel, lijst, van, tot in gaten[:AANTAL]:
        naam = con.execute(
            "SELECT artiest, titel FROM noteringen WHERE sleutel=? LIMIT 1",
            (sleutel,)).fetchone()
        regels.append([naam["artiest"], (naam["titel"], sleutel), lijst,
                       f"{van} → {tot}", f"{gat} jaar"])
    blokken.append({
        "titel": "Langste terugkeer",
        "uitleg": "Uit de lijst verdwenen en jaren later alsnog terug.",
        "kolommen": ["Artiest", "Titel", "Lijst", "Weg en terug", "Gat"],
        "regels": regels,
    })

    # 6. Eenhitwonders op nummer 1 (Top 40)
    rijen = list(con.execute(
        """SELECT a.artiestdeel, MAX(n.artiest) artiest, MAX(n.titel) titel,
                  MAX(n.sleutel) sleutel, MIN(n.jaar) jaar
           FROM (SELECT substr(sleutel, 1, instr(sleutel, '|') - 1) artiestdeel
                 FROM noteringen WHERE lijst='top40'
                 GROUP BY artiestdeel HAVING COUNT(DISTINCT sleutel) = 1) a
           JOIN noteringen n
             ON substr(n.sleutel, 1, instr(n.sleutel, '|') - 1) = a.artiestdeel
            AND n.lijst='top40'
           GROUP BY a.artiestdeel
           HAVING MIN(n.positie) = 1
           ORDER BY jaar LIMIT 40"""))
    blokken.append({
        "titel": "Eenhitwonders op nummer 1",
        "uitleg": "Eén hit in de Top 40 — maar die stond wel op 1.",
        "kolommen": ["Artiest", "De ene hit", "Jaar"],
        "regels": [[r["artiest"], (r["titel"], r["sleutel"]), r["jaar"]]
                   for r in rijen],
    })

    # 7. Langste carrière in de lijsten (artiest)
    rijen = list(con.execute(
        f"""SELECT substr(sleutel, 1, instr(sleutel, '|') - 1) artiestdeel,
                   MAX(artiest) artiest, MIN(jaar) van, MAX(jaar) tot,
                   MAX(jaar) - MIN(jaar) spanne,
                   COUNT(DISTINCT sleutel) nummers
            FROM noteringen WHERE lijst IN ({_plek(week)})
            GROUP BY artiestdeel ORDER BY spanne DESC LIMIT {AANTAL}""", week))
    blokken.append({
        "titel": "Langste carrière in de weeklijsten",
        "uitleg": "Eerste tot laatste notering, alle weeklijsten.",
        "kolommen": ["Artiest", "Van", "Tot", "Spanne", "Nummers"],
        "regels": [[(r["artiest"], None, r["artiestdeel"]), r["van"],
                    r["tot"], f"{r['spanne']} jaar", r["nummers"]]
                   for r in rijen],
    })

    # 8. Meeste hits (artiest, weeklijsten)
    rijen = list(con.execute(
        f"""SELECT substr(sleutel, 1, instr(sleutel, '|') - 1) artiestdeel,
                   MAX(artiest) artiest, COUNT(DISTINCT sleutel) nummers,
                   MIN(jaar) van, MAX(jaar) tot
            FROM noteringen WHERE lijst IN ({_plek(week)})
            GROUP BY artiestdeel ORDER BY nummers DESC LIMIT {AANTAL}""",
        week))
    blokken.append({
        "titel": "Meeste hits",
        "uitleg": "Aantal verschillende nummers in de weeklijsten.",
        "kolommen": ["Artiest", "Nummers", "Periode"],
        "regels": [[(r["artiest"], None, r["artiestdeel"]), r["nummers"],
                    f"{r['van']}–{r['tot']}"] for r in rijen],
    })

    # 9. Trouwste jaarlijst-klanten: in de meeste edities
    from .db import jaarlijkse_totalen

    trouw = sorted(jaarlijkse_totalen(con),
                   key=lambda n: -n["edities"])[:AANTAL]
    blokken.append({
        "titel": "In de meeste jaaredities",
        "uitleg": "Over alle zeventien jaarlijkse lijsten bij elkaar.",
        "kolommen": ["Artiest", "Titel", "Edities", "Lijsten"],
        "regels": [[n["artiest"], (n["titel"], n["sleutel"]), n["edities"],
                    n["lijsten"]] for n in trouw],
    })

    return blokken
