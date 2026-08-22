"""Acht noteringen die op de verkeerde plek staan terugzetten.

Datastats zette telkens twee nummers op een plek en liet de plek ernaast
leeg; hitdossier-online.nl heeft ze wel uit elkaar. Zie het onderzoek in
LEESMIJ onder "Een gat in een editie".
"""
import sys

from hitlijsten import db, momentopnames
from hitlijsten.normalize import sleutel_van

DOEN = "--doen" in sys.argv

# lijst, jaar, van-plek, naar-plek, artiest, titel
CORRECTIES = [
    ("arrow", 2001, 391, 393, "Bob Seger & The Silver Bullet Band", "Like A Rock"),
    ("arrow", 2003, 472, 473, "Lenny Kravitz", "Always On The Run"),
    ("arrow", 2013, 384, 385, "Chuck Berry", "Johnny B. Goode"),
    ("evergreen", 2013, 279, 278, "Frank Sinatra", "It Was A Very Good Year"),
    ("veronica", 2022, 192, 29, "Metallica", "Nothing Else Matters"),
    ("festival", 2021, 70, 22, "Arctic Monkeys", "Do I Wanna Know"),
    ("festival", 2025, 34, 31, "Rage Against The Machine", "Killing In The Name"),
    ("festival", 2025, 48, 43, "Goldband", "Witte Was"),
]

with db.verbinding() as con:
    plan = []
    for lijst, jaar, van, naar, artiest, titel in CORRECTIES:
        week = con.execute("SELECT week FROM noteringen WHERE lijst=? AND jaar=?"
                           " LIMIT 1", (lijst, jaar)).fetchone()[0]
        s = sleutel_van(artiest, titel)
        rijen = list(con.execute(
            "SELECT id, artiest, titel FROM noteringen WHERE lijst=? AND jaar=?"
            " AND week=? AND positie=? AND sleutel=?",
            (lijst, jaar, week, van, s)))
        bezet = con.execute(
            "SELECT COUNT(*) FROM noteringen WHERE lijst=? AND jaar=? AND week=?"
            " AND positie=?", (lijst, jaar, week, naar)).fetchone()[0]
        if len(rijen) != 1:
            print(f"OVERSLAAN {lijst} {jaar} #{van}: {len(rijen)} treffers")
            continue
        if bezet:
            print(f"OVERSLAAN {lijst} {jaar} #{naar} is al bezet")
            continue
        plan.append((rijen[0]["id"], lijst, jaar, week, van, naar,
                     rijen[0]["artiest"], rijen[0]["titel"]))
        print(f"{lijst} {jaar} wk{week}: #{van} -> #{naar}   "
              f"{rijen[0]['artiest']} - {rijen[0]['titel']}")

    if not DOEN:
        print(f"\n{len(plan)} van {len(CORRECTIES)} klaar -- PROEF, niets gewijzigd")
        raise SystemExit(0 if len(plan) == len(CORRECTIES) else 1)

    momentopnames.maak("voor-acht-plekcorrecties")
    for nr, lijst, jaar, week, van, naar, artiest, titel in plan:
        con.execute("UPDATE noteringen SET positie=? WHERE id=?", (naar, nr))
        con.execute(
            "INSERT INTO wijzigingen (tijdstip, soort, verwijst, veld, oud,"
            " nieuw, reden) VALUES (datetime('now'),'notering',?,?,?,?,?)",
            (f"{lijst} {jaar} wk{week} {artiest} - {titel}", "positie",
             str(van), str(naar),
             "datastats zette twee nummers op een plek; hitdossier-online.nl"
             " heeft ze uit elkaar"))
    db.markeer_te_bouwen(con, sleutels=sorted(
        {r[0] for r in con.execute(
            "SELECT DISTINCT sleutel FROM noteringen WHERE id IN ("
            + ",".join("?" for _ in plan) + ")", [p[0] for p in plan])}))
    con.commit()
    print(f"\n{len(plan)} noteringen verplaatst")
