"""De vier Tipparade-noteringen van Seal die top40.nl in zijn lijst mist.

De HTML-lijst van top40.nl geeft voor 1994 weken 34-37 maar 29 regels; de
gescande papieren Tipparade op diezelfde site (de pdf-knop) heeft ze wel.
"""
import sys

from hitlijsten import db, momentopnames

DOEN = "--doen" in sys.argv
# week, positie, vorige positie, aantal weken -- afgelezen van de scans
NIEUW = [(34, 11, 22, 2), (35, 5, 11, 3), (36, 4, 5, 4), (37, 3, 4, 5)]

with db.verbinding() as con:
    bron = con.execute(
        "SELECT * FROM noteringen WHERE lijst='tipparade' AND jaar=1994"
        " AND week=33 AND positie=22").fetchone()
    print("wk33 als voorbeeld:", dict(bron))
    print()
    for week, plek, vorig, weken in NIEUW:
        bezet = con.execute(
            "SELECT COUNT(*) FROM noteringen WHERE lijst='tipparade'"
            " AND jaar=1994 AND week=? AND positie=?", (week, plek)).fetchone()[0]
        al = con.execute(
            "SELECT COUNT(*) FROM noteringen WHERE lijst='tipparade'"
            " AND jaar=1994 AND week=? AND sleutel=?",
            (week, bron["sleutel"])).fetchone()[0]
        print(f"wk{week} #{plek}: plek {'BEZET' if bezet else 'vrij'},"
              f" nummer {'staat er al' if al else 'ontbreekt'}"
              f"  (vorige {vorig}, {weken} weken)")
        if bezet or al:
            print("   -> overslaan")
            continue
        if not DOEN:
            continue
        con.execute(
            "INSERT INTO noteringen (lijst, jaar, week, positie, titel, artiest,"
            " label, weken_genoteerd, vorige_positie, site_status, sleutel,"
            " uitjaar, alarmschijf, stip, kroon, dubbele_a)"
            " VALUES ('tipparade', 1994, ?, ?, ?, ?, ?, ?, ?, 'stijger', ?, ?,"
            " ?, 0, 0, 0)",
            (week, plek, bron["titel"], bron["artiest"], bron["label"], weken,
             vorig, bron["sleutel"], bron["uitjaar"], bron["alarmschijf"]))
        con.execute(
            "INSERT INTO wijzigingen (tijdstip, soort, verwijst, veld, oud,"
            " nieuw, reden) VALUES (datetime('now'),'notering',?,?,?,?,?)",
            (f"tipparade 1994 wk{week} {bron['artiest']} - {bron['titel']}",
             "positie", None, str(plek),
             "ontbrak in de lijst van top40.nl; afgelezen van de gescande"
             " Tipparade op diezelfde site"))

    if not DOEN:
        print("\nPROEF -- niets gewijzigd")
        raise SystemExit
    db.markeer_te_bouwen(con, sleutels=[bron["sleutel"]])
    con.commit()
    print("\nvier noteringen toegevoegd")
