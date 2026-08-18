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
import logging
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HIER = Path(__file__).resolve().parent
PAGINA = HIER / "hitlijsten" / "web" / "static" / "onderhoud.html"
BANNER = HIER / "hitlijsten" / "web" / "static" / "banner.jpg"

# Een halve minuut: hetzelfde ritme als de meta-refresh in de pagina zelf.
WACHTTIJD = 30


def bouw_pagina() -> bytes:
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
    return html.encode("utf-8")


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
    Onderhoud.pagina = bouw_pagina()
    dienst = ThreadingHTTPServer((argumenten.adres, argumenten.poort), Onderhoud)
    logging.info("onderhoudspagina op %s:%s (%d bytes)",
                 argumenten.adres, argumenten.poort, len(Onderhoud.pagina))
    try:
        dienst.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        dienst.server_close()


if __name__ == "__main__":
    main()
