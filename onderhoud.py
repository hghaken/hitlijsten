"""Een onderhoudspagina op de poort van de webapplicatie.

Waarom dit een eigen dienstje is en geen instelling in de reverse proxy: DSM
schrijft `/etc/nginx/sites-enabled/server.ReverseProxy.conf` bij elke wijziging
opnieuw uit `ReverseProxy.json`, dus een `error_page` die je daar met de hand
inzet is bij de volgende aanpassing weg. Bovendien kun je aan een bestaand
server-blok van buitenaf geen `location` toevoegen. Luistert er tijdens
onderhoud niemand op poort 8642, dan komt nginx niet verder dan zijn eigen
foutpagina -- die grijze Synology-pagina.

Dit serverje pakt die poort over zolang de applicatie stilstaat, zodat de
bezoeker een nette pagina krijgt in plaats van een gat. Het antwoordt op elk
adres met **503** en een `Retry-After`, zodat zoekmachines begrijpen dat het
tijdelijk is en de pagina niet in de plaats van de site komt te staan.

De banner wordt bij het starten in de pagina gebakken als data-URI: één
antwoord, geen vervolgverzoeken, dus het maakt niet uit dat er verder niets
draait.

    python onderhoud.py [--poort 8642] [--adres 0.0.0.0]
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import logging
import mimetypes
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HIER = Path(__file__).resolve().parent
PAGINA = HIER / "hitlijsten" / "web" / "static" / "onderhoud.html"
BANNER = HIER / "hitlijsten" / "web" / "static" / "banner.jpg"
FAVICON = HIER / "hitlijsten" / "web" / "static" / "favicon.png"
# Wie de onderhoudsstand aanzet schrijft hier de eindtijd neer (ISO-8601).
# Zo hoeft de systemd-unit geen argumenten te kennen: hij start altijd
# hetzelfde commando en de eindtijd komt uit het bestand.
# Dezelfde datamap als de applicatie (HITLIJSTEN_DATA uit omgeving.sh); de
# terugval op app/data komt uit config.py, zodat beide kanten hetzelfde
# bestand aanwijzen.
TOT = Path(os.environ.get("HITLIJSTEN_DATA") or HIER / "data") / "onderhoud-tot.txt"

# Een halve minuut: hetzelfde ritme als de meta-refresh in de pagina zelf.
WACHTTIJD = 30


def lees_eindtijd() -> dt.datetime | None:
    """Tot hoe laat het onderhoud duurt, of None als het open einde heeft."""
    try:
        tijd = dt.datetime.fromisoformat(TOT.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    return tijd if tijd > dt.datetime.now() else None


def bouw_pagina(eind: dt.datetime | None = None) -> bytes:
    """De pagina met de banner erin, klaar om onveranderd uit te sturen."""
    html = PAGINA.read_text(encoding="utf-8")
    if BANNER.exists():
        soort = mimetypes.guess_type(BANNER.name)[0] or "image/jpeg"
        data = base64.b64encode(BANNER.read_bytes()).decode("ascii")
        html = html.replace("BANNER", f"data:{soort};base64,{data}")
    else:
        # Zonder banner blijft de pagina werken; het verloop op de achtergrond
        # draagt hem prima. Een ontbrekend bestand mag geen dienst tegenhouden.
        html = html.replace('url("BANNER") center/cover no-repeat', "none")
        logging.warning("banner niet gevonden: %s", BANNER)
    if FAVICON.exists():
        data = base64.b64encode(FAVICON.read_bytes()).decode("ascii")
        html = html.replace("FAVICON", f"data:image/png;base64,{data}")
    if eind is not None:
        html = html.replace(
            "<!--TERUG-->",
            '<p class="terug">🕑 We verwachten om <b>'
            f'{eind:%H:%M}</b> weer online te zijn</p>')
    return html.encode("utf-8")


def geef_de_poort_terug() -> None:
    """De webapplicatie weer starten en daarmee zichzelf uitzetten.

    Er is op DSM geen `systemd-run` en geen `at`, dus de terugkeer moet uit
    dit proces zelf komen. `start hitlijsten-web` is genoeg: het Conflicts= in
    de unit stopt deze dienst als onderdeel van diezelfde opdracht. Met
    --no-block wacht dit proces niet op zijn eigen afscheid.
    """
    logging.info("onderhoudstijd voorbij, de webapplicatie mag weer")
    try:
        subprocess.run(["sudo", "-n", "systemctl", "--no-block", "start",
                        "hitlijsten-web"], check=True, timeout=30)
    except (subprocess.SubprocessError, OSError) as fout:
        # Blijft de onderhoudspagina staan, dan is dat vervelend maar niet
        # stuk: hij is met de hand uit te zetten. Zwijgend eindigen zou juist
        # een dienst achterlaten die niemand meer verwacht.
        logging.error("kon de webapplicatie niet starten: %s", fout)


class Onderhoud(BaseHTTPRequestHandler):
    server_version = "hitlijsten-onderhoud"
    sys_version = ""
    pagina = b""

    def _antwoord(self, met_inhoud: bool) -> None:
        self.send_response(503)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(self.pagina)))
        self.send_header("Retry-After", str(WACHTTIJD))
        # Anders houdt een tussenliggende cache de onderhoudspagina vast
        # nadat de site alweer draait.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if met_inhoud:
            self.wfile.write(self.pagina)

    def do_GET(self) -> None:      # noqa: N802  (naam ligt vast in de basisklasse)
        self._antwoord(True)

    def do_HEAD(self) -> None:     # noqa: N802
        self._antwoord(False)

    def do_POST(self) -> None:     # noqa: N802
        # Een formulier dat tijdens het onderhoud wordt verstuurd hoort ook
        # de pagina te zien en niet een 501 uit de basisklasse.
        self._antwoord(True)

    def log_message(self, formaat: str, *args) -> None:
        # De standaardlogregel gaat naar stderr en vult daarmee het journaal
        # met een regel per plaatje. Alleen het opstarten is interessant.
        pass


def main() -> None:
    kies = argparse.ArgumentParser(description=__doc__)
    kies.add_argument("--poort", type=int, default=8642)
    kies.add_argument("--adres", default="0.0.0.0")
    argumenten = kies.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    eind = lees_eindtijd()
    Onderhoud.pagina = bouw_pagina(eind)
    dienst = ThreadingHTTPServer((argumenten.adres, argumenten.poort), Onderhoud)
    logging.info("onderhoudspagina op %s:%s (%d bytes)",
                 argumenten.adres, argumenten.poort, len(Onderhoud.pagina))

    wekker = None
    if eind is not None:
        seconden = (eind - dt.datetime.now()).total_seconds()
        logging.info("de webapplicatie komt vanzelf terug om %s", f"{eind:%H:%M}")
        wekker = threading.Timer(seconden, geef_de_poort_terug)
        wekker.daemon = True
        wekker.start()

    try:
        dienst.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if wekker is not None:
            wekker.cancel()
        dienst.server_close()


if __name__ == "__main__":
    main()
