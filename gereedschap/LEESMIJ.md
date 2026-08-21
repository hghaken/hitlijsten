# Gereedschap

Losse scripts voor het opschonen van credits en titels. Ze draaien op de NAS,
tegen de echte database, en doen **niets** zonder `--doen` — zonder die vlag
laten ze alleen zien wat er zou gebeuren. Elk script maakt vooraf een
momentopname, dus alles is terug te draaien met `momentopnames.terugzetten()`.

    cd /volume1/Hitlijsten/app && . ./omgeving.sh
    PYTHONPATH=/volume1/Hitlijsten/app ./venv/bin/python gereedschap/<script> ...

Die `omgeving.sh` is niet optioneel: zonder de omgevingsvariabelen legt
`config.py` een verse, lege database aan in `app/data`.

| script | waarvoor |
|---|---|
| `hernoem.py "oud" "nieuw"` | een credit hernoemen, sleutel en doorverwijzing incluis; voegt samen als de nieuwe sleutel al bestaat |
| `titel.py "artiest" "oude titel" "nieuwe titel"` | een titel binnen één artiest hernoemen, met alias |
| `credit-per-titel.py "oude artiest" "titel" "nieuwe artiest"` | de artiest van één nummer omzetten in plaats van de hele credit |
| `titelvorm.py` | records waarvan de bronnen de titel anders spellen op de weeklijstvorm zetten |
| `kapitaal.py` | elk woord in artiest en titel een hoofdletter geven |

## Wat `kapitaal.py` bewust niet doet

De regel is eenzijdig: een kleine letter mag naar een hoofdletter, nooit
andersom. Een woord dat al érgens een hoofdletter heeft blijft ongemoeid, en
daarmee blijven `ABBA`, `E.L.O.`, `D.R.O.P.`, `McCloud`, `AC/DC`, `VOF` en de
landcodes `(NLD)` / `(BEL)` / `(DEU)` staan zoals ze staan. Er wordt alleen
gekapitaliseerd ná een spatie, haakje, koppelteken of schuine streep — anders
wordt `P!nk` `P!Nk` en `$hirak` `$Hirak`. Een woord dat op een apostrof volgt
blijft klein (`'k Heb Je Lief`), en `o.l.v.` blijft `o.l.v.`.

Draai hem via de koppeltabel-versie: per naam een `UPDATE` betekent per naam
een scan over 568.000 regels, en dat is het verschil tussen negen seconden en
een paar uur.
