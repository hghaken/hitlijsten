"""Hernoem een credit naar een opgegeven vorm, met sleutel en al.

Gebruik:  hernoem.py "oude naam" "nieuwe naam" [--doen]

Dezelfde controles als bij een slash-set: deelt de credit een plek met een
andere uitvoering, en ligt er een alias overheen die de hernoeming terugtrekt?
"""
import sys

from hitlijsten import db, momentopnames
from hitlijsten.normalize import sleutel_van

DOEN = "--doen" in sys.argv
args = [a for a in sys.argv[1:] if a != "--doen"]
OUD, NIEUW = args[0], args[1]

with db.verbinding() as con:
    rijen = list(con.execute(
        "SELECT id, titel, lijst, jaar, week, positie, sleutel FROM noteringen"
        " WHERE artiest=?", (OUD,)))
    if not rijen:
        raise SystemExit(f"{OUD!r} komt niet (meer) voor")
    print(f"{OUD}\n   -> {NIEUW}   ({len(rijen)} noteringen)")
    for r in rijen:
        print(f"      {r['lijst']} {r['jaar']} wk {r['week']} #{r['positie']}"
              f"  {r['titel']}")
    doel = sleutel_van(NIEUW, rijen[0]["titel"])
    print(f"   sleutel {rijen[0]['sleutel']!r}\n        -> {doel!r}")
    botst = con.execute("SELECT COUNT(*) FROM noteringen WHERE sleutel=?",
                        (doel,)).fetchone()[0]
    print(f"   die sleutel staat er nu {botst}x"
          + ("  -> voegt samen" if botst else ""))
    alias = con.execute("SELECT van FROM aliases WHERE naar=?",
                        (rijen[0]["sleutel"],)).fetchone()
    if alias:
        print(f"   LET OP alias: {alias['van']} -> {rijen[0]['sleutel']}")
    for r in rijen:
        buren = con.execute(
            "SELECT COUNT(*) FROM noteringen WHERE lijst=? AND jaar=? AND week=?"
            " AND positie=? AND titel=? AND artiest<>?",
            (r["lijst"], r["jaar"], r["week"], r["positie"], r["titel"],
             OUD)).fetchone()[0]
        if buren:
            print(f"   LET OP: deelt {r['lijst']} {r['jaar']} #{r['positie']}"
                  f" met {buren} andere uitvoering(en)")

    if not DOEN:
        print("\nPROEF -- niets gewijzigd")
        raise SystemExit

    print(f"\nmomentopname: {momentopnames.maak('voor een hernoeming').name}")
    for r in rijen:
        d = sleutel_van(NIEUW, r["titel"])
        if d != r["sleutel"]:
            db.onthoud_verhuizing(con, r["sleutel"], d, "credit gelijkgetrokken")
            con.execute("UPDATE noteringen SET sleutel=? WHERE id=?", (d, r["id"]))
    n = con.execute("UPDATE noteringen SET artiest=? WHERE artiest=?",
                    (NIEUW, OUD)).rowcount
    db.markeer_te_bouwen(con, sleutels=[doel], reden="credit gelijkgetrokken")
    con.commit()
    r = con.execute(
        "SELECT COUNT(*) n, COUNT(DISTINCT lijst) l, MIN(jaar) v, MAX(jaar) t"
        " FROM noteringen WHERE artiest=?", (NIEUW,)).fetchone()
    print(f"{n} noteringen om; {NIEUW} staat nu op {r['n']} noteringen"
          f" in {r['l']} lijst(en), {r['v']}-{r['t']}")
