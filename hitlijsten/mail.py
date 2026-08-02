"""Melding per mail na de wekelijkse run.

Alle instellingen komen uit `mail.ini` naast de code; dat bestand staat niet in
git. Zonder ontvanger doet deze module niets -- dat is met opzet: een standaard
adres in de broncode is precies het soort ding dat je vergeet aan te passen.

    [mail]
    host = mailserver.thuis
    poort = 25
    afzender = hitlijsten@voorbeeld.nl
    ontvanger = jij@voorbeeld.nl
    gebruiker =            ; leeg = geen aanmelding
    wachtwoord =
    starttls = nee
"""
from __future__ import annotations

import configparser
import smtplib
from email.message import EmailMessage
from email.utils import formatdate

from .config import ROOT

MAIL_INI = ROOT / "mail.ini"

STANDAARD = {
    "host": "localhost",
    "poort": "25",
    "afzender": "hitlijsten@localhost",
    "ontvanger": "",
    "gebruiker": "",
    "wachtwoord": "",
    "starttls": "nee",
}


def instellingen() -> dict[str, str]:
    waarden = dict(STANDAARD)
    if MAIL_INI.exists():
        parser = configparser.ConfigParser()
        parser.read(MAIL_INI, encoding="utf-8")
        if parser.has_section("mail"):
            waarden.update({k: v for k, v in parser.items("mail") if v is not None})
    return waarden


def verstuur(onderwerp: str, tekst: str, *, html: str | None = None) -> None:
    cfg = instellingen()
    if not cfg["ontvanger"]:
        # Liever hoorbaar niets doen dan post naar een leeg adres proberen.
        raise RuntimeError(
            f"geen ontvanger ingesteld; vul [mail] ontvanger in {MAIL_INI}")

    bericht = EmailMessage()
    bericht["Subject"] = onderwerp
    bericht["From"] = cfg["afzender"]
    bericht["To"] = cfg["ontvanger"]
    bericht["Date"] = formatdate(localtime=True)
    bericht.set_content(tekst)
    if html:
        bericht.add_alternative(html, subtype="html")

    with smtplib.SMTP(cfg["host"], int(cfg["poort"]), timeout=30) as server:
        server.ehlo()
        if cfg.get("starttls", "nee").strip().lower() in {"ja", "yes", "true", "1"}:
            server.starttls()
            server.ehlo()
        if cfg.get("gebruiker"):
            server.login(cfg["gebruiker"], cfg["wachtwoord"])
        server.send_message(bericht)
