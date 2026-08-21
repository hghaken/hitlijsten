"""Artiesten en titels in kapitalen: elk woord begint met een hoofdletter.

DE REGEL IS BEWUST EENZIJDIG: er wordt alleen een kleine letter naar een
hoofdletter getild, nooit andersom. Een woord dat al ergens een hoofdletter
heeft blijft ongemoeid -- anders sneuvelen ABBA, E.L.O., McCloud, AC/DC,
VOF en de landcodes (NLD, BEL, DEU).

Drie uitzonderingen, alle drie uit de proefdraai gekomen:
  * een woord dat op een apostrof volgt blijft klein ('n, 't, 'k, 's)
  * een woord midden in een naam blijft klein: P!nk, $hirak, e-mail-achtige
    constructies. Alleen na een spatie, haakje, koppelteken of schuine streep
    wordt er gekapitaliseerd.
  * o.l.v. blijft o.l.v.
"""
from __future__ import annotations

import re
import sys

from hitlijsten import db, momentopnames

DOEN = "--doen" in sys.argv

WOORD = re.compile(r"[^\W_]+[\w']*", re.UNICODE)
# Alleen hierna begint een nieuw woord. Let op: geen punt en geen uitroepteken,
# anders wordt P!nk P!Nk en d.c. D.c.
NA = set(' 	([{<"-/|+' + chr(92) + chr(0xab) + chr(0x2013) + chr(0x2014))
# Een afkorting met punten ertussen die in de bron klein stond -- o.l.v.,
# m.m.v., a.k.a. -- hoort klein te blijven. D.R.O.P., F.C. en 5 P.K. staan
# helemaal in hoofdletters en vallen hier dus buiten.
GEPUNT = re.compile(r"^[A-Z](?:\.[a-z])+\.?[:,;]?$")


def kapitaal(tekst: str) -> str:
    uit, eind = [], 0
    for m in WOORD.finditer(tekst):
        woord = m.group(0)
        uit.append(tekst[eind:m.start()])
        eind = m.end()
        voor = tekst[m.start() - 1] if m.start() else " "
        if any(c.isupper() for c in woord) or voor not in NA:
            uit.append(woord)
            continue
        uit.append(woord[0].upper() + woord[1:])
    uit.append(tekst[eind:])
    return " ".join(w.lower() if GEPUNT.match(w) else w
                    for w in "".join(uit).split(" "))


def main() -> int:
    with db.verbinding() as con:
        artiesten = [r[0] for r in con.execute(
            "SELECT DISTINCT artiest FROM noteringen")]
        titels = [r[0] for r in con.execute(
            "SELECT DISTINCT titel FROM noteringen")]
        a = {x: kapitaal(x) for x in artiesten if kapitaal(x) != x}
        t = {x: kapitaal(x) for x in titels if kapitaal(x) != x}
        print(f"artiesten: {len(a)} van {len(artiesten)}")
        print(f"titels:    {len(t)} van {len(titels)}")

        print("\n-- de gevallen die eerder misgingen --")
        for x in ("D.R.O.P.", "T.O.T.T.", "P!nk & Eminem", "$hirak & Boef",
                  "Guru & Ronny Jordan & D.C. Lee",
                  "Bob Smit & het Duke City Sextet o.l.v. Jan Bijlaart",
                  "Wim Sonneveld & Hetty Blok en orkest o.l.v. Harry Bannink",
                  "'k Heb je lief", "VOF de Kunst", "Hi-five in de zon"):
            merk = "" if kapitaal(x) == x else "  <-- verandert"
            print(f"   {x!r}\n-> {kapitaal(x)!r}{merk}")

        if not DOEN:
            print("\nPROEF -- niets gewijzigd")
            return 0

        momentopnames.maak("voor-de-kapitalisatie")
        # Per naam een UPDATE betekent per naam een scan over 568.000 regels.
        # Via een koppeltabel is het er twee, en dat scheelt uren.
        con.execute("CREATE TEMP TABLE kap_a (oud TEXT PRIMARY KEY, nieuw TEXT)")
        con.execute("CREATE TEMP TABLE kap_t (oud TEXT PRIMARY KEY, nieuw TEXT)")
        con.executemany("INSERT INTO kap_a VALUES (?,?)", a.items())
        con.executemany("INSERT INTO kap_t VALUES (?,?)", t.items())
        raakt = {r[0] for r in con.execute(
            "SELECT DISTINCT sleutel FROM noteringen"
            " WHERE artiest IN (SELECT oud FROM kap_a)"
            "    OR titel   IN (SELECT oud FROM kap_t)")}
        con.execute(
            "UPDATE noteringen SET artiest ="
            " (SELECT nieuw FROM kap_a WHERE oud = artiest)"
            " WHERE artiest IN (SELECT oud FROM kap_a)")
        con.execute(
            "UPDATE noteringen SET titel ="
            " (SELECT nieuw FROM kap_t WHERE oud = titel)"
            " WHERE titel IN (SELECT oud FROM kap_t)")
        for tabel in ("artiestnamen", "titelnamen"):
            for r in list(con.execute(f"SELECT sleutel, naam FROM {tabel}")):
                nieuw = kapitaal(r["naam"])
                if nieuw != r["naam"]:
                    con.execute(f"UPDATE {tabel} SET naam=? WHERE sleutel=?",
                                (nieuw, r["sleutel"]))
        con.execute(
            "INSERT INTO wijzigingen (tijdstip, soort, verwijst, veld, oud,"
            " nieuw, reden) VALUES (datetime('now'), 'notering', ?, ?, ?, ?, ?)",
            ("alle", "artiest+titel", f"{len(a)} artiesten, {len(t)} titels",
             "gekapitaliseerd", "elk woord een hoofdletter, op verzoek"))
        db.markeer_te_bouwen(con, sleutels=sorted(raakt))
        con.commit()
        print(f"klaar: {len(a)} artiesten, {len(t)} titels,"
              f" {len(raakt)} records in de bouwrij")
    return 0


raise SystemExit(main())
