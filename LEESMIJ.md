# Hitlijsten verzamelen

Haalt elke week de vier hitlijsten op, schrijft ze naar Excel en mailt wat er
nieuw binnenkwam.

| Lijst | Bron | Lengte | Archief vanaf |
|---|---|---|---|
| Nederlandse Top 40 | top40.nl/top40 | 40 | 1965 |
| Tipparade | top40.nl/tipparade | 30 | 1967 (± week 28) |
| Sterren NL Top 25 | top40.nl/sterren-nl-top25 | 25 | 2019 (week 40) |
| Oranje Top 30 | oranjetop30.nl | 30 | 2008 |

De archiefdieptes zijn gemeten, niet aangenomen — zie *Oude jaargangen ophalen*.

## Stand van zaken

- **2026** t/m week 31 en **heel 2025** staan in de database, plus 75 noteringen
  uit een testrestje van Sterren NL 2019 (week 40–42).
- De wekelijkse taak **"Hitlijsten verzamelen"** draait elke vrijdag om 09:00 en
  heeft op 31 juli 2026 zijn eerste echte run gedaan: Tipparade week 31
  opgehaald, bestanden herbouwd, mail verstuurd.
- Van de oudere jaargangen is verder nog niets opgehaald;
  `python -m hitlijsten historie` haalt de rest.

## Wat er uitkomt

Een map per decennium, daarin een map per jaargang, daarin per lijst twee
bestanden:

```
H:\HitLijsten_Verzamelen\
  2000-2009\
    2000\ ... 2009\
  2010-2019\
    2010\ ... 2019\
  2020-2029\
    2025\
    2026\
      Top40_2026.xlsx          Top40_Jaar_2026.xlsx
      Tipparade_2026.xlsx      Tipparade_Jaar_2026.xlsx
      SterrenNL_2026.xlsx      SterrenNL_Jaar_2026.xlsx
      OranjeTop30_2026.xlsx    OranjeTop30_Jaar_2026.xlsx
```

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

De **⤓ Excel**-knop naast de dropdown levert `Top40_Decennium_1970-1979.xlsx`:
één tab met hetzelfde klassement. Dat werkboek wordt bij het downloaden ter
plekke gemaakt en komt dus niet uit de wekelijkse run — het kost een fractie van
een seconde en kan zo nooit achterlopen op de database. Wil je ze wél op schijf,
in de decenniummappen naast de jaarmappen:

```bash
python -m hitlijsten.cli decennium                  # alle decennia
python -m hitlijsten.cli decennium --decennium 1970 # alleen de jaren zeventig
```

## Gebruik

```bash
python -m hitlijsten run
```

Dat is wat de wekelijkse taak doet: ontbrekende weken ophalen, Excel herbouwen,
mailen. Losse opdrachten:

| Opdracht | Wat het doet |
|---|---|
| `python -m hitlijsten bijwerken` | alleen wat nog ontbreekt ophalen |
| `python -m hitlijsten backfill` | alle weken van het lopende jaar |
| `python -m hitlijsten historie` | complete oude jaargangen uit het archief |
| `python -m hitlijsten excel` | Excel opnieuw bouwen uit de database |
| `python -m hitlijsten decennium` | decenniumklassementen van de Top 40 naar de decenniummappen |
| `python -m hitlijsten controle` | verdachte dubbelingen, met oordeel per paar |
| `python -m hitlijsten kruiscontrole --alle` | onze Top 40 vergelijken met michajans.nl |
| `python -m hitlijsten onderscheidingen` | Alarmschijven en Dancesmashes ophalen |
| `python -m hitlijsten hersleutel` | sleutels herberekenen na aliases.csv |
| `python -m hitlijsten testmail` | proefmail versturen |
| `python -m hitlijsten run --geen-mail` | run zonder mail, uitvoer op scherm |

`--jaar 2025` mag vóór of ná de opdracht — beide werken.

### De wekelijkse taak

Taakplanner-taak **"Hitlijsten verzamelen"**, vrijdag 09:00, aangemaakt met
`installeer-taak.ps1` (`-Verwijder` haalt hem weg, `-Tijd 20:00` verzet hem).

Stond de pc vrijdag uit, dan draait de taak zodra hij weer aan gaat — niet pas
de week erna. En de run haalt **elke** ontbrekende week op, niet alleen de
nieuwste, dus een paar gemiste weken halen zichzelf in. Dat geldt ook over de
jaarwisseling heen: is de vorige jaargang afgekapt, dan wordt de staart alsnog
aangevuld.

Alleen de staart, niet elk gat — een jaargang die pas halverwege begon (Sterren
NL start in 2019 bij week 40) heeft aan het begin gaten die nooit bestaan hebben.
Die elke week opnieuw proberen zou de mail voorgoed vervuilen.

Heeft de pc echt lang stilgestaan, gebruik dan `historie --vanaf <jaar>`.

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
hitlijsten/
  config.py     de vier lijsten, paden, URL-opbouw, lengte per jaargang
  fetch.py      HTML ophalen + schijfcache (.cache/), week- en jaarcontrole
  parsers/      HTML -> Notering  (top40nl.py, oranje.py)
  models.py     dataclass Notering + structuurcontrole
  normalize.py  nummers over weken heen herkennen
  db.py         sqlite-opslag (data/hitlijsten.sqlite), incl. bestaat_niet
aliases.csv           samen te voegen sleutels
niet-samenvoegen.csv  paren die juist gescheiden moeten blijven
te-beoordelen.csv     voorstellen uit `controle --alle`
  excel.py      de Excel-bestanden
  mail.py       melding via de MailPlus-relay
  cli.py        de opdrachten hierboven
tests/          zelftests, draaien op de cache dus zonder netwerk
```

**De database is de bron, niet de website.** Alles wat opgehaald is staat in
`data/hitlijsten.sqlite` en de ruwe HTML in `.cache/`. De Excel-bestanden opnieuw
bouwen kost dus geen enkel verzoek aan de sites, en je kunt ze zonder risico
weggooien en opnieuw laten maken.

### Testen

```bash
python tests\test_top40nl.py
python tests\test_oranje.py
python tests\test_excel.py
python tests\test_datums.py
python tests\test_decennium.py
node tests\test_grafiek.mjs
```

Draaien op de gecachete pagina's en een tijdelijke database, dus zonder netwerk
en zonder de echte data aan te raken. Handig na elke wijziging aan een parser of
aan `excel.py`.

`test_grafiek.mjs` is de vreemde eend: die knipt het grafiekscript uit
`templates/jaar.html` en draait het in node tegen een kleine DOM-stub. Dat is
geen browser en zegt dus **niets over de opmaak** — wel over de schaal, de
verschillen per week, de gaten en de streep bij de jaarwisseling. Het script
wordt uit de template geknipt in plaats van gekopieerd, zodat de test niet
stilletjes een oude versie blijft goedkeuren.

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
valt, maar toch een eigen nummer is — zet het dan in **`niet-samenvoegen.csv`**
als `sleutel_a;sleutel_b`. `controle` slaat die paren daarna over.

De grens van drie weken (`cli.MAX_GAT_WEKEN`) scheidt een hernoeming van een
heruitgave. Danzel's "Pump It Up" noteerde in 2004 van week 13 tot 18 en de remix
pas vanaf week 43 — 24 weken later, dus een eigen notering. Een typefout of een
toegevoegde gastartiest valt daarentegen altijd binnen een paar weken.

Samenvoegen doe je zelf, in **`aliases.csv`**: `van_sleutel;naar_sleutel`. De
sleutel staat als kolom in de Excel-bestanden. Ketens mogen: `a;b` plus `b;c`
laat a, b en c allemaal op c uitkomen.

### te-beoordelen.csv

```bash
python -m hitlijsten controle --alle
```

loopt alle jaargangen na en schrijft de gevallen die het script níét zelf durft
te beslissen naar **`te-beoordelen.csv`**, als kant-en-klare aliasregels met een
`#` ervoor. Wil je er een samenvoegen, haal het `#` weg en plak de regel in
`aliases.csv`.

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

## Als er iets misgaat

**Wijzigt een site zijn opmaak**, dan faalt de structuurcontrole (verwacht
40/30/25 aaneengesloten posities) en komt dat in de mail terecht: in de
onderwerpregel staat `-- N MISLUKT` en bovenaan het bericht welke weken het
betreft. Dat is met opzet — de taak draait zonder venster, dus een stille
mislukking zou maanden onopgemerkt kunnen blijven. Een lege tab wegschrijven is
erger dan een luide fout.

Een mislukte week wordt ook **uit de cache gegooid**, zodat de volgende run hem
gewoon opnieuw probeert. Anders zou één onderhoudspagina zich permanent
vastzetten. Blijft dezelfde week falen, dan is het geen toeval en moet de parser
aangepast worden.

Alle details staan in **`run.log`** naast dit bestand. Dat groeit langzaam en
wordt niet automatisch opgeschoond.

## Eigenaardigheden van de bronnen

**top40.nl heeft een kapotte certificaatketen.** De site stuurt het verkeerde
Sectigo-tussencertificaat mee. Browsers repareren dat zelf door het ontbrekende
certificaat op te halen; Python doet dat niet en faalt met
`CERTIFICATE_VERIFY_FAILED`. `certifi` lost het nooit op, hoe je het ook
instelt. `fetch.py` gebruikt daarom `truststore`, dat Python de
Windows-certificaatstore laat gebruiken — daar zit het ontbrekende certificaat
wel in, en certificaatcontrole blijft gewoon aan. Dit is een probleem van
top40.nl, niet van deze pc; oranjetop30.nl heeft het niet.

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

**Debuggen op deze pc:** de Windows-console is cp1252 en verminkt tekens als `ø`
en `ë`, wat er precies uitziet als een coderingsfout in de data. Dat is het niet
— de cache is correct UTF-8. Zet `PYTHONIOENCODING=utf-8` bij eigen scriptjes.

## Mail

De melding gaat naar `heye@hhaken.nl` via de MailPlus-relay op 10.10.8.20, zonder
wachtwoord — die relay accepteert post vanaf het thuisnetwerk. Wil je dat
dichtzetten, vul dan `mail.ini` in naast dit bestand:

```ini
[mail]
host = 10.10.8.20
poort = 587
starttls = ja
gebruiker = info@songhook.nl
wachtwoord = ...
ontvanger = heye@hhaken.nl
```
