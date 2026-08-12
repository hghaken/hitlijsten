"""Definitie van de vier hitlijsten en de projectpaden."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _map(naam: str, standaard: Path) -> Path:
    """Een map die met een omgevingsvariabele te verzetten is.

    Op de pc staat alles onder de projectmap. Op de NAS staat de code in
    <app-map> terwijl data, cache en Excel daarnaast staan, zodat
    de code vervangen kan worden zonder de gegevens aan te raken.
    """
    uit_omgeving = os.environ.get(naam)
    return Path(uit_omgeving) if uit_omgeving else standaard


CACHE_DIR = _map("HITLIJSTEN_CACHE", ROOT / ".cache")
DATA_DIR = _map("HITLIJSTEN_DATA", ROOT / "data")
EXCEL_DIR = _map("HITLIJSTEN_EXCEL", ROOT)
DB_PATH = DATA_DIR / "hitlijsten.sqlite"
ALIASES_PATH = ROOT / "aliases.csv"
NIET_SAMENVOEGEN_PATH = ROOT / "niet-samenvoegen.csv"
LOG_PATH = ROOT / "run.log"

# Het lopende jaar, niet vastgezet: begin januari publiceren de sites soms nog
# een week van de vorige jaargang. Welk jaar er echt bij een week hoort bepaalt
# de site, niet de kalender -- zie fetch.laatst_gepubliceerd().
JAAR = date.today().year

# site: welke parser de HTML afhandelt.
# lengte: verwacht aantal noteringen; None = variabel (structuurcontrole kijkt dan
#         alleen of de posities 1..N aaneengesloten zijn).
LIJSTEN = {
    "top40": {
        "naam": "Nederlandse Top 40",
        "site": "top40nl",
        "slug": "top40",
        "lengte": 40,
        "bestand": "Top40",
        "heeft_label": False,
        "vanaf_jaar": 1965,
    },
    "tipparade": {
        "naam": "Tipparade",
        "site": "top40nl",
        "slug": "tipparade",
        "lengte": 30,
        # De Tipparade is niet altijd 30 lang geweest: gemeten 20 in 1968,
        # 25 in 1969, en vanaf 1970 rond de 30 met uitschieters (32 in 1971,
        # 31 in 1974). Voor de oude jaargangen laten we de lengte daarom vrij;
        # de controle op aaneengesloten posities 1..N blijft wel gelden.
        "lengte_voor": {(1967, 1974): None},
        # Oudste jaargang die de site echt heeft. Daarvoor geeft hij geen 404
        # maar stilletjes een andere lijst -- zie fetch.controleer_gevraagde_week.
        "vanaf_jaar": 1967,
        "bestand": "Tipparade",
        "heeft_label": False,
    },
    "sterrennl": {
        "naam": "Sterren NL Top 25",
        "site": "top40nl",
        "slug": "sterren-nl-top25",
        "lengte": 25,
        "bestand": "SterrenNL",
        "heeft_label": False,
        "vanaf_jaar": 2019,   # 2019 loopt pas vanaf week 40
    },
    "oranje": {
        "naam": "Oranje Top 30",
        "site": "oranjetop30",
        "slug": None,
        "lengte": 30,
        "bestand": "OranjeTop30",
        "heeft_label": True,
        "vanaf_jaar": 2008,
    },
    # De vreemde eend. De Top 2000 is geen weeklijst maar een jaarlijkse
    # uitzending tussen kerst en oud en nieuw, met tweeduizend noteringen in
    # een keer. Er is geen site die wij uitlezen: de gegevens komen uit een
    # CSV (Music Datastats) en worden met de hand geimporteerd, zodra de
    # nieuwe editie er is. Vandaar site=None -- daar herkent de wekelijkse run
    # aan dat hij deze lijst met rust moet laten.
    "top2000": {
        "naam": "Top 2000 (NPO Radio 2)",
        "site": None,
        "slug": None,
        "lengte": 2000,
        "bestand": "Top2000",
        "heeft_label": False,
        "vanaf_jaar": 1999,
        "jaarlijks": True,
        # Week 52 is de PLEK IN HET SCHEMA waar de editie hoort, geen bewering
        # over de uitzenddatum: er is maar een notering per jaargang, en de
        # editiepagina toont jaartallen in plaats van weken.
        "editie_week": 52,
    },
    "qtop1500": {
        "naam": "Q Top 1500 (Qmusic)",
        "site": None,
        "slug": None,
        # Negentien edities van duizend; vanaf 2024 vijftienhonderd.
        "lengte": 1500,
        "bestand": "QTop1500",
        "heeft_label": False,
        "vanaf_jaar": 2005,
        "jaarlijks": True,
        "editie_week": 52,
    },
    "veronica": {
        "naam": "Top 1000 (Veronica)",
        "site": None,
        "slug": None,
        # Tweeentwintig edities lang precies duizend, maar in 2025 ineens
        # drieduizend. `lengte` is voor de jaarlijkse lijsten dan ook een
        # bovengrens en geen verwachting: de echte lengte komt per editie uit
        # de data zelf.
        "lengte": 3000,
        "bestand": "VeronicaTop1000",
        "heeft_label": False,
        "vanaf_jaar": 2003,
        "jaarlijks": True,
        "editie_week": 52,
    },
    "top4000": {
        "naam": "Top 4000 (Radio 10)",
        "site": None,
        "slug": None,
        "lengte": 4000,
        "bestand": "Top4000",
        "heeft_label": False,
        "vanaf_jaar": 2005,
        "jaarlijks": True,
        "editie_week": 52,
    },
    "evergreen": {
        "naam": "Evergreen Top 1000 (NPO Radio 5)",
        "site": None,
        "slug": None,
        "lengte": 1000,
        "bestand": "EvergreenTop1000",
        "heeft_label": False,
        "vanaf_jaar": 2008,
        "jaarlijks": True,
        "editie_week": 52,
    },
    # De enige jaarlijkse lijst waarvan de zender al in de naam zit; die staat
    # er dus niet nog eens tussen haakjes achter.
    "kink": {
        "naam": "Kink Top 1500",
        "site": None,
        "slug": None,
        "lengte": 1500,
        "bestand": "KinkTop1500",
        "heeft_label": False,
        "vanaf_jaar": 2019,
        "jaarlijks": True,
        "editie_week": 52,
    },
    "arrow": {
        "naam": "Rock Top 500 (Arrow)",
        "site": None,
        "slug": None,
        "lengte": 500,
        "bestand": "RockTop500",
        "heeft_label": False,
        "vanaf_jaar": 2000,
        "jaarlijks": True,
        "editie_week": 52,
    },
    # De tien lijsten hieronder kwamen er in een keer bij (augustus 2026).
    # `editie_week` is bij deze lijsten een benadering: het is de week waarin
    # de uitzending doorgaans valt, opgezocht per zender. De 80's Top 810
    # sluit bijvoorbeeld de 80's Maand van maart af en de Koninklijke 500
    # draait rond Koningsdag.
    "top810": {
        "naam": "80's Top 810 (Radio 10)",
        "site": None,
        "slug": None,
        "lengte": 810,
        "bestand": "80sTop810",
        "heeft_label": False,
        "vanaf_jaar": 2014,
        "jaarlijks": True,
        "editie_week": 13,
    },
    "q90s": {
        "naam": "90's Top 500 (Qmusic)",
        "site": None,
        "slug": None,
        "lengte": 500,
        "bestand": "90sTop500",
        "heeft_label": False,
        "vanaf_jaar": 2010,
        "jaarlijks": True,
        "editie_week": 7,
    },
    "koninklijke": {
        "naam": "De Koninklijke 500 (NPO Radio 2)",
        "site": None,
        "slug": None,
        "lengte": 500,
        "bestand": "Koninklijke500",
        "heeft_label": False,
        "vanaf_jaar": 2022,
        "jaarlijks": True,
        "editie_week": 17,
    },
    "festival": {
        "naam": "Festival Top 1003 (NPO Radio 3FM)",
        "site": None,
        "slug": None,
        # Heette eerst Festival Top 999; sinds 2024 vier nummers langer.
        "lengte": 1003,
        "bestand": "FestivalTop1003",
        "heeft_label": False,
        "vanaf_jaar": 2018,
        "jaarlijks": True,
        "editie_week": 24,
    },
    # Net als bij de Kink Top 1500 zit de zender al in de naam.
    "kink80s": {
        "naam": "Kink 80's Top 500",
        "site": None,
        "slug": None,
        "lengte": 500,
        "bestand": "Kink80sTop500",
        "heeft_label": False,
        "vanaf_jaar": 2021,
        "jaarlijks": True,
        "editie_week": 38,
    },
    "qzeroes": {
        "naam": "Q Zeroes Top 500 (Qmusic)",
        "site": None,
        "slug": None,
        "lengte": 500,
        "bestand": "QZeroesTop500",
        "heeft_label": False,
        "vanaf_jaar": 2013,
        "jaarlijks": True,
        "editie_week": 39,
    },
    "soul1000": {
        "naam": "Sublime Soul Top 1000 (Sublime)",
        "site": None,
        "slug": None,
        "lengte": 1000,
        "bestand": "SublimeSoulTop1000",
        "heeft_label": False,
        "vanaf_jaar": 2021,
        "jaarlijks": True,
        "editie_week": 15,
    },
    "jaren60": {
        "naam": "Toplijst van de jaren 60 (NPO Radio 5)",
        "site": None,
        "slug": None,
        # Een lijst zonder vaste lengte: tussen de 200 en 224 noteringen,
        # elk jaar anders. `lengte` is dan een ruime bovengrens.
        "lengte": 250,
        "bestand": "ToplijstJaren60",
        "heeft_label": False,
        "vanaf_jaar": 2010,
        "jaarlijks": True,
        "editie_week": 24,
    },
    "jaren70": {
        "naam": "Toplijst van de jaren 70 (NPO Radio 5)",
        "site": None,
        "slug": None,
        "lengte": 250,
        "bestand": "ToplijstJaren70",
        "heeft_label": False,
        "vanaf_jaar": 2010,
        "jaarlijks": True,
        "editie_week": 24,
    },
    "zomer500": {
        "naam": "Zomer Top 500 (Qmusic)",
        "site": None,
        "slug": None,
        "lengte": 500,
        "bestand": "ZomerTop500",
        "heeft_label": False,
        "vanaf_jaar": 2012,
        "jaarlijks": True,
        "editie_week": 30,
    },
}


def is_jaarlijks(lijst: str) -> bool:
    """Een lijst met een editie per jaar in plaats van een notering per week."""
    return bool(LIJSTEN.get(lijst, {}).get("jaarlijks"))


def wordt_opgehaald(lijst: str) -> bool:
    """Haalt de wekelijkse run deze lijst van een site? Zo niet: met rust laten."""
    return bool(LIJSTEN.get(lijst, {}).get("site"))


def verwachte_lengte(lijst: str, jaar: int) -> int | None:
    """Hoeveel noteringen een lijst in een bepaald jaar hoort te hebben.

    None betekent: lengte niet vastgezet, alleen controleren of de posities
    1..N aaneengesloten zijn.
    """
    cfg = LIJSTEN[lijst]
    for (vanaf, tot), lengte in cfg.get("lengte_voor", {}).items():
        if vanaf <= jaar <= tot:
            return lengte
    return cfg["lengte"]


def decennium_van(jaar: int) -> str:
    """De naam van de decenniummap: 2026 -> "2020-2029"."""
    begin = jaar // 10 * 10
    return f"{begin}-{begin + 9}"


def excel_map(jaar: int) -> Path:
    """Waar de Excel-bestanden van een jaargang landen: <excel>/2020-2029/2026/.

    Per jaar een eigen map, gegroepeerd per decennium. Met zestig jaargangen
    zouden zestig mappen naast elkaar onwerkbaar worden.
    """
    map_ = EXCEL_DIR / decennium_van(jaar) / str(jaar)
    map_.mkdir(parents=True, exist_ok=True)
    return map_


def url_voor(lijst: str, jaar: int, week: int) -> str:
    cfg = LIJSTEN[lijst]
    if cfg["site"] == "top40nl":
        return f"https://www.top40.nl/{cfg['slug']}/{jaar}/week-{week}"
    if cfg["site"] == "oranjetop30":
        return f"https://www.oranjetop30.nl/{jaar}/{week}"
    raise ValueError(f"onbekende site voor lijst {lijst!r}")
