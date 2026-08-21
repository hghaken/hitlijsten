"""Zet de tests op een wegwerpdatabase. Als eerste importeren, vóór hitlijsten.

WAAROM DIT BESTAAT
------------------
Op 21 augustus 2026 heeft een testrun het hele archief gewist: 568.143
noteringen terug naar negen. Terug te zetten uit een momentopname, maar het
had niet moeten kunnen.

De oorzaak was subtiel. De tests zetten hun eigen datamap met

    os.environ.setdefault("HITLIJSTEN_DATA", tempfile.mkdtemp())

en dat is precies één woord te beleefd. `setdefault` doet niets als de
variabele al bestaat -- en op de NAS bestaat hij altijd, want je draait de
tests na `. ./omgeving.sh`, en dat is ook de enige manier waarop ze draaien
(anders vindt de code de venv en de gegevens niet). De regel die de
wegwerpmap moest afdwingen, gaf de tests dus juist de echte database. Daarna
deed `test_taal.py` wat een test hoort te doen: `DELETE FROM noteringen`.

Vandaar dit bestand. Het dwingt de wegwerpmap af in plaats van hem voor te
stellen, en het weigert te draaien als `hitlijsten.config` al is ingeladen --
want dan staat het pad al vast en heeft overschrijven geen zin meer.

Gebruik, als allereerste regel van een test:

    import veilig  # noqa: F401  -- moet vóór hitlijsten
"""
from __future__ import annotations

import os
import sys
import tempfile

if "hitlijsten.config" in sys.modules:
    raise RuntimeError(
        "veilig moet geïmporteerd worden vóór hitlijsten: config heeft het"
        " datapad al vastgelegd en wijst nu mogelijk naar de echte database")

# Overschrijven, niet voorstellen. Zie de uitleg hierboven.
ECHT = os.environ.get("HITLIJSTEN_DATA")
MAP = tempfile.mkdtemp(prefix="hitlijsten-test-")
os.environ["HITLIJSTEN_DATA"] = MAP
os.environ["HITLIJSTEN_EXCEL"] = tempfile.mkdtemp(prefix="hitlijsten-test-")

# De cache mag wél de echte zijn: daar staan de opgehaalde pagina's waar de
# parsertests op draaien, en er wordt alleen uit gelezen.
