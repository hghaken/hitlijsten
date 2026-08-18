"""Parser voor top40.nl: Top 40, Tipparade en Sterren NL Top 25.

BRONKEUZE
---------
De pagina bevat wel een <script type="application/ld+json">-blok, maar dat is
*niet* bruikbaar: het is enkel een schema.org WebSite-object met de zoekactie
van de site (@type: WebSite + SearchAction, ~290 tekens). De hitlijst zelf zit
er niet in. Er is ook geen ander JSON-blob met de lijst. De HTML-opmaak is dus
de enige bron.

Gelukkig is die opmaak strak en identiek voor alle drie de lijsten (zelfde
Twig-template, alleen een andere container-id). Geverifieerd op 12 pagina's
(3 lijsten x weken 1/12/22/30 van 2026): geen enkele afwijking.

STRUCTUUR VAN EEN REGEL
-----------------------
    <div class="top40-list__item [nr1|hitrecord|dot|super|new|no-longer-listed]">
      <div class="top40-list__item__container">
        <div class="top40-list__item__info">
          <div class="top40-list__item__info__position">
            <div class="number-block ...."><span class="h4">7</span></div>   <- HUIDIGE positie
          </div>
          <a ...><h2 class="h3">Titel</h2></a>                               <- titel
          <a ...><h3 class="p lead lowercase">Artiest</h3></a>               <- artiest
        </div>
        <div class="top40-list__item__controls">
          <div class="top40-list__item__controls--rank"> ... </div>          <- vorige positie + richting
          <div class="top40-list__item__controls--weeks">
            <span class="h5">13</span><span class="h5">weken</span>          <- weken genoteerd
          </div>
        </div>
      </div>
    </div>

De klasse `lowercase` op de artiest is puur CSS (text-transform); de tekst in
de HTML heeft gewoon de juiste hoofdletters. Niets terugvertalen dus.

AFGEKAPTE ARTIESTNAMEN (belangrijk!)
------------------------------------
De zichtbare <h2>/<h3> worden door de site server-side afgekapt op ~46 tekens,
met ".." als staart:

    <h3 ...>Afro Bros x Billy Dans x Brace x Jeffrey Hees..</h3>

De volledige naam staat wel in het aria-label van de omliggende <a> (en in
alt/title van de <img>):

    aria-label="nummer Afro Bros x Billy Dans x Brace x Jeffrey Heesen - Meisje"

In de 12 onderzochte pagina's overkomt dit 7 van de 475 regels (1,5%), altijd
de artiest, nooit de titel -- maar een lange titel zou net zo goed afgekapt
worden, dus beide velden worden hersteld. Alle 475 regels hebben een
aria-label met het vaste voorvoegsel "nummer ".

Splitsen doen we NIET op " - " in het aria-label: een titel of artiest mag dat
zelf ook bevatten. In plaats daarvan gebruiken we het veld dat *niet* afgekapt
is als anker en knippen dat er aan de juiste kant af. Alleen als beide velden
afgekapt zijn (nooit waargenomen) valt de code terug op een " - "-splitsing
achter het onafgekapte deel van de artiestnaam.

DE RANK-CEL (de enige echt subtiele plek)
-----------------------------------------
`.top40-list__item__controls--rank` heeft precies drie verschijningsvormen:

1. Binnenkomer:
       <span class="h5 span-entry">NIEUW</span>
       <span class="h5">37 <span class="underline"></span></span>
   -> geen vorige positie; het getal is de HUIDIGE positie.

2. Stijger/daler:
       <span class="h5">6 <i class="fa fa-caret-right color-green"></i> 5</span>
   -> twee getallen: EERST de vorige positie, DAN de huidige. De kleur van het
      pijltje geeft de richting: color-green = stijger, color-red = daler.

3. Ongewijzigd:
       <span class="h5">7 <span class="underline"></span></span>
   -> een getal, gelijk aan de huidige positie -> vorige positie == huidige.

Geverifieerd op alle 427 regels in de 12 gecachete pagina's: in vorm 2 is het
tweede getal altijd de huidige positie en klopt de pijlkleur altijd met de
richting (groen <=> vorige > huidige); in vorm 1 en 3 is het enige getal altijd
de huidige positie. Nul afwijkingen.

UITGEVALLEN NUMMERS
-------------------
Onder de lijst toont de site de nummers die deze week juist uit de lijst zijn
gevallen. Die hebben klasse `no-longer-listed`, een number-block met "-" in
plaats van een positie, en in de rank-cel hun LAATSTE positie. Ze horen niet in
de lijst thuis en worden overgeslagen. Zonder die filter zou je 42/33/28 regels
krijgen in plaats van 40/30/25.

"TERUG" (re-entry)
------------------
De site markeert re-entries met een eigen entry-label "RE-ENTRY", naast "NIEUW"
voor echte binnenkomers. Beide hebben geen vorige positie; het verschil zit in
het label en in weken_genoteerd (bij een re-entry groter dan 1).

Dit stond hier eerder als "nooit waargenomen, ongetest vangnet". Dat was
onjuist: op de jaargangen 2025 en 2026 vuurt de regel zeven keer en klopt de
uitkomst elke keer -- bijvoorbeeld Zara Larsson "Lush life", die in 2025 week 49
terugkeert met 27 weken op de teller en geen vorige positie. Ook Bad Bunny
"DTMF" (Tipparade 2026 week 7) en Taylor Swift "Opalite" (2025 week 51).
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import Notering, ParseFout

# Alles wat we van de opmaak nodig hebben, op een rij.
CONTAINER_SELECTOR = "div.list__list"
ITEM_SELECTOR = ".top40-list__item"
KLASSE_UITGEVALLEN = "no-longer-listed"
SEL_POSITIE = ".number-block"
SEL_TITEL = ".top40-list__item__info h2"
SEL_ARTIEST = ".top40-list__item__info h3"
SEL_RANK = ".top40-list__item__controls--rank"
SEL_WEKEN = ".top40-list__item__controls--weeks"
SEL_ENTRY = ".span-entry"
SEL_VOLLEDIG = "a[aria-label]"
ARIA_VOORVOEGSEL = "nummer "
AFKAP_STAART = ".."
SCHEIDING = " - "

_GETAL = re.compile(r"\d+")


def _tekst(element) -> str:
    """Zichtbare tekst met genormaliseerde witruimte.

    BeautifulSoup heeft HTML-entities (&amp;, &#039;) op dit punt al omgezet,
    dus hier is geen extra unescape nodig.
    """
    return " ".join(element.get_text(" ", strip=True).split())


def _herstel_afkapping(rij, titel: str, artiest: str) -> tuple[str, str]:
    """Vervang door de site afgekapte titel/artiest door de volledige tekst.

    Zie de moduledocstring. Levert (titel, artiest) ongewijzigd op zodra er
    niets af te kappen valt -- dat is het geval voor ~98,5% van de regels.
    """
    if not (titel.endswith(AFKAP_STAART) or artiest.endswith(AFKAP_STAART)):
        return titel, artiest

    anker = rij.select_one(SEL_VOLLEDIG)
    if anker is None:
        return titel, artiest
    volledig = " ".join((anker.get("aria-label") or "").split())
    if not volledig.startswith(ARIA_VOORVOEGSEL):
        return titel, artiest
    volledig = volledig[len(ARIA_VOORVOEGSEL):]

    titel_af = titel.endswith(AFKAP_STAART)
    artiest_af = artiest.endswith(AFKAP_STAART)

    if not titel_af and volledig.endswith(SCHEIDING + titel):
        # Titel is heel: knip die er achteraan af, de rest is de artiest.
        return titel, volledig[: -(len(SCHEIDING) + len(titel))]
    if not artiest_af and volledig.startswith(artiest + SCHEIDING):
        # Artiest is heel: knip die er vooraan af, de rest is de titel.
        return volledig[len(artiest) + len(SCHEIDING):], artiest

    # Beide afgekapt: splits op de eerste " - " die voorbij het nog leesbare
    # deel van de artiestnaam ligt.
    kern = artiest[: -len(AFKAP_STAART)]
    knip = volledig.find(SCHEIDING, len(kern))
    if knip != -1:
        return volledig[knip + len(SCHEIDING):], volledig[:knip]

    # Komt er geen scheiding meer voorbij dat punt, dan is het aria-label KORTER
    # dan de zichtbare tekst. Dat is het patroon van de jaren zestig: een positie
    # werd gedeeld door meerdere versies van hetzelfde nummer, de zichtbare tekst
    # somt ze allemaal op ("Duo Acropolis / Trio Hellenique / Mikis Theod..")
    # en het aria-label geeft alleen de eerste ("Duo Acropolis - Zorba Le Grec").
    #
    # Neem dan het aria-label. Het is compleet in plaats van afgekapt, en vooral:
    # het blijft gelijk als er in een latere week nog een versie bijkomt. De
    # zichtbare tekst verandert dan wel, en dat zou de notering elke keer onder
    # een nieuwe sleutel laten vallen.
    knip = volledig.find(SCHEIDING)
    if knip != -1:
        return volledig[knip + len(SCHEIDING):], volledig[:knip]
    return titel, artiest


def _status_en_vorige(rank_cel, positie: int, weken: int | None) -> tuple[str, int | None]:
    """Leid (site_status, vorige_positie) af uit de rank-cel.

    Zie de moduledocstring voor de drie vormen die deze cel kan hebben.
    """
    entry = rank_cel.select_one(SEL_ENTRY)
    if entry is not None:
        # Binnenkomer: geen vorige positie. Belangrijk, want controleer_lijst()
        # klaagt als site_status "nieuw" is terwijl er een vorige positie staat.
        label = _tekst(entry).upper()
        if weken is not None and weken > 1 and "NIEUW" not in label:
            # Nooit waargenomen; puur een vangnet voor een expliciet
            # re-entry-label ("RE", "TERUG", ...) mocht de site dat ooit tonen.
            return "terug", None
        return "nieuw", None

    getallen = [int(g) for g in _GETAL.findall(_tekst(rank_cel))]
    pijl = rank_cel.select_one("i")

    if pijl is not None:
        if len(getallen) != 2:
            raise ParseFout(
                f"positie {positie}: rank-cel met pijl bevat {len(getallen)} "
                f"getallen in plaats van 2 ({getallen})"
            )
        vorige, huidig = getallen
        if huidig != positie:
            raise ParseFout(
                f"positie {positie}: rank-cel noemt {huidig} als huidige positie"
            )
        klassen = pijl.get("class") or []
        if "color-green" in klassen:
            return "stijger", vorige
        if "color-red" in klassen:
            return "daler", vorige
        # Onbekende pijlkleur: de richting weten we dan uit de getallen zelf.
        if vorige > positie:
            return "stijger", vorige
        if vorige < positie:
            return "daler", vorige
        return "gelijk", vorige

    if len(getallen) == 1:
        if getallen[0] != positie:
            raise ParseFout(
                f"positie {positie}: rank-cel zonder pijl noemt {getallen[0]}"
            )
        return "gelijk", positie

    raise ParseFout(
        f"positie {positie}: onbegrepen rank-cel {_tekst(rank_cel)!r}"
    )


# De lijsten waarin de stipnotering betekenis heeft; zie de toelichting bij
# het veld hieronder.
MET_STIP = {"top40", "sterrennl"}


def parse(html: str, lijst: str, jaar: int, week: int) -> list[Notering]:
    """HTML van een top40.nl-lijstpagina -> lijst van Notering."""
    soup = BeautifulSoup(html, "lxml")

    container = soup.select_one(CONTAINER_SELECTOR)
    if container is None:
        raise ParseFout(
            f"{lijst} {jaar}-w{week}: geen {CONTAINER_SELECTOR} gevonden; "
            "opmaak van top40.nl is waarschijnlijk gewijzigd"
        )

    rijen = container.select(ITEM_SELECTOR)
    if not rijen:
        raise ParseFout(
            f"{lijst} {jaar}-w{week}: geen enkele {ITEM_SELECTOR} in de lijst"
        )

    noteringen: list[Notering] = []
    for rij in rijen:
        klassen = rij.get("class") or []
        if KLASSE_UITGEVALLEN in klassen:
            # Uitgevallen nummer onder de lijst; hoort niet bij deze week.
            continue

        positie_el = rij.select_one(SEL_POSITIE)
        if positie_el is None:
            raise ParseFout(f"{lijst} {jaar}-w{week}: regel zonder {SEL_POSITIE}")
        positie_tekst = _tekst(positie_el)
        if not positie_tekst.isdigit():
            # "-" hoort bij no-longer-listed en is hierboven al afgevangen;
            # iets anders betekent dat de opmaak veranderd is.
            raise ParseFout(
                f"{lijst} {jaar}-w{week}: onverwachte positie {positie_tekst!r}"
            )
        positie = int(positie_tekst)

        titel_el = rij.select_one(SEL_TITEL)
        artiest_el = rij.select_one(SEL_ARTIEST)
        if titel_el is None or artiest_el is None:
            raise ParseFout(
                f"{lijst} {jaar}-w{week}: positie {positie} mist titel of artiest"
            )

        titel, artiest = _herstel_afkapping(
            rij, _tekst(titel_el), _tekst(artiest_el)
        )

        weken = None
        weken_el = rij.select_one(SEL_WEKEN)
        if weken_el is not None:
            treffer = _GETAL.search(_tekst(weken_el))
            if treffer:
                weken = int(treffer.group())

        rank_cel = rij.select_one(SEL_RANK)
        if rank_cel is None:
            raise ParseFout(
                f"{lijst} {jaar}-w{week}: positie {positie} mist {SEL_RANK}"
            )
        status, vorige = _status_en_vorige(rank_cel, positie, weken)

        noteringen.append(
            Notering(
                lijst=lijst,
                jaar=jaar,
                week=week,
                positie=positie,
                titel=titel,
                artiest=artiest,
                label=None,  # top40.nl toont geen platenlabel
                weken_genoteerd=weken,
                vorige_positie=vorige,
                site_status=status,
                # De klasse `hitrecord` op het lijst-item is wat het rode
                # belletje zichtbaar maakt (CSS: .top40-list__item.hitrecord
                # .alarmschijf-icon {display:flex}). Het zegt "dit nummer is
                # ooit Alarmschijf geweest" -- het staat er ook nog weken na
                # de toekenning, en in elke lijst waar het nummer in staat.
                alarmschijf="hitrecord" in (rij.get("class") or []),
                # `dot` en `super` op datzelfde lijst-item zijn de stip en
                # de superstip. Ze sluiten elkaar uit -- over 1965-2026 komt
                # geen enkele notering met allebei voor -- en de posities
                # kloppen met de officiele criteria: een stip nooit lager dan
                # 30, een superstip nooit lager dan 25.
                #
                # Alleen waar de stip ook echt een onderscheiding is. Dat
                # blijkt uit de grens: in de Top 40 staat een stip nooit onder
                # plek 30 en een superstip nooit onder 25, en Sterren NL heeft
                # diezelfde grens geschaald naar zijn Top 25 -- 20 en 15. In
                # beide lijsten draagt ongeveer een vijfde van de regels een
                # stip. De Tipparade zet dezelfde klassen, maar daar draagt
                # ruim de helft er een; in een lijst waarin per definitie
                # bijna alles stijgt onderscheidt dat niets meer.
                stip=(0 if lijst not in MET_STIP else
                      2 if "super" in (rij.get("class") or []) else
                      1 if "dot" in (rij.get("class") or []) else 0),
            )
        )

    if not noteringen:
        raise ParseFout(
            f"{lijst} {jaar}-w{week}: alleen uitgevallen nummers gevonden, "
            "geen enkele genoteerde regel"
        )

    return noteringen
