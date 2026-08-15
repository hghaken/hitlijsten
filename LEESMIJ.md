# Hitlijsten verzamelen

Haalt elke week de vier hitlijsten op, schrijft ze naar Excel en PDF, mailt wat
er nieuw binnenkwam, en zet zestig jaar archief online op
**[hitlijsten.hhaken.nl](https://hitlijsten.hhaken.nl)**.

| Lijst | Bron | Lengte | Archief vanaf |
|---|---|---|---|
| Nederlandse Top 40 | top40.nl/top40 | 40 | 1965 |
| Tipparade | top40.nl/tipparade | 30 | 1967 (± week 28) |
| Sterren NL Top 25 | top40.nl/sterren-nl-top25 | 25 | 2019 (week 40) |
| Oranje Top 30 | oranjetop30.nl | 30 | 2008 |
| Top 2000 (NPO Radio 2) | CSV (Music Datastats) | 2000 | 1999 |
| Evergreen Top 1000 (NPO Radio 5) | CSV (Music Datastats) | 1000 | 2008 |
| Top 4000 (Radio 10) | CSV (Music Datastats) | 4000 | 2005 |
| Top 1000 (Veronica) | CSV (Music Datastats) | 1000–3000 | 2003 |
| Q Top 1500 (Qmusic) | CSV (Music Datastats) | 1000–1500 | 2005 |
| Rock Top 500 (Arrow) | CSV (Music Datastats) | 500 | 2000 |
| Kink Top 1500 | CSV (Music Datastats) | 1500 | 2019 |

De archiefdieptes zijn gemeten, niet aangenomen — zie *Oude jaargangen ophalen*.
Waar elke lijst begint, met de nummer 1 van de oudste week die we hebben:

| Lijst | Oudste notering | Nummer 1 |
|---|---|---|
| Nederlandse Top 40 | 1965 week 1 | The Beatles — I Feel Fine |
| Tipparade | 1967 week 28 | Golden Earrings — Sound Of The Screaming Day |
| Oranje Top 30 | 2008 week 1 | Jan Smit — Dan volg je haar benen |
| Sterren NL Top 25 | 2019 week 40 | Marco Borsato, Armin van Buuren & Davina Michelle — Hoe Het Danst |
| Top 2000 | editie 1999 | Queen — Bohemian Rhapsody |
| Evergreen Top 1000 | editie 2008 | Elvis Presley — Are You Lonesome To-night |

## Waar het draait

Dit is een hobbyproject dat op een NAS in een meterkast draait; de precieze
opstelling — adressen, mappen, systemd-units, de mailrelay — staat in
`BEHEER.md`, dat bewust niet in deze repository zit.

Wat je moet weten om de code te begrijpen:

| | |
|---|---|
| Python | 3.14, eigen venv |
| Webapplicatie | Flask op **waitress** (één proces, acht draden), achter een reverse proxy |
| Wekelijkse run | een systemd-timer, vrijdagavond |
| Paden | via `HITLIJSTEN_DATA`, `HITLIJSTEN_CACHE` en `HITLIJSTEN_EXCEL` |
| Pakketten | zie [requirements.txt](requirements.txt): requests, beautifulsoup4, lxml, openpyxl, Flask, waitress, defusedxml, fpdf2 |

De code staat los van de gegevens: de database, de cache en de Excel-bestanden
liggen naast de broncode, niet erin. Zo kun je de code in zijn geheel vervangen
zonder de database aan te raken. Zonder die omgevingsvariabelen valt alles terug
op de projectmap zelf, wat handig is om lokaal te ontwikkelen.

## Stand van zaken

- **Het hele archief staat in de database**: 539.163 noteringen over
  eenentwintig lijsten. Top 40
  1965–2026 (62 jaargangen), Tipparade 1967–2026 (60), Oranje Top 30 2008–2026
  (19), Sterren NL 2019–2026 (8), Top 2000 1999–2025 (27 edities), Top 4000
  2005–2025 (21), Veronica Top 1000 2003–2025 (23), Q Top 1500 2005–2025 (21),
  Evergreen Top 1000 2008–2025 (18), Rock Top 500 2000–2025 (26) en
  Kink Top 1500 2019–2025 (7).
- 591 Excel-bestanden en 292 PDF-jaaroverzichten gebouwd, plus 651 aliassen,
  267 vastgelegde niet-bestaande weken en 4.044 onderscheidingen.
- De wekelijkse run staat ingepland op **vrijdag 22:00**, als systemd-timer
  `hitlijsten-run.timer`. Eerstvolgende keer: vrijdag 7 augustus 2026.

## Wat er uitkomt

Een map per decennium, daarin een map per jaargang, daarin per lijst drie
bestanden — twee werkboeken en een PDF:

```
<hitlijsten>/excel/
  1960-1969/ ... 2010-2019/
  2020-2029/
    Top40_Decennium_2020-2029.xlsx
    2020/ ... 2025/
    2026/
      Top40_2026.xlsx          Top40_Jaar_2026.xlsx        Top40_2026.pdf
      Tipparade_2026.xlsx      Tipparade_Jaar_2026.xlsx    Tipparade_2026.pdf
      SterrenNL_2026.xlsx      SterrenNL_Jaar_2026.xlsx    SterrenNL_2026.pdf
      OranjeTop30_2026.xlsx    OranjeTop30_Jaar_2026.xlsx  OranjeTop30_2026.pdf
```

Op de NAS ook via Samba te bereiken; zie `BEHEER.md`.

Met zestig jaargangen Top 40 zouden zestig mappen naast elkaar onwerkbaar zijn,
vandaar de tussenlaag.

Bijvoorbeeld voor de Top 40:

**`Top40_2026.xlsx`**
- `Week 01`, `Week 02`, … — per week de **complete lijst**, waarin de nummers die
  dit jaar nieuw binnenkomen een **lichtblauwe rij** krijgen
- `Totaal` — per nummer punten, hoogste positie, aantal weken, en de datum van
  binnenkomst en laatste notering

**`Top40_Jaar_2026.xlsx`**
- `Jaaroverzicht` — matrix: rij = nummer, kolom = week, cel = positie

### Wat "nieuw" betekent

Op een weektab staat de hele lijst van die week, op positie gesorteerd, met
`Vorige positie` erbij. **Lichtblauw** gemarkeerd zijn de nummers waarvan de
sleutel dit jaar niet eerder in díé lijst voorkwam. Op de tab van week 1 is
daardoor alles gemarkeerd; daarna alleen echte nieuwkomers.

De markering loopt over de volle rijbreedte, zodat je met een oogopslag ziet wat
er binnenkwam zonder de rest van de lijst kwijt te raken.

De kolom **Site-status** zegt wat de site er zelf van vindt: `nieuw`, `terug`
(re-entry), `stijger`, `daler`, `gelijk`. Zo zie je het verschil tussen een echte
binnenkomer en een nummer dat al liep toen wij begonnen met verzamelen.

### Van weeknummer naar uitzenddatum

De Top 40 werd op **vrijdag** uitgezonden en op zaterdag gepubliceerd. In de
`Totaal`-tab en op het jaaroverzicht staan daarom echte datums (`dd/mm/yyyy`) in
plaats van weeknummers, in Excel als datumwaarde zodat je erop kunt sorteren en
rekenen. De omrekening staat in `hitlijsten/datums.py`.

**De regel**: week N van jaar J is de **N-de zaterdag van dat jaar**; de
uitzending was de vrijdag ervoor. Die regel is niet bedacht maar gemeten aan 3798
koppels van (jaar, week) en datum uit michajans.nl, verspreid over vijftien
jaargangen tussen 1965 en 2025: 99,9% klopt. De voor de hand liggende ISO-week
haalt op dezelfde koppels maar 65% — in 1965 loopt de nummering een week voor.

**Twee dingen vallen daardoor buiten het jaar, en allebei terecht:**

1. Begint een jaar op zaterdag, dan is de vrijdag van week 1 de **31e december
   van het jaar ervoor**. Dat gebeurt in negen jaargangen: 1966, 1972, 1977,
   1983, 1994, 2000, 2005, 2011 en 2022.
2. Een notering die **over de jaarwisseling doorloopt** begint of eindigt in het
   buurjaar. Een jaarbestand ziet daar maar de helft van, dus zoekt
   `db.looptijden()` de rest op in de aangrenzende jaargangen. In de Excel staat
   dan *begon vorig jaar* of *loopt door* in de kolom **Loopt over jaargrens**;
   op het jaaroverzicht een ◀ of ▶ bij de datum.

De reeks stapt daarbij naar de vorige of volgende week die **daadwerkelijk is
uitgezonden**, niet botweg zeven dagen terug. De Top 40 slaat de laatste week van
december meestal over voor een jaaroverzicht — bij negentien van de tweeënzestig
jaargangen. Zou de reeks zeven dagen eisen, dan brak hij juist op de jaargrens
waar het hier om begonnen is. Een gat waarin de lijst wél verscheen maar het
nummer niet, breekt de reeks wel: dat is een re-entry, geen doorloper.

### Punten

Punten per notering = `lijstlengte − positie + 1`, waarbij de lengte **per week**
wordt bepaald uit de data zelf. In de Top 40 levert #1 dus 40 punten en #40 één
punt; in de Sterren NL Top 25 levert #1 vijfentwintig punten.

Per week rekenen is geen omslachtigheid: de Tipparade telde in 1968 twintig
noteringen en in 1969 vijfentwintig. Punten zijn daardoor **niet vergelijkbaar
tussen lijsten** — #1 in de Top 40 is 40 punten, #1 in Sterren NL 25.

### Het decennium

De webapplicatie heeft naast het jaaroverzicht een tabblad **Decennium**: alle
nummers uit tien jaargangen, op punten. Dat is er **alleen voor de Top 40**, en
dat is geen luiheid. De Top 40 is zijn hele bestaan veertig noteringen lang
(nagemeten: alle 3184 weken sinds 1965), dus een punt uit 1968 en een punt uit
2024 wegen precies evenveel. Bij de Tipparade zou optellen over tien jaar
betekenis­loos zijn: daar was #1 het ene jaar twintig punten waard en het andere
jaar dertig.

De punten worden **per jaargang gerekend en daarna opgeteld**, niet in één keer
over tien jaar. Zo blijft de decenniumlijst exact de som van de
jaaroverzichten — ook waar een jaartotaal van michajans.nl wordt aangehouden
(zie *Wie wint bij een verschil*). Datums blijven binnen het decennium; loopt de
notering erbuiten door, dan staat er een ◀ of ▶ waarmee je naar dat decennium
springt, net als bij de jaargangen.

### De totaallijst

Het tabblad **Top 40 totaal** is dezelfde som, maar over alle jaargangen:
ruim **15.000 nummers** van 1965 tot nu, met Pharrell Williams' *Happy* bovenaan
(1449 punten over 49 weken in 2013–2014). Nagerekend over alle nummers: punten,
weken en hoogste positie zijn exact gelijk aan de som van de zeven
decenniumlijsten.

Die lijst in zijn geheel op één pagina zetten is 11 MB HTML, en dat rendert geen
enkele browser prettig. Daarom staat er een keuze boven de tabel — top 100, 500,
1000 (standaard), 2500 of alles — en zit de **volledige** lijst altijd in de
Excel — die bouwen duurt op de NAS een seconde of tien. De berekening zelf kost
een halve seconde over 127.000 noteringen en wordt gecached tot er nieuwe data
bij komt.

De **⤓ Excel**-knop naast de dropdown levert `Top40_Decennium_1970-1979.xlsx`:
één tab met hetzelfde klassement. Dat werkboek wordt bij het downloaden ter
plekke gemaakt en komt dus niet uit de wekelijkse run — het kost een fractie van
een seconde en kan zo nooit achterlopen op de database. Wil je ze wél op schijf,
in de decenniummappen naast de jaarmappen:

```bash
python -m hitlijsten.cli decennium                  # alle decennia
python -m hitlijsten.cli decennium --decennium 1970 # alleen de jaren zeventig
```

De totaallijst kent geen bestand op schijf — die haal je op met de knop.

### De jaarlijkse lijsten

De vier weeklijsten komen van een website. De zeventien jaarlijkse lijsten —
van de Top 2000 en de Top 4000 tot de Festival Top 1003, de Sublime Soul
Top 1000 en de Toplijsten van de jaren 60 en 70 — zijn één
uitzending per jaar en komen binnen als CSV van Music
Datastats ([datastats.nl](https://www.datastats.nl/)) — een matrix met een regel
per nummer en een kolom per editie.

```bash
python -m hitlijsten.cli jaarlijks --lijst top2000  --bestand .../top2000.csv
python -m hitlijsten.cli jaarlijks --lijst evergreen --bestand .../evergreen.csv
```

Op het **overzicht** staan ze in een eigen tabel, en in de keuzelijst van het
jaaroverzicht in een eigen groep. Dat is niet alleen netjes: de kolom die bij
een weeklijst "weken" heet telt hier edities, en een lijst van tweeduizend naast
een van dertig nodigt uit tot vergelijkingen die nergens op slaan.

Alle lijsten met `jaarlijks` in hun definitie lopen door hetzelfde bestand
(`hitlijsten/jaarlijks.py`), dus **een lijst toevoegen is een regel in
`config.LIJSTEN` en één keer importeren** — geen nieuwe code. In dezelfde map staat er nog één klaar: de Rock Top 500.

Elke editie wordt weggeschreven als jaargang met **week 52**, de week van de
uitzending. Daardoor werken de sleutels, het jaaroverzicht en de database
zonder uitzondering mee. In de lijstdefinitie staat `site: None`; daaraan
herkent de wekelijkse run dat hij deze lijst met rust moet laten.

**Wat er niet in past is de weekmatrix.** Binnen een jaargang is er één meting,
dus "positie per week" zou een tabel van één kolom worden, en punten
(lijstlengte − positie + 1) zijn niets anders dan de omgekeerde positie. Deze
lijst krijgt daarom een eigen pagina: de editie met *vorige editie*, *verschil*,
*aantal edities* en *hoogste ooit*, en daaronder de matrix **nummer × editie**
— precies de vorm van de bron. Klikken op een artiest of titel opent dezelfde
grafiek als bij de weeklijsten, maar dan met een punt per editie in plaats van
per week; de server zegt in het veld `as` welke van de twee het is.

**De verticale schaal hangt af van de lengte van de lijst.**

Bij een **weeklijst** loopt hij van 1 tot de lengte van de lijst, lineair. Elke
plek is een stap, 1 en 2 staan dicht bij elkaar, en de schaal hangt aan de lijst
en niet aan het nummer — zo oogt een nummer dat tussen 1 en 3 schommelde niet
net zo grillig als een dat van 1 naar 40 zakte.

Bij een **lange lijst** houdt dat geen stand. Een nummer dat tussen 22 en 970
beweegt beslaat op een schaal van 1 tot 4000 een twintigste van de hoogte: een
vlakke streep bovenin met driekwart van de grafiek leeg. Boven de honderd loopt
de schaal daarom **logaritmisch van de beste tot de slechtste positie van dat
nummer zelf**. De hulplijnen dragen de echte positienummers — de randen van het
bereik plus de machten van tien die ertussen vallen — dus je kunt nog steeds
aflezen waar je naar kijkt.

De prijs is dat twee van die grafieken niet meer zonder meer naast elkaar te
leggen zijn: elk nummer heeft zijn eigen bereik. Bij lijsten van duizenden
noteringen weegt het kunnen zien van het verloop zwaarder dan die
vergelijkbaarheid; bij de weeklijsten is het andersom.

**Een overgeslagen editie is een eigen geval.** Van de 4927 nummers hebben er
1358 een gat in hun reeks — "Dolce Vita" van Ryan Paris miste er twintig. Dat
wordt op drie plekken getoond:

- in de **matrix** met een `–`, dus zichtbaar anders dan een lege cel (die
  betekent: hoorde er toen nog niet of niet meer in);
- in de **grafiek** blijft de overgeslagen editie een lege kolom, met een
  stippellijn over het gat — net als een re-entry bij de weeklijsten;
- in de **editietabel** met *terug sinds 2021* in plaats van *nieuw*. Dat
  onderscheid is niet klein: van de 127 nummers in de editie van 2025 zonder
  notering in 2024 waren er 74 echt nieuw en 53 terug van weggeweest. Die matrix toont standaard de top 250; 2000 rijen maal 27 kolommen maakt de
pagina anders 5 MB. Bij een editie van meer dan tweeduizend regels wordt ook de
tabel zelf afgetopt — de Top 4000 gaat daarmee van 2,9 naar 1,7 MB. Kortere
lijsten blijven compleet.

**De sleutel is de brug naar de andere lijsten.** Artiest en titel gaan door
dezelfde `sleutel_van()`, dus "Golden Earring — Radar Love" krijgt overal
dezelfde sleutel. Van de 4927 Top 2000-nummers delen er **3043** een sleutel met
de andere lijsten (2865 Tipparade, 2734 Top 40, 80 Oranje, 37 Sterren NL); van
de 2620 Evergreen-nummers **1812** (1555 Top 2000, 963 Top 40, 902 Tipparade).
De rest zijn grotendeels albumnummers die nooit als single noteerden.

**Niet alles wat scheef staat is kapot.** De controle scheidt fouten van
waarschuwingen: een fout betekent dat de bron van vorm veranderd is en er niets
geïmporteerd moet worden, een waarschuwing is een schoonheidsfoutje in verder
goede data. In de Evergreen van 2013 staan twee nummers op 279 en ontbreekt 278
— een typefout bij de bron. Dat wordt gemeld en verder genegeerd; achttien
jaargangen laten vallen om één verkeerd cijfer zou onzin zijn. Meer dan een
procent scheef is wél een fout. De lengte komt per editie uit de data zelf, en dat is geen theorie: de Veronica
Top 1000 was tweeëntwintig jaar lang precies duizend en werd in 2025 ineens
drieduizend, en de Q Top 1500 heette negentien jaar lang ten onrechte zo — die
was tot en met 2023 duizend lang. In de configuratie is `lengte`
voor deze lijsten dan ook een bovengrens en geen verwachting.

Nog niet gedaan: Excel en PDF voor deze lijst. Die bouwers gaan uit van weken en
punten, dus die hebben een eigen vorm nodig.

## De webapplicatie

**https://hitlijsten.hhaken.nl** — dezelfde gegevens als de Excel-bestanden,
maar doorzoekbaar en zonder download. Draait als systemd-dienst `hitlijsten-web`
op de NAS, achter een reverse proxy.

**Vrij toegankelijk:**

| Pagina | Wat je er ziet |
|---|---|
| Overzicht | wat er in de database zit, in twee tabellen: weeklijsten en jaarlijkse lijsten — die laatste **per zender gegroepeerd** (zenderkolom, afgeleid uit de lijstnaam via `zender_van()`); dezelfde groepjes vullen de optgroups van de lijst-keuzelijsten |
| Jaaroverzichten | puntenklassement en de matrix positie-per-week, per lijst en jaargang, met bladerknoppen langs de jaargangen; ook een **binnenkomers-vinkje** (nummers die dat jaar voor het éérst in de lijst verschenen — over de hele historie gerekend, dus Last Christmas telt alleen in 1984) |
| Selecties & downloads | overal dezelfde spelregels: keuzelijst top 100/500/1000/2500/alles (standaard 100; onder de 250 nummers geen keuzelijst maar meteen alles; opties vanaf de lijstlengte vervallen en het traag-label staat alleen boven de 2500 regels), de filters NL en binnenkomers, en **wat op het scherm staat, zit in het bestand** — Excel en PDF volgen de selectie met `_topN`/`_NL`/`_nieuw` in de bestandsnaam én, sinds augustus 2026, met een **FILTER-regel ín het stuk** (bij de PDF in de ondertitel onder de banner, bij Excel als eerste zin van de toelichting boven de tabel); een doorgestuurd of uitgeprint bestand draagt zijn bestandsnaam immers niet meer, en zes regels waar er veertig horen roept dan vragen op; op "alles" zonder filter komen de rijke voorgebouwde jaarwerkboeken met weektabs, en de matrix-downloads blijven altijd volledig |
| Decennia | het puntenklassement over tien jaargangen Top 40, met bladerknoppen langs de decennia |
| Top 40 totaal | hetzelfde over alle jaargangen 1965–nu |
| Zoeken | op artiest, titel of beide; `*` als jokerteken; `artiest \| titel` zoekt op allebei tegelijk (bij nul treffers met meerdere woorden stelt de pagina die schrijfwijze klikbaar voor); klik springt naar de jaargang van de hoogste notering — openbaar, net als de nummerpagina's (de bewerkkant blijft achter de login) |
| Artiest | eigen pagina per artiest (±13.600): alle nummers over alle lijsten heen, met carrière-spanne, hoogste posities en nummer-1-teller; bereikbaar via artiestnamen op de nummer- en zoekpagina's |
| Jouw dag | datumprikker: kies je geboortedag of trouwdag en zie de Top 40 die toen gold, met de nummer 1 groot in beeld; op de homepage staat "X jaar geleden op 1" voor deze week door de decennia heen |
| DJ Export (VirtualDJ & rekordbox) | laad éénmalig je `database.xml`, een **rekordbox-collectie-export** (xml, herkend aan de DJ_PLAYLISTS-wortel) of — makkelijker — de **backup-zip** van VirtualDJ (Instellingen → Backup; met de volledige database erin, ook van losse schijven), plus je voorkeuren (streaming/netsearch wel of niet, bestandssoort — standaard alleen audio, want een mp4 wint anders elke bitrate-vergelijking — en matching-strengheid in vier niveaus, waarbij duet-credits als "Meat Loaf & Ellen Foley" tegen "Meat Loaf" al op niveau strak matchen); daarna verschijnt op elke weeklijst, elk jaaroverzicht, de decennia en de beide totaallijsten een **⤓ DJ Export-knop** die de getoonde selectie — top-keuze en filters incluis — als playlist oplevert in het formaat dat bij de geladen bron past: `.vdjfolder` bij een VirtualDJ-upload, `.m3u8` bij een rekordbox-upload (te importeren in rekordbox/Engine DJ/Traktor/Serato — de route naar Pioneer/Denon-hardware loopt via die software), met rapport en boodschappenlijst van wat ontbreekt; lokaal bestand wint van streaming, hoogste bitrate bij dubbelen; de database leeft alleen tijdens je bezoek in het geheugen (max. 4 uur) en raakt nooit een schijf |
| Tweetalig | NL/EN-knop rechtsboven naast Aanmelden (cookie `taal`, route `/taal/<code>`); de menubalk, footer, alle lijstpagina's en DJ Export zijn vertaald via `web/vertalingen.py` (NL-tekst als sleutel, Nederlands als vangnet) plus taal-condities voor lange proza-blokken; de **disclaimer** is volledig tweetalig (taal-conditie in het sjabloon; de Nederlandse versie is leidend) en de **handleiding bestaat in twee talen** (`handleiding.pdf` + `manual.pdf`, de vrijdagrun bouwt beide, de menubalk-knop kiest op taal); sinds fase 2 zijn ook **alle specials** vertaald (zoeken, jouw dag, weekbericht, records, versies, vergelijk, wetenswaardigheden, nummer-/artiestpagina's, gastenboek, feedback en de grafiek-uitleg); de titels die uit Python komen (records- en wetenswaardigheden-blokken) lopen via hetzelfde woordenboek, met Nederlands als vangnet voor samengestelde uitlegzinnen; ook de **RSS-feed** is tweetalig (`weekbericht.rss?taal=en` — de taal zit in de URL omdat feedlezers geen cookies sturen; de feed-link op de pagina geeft hem door); alleen het beheer blijft Nederlands |
| Handleiding | de complete gebruiksaanwijzing voor bezoekers als PDF in de huisstijl, **in twee talen** (`/static/handleiding.pdf` NL + `/static/manual.pdf` EN; de menubalk-knop kiest op taalcookie; de **vrijdagrun herbouwt beide** met verse tellerstanden uit de database; met de hand: `python -m hitlijsten.handleiding`), met een eigen DJ Export-hoofdstuk |
| Records | de klappers over alle lijsten en jaargangen heen: meeste weken genoteerd, meeste weken op 1, grootste sprong en diepste val, langste terugkeer, eenhitwonders op 1, langste carrière, meeste hits en de trouwste jaarlijst-klanten |
| Versies | dezelfde titel door verschillende artiesten — covers, heropnames en soms naamgenoten, gesorteerd op aantal uitvoeringen |
| Vergelijk | twee jaargangen van dezelfde lijst naast elkaar: kerngetallen (incl. het Nederlandstalig-aandeel), de hoogst genoteerde nummers van elk jaar, en wat er in allebei stond |
| Verras me | het dobbelsteentje achteraan de tweede menuregel, naast het Gastenboek: een willekeurig nummer, gewogen naar noteringen |
| Weekbericht | de nieuwste Top 40 samengevat (nummer 1, binnenkomers, grootste stijger/daler, terugkeerders, uitvallers), bladerbaar per week en te volgen via de **RSS-feed** `/weekbericht.rss` — schrijft zichzelf uit de vrijdagrun |
| Weeklijsten | één week zoals uitgezonden, met week-keuzelijst, de extra keuze **Alle weeklijsten** (de vier onder elkaar, elk met eigen kop en posities; Excel krijgt dan een tab per lijst, de PDF de vier **doorlopend** onder elkaar — een nieuwe pagina alleen als het niet meer past, want met het nieuw-filter zijn vier hele pagina's voor zeventien binnenkomers verspilling — en de DJ Export één playlist met dubbelen eruit), bladeren over de jaargrens heen (een overgeslagen kerstweek wordt overgeslagen) en de nieuw/terug-spelden; het **nieuw-vinkje** betekent hier de binnenkomers van de wéék zelf (het groene speldje), niet de jaargang-binnenkomers |
| Zoeklinks | YouTube- en Spotify-icoontje bij elk nummer, dezelfde als op de Ots Radio-webplayer |
| Alarmschijf | rood belletje 🔔 vóór de titel op de Top 40-weeklijsten; het belletje van top40.nl zelf (klasse `hitrecord`), per plaat vastgelegd in `noteringen.alarmschijf` en elke vrijdagrun bijgehouden; michajans.nl blijft de bron voor de toekenningsdatum |
| Nederlandstalig | rood-wit-blauw vlaggetje voor de titel, op elke lijstpagina én de wetenswaardigheden óók als filter (checkbox "NL"; de weetjes-ranglijsten rekenen zichzelf dan opnieuw uit over alleen Nederlandstalig, en de ter-plekke gebouwde Excel- en PDF-downloads filteren mee, met `_NL` in de bestandsnaam); herkenning in drie trappen — lijstbewijs (Oranje/Sterren NL zijn per definitie Nederlandstalig), artiestroute en titel-woordenlijst — met handmatige correctie op de nummerpagina die altijd wint |
| Jaarlijsten totaal | alle zeventien jaarlijkse lijsten samen, genormaliseerd: elke notering telt (lengte − positie + 1) ÷ lengte, dus de nummer 1 van élke lijst is één punt waard |
| Beheer | alles wat de opdrachtregel kan, ook als knop — plus **Bijwerken wat veranderd is** (alleen de geraakte jaargangen), voortgangsbalken per stap, en een taakstand die een herstart overleeft |
| Wetenswaardigheden | tien ranglijsten over de hele historie, per lijst |
| Gastenboek | gepubliceerde bezoekersberichten, met eventueel een antwoord van de beheerder eronder |
| Bericht achterlaten | formulier voor opmerkingen, tips, bugs en aanvullingen; spamwering met honeypot, invultijd en per-IP-limiet, geen CAPTCHA; alles komt privé binnen en niets staat live zonder akkoord |
| Berichten | (achter de login) de postbus: publiceren, privé houden, verwijderen of beantwoorden; mailmelding bij elk nieuw bericht |
| Disclaimer | hobbyproject, bekende zwakke plekken, rechten, privacy; volledig tweetalig, en het contact-blok verwijst naar het feedbackformulier (geen klikbaar mailadres meer op de site) |
| Vormgeving | menubalk in twee rijen (de lijsten boven, de extra's en het beheer gedempt eronder), doorschijnend over de banner en met blur zodra er gescrold is; tabellen tot 100 rijen krijgen hun volle hoogte (geen binnenste scrollbalk), daarboven een scrollvak van 78vh; onder de 760px compact en niet-plakkend |
| Banner | eigen ontwerp, vast aan de bovenrand achter de doorzichtige menubalk (die dichtgaat na scrollen); dezelfde banner siert de kop van elke PDF en is de og:image van gedeelde links |
| Vindbaarheid | sitemap-index in twee delen (±50.000 pagina's incl. artiesten, gecachet), `robots.txt`, meta-descriptions, canonical-links, Open Graph-tags en JSON-LD structured data (MusicRecording, MusicGroup, ItemList) |

**Achter het wachtwoord** (staat in `app/webapp.ini`, niet in git): zoeken,
aliassen, uitzonderingen, vrije SELECT-query's, beheer (opnieuw ophalen, Excel
herbouwen) en het logboek van alle wijzigingen.

Klikken op een artiest of titel opent de **grafiek** van de positie per week.
Die volgt de hele notering, ook als die over de jaarwisseling loopt, met een
streep waar de jaargang wisselt. De ◀/▶-pijltjes bij de datums springen naar de
jaargang of het decennium waar de rest van de notering staat, met het nummer
daar alvast opgelicht.

Wachtwoord wijzigen: pas `wachtwoord` in `app/webapp.ini` aan en herstart de
dienst met `sudo systemctl restart hitlijsten-web`.

### De disclaimer

`/disclaimer` staat rechtsboven in de kop en onderaan in de bronvermelding. Hij
noemt niet alleen dat het een hobbyproject is, maar ook **wat er concreet mis
kan gaan** — de sleutel die een nummer kan splitsen, de punten die onze eigen
berekening zijn, de uitzenddatums die afgeleid zijn uit een gemeten regel, en
fouten in de bron zelf. Een disclaimer die alleen "aan deze gegevens kunnen geen
rechten worden ontleend" zegt, helpt niemand.

Verder: de rechten liggen bij de omroepen en de sites, met een verzoek om
contact op te nemen als iemand iets verwijderd wil zien (via het
feedbackformulier — sinds augustus 2026 staat er geen klikbaar mailadres
meer op de site, ook tegen adres-oogstende bots); en wat er van de
bezoeker wordt bijgehouden. Dat laatste is nagekeken en niet aangenomen — er
staat geen enkel script van een andere partij in de sjablonen, er wordt één
cookie gezet en alleen bij het aanmelden, en de webserver houdt een gewone
toegangslog bij.

### Terug kunnen

`wijzigingen` schrijft op wát er is veranderd, van wat naar wat en waarom. Dat
is een logboek en **geen terugdraaiknop**: een samenvoeging van duizenden
noteringen staat er als één regel, en daar bouw je de oude toestand niet uit
terug. Voor "even terug naar hoe het vanmorgen was" heb je het hele bestand
nodig.

`momentopnames.py` maakt dat bestand, met `VACUUM INTO` en niet met `cp` — dat
werkt binnen één transactie en kan dus terwijl de webapplicatie erin leest. Door
gzip komt 91 MB op 24 MB uit, in vijf seconden.

Alles hieronder kan ook **zonder opdrachtregel**, via de knoppen op de
beheerpagina — inclusief terugzetten, met een keuzelijst van wat er bewaard is
en een bevestiging die zegt wat je kwijtraakt.

```
python -m hitlijsten momentopname            # er een maken
python -m hitlijsten momentopname --lijst    # zien wat er staat
python -m hitlijsten momentopname --terug 20260802-125424-voor-opschonen.sqlite.gz
```

Er wordt er automatisch een gemaakt vóór de wekelijkse run en vóór
`opschonen --toepassen`. Terugzetten maakt er zelf ook een van de huidige
toestand — teruggaan is óók een ingreep, en die wil je net zo goed ongedaan
kunnen maken als blijkt dat je de verkeerde hebt gekozen. Bewaard blijven de
laatste twaalf plus van elke dag de oudste, tot dertig dagen terug.

**Dit is geen back-up.** Het staat op dezelfde schijf. Tegen een verkeerde
opdracht helpt het, tegen een kapot volume niet — daarvoor is er het
snapshotschema van de NAS, dat sinds 2 augustus 2026 ook op deze share staat.
De twee vullen elkaar aan: een snapshot bewaart de hele share en overleeft een
verwijderde map, deze kopieën zitten er juist in en gaan met één knop terug.

### Opschonen

De bronnen zijn niet schoon, en dat zie je pas als je eenentwintig lijsten naast elkaar
legt. `opschonen.py` spoort vier soorten fouten op, met een oplopend risico:

| Soort | Gevonden | Beslist door |
|---|---|---|
| Leestekens | 3.344 schrijfwijzen, 32.399 noteringen | een regel |
| Lidwoord ("The Beatles" / "Beatles") | 349 artiesten, 21.833 sleutels | MusicBrainz |
| Spatiëring ("ACDC" / "AC/DC") | 61 artiesten | MusicBrainz |
| Typefouten in namen en titels | 31 artiesten, 86 nummers | MusicBrainz + Wikipedia |
| Onmogelijke uitgavejaren | 47 nummers | de Top 40 zelf |
| Titels met twee schrijfwijzen | 1.544 nummers, 13.905 noteringen | een regel |
| Uitgave voor het nummer | 24 titels | een regel |
| Dubbele A-kanten | 210 nummers, 1.817 noteringen | een regel |
| Dubbele haken | 225 nummers, 1.703 noteringen | een regel |
| Eén samenwerkingscredit (feat./ft./featuring/x/komma/met → &) | 2.796 namen, ~30.000 noteringen | regels met beschermlijsten |
| Gastartiest uit de titel naar de artiest | 2 nummers | een smalle regel |
| Versies die een plek deelden (jaren 60) | 19 nummers, 269 noteringen | woordvergelijking + Discogs |
| ///-schrijfwijzen en /-hernoemingen | 21 + 16 gevallen | MusicBrainz, Discogs, hoezen |
| Ondertitel achter een streepje → tussen haken | 321 titels | versie-/themawoorden |

**Eén credit-stijl.** De bronnen schrijven een samenwerking op vijf manieren
(feat., feat, ft., ft, featuring) plus de x, de komma en het Nederlandse "met".
Alles wordt **&** — in de weergave én in de sleutel, zodat "Calvin Harris feat.
Rihanna" en "Calvin Harris & Rihanna" dezelfde artiest zijn. De beschermlijsten
zijn opgezocht en niet bedacht: alle 401 komma-namen zijn aan MusicBrainz
voorgelegd (26 echte bandnamen als Earth, Wind & Fire), de x kijkt naar zijn
buren (Lil Nas X, X Ambassadors), en "met" kent zijn zinsdelen (met dank aan,
met medewerking van) en zijn actnamen (Zondag Met Lubach, Fokko Met De
Bordjes).

**De dubbele haken** zijn de manier waarop Music Datastats naamgenoten uit
elkaar houdt: `Asia ((GBR))` naast `Asia ((NLD))`, `Nirvana ((USA))` naast
`Nirvana ((GBR))`, `Amber ((= Marie Claire Cremers))`. Dat onderscheid is echt
en blijft staan — alleen de tweede haak is nergens voor nodig. De sleutel
verandert er niet van, want die gooit leestekens toch al weg.

**De dubbele A-kant.** In de jaren zestig en zeventig kwamen er singles uit met
twee kanten die allebei gedraaid werden en allebei de lijst haalden. top40.nl
zet die in één regel met een puntkomma: `"No Reply ; Rock And Roll Music"`. Voor
een DJ zijn dat twee nummers, en zo staan ze nu ook in de database — twee
noteringen op dezelfde positie:

```
1965 wk 18   #9  The Beatles - Eight Days A Week
1965 wk 18   #9  The Beatles - Baby's In Black
```

Het schema kon dit al aan: twee noteringen op één positie bestonden al bij de
Tipparade, die echte gedeelde posities kent. **De positie telt één keer**: beide
nummers krijgen de punten van die ene plek en dus hetzelfde totaal, precies wat
de officiële jaarlijst de single toekent. In het jaaroverzicht staan ze naast
elkaar als gelijkspel. De verificatie tegen de officiële jaarlijst blijft
overeind, want sinds 2020 komt er geen dubbele A-kant meer voor.

Staat er ook in de artiest een puntkomma en zijn het er evenveel, dan horen ze
bij elkaar: "De Dijk ; The Scene" levert De Dijk bij de eerste titel en The
Scene bij de tweede. Klopt het aantal niet, dan krijgen beide kanten de hele
naam — dat is vaker een samenwerking dan een tweede uitvoerende.

**Een conventie van top40.nl** die de andere lijsten niet kennen: bij een EP of
album met een leadtrack schrijven ze de uitgave ervoor, met een
spatie-dubbelepunt-spatie ertussen. `">Abort, Retry, Fail?_ : Your Woman"`,
`"Ballad Of The Streets EP : Belfast Child"`, `"Live! : Roll Over Lay Down"`.
Dat splitst een nummer: *Your Woman* van White Town stond tien keer onder de
lange titel en twee keer onder de korte, met een eigen sleutel en verdeelde
punten. De uitgave gaat eraf en er komt een alias bij, zodat de notering
samenvalt met dezelfde titel in de andere lijsten.

**Het uitgavejaar heeft een ijkpunt dat beter is dan een catalogus: de eigen
Top 40.** Een nummer kan niet uitkomen nadat het genoteerd stond. Over de 6.004
nummers die zowel een uitjaar van Music Datastats als een Top 40-notering
hebben, staat het uitjaar in **94,7%** van de gevallen precies gelijk aan het
jaar van de eerste notering, en in 98,3% gelijk of eerder — het enige bereik dat
kan. De 33 die er *na* lagen zijn teruggezet op het jaar van hun eerste Top
40-notering. Daar zaten grove gevallen bij: *Space Oddity* van David Bowie stond
volgens de bron uit 1975 terwijl het in 1969 al in de Top 40 stond.

**De sleutel is waar het pijn doet.** Een verkeerd leesteken is lelijk maar
onschuldig: de sleutel gooit leestekens toch al weg. Erger is wat de sleutel
wél raakt. "Beatles" en "The Beatles" leverden twee gescheiden geschiedenissen
op, en "Crocodille Rock" naast "Crocodile Rock" splitste één nummer in tweeën —
met verdeelde punten en twee halve noteringen in de jaarlijst.

**Twee fouten in de normalisatie zelf** kwamen bij dit werk boven water. De
eerste: een lidwoord vooraan de artiestnaam telde mee, terwijl de bronnen het er
niet over eens zijn (top40.nl schrijft "The Beatles", Music Datastats schrijft
"Beatles"). De tweede: `normaliseer()` haalt accenten weg door letters te
ontleden — é wordt e plus een tekentje — maar de ø van Bløf is een eigen letter.
Die overleefde de ontleding en werd daarna als rommel geschrapt, waarna "Bløf"
als "bl f" naast "Blof" stond. Nu vertaald, samen met æ, ß, ł en een stuk of tien
andere.

**Eén schrijfwijze per artiest én per titel.** Dat tweede was er eerst niet, en
dat viel meteen op: "Beggin" van Madcon in de Top 40 naast "Beggin'" in de Top
4000 — één nummer volgens de sleutel, twee regels in het zoekscherm. Bij een
titel telt een **apostrof** mee als bewijs ("Dont Speak" verliest van "Don't
Speak"), bij een artiestnaam juist niet: Shakespears Sister en Dexys Midnight
Runners schrijven zich er echt zonder. En een titel die helemaal uit kleine
letters bestaat leent zijn hoofdletters van een gelijknamig nummer elders in de
database — zo werd Sandra van Nieuwlands "beggin'" alsnog "Beggin'".

**Drie strepen betekenen iets anders dan een.** top40.nl zet met `///` twee
schrijfwijzen van dezelfde notering achter elkaar: `Ella///Ella (TROS Tune)`,
`The Source///The Course`. Daar valt niets te splitsen — het is één notering —
maar er moet wel gekozen worden. `corrigeer_nummer()` voert zo'n keuze door met
alles wat erbij hoort: sleutel herberekenen, alias leggen, naam vastleggen,
jaargangen markeren, logboekregel.

En de juiste keuze is niet altijd de canonieke titel. Georgie Fame stond met
`Yeah, Yeah///Yeah, Yeh, Yeh` in de Top 40 van 1965. Het nummer heet *Yeh, Yeh*,
maar de **Nederlandse uitgave** heette *Yeah, Yeh, Yeh* — net als die in
Denemarken, Duitsland, Zwitserland en Zuid-Afrika, allemaal gebaseerd op de
Britse demoplaat. *Yeah, Yeah* was de foute eerste Britse persing. Voor een
Nederlandse hitlijst telt de Nederlandse uitgavetitel.

**Vier soorten streep, vier betekenissen.** De bronnen gebruiken de schuine
streep voor van alles, en het ziet er telkens hetzelfde uit:

| Vorm | Betekent meestal | Wat ermee gebeurt |
|---|---|---|
| `A / B` bij artiest én titel | twee opnamen op één plek | splitsen (17 gevallen, 1965–1972) |
| `A / B` alleen bij de titel | de uitgave voor het nummer | de uitgave eraf (24) |
| `A /// B` | dezelfde notering, twee schrijfwijzen | kiezen (21) |
| `A // B` | van alles | per geval (18) |

Die laatste is de lastigste, want daar zit élke betekenis in: een verminkte naam
(`Tino//Martin`), een remix die de notering overnam (`Love Tonight // Love
Tonight - David Guetta Remix`), twee opnamen die een plek deelden (`Ein Bißchen
Frieden // Een Beetje Vrede`) — en twee gevallen waar de dubbele streep gewoon
in de naam hoort. Discogs crediteert *This Is What You Came For* zelf als
**Calvin Harris // Rihanna**, en Outlandish' single heet echt *Warrior //
Worrier*. Daar viel niets te repareren.

**De Discogs-sleutel.** De zoek-API werkt zonder sleutel op 25 verzoeken per
minuut; met een persoonlijke token (gratis, discogs.com → Settings →
Developers) wordt dat 60. De token staat in `discogs.ini` naast `webapp.ini` en
`mail.ini` — buiten git, en zonder het bestand werkt alles gewoon, alleen
langzamer.

**Twee catalogi, twee vragen.** MusicBrainz is een catalogus van *nummers*,
Discogs een van *platen* — en dat verschil beslist welke je nodig hebt:

- **Een titel** is wat er op het Nederlandse label stond. Georgie Fame's
  *Yeh, Yeh* verscheen hier als *Yeah, Yeh, Yeh*, en Albert Hammonds
  *Air Disaster* heette op de Benelux-persing *I Don't Wanna Die In An Air
  Disaster* terwijl de VS en Japan de korte titel gebruikten. Discogs kent het
  land van uitgave; daar win je het.
- **Een artiest** is een identiteit, want daarop herkennen we hem over de
  lijsten heen. Dan telt de act zoals de catalogus hem kent en niet de credit
  op één persing. Discogs zet een sterretje achter zo'n afwijkende credit:
  `The Source*`, `Nicole McCloud*`, `M.A.*`, `Future's World Orchestra*` — vier
  gevallen die daarmee in één keer opgelost waren. Dat *The Course* de goede was
  bleek meteen: die verenigt zeven noteringen over 1996–1998.

Klein Nederlands repertoire staat bovendien wél in Discogs en niet in
MusicBrainz. Gaby Dirne presents: The Valentino's, de Buddy's, Harm Duimstra —
compleet met hoes.

**Waarom een externe bron.** Bij "Dexys Midnight Runners" tegen "Dexy's Midnight
Runners" helpt tellen niet: je moet weten hoe de band heet.
[MusicBrainz](https://musicbrainz.org/) is een catalogus met precies dat veld,
open en zonder sleutel, en Wikipedia is de tweede mening bij Nederlandse
artiesten. `muziekbron.py` houdt zich aan één verzoek per seconde, zet alles op
schijf en bewaart een mislukking **niet** — een 503 die als antwoord in de cache
belandt ziet er later uit als "die artiest bestaat niet".

**Wat er niet gebeurt.** Lijken is niet hetzelfde als zijn, en dat is geen
theorie:

- *The Unforgiven I*, *II* en *III* van Metallica lijken op elkaar en zijn drie
  nummers. De wachtregel: twee schrijfwijzen die ooit in dezelfde week van
  dezelfde lijst stonden worden nooit samengevoegd.
- **Roy Dekkers** (Oranje Top 30, 2012) is niet **Roxy Dekker** (Top 40, 2023),
  al schelen ze twee letters. **D:ream** is niet **Dream**, **Reunion** (1974)
  is niet **Re-Union** (2004), **R.O.O.S.** is niet **Roos** en **Pennywise**
  is niet **Penny Wise**. Die vijf staan met naam en reden in de code.
- 273 "dubbele posities" in de Tipparade bleken echt: in maart 1971 deelden
  **acht versies van *Love Story*** plek 23.
- 306 artiesten houden meer dan één schrijfwijze omdat er geen regel voor te
  maken is. Die blijven met rust; ze staan in `opschonen --toepassen` netjes
  geteld.

**De sleutel volgt de naam.** Een valkuil die pas opvalt als je hem al hebt
getrapt: de sleutel wordt uit de naam berekend, en `artiestnamen` verandert die
naam. "ACDC" werd "AC/DC", en de sleutel die je daaruit berekent is "ac dc" en
niet "acdc" — dus de eerstvolgende herberekening trok de zojuist samengevoegde
artiest weer uit elkaar. `verzeker_aliassen()` legt daarom een alias van de oude
sleutel naar de sleutel die uit de vastgestelde naam volgt, en verplaatst de
noteringen mee. Daarna is `hersleutel` onschadelijk: drie rondes achter elkaar
verandert er niets meer.

De richting doet ertoe. Andersom aliassen — de naam volgt de sleutel — lijkt ook
te werken tot er een verouderde naamregel blijkt te staan. Er stond er een op
`bl f`, de kapotte sleutel van vóór de letterregel, en die trok Bløf daar zo
weer naartoe.

**Elke correctie staat in `wijzigingen`**, met de oude waarde, de nieuwe en de
reden. Zonder dat logboek is een correctie niet te onderscheiden van wat de bron
zelf leverde, en dat is precies wat je later wilt kunnen nazoeken.

De vastgestelde schrijfwijze per artiest staat in de tabel `artiestnamen`.
Zonder die tabel zou de vrijdagrun de correctie de week erop weer ongedaan maken
— de bron blijft immers "coldplay" schrijven. Daarom draait `opschonen` ook mee
in de wekelijkse run, vóór het bouwen van de Excel-bestanden.

```
python -m hitlijsten opschonen              # alleen melden
python -m hitlijsten opschonen --toepassen  # doorvoeren
```

### Wetenswaardigheden

Tien ranglijsten per lijst, in `wetenswaardigheden.py`: meeste
noteringen, meeste nummer 1-hits, meeste weken, meeste punten, langst genoteerd,
langst op 1, hoogste binnenkomers, grootste sprong in één week, langste weg naar
de eerste plaats en langste terugkeer. Met een keuzelijst bovenaan; **elke lijst
kan erdoorheen**, ook de jaarlijkse.

De tien blokken staan **ingeklapt**; tien tabellen van tien regels onder elkaar
is een muur. In de kop van elk blok staat wel de nummer 1, zodat de pagina
dichtgeklapt ook iets vertelt, en één knop klapt ze allemaal open.

**Weken of edities.** Een jaarlijkse lijst rekent hetzelfde — een editie ligt
gewoon als één punt op dezelfde kalender — maar praat anders. "Langst genoteerd,
26 weken" is bij de Rock Top 500 geen afrondingsfout maar onzin; daar staat
"vaakst in de lijst, 26 edities". De woordenlijst `_TAAL` houdt die twee uit
elkaar, zodat de berekeningen eronder er niets van hoeven te weten, en de datums
worden jaartallen: de Top 2000 van 2024 is "2024" en niet "27/12/2024".

Eén blok is inhoudelijk anders, niet alleen in woorden. *Meeste nummer 1-hits*
telt verschillende nummers die de top haalden — bij de Top 40 een ranglijst met
De Beatles op 13, bij de Top 2000 zes artiesten met allemaal precies één. Voor
de jaarlijkse lijsten telt dat blok daarom **edities op 1**: Queen 22, Eagles 2.
Regels met een nul vallen weg, anders staat de Kink Top 1500 vol artiesten die
er nooit een hadden.

Alles komt uit **één doorloop** over de noteringen. Dat is geen zuinigheid maar
noodzaak: de meeste vragen ("hoe vaak kwam dit terug?", "wat was de grootste
sprong?") hebben de reeks per nummer op volgorde nodig, en die bouw je maar één
keer op. De uitkomst wordt per lijst gecached tot er data bij komt.

Drie dingen die de cijfers kleuren, en die ook op de pagina staan:

- **Een samenwerking telt als een eigen artiest.** "Lady Gaga & Bruno Mars" is
  hier niet Lady Gaga én Bruno Mars. Uit elkaar trekken lijkt aantrekkelijk,
  maar dan sneuvelen Simon & Garfunkel en Earth, Wind & Fire ook.
- **Weken worden langs de kalender geteld**, niet per jaargang; een notering over
  de jaarwisseling is één periode.
- **De allereerste week van 1965 telt niet als binnenkomst** — toen was de hele
  lijst nieuw.

Twee ranglijsten die voor de hand lagen zijn er *niet*, omdat de data ze niet
draagt: "vaakst teruggekeerd" en "in de meeste jaargangen" lopen allebei dood op
respectievelijk 2 en 4, want de Nederlandse Top 40 zet klassiekers zelden
opnieuw op de lijst (Wham's *Last Christmas* stond er alleen in 1984 en 1985).
Daarvoor in de plaats: **langste terugkeer**, en daar zit wél spreiding in — Kate
Bush' *Running Up That Hill* kwam na zesendertig jaar terug.

### Het jaaroverzicht als PDF

De knop **⤓ PDF** op het jaaroverzicht levert het puntenklassement als A4:
gekleurde banner en voetregel, verder zwart op wit, **veertig regels per
pagina**. Kolommen: nummer, artiest, titel, punten, hoogste positie, weken,
binnenkomst en laatste notering, met een ‹ of › als de notering buiten het jaar
doorloopt. Werkt voor alle vier de lijsten en alle jaargangen; het bestand wordt
bij het downloaden gemaakt en kan dus nooit achterlopen.

De bestanden **staan klaar op schijf**, naast de Excel van diezelfde jaargang:
`Top40_1975.pdf` in `1970-1979/1975/`. De jaargangen tot en met 2025 zijn
afgesloten, dus die hoeven maar één keer gebouwd te worden:

```bash
python -m hitlijsten.cli pdf --alle       # alles wat nog ontbreekt
python -m hitlijsten.cli pdf --jaar 2026  # één jaargang
python -m hitlijsten.cli pdf --alle --opnieuw   # ook wat al klopte
```

"Afgesloten" geldt wel voor de **bron**, niet voor onze afgeleide cijfers: een
nieuwe alias of een correctie verschuift de punten van een oude jaargang alsnog.
Daarom kijkt de download of het bewaarde bestand jonger is dan de laatste
ophaalactie én dan de laatste handmatige wijziging; is dat niet zo, dan wordt het
ter plekke opnieuw gebouwd. Een bewaard bestand levert de download in nul
seconden, een herbouw kost er een halve. De wekelijkse run vernieuwt de PDF van
elke jaargang die nieuwe weken kreeg.

**Er zit een lettertype bij** (`lettertypen/DejaVuSans*.ttf`, vrij
herdistribueerbaar, uit de matplotlib-wheel op PyPI). Dat moest wel: de
ingebouwde PDF-lettertypen kunnen alleen latin-1, en zesendertig van de
vijftienduizend nummers hebben een teken dat daar niet in past — juist de namen
die je niet wilt verminken, zoals "Orchestral Manœuvres In The Dark", "Tone
Lōc", "Givēon" en Tarkans "Şıkıdım". Kosten: zo'n honderd kilobyte per bestand.

Het ontwerp volgt de officiële jaarlijsten van top40.nl: zwart op wit met één
rood accent. **En onze cijfers zijn dezelfde**: de honderd puntentotalen van hun
Top 100-jaaroverzicht van 2025 zijn stuk voor stuk gelijk aan de onze, in
dezelfde volgorde.

## Gebruik

Alles draait op de NAS. Inloggen en de omgeving laden:

```bash
cd <app-map> && . ./omgeving.sh
./venv/bin/python -m hitlijsten run
```

Die laatste regel is wat de wekelijkse taak doet: ontbrekende weken ophalen,
Excel herbouwen, mailen. Hieronder staat kortweg `python`; lees dat als
`./venv/bin/python` met `omgeving.sh` geladen. Losse opdrachten:

| Opdracht | Wat het doet |
|---|---|
| `python -m hitlijsten bijwerken` | alleen wat nog ontbreekt ophalen |
| `python -m hitlijsten backfill` | alle weken van het lopende jaar |
| `python -m hitlijsten historie` | complete oude jaargangen uit het archief |
| `python -m hitlijsten excel` | Excel opnieuw bouwen uit de database |
| `python -m hitlijsten decennium` | decenniumklassementen van de Top 40 naar de decenniummappen |
| `python -m hitlijsten pdf --alle` | jaaroverzichten als PDF naar de jaarmappen |
| `python -m hitlijsten jaarlijks --lijst <x> --bestand <csv>` | een jaarlijkse lijst inlezen |
| `python -m hitlijsten controle` | verdachte dubbelingen, met oordeel per paar |
| `python -m hitlijsten kruiscontrole --alle` | onze Top 40 vergelijken met michajans.nl |
| `python -m hitlijsten onderscheidingen` | Alarmschijven en Dancesmashes ophalen |
| `python -m hitlijsten hersleutel` | sleutels herberekenen na een nieuwe alias |
| `python -m hitlijsten testmail` | proefmail versturen |
| `python -m hitlijsten run --geen-mail` | run zonder mail, uitvoer op scherm |

`--jaar 2025` mag vóór of ná de opdracht — beide werken.

### De wekelijkse taak

Elke **vrijdag om 22:00** start `hitlijsten-run.timer` het script
`app/wekelijkse-run.sh` als gebruiker `claude`. Dat script laadt zelf
`omgeving.sh` en gebruikt het venv.

```bash
sudo systemctl list-timers hitlijsten-run.timer   # wanneer gaat hij af?
sudo systemctl start hitlijsten-run.service       # nu draaien, mét mail
sudo journalctl -u hitlijsten-run.service         # wat deed hij?
```

Verzetten naar een ander moment: pas `OnCalendar` in
`/etc/systemd/system/hitlijsten-run.timer` aan en draai daarna
`sudo systemctl daemon-reload && sudo systemctl restart hitlijsten-run.timer`.
De units staan ook in de repo, zodat je ze kunt terugzetten.

**Waarom systemd en niet de DSM-taakplanner.** DSM bewaart geplande taken in een
eigen, ongedocumenteerd bestand (`/usr/syno/etc/synoschedule.d/root/50.task`)
waar geen ondersteunde CLI voor bestaat — je kunt er alleen via de UI bij. Daar
met de hand in schrijven kan de hele Taakplanner onderuit halen, inclusief de
backup- en replicatietaken die er ook in staan. De webapplicatie draait al onder
systemd, dus de timer past ernaast. Gevolg: **de taak is niet zichtbaar in de
DSM-UI**; kijk in `systemctl list-timers`.

`Persistent=true` staat aan: stond de NAS vrijdagavond uit, dan draait de run
alsnog zodra hij weer aan gaat — niet pas de week erna.

De run haalt **elke** ontbrekende week op, niet alleen de nieuwste, dus een paar
gemiste weken halen zichzelf in — bijvoorbeeld als de NAS een tijdje uit stond.
Dat geldt ook over de jaarwisseling heen: is de vorige jaargang afgekapt, dan
wordt de staart alsnog aangevuld.

Alleen de staart, niet elk gat — een jaargang die pas halverwege begon (Sterren
NL start in 2019 bij week 40) heeft aan het begin gaten die nooit bestaan hebben.
Die elke week opnieuw proberen zou de mail voorgoed vervuilen.

Heeft de NAS echt lang stilgestaan, gebruik dan `historie --vanaf <jaar>`.

### Oude jaargangen ophalen

```bash
python -m hitlijsten historie --vanaf 2015
```

Zonder `--vanaf` begint elke lijst bij zijn eigen oudste jaargang; `--tot`
begrenst het eind (standaard vorig jaar). Alles ophalen is ruwweg 7.400
pagina's, dus zo'n vier uur — het kan gerust onderbroken worden, want al
opgehaalde weken worden overgeslagen. Eén jaargang duurt ongeveer acht minuten.

Weken die niet bestaan komen vaker voor dan je zou denken:

- week 53 bestaat alleen in jaren die er 53 hebben;
- Sterren NL heeft **geen week 52 in 2025** — die lijst sloeg de kerstweek over,
  terwijl de Top 40 die week gewoon verscheen;
- een jaargang die pas halverwege startte heeft geen week 1.

Zulke weken worden bij een afgesloten jaargang **eenmalig vastgelegd** in de
tabel `bestaat_niet` en daarna nooit meer geprobeerd. Zonder dat zou de
wekelijkse run er elke vrijdag opnieuw over klagen — en een melding die altijd
een vals alarm bevat leest niemand meer.

Dat geldt alleen voor afgesloten jaargangen. Bij de lopende week betekent een 404
"nog niet gepubliceerd", en die wordt juist wél opnieuw geprobeerd. Ook een
parseerfout wordt nooit als "bestaat niet" weggeschreven: die kan door een
layoutwijziging komen die later hersteld wordt.

**Vraag je een jaargang op die een site niet heeft, dan krijg je geen foutmelding
maar stilletjes een andere lijst** — oranjetop30.nl geeft de nieuwste week terug,
top40.nl bij Sterren NL de oudste die ze hebben. Daarom controleert het script
van elke pagina of de titel de gevraagde jaargang en week noemt, en weigert hij
hem anders. Zonder die controle zou je vervalste historie opslaan: een "Oranje
Top 30 van 1965" die in werkelijkheid de lijst van vorige week is.

## Hoe het in elkaar zit

```
<app-map>/
  omgeving.sh          zet HITLIJSTEN_DATA / _CACHE / _EXCEL
  start-web.sh         wordt door systemd gestart (hitlijsten-web)
  wekelijkse-run.sh    wordt door hitlijsten-run.timer gestart
  hitlijsten-web.service      systemd-unit van de webapplicatie
  hitlijsten-run.service      systemd-unit van de wekelijkse run
  hitlijsten-run.timer        vrijdag 22:00
  venv/                Python 3.14.5 met de afhankelijkheden
  run.log              logboek van alle runs
  hitlijsten/
    config.py     de vier lijsten, paden, URL-opbouw, lengte per jaargang
    fetch.py      HTML ophalen + schijfcache, week- en jaarcontrole
    parsers/      HTML -> Notering  (top40nl.py, oranje.py)
    models.py     dataclass Notering + structuurcontrole
    normalize.py  nummers over weken heen herkennen
    datums.py     weeknummer -> uitzendvrijdag
    db.py         sqlite-opslag, incl. bestaat_niet en de totalen per periode
    excel.py      de Excel-bestanden
    pdf.py        het jaaroverzicht als PDF
    wetenswaardigheden.py   de tien ranglijsten
    opschonen.py            typefouten opsporen en rechtzetten
    momentopnames.py        kopie van de database, met bewaarbeleid
    muziekbron.py           MusicBrainz en Wikipedia bevragen
    jaarlijks.py  de CSV-lijsten (Top 2000, Evergreen)
    kruiscontrole.py / onderscheidingen.py  michajans.nl
    mail.py       melding via de mailrelay
    cli.py        de opdrachten hierboven
    web/          de Flask-applicatie (app.py, templates/)
  lettertypen/    DejaVu Sans, ingesloten in de PDF's (met licentie)
  tests/          zelftests, draaien op de cache dus zonder netwerk
```

De gegevens staan er bewust náást, niet in:

```
<hitlijsten>/
  data/hitlijsten.sqlite   de database (46 MB)
  cache/                   de ruwe HTML van alle opgehaalde pagina's (2 GB)
  excel/                   de werkboeken en PDF's (46 MB)
```

Zo kun je `app/` in zijn geheel vervangen zonder de database aan te raken.

**De database is de bron, niet de website.** Alles wat opgehaald is staat in
`data/hitlijsten.sqlite` en de ruwe HTML in `cache/`. De Excel-bestanden opnieuw
bouwen kost dus geen enkel verzoek aan de sites, en je kunt ze zonder risico
weggooien en opnieuw laten maken.

Aliassen, uitzonderingen en correcties zaten vroeger in CSV-bestanden; die staan
sinds juli 2026 in de database (tabellen `aliases`, `niet_samenvoegen`,
`correcties`) en zijn te beheren via de webapplicatie.

**Waarom er dan tóch `aliases-export.csv` en `niet-samenvoegen-export.csv` in
deze repository staan.** Ze worden door niets gelezen — de database is de bron.
Maar de database staat in `.gitignore`, en die honderddertig aliassen en vier
uitzonderingen zijn handwerk: elk paar is met de hand beoordeeld. Zonder export
zou dat werk op precies één plek bestaan, op één schijf. De export is de enige
versiebeheerde kopie ervan.

De wekelijkse run schrijft die export elke vrijdag opnieuw weg naast de code, dus
de kopie op de NAS is nooit ouder dan een week. Het bestand *in deze repository*
is een momentopname van de laatste keer dat de code is bijgewerkt; wil je hem
gelijktrekken, haal dan de verse op van de NAS. Terugzetten in een lege database
kan met `hitlijsten.migratie_csv`.

### Testen

```bash
cd <app-map> && . ./omgeving.sh
./venv/bin/python tests/test_top40nl.py
./venv/bin/python tests/test_oranje.py
./venv/bin/python tests/test_excel.py
./venv/bin/python tests/test_datums.py
./venv/bin/python tests/test_decennium.py
./venv/bin/python tests/test_wetenswaardigheden.py
./venv/bin/python tests/test_opschonen.py
./venv/bin/python tests/test_momentopnames.py
./venv/bin/python tests/test_pdf.py
./venv/bin/python tests/test_jaarlijks.py
node tests/test_grafiek.mjs        # node staat niet op de NAS
```

Acht reeksen, ruim vierduizend controles. Ze draaien op de gecachete pagina's
en een tijdelijke database, dus zonder netwerk en zonder de echte data aan te
raken. Handig na elke wijziging aan een parser of aan een bouwer.

`test_grafiek.mjs` is de vreemde eend: die knipt het grafiekscript uit
`templates/jaar.html` en draait het in node tegen een kleine DOM-stub. Dat is
geen browser en zegt dus **niets over de opmaak** — wel over de schaal, de
verschillen per week, de gaten en de streep bij de jaarwisseling. Het script
wordt uit de template geknipt in plaats van gekopieerd, zodat de test niet
stilletjes een oude versie blijft goedkeuren.

`test_pdf.py` heeft hetzelfde bezwaar: een PDF ziet er in een test altijd goed
uit, want je kunt hem niet bekijken. Wat daar vastligt is dus niet de opmaak
maar wat er misgaat als je niet oplet — het aantal regels per pagina, de namen
die het ingebouwde lettertype niet aankan, en of een bewaard bestand nog klopt.

## Nummers herkennen over weken heen

"Antoon ft. Sef" en "Antoon feat. Sef" moeten hetzelfde nummer zijn, anders valt
de jaarmatrix uit elkaar en worden de punten verdeeld. `normalize.py` maakt
daarvoor een sleutel: accenten weg, kleine letters, `feat.`/`ft`/`featuring`
gelijkgetrokken, en bij artiesten ook `x`/`&`/`+`. Bij titels gebeurt dat laatste
bewust níét — "Malcolm X" moet "Malcolm X" blijven.

**Sites hernoemen lopende noteringen.** Dat is de belangrijkste bron van fouten,
en het gebeurt vaker dan verwacht — in 2025 drie keer:

- Ed Sheeran stond één week als dubbele A-kant "Azizam / Azizam (Persian Version)";
- de Tipparade voegde bij "I Run" een gastartiest toe aan de credit;
- Oranje veranderde "Wij drinken wijn" in "We drinken wijn".

Zonder ingrijpen wordt dat twee rijen met verdeelde punten.

```bash
python -m hitlijsten controle
```

zoekt zulke gevallen op en **beoordeelt ze**, op grond van de weken in plaats van
alleen de gelijkenis van de namen:

| Wat de weken doen | Oordeel |
|---|---|
| staan ooit samen in dezelfde week | twee losse nummers — niet samenvoegen |
| hooguit 3 weken ertussen | zelfde notering, hernoemd |
| meer dan 3 weken ertussen | aparte notering — niet samenvoegen |

Het eerste geval is sluitend: een nummer kan niet twee keer tegelijk in één lijst
staan. Zo bleken "Anxiety" van Doechii en die van Sleepy Hallow ft. Doechii echt
twee nummers.

Blijft er een paar terugkomen dat je al hebt afgewezen — een kerst- of
voetbalversie die vlak na het origineel verscheen en dus binnen de weekgrens
valt, maar toch een eigen nummer is — zet het dan onder **Uitzonderingen** in de
webapplicatie. `controle` slaat die paren daarna over.

De grens van drie weken (`cli.MAX_GAT_WEKEN`) scheidt een hernoeming van een
heruitgave. Danzel's "Pump It Up" noteerde in 2004 van week 13 tot 18 en de remix
pas vanaf week 43 — 24 weken later, dus een eigen notering. Een typefout of een
toegevoegde gastartiest valt daarentegen altijd binnen een paar weken.

Samenvoegen doe je zelf, onder **Aliassen** in de webapplicatie: van welke
sleutel naar welke. De sleutel staat als kolom in de Excel-bestanden. Ketens
mogen: `a` → `b` plus `b` → `c` laat a, b en c allemaal op c uitkomen.

Aliassen en uitzonderingen stonden vroeger in `aliases.csv` en
`niet-samenvoegen.csv`; sinds juli 2026 staan ze in de database (tabellen
`aliases` en `niet_samenvoegen`) en legt de webapplicatie elke wijziging vast in
het logboek. De oude CSV's zijn gemigreerd en verwijderd.

### te-beoordelen.csv

```bash
python -m hitlijsten controle --alle
```

loopt alle jaargangen na en schrijft de gevallen die het script níét zelf durft
te beslissen naar **`te-beoordelen.csv`** (in `app/`), als kant-en-klare
aliasregels met een `#` ervoor. Wil je er een samenvoegen, neem de twee sleutels
dan over onder **Aliassen** in de webapplicatie.

Elk geval staat er met de weken erbij, want daar hangt het oordeel van af:

```
# 2004 top40
#   A  danzel|pump it up         (week 13-18, 6x)
#   B  danzel|pump it up remix   (week 43-49, 7x)
# danzel|pump it up remix;danzel|pump it up
```

Die twee moet je juist **niet** samenvoegen: de remix noteerde een half jaar na
het origineel als eigen notering. Maar "job bovelander" en "job bovenlander" in
hetzelfde jaar zijn duidelijk dezelfde artiest. Het script doet hier bewust geen
gok.

**Draai daarna altijd:**

```bash
python -m hitlijsten hersleutel
```

De sleutel wordt namelijk bij het opslaan berekend en in de database gezet;
alleen Excel opnieuw bouwen verandert dus niets. Daarna
`python -m hitlijsten excel`.

## Kruiscontrole met michajans.nl

Micha Jans publiceert de jaarlijsten van de Werkgroep Hitlijsten (top40web.nl),
een archief dat losstaat van top40.nl en alleen de Top 40 bijhoudt. Twee
onafhankelijke bronnen die op hetzelfde uitkomen is het sterkste bewijs dat onze
parser en puntenberekening kloppen.

```bash
python -m hitlijsten kruiscontrole --alle
```

Stand: over de jaargangen 2000–2025 zijn **5755 nummers exact gelijk** — punten,
hoogste positie én aantal weken alle drie. Hun puntentelling blijkt dezelfde als
de onze. Er blijven drie verschillen over, alle drie van één punt of één week;
daar wijkt de ene bron van de andere af en is niet uit te maken wie gelijk heeft.

De opdracht doet meer dan vergelijken. Heeft een nummer bij hen één notering waar
wij er twee hebben die in **punten én weken precies optellen**, dan is dat het
handtekeningpatroon van een gemiste alias: de site hernoemde een lopende
notering. Zulke gevallen komen in `kruiscontrole-aliases.csv` te staan. Zo
kwamen "Move" (2024) en "Iko Iko" (2021) alsnog boven water, die de gewone
`controle` miste omdat de artiestnaam te veel verschilde.

### Wie wint bij een verschil

Micha Jans haalt de fouten uit de officiële lijst, dus bij een **groot** verschil
geldt zijn cijfer. Dat legt de kruiscontrole vast en de `Totaal`-tab gebruikt het;
de kolom **Bron** laat zien welke rijen van hem komen.

De grens staat in `kruiscontrole.py`: meer dan **2 weken** verschil of meer dan
**5%** van zijn puntentotaal. Daaronder houden we onze eigen cijfers aan. Tussen
twee archieven van dezelfde lijst zit namelijk ruis — een positie die één plaats
afwijkt scheelt één punt — en onze eigen week-voor-weekgegevens zijn tenminste
na te rekenen.

Op de jaargangen 2000–2025 haalt geen enkel verschil die grens: er zijn er drie,
alle van één punt of één week.

**Let op als er ooit wél een correctie is:** de weektabs en de jaarmatrix blijven
onze eigen waarneming, want zijn jaarlijst geeft geen posities per week. Voor zo'n
rij is het jaartotaal dan niet de som van de weektabs. De kolom Bron maakt dat
zichtbaar.

**Hun site loopt achter**: de laatste jaarlijst is 2025 en hun "actuele" Top 40
dateert van 27 december 2025. Voor 2026 is er dus niets te vergelijken. Hun
weekarchief bestaat uit 52 pagina's die elk jaar overschreven worden, dus
weekposities zijn bij hen alleen voor 2025 beschikbaar.

### Alarmschijven en Dancesmashes

```bash
python -m hitlijsten onderscheidingen
```

Die twee aanduidingen staan niet op top40.nl. Ze komen als kolom in de
`Totaal`-tab van de Top 40-bestanden, met de datum van toekenning.

Koppelen gebeurt op naam, want zij schrijven artiesten anders dan top40.nl —
"Mirrors - JT" tegenover "Mirrors - Justin Timberlake", "Mimimi" tegenover
"Mi mi mi". Van de 2301 onderscheidingen binnen onze jaargangen wordt 89%
gekoppeld; van de rest haalde het overgrote deel de Top 40 nooit (een Alarmschijf
is een aanbeveling, geen notering). Bij een steekproef over 155 niet-gekoppelde
bleken er **4 een echte koppelfout**.

## Beveiliging

Augustus 2026 nagelopen (code-review plus proeven op de eigen site). Wat er
sindsdien vastligt, van meest naar minst blootgesteld:

**De upload van DJ Export** is het enige dat een vreemde zonder wachtwoord kan
aanspreken, dus daar zit de meeste wering. Twee dingen, elk op zijn eigen plek:

- **De omvang** bewaakt `vdj.Budget`: **één teller voor de hele upload**, niet
  per bestand. Dat verschil is het hele punt — met een teller per bestand
  stuurt iemand tien zip's die elk net onder de grens blijven, of vult hij één
  zip met twintig keer dezelfde `database.xml`. Het budget telt drie dingen:
  uitgepakte bytes (512 MB), nummers (300.000) en bestanden (20). Bytes en
  niet bestandsgrootte, want een zip comprimeerde in de test met factor 294;
  en bytes tellen óók als een bestand nul nummers oplevert, want het gaat om
  het werk dat de server verzet. De twee grenzen zijn op elkaar afgestemd:
  300.000 nummers is ruwweg 460 MB XML en kost ~160 MB geheugen, en er passen
  er acht in `_vdj_sessies`. Ter ijking: Heyes echte backup is 172 MB
  uitgepakt met 113.411 nummers. Daarbovenop een uploadplafond van 256 MB en
  `MemoryLimit=2G` op de dienst — let op: DSM draait systemd 219, dus
  `MemoryMax` werkt daar níét; het moet `MemoryLimit` heten met
  `MemoryAccounting=yes` erbij.
- **DTD's en entiteiten** weigert **defusedxml** (`veilig_iterparse`), niet
  wijzelf. Dat is een geleerde les: de eerste versie zocht in de bytes naar
  `<!DOCTYPE`, en dat leek te werken tot de hercontrole een **UTF-16**-bestand
  probeerde. Daar staat `<` NUL `!` NUL `D` NUL `…` en zag het patroon niets,
  terwijl de entiteit gewoon werd uitgevouwen — een DTD van 400 bytes werd een
  miljoen tekens ("billion laughs"). Een bibliotheek die de tekstcodering kent
  doet dit beter dan een patroon dat wij verzinnen; het sluit meteen XXE mee
  af. Geverifieerd tegen ascii, hoofdletters, UTF-16 met BOM, UTF-16BE en een
  externe entiteit.

Wat een zip-in-zip betreft: die wordt niet uitgepakt (alleen een
`database.xml` op het eerste niveau telt), dus daar zit geen tweede
versterkingstrap.

**CSRF**: elke route met `@vereist_aanmelding` zet zichzelf in `BEHEERROUTES`,
en `_csrf_bewaking` eist voor die routes een sessietoken (`{{ csrf_teken() }}`
als verborgen veld). Een nieuw beheerscherm krijgt de bescherming dus vanzelf.
De publieke formulieren (feedback, DJ Export) blijven bewust vrij: die hebben
hun eigen wering, en een token zou elke lezer een cookie bezorgen terwijl de
disclaimer belooft dat lezen geen cookie kost.

**De vrije query** (`/query`) is alleen-lezen doordat **SQLite** het afdwingt
met een authorizer, niet doordat er woorden gefilterd worden. Die woordenlijst
was te omzeilen: `WITH x AS (SELECT 1)DELETE FROM ...` — zonder spatie, of met
een newline of `/**/` ertussen — kwam er gewoon doorheen en wiste rijen.

**Verder**: het CSRF-token wordt vernieuwd zodra je je aanmeldt (een token dat
iemand daarvóór bemachtigde is dan niets meer waard); sessiecookie met
`Secure`, `SameSite=Lax` en zeven dagen
levensduur (let op: aanmelden kan daardoor **alleen nog via HTTPS**, niet meer
rechtstreeks op `http://<nas>:8642`); beveiligingsheaders op elk antwoord
(CSP met `unsafe-inline` omdat de sjablonen hun stijl en scriptjes inline
dragen — de winst is dat er van geen enkele andere herkomst iets geladen mag
worden); vijf mislukte aanmeldpogingen per kwartier per IP mét logregel; geen
open redirect meer via `?volgende=`; en `_eigen_pad()` op het pagina-veld van
feedback en de terug-link van het DJ Export-rapport, zodat daar geen
`javascript:`-link kan wachten op een klik van de beheerder. Die laatste
controle moet wél twee soorten invoer aankunnen: een kaal pad (het verborgen
formulierveld) én een volledige URL (de Referer-kop). De eerste versie kende
alleen paden en liet daarmee de terug-link op het DJ Export-rapport
verdwijnen — een eigen URL wordt nu herkend en teruggebracht tot zijn pad.

**De server**: `python -m hitlijsten.web` draait sinds augustus 2026 op
**waitress** in plaats van de ontwikkelserver van Flask (die is niet gebouwd
om aan het open internet te staan). Bewust **één proces met acht draden** en
niet meerdere workers: de applicatie houdt dingen in het geheugen die per
bezoeker gelden — de geladen DJ Export-bibliotheken, de aanmeldrem en de
caches — en met meerdere processen zou een bezoeker zijn database in het ene
proces laden en bij de volgende klik in het andere belanden. Draden delen hun
geheugen, dus dat probleem bestaat niet. Met `--debug` start nog steeds de
Flask-server, en die zet dan ook `Secure` van het sessiecookie uit, want
zonder HTTPS kun je je lokaal anders niet aanmelden.

**HTTP stuurt door naar HTTPS.** In de reverse proxy staat voor
hitlijsten.hhaken.nl alleen een HTTPS-regel (443 naar 10.10.8.20:8642). Wie
`http://` intikte viel daardoor door naar de standaard-site van Web Station en
kreeg de persoonlijke startpagina van hhaken.nl te zien — met een keurige 200,
dus zonder enig teken dat hij verkeerd zat, en onversleuteld. Opgelost met een
`.htaccess` in `/volume1/web/` die alléén dit hostname 301't naar https, met
behoud van pad en queryreeks; de voorwaarde kijkt naar de Host-kop, dus
www.hhaken.nl en de andere sites in die docroot merken er niets van. Een lus
kan niet ontstaan: HTTPS voor dit hostname eindigt in de proxy en bereikt
Apache nooit.

Dezelfde blinde vlek gold voor **keepass**, **console** en **has**; die staan
in hetzelfde bestand, met één verschil: zij krijgen een **308** in plaats van
een 301. Dat onderscheid telt alleen voor niet-browsers — bij een 301 mag een
client een POST als GET herhalen, bij een 308 moet hij de methode behouden, en
Home Assistant kent webhooks die posten. De site zelf houdt 301, de
gebruikelijke keuze voor iets met zoekmachines. `hasnc` reageert niet op
poort 80 en is dus niet getroffen.

> Dat dit niets kón breken zit hem hierin: wie vandaag `http://` gebruikte
> kreeg de verkeerde site, dus daar werkte al niets. Een nettere structurele
> oplossing blijft: per subdomein een HTTP-regel in DSM, of één nginx-
> serverblok dat alles doorstuurt.

**Wie mag zeggen namens wie hij spreekt.** `_bezoeker_ip()` gelooft
`X-Forwarded-For` en `X-Real-IP` alleen van `VERTROUWDE_PROXIES` (de
DSM-proxy en de machine zelf). Van buitenaf was dit nooit een probleem — nginx
overschrijft beide koppen — maar de applicatie luistert óók rechtstreeks op
poort 8642 op het LAN, en daar kon iemand ze wél verzinnen: goed voor het
omzeilen van de aanmeldrem én, met jouw adres in de kop, om jou een kwartier
buiten te sluiten. De rem-administratie zelf wordt bij elke poging opgeruimd
(verlopen adressen eruit, hard plafond van 5.000), anders groeit hij mee met
elk adres dat het ooit probeerde.

**Nagemeten en niet te breken** (hercontrole augustus 2026): een zip-in-zip
wordt niet uitgepakt; meerdere `database.xml` in één zip tellen correct op
tegen het budget; de authorizer laat `ATTACH`, `PRAGMA`, `load_extension` en
elke CTE-truc niet door; en het CSRF-token wordt na aanmelden vervangen, dus
een van tevoren bemachtigd token is waardeloos.

**Wat de hercontrole nog aan het licht bracht** — behalve de UTF-16-omweg
hierboven: de padcontrole liet `/` + backslash + `vreemd.example` door (browsers lezen `/\`
als `//`, dus dat is alsnog een uitstapje naar een andere site), en de
authorizer had recursieve CTE's stukgemaakt terwijl de pagina er wél mee
adverteert (`SQLITE_RECURSIVE` hoort in `_MAG_LEZEN`). Beide hersteld; de
vrije query heeft nu ook een afbreekrem van tien seconden.

Wat al goed zat en zo moet blijven: geparametriseerde SQL overal (de
zoekfunctie plakt wel SQL aan elkaar, maar uitsluitend uit vaste fragmenten),
Jinja-autoescaping zonder één `|safe`, constant-time wachtwoordvergelijking,
geheimen in `.gitignore` en nooit gecommit, en debug uit.

## Als er iets misgaat

**Wijzigt een site zijn opmaak**, dan faalt de structuurcontrole (verwacht
40/30/25 aaneengesloten posities) en komt dat in de mail terecht: in de
onderwerpregel staat `-- N MISLUKT` en bovenaan het bericht welke weken het
betreft. Dat is met opzet — de taak draait onbeheerd op de NAS, dus een stille
mislukking zou maanden onopgemerkt kunnen blijven. Een lege tab wegschrijven is
erger dan een luide fout.

Een mislukte week wordt ook **uit de cache gegooid**, zodat de volgende run hem
gewoon opnieuw probeert. Anders zou één onderhoudspagina zich permanent
vastzetten. Blijft dezelfde week falen, dan is het geen toeval en moet de parser
aangepast worden.

Alle details staan in **`run.log` naast de code**. Dat groeit langzaam
en wordt niet automatisch opgeschoond.

## Eigenaardigheden van de bronnen

**top40.nl heeft een kapotte certificaatketen.** De site stuurt het verkeerde
Sectigo-tussencertificaat mee. Browsers repareren dat zelf door het ontbrekende
certificaat op te halen; Python doet dat niet en faalt met
`CERTIFICATE_VERIFY_FAILED`. `certifi` lost het nooit op, hoe je het ook
instelt. `fetch.py` levert daarom het ontbrekende certificaat zelf mee in
`certificaten/sectigo-dv-r36.pem` en plakt dat achter de certifi-bundel.
Certificaatcontrole blijft gewoon aan staan. Dit is een probleem van top40.nl,
niet van de NAS; oranjetop30.nl heeft het niet.

`fetch.py` kent daarnaast een tweede weg: is `truststore` geïnstalleerd, dan
gebruikt Python de systeemcertificaatstore. Dat werkte op de Windows-pc waar dit
project begon. Op de NAS zit dat pakket er niet en kent de systeemstore het
certificaat ook niet, dus daar geldt altijd de meegeleverde bundel.

**top40.nl kort lange artiestnamen af** in de zichtbare HTML (op ~46 tekens, met
`..`). De volledige naam staat alleen in het `aria-label` van de link; de parser
herstelt dat.

**Onder elke top40.nl-lijst staan de uitvallers**, in exact dezelfde opmaak als
de lijst zelf. Ongefilterd krijg je 42 in plaats van 40 noteringen, met verkeerde
punten tot gevolg. Ze zijn herkenbaar aan de klasse `no-longer-listed`.

**oranjetop30.nl zet het platenlabel in een eigen element** binnen de artiestnaam.
Dat is maar goed ook, want titels bevatten zelf ook haakjes — "Er hangt iets in
de lucht (Amore)" zou anders "Amore" als label krijgen. Deze site is de enige die
een label toont.

**De Tipparade kent geen dalers.** Nummers klimmen of verdwijnen — nul dalers op
2460 noteringen over 2025 en 2026. Dat is een eigenschap van die lijst, geen
parseerfout.

**Tekens die verminkt lijken:** `omgeving.sh` zet `PYTHONIOENCODING=utf-8`, want
zonder dat kan een console `ø` en `ë` verminken — wat er precies uitziet als een
coderingsfout in de data. Dat is het niet; de cache is correct UTF-8. Draai je
iets met de hand buiten die shell om, zet die variabele dan zelf.

## Mail

Na de wekelijkse run gaat er een melding uit met wat er nieuw binnenkwam en wat
er misging. Alle instellingen staan in `mail.ini` naast de code; dat bestand
staat niet in git. Zonder ontvanger doet de module niets en zegt dat ook —
een standaardadres in de broncode is precies het soort ding dat je vergeet aan
te passen.

```ini
[mail]
host = mailserver.thuis
poort = 25
afzender = hitlijsten@voorbeeld.nl
ontvanger = jij@voorbeeld.nl
gebruiker =            ; leeg = geen aanmelding
wachtwoord =
starttls = nee
```
