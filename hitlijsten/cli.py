"""Opdrachtregel: ophalen, Excel bouwen, mailen.

    python -m hitlijsten run             bijwerken + excel + mail  (wekelijkse taak)
    python -m hitlijsten bijwerken       alleen ontbrekende weken ophalen
    python -m hitlijsten backfill        alle weken van het lopende jaar
    python -m hitlijsten historie        complete oude jaargangen uit het archief
    python -m hitlijsten excel           Excel-bestanden opnieuw bouwen
    python -m hitlijsten controle        verdachte dubbelingen, met oordeel per paar
    python -m hitlijsten hersleutel      sleutels herberekenen na aliases.csv
    python -m hitlijsten opschonen       leestekens en schrijfwijzen rechtzetten
    python -m hitlijsten testmail        proefmail versturen

--jaar mag voor of na de opdracht: "hitlijsten excel --jaar 2025" werkt, en
"hitlijsten --jaar 2025 excel" ook.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import traceback
from datetime import datetime

from . import db, fetch, mail, parsers
from .config import JAAR, LIJSTEN, wordt_opgehaald, LOG_PATH, ROOT, verwachte_lengte

TE_BEOORDELEN = ROOT / "te-beoordelen.csv"
from .models import ParseFout, controleer_lijst


def log(regel: str) -> None:
    stempel = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tekst = f"[{stempel}] {regel}"
    print(tekst, flush=True)
    try:
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(tekst + "\n")
    except OSError:
        pass  # logbestand is een gemak, geen reden om de run te laten falen


def haal_week(
    con: sqlite3.Connection, lijst: str, jaar: int, week: int, *, forceer: bool = False
) -> int:
    """Haal één week op, controleer de structuur en bewaar hem.

    Bij elke fout wordt de gecachete pagina weggegooid. Anders zou één
    onderhoudspagina of half antwoord zich permanent vastzetten: de cache wordt
    geschreven voordat de parser hem ziet, en daarna leest elke volgende run
    diezelfde kapotte pagina -- de wekelijkse herkansing zou dan machteloos zijn.
    """
    try:
        html = fetch.haal_html(lijst, jaar, week, forceer=forceer)
        # Eerst: is dit wel de week die we vroegen? Zie fetch.controleer_gevraagde_week.
        fetch.controleer_gevraagde_week(html, jaar, week)
        noteringen = parsers.parse(html, lijst, jaar, week)

        controle = controleer_lijst(noteringen, verwachte_lengte(lijst, jaar))
        if not controle.ok:
            raise ParseFout(
                f"{lijst} {jaar} week {week}: " + "; ".join(controle.meldingen)
            )
        for opmerking in controle.opmerkingen:
            log(f"  {lijst} {jaar} week {week}: {opmerking}")

        _waarschuw_bij_dubbele_week(con, lijst, jaar, week, noteringen)
        return db.bewaar_week(con, lijst, jaar, week, noteringen)
    except Exception:
        fetch.gooi_cache_weg(lijst, jaar, week)
        raise


def _waarschuw_bij_dubbele_week(con, lijst, jaar, week, noteringen) -> None:
    """Als een archiefpagina stiekem de nieuwste lijst teruggeeft, is de nieuwe
    week identiek aan de vorige. Dat is bij 25-40 posities praktisch onmogelijk
    als het echt een andere week is."""
    from .normalize import sleutel_van

    vorige = list(
        con.execute(
            "SELECT positie, sleutel FROM noteringen WHERE lijst=? AND jaar=? AND week=?",
            (lijst, jaar, week - 1),
        )
    )
    if not vorige:
        return
    oud = {(r["positie"], r["sleutel"]) for r in vorige}
    nieuw = {(n.positie, sleutel_van(n.artiest, n.titel)) for n in noteringen}
    if oud == nieuw:
        log(
            f"  LET OP: {lijst} week {week} is regel voor regel gelijk aan week "
            f"{week - 1}. Mogelijk serveert het archief de verkeerde week."
        )


def nieuwe_nummers(con: sqlite3.Connection, lijst: str, jaar: int, week: int) -> list[sqlite3.Row]:
    """Noteringen waarvan de sleutel dit jaar niet eerder in deze lijst stond."""
    return list(
        con.execute(
            "SELECT * FROM noteringen n WHERE n.lijst=? AND n.jaar=? AND n.week=?"
            " AND NOT EXISTS ("
            "   SELECT 1 FROM noteringen e WHERE e.lijst=n.lijst AND e.jaar=n.jaar"
            "     AND e.week < n.week AND e.sleutel = n.sleutel)"
            " ORDER BY n.positie",
            (lijst, jaar, week),
        )
    )


def opdracht_backfill(jaar: int, vanaf: int, tot: int | None) -> None:
    with db.verbinding() as con:
        for lijst in LIJSTEN:
            if not wordt_opgehaald(lijst):
                continue        # de Top 2000 komt uit een CSV, niet van een site
            laatste = tot
            if laatste is None:
                _, laatste = fetch.laatst_gepubliceerd(lijst)
                log(f"{lijst}: nieuwste gepubliceerde week is {laatste}")
            al_bekend = db.bekende_weken(con, lijst, jaar)
            for week in range(vanaf, laatste + 1):
                if week in al_bekend:
                    continue
                try:
                    aantal = haal_week(con, lijst, jaar, week)
                    log(f"{lijst} week {week:>2}: {aantal} noteringen")
                except Exception as fout:
                    log(f"{lijst} week {week:>2}: OVERGESLAGEN -- {fout}")
            con.commit()


def opdracht_bijwerken(
    jaar: int | None = None,
) -> tuple[dict[tuple[str, int], list[int]], list[str]]:
    """Haal per lijst alles op wat nog ontbreekt.

    De jaargang komt van de site, niet van de kalender: begin januari staat er
    soms nog een week van het vorige jaar. Geeft ({(lijst, jaar): [weken]},
    [mislukkingen]) terug -- de mislukkingen moeten de gebruiker bereiken, want
    de wekelijkse taak draait zonder venster.
    """
    nieuw: dict[tuple[str, int], list[int]] = {}
    mislukt: list[str] = []

    with db.verbinding() as con:
        for lijst in LIJSTEN:
            if not wordt_opgehaald(lijst):
                continue        # de Top 2000 komt uit een CSV, niet van een site
            site_jaar, laatste = fetch.laatst_gepubliceerd(lijst)
            if jaar is not None and site_jaar != jaar:
                log(
                    f"{lijst}: site publiceert jaargang {site_jaar}, gevraagd was "
                    f"{jaar} -- overgeslagen"
                )
                continue

            # Werk voor de jaarwisseling: als de site net op een nieuwe jaargang
            # is overgegaan, kunnen de laatste weken van vorig jaar nog ontbreken
            # doordat de pc uit stond. Zonder deze inhaalslag worden die nooit
            # meer opgehaald -- de lus keek alleen naar het jaar van de site.
            # De vorige jaargang is afgesloten: een week die daar niet bestaat
            # komt er ook nooit meer, dus die leggen we vast (onthoud_afwezig)
            # in plaats van hem elke vrijdag opnieuw te melden.
            staart = _afgekapte_staart(con, lijst, site_jaar - 1)
            if staart:
                gehaald, fouten = _haal_weken(
                    con, lijst, site_jaar - 1, staart, onthoud_afwezig=True
                )
                if gehaald:
                    nieuw.setdefault((lijst, site_jaar - 1), []).extend(gehaald)
                mislukt += fouten

            gehaald, fouten = _haal_weken(
                con, lijst, site_jaar, _ontbrekend(con, lijst, site_jaar, laatste)
            )
            if gehaald:
                nieuw.setdefault((lijst, site_jaar), []).extend(gehaald)
            mislukt += fouten
            con.commit()

            if not any(l == lijst for l, _ in nieuw):
                log(f"{lijst}: niets nieuws (t/m {site_jaar} week {laatste})")
    return nieuw, mislukt


def _afgekapte_staart(con: sqlite3.Connection, lijst: str, jaar: int) -> list[int]:
    """Welke weken ontbreken er aan het EIND van een eerdere jaargang?

    Stond de pc rond de jaarwisseling uit, dan houdt die jaargang op bij
    bijvoorbeeld week 49 terwijl de lus die alleen naar het jaar van de site
    kijkt hem nooit meer aanraakt.

    Bewust alleen de staart, niet elk gat: een jaargang die pas halverwege begon
    (Sterren NL start in 2019 pas bij week 40) heeft aan het begin gaten die
    nooit bestaan hebben. Die elke week opnieuw proberen zou de mail voorgoed
    vervuilen met mislukkingen.
    """
    vanaf = LIJSTEN[lijst].get("vanaf_jaar")
    if vanaf is not None and jaar < vanaf:
        return []
    bekend = db.bekende_weken(con, lijst, jaar)
    if not bekend:
        return []          # die jaargang verzamelen we blijkbaar niet
    # Weken die we al als onbestaand hebben vastgesteld tellen als afgehandeld,
    # anders blijft de staart eeuwig "onvolledig" lijken.
    afgehandeld = bekend | db.onbestaande_weken(con, lijst, jaar)
    hoogste = max(bekend)
    if hoogste >= 53:
        return []
    return [w for w in range(hoogste + 1, 54) if w not in afgehandeld]


def _ontbrekend(
    con: sqlite3.Connection, lijst: str, jaar: int, tot: int, vanaf: int = 1
) -> list[int]:
    """Weken die we nog missen -- zonder de weken die aantoonbaar niet bestaan."""
    overslaan = db.bekende_weken(con, lijst, jaar) | db.onbestaande_weken(con, lijst, jaar)
    return [w for w in range(vanaf, tot + 1) if w not in overslaan]


def _bestaat_echt_niet(fout: Exception) -> str | None:
    """Is dit een definitief 'deze week bestaat niet', of iets tijdelijks?

    404 en een pagina van een andere week zijn definitief: die week komt er nooit
    meer. Een parseerfout of netwerkstoring is dat niet -- daar moet de volgende
    run gewoon opnieuw op proberen, anders missen we een week bij een
    layoutwijziging die later hersteld wordt.
    """
    if isinstance(fout, fetch.WekenKomenNietOvereen):
        return str(fout)
    respons = getattr(fout, "response", None)
    if respons is not None and getattr(respons, "status_code", None) == 404:
        return "404 -- deze week bestaat niet op de site"
    return None


def _haal_weken(
    con: sqlite3.Connection,
    lijst: str,
    jaar: int,
    weken: list[int],
    *,
    onthoud_afwezig: bool = False,
) -> tuple[list[int], list[str]]:
    """Haal een reeks weken op; geef (gelukt, mislukkingen) terug.

    Met `onthoud_afwezig` wordt een week die aantoonbaar niet bestaat vastgelegd,
    zodat hij niet elke week opnieuw geprobeerd en gemeld wordt. Dat mag alleen
    voor afgesloten jaargangen: bij de lopende week betekent een 404 "nog niet
    gepubliceerd", en die moet juist wel opnieuw geprobeerd worden.
    """
    gelukt: list[int] = []
    mislukt: list[str] = []
    for week in weken:
        try:
            aantal = haal_week(con, lijst, jaar, week)
            log(f"{lijst} {jaar} week {week:>2}: {aantal} noteringen")
            gelukt.append(week)
        except Exception as fout:
            reden = _bestaat_echt_niet(fout)
            if onthoud_afwezig and reden:
                db.markeer_bestaat_niet(con, lijst, jaar, week, reden)
                log(f"{lijst} {jaar} week {week:>2}: bestaat niet ({reden}) "
                    "-- wordt niet meer geprobeerd")
                continue
            melding = f"{lijst} {jaar} week {week}: {fout}"
            log(f"MISLUKT -- {melding}")
            mislukt.append(melding)
    return gelukt, mislukt


def opdracht_excel(jaar: int) -> list:
    from . import excel

    bestanden = excel.bouw_alles(jaar)
    for pad in bestanden:
        log(f"geschreven: {pad.name}")
    return bestanden


def opdracht_pdf(jaar: int | None, *, altijd: bool = False) -> list:
    """De jaaroverzichten als PDF naar de jaarmappen.

    Zonder jaartal alle jaargangen van alle lijsten. Bestanden die er al staan
    en nog kloppen worden overgeslagen, tenzij `altijd` -- zo kost een tweede
    keer draaien vrijwel niets.
    """
    from . import pdf as pdfbouwer
    from .config import LIJSTEN
    from .db import verbinding

    bestanden, overgeslagen = [], 0
    with verbinding() as con:
        for lijst in LIJSTEN:
            jaren = ([jaar] if jaar is not None else
                     [r[0] for r in con.execute(
                         "SELECT DISTINCT jaar FROM noteringen WHERE lijst=?"
                         " ORDER BY jaar", (lijst,))])
            for j in jaren:
                pad = pdfbouwer.pad_van(lijst, j)
                bestond = pdfbouwer.is_actueel(con, pad, lijst, j)
                gemaakt = pdfbouwer.schrijf_jaaroverzicht(con, lijst, j, altijd=altijd)
                if gemaakt is None:
                    continue
                if bestond and not altijd:
                    overgeslagen += 1
                else:
                    log(f"geschreven: {gemaakt.name}")
                    bestanden.append(gemaakt)
    if overgeslagen:
        log(f"{overgeslagen} bestanden waren al actueel en zijn overgeslagen")
    return bestanden


def opdracht_jaarlijks(lijst: str, pad: str, jaar: int | None = None) -> dict:
    """Lees een jaarlijkse lijst uit een CSV van Music Datastats."""
    from .jaarlijks import importeer

    with db.verbinding() as con:
        uitkomst = importeer(con, lijst, pad, alleen_jaar=jaar)

    naam = LIJSTEN.get(lijst, {}).get("naam", lijst)
    edities = uitkomst["edities"]
    log(f"{naam}: {uitkomst['nummers']} nummers over {len(edities)} edities "
        f"({edities[0]}-{edities[-1]})")
    for waarschuwing in uitkomst["waarschuwingen"]:
        log(f"  let op: {waarschuwing}")
    for editiejaar, aantal in sorted(uitkomst["geschreven"].items()):
        log(f"  {editiejaar}: {aantal} noteringen")
    kruis = uitkomst["kruisverwijzing"]
    log(f"{kruis['raak']} van de {uitkomst['nummers']} nummers staan ook in een "
        f"andere lijst:")
    for andere, aantal in sorted(kruis["per_lijst"].items(), key=lambda p: -p[1]):
        log(f"  {LIJSTEN.get(andere, {}).get('naam', andere)}: {aantal}")
    return uitkomst


def opdracht_decennium(decennium: int | None) -> list:
    """Het decenniumklassement naar de decenniummap.

    Zonder opgave alle decennia die in de database zitten. Alleen voor de Top
    40: die is zijn hele bestaan veertig noteringen lang, dus punten uit
    verschillende jaargangen zijn zonder voorbehoud op te tellen.
    """
    from . import excel
    from .db import verbinding

    bestanden = []
    with verbinding() as con:
        if decennium is None:
            jaren = [r[0] for r in con.execute(
                "SELECT DISTINCT jaar FROM noteringen WHERE lijst='top40'")]
            decennia = sorted({j - j % 10 for j in jaren})
        else:
            decennia = [decennium - decennium % 10]
        for begin in decennia:
            for pad in excel.bouw_decennium(con, "top40", begin):
                log(f"geschreven: {pad.name}")
                bestanden.append(pad)
    return bestanden


def opdracht_historie(
    vanaf: int | None, tot: int, *, bouw_excel: bool = True,
    alleen_lijst: str | None = None,
) -> None:
    """Haal complete jaargangen op, van de oudste die een site heeft tot `tot`.

    Elke lijst heeft zijn eigen begin (zie config vanaf_jaar). Weken die niet
    bestaan -- het begin van een jaargang die pas halverwege startte, of week 53
    in een jaar met 52 weken -- mislukken en worden overgeslagen; dat is normaal
    en geen reden om te stoppen.
    """
    with db.verbinding() as con:
        for lijst, cfg in LIJSTEN.items():
            if alleen_lijst and lijst != alleen_lijst:
                continue
            if not wordt_opgehaald(lijst):
                continue        # de Top 2000 komt uit een CSV, niet van een site
            start = max(vanaf or cfg.get("vanaf_jaar", 1965), cfg.get("vanaf_jaar", 1965))
            log("=" * 60)
            log(f"{cfg['naam']}: jaargangen {start} t/m {tot}")
            for jaar in range(start, tot + 1):
                ontbreekt = _ontbrekend(con, lijst, jaar, 53)
                if not ontbreekt:
                    log(f"  {jaar}: al compleet")
                    continue
                # Afgesloten jaargangen: weken die niet bestaan eenmalig
                # vastleggen, zodat een herhaalde historie-run ze overslaat.
                gelukt, mislukt = _haal_weken(
                    con, lijst, jaar, ontbreekt, onthoud_afwezig=True
                )
                con.commit()
                log(f"  {jaar}: {len(gelukt)} weken opgehaald, {len(mislukt)} overgeslagen")

    if bouw_excel:
        jaren = _jaren_in_database()
        log(f"Excel bouwen voor {len(jaren)} jaargangen")
        for jaar in jaren:
            opdracht_excel(jaar)


def _jaren_in_database() -> list[int]:
    with db.verbinding() as con:
        return [r[0] for r in con.execute(
            "SELECT DISTINCT jaar FROM noteringen ORDER BY jaar")]


def opdracht_onderscheidingen(*, forceer: bool = False) -> None:
    """Haal de Alarmschijven en Dancesmashes op en koppel ze aan onze nummers."""
    from . import onderscheidingen as ond

    alles = ond.haal_alles(forceer=forceer)
    gekoppeld, niet = ond.koppel_aan_onze_nummers(alles)
    ond.bewaar(alles)
    for soort in ("alarmschijf", "dancesmash"):
        van_soort = [o for o in alles if o.soort == soort]
        if van_soort:
            log(f"{soort}: {len(van_soort)} stuks, "
                f"{min(o.jaar for o in van_soort)}-{max(o.jaar for o in van_soort)}")
    jaren = set(_jaren_in_database())
    binnen = [o for o in alles if o.jaar in jaren or o.jaar + 1 in jaren]
    binnen_gekoppeld = sum(1 for o in binnen if o.sleutel)
    log(f"totaal {len(alles)} onderscheidingen, {gekoppeld} gekoppeld")
    log(f"binnen onze jaargangen: {len(binnen)}, waarvan {binnen_gekoppeld} gekoppeld "
        f"({100 * binnen_gekoppeld // max(1, len(binnen))}%)")
    log(f"de overige {niet - (len(binnen) - binnen_gekoppeld)} vallen buiten onze "
        "jaargangen; van de rest haalde het merendeel de Top 40 nooit")
    log("draai 'python -m hitlijsten excel' om ze in de Totaal-tab te zetten")


def opdracht_kruiscontrole(jaar: int | None, *, alle_jaren: bool = False) -> None:
    """Leg onze Top 40-jaartotalen naast die van michajans.nl."""
    from . import kruiscontrole

    jaren = _jaren_in_database() if alle_jaren else [jaar]
    totaal_ok = 0
    totaal_overgenomen = 0
    voorstellen: list[str] = []
    overige: list[tuple[str, int, str]] = []

    for dit_jaar in jaren:
        rapport = kruiscontrole.vergelijk(dit_jaar)
        if rapport is None:
            log(f"{dit_jaar}: geen jaarlijst bij michajans.nl (hun archief loopt t/m 2025)")
            continue
        totaal_ok += rapport.identiek
        samen = [b for b in rapport.bevindingen if b.soort == "samenvoegen"]
        verschil = [b for b in rapport.bevindingen if b.soort == "verschil"]
        groot = [b for b in rapport.bevindingen if b.soort == "groot_verschil"]
        overgenomen = kruiscontrole.bewaar_correcties(dit_jaar, "top40", rapport.bevindingen)
        totaal_overgenomen += overgenomen
        log(
            f"{dit_jaar}: {rapport.identiek} identiek, {len(verschil)} klein afwijkend, "
            f"{len(groot)} groot afwijkend, {len(samen)} samen te voegen"
        )
        for b in groot:
            log(f"    OVERGENOMEN  {b.tekst}")
        for b in samen:
            log(f"    SAMENVOEGEN  {b.tekst}")
            if b.aliasregel:
                voorstellen.append(f"# {b.jaar}: {b.tekst.splitlines()[0]}")
                voorstellen.append(b.aliasregel)
        for b in verschil:
            log(f"    VERSCHIL     {b.tekst}")
        overige += [(b.soort, b.jaar, b.tekst) for b in rapport.bevindingen
                    if b.soort in ("alleen_bij_hen", "alleen_bij_ons")]

    log("")
    log(f"totaal {totaal_ok} nummers exact gelijk aan michajans.nl")
    if totaal_overgenomen:
        log(f"{totaal_overgenomen} nummers krijgen zijn cijfer in de Totaal-tab "
            "(kolom Bron); draai daarna 'excel' opnieuw")
    else:
        log("geen enkel verschil was groot genoeg om zijn cijfer over te nemen "
            f"(grens: meer dan {kruiscontrole.GROOT_VERSCHIL_WEKEN} weken of "
            f"{int(kruiscontrole.GROOT_VERSCHIL_PUNTEN * 100)}% van de punten)")
    if voorstellen:
        pad = ROOT / "kruiscontrole-aliases.csv"
        pad.write_text(
            "# Voorstellen uit de kruiscontrole met michajans.nl.\n"
            "# Zij hebben een notering waar wij er twee hebben die in punten EN\n"
            "# weken precies optellen -- het handtekeningpatroon van een lopende\n"
            "# notering die de site onderweg hernoemd heeft.\n"
            "# Controleer, plak in aliases.csv, draai daarna hersleutel + excel.\n\n"
            + "\n".join(voorstellen) + "\n",
            encoding="utf-8",
        )
        log(f"{len(voorstellen) // 2} aliasvoorstellen -> {pad.name}")
    if overige:
        log(f"{len(overige)} regels staan maar bij een van beide (meestal hun extra")
        log("   regels voor een hernoemde periode, die dubbel tellen)")


def opdracht_opschonen(*, toepassen: bool) -> None:
    """Leestekens rechtzetten en één schrijfwijze per artiest afdwingen.

    Twee dingen die na elke run opnieuw kunnen ontstaan, want de bronnen
    veranderen niet: de backtick van Music Datastats, en een lijst die
    "coldplay" schrijft waar een andere "Coldplay" schrijft. De zwaardere
    ingrepen -- nummers samenvoegen, artiesten samenvoegen -- staan hier NIET
    in. Die vragen een oordeel per geval en horen niet in een wekelijkse taak.

    Zonder --toepassen wordt alleen gemeld wat er zou gebeuren.
    """
    from .opschonen import (bewaar_artiestnaam, bewaar_titel,
                            geleende_hoofdletters, herstel_tekst,
                            meerderheidsnaam, naamvarianten, pas_namen_toe,
                            pas_titels_toe, splits_dubbele_a_kanten,
                            tekstfouten, titelvarianten, uitgave_en_nummer,
                            dubbele_a_kanten, spatievarianten)

    with db.verbinding() as con:
        fouten = tekstfouten(con)
        log(f"{len(fouten)} schrijfwijzen met een verkeerd leesteken"
            f" ({sum(f['aantal'] for f in fouten)} noteringen)")
        for fout in fouten[:5]:
            log(f"   {fout['oud'][0]} - {fout['oud'][1]}")
            log(f"   {fout['nieuw'][0]} - {fout['nieuw'][1]}")

        bakken = naamvarianten(con)
        log(f"{len(bakken['tekens'])} artiesten met alleen een verschil in "
            f"hoofdletters of accenten")
        log(f"{len(bakken['lidwoord'])} met en zonder lidwoord, "
            f"{len(bakken['anders'])} met een echt andere schrijfwijze")

        dubbel = dubbele_a_kanten(con)
        log(f"{len(dubbel)} noteringen met twee nummers op een positie "
            f"(dubbele A-kant)")

        uitgaven = uitgave_en_nummer(con)
        log(f"{len(uitgaven)} titels met de uitgave ervoor "
            f"(\"Live! : Roll Over Lay Down\")")

        titels = titelvarianten(con)
        log(f"{len(titels['tekens'])} nummers met meer dan een titel die "
            f"alleen in tekens verschilt, {len(titels['anders'])} die anders "
            f"zijn opgebouwd")

        if not toepassen:
            log("niets gewijzigd -- draai met --toepassen om het door te voeren")
            return

        log(f"{herstel_tekst(con, fouten)} noteringen met schone tekst")
        # Ook hier alle bakken: twee schrijfwijzen onder dezelfde artiestsleutel
        # zijn dezelfde artiest, want dat samenvoegen is eerder met de hand
        # nagelopen. "Wham" en "Wham!" hoeven niet allebei te blijven staan.
        for code, namen in (bakken["tekens"] + bakken["lidwoord"]
                            + bakken["anders"]):
            bewaar_artiestnaam(con, code, meerderheidsnaam(namen), "meerderheid")
        con.commit()
        verslag = pas_namen_toe(con)
        log(f"{verslag['noteringen']} noteringen kregen de vastgestelde "
            f"artiestnaam ({verslag['artiesten']} schrijfwijzen)")

        # Beide bakken, anders dan bij de artiesten. Alles wat dezelfde
        # sleutel heeft is per definitie hetzelfde nummer -- dat is wat een
        # sleutel betekent -- dus er valt hier niets te beschermen, alleen te
        # kiezen. "Beggin" en "Beggin'" verschillen in een apostrof en zaten
        # daardoor in de bak "echt anders"; dat was een verschil zonder gevolg.
        for sleutel, varianten in titels["tekens"] + titels["anders"]:
            bewaar_titel(con, sleutel,
                         meerderheidsnaam(varianten, apostrof=True),
                         "meerderheid")
        con.commit()
        verslag = pas_titels_toe(con)
        log(f"{verslag['noteringen']} noteringen kregen de vastgestelde titel "
            f"({verslag['nummers']} schrijfwijzen)")

        if dubbel:
            verslag = splits_dubbele_a_kanten(con)
            log(f"{verslag['nieuw']} noteringen erbij: elke kant van een "
                f"dubbele A-kant staat nu op zijn eigen regel")

        # De uitgave eraf, en een alias zodat de notering samenvalt met dezelfde
        # titel in de andere lijsten. Zonder die alias verandert alleen wat je
        # ziet en blijft het nummer in tweeen liggen.
        from .normalize import sleutel_van, vergeet_aliases

        for sleutel, oude_titel, nummer in uitgaven:
            artiest = con.execute(
                "SELECT artiest FROM noteringen WHERE sleutel=? LIMIT 1",
                (sleutel,)).fetchone()[0]
            doel = sleutel_van(artiest, nummer)
            if doel != sleutel:
                con.execute(
                    "INSERT OR REPLACE INTO aliases (van, naar, opmerking,"
                    " aangemaakt) VALUES (?,?,?,?)",
                    (sleutel, doel, "top40.nl zet de uitgave voor het nummer",
                     datetime.now().isoformat(timespec="seconds")))
            con.execute(
                "UPDATE noteringen SET titel=?, sleutel=? WHERE sleutel=?",
                (nummer, doel, sleutel))
            con.execute(
                "INSERT INTO wijzigingen (tijdstip, soort, verwijst, veld, oud,"
                " nieuw, reden) VALUES (?,?,?,?,?,?,?)",
                (datetime.now().isoformat(timespec="seconds"), "titel", doel,
                 "titel", oude_titel, nummer,
                 "de uitgave stond voor het nummer"))
        if uitgaven:
            con.commit()
            vergeet_aliases()
            log(f"{len(uitgaven)} titels ontdaan van hun uitgave")

        # Twee schrijfwijzen die alleen in spaties verschillen zijn een nummer.
        spaties = spatievarianten(con)
        for doel, andere, goede_titel in spaties:
            for bron in andere:
                con.execute(
                    "INSERT OR REPLACE INTO aliases (van, naar, opmerking,"
                    " aangemaakt) VALUES (?,?,?,?)",
                    (bron, doel, "zelfde nummer, andere spatiëring",
                     datetime.now().isoformat(timespec="seconds")))
                con.execute(
                    "UPDATE noteringen SET titel=?, sleutel=? WHERE sleutel=?",
                    (goede_titel, doel, bron))
                con.execute(
                    "INSERT INTO wijzigingen (tijdstip, soort, verwijst, veld,"
                    " oud, nieuw, reden) VALUES (?,?,?,?,?,?,?)",
                    (datetime.now().isoformat(timespec="seconds"), "titel",
                     doel, "titel", bron, goede_titel,
                     "zelfde nummer, andere spatiëring"))
        if spaties:
            con.commit()
            vergeet_aliases()
            log(f"{len(spaties)} nummers samengevoegd die alleen in spaties "
                f"verschilden")

        for sleutel, oud, goed in geleende_hoofdletters(con):
            bewaar_titel(con, sleutel, goed, "hoofdletters van elders")
        con.commit()
        verslag = pas_titels_toe(con)
        log(f"{verslag['noteringen']} noteringen kregen hoofdletters van een "
            f"gelijknamig nummer ({verslag['nummers']} titels)")


def opdracht_hersleutel(jaar: int) -> None:
    """Bereken alle sleutels opnieuw, bijvoorbeeld na het bewerken van aliases.csv.

    De sleutel wordt bij het opslaan berekend en in de tabel gezet. Zonder deze
    opdracht zou je alle weken opnieuw moeten wegschrijven om een nieuwe alias
    te laten gelden.
    """
    from .normalize import sleutel_van, vergeet_aliases

    vergeet_aliases()
    gewijzigd = 0
    with db.verbinding() as con:
        rijen = list(
            con.execute(
                "SELECT id, lijst, week, positie, artiest, titel, sleutel"
                " FROM noteringen WHERE jaar=?",
                (jaar,),
            )
        )
        for r in rijen:
            nieuw = sleutel_van(r["artiest"], r["titel"])
            if nieuw != r["sleutel"]:
                con.execute(
                    "UPDATE noteringen SET sleutel=? WHERE id=?", (nieuw, r["id"])
                )
                gewijzigd += 1
        con.commit()
    log(f"{gewijzigd} van {len(rijen)} sleutels bijgewerkt")
    if gewijzigd:
        log("draai nu 'python -m hitlijsten excel' om de bestanden te vernieuwen")


def opdracht_controle(jaar: int | None, *, alle_jaren: bool = False) -> None:
    """Zoek nummers die onder twee sleutels binnenkomen en beoordeel ze.

    Schrijft de gevallen die niet automatisch te beslissen zijn naar
    te-beoordelen.csv, in een vorm die je zo in aliases.csv kunt plakken.
    """
    from .normalize import niet_samenvoegen, verdachte_paren

    jaren = _jaren_in_database() if alle_jaren else [jaar]
    voorstellen: dict[tuple[str, str], tuple[int, str, list[int], list[int], int]] = {}
    # Ook ontdubbelen: hetzelfde sleutelpaar kan in meerdere jaargangen opduiken,
    # en een alias lost het in een keer voor allemaal op.
    apart: set[tuple[str, str]] = set()
    samen_in_een_week: set[tuple[str, str]] = set()

    with db.verbinding() as con:
        for dit_jaar in jaren:
            for lijst in LIJSTEN:
                rijen = db.noteringen_van_jaar(con, lijst, dit_jaar)
                if not rijen:
                    continue
                paren = verdachte_paren(
                    [(r["sleutel"], r["artiest"], r["titel"]) for r in rijen]
                )
                if not paren:
                    if not alle_jaren:
                        log(f"{lijst}: geen verdachte dubbelingen")
                    continue
                if not alle_jaren:
                    log(f"{lijst}: {len(paren)} verdachte paren")
                for a, b, score in paren:
                    if frozenset((a, b)) in niet_samenvoegen():
                        continue   # al beoordeeld als losse noteringen
                    oordeel = _oordeel_over_paar(rijen, a, b)
                    if not alle_jaren:
                        log(f"    {score}  {a}")
                        log(f"          {b}")
                        log(f"          -> {oordeel}")
                    wa = sorted({r["week"] for r in rijen if r["sleutel"] == a})
                    wb = sorted({r["week"] for r in rijen if r["sleutel"] == b})
                    if oordeel.startswith("zelfde notering"):
                        voorstellen.setdefault(
                            (a, b),
                            (dit_jaar, lijst, wa, wb,
                             _afstand_in_weken(set(wa), set(wb))),
                        )
                    elif oordeel.startswith("aparte notering"):
                        apart.add((a, b))
                    else:
                        samen_in_een_week.add((a, b))

    _schrijf_te_beoordelen(voorstellen)
    log(f"{len(voorstellen)} paren zijn dezelfde notering -> {TE_BEOORDELEN.name}")
    log(f"{len(apart)} paren liggen meer dan {MAX_GAT_WEKEN} weken uit elkaar: "
        "aparte notering")
    log(f"{len(samen_in_een_week)} paren stonden samen in een week: "
        "twee verschillende nummers")


def _schrijf_te_beoordelen(gevallen: dict) -> None:
    """Schrijf de voorstellen weg als voorbereide, uitgecommentarieerde aliasregels."""
    regels = [
        "# Nummers die onder twee sleutels binnenkomen en volgens de weken",
        f"# dezelfde notering zijn: er zitten hooguit {MAX_GAT_WEKEN} weken tussen de",
        "# twee reeksen. Meestal een typefout van de site, een toegevoegde",
        "# gastartiest of een dubbele A-kant.",
        "#",
        "# Wil je er een samenvoegen, haal dan het # voor de aliasregel weg en",
        "# plak hem in aliases.csv. Draai daarna:",
        "#     python -m hitlijsten hersleutel",
        "#     python -m hitlijsten excel",
        "#",
        "# Paren die verder uit elkaar liggen staan hier NIET in: die gelden als",
        "# aparte notering. Paren die ooit samen in een week stonden ook niet --",
        "# een nummer kan niet twee keer tegelijk noteren.",
        "",
    ]
    for (a, b), (jaar, lijst, wa, wb, gat) in sorted(gevallen.items()):
        tussen = "sluiten aaneen" if gat == 0 else f"{gat} week/weken ertussen"
        regels.append(f"# {jaar} {lijst}  ({tussen})")
        regels.append(f"#   A  {a}   (week {wa[0]}-{wa[-1]}, {len(wa)}x)")
        regels.append(f"#   B  {b}   (week {wb[0]}-{wb[-1]}, {len(wb)}x)")
        # Voorstel: de kortste reeks wijst naar de langste.
        van, naar = (a, b) if len(wa) <= len(wb) else (b, a)
        regels.append(f"# {van};{naar}")
        regels.append("")

    TE_BEOORDELEN.write_text("\n".join(regels), encoding="utf-8")


# Zitten er meer dan dit aantal weken tussen twee reeksen, dan is het een eigen
# notering en geen hernoeming. Een remix of heruitgave die maanden later opnieuw
# de lijst in komt hoort niet bij de oorspronkelijke notering.
MAX_GAT_WEKEN = 3


def _afstand_in_weken(wa: set[int], wb: set[int]) -> int:
    """Hoeveel weken zitten er tussen twee reeksen? 0 als ze in elkaar grijpen."""
    return max(0, max(min(wa), min(wb)) - min(max(wa), max(wb)) - 1)


def _oordeel_over_paar(rijen, a: str, b: str) -> str:
    """Zijn twee gelijkende sleutels dezelfde notering, of twee losse nummers?

    De beslissende vraag is niet hoe erg de namen op elkaar lijken, maar hoe de
    weken zich verhouden:

    - staan ze ooit samen in dezelfde week, dan zijn het per definitie twee
      verschillende nummers -- een nummer kan niet twee keer in een lijst staan;
    - zitten er hooguit MAX_GAT_WEKEN weken tussen, dan is het een notering die
      onderweg hernoemd is (een dubbele A-kant, een gewijzigde credit, een
      typefout van de site);
    - zit er meer tussen, dan is het een eigen notering.
    """
    wa = {r["week"] for r in rijen if r["sleutel"] == a}
    wb = {r["week"] for r in rijen if r["sleutel"] == b}
    if wa & wb:
        return (f"twee losse nummers (staan samen in week "
                f"{sorted(wa & wb)[0]}) -- NIET samenvoegen")

    gat = _afstand_in_weken(wa, wb)
    if gat <= MAX_GAT_WEKEN:
        omschrijving = "sluiten aaneen" if gat == 0 else f"{gat} week/weken ertussen"
        return (f"zelfde notering, hernoemd ({omschrijving}) -- regel in aliases.csv")
    return f"aparte notering ({gat} weken ertussen) -- NIET samenvoegen"


def _mailtekst(
    nieuwe_weken: dict[tuple[str, int], list[int]], mislukt: list[str]
) -> tuple[str, str]:
    regels: list[str] = []
    totaal_nieuw = 0
    jaren = sorted({jaar for _, jaar in nieuwe_weken}) or [JAAR]
    with db.verbinding() as con:
        for lijst, cfg in LIJSTEN.items():
            treffers = [(j, w) for (l, j), weken in nieuwe_weken.items()
                        if l == lijst for w in weken]
            if not treffers:
                regels.append(f"{cfg['naam']}: geen nieuwe week")
                continue
            for jaar, week in sorted(treffers):
                binnenkomers = nieuwe_nummers(con, lijst, jaar, week)
                totaal_nieuw += len(binnenkomers)
                regels.append("")
                regels.append(
                    f"{cfg['naam']} -- {jaar} week {week}: {len(binnenkomers)} nieuw"
                )
                for r in binnenkomers:
                    label = f"  [{r['label']}]" if r["label"] else ""
                    status = "" if r["site_status"] == "nieuw" else f"  ({r['site_status']})"
                    regels.append(
                        f"   {r['positie']:>3}. {r['artiest']} - {r['titel']}{label}{status}"
                    )

    # Mislukte weken bovenaan en in het onderwerp. Zonder dit ziet een mislukking
    # er in de mail precies zo uit als "de site heeft nog niets nieuws", en dat
    # kan maanden onopgemerkt blijven -- de taak draait zonder venster.
    kop: list[str] = []
    if mislukt:
        kop.append(f"LET OP: {len(mislukt)} week/weken niet opgehaald:")
        kop += [f"   - {m}" for m in mislukt]
        kop.append("")
        kop.append(
            "Deze weken worden bij de volgende run vanzelf opnieuw geprobeerd."
        )
        kop.append("Blijft het misgaan, dan is de opmaak van de site waarschijnlijk")
        kop.append("gewijzigd; zie run.log voor de details.")
        kop.append("")

    stempel = "/".join(str(j) for j in jaren)
    onderwerp = f"Hitlijsten {stempel}: {totaal_nieuw} nieuwe nummers"
    if mislukt:
        onderwerp += f" -- {len(mislukt)} MISLUKT"

    tekst = "\n".join(kop + regels).strip() or "Geen nieuwe noteringen."
    return onderwerp, tekst


def opdracht_run(jaar: int, *, stuur_mail: bool = True) -> None:
    log("=" * 60)
    log("wekelijkse run gestart")
    try:
        nieuwe_weken, mislukt = opdracht_bijwerken(None)
        # Alleen bouwen voor jaargangen die daadwerkelijk data kregen; anders
        # laat een stille januari-run een lege jaarmap achter.
        bestanden = []
        # Aliassen en uitzonderingen zijn handwerk dat alleen in de database
        # bestaat, en die staat niet in git. Elke run schrijft daarom een verse
        # export naast de code, zodat er nooit meer dan een week tussen de
        # database en de kopie zit.
        try:
            from .migratie_csv import exporteer

            for pad in exporteer():
                log(f"geexporteerd: {pad.name}")
        except Exception as fout:            # nooit de run laten stranden
            log(f"export van aliassen mislukt: {fout}")

        # Voor het bouwen opschonen, niet erna: de bronnen leveren elke week
        # opnieuw een backtick of een "coldplay", en die hoort niet in de
        # Excel-bestanden terecht te komen.
        try:
            opdracht_opschonen(toepassen=True)
        except Exception as fout:            # nooit de run laten stranden
            log(f"opschonen mislukt: {fout}")

        for bouwjaar in sorted({j for _, j in nieuwe_weken}):
            bestanden += opdracht_excel(bouwjaar)
            # De PDF van die jaargang klopt nu niet meer; meteen vernieuwen,
            # anders staat er tot de volgende run een verouderd bestand.
            bestanden += opdracht_pdf(bouwjaar, altijd=True)
        onderwerp, tekst = _mailtekst(nieuwe_weken, mislukt)
        tekst += "\n\nBestanden:\n" + "\n".join(f"  {p}" for p in bestanden)
        if stuur_mail:
            mail.verstuur(onderwerp, tekst)
            log(f"mail verstuurd: {onderwerp}")
        else:
            log("mail overgeslagen (--geen-mail)")
            print("\n" + tekst)
    except Exception:
        fout = traceback.format_exc()
        log("RUN MISLUKT\n" + fout)
        if stuur_mail:
            try:
                mail.verstuur("Hitlijsten: run MISLUKT", fout)
            except Exception as maalfout:  # mail mag de fout niet maskeren
                log(f"foutmelding kon niet gemaild worden: {maalfout}")
        raise
    log("wekelijkse run klaar")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="hitlijsten", description=__doc__)
    # Zonder --jaar volgen we de jaargang die de site zelf publiceert.
    p.add_argument("--jaar", type=int, default=None)

    # --jaar mag ook NA de opdracht ("excel --jaar 2025"); dat is hoe je het
    # intypt. SUPPRESS zorgt dat een niet-opgegeven --jaar hier de waarde van
    # vooraan niet overschrijft.
    jaar_ouder = argparse.ArgumentParser(add_help=False)
    jaar_ouder.add_argument("--jaar", type=int, default=argparse.SUPPRESS)

    sub = p.add_subparsers(dest="opdracht", required=True)

    b = sub.add_parser("backfill", parents=[jaar_ouder],
                       help="alle weken van het jaar ophalen")
    b.add_argument("--vanaf", type=int, default=1)
    b.add_argument("--tot", type=int, default=None)

    sub.add_parser("bijwerken", parents=[jaar_ouder],
                   help="alleen ontbrekende weken ophalen")

    h = sub.add_parser("historie", help="complete jaargangen uit het archief ophalen")
    h.add_argument("--vanaf", type=int, default=None,
                   help="beginjaar; standaard het oudste dat elke site heeft")
    h.add_argument("--tot", type=int, default=None, help="eindjaar (standaard vorig jaar)")
    h.add_argument("--geen-excel", action="store_true",
                   help="alleen ophalen, Excel later bouwen")
    h.add_argument("--lijst", choices=sorted(LIJSTEN), default=None,
                   help="beperk tot een lijst (standaard alle vier)")
    sub.add_parser("excel", parents=[jaar_ouder],
                   help="Excel-bestanden opnieuw bouwen")
    jl = sub.add_parser("jaarlijks", parents=[jaar_ouder],
                        help="een jaarlijkse lijst inlezen uit een CSV")
    jl.add_argument("--lijst", required=True,
                    help="welke lijst, bv. top2000 of evergreen")
    jl.add_argument("--bestand", required=True, help="pad naar de CSV")
    pd = sub.add_parser("pdf", parents=[jaar_ouder],
                        help="de jaaroverzichten als PDF naar de jaarmappen")
    pd.add_argument("--alle", action="store_true",
                    help="alle jaargangen, niet alleen het opgegeven jaar")
    pd.add_argument("--opnieuw", action="store_true",
                    help="ook bestanden herbouwen die al actueel zijn")
    d = sub.add_parser("decennium",
                       help="het decenniumklassement van de Top 40 als Excel")
    d.add_argument("--decennium", type=int, default=None,
                   help="beginjaar (1970); zonder opgave alle decennia")
    c = sub.add_parser("controle", parents=[jaar_ouder],
                       help="rapport van verdachte dubbelingen")
    c.add_argument("--alle", action="store_true",
                   help="alle jaargangen in de database, niet alleen een jaar")

    k = sub.add_parser("kruiscontrole", parents=[jaar_ouder],
                       help="onze Top 40-cijfers vergelijken met michajans.nl")
    k.add_argument("--alle", action="store_true", help="alle jaargangen")

    ond = sub.add_parser("onderscheidingen",
                         help="Alarmschijven en Dancesmashes ophalen (michajans.nl)")
    ond.add_argument("--forceer", action="store_true", help="cache negeren")
    sub.add_parser("hersleutel", parents=[jaar_ouder],
                   help="sleutels opnieuw berekenen na aliases.csv")
    o = sub.add_parser("opschonen",
                       help="leestekens en schrijfwijzen rechtzetten")
    o.add_argument("--toepassen", action="store_true",
                   help="ook echt wegschrijven; zonder dit alleen melden")
    sub.add_parser("testmail", help="proefmail versturen")

    r = sub.add_parser("run", parents=[jaar_ouder], help="bijwerken + excel + mail")
    r.add_argument("--geen-mail", action="store_true")

    args = p.parse_args(argv)

    jaar = args.jaar if args.jaar is not None else JAAR

    if args.opdracht == "backfill":
        opdracht_backfill(jaar, args.vanaf, args.tot)
    elif args.opdracht == "bijwerken":
        opdracht_bijwerken(args.jaar)
    elif args.opdracht == "historie":
        opdracht_historie(
            args.vanaf,
            args.tot if args.tot is not None else JAAR - 1,
            bouw_excel=not args.geen_excel,
            alleen_lijst=args.lijst,
        )
    elif args.opdracht == "excel":
        opdracht_excel(jaar)
    elif args.opdracht == "jaarlijks":
        opdracht_jaarlijks(args.lijst, args.bestand, args.jaar)
    elif args.opdracht == "pdf":
        opdracht_pdf(None if args.alle else jaar, altijd=args.opnieuw)
    elif args.opdracht == "decennium":
        opdracht_decennium(args.decennium)
    elif args.opdracht == "controle":
        opdracht_controle(jaar, alle_jaren=args.alle)
    elif args.opdracht == "kruiscontrole":
        opdracht_kruiscontrole(jaar, alle_jaren=args.alle)
    elif args.opdracht == "onderscheidingen":
        opdracht_onderscheidingen(forceer=args.forceer)
    elif args.opdracht == "opschonen":
        opdracht_opschonen(toepassen=args.toepassen)
    elif args.opdracht == "hersleutel":
        opdracht_hersleutel(jaar)
    elif args.opdracht == "testmail":
        mail.verstuur(
            "Hitlijsten: proefmail",
            "Als je dit leest werkt de melding vanaf de pc via de mailrelay.",
        )
        log("proefmail verstuurd")
    elif args.opdracht == "run":
        opdracht_run(jaar, stuur_mail=not args.geen_mail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
