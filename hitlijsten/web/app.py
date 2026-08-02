"""De webapplicatie: routes en schermlogica."""
from __future__ import annotations

import configparser
import io
import secrets
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask, abort, flash, g, jsonify, redirect, render_template, request,
    send_file, session, url_for,
)

from .. import db, excel
from ..config import EXCEL_DIR, LIJSTEN, ROOT, decennium_van, is_jaarlijks
from ..datums import als_tekst, vrijdag_van
from ..db import Looptijd, looptijden
from . import taken

INSTELLINGEN = ROOT / "webapp.ini"

# Vrije query's zijn alleen-lezen. Een typefout in een UPDATE zonder WHERE is
# onherstelbaar, en daar staat geen enkel gemak tegenover: wijzigen kan via de
# bewerkschermen, die alles vastleggen in de tabel `wijzigingen`.
VERBODEN_IN_QUERY = (
    "insert", "update", "delete", "drop", "alter", "create", "replace",
    "attach", "detach", "pragma", "vacuum",
)


def maak_app() -> Flask:
    app = Flask(__name__)
    app.config.update(_lees_instellingen())
    # Niet "lijsten" noemen: dat botst met de zoekresultaten die zo heten.
    app.jinja_env.globals["is_aangemeld"] = is_aangemeld
    app.jinja_env.globals["lijst_namen"] = {
        sleutel: cfg["naam"] for sleutel, cfg in LIJSTEN.items()
    }
    # De weeklijsten en de jaarlijkse lijsten zijn twee soorten: een week tegen
    # een editie, dertig noteringen tegen tweeduizend. Ze door elkaar tonen
    # nodigt uit tot vergelijkingen die nergens op slaan, dus de sjablonen
    # groeperen ze -- vandaar deze twee hulpjes.
    app.jinja_env.globals["is_jaarlijks"] = is_jaarlijks
    app.jinja_env.globals["weeklijsten"] = [
        s for s in LIJSTEN if not is_jaarlijks(s)]
    app.jinja_env.globals["jaarlijkse_lijsten"] = [
        s for s in LIJSTEN if is_jaarlijks(s)]
    _registreer(app)
    return app


def _lees_instellingen() -> dict:
    """Wachtwoord en sessiesleutel uit webapp.ini.

    Ontbreekt het bestand, dan wordt er een aangemaakt met een verzonnen
    wachtwoord dat in het opstartlogboek verschijnt. Beter een wachtwoord dat je
    een keer moet opzoeken dan een applicatie die per ongeluk open staat.
    """
    parser = configparser.ConfigParser()
    if INSTELLINGEN.exists():
        parser.read(INSTELLINGEN, encoding="utf-8")

    if not parser.has_section("web"):
        parser.add_section("web")
    if not parser.get("web", "wachtwoord", fallback=""):
        parser.set("web", "wachtwoord", secrets.token_urlsafe(12))
    if not parser.get("web", "sessiesleutel", fallback=""):
        parser.set("web", "sessiesleutel", secrets.token_hex(32))

    if not INSTELLINGEN.exists():
        with INSTELLINGEN.open("w", encoding="utf-8") as fh:
            fh.write("# Instellingen van de webapplicatie. Niet delen.\n")
            parser.write(fh)
        print(f"[web] webapp.ini aangemaakt -- wachtwoord: "
              f"{parser.get('web', 'wachtwoord')}")

    return {
        "SECRET_KEY": parser.get("web", "sessiesleutel"),
        "WACHTWOORD": parser.get("web", "wachtwoord"),
    }


def vereist_aanmelding(functie):
    """Zonder aanmelding doorsturen naar het aanmeldscherm.

    Twee pagina's dragen dit bewust NIET: het overzicht en het jaaroverzicht.
    Die zijn vrij toegankelijk. Alles wat gegevens toont die niet voor iedereen
    zijn (sleutels, logboek, wijzigingen) of wat iets kan veranderen, zit er wel
    achter.
    """
    @wraps(functie)
    def omhulsel(*args, **kwargs):
        if not session.get("aangemeld"):
            return redirect(url_for("aanmelden", volgende=request.path))
        return functie(*args, **kwargs)

    return omhulsel


def is_aangemeld() -> bool:
    return bool(session.get("aangemeld"))


def verbinding() -> sqlite3.Connection:
    """Een verbinding voor dit verzoek.

    Draait het schema mee: zonder dat mist een database die met een oudere
    versie is gemaakt de nieuwere tabellen, en dat merk je pas als een pagina
    omvalt.
    """
    if "con" not in g:
        g.con = sqlite3.connect(db.DB_PATH)
        g.con.row_factory = sqlite3.Row
        g.con.executescript(db.SCHEMA)
    return g.con


def leg_vast(soort: str, verwijst: str, veld: str, oud, nieuw, reden: str) -> None:
    con = verbinding()
    con.execute(
        "INSERT INTO wijzigingen (tijdstip, soort, verwijst, veld, oud, nieuw, reden)"
        " VALUES (?,?,?,?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"), soort, verwijst, veld,
         None if oud is None else str(oud), None if nieuw is None else str(nieuw),
         reden or None),
    )
    con.commit()


def _registreer(app: Flask) -> None:

    @app.teardown_appcontext
    def sluit(_):
        con = g.pop("con", None)
        if con is not None:
            con.close()

    # --- aanmelden ---------------------------------------------------------

    @app.route("/aanmelden", methods=["GET", "POST"])
    def aanmelden():
        if request.method == "POST":
            if secrets.compare_digest(
                request.form.get("wachtwoord", ""), app.config["WACHTWOORD"]
            ):
                session["aangemeld"] = True
                return redirect(request.args.get("volgende") or url_for("overzicht"))
            flash("Onjuist wachtwoord", "fout")
        return render_template("aanmelden.html")

    @app.route("/afmelden")
    def afmelden():
        session.clear()
        return redirect(url_for("aanmelden"))

    # --- overzicht ---------------------------------------------------------

    @app.route("/")
    def overzicht():
        con = verbinding()
        lijsten = list(con.execute(
            "SELECT lijst, MIN(jaar) van, MAX(jaar) tot, COUNT(DISTINCT jaar) jaren,"
            " COUNT(DISTINCT jaar || '-' || week) weken, COUNT(*) noteringen"
            " FROM noteringen GROUP BY lijst ORDER BY van"
        ))
        cijfers = {
            "noteringen": con.execute("SELECT COUNT(*) FROM noteringen").fetchone()[0],
            "aliassen": con.execute("SELECT COUNT(*) FROM aliases").fetchone()[0],
            "uitzonderingen": con.execute(
                "SELECT COUNT(*) FROM niet_samenvoegen").fetchone()[0],
            "wijzigingen": con.execute("SELECT COUNT(*) FROM wijzigingen").fetchone()[0],
        }
        laatste = con.execute(
            "SELECT lijst, jaar, week, opgehaald_op FROM opgehaald"
            " ORDER BY opgehaald_op DESC LIMIT 5"
        ).fetchall()
        # Hoe lang is een editie? Het gemiddelde (noteringen / edities) is
        # misleidend zodra een lijst van lengte verandert: de Veronica Top 1000
        # kwam zo op 1086 uit, en zo lang is geen enkele editie geweest.
        # Daarom de echte kortste en langste editie.
        editielengtes = {}
        for lijst_naam in [r["lijst"] for r in lijsten if is_jaarlijks(r["lijst"])]:
            rij = con.execute(
                "SELECT MIN(n), MAX(n) FROM (SELECT COUNT(*) n FROM noteringen"
                " WHERE lijst=? GROUP BY jaar)", (lijst_naam,)).fetchone()
            editielengtes[lijst_naam] = (
                f"{rij[0]}" if rij[0] == rij[1] else f"{rij[0]}–{rij[1]}")

        # Groeperen gebeurt hier en niet in het sjabloon: een sqlite3.Row kent
        # geen attributen, dus selectattr() vindt er niets in.
        return render_template(
            "overzicht.html", cijfers=cijfers, laatste=laatste,
            taak=taken.huidige(),
            week_rijen=[r for r in lijsten if not is_jaarlijks(r["lijst"])],
            jaar_rijen=[r for r in lijsten if is_jaarlijks(r["lijst"])],
            editielengtes=editielengtes,
        )

    @app.route("/disclaimer")
    def disclaimer():
        """Wat deze site is en wat je er niet van moet verwachten."""
        return render_template("disclaimer.html")

    # --- jaaroverzicht -----------------------------------------------------

    @app.route("/jaar")
    def jaaroverzicht():
        con = verbinding()
        lijst = request.args.get("lijst") or "top40"
        if lijst not in LIJSTEN:
            lijst = "top40"

        jaren = [r[0] for r in con.execute(
            "SELECT DISTINCT jaar FROM noteringen WHERE lijst=? ORDER BY jaar DESC",
            (lijst,))]
        # Het nummer waar de bezoeker via een jaargrenspijl vandaan komt; dat
        # wordt op de doelpagina opgelicht zodat hij niet hoeft te zoeken.
        markeer = request.args.get("markeer") or ""

        if not jaren:
            return render_template("jaar.html", lijst=lijst, jaren=[], jaar=None,
                                   nummers=[], weken=[], hoogtepunten={},
                                   markeer=markeer)

        gevraagd = request.args.get("jaar")
        jaar = int(gevraagd) if gevraagd and gevraagd.isdigit() and int(gevraagd) in jaren \
            else jaren[0]

        # De Top 2000 is geen weeklijst maar een editie per jaar. "Positie per
        # week" levert daar een tabel van een kolom en punten zijn niets anders
        # dan de omgekeerde positie; die jaargang krijgt dus een eigen opzet,
        # met de matrix over de edities heen.
        if is_jaarlijks(lijst):
            alle_nummers = db.editie_klassement(con, lijst, jaar)
            # Een editie van vierduizend regels is 2,9 MB HTML. Korte lijsten
            # blijven compleet; pas boven de grens wordt er afgetopt, met een
            # keuze om alsnog alles te tonen.
            toon = (len(alle_nummers)
                    if request.args.get("toon") == "alles"
                    else min(EDITIE_DREMPEL, len(alle_nummers)))
            nummers = alle_nummers[:toon]
            # De matrix is 2000 rijen x 27 edities; volledig getoond verdubbelt
            # dat de pagina naar ruim 5 MB. De editie zelf blijft compleet, de
            # matrix wordt begrensd -- met een keuze om hem toch uit te klappen.
            gevraagd = request.args.get("matrix", "")
            matrix_tot = (len(nummers) if gevraagd == "alles"
                          else int(gevraagd) if gevraagd.isdigit()
                          and int(gevraagd) in MATRIX_KEUZES else MATRIX_KEUZES[0])
            return render_template(
                "editie.html", lijst=lijst, jaren=jaren, jaar=jaar,
                nummers=nummers, totaal=len(alle_nummers),
                edities=db.edities_van(con, lijst),
                matrix=nummers[:matrix_tot], matrix_tot=matrix_tot,
                matrix_keuzes=MATRIX_KEUZES, toon=toon,
                drempel=EDITIE_DREMPEL,
                markeer=request.args.get("markeer") or "",
            )

        rijen = list(con.execute(
            "SELECT week, positie, titel, artiest, label, sleutel FROM noteringen"
            " WHERE lijst=? AND jaar=? ORDER BY week, positie", (lijst, jaar)))

        # Lengte per week bepaalt de punten: hoogste positienummer van die week.
        lengte = {}
        for r in rijen:
            lengte[r["week"]] = max(lengte.get(r["week"], 0), r["positie"])
        weken = sorted(lengte)

        nummers: dict[str, dict] = {}
        for r in rijen:
            n = nummers.setdefault(r["sleutel"], {
                "sleutel": r["sleutel"], "posities": {}, "punten": 0,
            })
            # Bij een gedeelde positie telt de beste notering van die week.
            vorige = n["posities"].get(r["week"])
            if vorige is None or r["positie"] < vorige:
                if vorige is not None:
                    n["punten"] -= lengte[r["week"]] - vorige + 1
                n["posities"][r["week"]] = r["positie"]
                n["punten"] += lengte[r["week"]] - r["positie"] + 1
            n["titel"], n["artiest"], n["label"] = r["titel"], r["artiest"], r["label"]

        # Binnenkomst en laatste notering als echte uitzenddatum. Een reeks die
        # over de jaarwisseling loopt begint of eindigt in het buurjaar; de
        # markering laat zien dat de datum daarom buiten dit jaar valt.
        looptijd = looptijden(con, lijst, jaar)
        for sleutel, n in nummers.items():
            n["hoogste"] = min(n["posities"].values())
            n["weken"] = len(n["posities"])
            n["eerste_week"] = min(n["posities"])
            n["laatste_week"] = max(n["posities"])
            loop = looptijd.get(sleutel)
            if loop is None:
                loop = Looptijd(
                    begin=vrijdag_van(jaar, n["eerste_week"]),
                    eind=vrijdag_van(jaar, n["laatste_week"]),
                    begon_eerder=False, loopt_door=False,
                )
            n["eerste"] = als_tekst(loop.begin)
            n["laatste"] = als_tekst(loop.eind)
            n["begon_eerder"] = loop.begon_eerder
            n["loopt_door"] = loop.loopt_door
            # Sorteerbaar houden: de tabel sorteert op de tekst van de cel, en
            # dd/mm/yyyy sorteert alfabetisch verkeerd.
            n["eerste_sorteer"] = loop.begin.isoformat()
            n["laatste_sorteer"] = loop.eind.isoformat()

        gesorteerd = sorted(nummers.values(),
                            key=lambda n: (-n["punten"], n["hoogste"], n["eerste_week"]))

        nummer_ees = [n for n in gesorteerd if n["hoogste"] == 1]
        hoogtepunten = {
            "nummers": len(gesorteerd),
            "weken": len(weken),
            "koploper": gesorteerd[0] if gesorteerd else None,
            "nummer1s": len(nummer_ees),
            "langst": max(gesorteerd, key=lambda n: n["weken"]) if gesorteerd else None,
        }
        return render_template(
            "jaar.html", lijst=lijst, jaren=jaren, jaar=jaar,
            nummers=gesorteerd, weken=weken, hoogtepunten=hoogtepunten,
            markeer=markeer,
        )

    # --- decennium ---------------------------------------------------------

    # Alleen voor de Top 40: die is zijn hele bestaan veertig noteringen lang,
    # dus punten uit 1968 en 2024 zijn zonder voorbehoud op te tellen. Bij de
    # Tipparade zou dat niet mogen -- die telde ooit twintig noteringen en later
    # dertig, waardoor een eerste plaats in het ene jaar meer waard is dan in
    # het andere.
    DECENNIUM_LIJST = "top40"

    # Hoeveel rijen de matrix van een jaarlijkse lijst standaard toont.
    MATRIX_KEUZES = (250, 500, 1000)
    # Boven dit aantal wordt de editietabel afgetopt. Alles tot en met dit
    # aantal is compleet te tonen -- de Top 2000 dus in zijn geheel.
    EDITIE_DREMPEL = 2000

    @app.route("/decennium")
    def decennium_overzicht():
        con = verbinding()
        jaren = [r[0] for r in con.execute(
            "SELECT DISTINCT jaar FROM noteringen WHERE lijst=? ORDER BY jaar",
            (DECENNIUM_LIJST,))]
        # decennium_van() levert de mapnaam ("1970-1979"); hier is het
        # beginjaar handiger, want daar rekent decennium_totalen() mee.
        decennia = sorted({j - j % 10 for j in jaren}, reverse=True)
        if not decennia:
            return render_template("decennium.html", decennia=[], decennium=None,
                                   nummers=[], jaren=[], nummer1s=0, markeer="")

        gevraagd = request.args.get("decennium", "")
        gekozen = (int(gevraagd) if gevraagd.isdigit() and int(gevraagd) in decennia
                   else decennia[0])
        nummers = db.decennium_totalen(con, DECENNIUM_LIJST, gekozen)
        return render_template(
            "decennium.html", decennia=decennia, decennium=gekozen, nummers=nummers,
            jaren=[j for j in jaren if gekozen <= j <= gekozen + 9],
            nummer1s=sum(1 for n in nummers if n["hoogste"] == 1),
            markeer=request.args.get("markeer") or "",
        )

    # --- totaal lijst (alle jaargangen) ------------------------------------

    # 15.127 nummers in één tabel is 12 MB HTML; dat rendert geen enkele browser
    # prettig en op een telefoon helemaal niet. Daarom een keuze, met de
    # volledige lijst als optie en in de Excel altijd alles.
    AANTALLEN = (100, 500, 1000, 2500)

    # De berekening kost een halve seconde over 127.000 noteringen. Dat is per
    # bezoek zonde, en de uitkomst verandert alleen als er data bij komt --
    # vandaar een cache op het aantal noteringen plus het laatste ophaalmoment.
    _totaal_cache: dict = {}

    def _totaal_lijst(con, lijst: str, van: int, tot: int) -> list:
        stempel = con.execute(
            "SELECT COUNT(*), MAX(opgehaald_op) FROM noteringen"
            " JOIN opgehaald USING (lijst, jaar, week) WHERE lijst=?", (lijst,)
        ).fetchone()
        sleutel = (lijst, van, tot, tuple(stempel))
        if _totaal_cache.get("sleutel") != sleutel:
            _totaal_cache["sleutel"] = sleutel
            _totaal_cache["nummers"] = db.totalen_over(con, lijst, van, tot)
        return _totaal_cache["nummers"]

    @app.route("/totaal")
    def totaal_lijst():
        con = verbinding()
        van, tot = db.alle_jaren(con, DECENNIUM_LIJST)
        if van > tot:
            return render_template("totaal.html", nummers=[], van=None, tot=None,
                                   aantallen=AANTALLEN, toon=0, totaal=0,
                                   nummer1s=0, markeer="")

        nummers = _totaal_lijst(con, DECENNIUM_LIJST, van, tot)
        gevraagd = request.args.get("toon", "")
        toon = (len(nummers) if gevraagd == "alles"
                else int(gevraagd) if gevraagd.isdigit() and int(gevraagd) in AANTALLEN
                else AANTALLEN[2])
        return render_template(
            "totaal.html", nummers=nummers[:toon], van=van, tot=tot,
            aantallen=AANTALLEN, toon=toon, totaal=len(nummers),
            nummer1s=sum(1 for n in nummers if n["hoogste"] == 1),
            markeer=request.args.get("markeer") or "",
        )

    @app.route("/download/totaal")
    def download_totaal():
        """De volledige lijst als Excel -- daar past hij wél in zijn geheel in."""
        con = verbinding()
        van, tot = db.alle_jaren(con, DECENNIUM_LIJST)
        wb = excel.bouw_totalen_werkboek(con, DECENNIUM_LIJST, van, tot)
        if wb is None:
            flash("Er staat nog niets in de database.", "fout")
            return redirect(url_for("totaal_lijst"))
        naam = LIJSTEN[DECENNIUM_LIJST]["bestand"]
        bestand = f"{naam}_Totaal_{van}-{tot}.xlsx"
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return send_file(
            buffer, as_attachment=True, download_name=bestand,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # --- wetenswaardigheden ------------------------------------------------

    _weetjes_cache: dict = {}

    @app.route("/wetenswaardigheden")
    def wetenswaardigheden():
        """Tien ranglijsten over de hele historie van de Top 40.

        Kost een seconde over 127.000 noteringen, dus gecached tot er nieuwe
        data bij komt -- net als de totaallijst.
        """
        from .. import wetenswaardigheden as weetjes

        con = verbinding()
        stempel = con.execute(
            "SELECT COUNT(*), MAX(opgehaald_op) FROM noteringen"
            " JOIN opgehaald USING (lijst, jaar, week) WHERE lijst=?",
            (DECENNIUM_LIJST,),
        ).fetchone()
        if _weetjes_cache.get("stempel") != tuple(stempel):
            _weetjes_cache["stempel"] = tuple(stempel)
            _weetjes_cache["blokken"] = weetjes.verzamel(con, DECENNIUM_LIJST)
            _weetjes_cache["cijfers"] = weetjes.cijfers(con, DECENNIUM_LIJST)
        return render_template(
            "wetenswaardigheden.html",
            blokken=_weetjes_cache["blokken"], cijfers=_weetjes_cache["cijfers"],
        )

    # --- reeks voor de grafiek ---------------------------------------------

    @app.route("/reeks")
    def reeks():
        """De volledige notering van een nummer, voor de grafiek.

        Vrij toegankelijk, net als het jaaroverzicht waar hij bij hoort. Apart
        van de pagina omdat de matrix bij het jaar ophoudt en een notering dat
        niet doet: een nummer dat in november binnenkwam heeft zijn halve
        verhaal in de vorige jaargang staan.
        """
        lijst = request.args.get("lijst", "")
        jaar = request.args.get("jaar", "")
        sleutel = request.args.get("sleutel", "")
        if lijst not in LIJSTEN or not jaar.isdigit() or not sleutel:
            abort(404)
        # Een jaarlijkse lijst heeft geen weken: daar loopt de as over de
        # edities, en dan is het jaartal het label in plaats van het weeknummer.
        if is_jaarlijks(lijst):
            gegevens = db.editie_reeks(verbinding(), lijst, sleutel)
        else:
            gegevens = db.reeks_van(verbinding(), lijst, sleutel, int(jaar))
        if gegevens is None:
            abort(404)
        gegevens.setdefault("as", "week")
        return jsonify(gegevens)

    # --- Excel downloaden --------------------------------------------------

    @app.route("/download/<lijst>/<int:jaar>")
    def download(lijst: str, jaar: int):
        """Het gebouwde Excel-bestand van een lijst en jaargang.

        Twee soorten: het werkboek met de weektabs en het puntenklassement, en
        het jaarbestand met de matrix. De bestanden worden niet hier gemaakt --
        ze komen uit de wekelijkse run of uit Beheer. Ontbreekt er een, dan is
        dat een melding en geen stille lege download.
        """
        if lijst not in LIJSTEN:
            abort(404)
        soort = request.args.get("soort", "weken")
        naam = LIJSTEN[lijst]["bestand"]
        bestand = (f"{naam}_Jaar_{jaar}.xlsx" if soort == "matrix"
                   else f"{naam}_{jaar}.xlsx")
        pad = EXCEL_DIR / decennium_van(jaar) / str(jaar) / bestand
        if not pad.exists():
            flash(f"{bestand} is nog niet gebouwd. Bouw hem via Beheer.", "fout")
            return redirect(url_for("jaaroverzicht", lijst=lijst, jaar=jaar))
        return send_file(pad, as_attachment=True, download_name=bestand)

    @app.route("/download/decennium/<int:decennium>")
    def download_decennium(decennium: int):
        """Het decenniumklassement als Excel.

        Anders dan de jaarbestanden wordt dit werkboek hier ter plekke gemaakt
        in plaats van uit de wekelijkse run te komen. Het kost een fractie van
        een seconde en kan zo nooit achterlopen op de database -- een
        decenniumbestand dat na de vrijdagrun een week oud is zou stilletjes
        verkeerde totalen laten zien.
        """
        wb = excel.bouw_decennium_werkboek(verbinding(), DECENNIUM_LIJST, decennium)
        if wb is None:
            flash(f"Voor de {decennium}'s staat er niets in de database.", "fout")
            return redirect(url_for("decennium_overzicht"))
        naam = LIJSTEN[DECENNIUM_LIJST]["bestand"]
        bestand = f"{naam}_Decennium_{decennium}-{decennium + 9}.xlsx"
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return send_file(
            buffer, as_attachment=True, download_name=bestand,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.route("/download/pdf/<lijst>/<int:jaar>")
    def download_pdf(lijst: str, jaar: int):
        """Het jaaroverzicht als PDF, ter plekke gemaakt.

        Anders dan de Excel-bestanden komt dit niet uit de wekelijkse run: het
        kost een halve seconde en kan zo nooit achterlopen op de database.
        """
        from .. import pdf as pdfbouwer

        if lijst not in LIJSTEN:
            abort(404)
        # De afgesloten jaargangen staan al op schijf; die worden alleen
        # opnieuw gebouwd als de gegevens sindsdien zijn veranderd.
        con = verbinding()
        bestand = f"{LIJSTEN[lijst]['bestand']}_{jaar}.pdf"
        try:
            pad = pdfbouwer.schrijf_jaaroverzicht(con, lijst, jaar)
        except Exception:
            pad = None      # geen schrijfrechten? dan alsnog uit het geheugen
        if pad is not None and pad.exists():
            return send_file(pad, as_attachment=True, download_name=bestand,
                             mimetype="application/pdf")

        gegevens = pdfbouwer.bouw_jaaroverzicht(con, lijst, jaar)
        if gegevens is None:
            flash(f"Voor {jaar} staat er niets in de database.", "fout")
            return redirect(url_for("jaaroverzicht", lijst=lijst))
        return send_file(io.BytesIO(gegevens), as_attachment=True,
                         download_name=bestand, mimetype="application/pdf")

    # --- noteringen zoeken -------------------------------------------------

    @app.route("/zoek")
    @vereist_aanmelding
    def zoek():
        term = (request.args.get("term") or "").strip()
        lijst = request.args.get("lijst") or ""
        resultaten = []
        if term:
            vraag = (
                "SELECT sleutel, lijst, MAX(titel) titel, MAX(artiest) artiest,"
                " MIN(jaar) van, MAX(jaar) tot, COUNT(*) weken, MIN(positie) hoogste"
                " FROM noteringen WHERE (titel LIKE ? OR artiest LIKE ?)"
            )
            waarden = [f"%{term}%", f"%{term}%"]
            if lijst in LIJSTEN:
                vraag += " AND lijst=?"
                waarden.append(lijst)
            vraag += " GROUP BY sleutel, lijst ORDER BY weken DESC LIMIT 200"
            resultaten = list(verbinding().execute(vraag, waarden))
        return render_template("zoek.html", term=term, lijst=lijst,
                               resultaten=resultaten)

    @app.route("/nummer/<path:sleutel>")
    @vereist_aanmelding
    def nummer(sleutel: str):
        con = verbinding()
        rijen = list(con.execute(
            "SELECT * FROM noteringen WHERE sleutel=? ORDER BY jaar, week, positie",
            (sleutel,),
        ))
        if not rijen:
            abort(404)
        # Punten per jaar en lijst, met de lijstlengte van die week.
        lengtes = {
            (r["lijst"], r["jaar"], r["week"]): r["n"]
            for r in con.execute(
                "SELECT lijst, jaar, week, MAX(positie) n FROM noteringen"
                " GROUP BY lijst, jaar, week"
            )
        }
        samenvatting: dict[tuple[str, int], dict] = {}
        for r in rijen:
            vak = samenvatting.setdefault(
                (r["lijst"], r["jaar"]), {"punten": 0, "weken": 0, "hoogste": 99}
            )
            lengte = lengtes[(r["lijst"], r["jaar"], r["week"])]
            vak["punten"] += lengte - r["positie"] + 1
            vak["weken"] += 1
            vak["hoogste"] = min(vak["hoogste"], r["positie"])
        alias = con.execute(
            "SELECT van, naar, opmerking FROM aliases WHERE naar=? OR van=?",
            (sleutel, sleutel),
        ).fetchall()
        return render_template("nummer.html", sleutel=sleutel, rijen=rijen,
                               samenvatting=sorted(samenvatting.items()),
                               aliassen=alias)

    # --- notering met de hand corrigeren -----------------------------------

    BEWERKBAAR = ("positie", "titel", "artiest", "label", "weken_genoteerd",
                  "vorige_positie", "site_status")

    @app.route("/notering/<int:id>", methods=["GET", "POST"])
    @vereist_aanmelding
    def notering_bewerk(id: int):
        con = verbinding()
        rij = con.execute("SELECT * FROM noteringen WHERE id=?", (id,)).fetchone()
        if rij is None:
            abort(404)

        if request.method == "POST":
            reden = (request.form.get("reden") or "").strip()
            if not reden:
                flash("Geef een reden op -- die komt in het logboek te staan", "fout")
                return render_template("notering.html", rij=rij, velden=BEWERKBAAR)

            gewijzigd = []
            for veld in BEWERKBAAR:
                nieuw = (request.form.get(veld) or "").strip()
                oud = rij[veld]
                if veld in ("positie", "weken_genoteerd", "vorige_positie"):
                    nieuw = int(nieuw) if nieuw else None
                else:
                    nieuw = nieuw or None
                if nieuw != oud:
                    con.execute(f"UPDATE noteringen SET {veld}=? WHERE id=?", (nieuw, id))
                    leg_vast("notering", f"id {id}", veld, oud, nieuw, reden)
                    gewijzigd.append(veld)

            if gewijzigd and ("titel" in gewijzigd or "artiest" in gewijzigd):
                # De sleutel volgt uit titel en artiest, dus die moet mee.
                from ..normalize import sleutel_van

                ververst = con.execute(
                    "SELECT titel, artiest, sleutel FROM noteringen WHERE id=?", (id,)
                ).fetchone()
                nieuwe = sleutel_van(ververst["titel"], ververst["artiest"])
                if nieuwe != ververst["sleutel"]:
                    con.execute("UPDATE noteringen SET sleutel=? WHERE id=?", (nieuwe, id))
                    leg_vast("notering", f"id {id}", "sleutel", ververst["sleutel"],
                             nieuwe, "volgt uit titel/artiest")
            con.commit()
            flash(
                f"{len(gewijzigd)} veld(en) gewijzigd" if gewijzigd
                else "Niets gewijzigd", "goed" if gewijzigd else "fout"
            )
            return redirect(url_for("nummer", sleutel=rij["sleutel"]))

        return render_template("notering.html", rij=rij, velden=BEWERKBAAR)

    # --- aliassen ----------------------------------------------------------

    @app.route("/aliassen")
    @vereist_aanmelding
    def aliassen():
        term = (request.args.get("term") or "").strip()
        vraag = "SELECT van, naar, opmerking, aangemaakt FROM aliases"
        waarden: list = []
        if term:
            vraag += " WHERE van LIKE ? OR naar LIKE ? OR opmerking LIKE ?"
            waarden = [f"%{term}%"] * 3
        vraag += " ORDER BY van"
        return render_template("aliassen.html", term=term,
                               rijen=list(verbinding().execute(vraag, waarden)))

    @app.route("/aliassen/bewaar", methods=["POST"])
    @vereist_aanmelding
    def alias_bewaar():
        van = (request.form.get("van") or "").strip()
        naar = (request.form.get("naar") or "").strip()
        opmerking = (request.form.get("opmerking") or "").strip()
        oude_van = (request.form.get("oude_van") or "").strip()

        if not van or not naar:
            flash("Beide sleutels zijn verplicht", "fout")
        elif van == naar:
            flash("Een sleutel kan niet naar zichzelf verwijzen", "fout")
        else:
            con = verbinding()
            if oude_van and oude_van != van:
                con.execute("DELETE FROM aliases WHERE van=?", (oude_van,))
            bestond = con.execute(
                "SELECT naar FROM aliases WHERE van=?", (van,)).fetchone()
            con.execute(
                "INSERT OR REPLACE INTO aliases (van, naar, opmerking, aangemaakt)"
                " VALUES (?,?,?,?)",
                (van, naar, opmerking or None,
                 datetime.now().isoformat(timespec="seconds")),
            )
            con.commit()
            leg_vast("alias", van, "naar", bestond["naar"] if bestond else None,
                     naar, opmerking)
            flash(f"Alias bewaard. Draai 'Sleutels herberekenen' om hem te laten "
                  f"gelden.", "goed")
        return redirect(url_for("aliassen"))

    @app.route("/aliassen/verwijder", methods=["POST"])
    @vereist_aanmelding
    def alias_verwijder():
        van = (request.form.get("van") or "").strip()
        con = verbinding()
        rij = con.execute("SELECT naar FROM aliases WHERE van=?", (van,)).fetchone()
        if rij:
            con.execute("DELETE FROM aliases WHERE van=?", (van,))
            con.commit()
            leg_vast("alias", van, "naar", rij["naar"], None, "verwijderd")
            flash("Alias verwijderd. Draai 'Sleutels herberekenen'.", "goed")
        return redirect(url_for("aliassen"))

    # --- uitzonderingen ----------------------------------------------------

    @app.route("/uitzonderingen")
    @vereist_aanmelding
    def uitzonderingen():
        return render_template("uitzonderingen.html", rijen=list(verbinding().execute(
            "SELECT sleutel_a, sleutel_b, reden, aangemaakt FROM niet_samenvoegen"
            " ORDER BY sleutel_a")))

    @app.route("/uitzonderingen/bewaar", methods=["POST"])
    @vereist_aanmelding
    def uitzondering_bewaar():
        a = (request.form.get("sleutel_a") or "").strip()
        b = (request.form.get("sleutel_b") or "").strip()
        reden = (request.form.get("reden") or "").strip()
        if not a or not b:
            flash("Beide sleutels zijn verplicht", "fout")
        else:
            con = verbinding()
            con.execute(
                "INSERT OR REPLACE INTO niet_samenvoegen"
                " (sleutel_a, sleutel_b, reden, aangemaakt) VALUES (?,?,?,?)",
                (a, b, reden or None, datetime.now().isoformat(timespec="seconds")),
            )
            con.commit()
            leg_vast("niet_samenvoegen", f"{a} <-> {b}", "paar", None, "toegevoegd", reden)
            flash("Uitzondering bewaard", "goed")
        return redirect(url_for("uitzonderingen"))

    @app.route("/uitzonderingen/verwijder", methods=["POST"])
    @vereist_aanmelding
    def uitzondering_verwijder():
        a = (request.form.get("sleutel_a") or "").strip()
        b = (request.form.get("sleutel_b") or "").strip()
        con = verbinding()
        con.execute("DELETE FROM niet_samenvoegen WHERE sleutel_a=? AND sleutel_b=?",
                    (a, b))
        con.commit()
        leg_vast("niet_samenvoegen", f"{a} <-> {b}", "paar", "bestond", None,
                 "verwijderd")
        flash("Uitzondering verwijderd", "goed")
        return redirect(url_for("uitzonderingen"))

    # --- vrije query -------------------------------------------------------

    @app.route("/query", methods=["GET", "POST"])
    @vereist_aanmelding
    def query():
        sql = (request.form.get("sql") or request.args.get("sql") or "").strip()
        kolommen: list[str] = []
        rijen: list = []
        fout = None
        if sql:
            eerste = sql.lstrip().split(None, 1)[0].lower() if sql.strip() else ""
            if eerste not in ("select", "with"):
                fout = ("Alleen SELECT (of WITH) is toegestaan. Wijzigen doe je via "
                        "de bewerkschermen, dan wordt het ook vastgelegd.")
            elif any(f" {w} " in f" {sql.lower()} " for w in VERBODEN_IN_QUERY):
                fout = "Deze query bevat een wijzigend commando en is geweigerd."
            else:
                try:
                    cur = verbinding().execute(sql)
                    kolommen = [k[0] for k in cur.description or []]
                    rijen = cur.fetchmany(500)
                except sqlite3.Error as e:
                    fout = f"sqlite: {e}"
        return render_template("query.html", sql=sql, kolommen=kolommen,
                               rijen=rijen, fout=fout)

    # --- wijzigingslogboek -------------------------------------------------

    @app.route("/wijzigingen")
    @vereist_aanmelding
    def wijzigingen():
        return render_template("wijzigingen.html", rijen=list(verbinding().execute(
            "SELECT * FROM wijzigingen ORDER BY id DESC LIMIT 300")))

    # --- beheer ------------------------------------------------------------

    @app.route("/beheer")
    @vereist_aanmelding
    def beheer():
        jaren = [r[0] for r in verbinding().execute(
            "SELECT DISTINCT jaar FROM noteringen ORDER BY jaar DESC")]
        return render_template("beheer.html", jaren=jaren, taak=taken.huidige())

    @app.route("/beheer/start", methods=["POST"])
    @vereist_aanmelding
    def beheer_start():
        wat = request.form.get("wat")
        jaar = request.form.get("jaar")
        from .werk import bouw_werk

        naam, werk = bouw_werk(wat, jaar)
        if werk is None:
            flash(naam, "fout")
        else:
            gestart, melding = taken.start(naam, werk)
            flash(melding, "goed" if gestart else "fout")
        return redirect(url_for("beheer"))

    @app.route("/taak")
    @vereist_aanmelding
    def taak_stand():
        t = taken.huidige()
        if t is None:
            return {"bezig": False, "regels": []}
        return {
            "bezig": not t.klaar, "naam": t.naam, "gestart": t.gestart,
            "regels": t.regels[-60:], "gelukt": t.gelukt, "fout": t.fout,
        }
