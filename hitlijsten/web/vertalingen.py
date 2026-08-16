"""De Engelse vertaling van de site-teksten (fase 1).

Nederlands is de moedertaal van de site; dit woordenboek vertaalt de vaste
teksten van de menubalk, de lijstpagina's en de DJ Export-pagina. De
sleutel is de Nederlandse tekst zoals hij in het sjabloon staat, dus een
ontbrekende vertaling valt vanzelf terug op het Nederlands in plaats van
op een kale sleutelnaam.

Lange lappen proza (uitlegparagrafen) staan niet hier maar als
taal-conditie in het sjabloon zelf: een woordenboeksleutel van vier
regels is onleesbaar en onvindbaar.
"""

EN = {
    # -- menubalk en voetregel ---------------------------------------------
    "Overzicht": "Overview",
    "Weeklijsten": "Weekly charts",
    "Jaaroverzichten": "Year charts",
    "Decennia": "Decades",
    "Top 40 totaal": "Top 40 all-time",
    "Jaarlijsten totaal": "Annual all-time",
    "Zoeken": "Search",
    "Jouw dag": "Your day",
    "Weekbericht": "Week report",
    "Wetenswaardigheden": "Fun facts",
    "Records": "Records",
    "Versies": "Versions",
    "Vergelijk": "Compare",
    "Gastenboek": "Guestbook",
    "Handleiding": "Manual",
    "Disclaimer": "Disclaimer",
    "Aanmelden": "Sign in",
    "Afmelden": "Sign out",
    "Verras me: een willekeurig nummer": "Surprise me: a random song",
    "De gebruiksaanwijzing voor bezoekers, als PDF":
        "The visitor manual, as a PDF",

    # -- gedeelde knoppen, filters en meldingen ----------------------------
    "vorige": "previous",
    "volgende": "next",
    "Toon": "Show",
    "alle": "all",
    "traag": "slow",
    "nieuw": "new",
    "terug": "back",
    "terug sinds": "back since",
    "week": "week",
    "per week…": "by week…",
    "Alleen Nederlandstalige nummers tonen": "Only Dutch-language songs",
    "Alleen de nummers die in dit jaar voor het eerst in deze lijst "
    "verschenen": "Only songs that entered this chart for the first time "
                  "this year",
    "Alleen de binnenkomers van deze week": "Only this week's new entries",
    "Deze week staat niet in de database.":
        "This week is not in the database.",
    "Voor deze lijst staat er nog niets in de database.":
        "Nothing in the database for this chart yet.",
    "Voor deze editie staat er nog niets in de database.":
        "Nothing in the database for this edition yet.",
    "Voor dit decennium staat er nog niets in de database.":
        "Nothing in the database for this decade yet.",
    "Er staat nog niets in de database.": "Nothing in the database yet.",
    "uitgezonden op vrijdag": "aired on Friday",
    "noteringen": "entries",
    "jaargangen beschikbaar": "years available",
    "edities beschikbaar": "editions available",
    "gegevens via": "data via",
    "Naar": "Go to",
    "opgehaald": "fetched",
    "Klik voor de grafiek": "Click for the chart run",
    "Klik voor het verloop": "Click for the chart run",

    # -- tabelkoppen --------------------------------------------------------
    "Positie": "Position",
    "Vorige": "Previous",
    "Artiest": "Artist",
    "Titel": "Title",
    "Label": "Label",
    "Weken": "Weeks",
    "Punten": "Points",
    "Hoogste": "Peak",
    "Binnenkomst": "First entry",
    "Laatste notering": "Last entry",
    "Jaargangen": "Years",
    "Edities": "Editions",
    "Lijsten": "Charts",
    "Uit": "From",
    "Vorige editie": "Previous edition",
    "Verschil": "Change",
    "Zender": "Station",
    "Lijst": "Chart",
    "Van": "From",
    "Tot": "To",
    "Per editie": "Per edition",
    "Noteringen": "Entries",
    "Jaar": "Year",
    "Week": "Week",
    "Wanneer": "When",
    "Artiest — titel": "Artist — title",
    "Status": "Status",
    "Bestand": "File",
    "ontbreekt": "missing",

    # -- kaartjes -----------------------------------------------------------
    "unieke nummers": "unique songs",
    "weken": "weeks",
    "nummer 1-noteringen": "number 1 entries",
    "nummers op 1 geweest": "songs that reached number 1",
    "koploper van": "front runner of",
    "koploper van de": "front runner of the",
    "koploper aller tijden": "all-time front runner",
    "langst genoteerd": "longest charting",
    "elk jaar genoteerd": "charted every year",
    "nieuw + terug": "new + returning",
    "nummer 1 van": "number 1 of",
    "edities in de database": "editions in the database",
    "jaarlijkse lijsten": "annual charts",
    "Jaarlijkse lijsten": "Annual charts",
    "hoogste score": "highest score",
    "punten over": "points across",
    "JAAR GELEDEN OP 1": "YEARS AGO AT NUMBER 1",
    "EN OP JOUW DAG?": "AND ON YOUR DAY?",
    "kies een datum ›": "pick a date ›",
    "je geboortedag, je trouwdag…": "your birthday, your wedding day…",
    "uit": "from",
    "Puntenklassement": "Points ranking",
    "Kies een lijst en een jaargang.": "Pick a chart and a year.",
    "Kies een lijst en een editie.": "Pick a chart and an edition.",
    "jaarmatrix": "year matrix",
    "editiematrix": "edition matrix",
    "hoogste": "peak",
    "jaargangen": "years",
    "edities": "editions",
    "Klik op een artiest of titel voor de grafiek van de positie per "
    "week.": "Click an artist or title for the week-by-week graph.",
    "De editie van": "The edition of",
    "Positie per editie": "Position per edition",
    "Laatst opgehaald": "Last fetched",
    "Er loopt iets": "Something is running",
    "handmatige wijzigingen": "manual corrections",
    "aliassen": "aliases",
    "uitzonderingen": "exceptions",

    # -- downloadknoppen ----------------------------------------------------
    "De getoonde selectie als werkboek": "The shown selection as a workbook",
    "De getoonde selectie als klassement-werkboek":
        "The shown selection as a ranking workbook",
    "Werkboek met een tab per week en het puntenklassement":
        "Workbook with a tab per week and the points ranking",
    "Werkboek met de complete editie en de kerngetallen":
        "Workbook with the complete edition and the key figures",
    "Werkboek met de matrix nummer x week, altijd de volledige jaargang":
        "Workbook with the song-by-week matrix, always the full year",
    "Werkboek met de matrix nummer x editie, altijd de volledige editie":
        "Workbook with the song-by-edition matrix, always complete",
    "De getoonde selectie als PDF": "The shown selection as a PDF",
    "Het puntenklassement als PDF, veertig regels per pagina":
        "The points ranking as a PDF, forty rows per page",
    "De complete editie als PDF, veertig regels per pagina":
        "The complete edition as a PDF, forty rows per page",
    "Deze weeklijst als werkboek": "This weekly chart as a workbook",
    "Deze weeklijst als PDF": "This weekly chart as a PDF",
    "De getoonde selectie als VirtualDJ-playlist uit je eigen bibliotheek":
        "The shown selection as a playlist from your own library",
    "Deze weeklijst als VirtualDJ-playlist uit je eigen bibliotheek "
    "(laad eerst je database op de VirtualDJ-pagina)":
        "This weekly chart as a playlist from your own library "
        "(load your database on the DJ Export page first)",

    # -- DJ Export ----------------------------------------------------------
    "bron": "source",
    "nummers geladen": "songs loaded",
    "lokaal": "local",
    "streaming (netsearch)": "streaming (netsearch)",
    "bestandssoort": "file type",
    "matching-strengheid": "matching strictness",
    "alleen audio": "audio only",
    "alleen video": "video only",
    "audio én video": "audio and video",
    "zeer strak": "very strict",
    "strak": "strict",
    "soepel": "loose",
    "zeer soepel": "very loose",
    "aan": "on",
    "uit": "off",
    "Een andere database laden": "Load another database",
    "Je muziek database": "Your music database",
    "Selecteer file": "Select file",
    "nog niets gekozen": "nothing chosen yet",
    "Laad de database": "Load the database",
    "versturen": "sending",
    "bezig met verwerken op de server…": "processing on the server…",
    "Versturen mislukt. Probeer het opnieuw.":
        "Sending failed. Please try again.",
    "vergeet mijn database": "forget my database",
    "Haalt je database uit het geheugen":
        "Removes your database from memory",
    "Je playlist staat klaar": "Your playlist is ready",
    "Gematcht tegen je geladen bibliotheek.":
        "Matched against your loaded library.",
    "terug naar de lijst": "back to the chart",
    "gevonden in je bibliotheek": "found in your library",
    "ontbreekt (je boodschappenlijst)": "missing (your shopping list)",
    "twijfelgevallen (zeer soepel gematcht)":
        "doubtful (very loosely matched)",
    "nummers in je bibliotheek": "songs in your library",
    "van": "of",
    "Het rapport": "The report",

    # -- records en wetenswaardigheden (titels uit Python) ------------------
    "Meeste weken genoteerd": "Most weeks on chart",
    "Eén nummer, één lijst, alle jaargangen bij elkaar.":
        "One song, one chart, all years combined.",
    "Meeste weken op nummer 1": "Most weeks at number 1",
    "Alleen de Nederlandse Top 40.": "Dutch Top 40 only.",
    "Grootste sprong omhoog": "Biggest jump up",
    "Van de ene week op de andere, binnen de Nederlandse Top 40.":
        "From one week to the next, within the Dutch Top 40.",
    "Diepste val": "Deepest fall",
    "Wat er nog nét in bleef; uitvallers tellen niet mee.":
        "Songs that just stayed in; drop-outs don't count.",
    "Langste terugkeer": "Longest re-entry gap",
    "Uit de lijst verdwenen en jaren later alsnog terug.":
        "Dropped out and returned years later.",
    "Eenhitwonders op nummer 1": "One-hit wonders at number 1",
    "Eén hit in de Top 40 — maar die stond wel op 1.":
        "One hit in the Top 40 — but it did reach number 1.",
    "Langste carrière in de weeklijsten":
        "Longest career in the weekly charts",
    "Eerste tot laatste notering, alle weeklijsten.":
        "First to last entry, all weekly charts.",
    "Meeste hits": "Most hits",
    "Aantal verschillende nummers in de weeklijsten.":
        "Number of different songs in the weekly charts.",
    "In de meeste jaaredities": "In the most annual editions",
    "Over alle zeventien jaarlijkse lijsten bij elkaar.":
        "Across all seventeen annual charts combined.",
    "Weken op 1": "Weeks at 1",
    "Weg en terug": "Away and back",
    "De ene hit": "The one hit",
    "Spanne": "Span",
    "Nummers": "Songs",
    "Periode": "Period",
    "Meeste weken in de lijst": "Most weeks in the chart",
    "Langst genoteerd": "Longest charting",
    "Langst op nummer 1": "Longest at number 1",
    "Grootste sprong in één week": "Biggest jump in one week",
    "Meeste nummer 1-hits": "Most number 1 hits",
    "Nummer 1-hits": "Number 1 hits",
    "Meeste noteringen over alle edities":
        "Most entries across all editions",
    "Vaakst in de lijst": "Most often in the chart",
    "Vaakst op nummer 1": "Most often at number 1",
    "Keer op 1": "Times at 1",
    "Grootste sprong in één jaar": "Biggest jump in one year",
    "Langste afwezigheid": "Longest absence",
    "Meeste edities op nummer 1": "Most editions at number 1",
    "Edities op 1": "Editions at 1",
    "Meeste noteringen": "Most entries",
    "Meeste punten aller tijden": "Most points all-time",
    "Hoogste binnenkomers": "Highest new entries",
    "Langste weg naar de eerste plaats": "Longest road to number 1",
    "Datum": "Date",
    "Editie": "Edition",
    "Binnen op": "Entered at",
    "Nummer": "Song",
    "Verschillende nummers die de eerste plaats haalden — hoe lang ze "
    "daar stonden telt hier niet mee.":
        "Different songs that reached the top spot — how long they "
        "stayed there does not count here.",
    "Hoe vaak een artiest de eerste plaats bezette. Een nummer dat er "
    "twintig jaar op stond telt dus twintig keer.":
        "How often an artist held the top spot. A song that sat there "
        "for twenty years counts twenty times.",
    "Gemeten in weken tussen de laatste notering en de terugkeer.":
        "Measured in weeks between the last entry and the return.",

    # -- specials-chrome ----------------------------------------------------
    "Alle hits van": "All hits by",
    "Alle noteringen en de grafiek": "All entries and the graph",
    "bekijk": "view",
    "of": "or",
    "artiest en titel": "artist and title",
    "alleen artiest": "artist only",
    "alleen titel": "title only",
    "alle lijsten": "all charts",
    "Noteringen zoeken": "Search the entries",
    "resultaten": "results",
    "Uitvoeringen": "Recordings",
    "tegen": "versus",
    "Unieke nummers": "Unique songs",
    "Binnenkomers (eerste jaar ooit)": "New entries (first year ever)",
    "Nummer-1-hits": "Number 1 hits",
    "Nederlandstalig": "Dutch-language",
    "Hoogst genoteerd in": "Highest charting in",
    "In allebei de jaargangen": "In both years",
    "noteringen dat jaar": "entries that year",
    "Toon mijn dag": "Show my day",
    "NUMMER 1 OP": "NUMBER 1 ON",
    "uitgezonden op": "aired on",
    "De top 10 van die week": "That week's top 10",
    "De volledige lijst van die week ›": "The full chart of that week ›",
    "de volledige lijst": "the full chart",
    "Ook deze week": "Also this week",
    "DE NUMMER 1": "THE NUMBER 1",
    "GROOTSTE STIJGER": "BIGGEST CLIMBER",
    "DIEPSTE DALER": "DEEPEST FALLER",
    "weken genoteerd": "weeks on chart",
    "kwam van": "up from",
    "Binnenkomers": "New entries",
    "Terug van weggeweest": "Back from away",
    "Eruit": "Out",
    "eruit": "out",
    "Per jaar en lijst": "Per year and chart",
    "Alle noteringen": "All entries",
    "Weken (site)": "Weeks (site)",
    "nummers": "songs",
    "actief in de lijsten": "active in the charts",
    "Eerste jaar": "First year",
    "Laatste jaar": "Last year",
    "artiesten": "artists",
    "uitgezonden weken": "weeks aired",
    "Alles uitklappen": "Expand all",
    "Alles inklappen": "Collapse all",
    "Antwoord:": "Reply:",
    "Een bezoeker": "A visitor",
    "schrijf een bericht": "write a message",
    "Versturen": "Send",
    "Bericht achterlaten": "Leave a message",
    "maak een keuze…": "pick one…",
    "een opmerking": "a remark",
    "een tip": "a tip",
    "een bug — er is iets stuk": "a bug — something is broken",
    "een aanvulling — er klopt of ontbreekt iets":
        "a correction — something is wrong or missing",
    "Je bericht": "Your message",
    "Schrijf maar…": "Write away…",
    "Naam": "Name",
    "(mag leeg)": "(may stay empty)",
    "E-mail": "E-mail",
    "(alleen als je antwoord wilt)": "(only if you want a reply)",
    "Gaat over:": "About:",
    "RSS-feed": "RSS feed",
    "Volg het weekbericht via RSS": "Follow the week report via RSS",
}
