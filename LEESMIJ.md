# Hitlijsten verzamelen

Haalt elke week de vier hitlijsten op, schrijft ze naar Excel en PDF, mailt wat
er nieuw binnenkwam, en zet zestig jaar archief online op
**[www.nl-hitlijsten.nl](https://www.nl-hitlijsten.nl)**.

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

- **Het hele archief staat in de database**: 540.352 noteringen over
  eenentwintig lijsten. Top 40
  1965–2026 (62 jaargangen), Tipparade 1967–2026 (60), Oranje Top 30 2008–2026
  (19), Sterren NL 2019–2026 (8), Top 2000 1999–2025 (27 edities), Top 4000
  2005–2025 (21), Veronica Top 1000 2003–2025 (23), Q Top 1500 2005–2025 (21),
  Evergreen Top 1000 2008–2025 (18), Rock Top 500 2000–2025 (26) en
  Kink Top 1500 2019–2025 (7).
- 811 Excel-bestanden en 402 PDF-jaaroverzichten gebouwd, plus 581 aliassen,
  4.044 onderscheidingen, 4.963 doorverwijzingen van verhuisde sleutels en
  7.006 taalbepalingen.
- De wekelijkse run staat ingepland op **vrijdag 22:00**, als systemd-timer
  `hitlijsten-run.timer`.

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

**Het venster opent vanuit twee tabellen, en dat is een valkuil geweest.** Op
een jaar- en editiepagina staan het klassement en de matrix onder elkaar, met
één klik-afhandelaar voor allebei: de rij draagt de gegevens die in de kop van
het venster komen. De matrixrijen droegen alles, de klassementsrijen alleen de
sleutel — dus vanuit het klassement opende het venster met een lege artiest en
titel, en bij een notering over de jaargrens stond er *undefined weken ·
undefined punten*. Wie hier een kenmerk bijzet, moet het in **beide** tabellen
doen; dat de grafiek het van de rij leest en niet van de server is juist wat
een tweede kopie in JSON bespaart.

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

**https://www.nl-hitlijsten.nl** — dezelfde gegevens als de Excel-bestanden,
maar doorzoekbaar en zonder download. Draait als systemd-dienst `hitlijsten-web`
op de NAS, achter een reverse proxy.

**Vrij toegankelijk:**

| Pagina | Wat je er ziet |
|---|---|
| Overzicht | wat er in de database zit, in twee tabellen: weeklijsten en jaarlijkse lijsten — die laatste **per zender gegroepeerd** (zenderkolom, afgeleid uit de lijstnaam via `zender_van()`); dezelfde groepjes vullen de optgroups van de lijst-keuzelijsten |
| Jaaroverzichten | puntenklassement en de matrix positie-per-week, per lijst en jaargang, met bladerknoppen langs de jaargangen; ook een **binnenkomers-vinkje** (nummers die dat jaar voor het éérst in de lijst verschenen — over de hele historie gerekend, dus Last Christmas telt alleen in 1984) |
| Selecties & downloads | overal dezelfde spelregels: keuzelijst top 100/500/1000/2500/alles (standaard 100; onder de 250 nummers geen keuzelijst maar meteen alles; opties vanaf de lijstlengte vervallen en het traag-label staat alleen boven de 2500 regels), de filters NL en binnenkomers, en **wat op het scherm staat, zit in het bestand** — Excel en PDF volgen de selectie met `_topN`/`_NL`/`_nieuw` in de bestandsnaam én, sinds augustus 2026, met een **FILTER-regel ín het stuk** (bij de PDF in de ondertitel onder de banner, bij Excel als eerste zin van de toelichting boven de tabel); een doorgestuurd of uitgeprint bestand draagt zijn bestandsnaam immers niet meer, en zes regels waar er veertig horen roept dan vragen op; op "alles" zonder filter komen de rijke voorgebouwde jaarwerkboeken met weektabs, en de matrix-downloads blijven altijd volledig |
| Alarmschijf in downloads | de weeklijst-Excel krijgt een kolom `Alarmschijf` ("ja"), de weeklijst-PDF een **ster vóór de titel** met `= Alarmschijf` in de ondertitel — allebei alleen bij de **Top 40**. De vlag is namelijk een eigenschap van de plaat en staat dus óók op de Tipparade- en Sterren NL-noteringen van hetzelfde nummer (gemeten: 2.651 en 451 stuks), maar uitgeroepen worden ze in de Top 40; een ster elders zou suggereren dat die lijst eigen Alarmschijven kent. Het belletje van de site kan niet in de PDF: dat teken zit niet in DejaVu Sans en zou een leeg blokje worden |
| Decennia | het puntenklassement over tien jaargangen Top 40, met bladerknoppen langs de decennia |
| Top 40 totaal | hetzelfde over alle jaargangen 1965–nu |
| Zoeken | op artiest, titel of beide; `*` als jokerteken; `artiest \| titel` zoekt op allebei tegelijk (bij nul treffers met meerdere woorden stelt de pagina die schrijfwijze klikbaar voor); klik springt naar de jaargang van de hoogste notering — openbaar, net als de nummerpagina's (de bewerkkant blijft achter de login) |
| Artiest | eigen pagina per artiest (±13.600): alle nummers over alle lijsten heen, met carrière-spanne, hoogste posities en nummer-1-teller; bereikbaar via artiestnamen op de nummer- en zoekpagina's |
| Jouw dag | datumprikker: kies je geboortedag of trouwdag en zie de Top 40 die toen gold, met de nummer 1 groot in beeld; op de homepage staat "X jaar geleden op 1" voor deze week door de decennia heen |
| DJ Export (VirtualDJ & rekordbox) | met **voortgangsbalk** bij het laden. Het formulier gaat met een XHR de deur uit, zodat het versturen een echt percentage krijgt — maar dat is op een thuisnetwerk in een tiende seconde klaar (gemeten: 29 MB in 67 ms, één enkele gebeurtenis op 100%), terwijl het verwerken zeven seconden duurt. Daarom **meldt de server zijn eigen stand**: `vdj.Budget` telt de uitgepakte bytes en de pagina vraagt ze elke 400 ms op via `/vdj/voortgang/<sleutel>` (sleutel = toevalsgetal van de bezoeker, alleen in het geheugen, weg zodra het verzoek klaar is). Dat dit werkt hangt aan de keuze voor **één proces met draden**: met losse workers zou de pollende draad een andere kopie zien. Een XHR krijgt JSON terug in plaats van een omleiding, want de XHR volgt die zelf en verbruikt de flash-melding, waarna de verversing niets meer vindt. Zonder JavaScript blijft het een gewone POST, die nu ook bij een fout omleidt in plaats van rendert (flash-melding), zodat opnieuw laden de upload niet herhaalt. Laad éénmalig je `database.xml`, een **rekordbox-collectie-export** (xml, herkend aan de DJ_PLAYLISTS-wortel) of — makkelijker — de **backup-zip** van VirtualDJ (Instellingen → Backup; met de volledige database erin, ook van losse schijven), plus je voorkeuren (streaming/netsearch wel of niet, bestandssoort — standaard alleen audio, want een mp4 wint anders elke bitrate-vergelijking — en matching-strengheid in vier niveaus, waarbij duet-credits als "Meat Loaf & Ellen Foley" tegen "Meat Loaf" al op niveau strak matchen); daarna verschijnt op elke weeklijst, elk jaaroverzicht, de decennia en de beide totaallijsten een **⤓ DJ Export-knop** die de getoonde selectie — top-keuze en filters incluis — als playlist oplevert in het formaat dat bij de geladen bron past: `.vdjfolder` bij een VirtualDJ-upload, `.m3u8` bij een rekordbox-upload (te importeren in rekordbox/Engine DJ/Traktor/Serato — de route naar Pioneer/Denon-hardware loopt via die software), met rapport en boodschappenlijst van wat ontbreekt (het rapport is ook als **.txt** te downloaden: vaste kolommen om te printen, met die boodschappenlijst er nog eens apart onder); lokaal bestand wint van streaming, hoogste bitrate bij dubbelen; de database leeft alleen tijdens je bezoek in het geheugen (max. 4 uur) en raakt nooit een schijf |
| Tweetalig | NL/EN-knop rechtsboven naast Aanmelden (cookie `taal`, route `/taal/<code>`); de menubalk, footer, alle lijstpagina's en DJ Export zijn vertaald via `web/vertalingen.py` (NL-tekst als sleutel, Nederlands als vangnet) plus taal-condities voor lange proza-blokken; de **disclaimer** is volledig tweetalig (taal-conditie in het sjabloon; de Nederlandse versie is leidend) en de **handleiding bestaat in twee talen** (`handleiding.pdf` + `manual.pdf`, de vrijdagrun bouwt beide, de menubalk-knop kiest op taal); sinds fase 2 zijn ook **alle specials** vertaald (zoeken, jouw dag, weekbericht, records, versies, vergelijk, wetenswaardigheden, nummer-/artiestpagina's, gastenboek, feedback en de grafiek-uitleg); de titels die uit Python komen (records- en wetenswaardigheden-blokken) lopen via hetzelfde woordenboek, met Nederlands als vangnet voor samengestelde uitlegzinnen; ook de **RSS-feed** is tweetalig (`weekbericht.rss?taal=en` — de taal zit in de URL omdat feedlezers geen cookies sturen; de feed-link op de pagina geeft hem door); alleen het beheer blijft Nederlands |
| Handleiding | de complete gebruiksaanwijzing voor bezoekers als PDF in de huisstijl, **in twee talen** (`/static/handleiding.pdf` NL + `/static/manual.pdf` EN; de menubalk-knop kiest op taalcookie; de **vrijdagrun herbouwt beide** met verse tellerstanden uit de database; met de hand: `python -m hitlijsten.handleiding`), met een eigen DJ Export-hoofdstuk |
| Records | de klappers over alle lijsten en jaargangen heen: meeste weken genoteerd, meeste weken op 1, grootste sprong en diepste val, langste terugkeer, eenhitwonders op 1, langste carrière, meeste hits en de trouwste jaarlijst-klanten |
| Versies | dezelfde titel door verschillende artiesten — covers, heropnames en soms naamgenoten, gesorteerd op aantal uitvoeringen |
| Vergelijk | twee jaargangen van dezelfde lijst naast elkaar: kerngetallen (incl. het Nederlandstalig-aandeel), de hoogst genoteerde nummers van elk jaar, en wat er in allebei stond |
| Verras me | het dobbelsteentje achteraan de tweede menuregel, naast het Gastenboek: een willekeurig nummer, gewogen naar noteringen |
| Weekbericht | de nieuwste Top 40 samengevat (nummer 1, binnenkomers, grootste stijger/daler, terugkeerders, uitvallers) plus een kaart per **andere weeklijst** (Tipparade, Oranje Top 30, Sterren NL Top 25: nummer 1 + aantal binnenkomers/herintreders + link, alleen als die lijst die week bestond — dezelfde regel als in het Facebook-bericht), bladerbaar per week en te volgen via de **RSS-feed** `/weekbericht.rss` — schrijft zichzelf uit de vrijdagrun |
| Weeklijsten | één week zoals uitgezonden, met **vaste kolombreedtes** zodat de vier lijsten onder elkaar uitlijnen (alleen vanaf 761 pixels; op een telefoon zou een positiekolom van 8% de ring om het cijfer afsnijden), met week-keuzelijst, de extra keuze **Alle weeklijsten** (de vier onder elkaar, elk met eigen kop en posities; Excel krijgt dan een tab per lijst, de PDF de vier **doorlopend** onder elkaar — een nieuwe pagina alleen als het niet meer past, want met het nieuw-filter zijn vier hele pagina's voor zeventien binnenkomers verspilling — en de DJ Export één playlist met dubbelen eruit), bladeren over de jaargrens heen (een overgeslagen kerstweek wordt overgeslagen) en de nieuw/terug-spelden; het **nieuw-vinkje** betekent hier de binnenkomers van de wéék zelf (het groene speldje), niet de jaargang-binnenkomers |
| Zoeklinks | YouTube- en Spotify-icoontje bij elk nummer, dezelfde als op de Ots Radio-webplayer |
| Alarmschijf | rood belletje 🔔 vóór de titel op de weeklijsten (Top 40, Tipparade en Sterren NL — de vlag hoort bij de plaat, dus hij reist mee); het belletje van top40.nl zelf (klasse `hitrecord`), per plaat vastgelegd in `noteringen.alarmschijf` en elke vrijdagrun bijgehouden; michajans.nl blijft de bron voor de toekenningsdatum |
| Merkteken | het icoontje van de Facebook-pagina staat in het tabblad: `favicon.png` (32), `favicon-180.png` (beginscherm telefoon) en `favicon.ico` (16/32/48 voor oudere browsers), plus een route op `/favicon.ico` omdat browsers en bots dat adres kaal opvragen. Achter de bestandsnaam staat `?v=1`; browsers houden een favicon hardnekkig vast, dus bij vervanging moet dat cijfer omhoog |
| Terugblik | op de voorpagina zes kaarten met de nummer 1 van deze week, tien tot **zestig** jaar geleden. Zestig haalt net de eerste jaargang; ontbreekt zo'n week, dan valt de kaart weg in plaats van leeg te blijven |
| Stipnotering | een ring om de positie op de weeklijsten van de Top 40 en Sterren NL: de gewone stip een gevulde rode schijf, de **superstip** een open ring — zoals top40.nl het tekent. Een onderscheiding voor een plaat die die week hard steeg; 39.538 en 2.901 noteringen, 1965 tot nu. Niet in de Tipparade: daar draagt ruim de helft van alle regels de markering en onderscheidt hij dus niets |
| Oranje Kroon | kroontje 👑 vóór de titel in de Oranje Top 30: de clip van de week van TV Oranje. Als de Alarmschijf een eigenschap van de plaat — eenmaal toegekend blijft hij staan. 6.620 noteringen over 685 nummers, vanaf 2012 |
| Gedeelde plek | een **gele** ring om de positie als meerdere uitvoeringen die plek deelden, een **lichtblauwe** als het een dubbele A-kant is. Aan de artiest is dat verschil niet te zien (229 dubbele A-kanten hebben per kant een andere artiest), dus het staat vast in `noteringen.dubbele_a`. Draagt de plek ook een stip, dan komt de ring er als schaduw omheen |
| Legenda | onder de kop van elke weeklijst, en alleen voor de tekens die er die week ook echt staan — een Top 40 uit 1965 krijgt geen uitleg over de Alarmschijf, die toen nog niet bestond |
| Nederlandstalig | rood-wit-blauw vlaggetje voor de titel, op elke lijstpagina én de wetenswaardigheden óók als filter (checkbox "NL"; de weetjes-ranglijsten rekenen zichzelf dan opnieuw uit over alleen Nederlandstalig, en de ter-plekke gebouwde Excel- en PDF-downloads filteren mee, met `_NL` in de bestandsnaam); herkenning in drie trappen — lijstbewijs (Oranje/Sterren NL zijn per definitie Nederlandstalig), artiestroute en titel-woordenlijst — met handmatige correctie op de nummerpagina die altijd wint |
| Jaarlijsten totaal | alle zeventien jaarlijkse lijsten samen, genormaliseerd: elke notering telt (lengte − positie + 1) ÷ lengte, dus de nummer 1 van élke lijst is één punt waard |
| Beheer | alles wat de opdrachtregel kan, ook als knop — plus een knop **Onderhoudspagina aanzetten** (zie BEHEER.md) — plus **Bijwerken wat veranderd is** (alleen de geraakte jaargangen), voortgangsbalken per stap, en een taakstand die een herstart overleeft |
| Wetenswaardigheden | tien ranglijsten over de hele historie, per lijst |
| Gastenboek | gepubliceerde bezoekersberichten, met eventueel een antwoord van de beheerder eronder |
| Bericht achterlaten | formulier voor opmerkingen, tips, bugs en aanvullingen; spamwering met honeypot, invultijd en per-IP-limiet, geen CAPTCHA; alles komt privé binnen en niets staat live zonder akkoord |
| Berichten | (achter de login) de postbus: publiceren, privé houden, verwijderen of beantwoorden; mailmelding bij elk nieuw bericht |
| Disclaimer | hobbyproject, bekende zwakke plekken, rechten, privacy; volledig tweetalig, en het contact-blok verwijst naar het feedbackformulier (geen klikbaar mailadres meer op de site) |
| Vormgeving | menubalk in twee rijen (de lijsten boven, de extra's en het beheer gedempt eronder), doorschijnend over de banner en met blur zodra er gescrold is; tabellen tot 100 rijen krijgen hun volle hoogte (geen binnenste scrollbalk), daarboven een scrollvak van 78vh; onder de 760px compact en niet-plakkend |
| Banner | eigen ontwerp, vast aan de bovenrand achter de doorzichtige menubalk (die dichtgaat na scrollen); dezelfde banner siert de kop van elke PDF en is de og:image van gedeelde links |
| Facebook (bericht) | de vrijdagrun plaatst een berichtje met de nieuwe nummer 1, de binnenkomers (max. 8, met Alarmschijf-belletje), de grootste stijger en **één regel per andere weeklijst** (Tipparade, Oranje Top 30, Sterren NL Top 25: wie op 1 staat + aantal binnenkomers én herintreders — geteld, niet bij naam, want de Oranje Top 30 haalde ooit acht herintreders in een week; alleen dezelfde week en alleen als die lijst toen bestond), plus een link naar het weekbericht — via de Graph API (`/{pagina}/feed`). Alleen bij een **nieuwe Top 40-week**, want anders plaatst een stille run dezelfde week opnieuw; nooit bij `--geen-mail`; en zonder `facebook.ini` (buiten git, bevat het token) gebeurt er niets — publiceren hoort een bewuste keuze te zijn, geen gevolg van een uitrol. `python -m hitlijsten facebook` toont de tekst, `--plaats` zet hem er echt op. **Geen lege regel na de kop**: Facebook klapt een bericht in na een paar regels en telt die lege regel mee, waardoor er in de tijdlijn alleen een titel met *Meer weergeven* stond — regel twee moet het nieuws dragen. Twee dingen die ik in de proef rechtzette: `weken_genoteerd` telt weken *in de lijst* en niet weken *op 1* (de zin noemt dat nu apart), en de legenda voor het belletje verscheen op grond van de hele Top 40 terwijl hij hoort bij de getoonde binnenkomers |
| Facebook (link) | de voettekst verwijst naar de pagina [Nederlandse Hitlijsten](https://www.facebook.com/nederlandsehitlijsten) (tweetalig, één `{% set %}` voor het adres zodat NL en EN niet uit elkaar kunnen lopen). Profielfoto en omslagfoto zijn in dezelfde huisstijl gemaakt; de omslag houdt alle tekst in de bovenhelft, want Facebook legt de profielcirkel op 54% van de hoogte, en noemt **geen** aantal noteringen — dat loopt elke vrijdag op |
| Bronvermelding | de voettekst met bronnen staat **alleen op het Overzicht** (`request.endpoint == 'overzicht'`); herhaald onder elke lijstpagina werd het behang. De naamsvermelding blijft compleet, want de disclaimerpagina noemt top40.nl, oranjetop30.nl en datastats.nl ook voluit, en die staat in de menubalk. Op het Overzicht linken de vier weeklijstnamen naar hun bronsite en de zendernamen naar de zender (`BRON_URLS` / `ZENDER_URLS` in config.py — gegevens over de lijst, niet iets voor een sjabloon; alle adressen opgevraagd vóór ze erin gingen, arrowclassicrock.nl → arrow.nl). De verwijzing naar de Facebook-pagina is het merkteken zelf, als **inline SVG** — geen bestand en geen verbinding met Meta op een site die verder niets van buiten haalt; grijs in rust, merkblauw bij aanwijzen, met `title`+`aria-label` in beide talen. Omdat de voettekst alleen hier staat, krimpt de ondermarge van `main` daar via `main:has(+ footer)` — anders telt die vier rem op bij de padding van de footer |
| Beheerbalk | de beheerlinks (Berichten, Aliassen, Uitzonderingen, Query, Beheer, Logboek) staan op een **eigen regel in de menubalk** en in geel (`--beheer: #ffc857`): daar wijzig je gegevens, en dat hoort zichtbaar anders te zijn dan rondkijken. De rij rendert alleen bij `is_aangemeld()`, dus een bezoeker krijgt hem niet in de HTML — nagekeken op de uitgelogde pagina |
| Feedback | staat sinds de voettekst-ingreep in de **tweede menubalk** (naast Gastenboek) en geeft `pagina=request.path` mee, zoals de oude voettekstlink deed; zonder die ingang had een bezoeker die iets ziet dat niet klopt geen weg meer naar het formulier |
| Snelheid | de webapplicatie draait als **één proces met acht threads** (waitress), dus meer bezoekers tegelijk maakt niets sneller: Python's threads draaien om beurten. Gemeten op de NAS (Ryzen R1600): weeklijst 58 ms, weekbericht 30 ms, zoeken 4 ms, jaaroverzicht 255 ms (639 kB), totaallijst 195 ms — ~15 verzoeken/sec in totaal. De **voorpagina** kostte 790 ms (een `GROUP BY` over alle noteringen + per jaarlijkse lijst een telling voor de editielengtes) en liep vast op 2,6/sec; sinds de cache 15 ms en ~75/sec. Stempel = (aantal noteringen, laatste ophaalmoment) — genoeg omdat er alleen tellingen in zitten, geen namen; de taakstand blijft er bewust buiten. **Bandbreedte is de rem niet:** een eerste bezoek is ~122 kB (35 kB HTML + 87 kB banner), en bij ~930 Mbit upload zou de lijn honderden bezoekers per seconde aankunnen — honderden malen meer dan de NAS |
| Vaste paginakop | de `h1` en de regel eronder blijven staan bij het scrollen. Ze worden door het scriptje in `basis.html` **in de menubalk gezet** (derde rij, `.paginakop`) en niet in een eigen band eronder: twee `backdrop-filter`-lagen naast elkaar blurren elk hun eigen stuk achtergrond, en omdat de banner naar beneden dimt zie je precies op de grens een randje. Eén ruit heeft dat niet. Het verplaatsen gebeurt in JavaScript en niet in de 29 sjablonen zelf; de hoogte van de menubalk komt uit een gemeten `--menuhoogte`, want die balk wrapt en een vast getal zou de kop er bij een smal venster onderdoor laten schuiven. Onder 760 px plakt hij niet, dezelfde afweging als bij de menubalk daar. Ook de **tabelkop** blijft staan bij een `past`-tabel (≤100 rijen, waar de pagina scrolt in plaats van het vak): `sticky` werkt daar tegen de scrollport van `.tabelvak` en die scrolt niet, dus krijgt zo'n vak `overflow: visible` — maar **alleen als de tabel horizontaal past**, want overflow-x en -y zijn niet los in te stellen en een brede matrix zou zijn schuifbaarheid verliezen. Het scriptje meet dat per tabel, opnieuw bij elke maatverandering. Boven **een derde van de vensterhoogte** aan vaste balken zet het scriptje de kop terug in de pagina: op een half venster wrapt de menubalk naar vier regels en de ondertitel naar drie, en dan lees je door een kier. Valkuil: `header .binnen` is een flexrij, dus die rij moet expliciet `display: block` krijgen om te stapelen |
| Compressie | tekstantwoorden gaan **gzipped** de deur uit (`_comprimeren`, after_request): het jaaroverzicht 707 → 47,6 kB, de voorpagina 39,9 → 11,7 kB. In de applicatie en niet in nginx, want DSM genereert het serverblok van hitlijsten uit `ReverseProxy.json` en overschrijft handmatige regels. Raakt niet aan: al ingepakte antwoorden, `direct_passthrough`-stromen (send_file — `get_data()` zou de download breken), niet-teksttypen en alles onder 1 kB. `Vary: Accept-Encoding` gaat mee |
| Nummerpagina | de noteringen **per lijst**, in twee tabellen: week- en jaarlijsten apart, want ze meten iets anders (wat er destijds verkocht werd tegenover waar mensen jaarlijks op blijven stemmen). Bij de hoogste positie staat **hoe vaak** die gehaald is — Bohemian Rhapsody heeft `1 (22×)` bij de Top 2000 en `1 (3×)` bij de Top 40, en dat contrast is het hele verhaal van een klassieker. Onder **Wetenswaardigheden** de golven: "Top 40, 1975–1992" suggereert zeventien jaar onafgebroken terwijl het twee periodes waren met vijftien jaar stilte ertussen (de heruitgave na het overlijden van Freddie Mercury). Een gat van twee jaargangen telt als nieuwe golf, zodat een notering over de jaarwisseling één periode blijft; alleen weeklijsten, want bij een jaarlijst is elke editie per definitie een los moment. Valkuil: het grafiek-id (`#perlijst`) moet meeverhuizen naar de jaartabel als een nummer alleen daarin voorkomt, anders vindt het grafiekscript zijn bron niet |
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

### Verhuisd naar nl-hitlijsten.nl

De site draaide op `hitlijsten.hhaken.nl` — een subdomein van een privédomein,
wat voor een publiek archief een vreemde plek is. Sinds 19 augustus 2026 heet
hij **www.nl-hitlijsten.nl**. Het oude adres blijft bestaan en stuurt door.

Het adres staat sindsdien op **één plek**, `config.HOOFD_URL`. Daarvoor stond
het letterlijk in elf bestanden — de webapplicatie, het Facebook-bericht, drie
PDF-generatoren, de DJ Export en zelfs de User-Agent waarmee MusicBrainz wordt
bevraagd. Bij zo'n verhuizing vergeet je er dan gegarandeerd een.

De doorverwijzing zit in de **applicatie**, niet in de reverse proxy: DSM
schrijft `ReverseProxy.json` bij elke wijziging opnieuw uit, dus een regel die
je daar met de hand inzet is bij de eerstvolgende aanpassing weg. Een
`before_request` stuurt alles wat op `hitlijsten.hhaken.nl` of op de kale
`nl-hitlijsten.nl` binnenkomt door naar de hoofdnaam, met pad en queryreeks —
via dezelfde `_canoniek()` die ook de canonical-link bouwt, zodat
`/nummer/golden earring|radar love` netjes percent-gecodeerd overkomt.

**Voorlopig een 302 en geen 301.** Een 301 wordt door browsers hard onthouden;
gaat er iets mis, dan zit dat dagen vast in caches die niemand kan legen. Zodra
de verhuizing een dag goed loopt gaan de omleiding in de applicatie én de regel
in `/volume1/web/.htaccess` samen op 301 — pas dan telt Google de verhuizing
mee, en pas dan hoort de adreswijziging in Search Console te worden ingediend.

Drie dingen die bij de verhuizing hoorden en makkelijk te missen zijn: het
wildcard `*.hhaken.nl` dekt de nieuwe naam **niet** (er is een eigen
Let's Encrypt-certificaat voor `nl-hitlijsten.nl` + `www.nl-hitlijsten.nl`), de
`.htaccess` die http naar https tilt toetst op hostnaam en liet de nieuwe naam
dus aanvankelijk op de persoonlijke startpagina landen, en de kale vorm zonder
www hoort ook door te sturen — anders staat dezelfde site op drie adressen en
telt een zoekmachine hem als drie.

### Aliassen die niet meer kunnen afgaan

Een alias die naar een sleutel wijst die geen enkele notering draagt, ziet er
dood uit. Dat is hij lang niet altijd. Van de 129 zulke regels bleken er drie
soorten te bestaan:

| | | |
|---|---|---|
| **80** | dood | weggehaald |
| **39** | wachtend | moeten juist blijven |
| **10** | ketenschakel | moeten blijven |

**De tachtig dode zijn allemaal hetzelfde geval**, en dat is de prijs van een
eerdere opschoning. Tot begin augustus 2026 werd een apostrof bij het
normaliseren een **spatie**; sinds de punt-en-apostrof-ronde verdwijnt hij
spoorloos. Elke alias die onder de oude regel geschreven was, heeft daardoor
een bronsleutel die niets meer voortbrengt: `you ve lost that lovin feelin`
bestaat niet meer, het is `youve lost that lovin feelin`. Die regels kunnen
sindsdien niet meer afgaan.

Dat ze echt dood waren is niet beredeneerd maar **gemeten**: van alle 36.028
voorkomende artiest/titel-combinaties is de sleutel berekend vóór en ná het
schrappen, en er veranderde er geen enkele.

**De negenendertig "wachtende" bleken helemaal niet te wachten.** Daar staat
zowel `ac dc|thunderstruck → acdc|thunderstruck` als de omgekeerde regel. Zo'n
lus is met opzet onschadelijk: `_volg_alias` ziet hem, stopt, en geeft
`min(gezien)` terug — "kies een vaste vertegenwoordiger, zodat alle leden er in
elk geval op dezelfde uitkomen". Een spatie sorteert vóór een letter, dus de
uitkomst is altijd `ac dc|…`. Beide schrijfwijzen belanden op dezelfde sleutel,
de samenvoeging wérkt, en daarom verzette een hersleutel over alle 62
jaargangen precies nul sleutels.

Ik heb daar één keer de verkeerde conclusie aan verbonden en de "tegenrichting"
weggehaald, waarna AC/DC, Mooi Wark en OG3NE op een samengetrokken sleutel
uitkwamen. Dat is teruggedraaid. De richting in deze database is namelijk
consequent: een alias wijst naar de sleutel van de **vastgestelde schrijfwijze**,
hoe die er na het normaliseren ook uitziet. "AC/DC" levert `ac dc` op, en dus
wijst alles daarheen — er staan drieënnegentig soortgelijke aliassen die dat
bevestigen (`beegees → bee gees`, `duranduran → duran duran`,
`no doubt|dont speak → no doubt|don t speak`). Aan die lussen valt niets te
verbeteren; ze zijn lelijk maar correct.

**En tien zijn ketenschakels.** Wie drie schrijfwijzen samenvoegt schrijft
twee regels, `a→b` en `b→c`; de tussenstap draagt per definitie niets, maar
weghalen breekt de hele samenvoeging. Een keten telt alleen als levend als er
aan het eind ook echt noteringen hangen — anders is hij net zo dood als een
losse regel, en zo zijn er ook een paar in de eerste groep beland.

### De sleutel staat in de URL, en dat heeft een prijs

Een nummerpagina heet `/nummer/<sleutel>`. Dat is prettig leesbaar, maar het
betekent ook dat **elke wijziging in de normalisatie webadressen breekt**. De
twee ingrepen van augustus 2026 samen hernoemden **4.929 sleutels** —
`10cc|i m not in love` werd `10cc|im not in love` — en evenzoveel bewaarde of
gedeelde links gaven daarna een 404. Intern viel dat niet op, want alle links
worden uit de database gebouwd; juist daarom is het pas achteraf gemeten, door
de database tegen de momentopname te leggen.

Daarvoor is er nu de tabel **`oude_sleutels`** (oud → nieuw), en beide routes
verwijzen bij een onbekende sleutel door met een **301** in plaats van te
stoppen bij 404. Ook de artiestpagina: `simon and garfunkel` werd
`simon & garfunkel`. De doorverwijzing controleert eerst of het doel bestaat —
anders zou een kapotte keten een lus worden — en volgt ketens door, want bij
twee opeenvolgende normalisatiewijzigingen wijst de eerste verhuizing naar een
adres dat zelf ook al verhuisd is.

**Bewust een eigen tabel, niet `aliases`.** Die laatste bevat gecureerde
beslissingen ("dit is dezelfde plaat", nagekeken tegen MusicBrainz), telt mee
bij het *berekenen* van sleutels, en wordt elke run naar CSV geëxporteerd.
Een verhuisbericht is iets anders: mechanisch, bij duizenden tegelijk, en het
mag nooit invloed hebben op wat een sleutel wordt. Vierduizend regels ertussen
zouden die curatie onleesbaar maken.

`hersleutel` legt verhuizingen sinds deze ronde **zelf** vast, dus de volgende
normalisatiewijziging regelt dit vanzelf. Een splitsing valt daar niet onder --
daar verdwijnt een sleutel in plaats van dat hij verandert -- dus die legt zijn
eigen omleidingen aan (34 stuks). De 4.929 van augustus 2026 zijn
nagekomen uit de momentopname: notering-id's zijn stabiel, dus een join tussen
de opname en de database van nu geeft precies waar elke sleutel heen ging.

### Twee stille fouten, gevonden doordat er iets naast kwam te staan

**De hoogste positie werd afgekapt op 99.** De startwaarde voor het minimum was
`99`, en `min()` maakt daar nooit meer 1279 van. Elke plaat die in een Top 2000,
Top 4000 of Evergreen Top 1000 lager dan 99 stond, kreeg "99" te zien. De fout
zat er al langer, maar viel pas op toen week- en jaarlijsten in aparte tabellen
kwamen te staan: dan staan er ineens vijf negenennegentigen onder elkaar.
Startwaarde is nu `None`, met een expliciete controle bij de eerste notering.
In `kruiscontrole.py` staat hetzelfde patroon, maar die werkt uitsluitend op
weeklijsten (posities tot 40) — daar kan 99 geen kwaad.

**De bouw-wachtrij liep vol.** `db.gebouwd()` bestond al, netjes geschreven,
maar werd nergens aangeroepen: `opdracht_excel` schreef de bestanden en liet de
markering in `te_bouwen` staan. Zolang je alleen de vrijdagrun draait valt dat
niet op, want die markeert en bouwt in één beweging. Na een `hersleutel` over 62
jaargangen stonden er in één klap **380 markeringen** voor bestanden die er
allang waren, en het beheerscherm meldt die als "openstaand". `opdracht_excel`
ruimt nu op wat het gebouwd heeft — voor de hele jaargang tegelijk, want
`bouw_alles` doet per definitie alle lijsten van dat jaar.

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
| Versies die een plek deelden | 1.115 weekregels → 2.471 | de weeklijst zelf + eigen keuzelijst |
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
Tipparade, die echte gedeelde posities kent. In de weeklijst staat het aantal
er sindsdien bij als het afwijkt — "56 noteringen op 40 plekken" — want een
Top 40 met 56 regels leest anders als een fout.

**Twee regels op één plek zijn twee verschillende dingen**, en dat is aan de
lijst te zien: geel voor meerdere uitvoeringen die de plek deelden,
lichtblauw voor een dubbele A-kant. Aan de artiest is het onderscheid niet te
maken — 229 dubbele A-kanten hebben per kant een ándere artiest ("De Dijk ;
The Scene") — dus het staat vast in de kolom `dubbele_a`, gevuld uit de bron:
top40.nl scheidt de twee kanten met een puntkomma in de titel. 3.735
noteringen op 1.817 plekken, en geen enkele plek is allebei; dat is over het
hele archief nagerekend. Dat komt vaker voor dan je
denkt: 1.269 Top 40-weken, 719 Tipparade-weken en 38 weken van de Oranje Top
30 hebben meer noteringen dan plekken. **De positie telt één keer**: beide
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

**En die correctie verdampte.** Bij een tweede ronde in augustus 2026 stonden
er weer 299 nummers met een onmogelijk uitjaar — Space Oddity incluis, maar nu
alleen nog in Toplijst jaren 60, de lijst die er op 12 augustus bijkwam. De
negen andere lijsten zeiden keurig 1969. Elke nieuwe import brengt namelijk het
uitjaar van de bron mee, en een losse correctie achteraf overleeft dat niet.
**Deze toets hoort dus bij het inlezen te horen**, niet bij een opschoonronde.

Die tweede ronde is nu wel breder gedaan: niet alleen tegen de Top 40 maar ook
tegen de Tipparade, wat het aantal toetsbare nummers van 6.004 op **8.221**
brengt. 299 nummers gecorrigeerd, samen 7.175 noteringen, waarna er nul
tegenspraken over zijn. De verdeling is geruststellend: 281 zaten er één jaar
naast — jaargrensruis, of een bron die het albumjaar noemt — en maar 18 meer
dan dat. Die achttien waren wel grof: *Drop The Pressure* van Mylo stond op
2022 terwijl het in 2004 al noteerde, *If It Makes You Happy* van Sheryl Crow
op 2009 tegen 1996.

De andere kant is óók bekeken en daar is niets mis: twaalf nummers hebben een
uitjaar meer dan 25 jaar vóór hun eerste notering, en dat klopt allemaal —
*White Christmas* (1947) werd hier pas in 1977 een hit, *Heartbreak Hotel*
(1956) pas in 1987.

**Voor de 5.447 nummers zonder eigen notering helpt MusicBrainz niet.** Die
staan in geen enkele weeklijst, dus daar is geen ijkpunt. Een steekproef van
twintig bekende nummers liep stuk op de aard van de catalogus: een zoekopdracht
op opname levert vooral heruitgaven en verzamelaars op. *No Woman, No Cry*
kwam terug als 1990, *Wish You Were Here* als 2001, *Paradise By The Dashboard
Light* als 2013. Vijf keer breder zoeken hielp maar half — *Desperado* en
*Eye Of The Tiger* kwamen dan wél goed uit, maar de eerste twee nog steeds
niet, en twee zoekopdrachten gaven helemaal niets meer terug. Op 5.447 nummers
zou dat meer bederven dan repareren, terwijl de bron juist betrouwbaar blijkt
waar we hem kúnnen controleren. Dus niet gedaan.

**De sleutel is waar het pijn doet.** Een verkeerd leesteken is lelijk maar
onschuldig: de sleutel gooit leestekens toch al weg. Erger is wat de sleutel
wél raakt. "Beatles" en "The Beatles" leverden twee gescheiden geschiedenissen
op, en "Crocodille Rock" naast "Crocodile Rock" splitste één nummer in tweeën —
met verdeelde punten en twee halve noteringen in de jaarlijst.

**Drie fouten in de normalisatie zelf** kwamen bij dit werk boven water. De
eerste: een lidwoord vooraan de artiestnaam telde mee, terwijl de bronnen het er
niet over eens zijn (top40.nl schrijft "The Beatles", Music Datastats schrijft
"Beatles"). De tweede: `normaliseer()` haalt accenten weg door letters te
ontleden — é wordt e plus een tekentje — maar de ø van Bløf is een eigen letter.
Die overleefde de ontleding en werd daarna als rommel geschrapt, waarna "Bløf"
als "bl f" naast "Blof" stond. Nu vertaald, samen met æ, ß, ł en een stuk of tien
andere.

De derde kwam pas boven toen een bezoeker een cijfer op de Facebook-pagina
betwistte (aug 2026). `_EN` trok `&`, `+`, `x` en `vs` gelijk, maar **niet het
woord "and"** — en daar loopt precies de scheidslijn tussen de bronnen: top40.nl
schrijft "Simon and Garfunkel", Music Datastats "Simon & Garfunkel". Gevolg:
**131 platen lagen in tweeën**, de weeklijsten op de ene sleutel en de
jaarlijsten op de andere, en op geen van beide pagina's het hele verhaal.
Purple Rain, Bridge Over Troubled Water, Band On The Run — 5.066 noteringen.

Titels kregen een **eigen, smallere regex** (`_EN_TITEL`). Die draaien bewust
met `samenwerking=False` omdat "x" er een letter is (Malcolm X) en "vs" bij de
titel hoort; alleen `&` en `and` worden er gelijkgetrokken. Zonder die splitsing
zou "Malcolm X" veranderen in "Malcolm &".

**Vooraf twee proefdraaien** die niets wijzigden maar wel uitrekenden wat er zou
samenvallen — de enige manier om te zien of er geen covers op één hoop belanden.
Uitkomst: nul samenvoegingen waarbij de artiest verschilt, dus East Side Beat
bleef los van Simple Minds en O'Hara's Playboys los van de Bee Gees. Twee
gevallen die verdacht leken (Despacito, Pilé) bleken **verouderde sleutels die
niet meer bij hun eigen titel pasten**; die zijn meegerepareerd.

Wat een `hersleutel` over álle jaargangen vraagt: die opdracht draait **per
jaargang**, dus een lus over `SELECT DISTINCT jaar`. Daarna de Excel-bestanden
herbouwen (62 jaargangen, ruim een kwartier).

**Zes gevallen blijven bewust staan**, met een andere oorzaak: punten en
apostrofs in de artiestnaam ("K.C." tegenover "KC", "The Mama's and The Papa's"
tegenover "The Mamas & The Papas", "Patti La Belle" tegenover "Patti Labelle").
Daar zou het wegstrepen van spaties ook echt verschillende artiesten kunnen
raken, dus dat vraagt een eigen afweging.

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
| `A / B` bij artiest én titel | twee opnamen op één plek | splitsen (1.115 weekregels, 1965–2026) |
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

### Eén plek, meerdere uitvoeringen

In de jaren zestig kwam het geregeld voor dat een nummer in meerdere
uitvoeringen tegelijk populair was, en de Top 40 zette die dan **samen op één
plek**. In het archief stonden ze als één regel met schuine strepen:

```
1965 wk 4   #29  Orkest Gudrun Jankis / Stig Rauno / Jan Rohde & The Wild Ones
                 Let Kiss / Letkis / Letka Jenka
```

Voor een DJ zijn dat drie platen. Ze staan nu als drie regels, **allemaal op
plek 29 en allemaal met de punten van plek 29** — niet opgeteld, net als bij de
dubbele A-kant. Dat raakte 993 weekregels in de Top 40 (die 2.229 werden) en
122 in de Tipparade (242). De Top 40 groeide van 129.170 naar 130.105
noteringen, de Tipparade van 91.397 naar 91.526.

**De weeklijst beslist, niet de notering.** Dit was de eerste aanname die
sneuvelde. Het lag voor de hand om per *nummer* te beslissen en dan alle weken
van die notering te splitsen, maar zo werkt het niet. Ed Sheeran deelde in 2025
maar **één** van zijn 26 weken de plek met de Googoosh-versie van *Azizam*; de
andere 25 stond hij alleen. En andersom wisselt de samenstelling van week tot
week. *Let Kiss* stond eenentwintig weken in de lijst, en de bezetting van die
plek veranderde drie keer:

| weken | wie er op die plek stonden |
|---|---|
| 3–4 | Orkest Gudrun Jankis · Stig Rauno · **Jan Rohde & The Wild Ones** |
| 5–12 | Orkest Gudrun Jankis · Stig Rauno |
| 13–16 | Orkest Gudrun Jankis · Stig Rauno · **The Dutch Swing College Band** |
| 17–23 | Orkest Gudrun Jankis · Stig Rauno |

Was ik van de notering uitgegaan, dan had Jan Rohde in alle eenentwintig weken
gestaan — inclusief de veertien waarin zijn versie er niet bij hoorde — en had
de Dutch Swing College Band óf overal, óf nergens gestaan. Wat er gesplitst
wordt komt dus uit de lijst van díé week; alleen de schrijfwijze van de namen
komt uit een vaste keuzelijst.

**Waar het één keer misging.** De koppeling van een blok aan een regel uit de
keuzelijst ging op naamgelijkenis van de hele artiestenreeks, en dat is een
keer te grof gebleken. *Ed Sheeran / Ed Sheeran & Beyoncé — Perfect* (2017)
lijkt als reeks sterk op *Ed Sheeran / Ed Sheeran & Googoosh — Azizam* (2025):
alleen het laatste woord verschilt. Negentien noteringen van Perfect kregen
daardoor de titel Azizam.

Het viel niet op aan de lijst zelf — het tweede deel van de plek bleef gewoon
"Ed Sheeran & Beyoncé | Perfect" — maar wel aan de **jaargangen**: Azizam stond
met 45 weken en 1466 punten bovenaan het puntenklassement aller tijden, met een
binnenkomst in december 2017 terwijl de plaat uit 2025 is. Een nummer dat pas
bestaat kan niet acht jaar eerder binnenkomen, en dat is precies het soort
tegenspraak waarop je zulke fouten vindt.

De controle achteraf is simpel en had meteen gemoeten: leg van elke gesplitste
plek de titel in de database naast de titel die de bron die week toonde. Over
alle 1.115 gesplitste weekregels leverde dat precies dit ene geval op. De
sleutel van Perfect blijft trouwens de gecombineerde: dezelfde plaat staat in
de Top 2000, Top 4000 en Veronica nog als één regel, en die hoort bij elkaar.

**De volledige tekst staat in een attribuut.** De zichtbare regel op top40.nl
is afgekapt (`Orkest Gudrun Jankis / Stig Rauno / Jan Rohde..`) en de
aria-label — waar de gewone parser op leunt omdat die tussen weken stabiel is —
noemt bij een gedeelde plek soms maar de eerste uitvoering. Alleen
`title="Details ..."` bevat alles. Wie dat over het hoofd ziet splitst netjes
in twee regels waar er drie hadden moeten staan.

**Aliassen trekken de splitsing meteen weer dicht.** Eerdere opschoonrondes
hebben aliassen aangelegd die een losse uitvoering aan de gecombineerde
notering koppelen: `shirley bassey|goldfinger` → `shirley bassey john barry zz
& de maskers the jets|goldfinger`. `sleutel_van()` volgt die aliassen, dus
zolang ze er staan krijgt de verse regel "Shirley Bassey — Goldfinger"
onmiddellijk de sleutel van de combinatie terug en is de splitsing onzichtbaar.
Eerst opruimen dus, dan pas splitsen.

Zoeken op "aliassen waarvan het doel verdwijnt" is daarbij niet genoeg. Het
doel bestaat soms helemaal niet als sleutel: `clinton ford|dandy` wees naar
`clinton ford the kinks herman s hermits|dandy` — met een spatie die nergens in
de database voorkomt. De toets moet vanaf de andere kant: bereken van elke
nieuwe regel de sleutel zónder alias, volg de alias, en kijk of daar na het
splitsen nog een notering op staat. Zo niet, dan wijst hij in het niets en moet
hij weg.

**Twee schrijfwijzen is een samenvoeging, geen splitsing.** `Elvis / Elvis
Presley`, `L.L. Cool J / LL Cool J`, `Guns N Roses / Guns N' Roses` — dezelfde
artiest, dezelfde plaat, alleen de bron is inconsequent. Die worden één regel.
Vallen twee delen zo samen, dan wint de **volledigste** schrijfwijze van de
naam: "Guns N' Roses" verslaat "Guns N Roses", "The Spencer Davis Group"
verslaat "Spencer Davis Group".

**Op naam alleen matchen gaat mis.** Om de goede schrijfwijze bij een
uitvoering te vinden werd elk deel met de keuzelijst vergeleken. Op artiestnaam
alleen liep dat twee keer stuk. *Mwaki* heet in beide uitvoeringen "Zerb &
Sofiya Nzau" en verschilt alleen in de titel — beide delen kozen dezelfde regel
en de notering klapte in elkaar. Op artiest plus titel samen ging het
vervolgens fout bij Rudy Bennett en Tim Hardin: de lange toevoeging achter Tim
Hardins titel (*Titelsong uit de film "Zoeken naar Eileen"*) overstemde het
naamverschil, zodat Tim Hardin bij Rudy Bennett belandde. Het werkt pas met
artiest en titel apart gewogen (0,65 / 0,35) én een **één-op-één-toewijzing**:
elk deel hoogstens één regel uit de keuzelijst, elke regel hoogstens één deel.

**Dubbele blokken in de bron.** In sommige weken staat dezelfde notering twee
keer in de opgeslagen pagina. Het plan kwam dan tweemaal langs dezelfde
databaserij: één keer verwijderen, twee keer terugschrijven. Dat leverde 328
dubbele regels op, die achteraf zijn opgeruimd — maar alleen op de posities die
deze ronde raakte. Elders in het archief staan nog 39 dubbele regels (3JS in
2011 bijvoorbeeld); die stonden er al en horen bij een andere opdracht.

**De oude sleutels leiden door.** De gecombineerde sleutel verdwijnt en dus ook
zijn adres. Alle 34 verdwenen sleutels staan in `oude_sleutels` en leiden met
een 301 door naar de eerste uitvoering:
`/nummer/bambis rocco granata peppino di capri|melancholie` komt uit bij
`/nummer/bambis|melancholie`.

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

### De stip en de superstip

De Top 40 kent sinds de jaren zestig de **stipnotering**: een onderscheiding
voor een plaat die hard stijgt of hoog binnenkomt. De criteria zijn scherp — en
de gegevens houden zich er precies aan:

| | krijgt hem bij | staat nooit lager dan |
|---|---|---|
| **stip** | binnenkomen op 30 of hoger, 3+ plaatsen stijgen tussen 30 en 11, elke stijging binnen de top 10 | 30 |
| **superstip** (sinds 1983) | binnenkomen op 25 of hoger, 10+ plaatsen stijgen tussen 25 en 11, 5+ plaatsen stijgen binnen de top 10 | 25 |

Die twee grenzen zijn niet uit de documentatie overgenomen maar in het archief
**gemeten**: over 1965–2026 komt geen enkele stip onder plek 30 voor en geen
enkele superstip onder plek 25. Ze sluiten elkaar ook uit — geen enkele
notering draagt ze allebei.

top40.nl zet ze in de HTML als de klassen `dot` en `super` op het lijst-item,
naast `hitrecord` (de alarmschijf), `new` en `nr1`. Ze staan dus in elke
opgeslagen weekpagina, en daarmee kon de hele reeks 1965–2026 in één keer
worden aangevuld zonder de site opnieuw te bevragen: 27.708 stippen en 11.830
superstippen.

**In de Top 40 en in Sterren NL, niet in de Tipparade.** top40.nl zet dezelfde
klassen op alle drie, maar of ze iets bétekenen verraadt de grens:

| lijst | stip | superstip | laagste plek met een stip |
|---|---|---|---|
| Top 40 (40 lang) | 21% | 9% | 30 / 25 |
| Sterren NL (25 lang) | 24% | 8% | **20 / 15** |
| Tipparade (30 lang) | **55%** | **30%** | 30 / 25 |

Sterren NL heeft zijn eigen grens, netjes geschaald naar een Top 25 — geen
enkele stip onder plek 20, geen enkele superstip onder 15 — en ongeveer
hetzelfde aandeel als de Top 40. Daar is het dus dezelfde onderscheiding.

De Tipparade niet. Daar draagt ruim de helft van alle regels een stip, en de
grens valt samen met de lengte van de lijst en zegt dus niets. Dat is ook
logisch: in een lijst waarin per definitie bijna alles stijgt, onderscheidt
"stijgt hard" niemand meer. De Oranje Top 30 komt van een andere bron en kent
de markering niet.

De parser vult het veld daarom alleen voor `top40` en `sterrennl` — 39.538 en
2.901 noteringen.

**De weergave volgt top40.nl, ook waar dat tegen het gevoel in gaat.** De
gewone stip is daar een *gevulde* rode schijf en de superstip juist een *open*
ring — de zwaarste onderscheiding krijgt dus de lichtste vorm. Week 4 van 1965
laat het zien: Petula Clark met *Down Town* ging van 8 naar 3, vijf plaatsen
binnen de top 10, en dat is het superstip-criterium; zij staat er met een open
kader, terwijl Cliff Richard op 4 met zijn gewone stip een gevuld kader
krijgt. Hier is het net zo, want wie de twee naast elkaar legt moet hetzelfde
zien.

Anders dan de alarmschijf hoort de stip bij de **week** en niet bij de plaat:
hij zegt iets over hoe de plaat het díe week deed. De alarmschijf blijft aan
een nummer plakken zolang het genoteerd staat.

### De Oranje Kroon

De Oranje Top 30 zet een kroontje bij sommige nummers, en nergens op
oranjetop30.nl staat wat dat betekent. Het is de **clip van de week van TV
Oranje**: elke week krijgt één nummer hem, en daarna blijft het kroontje bij
die plaat horen zolang hij genoteerd staat — net als de Alarmschijf bij de
Top 40.

Dat is niet aangenomen maar getoetst, op twee manieren. Week 33 van 2026 tegen
de winnaarslijst van TV Oranje gelegd, acht van acht raak, inclusief de enige
zonder kroon:

| | nummer | kroon | toegekend in |
|---|---|---|---|
| 1 | Justen de Wildt — Cheerio | ja | week 11, 2026 |
| 2 | Rutger van Barneveld — Zwoele zomernachten | ja | week 23 |
| 3 | Corry Konings — Er hangt iets in de lucht | ja | week 25 |
| 4 | Helemaal Hollands — Titanic | ja | week 30 |
| 5 | Tino Martin — Jong & dom | **nee** | — |
| 6 | Gebroeders Ko — Proud to be fout | ja | week 31 |
| 7 | Ferry de Lits & SHQQ — Baco in Monaco | ja | week 26 |
| 8 | Marco Schuitmaker — Loesoe | ja | week 32 |

En de aantallen: over 2012–2026 dragen **685 verschillende nummers** een kroon,
verdeeld over 6.620 noteringen. Dat is bijna precies één per week over die
periode — wat je verwacht bij een wekelijkse toekenning. Vóór 2012 staat het
plaatje niet in de pagina's; die weken lezen wel, maar hebben geen kroon.

In de HTML zit hij als een genest `<span>` binnen de titel, met
`<img class="ok">` voor het scherm en `<img class="okprint">` voor de
printversie. De parser haalde dat geneste span al weg om de titel schoon te
krijgen; nu leest hij er ook de kroon uit.

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

De grenzen zijn nagemeten (aug 2026), niet aangenomen. Wat wordt tegengehouden:
een `DELETE` verstopt achter een `WITH` (*not authorized*, 1 ms), een `ATTACH`
als tweede statement (één statement tegelijk), `readfile()` (bestaat niet in de
Python-koppeling), een kruisproduct van vier keer de hele tabel (afgebroken na
tien seconden) en een half miljoen rijen ophalen (`fetchmany(500)`).

**Wat er niet tegen beschermt, bewust:** één rij mag onbeperkt groot zijn.
`SELECT zeroblob(200000000)` levert een cel van 191 MB in 133 ms — te snel voor
de tijdrem, en met vijfhonderd van die rijen zit je over het geheugenplafond van
de dienst heen. Dan schiet systemd de webapplicatie af en is de site tien
seconden weg. Bewust gelaten: het scherm zit achter een aanmelding, dus dit is
jezelf in de voet schieten en niet een deur voor een ander. Een maat per cel of
een kortere rem lost het op als het ooit hindert.

**Afmelden gaat naar de voorpagina**, niet terug naar het aanmeldscherm: dat
laatste leest als een mislukte poging terwijl je juist weg wilde. Met een
bevestiging erbij (categorie `goed` — de site kent alleen `goed` en `fout` als
opmaakklasse, dus een verzonnen `gelukt` zou een kale regel geven), want anders
is het enige zichtbare verschil dat de gele beheerregel verdwenen is.

**Verder**: het CSRF-token wordt vernieuwd zodra je je aanmeldt (een token dat
iemand daarvóór bemachtigde is dan niets meer waard); sessiecookie met
`Secure`, `SameSite=Lax` en zeven dagen
levensduur (let op: aanmelden kan daardoor **alleen nog via HTTPS**, niet meer
rechtstreeks op `http://<nas>:8642`); beveiligingsheaders op elk antwoord
(CSP met `unsafe-inline` omdat de sjablonen hun stijl en scriptjes inline
dragen — de winst is dat er van geen enkele andere herkomst iets geladen mag
worden); vijf mislukte aanmeldpogingen per kwartier per IP mét logregel; geen
open redirect meer; **alle vier de plekken die een door de bezoeker
aangeleverd pad volgen** (`?volgende=` bij het aanmelden, `?terug=` bij de
taalkeuze, en `_eigen_pad()` op het pagina-veld van feedback en de terug-link
van het DJ Export-rapport) delen sinds aug 2026 één `_veilig_pad()`, zodat ze
niet meer uit elkaar kunnen lopen. `_eigen_pad()` zorgt bovendien dat er geen
`javascript:`-link in het pagina-veld kan wachten op een klik van de
beheerder. Die laatste
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

**HTTP stuurt door naar HTTPS.** In de reverse proxy staat voor elk hostname
van de site alleen een HTTPS-regel (443 naar 10.10.8.20:8642). Wie
`http://` intikte viel daardoor door naar de standaard-site van Web Station en
kreeg de persoonlijke startpagina van hhaken.nl te zien — met een keurige 200,
dus zonder enig teken dat hij verkeerd zat, en onversleuteld. Opgelost met een
`.htaccess` in `/volume1/web/` die alléén deze hostnames doorstuurt naar
https, met behoud van pad en queryreeks; de voorwaarde kijkt naar de Host-kop, dus
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

**Derde ronde (aug 2026), na de Facebook-, cache- en query-toevoegingen.**
De aanmeldrem bleek niet te omzeilen met een verzonnen `X-Forwarded-For`, maar
het mechanisme is anders dan je zou denken en dat is het opschrijven waard.
Nginx zet `X-Forwarded-For $proxy_add_x_forwarded_for` — dat **plakt** de kop
van de bezoeker ervóór, dus die is wél te beïnvloeden. Wat het tegenhoudt is
**waitress**: die strípt standaard alle proxy-koppen (`trusted_proxy` staat niet
ingesteld), zodat `X-Forwarded-For` de applicatie nooit bereikt. `X-Real-IP`
overleeft dat wél, en dáár leest `_bezoeker_ip()` het adres uit — maar nginx
overschrijft die met `$remote_addr`, wat een bezoeker niet kan vervalsen.
Gemeten: van buiten en vanaf een gewone LAN-machine (10.10.8.39) wordt een
gespooft adres genegeerd; alleen vanaf 127.0.0.1 of 10.10.8.20 — dus met een
voet op de NAS zelf — wordt `X-Real-IP` overgenomen. **Let op bij wijzigingen:**
zou iemand ooit `trusted_proxy` in waitress zetten, dan komt `X-Forwarded-For`
wél door en wordt `split(",")[0]` in `_bezoeker_ip()` alsnog vervalsbaar. De backslash-fout uit de vorige ronde was op **twee** plekken
hersteld (`_eigen_pad`) maar op twee andere blijven staan (`taal_kies`, de
`volgende` bij het aanmelden); die zijn nu samengevoegd tot één
`_veilig_pad()`. Bij dat samenvoegen kwam een **stuurteken-omweg** boven die
overal in zat: een tab, newline of return in het pad wordt door de browser én
door Werkzeug uit de URL geknipt, waarna `/\t/vreemd` overblijft als
`//vreemd` — gemeten kwam `?terug=/%09/evil` er als `Location: //evil.example`
uit, een echte open-redirect zonder proxy nodig. `_veilig_pad()` weigert nu
elk stuurteken. De query-OOM (één reuzegrote `zeroblob`-rij) is opnieuw
bekeken en als geaccepteerd risico gelaten: het scherm zit achter een
aanmelding.

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
een label in de **weeklijst** toont; daarom staat `label` alleen bij de Oranje
Top 30 gevuld (28.702 van de 28.709 noteringen).

top40.nl heeft het label wél, maar op de **detailpagina** van een nummer, onder
een kopje *Platenlabel*. Alle 79 detailpagina's die tijdens ander werk in de
cache belandden hebben er een. Het overnemen zou dus kunnen, maar het is geen
kleine ingreep: één detailpagina per nummer, en dat zijn er 15.386 voor de Top
40 alleen, 27.450 met de Tipparade en Sterren NL erbij — op een beleefd tempo
van één per seconde ruim zeven uur ophalen. En de waarden vragen dezelfde
opschoning als de titels: `Relax / Telstar / Decca` bij een gedeelde plek,
`Pye / Decca` per land, `Blue Horizon ((1969)) / CBS ((1974))` per hitperiode.
Bij een gedeelde plek zou bovendien uitgezocht moeten worden welk label bij
welke uitvoering hoort. Nog niet gedaan; eerst een proef op één jaargang is de
verstandige volgorde.

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
