"""De handleiding voor bezoekers, als PDF in de huisstijl van de site.

Zelfde banner, lettertype en voetregel als de jaaroverzichten, maar dan
lopende tekst: hoofdstukken, een klikbare inhoudsopgave en bladwijzers.
Sinds de tweetalige site wordt hij in twee talen gebouwd:
``handleiding.pdf`` (Nederlands) en ``manual.pdf`` (Engels) — de
Handleiding-knop in de menubalk kiest het bestand dat bij de taalkeuze
past. De inhoud is proza en verandert alleen als de site verandert::

    python -m hitlijsten.handleiding

De tekst wordt per taal twee keer gezet: de eerste ronde alleen om te
weten op welke pagina elk hoofdstuk valt, de tweede ronde met die
paginanummers in de inhoudsopgave. Dat is goedkoper dan het achteraf
verschuiven van ankers.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from fpdf import FPDF

from .config import LIJSTEN, ROOT
from .pdf import (ACCENT, BANNER, BANNER_AFBEELDING, GRIJS, KANTLIJN,
                  LETTERTYPEN, LIJN)

__all__ = ["bouw", "schrijf"]

BREED = 210 - 2 * KANTLIJN
DOEL = ROOT / "hitlijsten" / "web" / "static" / "handleiding.pdf"
DOEL_EN = ROOT / "hitlijsten" / "web" / "static" / "manual.pdf"
VLAK = (243, 243, 250)          # lichte achtergrond voor tip-kaders

MAANDEN = ("januari", "februari", "maart", "april", "mei", "juni", "juli",
           "augustus", "september", "oktober", "november", "december")
MAANDEN_EN = ("January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November",
              "December")


def _cijfers() -> dict:
    """De paar getallen in de tekst, vers uit de database.

    De vrijdagrun herbouwt de handleiding; zo lopen de teller op de omslag
    en de versiemaand vanzelf mee. Zonder database (bijvoorbeeld op de
    ontwikkelmachine) vallen de laatst bekende aantallen in.
    """
    uit = {"noteringen": "539.163", "lijsten": str(len(LIJSTEN)),
           "jaarlijks": str(len(LIJSTEN) - 4), "van": "1965"}
    try:
        from .db import verbinding
        with verbinding() as con:
            aantal = con.execute(
                "SELECT COUNT(*) FROM noteringen").fetchone()[0]
            van = con.execute("SELECT MIN(jaar) FROM noteringen").fetchone()[0]
        if aantal:
            uit["noteringen"] = f"{aantal:,}".replace(",", ".")
        if van:
            uit["van"] = str(van)
    except Exception:
        pass
    vandaag = date.today()
    uit["versie"] = f"{MAANDEN[vandaag.month - 1]} {vandaag.year}"
    uit["versie_en"] = f"{MAANDEN_EN[vandaag.month - 1]} {vandaag.year}"
    return uit


class _Boek(FPDF):
    """A4 met de sitebanner bovenaan; rechtsboven de naam van het hoofdstuk."""

    def __init__(self, taal: str = "nl") -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.taal = taal
        self.hoofdstuk = ""
        self.add_font("dejavu", "", LETTERTYPEN / "DejaVuSans.ttf")
        self.add_font("dejavu", "B", LETTERTYPEN / "DejaVuSans-Bold.ttf")
        self.set_title("Hitlijsten - visitor manual" if taal == "en"
                       else "Hitlijsten - handleiding voor bezoekers")
        self.set_creator("hitlijsten.hhaken.nl")
        self.set_margins(KANTLIJN, BANNER + 10, KANTLIJN)
        self.set_auto_page_break(True, margin=16)

    def header(self) -> None:
        if BANNER_AFBEELDING.exists():
            self.image(str(BANNER_AFBEELDING), 0, 0, 210, BANNER)
        else:
            self.set_fill_color(*ACCENT)
            self.rect(0, 0, 210, BANNER, "F")
        self.set_text_color(255, 255, 255)
        self.set_font("dejavu", "B", 16)
        self.set_xy(KANTLIJN, BANNER / 2 - 7.5)
        self.cell(120, 8, "Hitlijsten")
        self.set_font("dejavu", "", 8.5)
        self.set_xy(KANTLIJN, BANNER / 2 + 1)
        self.cell(120, 5, "Visitor manual · hitlijsten.hhaken.nl"
                  if self.taal == "en"
                  else "Handleiding voor bezoekers · hitlijsten.hhaken.nl")
        if self.hoofdstuk:
            self.set_font("dejavu", "B", 10)
            self.set_xy(105, BANNER / 2 - 3)
            self.cell(210 - 105 - KANTLIJN, 6, self.hoofdstuk, align="R")
        self.set_text_color(0, 0, 0)
        self.set_y(BANNER + 10)

    def footer(self) -> None:
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.6)
        self.line(KANTLIJN, 284, 210 - KANTLIJN, 284)
        self.set_line_width(0.2)
        self.set_text_color(*GRIJS)
        self.set_font("dejavu", "", 7.5)
        self.set_xy(KANTLIJN, 286)
        self.cell(90, 6, "hitlijsten.hhaken.nl · manual"
                  if self.taal == "en" else
                  "hitlijsten.hhaken.nl · handleiding")
        self.set_xy(210 - KANTLIJN - 90, 286)
        self.cell(90, 6, (f"page {self.page_no()} of {{nb}}"
                          if self.taal == "en"
                          else f"pagina {self.page_no()} van {{nb}}"),
                  align="R")
        self.set_text_color(0, 0, 0)

    # -- bouwstenen voor lopende tekst --------------------------------------

    def _ruimte(self, nodig: float) -> None:
        """Begin een nieuwe pagina als er minder dan `nodig` mm over is."""
        if self.get_y() + nodig > 284 - 16:
            self.add_page()

    def kop2(self, tekst: str) -> None:
        self._ruimte(18)
        self.ln(3)
        self.set_font("dejavu", "B", 11.5)
        self.set_text_color(*(round(c * 0.55) for c in ACCENT))
        self.multi_cell(BREED, 6, tekst)
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def p(self, tekst: str) -> None:
        self.set_font("dejavu", "", 9.5)
        self.multi_cell(BREED, 5.1, tekst, markdown=True)
        self.ln(1.6)

    def punten(self, regels: list) -> None:
        self.set_font("dejavu", "", 9.5)
        for regel in regels:
            self._ruimte(12)
            y = self.get_y()
            self.set_xy(KANTLIJN + 2, y)
            self.set_text_color(*ACCENT)
            self.cell(5, 5.1, "–")
            self.set_text_color(0, 0, 0)
            self.set_xy(KANTLIJN + 7, y)
            self.multi_cell(BREED - 7, 5.1, regel, markdown=True)
            self.ln(0.6)
        self.ln(1.2)

    def tip(self, tekst: str, kop: str = "Tip") -> None:
        self.set_font("dejavu", "", 9)
        regels = self.multi_cell(BREED - 12, 4.9, tekst, markdown=True,
                                 dry_run=True, output="LINES")
        hoogte = len(regels) * 4.9 + 9
        self._ruimte(hoogte + 4)
        y = self.get_y()
        self.set_fill_color(*VLAK)
        self.rect(KANTLIJN, y, BREED, hoogte, "F")
        self.set_fill_color(*ACCENT)
        self.rect(KANTLIJN, y, 1.4, hoogte, "F")
        self.set_xy(KANTLIJN + 5, y + 2.2)
        self.set_font("dejavu", "B", 8)
        self.set_text_color(*(round(c * 0.55) for c in ACCENT))
        self.cell(40, 4, kop.upper())
        self.set_text_color(0, 0, 0)
        self.set_xy(KANTLIJN + 5, y + 6.6)
        self.set_font("dejavu", "", 9)
        self.multi_cell(BREED - 12, 4.9, tekst, markdown=True)
        self.set_y(y + hoogte + 3)

    def tabel(self, kolommen: list, rijen: list) -> None:
        """Kleine tabel: kolommen = (kop, mm, uitlijning), cellen mogen
        omlopen."""
        self._ruimte(20)
        y = self.get_y()
        self.set_font("dejavu", "B", 7.5)
        self.set_text_color(*GRIJS)
        x = KANTLIJN
        for kop, breedte, uitlijning in kolommen:
            self.set_xy(x, y)
            self.cell(breedte, 5, kop.upper(), align=uitlijning)
            x += breedte
        self.set_text_color(0, 0, 0)
        breed = sum(k[1] for k in kolommen)
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.5)
        self.line(KANTLIJN, y + 5.3, KANTLIJN + breed, y + 5.3)
        self.set_line_width(0.2)
        y += 6.6

        for rij in rijen:
            self.set_font("dejavu", "", 8.5)
            hoogte = max(
                len(self.multi_cell(breedte - 3, 4.4, str(waarde),
                                    dry_run=True, output="LINES")) * 4.4
                for (kop, breedte, uitlijning), waarde in zip(kolommen, rij))
            if y + hoogte + 2 > 284 - 16:
                self.add_page()
                y = self.get_y()
            x = KANTLIJN
            for (kop, breedte, uitlijning), waarde in zip(kolommen, rij):
                self.set_font("dejavu",
                              "B" if kop == kolommen[0][0] else "", 8.5)
                self.set_xy(x, y)
                self.multi_cell(breedte - 3, 4.4, str(waarde),
                                align=uitlijning)
                x += breedte
            self.set_draw_color(*LIJN)
            self.line(KANTLIJN, y + hoogte + 1, KANTLIJN + breed,
                      y + hoogte + 1)
            y += hoogte + 2.4
            self.set_y(y)
        self.ln(2.5)


def _omslag(pdf: _Boek, versie: str, c: dict) -> None:
    en = pdf.taal == "en"
    pdf.add_page()
    pdf.set_y(80)
    pdf.set_font("dejavu", "B", 34)
    pdf.cell(BREED, 16, "Hitlijsten", align="C")
    pdf.ln(18)
    pdf.set_font("dejavu", "", 13)
    pdf.set_text_color(*GRIJS)
    pdf.cell(BREED, 8, "Visitor manual" if en
             else "Handleiding voor bezoekers", align="C")
    pdf.ln(9)
    pdf.set_text_color(*(round(k * 0.55) for k in ACCENT))
    pdf.set_font("dejavu", "B", 12)
    pdf.cell(BREED, 8, "hitlijsten.hhaken.nl", align="C")
    pdf.set_text_color(0, 0, 0)

    pdf.set_y(140)
    if en:
        kaarten = [(c["lijsten"], "charts"), (c["noteringen"], "entries"),
                   (f"{c['van']}–now", "six decades"),
                   ("free", "no account")]
    else:
        kaarten = [(c["lijsten"], "hitlijsten"),
                   (c["noteringen"], "noteringen"),
                   (f"{c['van']}–nu", "zes decennia"),
                   ("gratis", "geen account")]
    kaartbreed = (BREED - 3 * 6) / 4
    x = KANTLIJN
    for cijfer, naam in kaarten:
        pdf.set_fill_color(*VLAK)
        pdf.rect(x, 140, kaartbreed, 24, "F")
        pdf.set_fill_color(*ACCENT)
        pdf.rect(x, 140, kaartbreed, 0.9, "F")
        pdf.set_font("dejavu", "B", 14)
        pdf.set_xy(x, 145)
        pdf.cell(kaartbreed, 8, cijfer, align="C")
        pdf.set_font("dejavu", "", 8)
        pdf.set_text_color(*GRIJS)
        pdf.set_xy(x, 154)
        pdf.cell(kaartbreed, 5, naam, align="C")
        pdf.set_text_color(0, 0, 0)
        x += kaartbreed + 6

    pdf.set_y(250)
    pdf.set_font("dejavu", "", 9)
    pdf.set_text_color(*GRIJS)
    pdf.cell(BREED, 5, versie, align="C")
    pdf.set_text_color(0, 0, 0)


def _inhoudsopgave(pdf: _Boek, toc: list, links: dict) -> None:
    pdf.add_page()
    pdf.set_font("dejavu", "B", 16)
    pdf.cell(BREED, 10, "Contents" if pdf.taal == "en" else "Inhoud")
    pdf.ln(14)
    for nr, titel, pagina in toc:
        link = links.setdefault(nr, pdf.add_link())
        y = pdf.get_y()
        pdf.set_font("dejavu", "B", 10.5)
        pdf.set_text_color(*(round(k * 0.55) for k in ACCENT))
        pdf.set_xy(KANTLIJN, y)
        pdf.cell(10, 7, str(nr), link=link)
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(KANTLIJN + 10, y)
        pdf.cell(140, 7, titel, link=link)
        pdf.set_font("dejavu", "", 10.5)
        pdf.set_xy(210 - KANTLIJN - 20, y)
        pdf.cell(20, 7, str(pagina) if pagina else "", align="R", link=link)
        pdf.set_draw_color(*LIJN)
        pdf.line(KANTLIJN, y + 7.6, 210 - KANTLIJN, y + 7.6)
        pdf.ln(9)


def _hoofdstuk(pdf: _Boek, toc: list, links: dict, nr: int,
               titel: str) -> None:
    pdf.hoofdstuk = f"{nr}. {titel}"
    pdf.add_page()
    toc.append((nr, titel, pdf.page_no()))
    if nr in links:
        pdf.set_link(links[nr])
    pdf.start_section(f"{nr}. {titel}")
    pdf.set_font("dejavu", "B", 17)
    pdf.set_text_color(*(round(k * 0.55) for k in ACCENT))
    pdf.cell(12, 10, str(nr))
    pdf.set_text_color(0, 0, 0)
    pdf.cell(BREED - 12, 10, titel)
    pdf.ln(11)
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.6)
    pdf.line(KANTLIJN, pdf.get_y(), KANTLIJN + 40, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(5)


def _hoofdstukken_nl(pdf: _Boek, toc: list, links: dict, c: dict) -> None:
    h = 0

    # -- 1 · Welkom ---------------------------------------------------------
    h += 1
    _hoofdstuk(pdf, toc, links, h, "Welkom")
    pdf.p("hitlijsten.hhaken.nl is een doorzoekbaar archief van "
          f"Nederlandse hitlijsten: **{c['noteringen']} noteringen** "
          f"uit **{c['lijsten']} lijsten**, van de allereerste Top 40 "
          f"uit {c['van']} tot de lijst van afgelopen vrijdag. De site "
          "is gratis, kent geen accounts en toont geen advertenties.")
    pdf.p("Er zijn twee soorten lijsten. De **vier weeklijsten** — "
          "Nederlandse Top 40, Tipparade, Oranje Top 30 en Sterren NL "
          "Top 25 — worden elke vrijdagavond automatisch bijgewerkt. "
          f"Daarnaast staan er **{c['jaarlijks']} jaarlijkse lijsten** "
          "in het archief, van de Top 2000 tot de Zomer Top 500: "
          "lijsten die radiozenders één keer per jaar uitzenden.")
    pdf.kop2("De menubalk")
    pdf.p("Bovenaan elke pagina staan drie rijen. De **bovenste rij** "
          "bevat de lijstweergaven: Overzicht, Weeklijsten, "
          "Jaaroverzichten, Decennia, Top 40 totaal en Jaarlijsten "
          "totaal. De **tweede rij** bevat de specials: Zoeken, Jouw "
          "dag, Weekbericht, Wetenswaardigheden, Records, Versies, "
          "Vergelijk, VirtualDJ, het Gastenboek, Feedback en — "
          "helemaal achteraan — een dobbelsteen: die opent een "
          "willekeurig nummer uit het archief. **Feedback** neemt de "
          "pagina mee waar je vandaan komt, dus meld een fout het "
          "liefst vanaf de pagina waar je hem ziet. De **derde rij** is "
          "de titel van de pagina waar je bent, met een regel uitleg. "
          "Rechtsboven wissel je met de NL/EN-knop tussen Nederlands "
          "en Engels.")
    pdf.p("Die hele balk blijft staan als je scrolt, en de kolomkoppen "
          "van een lijst blijven er net onder hangen. Bij een lange "
          "lijst weet je zo halverwege nog welke lijst je bekijkt en "
          "welke kolom welke is. Op een klein scherm gebeurt dat niet: "
          "daar zou een vaste balk te veel van het beeld opeten.")
    pdf.tip("De site werkt net zo goed op je telefoon als op een groot "
            "scherm; op smalle schermen schuiven de menu's en tabellen "
            "vanzelf in een compactere vorm.")

    # -- 2 · De lijstpagina's -----------------------------------------------
    h += 1
    _hoofdstuk(pdf, toc, links, h, "De lijstpagina's")
    pdf.kop2("Overzicht")
    pdf.p("De voorpagina toont de kerncijfers van het archief, de meest "
          "recente weeklijsten en een terugblik-blok: welke nummers "
          "stonden er vandaag 10, 25 of 40 jaar geleden op nummer 1? In "
          "de twee tabellen zijn de lijstnamen en de zenders "
          "aanklikbaar: die brengen je naar de bronsite of de zender "
          "zelf. Onderaan deze pagina — en alleen hier — staat de "
          "bronvermelding, met daarboven het Facebook-teken.")
    pdf.kop2("Weeklijsten")
    pdf.p("Kies een lijst, jaargang en week en je ziet de lijst zoals "
          "hij is uitgezonden, met de uitzenddatum erbij: positie, "
          "vorige positie, artiest, titel en het aantal weken "
          "genoteerd. Nieuwe binnenkomers en terugkeerders krijgen een "
          "gekleurd speldje, en met de knoppen ‹ vorige en volgende › "
          "blader je week voor week door de kalender — ook over de "
          "jaargrens heen. Onderaan de lijstkeuze staat **Alle "
          "weeklijsten**: dan zie je de vier lijsten van diezelfde week "
          "onder elkaar, elk met een eigen kop en eigen posities.")
    pdf.kop2("Jaaroverzichten")
    pdf.p("Per lijst en jaargang bouwt de site een **puntenklassement** "
          "uit alle weeknoteringen van dat jaar: hoe hoger en hoe "
          "langer een nummer genoteerd stond, hoe meer punten. Zo zie "
          "je in één tabel wat er dat jaar écht toe deed — inclusief "
          "hoogste positie, aantal weken en de periode van binnenkomst "
          "tot laatste notering. Van de jaarlijkse lijsten (Top 2000 "
          "en dergelijke) staat elke **editie** er precies zoals "
          "uitgezonden. Ook hier bladeren de knoppen ‹ vorige en "
          "volgende › langs de jaargangen, en op de Decennia-pagina "
          "langs de decennia. In de lijstkeuze staan de jaarlijkse "
          "lijsten per zender gegroepeerd, van Arrow tot Veronica.")
    pdf.kop2("Decennia en Top 40 totaal")
    pdf.p("Hetzelfde puntenklassement, maar dan over tien jaargangen "
          "(de jaren 60 tot en met nu) of over de **volledige Top "
          "40-geschiedenis** vanaf 1965 in één lijst.")
    pdf.kop2("Jaarlijsten totaal")
    pdf.p(f"Alle {c['jaarlijks']} jaarlijkse lijsten samengevoegd "
          "tot één "
          "klassement. Omdat een 15e plek in een Top 500 iets anders "
          "waard is dan een 15e plek in een Top 2000, worden de "
          "posities **genormaliseerd** naar de lengte van de lijst; "
          "daarna telt alles eerlijk op. De Top 40-cijfers blijven "
          "hier bewust buiten: weeklijsten en jaarlijsten meten "
          "verschillende dingen.")

    # -- 3 · Kiezen, filteren en downloaden ---------------------------------
    h += 1
    _hoofdstuk(pdf, toc, links, h, "Kiezen, filteren en downloaden")
    pdf.p("Op elke lijstpagina bepaal jij wat er op het scherm staat — "
          "en alles wat je downloadt volgt die keuze exact.")
    pdf.punten([
        "**Toon**: standaard zie je de top 100; de keuzelijst biedt "
        "ook 500, 1000, 2500 of de complete lijst — alleen de keuzes "
        "die bij de lengte van de lijst passen. Korte lijsten (tot "
        "250 nummers) tonen meteen alles.",
        "**Alleen Nederlandstalig**: het vinkje met het vlaggetje "
        "beperkt de lijst tot (vermoedelijk) Nederlandstalige "
        "nummers.",
        "**Alleen binnenkomers**: toont alleen nummers die in de "
        "gekozen jaargang voor het eerst in de lijst verschenen. Op "
        "een weeklijst betekent het vinkje de binnenkomers van die "
        "wéék — precies de rijen met het groene speldje.",
    ])
    pdf.p("Onder elke lijst staan downloadknoppen voor **Excel** en "
          "**PDF** (en, als je een DJ-database hebt geladen, "
          "**DJ Export** — zie hoofdstuk 6). De download bevat precies "
          "de selectie die op je scherm staat; de bestandsnaam vertelt "
          "het na met een achtervoegsel als _top100, _NL of _nieuw, en "
          "staat er een filter aan, dan zegt het bestand dat ook zelf — "
          "in de PDF onder de kop, in Excel boven de tabel. Een "
          "doorgestuurd of uitgeprint blad draagt zijn bestandsnaam "
          "immers niet meer.")
    pdf.p("Koos je **Alle weeklijsten**, dan krijg je één werkboek met "
          "een tab per lijst en één PDF waarin de lijsten onder elkaar "
          "doorlopen.")
    pdf.tip("De PDF's zijn gemaakt om te printen: veertig regels per "
            "pagina, rustig zwart-op-wit, alleen de kop in kleur. "
            "Handig voor in de studio of op de vlooienmarkt.")

    # -- 4 · Zoeken en bladeren ---------------------------------------------
    h += 1
    _hoofdstuk(pdf, toc, links, h, "Zoeken en bladeren")
    pdf.kop2("Het zoekveld")
    pdf.p("Zoek op artiest, titel of allebei. Een paar handigheden:")
    pdf.punten([
        "**artiest | titel** — met een rechte streep zoek je "
        "gericht: links van de streep de artiest, rechts de titel. "
        "Bijvoorbeeld: abba | waterloo.",
        "**Jokers**: een sterretje (*) staat voor „maakt niet "
        "uit wat”. do*n zoeken vindt zowel Down als Doorgaan.",
        "Vind je niets, dan doet de site een suggestie waar je "
        "meteen op kunt klikken.",
    ])
    pdf.kop2("Nummerpagina's")
    pdf.p("Klik op een titel en je komt op de pagina van dat nummer: "
          "het complete chartverloop als grafiek, elke notering in "
          "elke lijst, en zoekknoppen naar YouTube en Spotify. Bestaan "
          "er meerdere versies van een titel, dan staan die er ook.")
    pdf.kop2("Artiestpagina's")
    pdf.p("Klik op een artiestnaam en je ziet de complete "
          "hitgeschiedenis van die artiest over alle lijsten heen — "
          "ruim 13.000 artiesten hebben zo'n eigen pagina.")
    pdf.kop2("Wat de symbolen betekenen")
    pdf.tabel(
        [("Symbool", 34, "L"), ("Betekenis", BREED - 34, "L")],
        [
            ["NL-vlaggetje", "(Vermoedelijk) Nederlandstalig nummer; "
             "op de nummerpagina kan dit per nummer gecorrigeerd zijn."],
            ["Belletje", "Alarmschijf: door de Top 40 uitgeroepen tot "
             "aandachtsplaat van de week. In de downloads heet dit een "
             "kolom (Excel) of een ster vóór de titel (PDF)."],
            ["Speldje „nieuw”", "Nieuwe binnenkomer in die "
             "week."],
            ["Speldje „terug”", "Terugkeerder: stond eerder "
             "in de lijst, viel eruit en kwam terug."],
            ["‹ en ›", "In jaaroverzichten: de notering begon vóór of "
             "liep door ná de getoonde jaargang."],
        ])

    # -- 5 · De speciale pagina's -------------------------------------------
    h += 1
    _hoofdstuk(pdf, toc, links, h, "De speciale pagina's")
    pdf.kop2("Jouw dag")
    pdf.p("Kies een datum — je verjaardag, je trouwdag — en zie welke "
          "lijst er die week gold, wat er op 1 stond en hoe de hele "
          "lijst eruitzag. Werkt voor elke datum vanaf 1965.")
    pdf.kop2("Weekbericht")
    pdf.p("Elke vrijdagavond, zodra de nieuwe lijsten binnen zijn, "
          "schrijft de site zelf een kort bericht: de nieuwe nummer 1, "
          "de hoogste binnenkomer, de grootste stijger en daler. Wil "
          "je het automatisch volgen, dan is er een **RSS-feed** "
          "(weekbericht.rss) voor je feedlezer — de feed-link op de "
          "pagina volgt je taalkeuze.")
    pdf.p("Onderaan die pagina staat **Ook deze week**: een kaartje per "
          "andere weeklijst — de Tipparade, de Oranje Top 30 en de "
          "Sterren NL Top 25 — met wie daar op 1 staat en hoeveel "
          "binnenkomers en terugkeerders er zijn. Lijsten die in die "
          "week nog niet bestonden blijven weg; bij een weekbericht "
          "uit 1972 zie je dus alleen de Tipparade.")
    pdf.kop2("Records")
    pdf.p("De klappers over het complete archief: meeste weken "
          "genoteerd, langste tijd op 1, grootste sprong en diepste "
          "val, langste terugkeer, eenhitwonders die meteen op 1 "
          "stonden, langste carrières en meer.")
    pdf.kop2("Versies")
    pdf.p("Dezelfde titel, andere uitvoering: deze pagina groepeert "
          "titelfamilies zodat je ziet wie een nummer allemaal in de "
          "lijsten bracht — en wiens versie het hoogst kwam.")
    pdf.kop2("Vergelijk")
    pdf.p("Zet twee jaargangen naast elkaar: aantal nummers, "
          "binnenkomers, taalverdeling en de toppers van beide jaren "
          "in één oogopslag.")
    pdf.kop2("Wetenswaardigheden")
    pdf.p("Een verzameling opvallende feiten uit het archief, per "
          "lijst en met het NL-filter te verfijnen.")
    pdf.kop2("Verras me (de dobbelsteen)")
    pdf.p("De dobbelsteen achteraan de menubalk opent een willekeurig "
          f"nummer uit de {c['noteringen']} noteringen — met zijn "
          "complete "
          "chartverloop erbij. Elke worp iets anders: van een "
          "vergeten tipparadeplaatje uit 1971 tot de hit van vorige "
          "maand. Leuk om te bladeren, en verslavender dan je denkt.")
    pdf.kop2("Gastenboek en feedback")
    pdf.p("Zie je iets dat niet klopt, of wil je gewoon iets kwijt? "
          "Onderaan elke pagina staan links naar het feedbackformulier "
          "en het gastenboek. Berichten komen eerst privé binnen; de "
          "beheerder publiceert wat in het gastenboek hoort.")

    # -- 6 · VirtualDJ ------------------------------------------------------
    h += 1
    _hoofdstuk(pdf, toc, links, h, "VirtualDJ: van lijst naar playlist")
    pdf.p("Draai je met VirtualDJ? Dan kan de site elke lijst uit het "
          "archief omzetten in een **kant-en-klare playlist uit je "
          "eigen muziekbibliotheek**. Je laadt één keer je "
          "VirtualDJ-database; daarna staat er op elke lijstpagina een "
          "DJ Export-knop die de getoonde selectie matcht tegen wat jij "
          "hebt, en het resultaat als .vdjfolder-bestand aanbiedt — "
          "plus een boodschappenlijst van wat je nog mist.")
    pdf.kop2("Stap 1 · maak een backup in VirtualDJ")
    pdf.p("Open VirtualDJ en kies **Instellingen → Backup**. Dat "
          "levert één zip-bestand op met daarin je complete database "
          "— óók de muziek op externe schijven die nu niet "
          "aangesloten zijn. Die zip is precies wat de site nodig "
          "heeft. Een kale database.xml uploaden mag ook (meerdere "
          "tegelijk zelfs), maar de backup-zip is kleiner en "
          "completer. Draai je **rekordbox** in plaats van VirtualDJ? "
          "Exporteer daar je collectie (Bestand → Collectie "
          "exporteren in xml-formaat) en upload dat bestand — de "
          "site herkent het vanzelf.")
    pdf.tip("Een upload mag hoogstens 256 MB zijn. Dat is ruim voor elke "
            "backup-zip (meestal een paar tientallen megabytes), maar een "
            "kale database.xml kan er overheen gaan — nog een reden om de "
            "zip te nemen.")
    pdf.kop2("Stap 2 · laad hem op de DJ Export-pagina")
    pdf.p("Ga naar **DJ Export** in de menubalk, kies je zip en druk "
          "op „Laad de database”. Drie keuzes bepalen wat er "
          "geladen wordt:")
    pdf.punten([
        "**Streaming-nummers meenemen**: VirtualDJ kent naast lokale "
        "bestanden ook streaming-verwijzingen (netsearch). Standaard "
        "blijven die buiten beschouwing; vink je ze aan, dan wint "
        "een lokaal bestand nog altijd van een streaming-versie.",
        "**Bestandssoort**: standaard telt alleen audio (mp3, flac "
        "en dergelijke) mee. Videobestanden winnen anders nogal "
        "eens op bestandsgrootte van de mp3 — een mp4 in je "
        "playlist terwijl je audio wilde. Draai je juist videosets, "
        "kies dan „alleen video” of „audio én "
        "video”.",
        "**Matching-strengheid**: hoe soepel de site jouw tags aan "
        "de lijsttitels mag koppelen — zie de tabel hieronder.",
    ])
    pdf.p("Tijdens het laden verschijnt een balk met een percentage. Een "
          "grote database duurt een seconde of tien; de balk laat zien "
          "hoever de server is, zodat je weet dat er nog gewerkt wordt.")
    pdf.tabel(
        [("Niveau", 30, "L"), ("Hoe streng", BREED - 30, "L")],
        [
            ["zeer strak", "Artiest en titel moeten (na normalisatie "
             "van hoofdletters, accenten en „feat.”-"
             "schrijfwijzen) exact overeenkomen."],
            ["strak", "Ook goed: verschillen tussen haakjes — "
             "(Radio Edit), (Live) — en duet-credits. Staat de lijst "
             "op „Meat Loaf & Ellen Foley” en jouw tag op "
             "„Meat Loaf”, dan is dat dezelfde plaat. Dit "
             "is de standaard."],
            ["soepel", "De titel moet kloppen, de artiestnaam mag "
             "ruwweg lijken (tikfouten, andere volgorde)."],
            ["zeer soepel", "Ook de titel mag nét afwijken. Deze "
             "treffers heten in het rapport „twijfel” — "
             "loop ze even na."],
        ])
    pdf.tip("Je database blijft alleen tijdens je bezoek in het "
            "werkgeheugen van de server (hooguit vier uur) en wordt "
            "**nooit op schijf bewaard**. Met de knop „vergeet "
            "mijn database” haal je hem er direct uit; opnieuw "
            "laden vervangt de vorige.", kop="Privacy")
    pdf.kop2("Stap 3 · druk op de DJ Export-knop")
    pdf.p("Zodra je database geladen is, verschijnt naast de Excel- en "
          "PDF-knop op **elke lijstpagina** — weeklijsten, "
          "jaaroverzichten, edities, decennia en de beide "
          "totaallijsten — een DJ Export-knop. Die neemt exact de selectie "
          "die op je scherm staat: kies je de top 100 met het "
          "NL-filter aan, dan wordt dát je playlist.")
    pdf.kop2("Stap 4 · het rapport")
    pdf.p("Je krijgt een rapportpagina met vier tellers: hoeveel "
          "nummers **gevonden** zijn in je bibliotheek, hoeveel er "
          "**ontbreken** (je boodschappenlijst), hoeveel "
          "**twijfelgevallen** er zijn en hoe groot je geladen "
          "bibliotheek is. Daaronder staat elke lijstregel met zijn "
          "status en het gevonden bestandspad. Bestaat een nummer "
          "meerdere keren in je bibliotheek, dan wint het lokale "
          "bestand met de hoogste bitrate.")
    pdf.p("Naast de playlist staat een knop die datzelfde rapport als "
          "**tekstbestand** (.txt) oplevert: dezelfde tabel in vaste "
          "kolommen, en onderaan nog eens los je boodschappenlijst — "
          "alleen wat je mist, met de volledige titel. Handig om uit te "
          "printen, mee te nemen naar de platenzaak of in een berichtje "
          "te plakken.")
    pdf.kop2("Stap 5 · gebruik hem in je DJ-software")
    pdf.p("De downloadknop past zich aan je bron aan, en het bestand "
          "is genoemd naar de lijst en je selectie. Laadde je een "
          "**VirtualDJ**-database, dan krijg je een "
          "**.vdjfolder**-bestand: zet het in de map **MyLists** "
          "binnen je VirtualDJ-map (meestal "
          "Documenten\\VirtualDJ\\MyLists) en hij verschijnt daar "
          "als playlist, in lijstvolgorde. Laadde je een "
          "**rekordbox**-collectie, dan krijg je een "
          "**.m3u8**-bestand: importeer dat in rekordbox — of in "
          "Engine DJ, Traktor, Serato en vrijwel elke mediaspeler. "
          "Wil je hem op **Pioneer- of Denon-apparatuur** (CDJ's, "
          "Prime-spelers), importeer de M3U8 dan in rekordbox "
          "respectievelijk Engine DJ en laat díe hem naar je "
          "USB-stick exporteren — de spelers lezen alleen hun eigen "
          "formaat.")
    pdf.tip("Staat je muziek op een externe schijf, sluit die dan aan "
            "voordat je de playlist draait: het .vdjfolder-bestand "
            "verwijst naar de bestandspaden zoals ze in je database "
            "staan.")

    # -- 7 · Privacy, bronnen en contact --------------------------------
    h += 1
    _hoofdstuk(pdf, toc, links, h, "Privacy, bronnen en contact")
    pdf.kop2("Privacy")
    pdf.p("De site kent geen accounts, geen advertenties en geen "
          "volg-cookies; er is alleen een functioneel sessiecookie. "
          "Een geladen VirtualDJ-database leeft uitsluitend in het "
          "werkgeheugen en verdwijnt vanzelf.")
    pdf.kop2("Bronnen")
    pdf.p("De weeklijsten worden samengesteld door top40.nl "
          "(Nederlandse Top 40, Tipparade, Sterren NL Top 25) en "
          "oranjetop30.nl; Alarmschijf-markeringen via top40.nl. De "
          "jaarlijkse lijsten worden samengesteld "
          "door de radiozenders en verzameld via datastats.nl. Deze "
          "site toont hun gegevens; de rechten liggen bij de "
          "samenstellers. Zie de disclaimer op de site voor het "
          "volledige verhaal.")
    pdf.kop2("De broncode")
    pdf.p("De site is met de hand gebouwd en de code is openbaar: "
          "**github.com/hghaken/hitlijsten**, onder de MIT-licentie. "
          "De gegevens niet — de noteringen blijven van de "
          "samenstellers hierboven; dit project verzamelt en toont hun "
          "werk, het claimt het niet.")
    pdf.p("Geschreven met hulp van **Claude Code** van Anthropic. Bij "
          "elke wijziging staat in het logboek van de code waarom hij "
          "zo gemaakt is en niet anders — ook de keuzes die achteraf "
          "verkeerd bleken.")

    pdf.kop2("Contact")
    pdf.p("Een fout gezien, een lijst die je mist, of gewoon een "
          "groet? Gebruik het feedbackformulier of het gastenboek — "
          "beide staan onderaan elke pagina.")
    pdf.p("De site staat ook op Facebook, als **Nederlandse "
          "Hitlijsten**. Daar verschijnt elke vrijdag automatisch het "
          "weekbericht: de nieuwe nummer 1, de binnenkomers en wat er "
          "in de andere lijsten gebeurde. Veel plezier met het "
          "archief!")


def _hoofdstukken_en(pdf: _Boek, toc: list, links: dict, c: dict) -> None:
    h = 0

    # -- 1 · Welcome --------------------------------------------------------
    h += 1
    _hoofdstuk(pdf, toc, links, h, "Welcome")
    pdf.p("hitlijsten.hhaken.nl is a searchable archive of Dutch music "
          f"charts: **{c['noteringen']} chart entries** from "
          f"**{c['lijsten']} charts**, from the very first Top 40 of "
          f"{c['van']} to last Friday's chart. The site is free, has no "
          "accounts and shows no advertising.")
    pdf.p("There are two kinds of charts. The **four weekly charts** — "
          "Dutch Top 40, Tipparade, Oranje Top 30 and Sterren NL "
          "Top 25 — are updated automatically every Friday evening. "
          f"Alongside them the archive holds **{c['jaarlijks']} annual "
          "charts**, from the Top 2000 to the Zomer Top 500: charts "
          "that Dutch radio stations broadcast once a year.")
    pdf.kop2("The menu bar")
    pdf.p("Every page has three menu rows. The **top row** holds the "
          "chart views: Overview, Weekly charts, Year charts, Decades, "
          "Top 40 all-time and Annual all-time. The **second row** "
          "holds the specials: Search, Your day, Week report, Fun "
          "facts, Records, Versions, Compare, DJ Export, the Guestbook, "
          "Feedback and — at the very end — a die that opens a random "
          "song from the archive. **Feedback** carries along the page "
          "you came from, so report a mistake from the page where you "
          "spot it. The **third row** is the title of the page you are "
          "on, with a line of explanation. At the top right, the NL/EN "
          "button switches between Dutch and English.")
    pdf.p("That whole bar stays put as you scroll, and a chart's column "
          "headings stay just below it. On a long chart you can still "
          "see which chart you are looking at and which column is "
          "which. Not on a small screen: there a fixed bar would eat "
          "too much of the view.")
    pdf.tip("The whole site is bilingual: the chart pages, the "
            "special pages and this manual all follow the NL/EN "
            "switch. Only the admin area is Dutch-only.")

    # -- 2 · The chart pages ------------------------------------------------
    h += 1
    _hoofdstuk(pdf, toc, links, h, "The chart pages")
    pdf.kop2("Overview")
    pdf.p("The front page shows the key figures of the archive, the "
          "most recent weekly charts and a look-back block: which songs "
          "were number 1 on this day 10, 25 or 40 years ago? In both "
          "tables the chart names and the stations are clickable: they "
          "take you to the source site or to the station itself. At the "
          "foot of this page — and only here — sits the source credit, "
          "with the Facebook mark above it.")
    pdf.kop2("Weekly charts")
    pdf.p("Pick a chart, a year and a week and you see the chart as it "
          "aired, with the broadcast date: position, previous position, "
          "artist, title and weeks on chart. New entries and returning "
          "songs get a coloured badge, and the ‹ previous and next › "
          "buttons page through the calendar week by week — across the "
          "year boundary too. At the bottom of the chart picker sits "
          "**All weekly charts**: that shows all four charts of the same "
          "week below each other, each with its own heading and its own "
          "positions.")
    pdf.kop2("Year charts")
    pdf.p("For every chart and year the site builds a **points "
          "ranking** from all weekly entries of that year: the higher "
          "and the longer a song charted, the more points. One table "
          "shows what really mattered that year — including peak "
          "position, weeks on chart and the run from first to last "
          "entry. For the annual charts (Top 2000 and the like) every "
          "**edition** is shown exactly as broadcast. Here too the "
          "‹ previous and next › buttons page through the years, and "
          "on the Decades page through the decades. In the chart "
          "picker the annual charts are grouped by station, from "
          "Arrow to Veronica.")
    pdf.kop2("Decades and Top 40 all-time")
    pdf.p("The same points ranking, but across ten years (the sixties "
          "up to now) or across the **complete Top 40 history** since "
          "1965 in one list.")
    pdf.kop2("Annual all-time")
    pdf.p(f"All {c['jaarlijks']} annual charts merged into one "
          "ranking. Because 15th place in a Top 500 is worth something "
          "different than 15th place in a Top 2000, positions are "
          "**normalised** to the length of the chart; after that "
          "everything adds up fairly. The Top 40 numbers deliberately "
          "stay out of this list: weekly and annual charts measure "
          "different things.")

    # -- 3 · Choosing, filtering and downloading ----------------------------
    h += 1
    _hoofdstuk(pdf, toc, links, h, "Choosing, filtering and downloading")
    pdf.p("On every chart page you decide what is on the screen — and "
          "everything you download follows that choice exactly.")
    pdf.punten([
        "**Show**: by default you see the top 100; the picker also "
        "offers 500, 1000, 2500 or the complete chart — only the "
        "choices that fit the chart's length. Short charts (up to "
        "250 songs) simply show everything.",
        "**Dutch-language only**: the checkbox with the little flag "
        "limits the chart to (presumably) Dutch-language songs.",
        "**New entries only**: shows only songs that entered this "
        "chart for the first time in the chosen year. On a weekly "
        "chart the checkbox means that wéék's new entries — exactly "
        "the rows with the green badge.",
    ])
    pdf.p("Below every chart are download buttons for **Excel** and "
          "**PDF** (and, with a DJ database loaded, **DJ Export** — "
          "see chapter 6). The download contains exactly the selection "
          "on your screen; the file name says so, with a suffix like "
          "_top100, _NL or _nieuw — and with a filter on, the file "
          "says so itself: under the heading in the PDF, above the "
          "table in Excel. A forwarded or printed sheet no longer "
          "carries its file name, after all.")
    pdf.p("If you picked **All weekly charts**, you get one workbook "
          "with a tab per chart and one PDF in which the charts follow "
          "each other continuously.")
    pdf.tip("The PDFs are made for printing: forty rows per page, "
            "calm black-on-white, only the header in colour. Handy "
            "for the studio or the record fair.")

    # -- 4 · Searching and browsing -----------------------------------------
    h += 1
    _hoofdstuk(pdf, toc, links, h, "Searching and browsing")
    pdf.kop2("The search box")
    pdf.p("Search by artist, title or both. A few tricks:")
    pdf.punten([
        "**artist | title** — a vertical bar searches precisely: "
        "artist left of the bar, title right of it. For example: "
        "abba | waterloo.",
        "**Wildcards**: an asterisk (*) means „anything "
        "goes”. Searching do*n finds both Down and Doorgaan.",
        "If nothing turns up, the site offers a clickable "
        "suggestion.",
    ])
    pdf.kop2("Song pages")
    pdf.p("Click a title and you land on that song's page: the "
          "complete chart run as a graph, every entry in every chart, "
          "and search buttons for YouTube and Spotify. If several "
          "versions of a title exist, they are listed too.")
    pdf.kop2("Artist pages")
    pdf.p("Click an artist name for that artist's complete chart "
          "history across all charts — over 13,000 artists have such "
          "a page.")
    pdf.kop2("What the symbols mean")
    pdf.tabel(
        [("Symbol", 34, "L"), ("Meaning", BREED - 34, "L")],
        [
            ["NL flag", "(Presumably) Dutch-language song; on the "
             "song page this can be corrected per song."],
            ["Bell", "Alarmschijf: named record of the week by the "
             "Top 40. In the downloads this becomes a column (Excel) or "
             "a star before the title (PDF)."],
            ["„new” badge", "New entry that week."],
            ["„back” badge", "Re-entry: charted before, "
             "dropped out and returned."],
            ["‹ and ›", "In year charts: the run started before or "
             "continued after the year shown."],
        ])

    # -- 5 · The special pages ----------------------------------------------
    h += 1
    _hoofdstuk(pdf, toc, links, h, "The special pages")
    pdf.kop2("Your day (Jouw dag)")
    pdf.p("Pick a date — your birthday, your wedding day — and see "
          "which chart was current that week, what was number 1 and "
          "what the whole chart looked like. Works for any date from "
          "1965 on.")
    pdf.kop2("Week report (Weekbericht)")
    pdf.p("Every Friday evening, as soon as the new charts are in, the "
          "site writes a short report of its own: the new number 1, "
          "the highest new entry, the biggest climber and faller. To "
          "follow it automatically there is an **RSS feed** "
          "(weekbericht.rss) for your feed reader — the feed link on "
          "the page follows your language choice, so you subscribe to "
          "the English edition.")
    pdf.p("At the foot of that page sits **Also this week**: one card "
          "per other weekly chart — the Tipparade, the Oranje Top 30 "
          "and the Sterren NL Top 25 — showing who is at number 1 "
          "there and how many new entries and re-entries there are. "
          "Charts that did not yet exist that week are left out, so a "
          "week report from 1972 shows only the Tipparade.")
    pdf.kop2("Records")
    pdf.p("The record books of the whole archive: most weeks on "
          "chart, longest run at number 1, biggest jump and deepest "
          "fall, longest re-entry gap, one-hit wonders that went "
          "straight to number 1, longest careers and more.")
    pdf.kop2("Versions (Versies)")
    pdf.p("Same title, different recording: this page groups title "
          "families so you can see who took a song into the charts — "
          "and whose version went highest.")
    pdf.kop2("Compare (Vergelijk)")
    pdf.p("Put two years side by side: number of songs, new entries, "
          "language split and the top songs of both years at a "
          "glance.")
    pdf.kop2("Fun facts (Wetenswaardigheden)")
    pdf.p("A collection of striking facts from the archive, per chart "
          "and refinable with the NL filter.")
    pdf.kop2("Surprise me (the die)")
    pdf.p("The die at the end of the menu bar opens a random song "
          f"from the {c['noteringen']} entries — complete with its "
          "chart run. Every roll is different: from a forgotten 1971 "
          "Tipparade record to last month's hit. Fun to browse, and "
          "more addictive than you'd think.")
    pdf.kop2("Guestbook and feedback")
    pdf.p("Spotted something wrong, or just want to say hello? The "
          "bottom of every page links to the feedback form and the "
          "guestbook. Messages arrive privately first; the site owner "
          "publishes what belongs in the guestbook.")

    # -- 6 · DJ Export ------------------------------------------------------
    h += 1
    _hoofdstuk(pdf, toc, links, h, "DJ Export: from chart to playlist")
    pdf.p("Do you DJ with VirtualDJ or rekordbox? Then the site can "
          "turn any chart in the archive into a **ready-made playlist "
          "from your own music library**. You load your database once; "
          "every chart page then gets a DJ Export button that matches "
          "the shown selection against what you own, and offers the "
          "result as a playlist file — plus a shopping list of what "
          "you are still missing.")
    pdf.kop2("Step 1 · make a backup in VirtualDJ")
    pdf.p("Open VirtualDJ and choose **Settings → Backup**. That "
          "produces a single zip with your complete database in it — "
          "including music on external drives that are not connected "
          "right now. That zip is exactly what the site needs. A bare "
          "database.xml works too (even several at once), but the "
          "backup zip is smaller and more complete. Running "
          "**rekordbox** instead? Export your collection there "
          "(File → Export collection in xml format) and upload that "
          "file — the site recognises it automatically.")
    pdf.tip("An upload may be 256 MB at most. That is ample for any backup "
            "zip (usually a few tens of megabytes), but a bare database.xml "
            "can exceed it — one more reason to use the zip.")
    pdf.kop2("Step 2 · load it on the DJ Export page")
    pdf.p("Go to **DJ Export** in the menu bar, pick your zip and "
          "press „Load the database”. Three choices control "
          "what gets loaded:")
    pdf.punten([
        "**Include streaming tracks**: besides local files VirtualDJ "
        "also knows streaming references (netsearch). By default "
        "they are left out; tick the box and a local file still "
        "beats a streaming version.",
        "**File type**: by default only audio (mp3, flac and the "
        "like) counts. Video files otherwise tend to win on file "
        "size — an mp4 in your playlist when you wanted audio. "
        "Playing video sets? Choose „video only” or "
        "„audio and video”.",
        "**Matching strictness**: how loosely the site may match "
        "your tags to the chart titles — see the table below.",
    ])
    pdf.p("While loading, a bar with a percentage appears. A large "
          "database takes ten seconds or so; the bar shows how far the "
          "server has got, so you know it is still working.")
    pdf.tabel(
        [("Level", 30, "L"), ("How strict", BREED - 30, "L")],
        [
            ["very strict", "Artist and title must match exactly "
             "(after normalising case, accents and "
             "„feat.” spellings)."],
            ["strict", "Also fine: differences in brackets — "
             "(Radio Edit), (Live) — and duet credits. If the chart "
             "says „Meat Loaf & Ellen Foley” and your tag "
             "says „Meat Loaf”, that is the same record. "
             "This is the default."],
            ["loose", "The title must match; the artist name may "
             "roughly resemble it (typos, different order)."],
            ["very loose", "The title may be slightly off too. These "
             "matches are labelled „doubtful” in the "
             "report — do check them."],
        ])
    pdf.tip("Your database only lives in the server's working memory "
            "during your visit (four hours at most) and is **never "
            "stored on disk**. The „forget my database” "
            "button removes it immediately; loading again replaces "
            "the previous one.", kop="Privacy")
    pdf.kop2("Step 3 · press the DJ Export button")
    pdf.p("Once your database is loaded, a DJ Export button appears "
          "next to the Excel and PDF buttons on **every chart page** — "
          "weekly charts, year charts, editions, decades and both "
          "all-time lists. It takes exactly the selection on your "
          "screen: pick the top 100 with the NL filter on, and thát "
          "becomes your playlist.")
    pdf.kop2("Step 4 · the report")
    pdf.p("You get a report page with four counters: how many songs "
          "were **found** in your library, how many are **missing** "
          "(your shopping list), how many are **doubtful** and how "
          "big your loaded library is. Below that, every chart row "
          "with its status and the file path found. If a song exists "
          "more than once in your library, the local file with the "
          "highest bitrate wins.")
    pdf.p("Next to the playlist there is a button that gives you that "
          "same report as a **text file** (.txt): the same table in "
          "fixed columns, and your shopping list again separately at "
          "the bottom — only what you are missing, with the full "
          "title. Handy to print, take to the record shop or paste "
          "into a message.")
    pdf.kop2("Step 5 · use it in your DJ software")
    pdf.p("The download button adapts to your source, and the file is "
          "named after the chart and your selection. If you loaded a "
          "**VirtualDJ** database you get a **.vdjfolder** file: put "
          "it in the **MyLists** folder inside your VirtualDJ folder "
          "(usually Documents\\VirtualDJ\\MyLists) and it appears "
          "there as a playlist, in chart order. If you loaded a "
          "**rekordbox** collection you get an **.m3u8** file: import "
          "it into rekordbox — or Engine DJ, Traktor, Serato and "
          "almost any media player. Want it on **Pioneer or Denon "
          "hardware** (CDJs, Prime players)? Import the M3U8 into "
          "rekordbox or Engine DJ respectively and let thát export it "
          "to your USB stick — the players only read their own "
          "format.")
    pdf.tip("If your music lives on an external drive, connect it "
            "before playing the playlist: the playlist file points at "
            "the file paths as they are in your database.")

    # -- 7 · Privacy, sources and contact -------------------------------
    h += 1
    _hoofdstuk(pdf, toc, links, h, "Privacy, sources and contact")
    pdf.kop2("Privacy")
    pdf.p("The site has no accounts, no advertising and no tracking "
          "cookies; there is only a functional session cookie (and a "
          "cookie remembering your language). A loaded DJ database "
          "lives exclusively in working memory and disappears by "
          "itself.")
    pdf.kop2("Sources")
    pdf.p("The weekly charts are compiled by top40.nl (Dutch Top 40, "
          "Tipparade, Sterren NL Top 25) and oranjetop30.nl; "
          "Alarmschijf markings via top40.nl. The annual charts are "
          "compiled by the radio stations and collected via "
          "datastats.nl. This site shows their data; the rights remain "
          "with the compilers. See the site's disclaimer for the full "
          "story.")
    pdf.kop2("The source code")
    pdf.p("The site was built by hand and the code is public: "
          "**github.com/hghaken/hitlijsten**, under the MIT licence. "
          "The data is not — the chart entries remain with the "
          "compilers named above; this project collects and shows "
          "their work, it does not claim it.")
    pdf.p("Written with the help of **Claude Code** by Anthropic. Every "
          "change carries a note in the code’s log explaining why it "
          "was made that way and not another — including the choices "
          "that turned out to be wrong.")

    pdf.kop2("Contact")
    pdf.p("Found a mistake, missing a chart, or just want to wave? "
          "Use the feedback form or the guestbook — both are linked "
          "at the bottom of every page.")
    pdf.p("The site is on Facebook too, as **Nederlandse Hitlijsten**. "
          "The week report appears there automatically every Friday: "
          "the new number 1, the new entries and what happened in the "
          "other charts. Enjoy the archive!")


def bouw(versie: str | None = None, taal: str = "nl") -> bytes:
    """Zet de handleiding; twee rondes voor de paginanummers in de inhoud."""
    c = _cijfers()
    if versie is None:
        versie = c["versie_en"] if taal == "en" else c["versie"]
    hoofdstukken = _hoofdstukken_en if taal == "en" else _hoofdstukken_nl
    etiket = "Version" if taal == "en" else "Versie"
    toc_klaar: list = []
    for ronde in (1, 2):
        pdf = _Boek(taal)
        pdf.alias_nb_pages()
        toc: list = []
        links: dict = {}

        _omslag(pdf, f"{etiket} {versie}", c)
        pdf.hoofdstuk = "Contents" if taal == "en" else "Inhoud"
        _inhoudsopgave(pdf, toc_klaar or [], links)
        hoofdstukken(pdf, toc, links, c)
        toc_klaar = toc

    return bytes(pdf.output())


def schrijf() -> str:
    """Bouw beide talen; de knop in de menubalk kiest het juiste bestand."""
    DOEL.parent.mkdir(parents=True, exist_ok=True)
    DOEL.write_bytes(bouw(taal="nl"))
    DOEL_EN.write_bytes(bouw(taal="en"))
    return f"{DOEL.name} + {DOEL_EN.name}"


if __name__ == "__main__":
    print(schrijf())
