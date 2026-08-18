#!/bin/sh
# De site tijdens onderhoud achter een nette pagina zetten, en er weer achter
# vandaan halen. Het omwisselen zelf regelt systemd via Conflicts= in
# hitlijsten-onderhoud.service; dit script is de leesbare voorkant.
#
#   ./onderhoud.sh aan [minuten]   bezoekers krijgen de onderhoudspagina (503)
#   ./onderhoud.sh uit             de webapplicatie draait weer
#   ./onderhoud.sh stand           wat draait er nu
#
# Zonder minuten blijft de pagina staan tot je hem uitzet. Geef je ze wel op,
# dan noemt de pagina de verwachte eindtijd en zet de dienst zichzelf terug --
# een vergeten onderhoudsstand is erger dan een paar minuten te vroeg terug.
set -e

HIER=$(cd "$(dirname "$0")" && pwd)
. "$HIER/omgeving.sh"
TOT="${HITLIJSTEN_DATA:-$HIER/data}/onderhoud-tot.txt"

case "$1" in
  aan)
    if [ -n "$2" ]; then
      date -d "+$2 minutes" +%Y-%m-%dT%H:%M:%S > "$TOT"
      echo "onderhoud tot $(cat "$TOT")"
    else
      rm -f "$TOT"
    fi
    sudo systemctl start hitlijsten-onderhoud
    sleep 1
    echo "onderhoudspagina staat aan"
    ;;
  uit)
    rm -f "$TOT"
    sudo systemctl start hitlijsten-web
    sleep 2
    echo "de webapplicatie draait weer"
    ;;
  stand)
    ;;
  *)
    echo "gebruik: $0 aan [minuten] | uit | stand" >&2
    exit 2
    ;;
esac

printf 'web        : %s\n' "$(systemctl is-active hitlijsten-web)"
printf 'onderhoud  : %s\n' "$(systemctl is-active hitlijsten-onderhoud)"
