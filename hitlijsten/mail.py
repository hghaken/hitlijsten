"""Melding per mail via de MailPlus-relay op de NAS.

De relay op 10.10.8.20 accepteert post vanaf het thuisnetwerk zonder wachtwoord.
Wil je dat later dichtzetten, vul dan gebruiker/wachtwoord in mail.ini; deze
module gebruikt ze zodra ze er staan.
"""
from __future__ import annotations

import configparser
import smtplib
from email.message import EmailMessage
from email.utils import formatdate

from .config import ROOT

MAIL_INI = ROOT / "mail.ini"

STANDAARD = {
    "host": "10.10.8.20",
    "poort": "25",
    "afzender": "hitlijsten@hhaken.nl",
    "ontvanger": "heye@hhaken.nl",
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
