"""Parser voor oranjetop30.nl (Oranje Top 30).

De pagina is server-rendered en heeft een keurige structuur; we parsen op die
structuur en niet op een platte tekstdump.

    <div id="list">
      <div class="entry" id="entry1">
        <div class="nummer dw">1</div>
        <div class="nummer dif">
            <img class="difLarge" src="/resources/dif/same.png"/>      (of up/down/new)
            <div>+ 4</div>                                             (alleen bij up/down)
        </div>
        <div class="info">
          <span class="titel">Cheerio<span><img .../></span></span>    (genest span = kroon-icoon)
          <span class="artiest">Justen de Wildt <span class="label">(cornelis music)</span></span>
          <span class="history">Aantal Weken: 20 Vorige week: 1</span>
        </div>
        <div class="profile">...</div>
      </div>
      ...

Belangrijk: het platenlabel staat in een eigen <span class="label"> BINNEN de
artiest-span. Titels met haakjes ("Er hangt iets in de lucht (Amore)") kunnen
dus nooit per ongeluk als label gelezen worden.

Binnenkomers hebben geen ontbrekende regel maar letterlijk "Vorige week: -".
De site gebruikt new.png zowel voor echte binnenkomers als voor re-entries;
"Aantal Weken" onderscheidt die twee (1 = nieuw, >1 = terug).
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import Notering, ParseFout

# icoon-bestandsnaam -> site_status (voor het geval er wel een vorige positie is)
_ICOON_STATUS = {
    "up": "stijger",
    "down": "daler",
    "same": "gelijk",
    "new": "nieuw",  # wordt hieronder omgezet als er tóch een vorige positie is
}

_WEKEN_RE = re.compile(r"Aantal\s*Weken\s*:\s*(\d+)", re.IGNORECASE)
_VORIGE_RE = re.compile(r"Vorige\s*week\s*:\s*(\d+)", re.IGNORECASE)


def _tekst(node) -> str:
    """Normaliseer whitespace (incl. &nbsp;) van een bs4-node."""
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True).replace("\xa0", " ")).strip()


def _icoon_naam(dif_div) -> str | None:
    """Geef 'up' / 'down' / 'same' / 'new' uit de <img src=.../dif/xxx.png>."""
    if dif_div is None:
        return None
    img = dif_div.find("img")
    if img is None or not img.get("src"):
        return None
    naam = img["src"].rsplit("/", 1)[-1]
    return naam.rsplit(".", 1)[0].lower() or None


def parse(html: str, lijst: str, jaar: int, week: int) -> list[Notering]:
    soup = BeautifulSoup(html, "lxml")

    lijst_div = soup.find(id="list")
    if lijst_div is None:
        raise ParseFout(
            f"{lijst} {jaar}-w{week}: geen <div id='list'> gevonden -- "
            "layout gewijzigd of pagina bestaat niet"
        )

    entries = lijst_div.find_all("div", class_="entry")
    if not entries:
        raise ParseFout(
            f"{lijst} {jaar}-w{week}: nul <div class='entry'> in de lijst gevonden"
        )

    noteringen: list[Notering] = []
    for index, entry in enumerate(entries, start=1):
        # --- positie -------------------------------------------------------
        pos_div = entry.select_one("div.nummer.dw")
        if pos_div is None:
            raise ParseFout(
                f"{lijst} {jaar}-w{week}: entry {index} heeft geen div.nummer.dw (positie)"
            )
        pos_tekst = _tekst(pos_div)
        if not pos_tekst.isdigit():
            raise ParseFout(
                f"{lijst} {jaar}-w{week}: entry {index} heeft geen numerieke positie "
                f"({pos_tekst!r})"
            )
        positie = int(pos_tekst)

        info = entry.find("div", class_="info")
        if info is None:
            raise ParseFout(
                f"{lijst} {jaar}-w{week}: positie {positie} heeft geen div.info"
            )

        # --- titel ---------------------------------------------------------
        titel_span = info.find("span", class_="titel")
        if titel_span is None:
            raise ParseFout(
                f"{lijst} {jaar}-w{week}: positie {positie} heeft geen span.titel"
            )
        titel_kopie = _kopie_zonder_geneste_spans(titel_span)
        titel = _tekst(titel_kopie)
        if not titel:
            raise ParseFout(f"{lijst} {jaar}-w{week}: positie {positie} heeft lege titel")

        # --- artiest + label -----------------------------------------------
        artiest_span = info.find("span", class_="artiest")
        if artiest_span is None:
            raise ParseFout(
                f"{lijst} {jaar}-w{week}: positie {positie} heeft geen span.artiest"
            )
        label = None
        label_span = artiest_span.find("span", class_="label")
        if label_span is not None:
            label = _haakjes_af(_tekst(label_span)) or None
        artiest = _tekst(_kopie_zonder_geneste_spans(artiest_span))
        if not artiest:
            raise ParseFout(
                f"{lijst} {jaar}-w{week}: positie {positie} heeft lege artiest"
            )

        # --- geschiedenis ---------------------------------------------------
        weken_genoteerd = None
        vorige_positie = None
        hist_span = info.find("span", class_="history")
        if hist_span is not None:
            hist = _tekst(hist_span)
            m = _WEKEN_RE.search(hist)
            if m:
                weken_genoteerd = int(m.group(1))
            m = _VORIGE_RE.search(hist)      # matcht bewust NIET op "Vorige week: -"
            if m:
                vorige_positie = int(m.group(1))

        # --- bewegingsaanduiding --------------------------------------------
        icoon = _icoon_naam(entry.select_one("div.nummer.dif"))
        site_status = _status(icoon, positie, vorige_positie, weken_genoteerd)

        noteringen.append(
            Notering(
                lijst=lijst,
                jaar=jaar,
                week=week,
                positie=positie,
                titel=titel,
                artiest=artiest,
                label=label,
                weken_genoteerd=weken_genoteerd,
                vorige_positie=vorige_positie,
                site_status=site_status,
            )
        )

    return noteringen


def _kopie_zonder_geneste_spans(span):
    """Kopieer een span en gooi geneste <span>-kinderen eruit.

    span.titel bevat soms een genest <span> met kroon-plaatjes, span.artiest
    bevat het label-span. Beide horen niet in de tekstwaarde thuis.
    """
    kopie = BeautifulSoup(str(span), "lxml").find("span")
    if kopie is None:  # zou niet moeten kunnen
        return span
    for kind in kopie.find_all("span"):
        kind.decompose()
    return kopie


def _haakjes_af(tekst: str) -> str:
    tekst = tekst.strip()
    if tekst.startswith("(") and tekst.endswith(")"):
        tekst = tekst[1:-1]
    return tekst.strip()


def _status(
    icoon: str | None,
    positie: int,
    vorige_positie: int | None,
    weken_genoteerd: int | None,
) -> str:
    """Leid site_status af. Nooit 'nieuw' als er een vorige positie is."""
    if vorige_positie is None:
        # Geen vorige notering: binnenkomer of re-entry. De site toont bij beide
        # new.png; het aantal weken maakt het onderscheid.
        if weken_genoteerd is not None and weken_genoteerd > 1:
            return "terug"
        return "nieuw"

    status = _ICOON_STATUS.get(icoon or "")
    if status == "nieuw":
        # Site zegt "nieuw" maar er is wél een vorige positie -> re-entry.
        return "terug"
    if status:
        return status

    # Geen bruikbaar icoon: val terug op het positieverschil.
    if vorige_positie == positie:
        return "gelijk"
    return "stijger" if vorige_positie > positie else "daler"
