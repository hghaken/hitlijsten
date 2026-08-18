#!/bin/sh
# De site tijdens onderhoud achter een nette pagina zetten, en er weer achter
# vandaan halen. Het omwisselen zelf regelt systemd via Conflicts= in
# hitlijsten-onderhoud.service; dit script is de leesbare voorkant.
#
#   ./onderhoud.sh aan     bezoekers krijgen de onderhoudspagina (503)
#   ./onderhoud.sh uit     de webapplicatie draait weer
#   ./onderhoud.sh stand   wat draait er nu
set -e

case "$1" in
  aan)
    sudo systemctl start hitlijsten-onderhoud
    sleep 1
    echo "onderhoudspagina staat aan"
    ;;
  uit)
    sudo systemctl start hitlijsten-web
    sleep 2
    echo "de webapplicatie draait weer"
    ;;
  stand)
    ;;
  *)
    echo "gebruik: $0 aan|uit|stand" >&2
    exit 2
    ;;
esac

printf 'web        : %s\n' "$(systemctl is-active hitlijsten-web)"
printf 'onderhoud  : %s\n' "$(systemctl is-active hitlijsten-onderhoud)"
