#!/bin/sh
# Zet het failover-blok terug als een DSM-upgrade /etc/nginx/conf.d heeft
# geleegd. Draait bij elke start van hitlijsten-standby (ExecStartPre), dus
# ook na de reboot die bij zo'n upgrade hoort. Zonder dit bestand wijzen de
# DSM-proxyregels naar een poort waar niemand luistert en ligt de site eruit.
#
# Idempotent en stil als er niets te doen valt.
BRON=/volume1/Hitlijsten/app/http.zz-hitlijsten.conf
DOEL=/etc/nginx/conf.d/http.zz-hitlijsten.conf

[ -f "$BRON" ] || exit 0
if [ ! -f "$DOEL" ] || ! cmp -s "$BRON" "$DOEL"; then
    sudo -n cp "$BRON" "$DOEL"
    sudo -n nginx -t >/dev/null 2>&1 && sudo -n nginx -s reload
    echo "failover-blok teruggezet in /etc/nginx/conf.d"
fi
exit 0
