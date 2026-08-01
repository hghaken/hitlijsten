"""Kruiscontrole van onze Top 40-cijfers tegen michajans.nl.

Micha Jans publiceert de jaarlijsten van de Werkgroep Hitlijsten (top40web.nl),
een archief dat losstaat van top40.nl. Twee onafhankelijke bronnen die op
hetzelfde uitkomen is het sterkste bewijs dat onze parser en puntenberekening
kloppen -- en waar ze verschillen zit vrijwel altijd een echte fout.

Hun jaarlijst geeft per nummer: punten, hoogste positie, aantal weken en de
datum van binnenkomst. De puntentelling is dezelfde als de onze
(41 - positie per notering), wat over 26 jaargangen op 5898 nummers exact
uitkwam.

Twee dingen om te weten over hun lijst:

* Een nummer dat onderweg hernoemd werd (dubbele A-kant, remix, toegevoegde
  gastartiest) krijgt bij hen soms een EXTRA regel voor die periode. De punten
  van die regel zitten ook al in het hoofdtotaal, dus zo'n regel telt dubbel.
  Voorbeeld: "Azizam" 862 punten over 26 weken, plus "Azizam (Persion versian)"
  32 punten over 1 week -- die ene week zit in beide.
* Hun site loopt achter. De laatste jaarlijst is 2025.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .config import CACHE_DIR
from .db import noteringen_van_jaar, verbinding
from .normalize import normaliseer

BASIS = "https://www.michajans.nl"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
PAUZE = 1.0


@dataclass
class Regel:
    """Een regel uit hun jaarlijst."""

    positie: int
    punten: int
    hoogste: int
    weken: int
    binnenkomst: str
    naam: str

    @property
    def woorden(self) -> set[str]:
        return set(normaliseer(self.naam, samenwerking=False).split())


@dataclass
class OnsNummer:
    sleutel: str
    naam: str
    punten: int
    hoogste: int
    weken: int

    @property
    def woorden(self) -> set[str]:
        return set(normaliseer(self.naam, samenwerking=False).split())


# Wanneer is een verschil groot genoeg om hun cijfer aan te houden?
#
# Micha Jans corrigeert de fouten die de officiele lijst soms bevat, dus bij een
# echt verschil heeft hij vrijwel altijd gelijk. Maar tussen twee archieven van
# dezelfde lijst zit ook ruis: een positie die een plaats afwijkt levert een
# verschil van een punt op. Dat is geen fout maar bronruis, en daarvoor houden we
# onze eigen week-voor-weekgegevens aan -- die kunnen we tenminste narekenen.
#
# Boven deze grenzen nemen we zijn cijfers over.
GROOT_VERSCHIL_WEKEN = 2
GROOT_VERSCHIL_PUNTEN = 0.05     # 5% van hun puntentotaal


def is_groot_verschil(hun_punten: int, hun_weken: int,
                      onze_punten: int, onze_weken: int) -> bool:
    if abs(hun_weken - onze_weken) > GROOT_VERSCHIL_WEKEN:
        return True
    drempel = max(2, round(hun_punten * GROOT_VERSCHIL_PUNTEN))
    return abs(hun_punten - onze_punten) > drempel


SCHEMA_CORRECTIES = """
CREATE TABLE IF NOT EXISTS correcties (
    id       INTEGER PRIMARY KEY,
    jaar     INTEGER NOT NULL,
    lijst    TEXT    NOT NULL,
    sleutel  TEXT    NOT NULL,
    punten   INTEGER NOT NULL,
    hoogste  INTEGER NOT NULL,
    weken    INTEGER NOT NULL,
    bron     TEXT    NOT NULL,
    naam     TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_correcties ON correcties (lijst, jaar, sleutel);
"""


@dataclass
class Bevinding:
    # verschil | groot_verschil | samenvoegen | alleen_bij_hen | alleen_bij_ons
    soort: str
    jaar: int
    tekst: str
    aliasregel: Optional[str] = None
    # alleen gevuld bij (groot_)verschil, om zijn cijfer te kunnen overnemen
    sleutel: Optional[str] = None
    hun_punten: Optional[int] = None
    hun_hoogste: Optional[int] = None
    hun_weken: Optional[int] = None
    hun_naam: Optional[str] = None


@dataclass
class Rapport:
    jaar: int
    identiek: int = 0
    bevindingen: list[Bevinding] = field(default_factory=list)
    hun_aantal: int = 0
    ons_aantal: int = 0


def decodeer(rauw: bytes) -> str:
    """Maak tekst van een michajans-pagina.

    Hun pagina's melden allemaal windows-1252 in de meta-tag, maar een deel is
    in werkelijkheid UTF-8 -- de alarmschijfpagina's bijvoorbeeld. Blind
    windows-1252 aannemen levert daar "TiÃ«sto" op in plaats van "Tiësto".

    UTF-8 strikt proberen is een betrouwbare test: echte windows-1252-tekst met
    accenten levert bijna altijd ongeldige vervolgbytes op en valt dus vanzelf
    door naar de andere codering.
    """
    try:
        return rauw.decode("utf-8")
    except UnicodeDecodeError:
        return rauw.decode("windows-1252", errors="replace")


def _cache_pad(jaar: int):
    return CACHE_DIR / "michajans" / f"jaarlijst-{jaar}.html"


def haal_jaarlijst(jaar: int, *, forceer: bool = False) -> Optional[list[Regel]]:
    """Hun jaarlijst van dat jaar, uit de cache tenzij `forceer`."""
    pad = _cache_pad(jaar)
    if pad.exists() and not forceer:
        html = pad.read_text(encoding="utf-8")
    else:
        html = None
        # Hun bestandsnamen wisselen tussen .htm en .html.
        for extensie in ("htm", "html"):
            respons = requests.get(
                f"{BASIS}/{jaar}.{extensie}", headers={"User-Agent": UA}, timeout=30
            )
            time.sleep(PAUZE)
            if respons.status_code == 200:
                tekst = decodeer(respons.content)
                if "<table" in tekst.lower():
                    html = tekst
                    break
        if html is None:
            return None
        pad.parent.mkdir(parents=True, exist_ok=True)
        pad.write_text(html, encoding="utf-8")

    tabel = BeautifulSoup(html, "lxml").find("table")
    if tabel is None:
        return None

    regels: list[Regel] = []
    for tr in tabel.find_all("tr"):
        cellen = [
            " ".join(td.get_text(" ", strip=True).split())
            for td in tr.find_all(["td", "th"])
        ]
        if len(cellen) < 6 or not cellen[0].isdigit():
            continue
        try:
            regels.append(
                Regel(
                    positie=int(cellen[0]),
                    punten=int(cellen[1]),
                    hoogste=int(cellen[2]),
                    weken=int(cellen[3]),
                    binnenkomst=cellen[4],
                    naam=cellen[5],
                )
            )
        except ValueError:
            continue  # tussenkopje of lege regel
    return regels or None


def bewaar_correcties(jaar: int, lijst: str, bevindingen: list[Bevinding]) -> int:
    """Leg de grote verschillen vast: zijn cijfer geldt voor die nummers.

    De weektabs blijven ongewijzigd -- die kunnen we niet corrigeren, want zijn
    jaarlijst geeft geen posities per week. Alleen het jaartotaal volgt hem.
    """
    groot = [b for b in bevindingen if b.soort == "groot_verschil" and b.sleutel]
    with verbinding() as con:
        con.executescript(SCHEMA_CORRECTIES)
        con.execute("DELETE FROM correcties WHERE jaar=? AND lijst=?", (jaar, lijst))
        con.executemany(
            "INSERT INTO correcties (jaar, lijst, sleutel, punten, hoogste, weken,"
            " bron, naam) VALUES (?,?,?,?,?,?,?,?)",
            [(jaar, lijst, b.sleutel, b.hun_punten, b.hun_hoogste, b.hun_weken,
              "michajans.nl", b.hun_naam or "") for b in groot],
        )
        con.commit()
    return len(groot)


def correcties_voor(jaar: int, lijst: str = "top40", con=None) -> dict[str, dict]:
    """{sleutel: {punten, hoogste, weken, bron}} voor een jaargang."""
    def lees(verbonden):
        verbonden.executescript(SCHEMA_CORRECTIES)
        return {
            r["sleutel"]: {
                "punten": r["punten"], "hoogste": r["hoogste"],
                "weken": r["weken"], "bron": r["bron"],
            }
            for r in verbonden.execute(
                "SELECT * FROM correcties WHERE jaar=? AND lijst=?", (jaar, lijst)
            )
        }

    if con is not None:
        return lees(con)
    with verbinding() as eigen:
        return lees(eigen)


def onze_jaarlijst(jaar: int, lijst: str = "top40") -> list[OnsNummer]:
    """Onze eigen jaartotalen, op dezelfde manier gerekend als zij."""
    with verbinding() as con:
        rijen = noteringen_van_jaar(con, lijst, jaar)
    if not rijen:
        return []

    lengte_per_week: dict[int, int] = {}
    for r in rijen:
        lengte_per_week[r["week"]] = max(lengte_per_week.get(r["week"], 0), r["positie"])

    verzameld: dict[str, dict] = {}
    for r in rijen:
        vak = verzameld.setdefault(
            r["sleutel"], {"punten": 0, "weken": set(), "hoogste": 99}
        )
        vak["punten"] += lengte_per_week[r["week"]] - r["positie"] + 1
        vak["weken"].add(r["week"])
        vak["hoogste"] = min(vak["hoogste"], r["positie"])
        vak["naam"] = f"{r['titel']} - {r['artiest']}"

    return [
        OnsNummer(
            sleutel=sleutel,
            naam=v["naam"],
            punten=v["punten"],
            hoogste=v["hoogste"],
            weken=len(v["weken"]),
        )
        for sleutel, v in verzameld.items()
    ]


def _gelijkenis(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# Onder deze gelijkenis is een koppeling te zwak om er een verschil op te
# baseren. "Adrenaline" en "Rollercoaster" van Di-Rect delen alleen de
# artiestnaam; ze als afwijking melden zou het rapport vervuilen met
# nepverschillen.
ZEKERE_KOPPELING = 0.75


def _koppel(
    hun: list[Regel], ons: list[OnsNummer]
) -> tuple[dict[int, int], set[int], dict[int, float]]:
    """Koppel hun regels aan de onze. Exacte naamovereenkomst gaat voor.

    Zonder die voorrang koppelt een gulzige gelijkenisvergelijking soms twee
    verschillende nummers van dezelfde artiest aan elkaar -- "Adrenaline" en
    "Rollercoaster" van Di-Rect delen alleen het woord "direct" en kwamen zo
    toch bij elkaar terecht.
    """
    koppeling: dict[int, int] = {}
    scores: dict[int, float] = {}
    bezet: set[int] = set()

    ons_op_naam: dict[str, list[int]] = {}
    for i, o in enumerate(ons):
        ons_op_naam.setdefault(" ".join(sorted(o.woorden)), []).append(i)

    for j, h in enumerate(hun):
        sleutel = " ".join(sorted(h.woorden))
        kandidaten = [i for i in ons_op_naam.get(sleutel, []) if i not in bezet]
        if kandidaten:
            koppeling[j] = kandidaten[0]
            scores[j] = 1.0
            bezet.add(kandidaten[0])

    for j, h in enumerate(hun):
        if j in koppeling:
            continue
        beste, hoogste = None, 0.0
        for i, o in enumerate(ons):
            if i in bezet:
                continue
            score = _gelijkenis(h.woorden, o.woorden)
            if score > hoogste:
                beste, hoogste = i, score
        if beste is not None and hoogste >= 0.6:
            koppeling[j] = beste
            scores[j] = hoogste
            bezet.add(beste)

    return koppeling, bezet, scores


MAX_STUKKEN = 4


def _zoek_samenvoeging(
    h: Regel, ons: list[OnsNummer], vrij: set[int]
) -> Optional[tuple[int, ...]]:
    """Vormen enkele van onze nummers samen precies deze ene regel van hen?

    Dat is het handtekeningpatroon van een gemiste alias: de site hernoemde een
    lopende notering, wij zagen meerdere nummers, zij een. Punten en weken
    moeten allebei optellen -- alleen punten is te weinig bewijs.

    In de jaren zestig deelden meerdere versies van hetzelfde nummer een
    positie, en de artiestenlijst groeide week na week aan: "Goldfinger -
    Shirley Bassey", dan "... / John Barry", dan "... / ZZ & de Maskers". Zo'n
    notering valt bij ons in drie of vier stukken uiteen, vandaar dat we tot
    MAX_STUKKEN zoeken en niet alleen naar paren.
    """
    from itertools import combinations

    # Zeef op INSLUITING, niet op gelijkenis: een fragment hoort in hun regel
    # thuis, maar hoeft er niet op te lijken. "Goldfinger - Shirley Bassey"
    # bestaat uit drie woorden en hun regel uit elf ("... / the Jets / John
    # Barry / ZZ & de Maskers"); de gelijkenis is dan 0,27 terwijl alle drie de
    # woorden er wel degelijk in staan.
    # Twee trappen. Eerst streng, wat vrijwel altijd meteen raak is. Levert dat
    # niets op, dan ruimer -- want top40.nl verminkt in de oude jaargangen soms
    # een hele notering: 'Titelsong Uit De Film "Zoeken Naar Eileen" - Tim
    # Hardin - How Can We Hang On To A Dre..' bevat de filmtitel en de artiest
    # in het titelveld, waardoor de insluiting op 0,53 uitkomt.
    #
    # Het echte bewijs is de optelling zelf: punten, weken en hoogste positie
    # moeten alle drie exact kloppen. Dat drievoudige samenvallen is bij
    # toevallige combinaties vrijwel uitgesloten, dus de zeef mag ruim.
    for ondergrens in (0.6, 0.35):
        kandidaten = [
            i for i in sorted(vrij)
            if ons[i].punten <= h.punten
            and ons[i].weken <= h.weken
            and ons[i].woorden
            and len(ons[i].woorden & h.woorden) / len(ons[i].woorden) >= ondergrens
        ]
        for aantal in range(2, MAX_STUKKEN + 1):
            for combinatie in combinations(kandidaten, aantal):
                stukken = [ons[i] for i in combinatie]
                if sum(s.punten for s in stukken) != h.punten:
                    continue
                if sum(s.weken for s in stukken) != h.weken:
                    continue
                if min(s.hoogste for s in stukken) != h.hoogste:
                    continue
                return combinatie
    return None


def vergelijk(jaar: int, *, lijst: str = "top40") -> Optional[Rapport]:
    """Leg onze jaartotalen naast die van michajans.nl."""
    hun = haal_jaarlijst(jaar)
    if hun is None:
        return None
    ons = onze_jaarlijst(jaar, lijst)
    if not ons:
        return None

    rapport = Rapport(jaar=jaar, hun_aantal=len(hun), ons_aantal=len(ons))
    koppeling, bezet, scores = _koppel(hun, ons)

    for j, h in enumerate(hun):
        if j in koppeling:
            o = ons[koppeling[j]]
            if (h.punten, h.hoogste, h.weken) == (o.punten, o.hoogste, o.weken):
                rapport.identiek += 1
                continue
            # Een gekoppelde regel die tóch afwijkt is vaak de ene helft van een
            # notering die wij in tweeen hebben. Zoek de andere helft, met deze
            # regel weer in de pool -- anders vinden we de optelling nooit.
            vrij = {i for i in range(len(ons)) if i not in bezet} | {koppeling[j]}
            paar = _zoek_samenvoeging(h, ons, vrij)
            if paar is None:
                if scores.get(j, 0.0) < ZEKERE_KOPPELING:
                    # Te zwakke koppeling om een verschil op te baseren: laat de
                    # regel los en meld hem als "staat maar bij een van beide".
                    bezet.discard(koppeling[j])
                    rapport.bevindingen.append(
                        Bevinding("alleen_bij_hen", jaar,
                                  f"{h.naam}  ({h.punten} pnt, {h.weken} wk)")
                    )
                    continue
                groot = is_groot_verschil(h.punten, h.weken, o.punten, o.weken)
                rapport.bevindingen.append(
                    Bevinding(
                        "groot_verschil" if groot else "verschil",
                        jaar,
                        f"{h.naam}\n"
                        f"        zij: {h.punten:>5} pnt  hoogste {h.hoogste:>2}  {h.weken:>2} wk\n"
                        f"        wij: {o.punten:>5} pnt  hoogste {o.hoogste:>2}  {o.weken:>2} wk"
                        f"   ({o.naam})"
                        + ("\n        -> groot verschil, zijn cijfer wordt aangehouden"
                           if groot else ""),
                        sleutel=o.sleutel,
                        hun_punten=h.punten,
                        hun_hoogste=h.hoogste,
                        hun_weken=h.weken,
                        hun_naam=h.naam,
                    )
                )
                continue
        else:
            vrij = {i for i in range(len(ons)) if i not in bezet}
            paar = _zoek_samenvoeging(h, ons, vrij)

        if paar:
            stukken = [ons[i] for i in paar]
            bezet.update(paar)
            # Alles wijst naar het stuk met de meeste weken.
            doel = max(stukken, key=lambda s: (s.weken, s.punten))
            regels = "\n".join(
                f"          {s.punten:>5} pnt  {s.weken:>2} wk  {s.naam}" for s in stukken
            )
            rapport.bevindingen.append(
                Bevinding(
                    "samenvoegen",
                    jaar,
                    f"{h.naam}\n"
                    f"        zij hebben een notering van {h.punten} punten over "
                    f"{h.weken} weken;\n"
                    f"        wij hebben er {len(stukken)} die daar precies bij optellen:\n"
                    + regels,
                    aliasregel="\n".join(
                        f"{s.sleutel};{doel.sleutel}" for s in stukken if s is not doel
                    ),
                )
            )
        else:
            rapport.bevindingen.append(
                Bevinding("alleen_bij_hen", jaar,
                          f"{h.naam}  ({h.punten} pnt, {h.weken} wk)")
            )

    for i, o in enumerate(ons):
        if i not in bezet:
            rapport.bevindingen.append(
                Bevinding("alleen_bij_ons", jaar,
                          f"{o.naam}  ({o.punten} pnt, {o.weken} wk)")
            )
    return rapport
