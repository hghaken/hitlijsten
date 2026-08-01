# hitlijsten

Verzamelt wekelijks de vier Nederlandse hitlijsten, bewaart ze in sqlite en
maakt er Excel-werkboeken en PDF's van. Het hele archief staat online op
**[hitlijsten.hhaken.nl](https://hitlijsten.hhaken.nl)**.

| Lijst | Bron | Archief |
|---|---|---|
| Nederlandse Top 40 | top40.nl | vanaf 1965 |
| Tipparade | top40.nl | vanaf 1967 |
| Oranje Top 30 | oranjetop30.nl | vanaf 2008 |
| Sterren NL Top 25 | top40.nl | vanaf 2019 |

255.482 noteringen over 7.541 weken. Draait op een Synology NAS: een
Flask-applicatie achter de reverse proxy, en een systemd-timer die elke vrijdag
om 22:00 de nieuwe week ophaalt.

**De documentatie staat in [LEESMIJ.md](LEESMIJ.md)** — opzet, opdrachten,
ontwerpkeuzes en de valkuilen van de bronsites.

De noteringen zijn samengesteld door top40.nl en oranjetop30.nl; de rechten
liggen bij hen. Deze code verzamelt en toont hun gegevens.
