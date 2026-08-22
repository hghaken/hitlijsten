"""Elke opgeslagen weekpagina narekenen tegen het archief.

WAAROM DIT NIET UIT DE PARSER KAN KOMEN
---------------------------------------
`parsers/top40nl.py` neemt bij een afgekapte regel het **aria-label**, en dat
noemt bij een gedeelde plek alleen de eerste uitvoering -- met opzet, want het
blijft gelijk als er later een versie bijkomt. De volledige tekst staat in het
`title="Details ..."`-attribuut van dezelfde regel, en dat is dus waar deze
controle naar kijkt. Een eerdere versie las de parser-uitvoer en meldde 413
plekken die allemaal loos alarm bleken.

TEL PER KANT, NIET OVER DE HELE REGEL
-------------------------------------
Het Details-attribuut is "artiesten - titels", en een scheidingsteken staat
meestal aan allebei de kanten: "Paul De Leeuw ; Annie De Rooy - Ik Wil Niet
Dat Je Liegt ; Waarheen Waarvoor" is TWEE noteringen en niet drie. Wie de hele
tekst in een keer splitst telt elk teken dubbel. Daarom eerst de titels van de
<h2> pakken, die er aan de achterkant afknippen, en dan per kant tellen --
precies wat `opschonen.splits_kanten` doet.

HOEVEEL NOTERINGEN HOORT EEN PLEK TE HEBBEN
-------------------------------------------
    A ; B    aan een van beide kanten   dubbele A-kant       -> twee
    A / B    aan beide kanten           twee uitvoeringen    -> twee
    A / B    alleen bij de artiest      hangt ervan af, zie onder
    A // B, A /// B                     per geval / een keuze -> een
    A/B zonder spaties                  geen scheiding        -> een

Staat de streep alleen bij de artiest, dan is het of drie uitvoeringen van
hetzelfde nummer ("De Bambis / Rocco Granata / Peppino Di Capri" met een keer
"Melancholie") of twee schrijfwijzen van dezelfde naam ("Elvis / Elvis
Presley"). `opschonen.zelfde_act` beslist: delen de namen een betekenisvol
woord, dan is het dezelfde act en telt het als een.

Staat de streep aan BEIDE kanten, dan wordt `zelfde_act` NIET geraadpleegd.
Die regel zegt dat een hernoemde notering ("Old Town Road / Old Town Road -
Remix") een notering blijft, maar zo staat het archief er niet in: waar de
bron de twee als losse regels aanleverde staan ze er allebei. Sinds augustus
2026 is dat de afspraak, en de teller volgt hem.

Gebruik:  bronvergelijk.py [--alles]
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict

from bs4 import BeautifulSoup

from hitlijsten import db, fetch
from hitlijsten.config import LIJSTEN, is_jaarlijks
from hitlijsten.opschonen import zelfde_act

DETAIL = "Details "
KANT = re.compile(r" ; ")
STREEP = re.compile(r"(?<!/) / (?!/)")


def hoeveel(artiesten: str, titels: str) -> int:
    """Hoeveel losse noteringen hoort deze bronregel op te leveren?"""
    aantal = max(len(KANT.split(artiesten)), len(KANT.split(titels)))
    a, t = STREEP.split(artiesten), STREEP.split(titels)
    if len(a) > 1 and len(t) > 1:
        aantal = max(aantal, min(len(a), len(t)))
    elif len(a) > 1 and not zelfde_act(a):
        aantal = max(aantal, len(a))
    return aantal


def uit_pagina(html: str) -> dict[int, list[tuple[str, str]]]:
    """Per plek de (artiesten, titels) uit de Details-attributen.

    De titels komen uit de <h2> -- die is bijna nooit afgekapt -- en de
    artiesten uit het Details-attribuut met die titels eraf geknipt. De <h3>
    met de artiesten is juist wél vaak afgekapt.
    """
    soep = BeautifulSoup(html, "html.parser")
    uit: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for rij in soep.select(".top40-list__item"):
        blok = rij.select_one(".number-block")
        kop = rij.select_one(".top40-list__item__info h2")
        if blok is None or kop is None:
            continue
        cijfer = re.search(r"\d+", blok.get_text(" ", strip=True))
        if not cijfer:
            continue
        titels = " ".join(kop.get_text(" ", strip=True).split())
        vol = None
        for tag in rij.select("[title]"):
            t = " ".join((tag.get("title") or "").split())
            if t.startswith(DETAIL):
                vol = t[len(DETAIL):]
                break
        if not vol:
            continue
        staart = " - " + titels
        artiesten = (vol[: -len(staart)] if vol.endswith(staart)
                     else vol.partition(" - ")[0])
        uit[int(cijfer.group())].append((artiesten, titels))
    return dict(uit)


def main() -> int:
    groepen: dict = defaultdict(list)
    gedaan = zonder = 0
    with db.verbinding() as con:
        for lijst in [x for x in LIJSTEN if not is_jaarlijks(x)]:
            if LIJSTEN[lijst].get("site") != "top40nl":
                continue  # de Oranje Top 30 komt van een andere site
            for jaar, week in [(r[0], r[1]) for r in con.execute(
                    "SELECT DISTINCT jaar, week FROM noteringen WHERE lijst=?"
                    " ORDER BY jaar, week", (lijst,))]:
                if not fetch.in_cache(lijst, jaar, week):
                    continue
                bron = uit_pagina(fetch.haal_html(lijst, jaar, week))
                if not bron:
                    zonder += 1
                    continue
                gedaan += 1
                heeft = {r["positie"]: r["n"] for r in con.execute(
                    "SELECT positie, COUNT(*) n FROM noteringen WHERE lijst=?"
                    " AND jaar=? AND week=? GROUP BY positie",
                    (lijst, jaar, week))}
                for plek, paren in bron.items():
                    moet = sum(hoeveel(a, t) for a, t in paren)
                    er = heeft.get(plek, 0)
                    if er != moet:
                        wat = " | ".join(f"{a} - {t}" for a, t in paren)
                        groepen[(lijst, wat[:110], moet, er)].append(
                            (jaar, week, plek))

    print(f"{gedaan} edities nagerekend ({zonder} zonder Details-attribuut),"
          f" {len(groepen)} gevallen, {sum(len(v) for v in groepen.values())}"
          f" plekken\n")
    for kop, test in (("TE WEINIG in het archief", lambda m, e: e < m),
                      ("TE VEEL in het archief", lambda m, e: e > m)):
        deel = {k: v for k, v in groepen.items() if test(k[2], k[3])}
        print(f"{kop}: {len(deel)} gevallen,"
              f" {sum(len(v) for v in deel.values())} plekken")
        grens = None if "--alles" in sys.argv else 25
        for (lijst, wat, moet, er), waar in sorted(
                deel.items(), key=lambda x: -len(x[1]))[:grens]:
            eerste, laatste = waar[0], waar[-1]
            rest = (f" .. {laatste[0]} wk{laatste[1]}" if len(waar) > 1 else "")
            print(f"   {len(waar):>3}x  {lijst} {eerste[0]} wk{eerste[1]}{rest}"
                  f"   bron {moet}, archief {er}\n        {wat}")
        if grens and len(deel) > grens:
            print(f"   ... en nog {len(deel) - grens} gevallen (--alles toont ze)")
        print()
    return 0


raise SystemExit(main())
