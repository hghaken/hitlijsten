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
}
