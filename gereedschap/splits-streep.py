"""Gedeelde plekken splitsen die als één regel in het archief staan.

top40.nl zet twee uitvoeringen op een plek soms als twee losse regels en soms
als één regel met een schuine streep. In het eerste geval komen ze allebei het
archief in, in het tweede blijft er één over. Dezelfde plaat krijgt daardoor
twee behandelingen, puur naar hoe de bron het die week opschreef.

Anders dan `opschonen.splits_versies` kijkt dit NIET naar `zelfde_act`. Die
regel zegt dat een hernoemde notering ("Old Town Road / Old Town Road - Remix")
één notering blijft, maar zo staat het archief er niet in. Doortrekken is de
keuze voor wat er al staat.

DRIE VORMEN, DRIE BEHANDELINGEN -- alle drie kwamen ze uit een proefdraai:

1. De gecombineerde regel staat nog in het archief ("Mauvais Djo / Kano Choir
   & Mauvais Djo - Pilé / Pilé (Chorist Remix)"). Dan wordt die regel de eerste
   uitvoering en komen de andere erbij. Er blind bij inserten zou er drie van
   maken.
2. Het archief heeft de eerste uitvoering al, met dezelfde sleutel als de bron.
   Dan komt alleen de rest erbij.
3. Het archief heeft de eerste uitvoering al maar onder een met de hand
   rechtgezette naam, dus met een ándere sleutel ("Lustrum U.V.S.V. & N.V.V.S.U.
   & Anno Ons & ..." tegenover de bron "Lustrum U.V.S.V./N.V.V.S.U., ..."). Op
   sleutel vergelijken zou beide kanten als ontbrekend aanmerken. Daarom telt
   het AANTAL: de bestaande regels zijn de eerste uitvoeringen, wat daarna komt
   ontbreekt.

En de titels staan niet altijd heel in de <h2> -- bij een lange regel kapt de
site ook die af. Het scheidingspunt tussen artiesten en titels wordt daarom uit
het Details-attribuut zelf gezocht: de " - " waarbij beide kanten in even veel
stukken uiteenvallen.

Gebruik:  splits-streep.py [--doen]
"""
from __future__ import annotations

import re
import sys

from bs4 import BeautifulSoup

from hitlijsten import db, fetch, momentopnames
from hitlijsten.config import LIJSTEN, is_jaarlijks
from hitlijsten.normalize import sleutel_van

DOEN = "--doen" in sys.argv
DETAIL = "Details "
STREEP = " / "


def knip(vol: str) -> list[tuple[str, str]] | None:
    """Splits "artiesten - titels" in losse (artiest, titel)-paren.

    Probeert elke " - " als scheidingspunt en houdt de eerste waarbij links en
    rechts in even veel stukken uiteenvallen, met minstens twee stukken.
    """
    for m in re.finditer(" - ", vol):
        a = vol[:m.start()].split(STREEP)
        t = vol[m.end():].split(STREEP)
        if len(a) == len(t) > 1:
            return [(x.strip(), y.strip()) for x, y in zip(a, t)]
    return None


def uit_pagina(html: str) -> dict[int, list[tuple[str, str]]]:
    soep = BeautifulSoup(html, "html.parser")
    uit: dict[int, list[tuple[str, str]]] = {}
    for rij in soep.select(".top40-list__item"):
        blok = rij.select_one(".number-block")
        if blok is None:
            continue
        cijfer = re.search(r"\d+", blok.get_text(" ", strip=True))
        if not cijfer:
            continue
        for tag in rij.select("[title]"):
            t = " ".join((tag.get("title") or "").split())
            if t.startswith(DETAIL):
                paren = knip(t[len(DETAIL):])
                if paren:
                    uit[int(cijfer.group())] = paren
                break
    return uit


def main() -> int:
    werk = []
    with db.verbinding() as con:
        for lijst in [x for x in LIJSTEN if not is_jaarlijks(x)]:
            if LIJSTEN[lijst].get("site") != "top40nl":
                continue
            for jaar, week in [(r[0], r[1]) for r in con.execute(
                    "SELECT DISTINCT jaar, week FROM noteringen WHERE lijst=?"
                    " ORDER BY jaar, week", (lijst,))]:
                if not fetch.in_cache(lijst, jaar, week):
                    continue
                for plek, paren in uit_pagina(
                        fetch.haal_html(lijst, jaar, week)).items():
                    rijen = list(con.execute(
                        "SELECT * FROM noteringen WHERE lijst=? AND jaar=?"
                        " AND week=? AND positie=? ORDER BY id",
                        (lijst, jaar, week, plek)))
                    if not rijen or len(rijen) >= len(paren):
                        continue
                    samen = [r for r in rijen if STREEP in (r["titel"] or "")
                             and STREEP in (r["artiest"] or "")]
                    werk.append({"rijen": [dict(r) for r in rijen],
                                 "samen": dict(samen[0]) if samen else None,
                                 "paren": paren})

        bij = om = 0
        for w in werk:
            r0 = w["rijen"][0]
            kop = f"{r0['lijst']} {r0['jaar']} wk{r0['week']} #{r0['positie']}"
            if w["samen"]:
                a, t = w["paren"][0]
                print(f"{kop}: ~ {w['samen']['artiest'][:44]} -> {a} - {t}")
                om += 1
                rest = w["paren"][1:]
            else:
                rest = w["paren"][len(w["rijen"]):]
            for a, t in rest:
                print(f"{kop}: + {a} - {t}")
                bij += 1
        print(f"\n{om} gecombineerde regels omgezet, {bij} noteringen erbij")
        if not DOEN:
            print("PROEF -- niets gewijzigd")
            return 0

        momentopnames.maak("voor-splitsen-op-streep")
        for w in werk:
            r0 = w["rijen"][0]
            if w["samen"]:
                a, t = w["paren"][0]
                con.execute(
                    "UPDATE noteringen SET artiest=?, titel=?, sleutel=?,"
                    " dubbele_a=1 WHERE id=?",
                    (a, t, sleutel_van(a, t), w["samen"]["id"]))
                db.markeer_te_bouwen(con, sleutels=[sleutel_van(a, t)])
                rest = w["paren"][1:]
            else:
                rest = w["paren"][len(w["rijen"]):]
            for a, t in rest:
                s = sleutel_van(a, t)
                con.execute(
                    "INSERT INTO noteringen (lijst, jaar, week, positie, titel,"
                    " artiest, label, weken_genoteerd, vorige_positie,"
                    " site_status, sleutel, uitjaar, alarmschijf, stip, kroon,"
                    " dubbele_a) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,0,0,?)",
                    (r0["lijst"], r0["jaar"], r0["week"], r0["positie"], t, a,
                     r0["label"], r0["weken_genoteerd"], r0["vorige_positie"],
                     r0["site_status"], s, r0["uitjaar"],
                     1 if w["samen"] else 0))
                con.execute(
                    "INSERT INTO wijzigingen (tijdstip, soort, verwijst, veld,"
                    " oud, nieuw, reden)"
                    " VALUES (datetime('now'),'versies',?,?,?,?,?)",
                    (f"{r0['lijst']} {r0['jaar']} wk{r0['week']}"
                     f" #{r0['positie']}", "artiest+titel", None, f"{a} - {t}",
                     "de bron zette meer uitvoeringen op deze plek dan het"
                     " archief bewaarde"))
                db.markeer_te_bouwen(con, sleutels=[s])
        con.commit()
        print(f"klaar: {om} omgezet, {bij} toegevoegd")
    return 0


raise SystemExit(main())
