# hitlijsten

Verzamelt wekelijks de vier Nederlandse hitlijsten en houdt zeven
jaarlijkse lijsten bij, bewaart ze in sqlite en
maakt er Excel-werkboeken en PDF's van. Het hele archief staat online op
**[hitlijsten.hhaken.nl](https://hitlijsten.hhaken.nl)**.

| Lijst | Bron | Archief |
|---|---|---|
| Nederlandse Top 40 | top40.nl | vanaf 1965 |
| Tipparade | top40.nl | vanaf 1967 |
| Oranje Top 30 | oranjetop30.nl | vanaf 2008 |
| Sterren NL Top 25 | top40.nl | vanaf 2019 |
| Top 2000 (NPO Radio 2) | datastats.nl | vanaf 1999 |
| Top 4000 (Radio 10) | datastats.nl | vanaf 2005 |
| Top 1000 (Veronica) | datastats.nl | vanaf 2003 |
| Q Top 1500 (Qmusic) | datastats.nl | vanaf 2005 |
| Evergreen Top 1000 (NPO Radio 5) | datastats.nl | vanaf 2008 |
| Rock Top 500 (Arrow) | datastats.nl | vanaf 2000 |
| Kink Top 1500 | datastats.nl | vanaf 2019 |

484.386 noteringen over elf lijsten: 7.541 weken en 143 jaaredities.
De namen en titels zijn opgeschoond en geverifieerd tegen MusicBrainz,
Discogs en Wikipedia; elke correctie staat met reden in een logboek. Draait op een Synology NAS: een
Flask-applicatie achter de reverse proxy, en een systemd-timer die elke vrijdag
om 22:00 de nieuwe week ophaalt.

Geschreven met hulp van **Claude Code**; alle commits dragen die
vermelding, en de overwegingen bij elke keuze staan in de commitberichten.

**De documentatie staat in [LEESMIJ.md](LEESMIJ.md)** — opzet, opdrachten,
ontwerpkeuzes en de valkuilen van de bronsites. De database zelf, tabel voor
tabel en kolom voor kolom, staat in [DATABASE.md](DATABASE.md).

## Licentie

De **code** staat onder de [MIT-licentie](LICENSE) — doe ermee wat je wilt, met
naamsvermelding en zonder garantie.

De **gegevens niet.** De noteringen zijn samengesteld door top40.nl en
oranjetop30.nl, en voor de jaarlijkse lijsten door NPO Radio 2, Radio 10,
Veronica, Qmusic, NPO Radio 5 en Arrow Classic Rock (verzameld via
[datastats.nl](https://www.datastats.nl/)). Die rechten liggen
bij hen en worden door deze licentie niet geraakt: dit project verzamelt en
toont hun werk, het claimt het niet. De database en de opgehaalde pagina's zitten
daarom ook niet in deze repository.

En verder: `lettertypen/DejaVuSans*.ttf` heeft zijn eigen, vrije licentie —
zie `lettertypen/LICENSE_DEJAVU`.
