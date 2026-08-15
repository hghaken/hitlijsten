"""Het wekelijkse bericht op de Facebook-pagina.

De vrijdagrun haalt de nieuwe Top 40 op; deze module maakt daar een berichtje
van en zet het op de pagina. Alles komt uit `facebook.ini` naast de code, en
dat bestand staat niet in git -- er staat een token in waarmee iemand namens
de pagina kan schrijven.

    [facebook]
    pagina_id = 123456789012345
    token     = EAAG...                ; page access token, langlevend
    api       = v25.0                  ; optioneel
    link      = https://hitlijsten.hhaken.nl/weekbericht

**Zonder dat bestand doet deze module niets.** Dat is met opzet: publiceren is
naar buiten treden, en dat hoort niet te gebeuren doordat iemand toevallig de
code uitrolt. Wie het aanzet, zet het bewust aan.

Het token halen (eenmalig, in de browser -- niet iets wat een script kan doen):
zie BEHEER.md.
"""
from __future__ import annotations

import configparser
import sqlite3

import requests

from .config import ROOT

FACEBOOK_INI = ROOT / "facebook.ini"
HOOFD_URL = "https://hitlijsten.hhaken.nl"

STANDAARD = {
    "pagina_id": "",
    "token": "",
    "api": "v25.0",
    "link": HOOFD_URL + "/weekbericht",
}

# Meer dan dit maakt van een berichtje een lijstpagina, en die staat al op de
# site -- daar wijst de link naartoe.
MAX_BINNENKOMERS = 8


def instellingen() -> dict[str, str]:
    waarden = dict(STANDAARD)
    if FACEBOOK_INI.exists():
        parser = configparser.ConfigParser()
        parser.read(FACEBOOK_INI, encoding="utf-8")
        if parser.has_section("facebook"):
            waarden.update({k: v.strip() for k, v in parser.items("facebook")
                            if v is not None})
    return waarden


def is_ingesteld() -> bool:
    cfg = instellingen()
    return bool(cfg["pagina_id"] and cfg["token"])


def _regel(rij: sqlite3.Row) -> str:
    bel = " \U0001f514" if rij["alarmschijf"] else ""
    return f"{rij['positie']:>3}. {rij['artiest']} - {rij['titel']}{bel}"


def berichttekst(con: sqlite3.Connection, jaar: int, week: int) -> str | None:
    """Het bericht over één Top 40-week, of None als die week leeg is.

    Bewust kort. Wat hier staat moet iemand in de tijdlijn in twee tellen
    kunnen lezen; wie meer wil, klikt door naar het weekbericht op de site.
    """
    rijen = list(con.execute(
        "SELECT positie, vorige_positie, artiest, titel, weken_genoteerd,"
        " alarmschijf, site_status FROM noteringen"
        " WHERE lijst='top40' AND jaar=? AND week=? ORDER BY positie",
        (jaar, week)))
    if not rijen:
        return None

    top = rijen[0]
    regels = [f"Nederlandse Top 40 — week {week} van {jaar}", ""]

    # weken_genoteerd telt weken IN de lijst, niet weken op 1. Dat verschil
    # moet uit de zin blijken, anders staat er straks dat een plaat twaalf
    # weken op 1 staat terwijl hij er pas twee weken bovenaan staat.
    weken = top["weken_genoteerd"] or 0
    erbij = f" ({weken}e week in de lijst)" if weken > 1 else ""
    if top["vorige_positie"] == 1:
        regels.append(f"\U0001f947 Nog steeds op 1: "
                      f"{top['artiest']} - {top['titel']}{erbij}")
    else:
        regels.append(f"\U0001f947 Nieuw op 1: "
                      f"{top['artiest']} - {top['titel']}{erbij}")

    binnen = [r for r in rijen
              if r["vorige_positie"] is None and r["site_status"] != "terug"]
    getoond = binnen[:MAX_BINNENKOMERS]
    if binnen:
        regels += ["", f"Nieuw binnen ({len(binnen)}):"]
        regels += [_regel(r) for r in getoond]
        if len(binnen) > MAX_BINNENKOMERS:
            regels.append(f"     ... en nog {len(binnen) - MAX_BINNENKOMERS}")

    met_vorige = [r for r in rijen if r["vorige_positie"] is not None]
    if met_vorige:
        stijger = max(met_vorige,
                      key=lambda r: r["vorige_positie"] - r["positie"])
        sprong = stijger["vorige_positie"] - stijger["positie"]
        # Een sprong van één plek is geen nieuws; dan liever niets melden.
        if sprong >= 3:
            regels += ["", f"\U0001f4c8 Grootste stijger: {stijger['artiest']} - "
                           f"{stijger['titel']}, van {stijger['vorige_positie']} "
                           f"naar {stijger['positie']}"]

    terug = [r for r in rijen
             if r["vorige_positie"] is None and r["site_status"] == "terug"]
    if terug:
        namen = ", ".join(f"{r['artiest']} - {r['titel']}" for r in terug[:3])
        regels += ["", f"↩️ Terug in de lijst: {namen}"]

    # Alleen uitleggen wat er ook echt staat: het belletje hangt aan de
    # getoonde binnenkomers, niet aan de hele lijst.
    if any(r["alarmschijf"] for r in getoond):
        regels += ["", "\U0001f514 = Alarmschijf"]

    regels += ["", "De hele lijst, alle wisselingen en het archief vanaf 1965:",
               f"{HOOFD_URL}/weekbericht?jaar={jaar}&week={week}"]
    return "\n".join(regels)


def plaats(tekst: str, link: str | None = None) -> str:
    """Zet het bericht op de pagina. Geeft het id van het bericht terug.

    De link gaat als apart veld mee, niet alleen als tekst: dan maakt Facebook
    er een voorbeeldkaartje van met de banner en de omschrijving van de site,
    en dat valt in een tijdlijn meer op dan een kale regel.
    """
    cfg = instellingen()
    if not (cfg["pagina_id"] and cfg["token"]):
        raise RuntimeError(
            f"geen pagina_id/token ingesteld; vul [facebook] in {FACEBOOK_INI}")

    antwoord = requests.post(
        f"https://graph.facebook.com/{cfg['api']}/{cfg['pagina_id']}/feed",
        data={"message": tekst,
              "link": link or cfg["link"],
              "access_token": cfg["token"]},
        timeout=30)
    uitkomst = antwoord.json()
    if "id" not in uitkomst:
        # De boodschap van Facebook zelf is bruikbaarder dan een HTTP-code:
        # hij noemt het verlopen token of de ontbrekende rechten bij naam.
        fout = uitkomst.get("error", {})
        raise RuntimeError(
            f"Facebook weigerde het bericht: "
            f"{fout.get('message', antwoord.text)[:300]}")
    return uitkomst["id"]
