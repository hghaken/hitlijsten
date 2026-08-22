"""Welke plekken ontbreken er in een editie?"""
from hitlijsten import db
from hitlijsten.config import LIJSTEN, is_jaarlijks

with db.verbinding() as con:
    for lijst in [x for x in LIJSTEN if is_jaarlijks(x)]:
        for r in con.execute(
                "SELECT jaar, week, COUNT(DISTINCT positie) p, MAX(positie) m"
                " FROM noteringen WHERE lijst=? GROUP BY jaar, week"
                " HAVING p <> m", (lijst,)):
            er = {x[0] for x in con.execute(
                "SELECT DISTINCT positie FROM noteringen"
                " WHERE lijst=? AND jaar=? AND week=?",
                (lijst, r["jaar"], r["week"]))}
            mist = sorted(set(range(1, r["m"] + 1)) - er)
            print(f"{lijst} {r['jaar']} wk{r['week']}: {r['p']}/{r['m']}"
                  f" -- mist {mist}")
            for p in mist:
                for buur in (p - 1, p + 1):
                    for x in con.execute(
                            "SELECT positie, artiest, titel FROM noteringen"
                            " WHERE lijst=? AND jaar=? AND week=? AND positie=?",
                            (lijst, r["jaar"], r["week"], buur)):
                        print(f"      buur #{x['positie']:<5}"
                              f" {x['artiest']} - {x['titel']}")
