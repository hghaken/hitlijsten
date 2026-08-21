"""Zet de artiest van één nummer om, niet van de hele credit.

Gebruik:  credit-per-titel.py "oude artiest" "titel" "nieuwe artiest" [--doen]

Nodig waar een kale credit over twee naamgenoten verdeeld moet worden: de
jaarlijsten schrijven "Free" zonder onderscheid, maar All Right Now is de
Britse Free en Keep In Touch de Nederlandse. Dan kan de credit niet in één
keer om.
"""
import sys

from hitlijsten import db, momentopnames
from hitlijsten.normalize import sleutel_van

DOEN = "--doen" in sys.argv
a = [x for x in sys.argv[1:] if x != "--doen"]
OUD, TITEL, NIEUW = a[0], a[1], a[2]

with db.verbinding() as con:
    rijen = list(con.execute(
        "SELECT id, lijst, jaar, week, positie, titel, sleutel FROM noteringen"
        " WHERE artiest=? AND lower(titel)=lower(?)", (OUD, TITEL)))
    if not rijen:
        raise SystemExit(f"{OUD} - {TITEL}: komt niet voor")
    doel = sleutel_van(NIEUW, rijen[0]["titel"])
    botst = con.execute("SELECT COUNT(*) FROM noteringen WHERE sleutel=?",
                        (doel,)).fetchone()[0]
    print(f"{OUD} - {rijen[0]['titel']}   ({len(rijen)} noteringen)")
    print(f"   -> {NIEUW}")
    print(f"   {rijen[0]['sleutel']!r} -> {doel!r}   (staat er nu {botst}x)")

    # Zou een sleutel twee keer in dezelfde editie belanden?
    bestaand = {(r["lijst"], r["jaar"], r["week"]) for r in con.execute(
        "SELECT lijst, jaar, week FROM noteringen WHERE sleutel=?", (doel,))}
    botsingen = [r for r in rijen
                 if (r["lijst"], r["jaar"], r["week"]) in bestaand]
    print(f"   gedeelde edities met het doel: {len(botsingen)}")
    for r in botsingen:
        print(f"      {r['lijst']} {r['jaar']} wk {r['week']} #{r['positie']}")

    if not DOEN:
        print("\nPROEF -- niets gewijzigd")
        raise SystemExit

    print(f"\nmomentopname: {momentopnames.maak('voor een credit per titel').name}")
    db.onthoud_verhuizing(con, rijen[0]["sleutel"], doel, "credit per nummer")
    n = con.execute(
        "UPDATE noteringen SET artiest=?, sleutel=? WHERE artiest=?"
        " AND lower(titel)=lower(?)", (NIEUW, doel, OUD, TITEL)).rowcount
    db.markeer_te_bouwen(con, sleutels=[doel], reden="credit per nummer")
    con.commit()
    r = con.execute(
        "SELECT COUNT(*) n, COUNT(DISTINCT sleutel) k, MIN(jaar) v, MAX(jaar) t"
        " FROM noteringen WHERE artiest=?", (NIEUW,)).fetchone()
    print(f"{n} noteringen om; {NIEUW} staat nu op {r['n']} noteringen,"
          f" {r['k']} nummers, {r['v']}-{r['t']}")
    over = con.execute("SELECT COUNT(*) FROM noteringen WHERE artiest=?",
                       (OUD,)).fetchone()[0]
    print(f"{OUD} houdt er {over} over")
