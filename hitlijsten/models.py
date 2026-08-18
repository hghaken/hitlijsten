"""Het datacontract tussen parsers, database en Excel-bouwer.

Elke parser levert een lijst van `Notering` op en niets anders. Wie een parser
schrijft hoeft alleen deze module te kennen.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Optional

# Toegestane waarden voor Notering.site_status -- wat de site zelf over de
# notering zegt. Dit is iets anders dan "nieuw" in onze Excel-zin (= eerste keer
# dit jaar in deze lijst); die bepalen wij zelf uit de database.
# Hoeveel posities de bron mag overslaan voordat we het een parseerfout noemen.
MAX_ONTBREKENDE_POSITIES = 2

STATUSSEN = {
    "nieuw",     # site markeert de notering als binnenkomer
    "stijger",   # stond vorige week lager
    "daler",     # stond vorige week hoger
    "gelijk",    # zelfde positie als vorige week
    "terug",     # re-entry, indien de site dat apart aangeeft
    "onbekend",  # site geeft niets bruikbaars
}


@dataclass
class Notering:
    """Eén regel uit één hitlijst in één week."""

    lijst: str                       # sleutel uit config.LIJSTEN
    jaar: int
    week: int
    positie: int                     # 1-gebaseerd
    titel: str
    artiest: str
    label: Optional[str] = None      # alleen Oranje Top 30 vermeldt dit
    weken_genoteerd: Optional[int] = None
    vorige_positie: Optional[int] = None   # None bij binnenkomers
    site_status: str = "onbekend"
    # top40.nl zet een belletje bij elk nummer dat ooit Alarmschijf was; dat
    # is een eigenschap van de plaat, niet van de week.
    alarmschijf: bool = False
    # De stipnotering: 0 = geen, 1 = stip, 2 = superstip. Anders dan de
    # alarmschijf hoort dit wel bij de week -- het gaat over hoe hard de plaat
    # die week steeg. Een notering heeft er hoogstens een van de twee.
    stip: int = 0

    def __post_init__(self) -> None:
        self.titel = (self.titel or "").strip()
        self.artiest = (self.artiest or "").strip()
        if self.label is not None:
            self.label = self.label.strip() or None
        if self.site_status not in STATUSSEN:
            raise ValueError(
                f"site_status {self.site_status!r} niet in {sorted(STATUSSEN)}"
            )
        if self.stip not in (0, 1, 2):
            raise ValueError(f"stip moet 0, 1 of 2 zijn, kreeg {self.stip}")
        if self.positie < 1:
            raise ValueError(f"positie moet >= 1 zijn, kreeg {self.positie}")
        if not self.titel:
            raise ValueError(f"lege titel op positie {self.positie} ({self.lijst})")
        if not self.artiest:
            raise ValueError(f"lege artiest op positie {self.positie} ({self.lijst})")

    def als_dict(self) -> dict:
        return asdict(self)


class ParseFout(Exception):
    """De HTML zag er niet uit zoals de parser verwacht."""


@dataclass
class ControleResultaat:
    ok: bool
    meldingen: list[str] = field(default_factory=list)
    # Waarnemingen die geen fout zijn maar wel het vermelden waard, zoals een
    # gedeelde positie. Deze maken `ok` niet False.
    opmerkingen: list[str] = field(default_factory=list)


def controleer_lijst(
    noteringen: list[Notering], verwachte_lengte: Optional[int]
) -> ControleResultaat:
    """Structuurcontrole: liever hard falen dan stil een halve lijst wegschrijven.

    Gedeelde posities zijn toegestaan. Hitlijsten kennen ex aequo: in de
    Tipparade van 2004 week 39 staan Usher en Usher & Alicia Keys allebei op 27,
    wat 31 rijen voor 30 posities oplevert. De controle kijkt daarom naar de
    UNIEKE posities: die moeten 1..N aaneengesloten zijn en N moet kloppen met de
    verwachte lengte. Een lijst met een gat of een verdwaalde rij valt daar nog
    steeds door.
    """
    meldingen: list[str] = []
    opmerkingen: list[str] = []
    if not noteringen:
        return ControleResultaat(False, ["parser leverde nul noteringen op"])

    posities = sorted(n.positie for n in noteringen)
    uniek = sorted(set(posities))
    lengte = uniek[-1]          # de lijst loopt van 1 tot en met de hoogste positie
    ontbrekend = sorted(set(range(1, lengte + 1)) - set(uniek))

    # Een enkel gat is geen parseerfout maar een eigenaardigheid van de bron:
    # top40.nl slaat in de Tipparade van 1994 week 34 gewoon positie 11 over en
    # springt van 10 naar 12. Zulke weken weggooien zou echte data kosten.
    #
    # Meer dan een paar gaten wijst wel op een kapotte parse -- dan blijft het
    # een fout, want een half ingelezen week is het ergste wat er kan gebeuren.
    if len(ontbrekend) > MAX_ONTBREKENDE_POSITIES:
        meldingen.append(f"ontbrekende posities: {ontbrekend}")
    elif ontbrekend:
        opmerkingen.append(
            f"de bron slaat positie {ontbrekend} over -- {len(uniek)} noteringen "
            f"op een lijst tot {lengte}"
        )

    gedeeld = sorted({p for p in posities if posities.count(p) > 1})
    if gedeeld:
        opmerkingen.append(
            f"gedeelde positie(s): {gedeeld} -- {len(noteringen)} noteringen "
            f"op {len(uniek)} posities"
        )
        # Twee artiesten op dezelfde positie is normaal; twee keer exact dezelfde
        # artiest met hetzelfde nummer niet. De database houdt dat sinds de
        # rijteller niet meer tegen, dus hier wel. Zonder deze controle telt zo'n
        # dubbele rij stil mee in de punten.
        gezien: set[tuple[int, str, str]] = set()
        for n in noteringen:
            kenmerk = (n.positie, n.artiest.casefold(), n.titel.casefold())
            if kenmerk in gezien:
                meldingen.append(
                    f"positie {n.positie}: '{n.artiest} - {n.titel}' staat er twee keer"
                )
            gezien.add(kenmerk)

    # Vergelijk met de hoogste positie, niet met het aantal noteringen: bij een
    # overgeslagen positie is de lijst nog steeds 30 lang, er staan alleen 29
    # nummers in.
    if verwachte_lengte is not None and lengte != verwachte_lengte:
        meldingen.append(
            f"verwachtte een lijst tot {verwachte_lengte}, hoogste positie is {lengte}"
        )

    for n in noteringen:
        if n.vorige_positie is not None and n.site_status == "nieuw":
            meldingen.append(
                f"positie {n.positie}: gemarkeerd als nieuw maar heeft vorige positie "
                f"{n.vorige_positie}"
            )

    return ControleResultaat(not meldingen, meldingen, opmerkingen)
