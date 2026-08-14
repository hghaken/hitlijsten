"""De handleiding voor bezoekers, als PDF in de huisstijl van de site.

Zelfde banner, lettertype en voetregel als de jaaroverzichten, maar dan
lopende tekst: hoofdstukken, een klikbare inhoudsopgave en bladwijzers.
De inhoud is proza en verandert alleen als de site verandert, dus dit
bestand wordt met de hand gebouwd::

    python -m hitlijsten.handleiding

en het resultaat landt in ``web/static/handleiding.pdf`` (de menubalk linkt
ernaar, rechtsboven naast de disclaimer).

De tekst wordt twee keer gezet: de eerste ronde alleen om te weten op welke
pagina elk hoofdstuk valt, de tweede ronde met die paginanummers in de
inhoudsopgave. Dat is goedkoper dan het achteraf verschuiven van ankers.
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
VLAK = (243, 243, 250)          # lichte achtergrond voor tip-kaders

MAANDEN = ("januari", "februari", "maart", "april", "mei", "juni", "juli",
           "augustus", "september", "oktober", "november", "december")


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
    return uit


class _Boek(FPDF):
    """A4 met de sitebanner bovenaan; rechtsboven de naam van het hoofdstuk."""

    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.hoofdstuk = ""
        self.add_font("dejavu", "", LETTERTYPEN / "DejaVuSans.ttf")
        self.add_font("dejavu", "B", LETTERTYPEN / "DejaVuSans-Bold.ttf")
        self.set_title("Hitlijsten - handleiding voor bezoekers")
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
        self.cell(120, 5, "Handleiding voor bezoekers · hitlijsten.hhaken.nl")
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
        self.cell(90, 6, "hitlijsten.hhaken.nl · handleiding")
        self.set_xy(210 - KANTLIJN - 90, 286)
        self.cell(90, 6, f"pagina {self.page_no()} van {{nb}}", align="R")
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
    pdf.add_page()
    pdf.set_y(80)
    pdf.set_font("dejavu", "B", 34)
    pdf.cell(BREED, 16, "Hitlijsten", align="C")
    pdf.ln(18)
    pdf.set_font("dejavu", "", 13)
    pdf.set_text_color(*GRIJS)
    pdf.cell(BREED, 8, "Handleiding voor bezoekers", align="C")
    pdf.ln(9)
    pdf.set_text_color(*(round(c * 0.55) for c in ACCENT))
    pdf.set_font("dejavu", "B", 12)
    pdf.cell(BREED, 8, "hitlijsten.hhaken.nl", align="C")
    pdf.set_text_color(0, 0, 0)

    pdf.set_y(140)
    kaarten = [(c["lijsten"], "hitlijsten"), (c["noteringen"], "noteringen"),
               (f"{c['van']}–nu", "zes decennia"), ("gratis", "geen account")]
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
    pdf.cell(BREED, 10, "Inhoud")
    pdf.ln(14)
    for nr, titel, pagina in toc:
        link = links.setdefault(nr, pdf.add_link())
        y = pdf.get_y()
        pdf.set_font("dejavu", "B", 10.5)
        pdf.set_text_color(*(round(c * 0.55) for c in ACCENT))
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
    pdf.set_text_color(*(round(c * 0.55) for c in ACCENT))
    pdf.cell(12, 10, str(nr))
    pdf.set_text_color(0, 0, 0)
    pdf.cell(BREED - 12, 10, titel)
    pdf.ln(11)
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.6)
    pdf.line(KANTLIJN, pdf.get_y(), KANTLIJN + 40, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(5)


def bouw(versie: str | None = None) -> bytes:
    """Zet de handleiding; twee rondes voor de paginanummers in de inhoud."""
    c = _cijfers()
    versie = versie or c["versie"]
    toc_klaar: list = []
    for ronde in (1, 2):
        pdf = _Boek()
        pdf.alias_nb_pages()
        toc: list = []
        links: dict = {}

        _omslag(pdf, f"Versie {versie}", c)
        pdf.hoofdstuk = "Inhoud"
        _inhoudsopgave(pdf, toc_klaar or [], links)

        h = 0

        # -- 1 · Welkom ------------------------------------------------------
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
        pdf.p("Bovenaan elke pagina staan twee rijen. De **bovenste rij** "
              "bevat de lijstweergaven: Overzicht, Weeklijsten, "
              "Jaaroverzichten, Decennia, Top 40 totaal en Jaarlijsten "
              "totaal. De **tweede rij** bevat de specials: Zoeken, Jouw "
              "dag, Weekbericht, Wetenswaardigheden, Records, Versies, "
              "Vergelijk, VirtualDJ, het Gastenboek en — helemaal "
              "achteraan — een dobbelsteen: die opent een willekeurig "
              "nummer uit het archief.")
        pdf.tip("De site werkt net zo goed op je telefoon als op een groot "
                "scherm; op smalle schermen schuiven de menu's en tabellen "
                "vanzelf in een compactere vorm.")

        # -- 2 · De lijstpagina's -------------------------------------------
        h += 1
        _hoofdstuk(pdf, toc, links, h, "De lijstpagina's")
        pdf.kop2("Overzicht")
        pdf.p("De voorpagina toont de kerncijfers van het archief, de meest "
              "recente weeklijsten en een terugblik-blok: welke nummers "
              "stonden er vandaag 10, 25 of 40 jaar geleden op nummer 1?")
        pdf.kop2("Weeklijsten")
        pdf.p("Kies een lijst, jaargang en week en je ziet de lijst zoals "
              "hij is uitgezonden, met de uitzenddatum erbij: positie, "
              "vorige positie, artiest, titel en het aantal weken "
              "genoteerd. Nieuwe binnenkomers en terugkeerders krijgen een "
              "gekleurd speldje, en met de knoppen ‹ vorige en volgende › "
              "blader je week voor week door de kalender — ook over de "
              "jaargrens heen.")
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
              "langs de decennia.")
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

        # -- 3 · Kiezen, filteren en downloaden -----------------------------
        h += 1
        _hoofdstuk(pdf, toc, links, h, "Kiezen, filteren en downloaden")
        pdf.p("Op elke lijstpagina bepaal jij wat er op het scherm staat — "
              "en alles wat je downloadt volgt die keuze exact.")
        pdf.punten([
            "**Toon**: standaard zie je de top 100; de keuzelijst biedt "
            "ook 500, 1000, 2500 of de complete lijst. Korte lijsten "
            "(tot 250 nummers) tonen meteen alles.",
            "**Alleen Nederlandstalig**: het vinkje met het vlaggetje "
            "beperkt de lijst tot (vermoedelijk) Nederlandstalige "
            "nummers.",
            "**Alleen binnenkomers**: toont alleen nummers die in de "
            "gekozen jaargang voor het eerst in de lijst verschenen. Op "
            "een weeklijst betekent het vinkje de binnenkomers van die "
            "wéék — precies de rijen met het groene speldje.",
        ])
        pdf.p("Onder elke lijst staan downloadknoppen voor **Excel** en "
              "**PDF** (en, als je een VirtualDJ-database hebt geladen, "
              "**VDJ** — zie hoofdstuk 6). De download bevat precies de "
              "selectie die op je scherm staat; de bestandsnaam vertelt "
              "het na: een achtervoegsel als _top100, _NL of _nieuw.")
        pdf.tip("De PDF's zijn gemaakt om te printen: veertig regels per "
                "pagina, rustig zwart-op-wit, alleen de kop in kleur. "
                "Handig voor in de studio of op de vlooienmarkt.")

        # -- 4 · Zoeken en bladeren -----------------------------------------
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
                 "aandachtsplaat van de week."],
                ["Speldje „nieuw”", "Nieuwe binnenkomer in die "
                 "week."],
                ["Speldje „terug”", "Terugkeerder: stond eerder "
                 "in de lijst, viel eruit en kwam terug."],
                ["‹ en ›", "In jaaroverzichten: de notering begon vóór of "
                 "liep door ná de getoonde jaargang."],
            ])

        # -- 5 · De speciale pagina's ---------------------------------------
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
              "(weekbericht.rss) voor je feedlezer.")
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

        # -- 6 · VirtualDJ ---------------------------------------------------
        h += 1
        _hoofdstuk(pdf, toc, links, h, "VirtualDJ: van lijst naar playlist")
        pdf.p("Draai je met VirtualDJ? Dan kan de site elke lijst uit het "
              "archief omzetten in een **kant-en-klare playlist uit je "
              "eigen muziekbibliotheek**. Je laadt één keer je "
              "VirtualDJ-database; daarna staat er op elke lijstpagina een "
              "VDJ-knop die de getoonde selectie matcht tegen wat jij "
              "hebt, en het resultaat als .vdjfolder-bestand aanbiedt — "
              "plus een boodschappenlijst van wat je nog mist.")
        pdf.kop2("Stap 1 · maak een backup in VirtualDJ")
        pdf.p("Open VirtualDJ en kies **Instellingen → Backup**. Dat "
              "levert één zip-bestand op met daarin je complete database "
              "— óók de muziek op externe schijven die nu niet "
              "aangesloten zijn. Die zip is precies wat de site nodig "
              "heeft. Een kale database.xml uploaden mag ook (meerdere "
              "tegelijk zelfs), maar de backup-zip is kleiner en "
              "completer.")
        pdf.kop2("Stap 2 · laad hem op de VirtualDJ-pagina")
        pdf.p("Ga naar **VirtualDJ** in de menubalk, kies je zip en druk "
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
        pdf.kop2("Stap 3 · druk op de VDJ-knop")
        pdf.p("Zodra je database geladen is, verschijnt naast de Excel- en "
              "PDF-knop op **elke lijstpagina** — weeklijsten, "
              "jaaroverzichten, edities, decennia en de beide "
              "totaallijsten — een VDJ-knop. Die neemt exact de selectie "
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
        pdf.kop2("Stap 5 · gebruik hem in VirtualDJ")
        pdf.p("De downloadknop levert een .vdjfolder-bestand, genoemd "
              "naar de lijst en je selectie. Zet dat bestand in de map "
              "**MyLists** binnen je VirtualDJ-map (meestal "
              "Documenten\\VirtualDJ\\MyLists) en hij verschijnt in "
              "VirtualDJ als playlist, in lijstvolgorde.")
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
        pdf.kop2("Contact")
        pdf.p("Een fout gezien, een lijst die je mist, of gewoon een "
              "groet? Gebruik het feedbackformulier of het gastenboek — "
              "beide staan onderaan elke pagina. Veel plezier met het "
              "archief!")

        toc_klaar = toc

    return bytes(pdf.output())


def schrijf(pad: Path = DOEL) -> Path:
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_bytes(bouw())
    return pad


if __name__ == "__main__":
    print(schrijf())
