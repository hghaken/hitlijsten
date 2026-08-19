"""Start de webapplicatie.

    python -m hitlijsten.web            luistert op 0.0.0.0:8642
    python -m hitlijsten.web --poort 80xx
    python -m hitlijsten.web --debug    ontwikkelserver, herlaadt bij wijziging

Op de NAS draait dit als dienst achter de reverse proxy van DSM; die regelt
HTTPS en het adres www.nl-hitlijsten.nl.

WAAROM WAITRESS, EN WAAROM ÉÉN PROCES
-------------------------------------
De ingebouwde server van Flask is een ontwikkelhulpje: hij zegt het zelf bij
elke start, en hij is niet gebouwd om aan het open internet te staan. Waitress
is dat wel, draait op alles (pure Python, geen compileerwerk op de NAS) en
vraagt geen configuratiebestand.

Belangrijker is het aantal processen. Deze applicatie houdt dingen in het
geheugen die per bezoeker of per installatie gelden: de geladen
DJ Export-bibliotheken (`_vdj_sessies`), de rem op mislukte aanmeldingen en
een handvol caches. Met meerdere worker-processen zou een bezoeker zijn
database in het ene proces laden en bij de volgende klik in het andere
belanden -- dan is de DJ Export-knop de ene keer wel en de andere keer niet
bruikbaar. Waitress draait daarom in één proces met meerdere **draden**: die
delen hun geheugen, dus alles blijft vindbaar, en gelijktijdige bezoekers
worden gewoon naast elkaar bediend.
"""
from __future__ import annotations

import argparse

from .app import INSTELLINGEN, maak_app

STANDAARD_POORT = 8642
STANDAARD_DRADEN = 8


def main() -> None:
    p = argparse.ArgumentParser(prog="hitlijsten.web")
    p.add_argument("--poort", type=int, default=STANDAARD_POORT)
    p.add_argument("--adres", default="0.0.0.0")
    p.add_argument("--draden", type=int, default=STANDAARD_DRADEN,
                   help="gelijktijdige verzoeken (één proces, gedeeld geheugen)")
    p.add_argument("--debug", action="store_true",
                   help="ontwikkelserver van Flask; nooit op de NAS")
    args = p.parse_args()

    app = maak_app()
    print(f"[web] instellingen: {INSTELLINGEN}")

    if args.debug:
        # Het sessiecookie draagt in productie `Secure` en gaat dus alleen
        # over HTTPS. Op de ontwikkelmachine is er geen HTTPS, en zonder deze
        # uitzondering kun je je niet aanmelden en houdt een geladen
        # DJ Export-bibliotheek het geen twee klikken vol. Alleen hier, nooit
        # in het pad dat de NAS gebruikt.
        app.config["SESSION_COOKIE_SECURE"] = False
        print(f"[web] ONTWIKKELSERVER op http://{args.adres}:{args.poort}"
              " (sessiecookie zonder Secure)")
        app.run(host=args.adres, port=args.poort, debug=True, threaded=True)
        return

    try:
        from waitress import serve
    except ImportError:
        # Beter draaien dan stilstaan, maar het moet wel opvallen.
        print("[web] LET OP: waitress ontbreekt (pip install waitress) --"
              " terugval op de ontwikkelserver van Flask")
        app.run(host=args.adres, port=args.poort, threaded=True)
        return

    print(f"[web] waitress op http://{args.adres}:{args.poort}"
          f" ({args.draden} draden, één proces)")
    serve(
        app,
        host=args.adres,
        port=args.poort,
        threads=args.draden,
        # Dezelfde grens als Flask hanteert, maar dan al bij de voordeur:
        # een te grote upload wordt geweigerd voordat hij is ingelezen.
        max_request_body_size=app.config["MAX_CONTENT_LENGTH"],
        # Geen versienummers in de Server-kop.
        ident="hitlijsten",
    )


if __name__ == "__main__":
    main()
