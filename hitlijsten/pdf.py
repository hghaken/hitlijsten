"""Het jaaroverzicht als PDF: het puntenklassement van één lijst en jaargang.

Zwart op wit, met alleen in de banner en de voetregel een kleur. Veertig regels
per pagina, zodat er ruimte tussen de regels blijft en je hem kunt meenemen naar
de studio zonder te turen.

WAAROM EEN EIGEN LETTERTYPE
---------------------------
De ingebouwde lettertypen van PDF kunnen alleen latin-1. Dat lijkt genoeg tot je
"Orchestral Manœuvres In The Dark", "Tone Lōc", "Givēon" of "Şıkıdım" tegenkomt
-- zesendertig van de vijftienduizend nummers hebben een teken dat er niet in
past, en dat zijn precies de namen die je niet wilt verminken. Daarom sluit dit
werkboek DejaVu Sans in (`lettertypen/`, vrij herdistribueerbaar). Dat kost zo'n
honderd kilobyte per bestand en dan klopt elke naam.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from fpdf import FPDF

from .config import LIJSTEN, ROOT, excel_map
from .db import looptijden
from .excel import BestandInGebruik, verzamel_lijst

__all__ = [
    "bouw_jaaroverzicht", "schrijf_jaaroverzicht", "pad_van", "is_actueel",
    "bouw_week_alle", "REGELS_PER_PAGINA",
]

LETTERTYPEN = ROOT / "lettertypen"

REGELS_PER_PAGINA = 40

# Sinds de eigen banner (blauwpaars, zoals de site) kleuren de lijnen mee;
# het rood van de officiële jaarlijsten paste daar niet meer bij.
ACCENT = (86, 80, 245)
ACCENT_DONKER = (43, 36, 140)
BANNER_AFBEELDING = ROOT / "middelen" / "banner.jpg"
GRIJS = (110, 110, 110)
LIJN = (214, 214, 214)

BANNER = 24.0                   # hoogte van de gekleurde balk in mm
KANTLIJN = 12.0
REGEL = 6.0                     # hoogte van een tabelregel in mm

# (kop, breedte in mm, uitlijning) -- samen 186, precies de bladbreedte tussen
# de kantlijnen.
KOLOMMEN = [
    ("#", 9, "C"),
    ("Artiest", 43, "L"),
    ("Titel", 51, "L"),
    ("Punten", 14, "C"),
    ("Hoogste", 15, "C"),
    ("Weken", 13, "C"),
    ("Binnenkomst", 20.5, "C"),
    ("Laatste notering", 20.5, "C"),
]
BREED = sum(k[1] for k in KOLOMMEN)


class _Blad(FPDF):
    """A4 met de banner bovenaan en de voetregel onderaan."""

    def __init__(self, naam: str, jaar: int, ondertitel: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.naam, self.jaar, self.ondertitel = naam, jaar, ondertitel
        self.add_font("dejavu", "", LETTERTYPEN / "DejaVuSans.ttf")
        self.add_font("dejavu", "B", LETTERTYPEN / "DejaVuSans-Bold.ttf")
        self.set_auto_page_break(False)
        self.set_title(f"{naam} {jaar} - jaaroverzicht")
        self.set_creator("hitlijsten.hhaken.nl")

    def header(self) -> None:
        if BANNER_AFBEELDING.exists():
            # De banner van de site, op maat gesneden voor 210 x 24 mm.
            self.image(str(BANNER_AFBEELDING), 0, 0, 210, BANNER)
        else:
            # Zonder afbeelding: verloop in strookjes, fpdf2 kent geen echte
            # gradiënt.
            stappen = 60
            breedte = 210 / stappen
            for i in range(stappen):
                deel = i / (stappen - 1)
                self.set_fill_color(*(round(a + (b - a) * deel)
                                      for a, b in zip(ACCENT, ACCENT_DONKER)))
                self.rect(i * breedte, 0, breedte + 0.3, BANNER, "F")

        self.set_text_color(255, 255, 255)
        self.set_font("dejavu", "B", 16)
        self.set_xy(KANTLIJN, BANNER / 2 - 7.5)
        self.cell(120, 8, self.naam)
        self.set_font("dejavu", "", 8.5)
        self.set_xy(KANTLIJN, BANNER / 2 + 1)
        self.cell(120, 5, self.ondertitel)
        self.set_font("dejavu", "B", 23)
        self.set_xy(120, BANNER / 2 - 8)
        self.cell(210 - 120 - KANTLIJN, 14, str(self.jaar), align="R")
        self.set_text_color(0, 0, 0)

    def footer(self) -> None:
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.6)
        self.line(KANTLIJN, 284, 210 - KANTLIJN, 284)
        self.set_line_width(0.2)
        self.set_text_color(*GRIJS)
        self.set_font("dejavu", "", 7.5)
        self.set_xy(KANTLIJN, 286)
        self.cell(90, 6, "hitlijsten.hhaken.nl")
        self.set_xy(210 - KANTLIJN - 90, 286)
        self.cell(90, 6, f"pagina {self.page_no()} van {{nb}}", align="R")
        self.set_text_color(0, 0, 0)


def _kort(pdf: FPDF, tekst: str, breedte: float) -> str:
    """Kap af op de beschikbare breedte. Liever een puntje dan over de rand."""
    if not tekst:
        return ""
    if pdf.get_string_width(tekst) <= breedte:
        return tekst
    while tekst and pdf.get_string_width(tekst + "…") > breedte:
        tekst = tekst[:-1]
    return tekst.rstrip() + "…"


def _pas_nummerkolom(kolommen: list, aantal: int) -> list:
    """Maak de #-kolom breed genoeg voor het hoogste nummer.

    Negen millimeter past tot 999; de Top 4000 en de totaallijsten komen
    daarboven en werden "10…". Elke cijfer extra kost 2,2 mm, en die ruimte
    gaat af van de titelkolom -- de breedste, en de enige waar een puntje
    niemand stoort.
    """
    extra = max(0, (len(str(aantal)) - 3) * 2.2)
    if not extra:
        return kolommen
    uit = []
    for kop, breedte, uitlijning in kolommen:
        if kop == "#":
            breedte += extra
        elif kop == "Titel":
            breedte -= extra
        uit.append((kop, breedte, uitlijning))
    return uit


def _kopregel(pdf: _Blad, y: float, kolommen: list = KOLOMMEN) -> float:
    pdf.set_font("dejavu", "B", 7.5)
    pdf.set_text_color(*GRIJS)
    x = KANTLIJN
    for naam, breedte, uitlijning in kolommen:
        pdf.set_xy(x, y)
        pdf.cell(breedte, 5, naam.upper(), align=uitlijning)
        x += breedte
    pdf.set_text_color(0, 0, 0)
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.5)
    pdf.line(KANTLIJN, y + 5.3, KANTLIJN + BREED, y + 5.3)
    pdf.set_line_width(0.2)
    return y + 6.8


def bouw_jaaroverzicht(
    con: sqlite3.Connection, lijst: str, jaar: int
) -> Optional[bytes]:
    """Het puntenklassement van één lijst en jaargang. None als er niets is."""
    gegevens = verzamel_lijst(con, lijst, jaar)
    if gegevens is None:
        return None
    loop = looptijden(con, lijst, jaar)

    nummers = sorted(
        gegevens.nummers.values(),
        key=lambda n: (-n.punten, n.hoogste_positie, n.eerste_week, n.titel.lower()),
    )
    naam = LIJSTEN.get(lijst, {}).get("naam", lijst)
    ondertitel = (f"Puntenklassement · {len(nummers)} nummers "
                  f"over {len(gegevens.weken)} weken")

    pdf = _Blad(naam, jaar, ondertitel)
    pdf.alias_nb_pages()
    kolommen = _pas_nummerkolom(KOLOMMEN, len(nummers))

    for begin in range(0, len(nummers), REGELS_PER_PAGINA):
        pdf.add_page()
        y = _kopregel(pdf, BANNER + 9, kolommen)
        for nr, n in enumerate(nummers[begin:begin + REGELS_PER_PAGINA],
                               start=begin + 1):
            lt = loop.get(n.sleutel)
            # Het pijltje zegt dat de notering buiten dit jaar doorloopt, net als
            # in de Excel en op de website.
            eerste = lt.begin.strftime("%d/%m/%Y") if lt else ""
            laatste = lt.eind.strftime("%d/%m/%Y") if lt else ""
            if lt and lt.begon_eerder:
                eerste = "‹ " + eerste
            if lt and lt.loopt_door:
                laatste += " ›"

            pdf.set_draw_color(*LIJN)
            pdf.line(KANTLIJN, y + REGEL - 0.6, KANTLIJN + BREED, y + REGEL - 0.6)

            waarden = [str(nr), n.artiest, n.titel, str(n.punten),
                       str(n.hoogste_positie), str(n.aantal_weken),
                       eerste, laatste]
            x = KANTLIJN
            for (kop, breedte, uitlijning), waarde in zip(kolommen, waarden):
                pdf.set_font("dejavu", "B" if kop in ("#", "Punten") else "", 8)
                pdf.set_xy(x, y)
                pdf.cell(breedte, REGEL - 0.6,
                         _kort(pdf, waarde, breedte - 2), align=uitlijning)
                x += breedte
            y += REGEL

    return bytes(pdf.output())


# --- de andere uitvoer: dezelfde vormgeving, andere kolommen ---------------
#
# De banner, de voetregel en de tabelstijl zijn die van het jaaroverzicht;
# alleen de kolommen en de rijen verschillen per lijstsoort. Deze bouwers
# maken de bytes ter plekke (geen bestanden op schijf): een weeklijst is
# klein, en de klassementen mogen nooit achterlopen op de database.


def _tabel_pdf(naam: str, jaartekst, ondertitel: str, kolommen: list,
               rijen: list, vet: tuple = ("#", "Punten")) -> bytes:
    """Een klassement als PDF: kolommen (kop, mm, uitlijning) en rijen."""
    pdf = _Blad(naam, jaartekst, ondertitel)
    pdf.alias_nb_pages()
    _tabel_op_blad(pdf, kolommen, rijen, vet)
    return bytes(pdf.output())


def _tabel_op_blad(pdf: "_Blad", kolommen: list, rijen: list,
                   vet: tuple = ("#", "Punten")) -> None:
    """Zet één tabel op een bestaand blad, vanaf een nieuwe pagina.

    Apart van `_tabel_pdf` omdat een document meer dan één tabel kan
    dragen: bij "alle weeklijsten" volgen de vier lijsten elkaar op in
    hetzelfde bestand, elk met een eigen kop in de banner.
    """
    kolommen = _pas_nummerkolom(kolommen, len(rijen))
    breed = sum(k[1] for k in kolommen)

    for begin in range(0, len(rijen), REGELS_PER_PAGINA):
        pdf.add_page()
        y = BANNER + 9
        pdf.set_font("dejavu", "B", 7.5)
        pdf.set_text_color(*GRIJS)
        x = KANTLIJN
        for kop, kolbreed, uitlijning in kolommen:
            pdf.set_xy(x, y)
            pdf.cell(kolbreed, 5, kop.upper(), align=uitlijning)
            x += kolbreed
        pdf.set_text_color(0, 0, 0)
        pdf.set_draw_color(*ACCENT)
        pdf.set_line_width(0.5)
        pdf.line(KANTLIJN, y + 5.3, KANTLIJN + breed, y + 5.3)
        pdf.set_line_width(0.2)
        y += 6.8

        for rij in rijen[begin:begin + REGELS_PER_PAGINA]:
            pdf.set_draw_color(*LIJN)
            pdf.line(KANTLIJN, y + REGEL - 0.6, KANTLIJN + breed, y + REGEL - 0.6)
            x = KANTLIJN
            for (kop, kolbreed, uitlijning), waarde in zip(kolommen, rij):
                pdf.set_font("dejavu", "B" if kop in vet else "", 8)
                pdf.set_xy(x, y)
                tekst = "" if waarde is None else str(waarde)
                pdf.cell(kolbreed, REGEL - 0.6,
                         _kort(pdf, tekst, kolbreed - 2), align=uitlijning)
                x += kolbreed
            y += REGEL


def bouw_weeklijst(con: sqlite3.Connection, lijst: str, jaar: int,
                   week: int, alleen: Optional[set] = None) -> Optional[bytes]:
    """Eén week zoals uitgezonden."""
    rijen_db = list(con.execute(
        "SELECT positie, vorige_positie, artiest, titel, weken_genoteerd,"
        " site_status, sleutel FROM noteringen WHERE lijst=? AND jaar=?"
        " AND week=? ORDER BY positie", (lijst, jaar, week)))
    if alleen is not None:
        rijen_db = [r for r in rijen_db if r["sleutel"] in alleen]
    if not rijen_db:
        return None

    kolommen = [("Positie", 15, "C"), ("Vorige", 15, "C"),
                ("Artiest", 63, "L"), ("Titel", 78, "L"), ("Weken", 15, "C")]
    rijen = []
    for r in rijen_db:
        vorige = r["vorige_positie"]
        if vorige is None:
            vorige = "terug" if r["site_status"] == "terug" else "nieuw"
        rijen.append([r["positie"], vorige, r["artiest"], r["titel"],
                      r["weken_genoteerd"]])

    naam = LIJSTEN.get(lijst, {}).get("naam", lijst)
    return _tabel_pdf(naam, f"week {week}", f"Weeklijst · {len(rijen)} noteringen",
                      kolommen, rijen, vet=("Positie",))


# De maten van de doorlopende opzet (alle weeklijsten samen). Ze zijn zo
# gekozen dat een volledige Top 40 met zijn kop op ÉÉN pagina past: dat is
# de lijst waar je het vaakst naar kijkt, en hem over twee bladen zien
# lopen leest slecht. De rekensom, van boven naar beneden:
#
#   281,0  ondergrens (de voetregel begint op 284)
#  - 29,0  waar de inhoud onder de banner begint
#  = 252,0 mm werkruimte
#  -  7,0  de kop van de sectie
#  -  6,8  de kolomnamen met hun accentlijn
#  = 238,2 mm voor de regels -> 41 bij 5,8 mm per regel
#
# De losse weeklijst-PDF's houden hun eigen, iets ruimere REGEL van 6 mm;
# daar staat maar één tabel op een blad en is die ruimte er gewoon.
ONDERGRENS = 281.0
BOVENGRENS = BANNER + 5
SECTIEKOP = 7.0
SECTIEREGEL = 5.8


def _kolomkop(pdf: "_Blad", kolommen: list, y: float, breed: float) -> float:
    """De kolomnamen met de accentlijn eronder; geeft de nieuwe y terug."""
    pdf.set_font("dejavu", "B", 7.5)
    pdf.set_text_color(*GRIJS)
    x = KANTLIJN
    for kop, kolbreed, uitlijning in kolommen:
        pdf.set_xy(x, y)
        pdf.cell(kolbreed, 5, kop.upper(), align=uitlijning)
        x += kolbreed
    pdf.set_text_color(0, 0, 0)
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.5)
    pdf.line(KANTLIJN, y + 5.3, KANTLIJN + breed, y + 5.3)
    pdf.set_line_width(0.2)
    return y + 6.8


def _sectie_op_blad(pdf: "_Blad", titel: str, kolommen: list, rijen: list,
                    y: float, vet: tuple = ("#", "Punten")) -> float:
    """Eén tabel met een kop erboven, doorlopend vanaf `y`.

    Anders dan `_tabel_op_blad` begint dit niet aan een nieuwe pagina: bij
    "alle weeklijsten" met het binnenkomers-filter houdt elke lijst maar een
    handvol regels over, en dan is een pagina per lijst verspilling. Er komt
    alleen een nieuwe pagina als de kop met de eerste regels er niet meer op
    zou passen.
    """
    kolommen = _pas_nummerkolom(kolommen, len(rijen))
    breed = sum(k[1] for k in kolommen)

    # Een kop onderaan de pagina met de tabel op de volgende is lelijk; eis
    # daarom ruimte voor de kop, de kolomnamen en drie regels. En past de
    # hele sectie op een verse pagina, dan hem daar in zijn geheel zetten in
    # plaats van na twee regels afbreken.
    heel = SECTIEKOP + 6.8 + len(rijen) * SECTIEREGEL
    past_vers = BOVENGRENS + heel <= ONDERGRENS
    if (y + SECTIEKOP + 6.8 + 3 * SECTIEREGEL > ONDERGRENS
            or (past_vers and y + heel > ONDERGRENS)):
        pdf.add_page()
        y = BOVENGRENS

    pdf.set_font("dejavu", "B", 12)
    pdf.set_text_color(*(round(k * 0.55) for k in ACCENT))
    pdf.set_xy(KANTLIJN, y)
    pdf.cell(breed, 6, titel)
    pdf.set_text_color(0, 0, 0)
    y += SECTIEKOP
    y = _kolomkop(pdf, kolommen, y, breed)

    for rij in rijen:
        if y + SECTIEREGEL > ONDERGRENS:
            pdf.add_page()
            y = BOVENGRENS
            # Op een vervolgpagina de kolomnamen herhalen, met de lijstnaam
            # erbij -- anders sta je te raden bij welke lijst je kijkt.
            pdf.set_font("dejavu", "", 8.5)
            pdf.set_text_color(*GRIJS)
            pdf.set_xy(KANTLIJN, y)
            pdf.cell(breed, 5, f"{titel} (vervolg)")
            pdf.set_text_color(0, 0, 0)
            y += 7
            y = _kolomkop(pdf, kolommen, y, breed)
        pdf.set_draw_color(*LIJN)
        pdf.line(KANTLIJN, y + SECTIEREGEL - 0.6,
                 KANTLIJN + breed, y + SECTIEREGEL - 0.6)
        x = KANTLIJN
        for (kop, kolbreed, uitlijning), waarde in zip(kolommen, rij):
            pdf.set_font("dejavu", "B" if kop in vet else "", 8)
            pdf.set_xy(x, y)
            tekst = "" if waarde is None else str(waarde)
            pdf.cell(kolbreed, SECTIEREGEL - 0.6,
                     _kort(pdf, tekst, kolbreed - 2), align=uitlijning)
            x += kolbreed
        y += SECTIEREGEL
    return y + 5          # witruimte voor de volgende sectie


def bouw_week_alle(con: sqlite3.Connection, jaar: int, week: int,
                   alleen: Optional[set] = None,
                   binnenkomers: bool = False) -> Optional[bytes]:
    """Alle weeklijsten van één week in één PDF, elke lijst een eigen deel.

    Niet samengevoegd tot één tabel: elke lijst heeft zijn eigen nummer 1,
    en die naast elkaar zetten zou een rangorde suggereren die er niet is.
    De banner draagt per deel de naam van de lijst, zodat je op elke pagina
    ziet waar je in zit.
    """
    from .config import is_jaarlijks

    weeklijsten = [k for k in LIJSTEN if not is_jaarlijks(k)]
    delen = []
    for welke in weeklijsten:
        rijen_db = list(con.execute(
            "SELECT positie, vorige_positie, artiest, titel, weken_genoteerd,"
            " site_status, sleutel FROM noteringen WHERE lijst=? AND jaar=?"
            " AND week=? ORDER BY positie", (welke, jaar, week)))
        if alleen is not None:
            rijen_db = [r for r in rijen_db if r["sleutel"] in alleen]
        if binnenkomers:
            rijen_db = [r for r in rijen_db if not r["vorige_positie"]
                        and r["site_status"] != "terug"]
        if rijen_db:
            delen.append((welke, rijen_db))
    if not delen:
        return None

    kolommen = [("Positie", 15, "C"), ("Vorige", 15, "C"),
                ("Artiest", 63, "L"), ("Titel", 78, "L"), ("Weken", 15, "C")]
    totaal = sum(len(r) for _, r in delen)
    soort = "binnenkomers" if binnenkomers else "noteringen"
    pdf = _Blad("Weeklijsten", f"week {week}",
                f"{len(delen)} lijsten · {totaal} {soort} · {jaar}")
    pdf.alias_nb_pages()
    pdf.add_page()
    y = BOVENGRENS
    for welke, rijen_db in delen:
        rijen = []
        for r in rijen_db:
            vorige = r["vorige_positie"]
            if vorige is None:
                vorige = "terug" if r["site_status"] == "terug" else "nieuw"
            rijen.append([r["positie"], vorige, r["artiest"], r["titel"],
                          r["weken_genoteerd"]])
        naam = LIJSTEN.get(welke, {}).get("naam", welke)
        y = _sectie_op_blad(pdf, f"{naam} — {len(rijen)} {soort}",
                            kolommen, rijen, y, vet=("Positie",))
    return bytes(pdf.output())


def bouw_klassement(con: sqlite3.Connection, lijst: str, van: int,
                    tot: int, top: Optional[int] = None,
                    alleen: Optional[set] = None) -> Optional[bytes]:
    """Het puntenklassement over een reeks jaargangen (decennium of alles)."""
    from .db import totalen_over

    nummers = totalen_over(con, lijst, van, tot)
    if alleen is not None:
        nummers = [n for n in nummers if n["sleutel"] in alleen]
    if not nummers:
        return None
    if top:
        nummers = nummers[:top]

    kolommen = [("#", 9, "C"), ("Artiest", 48, "L"), ("Titel", 62, "L"),
                ("Punten", 16, "C"), ("Hoogste", 15, "C"), ("Weken", 13, "C"),
                ("Jaargangen", 23, "C")]
    rijen = []
    for nr, n in enumerate(nummers, start=1):
        jaren = n["jaren"]
        rijen.append([nr, n["artiest"], n["titel"], n["punten"], n["hoogste"],
                      n["weken"],
                      str(jaren[0]) if len(jaren) == 1
                      else f"{jaren[0]}-{jaren[-1]}"])

    naam = LIJSTEN.get(lijst, {}).get("naam", lijst)
    soort = f"Top {top} van het puntenklassement" if top else "Puntenklassement"
    return _tabel_pdf(naam, f"{van}-{tot}",
                      f"{soort} · {len(rijen)} nummers over "
                      f"{tot - van + 1} jaargangen", kolommen, rijen)


def bouw_jaarlijksen(con: sqlite3.Connection, top: Optional[int] = None,
                     alleen: Optional[set] = None) -> Optional[bytes]:
    """De gecombineerde lijst over alle jaarlijkse lijsten."""
    from .db import jaarlijkse_totalen

    nummers = jaarlijkse_totalen(con)
    if alleen is not None:
        nummers = [n for n in nummers if n["sleutel"] in alleen]
    if not nummers:
        return None
    if top:
        nummers = nummers[:top]

    kolommen = [("#", 10, "C"), ("Artiest", 46, "L"), ("Titel", 58, "L"),
                ("Punten", 14, "C"), ("Edities", 13, "C"), ("Lijsten", 12, "C"),
                ("Hoogste", 14, "C"), ("Hoogste in", 19, "L")]
    rijen = []
    for nr, n in enumerate(nummers, start=1):
        rijen.append([nr, n["artiest"], n["titel"], n["punten"], n["edities"],
                      n["lijsten"], n["hoogste"],
                      f"{n['hoogste_lijst']} {n['hoogste_jaar']}"])

    kop = f"top {top} van alle" if top else "alle"
    return _tabel_pdf("Jaarlijsten totaal", "alle lijsten",
                      f"De {kop} jaarlijkse lijsten samen, genormaliseerd · "
                      f"{len(rijen)} nummers", kolommen, rijen)


# --- op schijf bewaren ------------------------------------------------------
#
# De jaargangen 1965-2025 zijn afgesloten en veranderen niet meer, dus die
# hoeven maar één keer gebouwd te worden. Maar "veranderen niet meer" geldt voor
# de BRON, niet voor onze afgeleide cijfers: een nieuwe alias of een correctie
# verschuift de punten van een oude jaargang alsnog. Daarom bewaart dit deel de
# bestanden wel, maar controleert het bij elke download of ze nog kloppen.


def pad_van(lijst: str, jaar: int, map_: Optional[Path] = None) -> Path:
    """Waar het jaarbestand landt: naast de Excel van diezelfde jaargang."""
    bestand = LIJSTEN.get(lijst, {}).get("bestand", lijst)
    return (Path(map_) if map_ is not None else excel_map(jaar)) / f"{bestand}_{jaar}.pdf"


def is_actueel(con: sqlite3.Connection, pad: Path, lijst: str, jaar: int) -> bool:
    """Is het bewaarde bestand jonger dan de gegevens waar het uit komt?

    Twee dingen kunnen het verouderen: een week die opnieuw is opgehaald, en een
    handmatige wijziging (alias, uitzondering, correctie). Dat tweede stond
    vroeger in `wijzigingen` en gold voor alles tegelijk -- één alias maakte
    zeshonderd bestanden verdacht, en dat is een half uur bouwen voor drie
    jaargangen werk. Nu houdt `te_bouwen` per (lijst, jaargang) bij wat er
    aangeraakt is.
    """
    if not pad.exists():
        return False
    if con.execute("SELECT 1 FROM te_bouwen WHERE lijst=? AND jaar=?",
                   (lijst, jaar)).fetchone():
        return False
    gemaakt = datetime.fromtimestamp(pad.stat().st_mtime)
    for vraag, waarden in (
        ("SELECT MAX(opgehaald_op) FROM opgehaald WHERE lijst=? AND jaar=?",
         (lijst, jaar)),
    ):
        try:
            laatste = con.execute(vraag, waarden).fetchone()[0]
        except sqlite3.Error:
            return False
        if laatste and datetime.fromisoformat(laatste) > gemaakt:
            return False
    return True


def schrijf_jaaroverzicht(
    con: sqlite3.Connection, lijst: str, jaar: int,
    map_: Optional[Path] = None, *, altijd: bool = False,
) -> Optional[Path]:
    """Bouw het jaarbestand en zet het op schijf. None als er geen data is.

    Is het bestand er al en nog actueel, dan gebeurt er niets -- tenzij `altijd`.
    """
    pad = pad_van(lijst, jaar, map_)
    if not altijd and is_actueel(con, pad, lijst, jaar):
        return pad
    gegevens = bouw_jaaroverzicht(con, lijst, jaar)
    if gegevens is None:
        return None
    pad.parent.mkdir(parents=True, exist_ok=True)
    try:
        pad.write_bytes(gegevens)
    except PermissionError as fout:
        raise BestandInGebruik(
            f"Kan {pad} niet opslaan; staat hij nog open in een pdf-lezer?"
        ) from fout
    return pad
