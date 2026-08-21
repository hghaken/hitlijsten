"""Records waarvan de bronnen de titel anders spellen gelijktrekken.

De weeklijst wint van de jaarlijst: die staat dichter bij de plaat.
Records zonder weeknotering worden gemeld en niet aangeraakt.

Gebruik:  titelvorm.py [--doen]
"""
import subprocess
import sys
from collections import Counter
from pathlib import Path

from hitlijsten import config, db

DOEN = "--doen" in sys.argv

with db.verbinding() as con:
    scheef = [r["sleutel"] for r in con.execute(
        "SELECT sleutel FROM noteringen GROUP BY sleutel"
        " HAVING COUNT(DISTINCT titel) > 1")]
    plan, geen_week = [], []
    for sleutel in scheef:
        week, alles, artiest = Counter(), Counter(), None
        for r in con.execute("SELECT artiest, titel, lijst FROM noteringen"
                             " WHERE sleutel=?", (sleutel,)):
            artiest = r["artiest"]
            alles[r["titel"]] += 1
            if not config.is_jaarlijks(r["lijst"]):
                week[r["titel"]] += 1
        if not week:
            geen_week.append((artiest, alles))
            continue
        wint = week.most_common(1)[0][0]
        for titel in alles:
            if titel != wint:
                plan.append((artiest, titel, wint, alles[titel]))

for artiest, oud, nieuw, n in plan:
    print(f"{artiest}")
    print(f"   {oud!r}  ({n}x)")
    print(f"-> {nieuw!r}")
for artiest, alles in geen_week:
    print(f"GEEN WEEKNOTERING: {artiest} -- {dict(alles)}")

if not DOEN:
    print("\nPROEF -- niets gewijzigd")
    raise SystemExit
for artiest, oud, nieuw, _ in plan:
    subprocess.call([sys.executable, str(Path(__file__).with_name("titel.py")), artiest, oud, nieuw,
                     "--doen"], stdout=subprocess.DEVNULL)
print(f"\n{len(plan)} titels gelijkgetrokken")
