"""Fuzzy zoeken: vinden wat je bedoelde, niet wat je typte.

WAAROM NIET GEWOON LIKE
-----------------------
`bevat` en `exact` zijn precies: ze vinden de tekens die je intypt. Dat is de
goede stand zodra je weet hoe iets gespeld wordt. Maar bij een archief van
zesendertigduizend nummers weet je dat vaak niet -- "Bohemian Rapsody",
"Chubby Chequer", "Anni Frid" -- en dan levert precisie nul treffers op
terwijl het nummer er gewoon staat.

HOE HET WERKT
-------------
Twee trappen, want er zijn twee soorten missers.

1. **De spelling zit er dichtbij.** `difflib.SequenceMatcher` geeft een
   gelijkenis tussen 0 en 1; vanaf `DREMPEL` telt het als treffer. Beide
   kanten gaan eerst door `normaliseer`, dus accenten, leestekens en
   hoofdletters spelen al geen rol meer -- die zou je anders als "fuzzy"
   verkopen terwijl het gewoon opruimen is.

2. **Je typte er een woord bij, of juist een woord te weinig.** "queen
   bohemian" staat in geen enkel veld zo, want de artiest is Queen en de titel
   Bohemian Rhapsody. Daarom telt ook een treffer waarbij **elk woord uit de
   zoekterm** een woord in artiest of titel dicht benadert.

De uitkomst is gesorteerd op gelijkenis, want bij fuzzy zoeken is de volgorde
het halve antwoord.

WAT HET KOST -- EN WAAR DAT IN ZIT
----------------------------------
De eerste versie deed er vijf seconden over, en de schuldige was niet het
vergelijken maar het **voorbereiden**: `normaliseer` liep per zoekopdracht
over alle 36.000 kandidaten, en dat zijn een stuk of tien regex-vervangingen
per veld. Dat werk hangt niet van de zoekterm af, dus het hoort in de cache en
niet in de zoekopdracht -- vandaar `bereid_voor()`, die de aanroeper één keer
draait en bewaart.

Wat overblijft is difflib, en daar helpen twee dingen. De zoekterm gaat als
`b` in één `SequenceMatcher` die hergebruikt wordt: difflib bouwt voor `b` een
index op en die hoeft dan maar één keer. En `real_quick_ratio`/`quick_ratio`
zijn bovengrenzen die het dure vergelijken overslaan zodra ze al onder de
drempel blijven. Samen brengt dat het terug tot een halve seconde.
"""
from __future__ import annotations

from difflib import SequenceMatcher

from .normalize import normaliseer

__all__ = ["treffers", "bereid_voor", "DREMPEL", "DREMPEL_WOORD"]

# Vanaf welke gelijkenis iets een treffer is. 0,68 laat "bohemian rapsody"
# door en "chubby chequer", maar houdt losse woorden die toevallig op elkaar
# lijken buiten de deur.
DREMPEL = 0.68

# Per woord mag het strenger: korte woorden lijken snel op elkaar, en een
# zoekterm van drie woorden waarvan er twee half kloppen is geen treffer.
DREMPEL_WOORD = 0.82

# Onder de drie tekens heeft fuzzy geen betekenis meer -- dan lijkt alles op
# alles en komt het hele archief terug.
KORTSTE = 3


def bereid_voor(rijen) -> list[tuple]:
    """Normaliseer de kandidaten één keer, zodat zoeken goedkoop wordt.

    `rijen` is een rij (sleutel, artiest, titel); terug komt
    (sleutel, artiest, titel, woorden) met alles al genormaliseerd. Hoort in
    de cache van de aanroeper: dit werk hangt van de gegevens af en niet van
    de zoekterm.
    """
    uit = []
    for sleutel, artiest, titel in rijen:
        a = normaliseer(artiest, samenwerking=False)
        t = normaliseer(titel, samenwerking=False)
        uit.append((sleutel, a, t, (a + " " + t).split()))
    return uit


def treffers(term: str, kandidaten, waar: str = "beide",
             grens: int = 200) -> list[tuple[str, float]]:
    """De sleutels die op `term` lijken, met hun score, beste eerst.

    `kandidaten` komt uit `bereid_voor()`. `waar` bepaalt waar gekeken wordt,
    net als bij het gewone zoeken.
    """
    gezocht = normaliseer(term, samenwerking=False)
    if len(gezocht) < KORTSTE:
        return []
    woorden = gezocht.split()
    meerdere = len(woorden) > 1

    # Eén matcher, met de zoekterm als b: difflib bouwt voor b een index op en
    # hergebruikt die zolang b niet verandert.
    meter = SequenceMatcher(None, "", gezocht, autojunk=False)
    woordmeters = {}
    if meerdere:
        for woord in woorden:
            woordmeters[woord] = SequenceMatcher(None, "", woord,
                                                 autojunk=False)

    def gelijk(meter, tekst: str, drempel: float) -> float:
        meter.set_seq1(tekst)
        if meter.real_quick_ratio() < drempel or meter.quick_ratio() < drempel:
            return 0.0
        r = meter.ratio()
        return r if r >= drempel else 0.0

    def woorden_passen(kandidaatwoorden) -> float:
        """De zwakste van de zoekwoorden, of 0 als er een helemaal mist.

        De zwakste en niet het gemiddelde: bij "queen bohemian" moeten ze
        allebei kloppen. Een gemiddelde laat een half fout woord verdwijnen
        achter een perfect eerste.
        """
        zwakste = 1.0
        for woord in woorden:
            beste = 0.0
            m = woordmeters[woord]
            for ander in kandidaatwoorden:
                if woord == ander or (len(woord) >= 4 and woord in ander):
                    beste = 1.0
                    break
                beste = max(beste, gelijk(m, ander, DREMPEL_WOORD))
            if not beste:
                return 0.0
            zwakste = min(zwakste, beste)
        return zwakste

    uit: list[tuple[str, float]] = []
    for sleutel, artiest, titel, kandidaatwoorden in kandidaten:
        if waar == "artiest":
            velden = (artiest,)
        elif waar == "titel":
            velden = (titel,)
        else:
            # Ook de combinatie, want een zoekterm die artiest en titel
            # overspant staat in geen van beide velden apart.
            velden = (artiest, titel, artiest + " " + titel)

        beste = 0.0
        for veld in velden:
            if not veld:
                continue
            if gezocht in veld:
                # Een letterlijke treffer is geen benadering; die hoort
                # bovenaan, ook als de rest van het veld lang is.
                beste = 1.0
                break
            r = gelijk(meter, veld, DREMPEL)
            if r > beste:
                beste = r
        if beste < 1.0 and meerdere:
            if waar == "artiest":
                kandidaatwoorden = artiest.split()
            elif waar == "titel":
                kandidaatwoorden = titel.split()
            # Iets lager gewaardeerd dan een gelijkenis over het hele veld:
            # losse woorden die kloppen is zwakker bewijs dan een tekst die
            # als geheel lijkt.
            beste = max(beste, woorden_passen(kandidaatwoorden) * 0.95)
        if beste:
            uit.append((sleutel, round(beste, 3)))

    uit.sort(key=lambda p: (-p[1], p[0]))
    return uit[:grens]
