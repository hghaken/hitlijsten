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
| Top 2000 (NPO Radio 2) | datastats.nl | vanaf 1999 |
| Evergreen Top 1000 (NPO Radio 5) | datastats.nl | vanaf 2008 |

255.482 noteringen over 7.541 weken. Draait op een Synology NAS: een
Flask-applicatie achter de reverse proxy, en een systemd-timer die elke vrijdag
om 22:00 de nieuwe week ophaalt.

Geschreven met hulp van **Claude Code**; alle achtendertig commits dragen die
vermelding, en de overwegingen bij elke keuze staan in de commitberichten.

**De documentatie staat in [LEESMIJ.md](LEESMIJ.md)** — opzet, opdrachten,
ontwerpkeuzes en de valkuilen van de bronsites.

## Licentie

De **code** staat onder de [MIT-licentie](LICENSE) — doe ermee wat je wilt, met
naamsvermelding en zonder garantie.

De **gegevens niet.** De noteringen zijn samengesteld door top40.nl en
oranjetop30.nl, en voor de jaarlijkse lijsten door NPO Radio 2 en NPO Radio 5
(verzameld via [datastats.nl](https://www.datastats.nl/)). Die rechten liggen
bij hen en worden door deze licentie niet geraakt: dit project verzamelt en
toont hun werk, het claimt het niet. De database en de opgehaalde pagina's zitten
daarom ook niet in deze repository.

En verder: `lettertypen/DejaVuSans*.ttf` heeft zijn eigen, vrije licentie —
zie `lettertypen/LICENSE_DEJAVU`.
