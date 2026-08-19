"""Webapplicatie voor het beheer van de hitlijstenverzameling.

Draait op de NAS achter www.nl-hitlijsten.nl en biedt wat de opdrachtregel ook
kan, maar dan aanwijsbaar: noteringen zoeken, aliassen beheren, Excel bouwen,
weken ophalen, controles draaien en vrije query's.

Twee bewuste keuzes:

* De query-pagina is **alleen-lezen**. Vrij SQL intypen is nuttig om iets op te
  zoeken, maar een typefout in een UPDATE is onherstelbaar. Wijzigen gaat via
  de bewerkschermen, die elke wijziging in de tabel `wijzigingen` vastleggen.
* Langlopend werk (ophalen, alles herbouwen) draait in een aparte draad met een
  voortgangsmelding. Anders zou de browser minutenlang staan wachten en bij een
  time-out het werk half afmaken.
"""
