# hitlijsten

Verzamelt wekelijks de vier Nederlandse hitlijsten en houdt zeventien
jaarlijkse lijsten bij, bewaart ze in sqlite en
maakt er Excel-werkboeken en PDF's van. Het hele archief staat online op
**[www.nl-hitlijsten.nl](https://www.nl-hitlijsten.nl)**.

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
| 90's Top 500 (Qmusic) | datastats.nl | vanaf 2010 |
| Toplijst van de jaren 60 (NPO Radio 5) | datastats.nl | vanaf 2010 |
| Toplijst van de jaren 70 (NPO Radio 5) | datastats.nl | vanaf 2010 |
| Zomer Top 500 (Qmusic) | datastats.nl | vanaf 2012 |
| Q Zeroes Top 500 (Qmusic) | datastats.nl | vanaf 2013 |
| 80's Top 810 (Radio 10) | datastats.nl | vanaf 2014 |
| Festival Top 1003 (NPO Radio 3FM) | datastats.nl | vanaf 2018 |
| Kink 80's Top 500 | datastats.nl | vanaf 2021 |
| Sublime Soul Top 1000 (Sublime) | datastats.nl | vanaf 2021 |
| De Koninklijke 500 (NPO Radio 2) | datastats.nl | vanaf 2022 |
| 80's Top 500/750/880/1000 (Veronica) | hitdossier-online.nl | vanaf 2005 |

555.239 noteringen over tweeëntwintig lijsten: 7.549 weken en 272 jaaredities.
De namen en titels zijn opgeschoond en geverifieerd tegen MusicBrainz,
Discogs en Wikipedia; elke correctie staat met reden in een logboek. Elk
nummer draagt bovendien zijn Alarmschijf-belletje (bron: top40.nl) en een
Nederlandstalig-markering met filter. Voor bezoekers: artiestpagina's, een
datumprikker ("wat stond er op 1 op jouw geboortedag?"), records, versies,
een jaargang-vergelijker, een wekelijks weekbericht met RSS-feed dat ook de andere drie weeklijsten
samenvat en elke vrijdag automatisch op de
[Facebook-pagina](https://www.facebook.com/nederlandsehitlijsten) verschijnt,
een gastenboek, **DJ Export** (laad je VirtualDJ- of rekordbox-database en
download elke lijst als playlist uit je eigen bibliotheek, met een
rapport en een boodschappenlijst van wat ontbreekt), een
handleiding-PDF in twee talen en een NL/EN-taalkeuze die de hele site
dekt, van lijstpagina's tot disclaimer. Draait op een Synology NAS: een
Flask-applicatie op waitress achter de reverse proxy, en een systemd-timer die elke vrijdag
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
oranjetop30.nl, en voor de jaarlijkse lijsten door NPO Radio 2, NPO 3FM,
NPO Radio 5, Radio 10, Veronica, Qmusic, Sublime, Arrow Classic Rock en
KINK (verzameld via
[datastats.nl](https://www.datastats.nl/)). Die rechten liggen
bij hen en worden door deze licentie niet geraakt: dit project verzamelt en
toont hun werk, het claimt het niet. De database en de opgehaalde pagina's zitten
daarom ook niet in deze repository.

En verder: `lettertypen/DejaVuSans*.ttf` heeft zijn eigen, vrije licentie —
zie `lettertypen/LICENSE_DEJAVU`.
