# De database

Eén sqlite-bestand, `data/hitlijsten.sqlite`, ongeveer 90 MB, met elf
lijsten erin. Elf tabellen,
waarvan er één de gegevens bevat en tien eromheen staan: wat er is opgehaald,
wat er met de hand is rechtgezet, en wat er nog gebouwd moet worden.

Het schema staat als één string in [`hitlijsten/db.py`](hitlijsten/db.py) en
wordt bij **elke** verbinding uitgevoerd (`CREATE TABLE IF NOT EXISTS`). Een
nieuwe tabel toevoegen is dus een regel in die string; er is geen apart
migratiebestand. Kolommen die later bij een bestaande tabel komen krijgen een
eigen `_voeg_..._toe()`-functie, want `CREATE TABLE IF NOT EXISTS` doet niets
aan een tabel die er al staat.

Erin kijken doe je via de webapplicatie onder **Query**. Die is alleen-lezen:
`INSERT`, `UPDATE`, `DELETE`, `DROP` en `PRAGMA` worden geweigerd — een typefout in een
`UPDATE` zonder `WHERE` is onherstelbaar en daar staat geen enkel gemak
tegenover. Wijzigen gaat via de bewerkschermen, en die leggen alles vast in
`wijzigingen`.

## In één oogopslag

| Tabel | Rijen | Waarvoor |
|---|---|---|
| [`noteringen`](#noteringen) | 540.352 | de gegevens: één rij per nummer per week |
| [`opgehaald`](#opgehaald) | 7.684 | welke week wanneer is binnengehaald |
| [`bestaat_niet`](#bestaat_niet) | 267 | weken die nooit zijn uitgezonden |
| [`aliases`](#aliases) | 651 | twee sleutels die hetzelfde nummer zijn |
| [`niet_samenvoegen`](#niet_samenvoegen) | 4 | het omgekeerde: lijkt hetzelfde, is het niet |
| [`artiestnamen`](#artiestnamen-en-titelnamen) | 1.131 | de vastgestelde schrijfwijze per artiest |
| [`titelnamen`](#artiestnamen-en-titelnamen) | 1.975 | idem per nummer |
| [`onderscheidingen`](#onderscheidingen) | 4.044 | Alarmschijven en Dancesmashes |
| [`correcties`](#correcties) | 0 | jaartotalen van een tweede bron |
| [`te_bouwen`](#te_bouwen) | 0 | welke jaargang opnieuw gebouwd moet |
| [`wijzigingen`](#wijzigingen) | 11.437 | logboek van elke correctie |
| [`taak`](#taak) | 0–1 | de lopende (of laatst gedraaide) achtergrondtaak |
| [`berichten`](#berichten) | groeit | bezoekersberichten voor gastenboek en postbus |
| [`taal`](#taal) | ±7.000 | welke nummers Nederlandstalig zijn, met de bewijsgrond |

Peildatum 3 augustus 2026.

---

## De sleutel

Bijna alles hangt aan één begrip, dus dat eerst.

Een **sleutel** is `artiest|titel`, allebei genormaliseerd: kleine letters, geen
accenten, geen leestekens. `sleutel_van("The Beatles", "Hey Jude")` levert
`beatles|hey jude`. Daarmee wordt een nummer over de weken heen herkend, ook als
de bron zijn schrijfwijze halverwege verandert.

Wat de normalisatie doet, in volgorde:

1. **Typografie gelijktrekken** — de kromme apostrof wordt een rechte, het
   gedachtestreepje een koppelteken.
2. **Bijzondere letters vertalen** — ø→o, æ→ae, ß→ss, ł→l. Zonder deze stap
   overleeft de ø de accentverwijdering en wordt hij daarna als rommel
   geschrapt: "Bløf" werd "bl f" en stond los van "Blof".
3. **Accenten weghalen** — "Beyoncé" wordt "beyonce".
4. **Samenwerkingstekens gelijktrekken** — `feat.`, `ft`, `featuring`, `with`,
   het Nederlandse `met`, `&`, `+`, `x` en `vs` worden allemaal ` & `. **Alleen bij de artiest**: in
   een titel is de x van "Malcolm X" gewoon een letter. Dat `feat.` en `&`
   hetzelfde opleveren is bewust: het gaat om dezelfde twee mensen op dezelfde
   plaat, en anders staan "Calvin Harris feat. Rihanna" en "Calvin Harris &
   Rihanna" als twee artiesten in de database.
5. **Het lidwoord vooraan de artiest weghalen** — `the`, `de`, `het`. De bronnen
   zijn het er niet over eens: top40.nl schrijft "The Beatles", Music Datastats
   schrijft "Beatles". **Alleen bij de artiest**: "The Wall" is niet "Wall".
6. **De rest weggooien** — alles wat geen letter, cijfer, spatie of `&` is.
7. **De alias volgen** — zie [`aliases`](#aliases).

Die laatste stap maakt de sleutel afhankelijk van de database. Verander je een
alias, dan moeten de sleutels opnieuw berekend worden; dat is wat
*Sleutels herberekenen* op de beheerpagina doet.

> **Valkuil.** Het aliasscherm vraagt om `artiest|titel` en dan typ je vanzelf
> over wat er op het scherm staat: `ABBA*Teens|Mamma Mia`. Dat wordt nooit
> gevonden, want de sleutel is `abba teens|mamma mia`. Het veld normaliseert
> daarom zelf en meldt wat het ervan gemaakt heeft.

---

## noteringen

De tabel waar het om gaat. **Eén rij per nummer per week per lijst.**

| Kolom | Type | Betekenis |
|---|---|---|
| `id` | INTEGER | primaire sleutel, een rijteller |
| `lijst` | TEXT | `top40`, `tipparade`, `oranje`, `sterrennl`, `top2000`, `top4000`, `veronica`, `qtop1500`, `evergreen`, `arrow`, `kink` |
| `jaar` | INTEGER | de jaargang |
| `week` | INTEGER | het weeknummer; bij een jaarlijkse lijst altijd `52` |
| `positie` | INTEGER | 1 = hoogste |
| `titel` | TEXT | zoals getoond |
| `artiest` | TEXT | zoals getoond |
| `label` | TEXT | platenlabel; alleen de Oranje Top 30 levert dit (28.583 rijen) |
| `weken_genoteerd` | INTEGER | wat de bron zegt; bij de jaarlijkse lijsten het aantal edities |
| `vorige_positie` | INTEGER | vorige week, of vorige editie; leeg bij een binnenkomer |
| `site_status` | TEXT | `nieuw`, `stijger`, `daler`, `gelijk`, `terug`, `onbekend` |
| `sleutel` | TEXT | zie [De sleutel](#de-sleutel) |
| `uitjaar` | INTEGER | jaar van uitgave; alleen de jaarlijkse lijsten leveren dit |
| `alarmschijf` | INTEGER | het belletje van top40.nl: dit nummer is (ooit) Alarmschijf geweest; per notering zoals de bron het toont |
| `stip` | INTEGER | de stipnotering: 0 geen, 1 stip, 2 superstip. Hoort bij de wéék, niet bij de plaat. Alleen gevuld voor `top40` (39.538) en `sterrennl` (2.901) — elders heeft de markering geen betekenis |
| `kroon` | INTEGER | de Oranje Kroon: clip van de week bij TV Oranje. Als de alarmschijf een eigenschap van de plaat; alleen `oranje` (6.620 noteringen, 685 nummers, vanaf 2012) |

Indexen: `(lijst, jaar, sleutel)`, `(lijst, jaar, week)` en een kale
`(sleutel)` — die laatste draagt de artiestpagina's (alles van één artiest
is een prefix-zoektocht op `artiest|…`).

**Indexen:** `(lijst, jaar, sleutel)` en `(lijst, jaar, week)`.

### Waarom de primaire sleutel een rijteller is

Dit lijkt slordig en is het niet. `(lijst, jaar, week, positie)` zou een nette
sleutel zijn, maar **hitlijsten kennen gedeelde posities**. De Tipparade van
1971 week 12 heeft acht nummers op plek 23 — allemaal een versie van *Love
Story*, dat voorjaar. En sinds de dubbele A-kanten uit elkaar zijn getrokken
staan er ook twee nummers op één plek in de Top 40:

```
1965 wk 18   #9  The Beatles - Eight Days A Week
1965 wk 18   #9  The Beatles - Baby's In Black
```

Uniciteit wordt bewaakt door `bewaar_week()`, dat de week eerst wist en daarna
in één transactie opnieuw schrijft.

### Wat er níét in staat

- **Punten.** Die worden gerekend als `lijstlengte − positie + 1`, waarbij de
  lengte per week uit de gegevens zelf komt (de hoogste positie van die week).
  Opslaan zou betekenen dat je ze na elke alias moet bijwerken.
- **De uitzenddatum.** Die wordt afgeleid: week N is de N-de zaterdag van dat
  jaar, de uitzending was de vrijdag ervoor. Zie `datums.py`.
- **De lijstlengte.** Zie hierboven; de Tipparade wisselde tussen 20 en 30, en
  de Q Top 1500 begon als duizend.

---

## opgehaald

Wat er wanneer is binnengehaald. **Primaire sleutel `(lijst, jaar, week)`.**

| Kolom | Type | Betekenis |
|---|---|---|
| `lijst`, `jaar`, `week` | | welke week |
| `aantal` | INTEGER | hoeveel noteringen die week opleverde |
| `opgehaald_op` | TEXT | tijdstip, ISO met een `T`, **lokale tijd** |

Deze tabel bepaalt wat de wekelijkse run nog moet doen: alles wat in het bereik
van een lijst valt en hier niet in staat (en ook niet in `bestaat_niet`) wordt
opgehaald. Hij bepaalt ook of een Excel- of PDF-bestand verouderd is.

> **Valkuil, en hij is er ingelopen.** `datetime('now')` van sqlite geeft
> **UTC**. De import van de jaarlijkse lijsten deed dat, en dan staat het
> ophaalmoment in de zomer twee uur achter — zichtbaar op het overzicht, en
> `is_actueel` denkt dat een net ingelezen editie al twee uur oud is. Overal in
> deze code hoort `datetime.now().isoformat(timespec="seconds")` te staan. Te
> herkennen aan de vorm: sqlite schrijft `2026-08-02 10:22:24`, Python
> `2026-08-02T12:22:24`.

---

## bestaat_niet

Weken die er nooit zijn geweest. **Primaire sleutel `(lijst, jaar, week)`.**

| Kolom | Type | Betekenis |
|---|---|---|
| `lijst`, `jaar`, `week` | | welke week |
| `reden` | TEXT | waarom, bv. `404 -- deze week bestaat niet op de site` |
| `vastgesteld` | TEXT | wanneer dat is bepaald |

Zonder deze tabel zou elke run opnieuw proberen de kerstweek van 1972 op te
halen. De Top 40 slaat in 19 van de 62 jaargangen de laatste decemberweek over,
en geen enkele lijst heeft een week 53 in 2025.

---

## aliases

Twee sleutels die hetzelfde nummer zijn. **Primaire sleutel `van`.**

| Kolom | Type | Betekenis |
|---|---|---|
| `van` | TEXT | de sleutel die verdwijnt |
| `naar` | TEXT | waar hij op uitkomt |
| `opmerking` | TEXT | waarom |
| `aangemaakt` | TEXT | wanneer |

**Ketens mogen.** `a → b` en `b → c` laat `a`, `b` en `c` allemaal op `c`
uitkomen; `_volg_alias()` loopt de keten door en heeft een beveiliging tegen
cykels (bij `a → b → a` wint de laagste sleutel, zodat iedereen in elk geval op
dezelfde uitkomt).

Waar ze vandaan komen:

- **Bronnen hernoemen een lopende notering** — een dubbele A-kant, een
  gastartiest die erbij komt, een typefout. `python -m hitlijsten controle`
  spoort ze op en beoordeelt zelf of het dezelfde notering is: samen in dezelfde
  week = twee nummers, aansluitend = een hernoeming.
- **Het opschonen** — typefouten in artiestnamen, gesplitste nummers, de
  uitgave die vóór de titel stond.
- **De vastgestelde schrijfwijze** — zie hieronder.

---

## oude_sleutels

Waar een verhuisde sleutel tegenwoordig te vinden is. **Primaire sleutel
`oud`.**

| Kolom | Type | Betekenis |
|---|---|---|
| `oud` | TEXT | de sleutel zoals hij in oude webadressen staat |
| `nieuw` | TEXT | waar hij nu heet |
| `reden` | TEXT | waarom hij verhuisde |
| `aangemaakt` | TEXT | wanneer |

**Waarom apart van `aliases`.** Die tabel bevat gecureerde beslissingen ("dit
is dezelfde plaat", nagekeken tegen MusicBrainz), telt mee bij het *berekenen*
van sleutels en wordt elke run naar CSV geëxporteerd. Deze tabel is puur
routering: mechanisch gevuld, bij duizenden tegelijk, en zonder enige invloed
op wat een sleutel wordt. Ze door elkaar halen zou de curatie onleesbaar maken
en — erger — een verhuisbericht laten meetellen bij het samenvoegen van
platen.

**Waar hij voor is.** De sleutel staat in de URL van een nummerpagina, dus een
wijziging in de normalisatie breekt webadressen. In augustus 2026 hernoemden
twee ingrepen samen 4.929 sleutels; het splitsen van gedeelde plekken
liet er daarna nog 34 verdwijnen. De tabel telt nu 4.963 regels. `/nummer/<sleutel>` en
`/artiest/<sleutel>` verwijzen bij een onbekende sleutel door met een **301**,
na controle dat het doel bestaat; ketens worden doorgevolgd.

`hersleutel` vult de tabel voortaan zelf bij elke sleutel die hij wijzigt.

---

## niet_samenvoegen

Het omgekeerde. **Primaire sleutel `(sleutel_a, sleutel_b)`.**

| Kolom | Type | Betekenis |
|---|---|---|
| `sleutel_a`, `sleutel_b` | TEXT | het paar |
| `reden` | TEXT | waarom het twee nummers zijn |
| `aangemaakt` | TEXT | wanneer |

Zonder deze tabel stelt `controle` dezelfde afgewezen paren elke keer opnieuw
voor — een kerst- of voetbalversie die vlak na het origineel verscheen en dus
binnen de weekgrens valt, maar toch een eigen nummer is.

---

## artiestnamen en titelnamen

Dezelfde opzet, de een per artiest en de ander per nummer. **Primaire sleutel
`sleutel`** — bij `artiestnamen` alleen het deel vóór de streep, bij
`titelnamen` de hele sleutel.

| Kolom | Type | Betekenis |
|---|---|---|
| `sleutel` | TEXT | artiestsleutel, of de volledige sleutel |
| `naam` | TEXT | zo hoort het te staan |
| `bron` | TEXT | `meerderheid`, `musicbrainz`, `spatiëring`, `hand`, `sleutel volgt de naam` |
| `aangemaakt` | TEXT | wanneer |

Nodig omdat de bronnen het oneens zijn: "Beatles" tegen "The Beatles",
"coldplay" tegen "Coldplay". Zonder deze tabel zou de vrijdagrun zo'n correctie
de week erop weer ongedaan maken, want de bron blijft schrijven wat hij schrijft.

Hoe de juiste schrijfwijze wordt gekozen, in volgorde van gewicht:

1. **Een bijzondere letter wint altijd.** Niemand typt per ongeluk "Buisonjé";
   wél laat de ene bron na de andere het streepje weg. Van "Xander De Buisonje"
   (25 keer) en "Xander De Buisonjé" (5 keer) is de zeldzame dus de goede.
2. **Bij een titel telt een apostrof mee**, bij een artiestnaam niet. "Dont
   Speak" verliest van "Don't Speak", maar Shakespears Sister en Dexys Midnight
   Runners schrijven zich er echt zonder.
3. **Alles in kleine letters verliest** van iets met hoofdletters.
4. **Daarna telt het aantal.** Over "Rob de Nijs" tegen "Rob De Nijs" valt te
   twisten, en dan is de gewoonte van de bronnen zo goed als elk ander oordeel.

> **Valkuil.** De sleutel wordt uit de naam berekend, en deze tabel verandert
> die naam. "ACDC" werd "AC/DC", en daaruit volgt de sleutel `ac dc` en niet
> `acdc` — dus de eerstvolgende herberekening trok de zojuist samengevoegde
> artiest weer uit elkaar. `verzeker_aliassen()` legt daarom een alias van de
> oude sleutel naar die van de vastgestelde naam. **De sleutel volgt de naam**,
> niet andersom: de omgekeerde richting lijkt ook te werken tot er een
> verouderde naamregel blijkt te staan.

---

## onderscheidingen

Alarmschijven en Dancesmashes, van michajans.nl.

| Kolom | Type | Betekenis |
|---|---|---|
| `id` | INTEGER | rijteller |
| `soort` | TEXT | `alarmschijf` (2.878) of `dancesmash` (1.166) |
| `datum` | TEXT | de datum van toekenning |
| `jaar` | INTEGER | het jaar daarvan |
| `naam` | TEXT | zoals de bron het schrijft |
| `sleutel` | TEXT | gekoppeld aan een notering, of leeg als dat niet lukte |
| `volgnr` | INTEGER | het nummer dat de bron eraan geeft |

**Index** op `sleutel`. Verschijnt als kolom in de Totaal-tab van de
Excel-werkboeken.

---

## correcties

Nu leeg, maar met een reden aanwezig: jaartotalen van een **tweede bron**
(michajans.nl) die van de onze afwijken en waarvan is vastgesteld dat die van
hen klopt.

| Kolom | Type | Betekenis |
|---|---|---|
| `id` | INTEGER | rijteller |
| `jaar`, `lijst` | | welke jaargang |
| `sleutel` | TEXT | welk nummer |
| `punten`, `hoogste`, `weken` | INTEGER | de aangehouden cijfers |
| `bron` | TEXT | waar ze vandaan komen |
| `naam` | TEXT | hoe die bron het nummer noemt |

Wordt gevuld door `python -m hitlijsten kruiscontrole`. `totalen_over()` rekent
de punten daarom per jaargang en telt die op, in plaats van in één keer over de
hele periode — anders zou de totaallijst niet meer gelijk zijn aan de som van de
jaaroverzichten.

---

## te_bouwen

Welke jaargang opnieuw gebouwd moet worden. **Primaire sleutel `(lijst, jaar)`.**

| Kolom | Type | Betekenis |
|---|---|---|
| `lijst`, `jaar` | | welke jaargang |
| `reden` | TEXT | wat hem aanraakte, bv. `artiestnaam` |
| `aangemaakt` | TEXT | wanneer |

Elke plek die een notering wijzigt schrijft hierin. Zonder deze tabel is
"verouderd" niet per jaargang te bepalen en maakt één alias alle 883 bestanden
verdacht — een half uur bouwen voor drie jaargangen werk. De rij wordt geleegd
zodra het bestand er staat.

---

## wijzigingen

Het logboek. Elke correctie staat erin, met wat er stond en wat er nu staat.

| Kolom | Type | Betekenis |
|---|---|---|
| `id` | INTEGER | rijteller |
| `tijdstip` | TEXT | ISO met een `T`, lokale tijd |
| `soort` | TEXT | `tekst`, `artiestnaam`, `titelnaam`, `dubbele a-kant`, `versies`, `correctie`, `titel`, `artiest`, `uitjaar`, `sleutel`, `alias` |
| `verwijst` | TEXT | welke rij of sleutel |
| `veld` | TEXT | welke kolom |
| `oud`, `nieuw` | TEXT | de waarden |
| `reden` | TEXT | waarom |

Zonder dit logboek is een correctie niet te onderscheiden van wat de bron zelf
leverde, en dat is precies wat je later wilt kunnen nazoeken.

> **Het is een logboek en geen terugdraaiknop.** Bij een samenvoeging van
> duizenden noteringen staat er één regel met een samenvatting; daar bouw je de
> oude toestand niet uit terug. Daarvoor zijn de
> [momentopnames](LEESMIJ.md#terug-kunnen): een gzip-kopie van het hele bestand,
> automatisch vóór elke run en vóór elk opschonen, met één knop terug te zetten.

---

## berichten

Wat bezoekers achterlaten via het formulier. Alles komt binnen met status
`nieuw`; de beheerder publiceert (→ `gepubliceerd`, zichtbaar in het
gastenboek), houdt privé (→ `prive`) of verwijdert (spam laat geen rij achter).

| Kolom | Type | Betekenis |
|---|---|---|
| `id` | INTEGER | rijteller |
| `tijdstip` | TEXT | lokale tijd, ISO |
| `soort` | TEXT | `opmerking`, `tip`, `bug` of `aanvulling` |
| `naam` | TEXT | zoals opgegeven; leeg = "Een bezoeker" |
| `email` | TEXT | alleen voor antwoord; komt nooit op de site |
| `tekst` | TEXT | het bericht, maximaal 5.000 tekens |
| `pagina` | TEXT | waar de melder stond ("gaat over") |
| `mag_openbaar` | INTEGER | het vinkje "mag in het gastenboek" |
| `status` | TEXT | `nieuw`, `gepubliceerd` of `prive` |
| `antwoord` | TEXT | korte reactie van de beheerder, onder het bericht |
| `ip` | TEXT | voor de limiet van vijf berichten per adres per dag |

## taal

Welke nummers Nederlandstalig zijn. Gevuld door `taal.herken_alles()` in drie
trappen: `lijst` (stond in de Oranje Top 30 of Sterren NL Top 25 — hard
bewijs), `artiest` (artiest met vrijwel alleen Nederlandstalig werk),
`titel` (overtuigend Nederlandse woorden/patronen in de titel). `hand` is
een handmatige beslissing via de nummerpagina en wint altijd; de rest wordt
bij elke run opnieuw bepaald. De vrijdagrun draait de herkenning mee.

| Kolom | Type | Betekenis |
|---|---|---|
| `sleutel` | TEXT | het nummer |
| `nederlandstalig` | INTEGER | 1 of (alleen bij `hand`) 0 |
| `bron` | TEXT | `lijst`, `artiest`, `titel` of `hand` |
| `aangemaakt` | TEXT | lokale tijd, ISO |

## taak

De lopende — of laatst gedraaide — achtergrondtaak. **Eén rij, `id` is altijd 1.**

| Kolom | Type | Betekenis |
|---|---|---|
| `naam`, `gestart`, `bijgewerkt` | TEXT | wat er draait en sinds wanneer |
| `proces` | INTEGER | het procesnummer, om te zien of hij nog leeft |
| `klaar`, `gelukt` | INTEGER | de uitkomst |
| `fout` | TEXT | de foutmelding, als die er is |
| `regels` | TEXT | de laatste meldingen, één per regel |
| `stap`, `stappen`, `stap_naam` | | waar hij is ("stap 3 van 5: Excel bouwen") |
| `deel`, `deel_van` | INTEGER | de plek binnen die stap ("jaargang 40 van 62") |

Stond eerst in het geheugen van de webapplicatie, en dat gaf twee keer een
verkeerd beeld: na een herstart was de voortgang weg, en werk vanaf de
opdrachtregel was onzichtbaar. Nu ziet elk proces dezelfde stand, tekent de
beheerpagina er voortgangsbalken van, en blijkt uit het procesnummer of een
taak die op "bezig" staat echt nog leeft — zo niet, dan meldt de pagina dat hij
is afgebroken. Een voorbije taak verdwijnt na een kwartier, of eerder met de
knop *Melding opruimen*.

---

## Gelijktijdig gebruik

De database staat in **WAL-modus** met een **wachttijd van dertig seconden**.
Dat is geen voorkeur maar een reparatie.

In de standaardmodus (`delete`) blokkeert een lezer een schrijver. De
webapplicatie voerde bovendien bij *elk* paginaverzoek het schema opnieuw uit —
`CREATE TABLE IF NOT EXISTS` doet niets, maar het is wél een schrijfactie. Wie
door de zoekresultaten klikte terwijl er een achtergrondtaak liep, legde die
taak dus stil: na vijf seconden wachten geeft sqlite het op met
`database is locked`, en dan valt hij om halverwege het bijwerken van de
sleutels.

Drie dingen veranderd:

- **WAL** — lezers en schrijvers gaan langs elkaar heen. Staat in het bestand
  zelf, dus eenmalig, maar `db._stel_in()` zet hem bij elke verbinding zodat een
  verse database het meteen goed heeft.
- **`busy_timeout=30000`** — dertig seconden wachten in plaats van vijf.
- **Het schema draait nog één keer per proces**, niet per verzoek.

`synchronous=NORMAL` hoort bij WAL: bij een stroomstoring kan de laatste
transactie verloren gaan, maar de database raakt niet beschadigd. Voor een
hitlijstenarchief is dat de goede afweging — en er staat een momentopname naast.

Naast `hitlijsten.sqlite` staan nu `-wal` en `-shm`. Die horen erbij; een kopie
maak je met `VACUUM INTO` (wat `momentopnames.py` doet) en niet met `cp`.

## Conventies

**Tijdstempels** zijn ISO-8601 met een `T` en in **lokale tijd**
(`datetime.now().isoformat(timespec="seconds")`). Niet `datetime('now')` van
sqlite — dat is UTC.

**`NOT NULL` betekent hier "de bron levert dit altijd"**, niet "dit is
verplicht". `label`, `weken_genoteerd`, `vorige_positie` en `uitjaar` mogen leeg
zijn omdat niet elke bron ze geeft.

**Er staan geen vreemde sleutels in.** Sqlite dwingt ze standaard niet af en de
tabellen worden altijd via de code gevuld; een `REFERENCES` zou een belofte zijn
die niemand controleert. De samenhang zit in `sleutel` en in `(lijst, jaar,
week)`, en die worden bewaakt door de controles (`python -m hitlijsten controle`
en `kruiscontrole`).

**Alles wat afgeleid kan worden staat er niet in**: punten, uitzenddatums,
lijstlengtes, decennium- en totaallijsten. Dat scheelt niet alleen ruimte maar
vooral onderhoud — een alias verschuift punten, en dan hoeft er niets
bijgewerkt te worden wat had kunnen verouderen.
