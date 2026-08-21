"""Hernoem een titel binnen een artiest, met sleutel en alias.

Gebruik:  titel.py "artiest" "oude titel" "nieuwe titel" [--doen]

De alias is het vangnet: haal je die jaargang later opnieuw op, dan levert de
bron de oude titel weer aan en zou het nummer opnieuw splitsen.
"""
import sys
from datetime import datetime

from hitlijsten import db, momentopnames
from hitlijsten.normalize import sleutel_van, vergeet_aliases

DOEN = "--doen" in sys.argv
a = [x for x in sys.argv[1:] if x != "--doen"]
ARTIEST, OUD, NIEUW = a[0], a[1], a[2]

with db.verbinding() as con:
    rijen = list(con.execute(
        "SELECT id, sleutel, lijst, jaar, week, positie FROM noteringen"
        " WHERE artiest=? AND titel=?", (ARTIEST, OUD)))
    if not rijen:
        raise SystemExit(f"{ARTIEST} — {OUD}: komt niet voor")
    doel = sleutel_van(ARTIEST, NIEUW)
    botst = con.execute("SELECT COUNT(*) FROM noteringen WHERE sleutel=?",
                        (doel,)).fetchone()[0]
    print(f"{ARTIEST}")
    print(f"   {OUD!r} -> {NIEUW!r}   ({len(rijen)} noteringen)")
    for r in rijen[:4]:
        print(f"      {r['lijst']} {r['jaar']} wk {r['week']} #{r['positie']}")
    print(f"   sleutel {rijen[0]['sleutel']!r}")
    print(f"        -> {doel!r}   (staat er nu {botst}x)")
    if not DOEN:
        print("\nPROEF -- niets gewijzigd")
        raise SystemExit

    print(f"\nmomentopname: {momentopnames.maak('voor een titelhernoeming').name}")
    db.onthoud_verhuizing(con, rijen[0]["sleutel"], doel, "titel gelijkgetrokken")
    con.execute(
        "INSERT OR REPLACE INTO aliases (van, naar, opmerking, aangemaakt)"
        " VALUES (?,?,?,?)",
        (rijen[0]["sleutel"], doel, "de bron schrijft de titel zonder toevoeging",
         datetime.now().isoformat(timespec="seconds")))
    n = con.execute("UPDATE noteringen SET titel=?, sleutel=? WHERE artiest=?"
                    " AND titel=?", (NIEUW, doel, ARTIEST, OUD)).rowcount
    db.markeer_te_bouwen(con, sleutels=[doel], reden="titel gelijkgetrokken")
    con.commit()
    vergeet_aliases()
    print(f"{n} noteringen om, alias gelegd")
    for r in con.execute(
            "SELECT titel, COUNT(*) n, COUNT(DISTINCT lijst) l, MIN(jaar) v,"
            " MAX(jaar) t, MIN(positie) h FROM noteringen WHERE artiest=?"
            " GROUP BY sleutel ORDER BY n DESC", (ARTIEST,)):
        print(f"   {r['titel'][:32]:<34} {r['n']:>3}x, {r['l']} lijst(en),"
              f" {r['v']}-{r['t']}, hoogste #{r['h']}")
