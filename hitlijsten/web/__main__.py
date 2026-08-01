"""Start de webapplicatie.

    python -m hitlijsten.web            luistert op 0.0.0.0:8642
    python -m hitlijsten.web --poort 80xx

Op de NAS draait dit als dienst achter de reverse proxy van DSM; die regelt
HTTPS en het adres hitlijsten.hhaken.nl.
"""
from __future__ import annotations

import argparse

from .app import INSTELLINGEN, maak_app

STANDAARD_POORT = 8642


def main() -> None:
    p = argparse.ArgumentParser(prog="hitlijsten.web")
    p.add_argument("--poort", type=int, default=STANDAARD_POORT)
    p.add_argument("--adres", default="0.0.0.0")
    p.add_argument("--debug", action="store_true")
    args = p.parse_args()

    app = maak_app()
    print(f"[web] instellingen: {INSTELLINGEN}")
    print(f"[web] luistert op http://{args.adres}:{args.poort}")
    app.run(host=args.adres, port=args.poort, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
