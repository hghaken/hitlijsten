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

# Waar de site voor de buitenwereld woont; voor canonical-links, Open
# Graph-tags en de sitemap. Achter de reverse proxy is request.url_root
# onbetrouwbaar (http, intern adres), dus dit staat vast.
HOOFD_URL = "https://hitlijsten.hhaken.nl"

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
    app.jinja_env.globals["hoofd_url"] = HOOFD_URL
    app.jinja_env.globals["canoniek"] = _canoniek
    app.jinja_env.globals["lijst_namen"] = {
        sleutel: cfg["naam"] for sleutel, cfg in LIJSTEN.items()
    }
    # De weeklijsten en de jaarlijkse lijsten zijn twee soorten: een week tegen
    # een editie, dertig noteringen tegen tweeduizend. Ze door elkaar tonen
    # nodigt uit tot vergelijkingen die nergens op slaan, dus de sjablonen
    # groeperen ze -- vandaar deze twee hulpjes.
    app.jinja_env.globals["is_jaarlijks"] = is_jaarlijks
    app.jinja_env.filters["tijd"] = leesbare_tijd
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


def _canoniek() -> str:
    """Het publieke adres van de huidige pagina, netjes percent-gecodeerd.

    Flask levert request.path ontcijferd af ("/nummer/golden earring|radar
    love"); voor een canonical-link moeten spaties en pijpen weer %20 en %7C
    worden. De query-string is nog rauw en kan zo mee.
    """
    from urllib.parse import quote

    pad = quote(request.path, safe="/")
    vraag = request.query_string.decode()
    return HOOFD_URL + pad + (f"?{vraag}" if vraag else "")


def is_aangemeld() -> bool:
    return bool(session.get("aangemeld"))


_schema_gedraaid = False


def verbinding() -> sqlite3.Connection:
    """Een verbinding voor dit verzoek.

    Draait het schema mee: zonder dat mist een database die met een oudere
    versie is gemaakt de nieuwere tabellen, en dat merk je pas als een pagina
    omvalt.
    """
    if "con" not in g:
        g.con = sqlite3.connect(db.DB_PATH)
        g.con.row_factory = sqlite3.Row
        db._stel_in(g.con)
        # Het schema wordt één keer per proces gedraaid en niet per verzoek.
        # `CREATE TABLE IF NOT EXISTS` doet weliswaar niets, maar het is wél een
        # schrijfactie -- en dan botst elke paginaweergave met een lopende
        # achtergrondtaak. Precies zo viel er een om met "database is locked"
        # terwijl er alleen maar iemand door de zoekresultaten klikte.
        global _schema_gedraaid
        if not _schema_gedraaid:
            g.con.executescript(db.SCHEMA)
            _schema_gedraaid = True
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


def zoekpatroon(term: str) -> str:
    """Maak van wat er is ingetypt een patroon voor LIKE.

    Een sterretje is het jokerteken, want dat is wat mensen typen; SQL wil er
    een procentteken. Zonder sterretje zoeken we "bevat", want dat is bij een
    hitlijst bijna altijd de bedoeling -- wie "beatles" intypt wil ook "The
    Beatles" vinden.

        beatles      bevat        ->  %beatles%
        beatles*     begint met   ->  beatles%
        *beatles     eindigt op   ->  %beatles
        *beatles*    bevat        ->  %beatles%

    De procent- en onderstrepingstekens die iemand zélf intypt worden ontsnapt,
    anders is "50%" ineens een joker en vindt hij alles.
    """
    term = (term or "").strip()
    if not term:
        return ""
    veilig = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    if "*" in veilig:
        return veilig.replace("*", "%")
    return f"%{veilig}%"


def _als_sleutel(tekst: str | None) -> str:
    """Maak van wat er is ingetypt een echte sleutel.

    Het aliasscherm vraagt om "artiest|titel" en dan typ je vanzelf op wat je op
    de site ziet: "ABBA*Teens|Mamma Mia". Een sleutel is echter altijd kleine
    letters zonder leestekens, dus zo'n alias wordt nooit gevonden -- en het
    ergste is dat er geen foutmelding komt, want de regel staat er keurig in.
    Vandaar dat allebei de vormen worden geaccepteerd.

    `sleutel_van` wordt hier bewust niet gebruikt: die volgt aan het eind de
    aliassen door, en juist bij de "van"-kant wil je de sleutel zoals hij uit de
    naam volgt en niet waar hij nu al naartoe wijst.
    """
    from ..normalize import artiestsleutel, normaliseer

    tekst = (tekst or "").strip()
    if "|" not in tekst:
        return tekst
    artiest, _, titel = tekst.partition("|")
    return f"{artiestsleutel(artiest)}|{normaliseer(titel, samenwerking=False)}"


def leesbare_tijd(stempel: str | None) -> str:
    """2026-08-02T11:17:18 -> 02-08-2026 11:17. Leeg blijft leeg."""
    if not stempel:
        return ""
    try:
        return datetime.fromisoformat(stempel).strftime("%d-%m-%Y %H:%M")
    except ValueError:
        return stempel


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

    # --- Nederlandstalig ---------------------------------------------------

    _taal_cache: dict = {}

    def _nl_sleutels() -> set:
        """Alle Nederlandstalige sleutels, gecachet tot de tabel verandert."""
        from ..taal import SCHEMA, nederlandstalige_sleutels

        con = verbinding()
        con.executescript(SCHEMA)
        stempel = tuple(con.execute(
            "SELECT COUNT(*), MAX(aangemaakt) FROM taal").fetchone())
        if _taal_cache.get("stempel") != stempel:
            _taal_cache["stempel"] = stempel
            _taal_cache["sleutels"] = nederlandstalige_sleutels(con)
        return _taal_cache["sleutels"]

    def _is_nl(sleutel: str) -> bool:
        return sleutel in _nl_sleutels()

    app.jinja_env.globals["is_nl"] = _is_nl

    @app.context_processor
    def _nl_filter_stand():
        # Elke lijstpagina kent hetzelfde filter; de templates lezen de stand
        # hieruit zodat niet elke render-aanroep hem hoeft door te geven.
        return {"nl_filter_aan": bool(request.args.get("nl"))}

    def _alleen_nl(rijen, sleutel_van=lambda r: r["sleutel"]):
        """Pas het Nederlandstalig-filter toe als dat aan staat."""
        if not request.args.get("nl"):
            return rijen
        nlset = _nl_sleutels()
        return [r for r in rijen if sleutel_van(r) in nlset]

    @app.route("/taal/zet", methods=["POST"])
    @vereist_aanmelding
    def taal_zet():
        """Handmatig markeren of ontmarkeren; wint van de automatiek."""
        from ..taal import zet_hand

        sleutel = request.form.get("sleutel", "")
        if not sleutel:
            abort(400)
        zet_hand(verbinding(), sleutel,
                 request.form.get("nederlandstalig") == "1")
        _taal_cache.clear()
        return redirect(request.referrer or url_for("overzicht"))

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
        # Wanneer is er voor het laatst iets binnengehaald? Alleen de
        # weeklijsten tonen dit: bij een jaarlijkse lijst is het niet meer dan
        # het moment van de handmatige import.
        laatst_op = {
            r[0]: r[1] for r in con.execute(
                "SELECT lijst, MAX(opgehaald_op) FROM opgehaald GROUP BY lijst")
        }
        # En tot welke week loopt die lijst? De laatste week van het laatste
        # jaar -- uit `noteringen`, net als het jaartal ernaast, want een
        # opgehaalde week zonder noteringen (kerst) is geen "tot".
        laatste_week = {
            r[0]: r[1] for r in con.execute(
                "SELECT lijst, MAX(week) FROM noteringen n WHERE jaar ="
                " (SELECT MAX(jaar) FROM noteringen WHERE lijst=n.lijst)"
                " GROUP BY lijst")
        }

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
            editielengtes=editielengtes, laatst_op=laatst_op,
            laatste_week=laatste_week,
        )

    @app.route("/week")
    def weeklijst():
        """Eén week zoals hij is uitgezonden, met bladeren langs de kalender.

        Alleen voor de weeklijsten: een jaarlijkse lijst heeft geen weken, en
        de editie staat al compleet op de jaarpagina.
        """
        con = verbinding()
        lijst = request.args.get("lijst") or "top40"
        if lijst not in LIJSTEN or is_jaarlijks(lijst):
            lijst = "top40"

        # De kalender van uitgezonden weken van deze lijst, op volgorde. Daar
        # komt alles uit: de keuzelijsten, de standaardweek (de nieuwste) en de
        # buren om langs te bladeren -- over de jaargrens heen, en een
        # overgeslagen kerstweek wordt daarbij vanzelf overgeslagen.
        kalender = [(r[0], r[1]) for r in con.execute(
            "SELECT DISTINCT jaar, week FROM noteringen WHERE lijst=?"
            " ORDER BY jaar, week", (lijst,))]
        if not kalender:
            abort(404)

        try:
            jaar = int(request.args.get("jaar", ""))
            week = int(request.args.get("week", ""))
        except ValueError:
            jaar, week = kalender[-1]
        if (jaar, week) not in kalender:
            # Een jaartal zonder geldige week: de eerste week van dat jaar,
            # zodat wisselen van jaar in de keuzelijst altijd ergens uitkomt.
            in_jaar = [w for j, w in kalender if j == jaar]
            if in_jaar:
                week = in_jaar[0] if week not in in_jaar else week
            else:
                jaar, week = kalender[-1]

        plek = kalender.index((jaar, week))
        vorige = kalender[plek - 1] if plek > 0 else None
        volgende = kalender[plek + 1] if plek + 1 < len(kalender) else None

        rijen = list(con.execute(
            "SELECT positie, vorige_positie, artiest, titel, label,"
            " weken_genoteerd, site_status, sleutel, alarmschijf FROM noteringen"
            " WHERE lijst=? AND jaar=? AND week=? ORDER BY positie, artiest",
            (lijst, jaar, week)))
        rijen = _alleen_nl(rijen)
        try:
            datum = als_tekst(vrijdag_van(jaar, week))
        except Exception:
            datum = None
        return render_template(
            "week.html", lijst=lijst, jaar=jaar, week=week, rijen=rijen,
            jaren=sorted({j for j, _ in kalender}, reverse=True),
            weken=[w for j, w in kalender if j == jaar],
            vorige=vorige, volgende=volgende, datum=datum,
            heeft_label=any(r["label"] for r in rijen),
        )

    _sitemap_cache: dict = {}

    @app.route("/sitemap.xml")
    def sitemap():
        """Alle openbare pagina's voor de zoekmachines.

        Verreweg de meeste regels zijn nummerpagina's: elke unieke sleutel is
        een landingspagina voor een zoekopdracht als "hoogste positie Radar
        Love". De limiet van het sitemap-formaat is 50.000 regels; met zo'n
        45.000 nummers past alles nu in een bestand, en de teller hieronder
        maakt er lawaai van als dat ooit niet meer zo is.
        """
        con = verbinding()
        stempel = tuple(con.execute(
            "SELECT COUNT(*), MAX(tijdstip) FROM wijzigingen").fetchone()) + (
            con.execute("SELECT COUNT(*) FROM noteringen").fetchone()[0],)
        if _sitemap_cache.get("stempel") != stempel:
            regels = ["/", "/jaar", "/week", "/decennium", "/totaal",
                      "/jaarlijksen", "/wetenswaardigheden", "/zoek",
                      "/gastenboek", "/feedback", "/disclaimer"]
            for r in con.execute(
                    "SELECT DISTINCT lijst, jaar FROM noteringen"
                    " ORDER BY lijst, jaar"):
                regels.append(url_for("jaaroverzicht", lijst=r["lijst"],
                                      jaar=r["jaar"]))
            for r in con.execute(
                    "SELECT DISTINCT sleutel FROM noteringen ORDER BY sleutel"):
                regels.append(url_for("nummer", sleutel=r["sleutel"]))
            if len(regels) > 50000:
                app.logger.warning("sitemap: %d regels, boven de limiet van"
                                   " 50.000 -- opsplitsen", len(regels))
            stukken = ['<?xml version="1.0" encoding="UTF-8"?>',
                       '<urlset xmlns="http://www.sitemaps.org/schemas/'
                       'sitemap/0.9">']
            # XML-escape: de jaargang-URL's dragen een & in de query.
            stukken += [f"<url><loc>{HOOFD_URL}{pad.replace('&', '&amp;')}"
                        f"</loc></url>" for pad in regels[:50000]]
            stukken.append("</urlset>")
            _sitemap_cache["stempel"] = stempel
            _sitemap_cache["xml"] = "\n".join(stukken)
        return app.response_class(_sitemap_cache["xml"],
                                  mimetype="application/xml")

    @app.route("/robots.txt")
    def robots():
        regels = ["User-agent: *"]
        regels += [f"Disallow: {pad}" for pad in (
            "/beheer", "/berichten", "/taak", "/aliassen", "/uitzonderingen",
            "/query", "/wijzigingen", "/aanmelden", "/notering/", "/reeks",
            "/download/")]
        regels.append(f"Sitemap: {HOOFD_URL}/sitemap.xml")
        return app.response_class("\n".join(regels) + "\n",
                                  mimetype="text/plain")

    @app.route("/disclaimer")
    def disclaimer():
        """Wat deze site is en wat je er niet van moet verwachten."""
        return render_template("disclaimer.html")

    # --- gastenboek en feedback --------------------------------------------

    @app.route("/gastenboek")
    def gastenboek():
        """De gepubliceerde berichten, nieuwste bovenaan."""
        con = verbinding()
        berichten = list(con.execute(
            "SELECT * FROM berichten WHERE status='gepubliceerd'"
            " ORDER BY tijdstip DESC"))
        return render_template("gastenboek.html", berichten=berichten)

    @app.route("/feedback", methods=["GET", "POST"])
    def feedback():
        """Het formulier voor bezoekers; alles komt privé binnen.

        Spamwering zonder CAPTCHA, drie lagen: een honeypot-veld dat mensen
        niet zien maar bots invullen, een minimale invultijd, en een limiet
        per IP-adres. Wie daar doorheen komt en toch rommel stuurt, wordt
        gewoon niet gepubliceerd -- niets staat live zonder akkoord.
        """
        if request.method == "POST":
            fout = _bewaar_bericht(verbinding())
            if fout:
                flash(fout, "fout")
            else:
                flash("Dank voor je bericht! Het is aangekomen en wordt "
                      "gelezen; wat in het gastenboek mag, verschijnt daar "
                      "na een akkoord.", "goed")
                return redirect(url_for("gastenboek"))
        return render_template(
            "feedback.html",
            pagina=request.args.get("pagina") or request.form.get("pagina") or "",
            soort=request.args.get("soort") or request.form.get("soort") or "",
            geopend=int(datetime.now().timestamp()))

    def _bezoeker_ip() -> str:
        """Het echte adres, ook achter de reverse proxy van de NAS."""
        doorgegeven = request.headers.get("X-Forwarded-For", "")
        if doorgegeven:
            return doorgegeven.split(",")[0].strip()
        return request.headers.get("X-Real-IP") or request.remote_addr or "?"

    def _bewaar_bericht(con: sqlite3.Connection) -> str | None:
        """Controleer en bewaar een binnengekomen bericht. Geeft de foutmelding
        terug, of None als het gelukt is."""
        # De honeypot: een veld dat via CSS onzichtbaar is. Een mens laat het
        # leeg; een bot die blind alle velden invult, valt hier door de mand.
        if request.form.get("website", ""):
            return "Er ging iets mis met het formulier."
        try:
            geopend = int(request.form.get("geopend", "0"))
        except ValueError:
            geopend = 0
        duur = datetime.now().timestamp() - geopend
        if not 4 <= duur <= 6 * 3600:
            return ("Dat ging wel erg snel — probeer het nog een keer "
                    "(dit weert geautomatiseerde inzendingen).")

        soort = request.form.get("soort", "")
        if soort not in ("opmerking", "tip", "bug", "aanvulling"):
            return "Kies wat voor soort bericht het is."
        tekst = request.form.get("tekst", "").strip()
        if not tekst:
            return "Een leeg bericht heeft geen zin — schrijf iets!"
        if len(tekst) > 5000:
            return "Dat is te lang voor één bericht (maximaal 5.000 tekens)."
        naam = request.form.get("naam", "").strip()[:100]
        email = request.form.get("email", "").strip()[:200]
        if email and ("@" not in email or "." not in email.split("@")[-1]):
            return "Dat e-mailadres ziet er niet goed uit."

        ip = _bezoeker_ip()
        gister = datetime.fromtimestamp(
            datetime.now().timestamp() - 24 * 3600).isoformat(timespec="seconds")
        aantal = con.execute(
            "SELECT COUNT(*) FROM berichten WHERE ip=? AND tijdstip>?",
            (ip, gister)).fetchone()[0]
        if aantal >= 5:
            return ("Vanaf dit adres zijn al vijf berichten binnengekomen "
                    "vandaag — probeer het morgen weer.")

        con.execute(
            "INSERT INTO berichten (tijdstip, soort, naam, email, tekst,"
            " pagina, mag_openbaar, ip) VALUES (?,?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), soort,
             naam or None, email or None, tekst,
             request.form.get("pagina", "").strip()[:300] or None,
             1 if request.form.get("mag_openbaar") else 0, ip))
        con.commit()

        # De mailmelding is een luxe, geen voorwaarde: als de mail faalt is
        # het bericht al veilig bewaard en zichtbaar op de berichtenpagina.
        try:
            from ..mail import verstuur
            verstuur(
                f"Hitlijsten: nieuw bericht ({soort})",
                f"Van: {naam or 'anoniem'} {email or ''}\n"
                f"Soort: {soort}\n"
                f"Pagina: {request.form.get('pagina', '') or '-'}\n"
                f"Gastenboek: {'ja' if request.form.get('mag_openbaar') else 'nee'}\n"
                f"\n{tekst}\n")
        except Exception:
            pass
        return None

    @app.route("/berichten")
    @vereist_aanmelding
    def berichten():
        """De postbus voor de beheerder: alles, met knoppen per bericht."""
        con = verbinding()
        rijen = list(con.execute(
            "SELECT * FROM berichten ORDER BY"
            " CASE status WHEN 'nieuw' THEN 0 ELSE 1 END, tijdstip DESC"))
        return render_template("berichten.html", berichten=rijen)

    @app.route("/berichten/actie", methods=["POST"])
    @vereist_aanmelding
    def berichten_actie():
        con = verbinding()
        nummer = request.form.get("id", "")
        actie = request.form.get("actie", "")
        rij = con.execute("SELECT * FROM berichten WHERE id=?",
                          (nummer,)).fetchone()
        if rij is None:
            abort(404)
        if actie == "publiceren":
            con.execute("UPDATE berichten SET status='gepubliceerd'"
                        " WHERE id=?", (nummer,))
        elif actie == "prive":
            con.execute("UPDATE berichten SET status='prive' WHERE id=?",
                        (nummer,))
        elif actie == "verwijderen":
            con.execute("DELETE FROM berichten WHERE id=?", (nummer,))
        elif actie == "antwoord":
            con.execute("UPDATE berichten SET antwoord=? WHERE id=?",
                        (request.form.get("antwoord", "").strip()[:2000]
                         or None, nummer))
        else:
            abort(400)
        con.commit()
        return redirect(url_for("berichten"))

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
            alle_nummers = _alleen_nl(alle_nummers)
            toon = (len(alle_nummers)
                    if request.args.get("toon") == "alles"
                    else min(EDITIE_DREMPEL, len(alle_nummers)))
            # Komt de bezoeker binnen via een verwijzing naar een bepaald
            # nummer, dan is aftoppen juist verkeerd: bij een editie van
            # vierduizend staat plek 3033 niet op de eerste tweeduizend, en dan
            # land je op een pagina waar je nummer niet op staat. Klik je van
            # een zoekresultaat naar "Paul De Leeuw ; Bob De Rooy - Annie" in de
            # Top 4000 van 2005, dan hoort die regel er gewoon te zijn.
            markeer = request.args.get("markeer") or ""
            if markeer:
                plek = next((i for i, n in enumerate(alle_nummers, 1)
                             if n["sleutel"] == markeer), 0)
                if plek > toon:
                    toon = len(alle_nummers)
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
                drempel=EDITIE_DREMPEL, markeer=markeer,
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

        gesorteerd = _alleen_nl(gesorteerd)
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
        nummers = _alleen_nl(db.decennium_totalen(con, DECENNIUM_LIJST,
                                                  gekozen))
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

        nummers = _alleen_nl(_totaal_lijst(con, DECENNIUM_LIJST, van, tot))
        gevraagd = request.args.get("toon", "")
        # Standaard de top 100: dat laadt vlot en is wat je meestal zoekt;
        # wie meer wil, kiest het in de keuzelijst.
        toon = (len(nummers) if gevraagd == "alles"
                else int(gevraagd) if gevraagd.isdigit() and int(gevraagd) in AANTALLEN
                else AANTALLEN[0])
        return render_template(
            "totaal.html", nummers=nummers[:toon], van=van, tot=tot,
            aantallen=AANTALLEN, toon=toon, totaal=len(nummers),
            nummer1s=sum(1 for n in nummers if n["hoogste"] == 1),
            markeer=request.args.get("markeer") or "",
        )

    _jaarlijksen_cache: dict = {}

    @app.route("/jaarlijksen")
    def jaarlijksen_lijst():
        """Alle jaarlijkse lijsten samen, genormaliseerd op lijstlengte.

        Dezelfde cache-opzet als de wetenswaardigheden: één telling over
        238.500 noteringen kost een seconde, en de uitkomst verandert alleen
        als er een editie bij komt of een correctie is gedaan.
        """
        con = verbinding()
        namen = [s for s in LIJSTEN if is_jaarlijks(s)]
        plek = ",".join("?" for _ in namen)
        stempel = tuple(con.execute(
            f"SELECT COUNT(*), MAX(opgehaald_op) FROM noteringen"
            f" JOIN opgehaald USING (lijst, jaar, week)"
            f" WHERE lijst IN ({plek})", namen).fetchone())
        wijzig = con.execute(
            "SELECT MAX(tijdstip) FROM wijzigingen").fetchone()[0]
        if _jaarlijksen_cache.get("stempel") != (stempel, wijzig):
            _jaarlijksen_cache["stempel"] = (stempel, wijzig)
            _jaarlijksen_cache["nummers"] = db.jaarlijkse_totalen(con)
        nummers = _alleen_nl(_jaarlijksen_cache["nummers"])

        gevraagd = request.args.get("toon", "")
        # Net als de totaallijst: standaard de top 100.
        toon = (len(nummers) if gevraagd == "alles"
                else int(gevraagd) if gevraagd.isdigit() and int(gevraagd) in AANTALLEN
                else AANTALLEN[0])
        edities = con.execute(
            f"SELECT COUNT(DISTINCT lijst || '-' || jaar) FROM noteringen"
            f" WHERE lijst IN ({plek})", namen).fetchone()[0]
        return render_template(
            "jaarlijksen.html", nummers=nummers[:toon],
            aantallen=AANTALLEN, toon=toon, totaal=len(nummers),
            aantal_lijsten=len(namen), edities=edities,
            markeer=request.args.get("markeer") or "",
        )

    def _gekozen_top():
        """De top uit de keuzelijst, of None voor alles.

        Zelfde spelregels als op het scherm: alleen de vaste keuzes tellen,
        al het andere betekent "alles". Zo kan een gemanipuleerde URL nooit
        iets anders opleveren dan de pagina zelf toont.
        """
        ruw = request.args.get("toon", "")
        if ruw.isdigit() and int(ruw) in AANTALLEN:
            return int(ruw)
        return None

    def _stuur_excel(wb, bestand: str):
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return send_file(
            buffer, as_attachment=True, download_name=bestand,
            mimetype="application/vnd.openxmlformats-officedocument"
                     ".spreadsheetml.sheet")

    def _stuur_pdf(inhoud: bytes, bestand: str):
        return send_file(io.BytesIO(inhoud), as_attachment=True,
                         download_name=bestand, mimetype="application/pdf")

    @app.route("/download/week/<lijst>/<int:jaar>/<int:week>")
    def download_week(lijst: str, jaar: int, week: int):
        """Eén weeklijst als Excel."""
        if lijst not in LIJSTEN or is_jaarlijks(lijst):
            abort(404)
        wb = excel.bouw_week_werkboek(verbinding(), lijst, jaar, week)
        if wb is None:
            abort(404)
        naam = LIJSTEN[lijst]["bestand"]
        return _stuur_excel(wb, f"{naam}_{jaar}_Week{week:02d}.xlsx")

    @app.route("/download/pdf/week/<lijst>/<int:jaar>/<int:week>")
    def download_week_pdf(lijst: str, jaar: int, week: int):
        """Eén weeklijst als PDF."""
        if lijst not in LIJSTEN or is_jaarlijks(lijst):
            abort(404)
        from .. import pdf as pdfbouwer
        inhoud = pdfbouwer.bouw_weeklijst(verbinding(), lijst, jaar, week)
        if inhoud is None:
            abort(404)
        naam = LIJSTEN[lijst]["bestand"]
        return _stuur_pdf(inhoud, f"{naam}_{jaar}_Week{week:02d}.pdf")

    @app.route("/download/jaarlijksen")
    def download_jaarlijksen():
        """De gecombineerde jaarlijst als Excel, alle nummers."""
        top = _gekozen_top()
        wb = excel.bouw_jaarlijksen_werkboek(verbinding(), top=top)
        if wb is None:
            flash("Er staat nog niets in de database.", "fout")
            return redirect(url_for("jaarlijksen_lijst"))
        naam = f"JaarlijstenTotaal_top{top}" if top else "JaarlijstenTotaal"
        return _stuur_excel(wb, f"{naam}.xlsx")

    @app.route("/download/pdf/jaarlijksen")
    def download_jaarlijksen_pdf():
        """De gecombineerde jaarlijst als PDF, alle nummers."""
        from .. import pdf as pdfbouwer
        top = _gekozen_top()
        inhoud = pdfbouwer.bouw_jaarlijksen(verbinding(), top=top)
        if inhoud is None:
            flash("Er staat nog niets in de database.", "fout")
            return redirect(url_for("jaarlijksen_lijst"))
        naam = f"JaarlijstenTotaal_top{top}" if top else "JaarlijstenTotaal"
        return _stuur_pdf(inhoud, f"{naam}.pdf")

    @app.route("/download/pdf/decennium/<int:decennium>")
    def download_decennium_pdf(decennium: int):
        """Het decenniumklassement als PDF."""
        from .. import pdf as pdfbouwer
        inhoud = pdfbouwer.bouw_klassement(
            verbinding(), DECENNIUM_LIJST, decennium, decennium + 9)
        if inhoud is None:
            flash(f"Voor de {decennium}'s staat er niets in de database.",
                  "fout")
            return redirect(url_for("decennium_overzicht"))
        naam = LIJSTEN[DECENNIUM_LIJST]["bestand"]
        return _stuur_pdf(
            inhoud, f"{naam}_Decennium_{decennium}-{decennium + 9}.pdf")

    @app.route("/download/pdf/totaal")
    def download_totaal_pdf():
        """Het totaalklassement over alle jaargangen als PDF."""
        from .. import pdf as pdfbouwer
        con = verbinding()
        van, tot = db.alle_jaren(con, DECENNIUM_LIJST)
        top = _gekozen_top()
        inhoud = pdfbouwer.bouw_klassement(con, DECENNIUM_LIJST, van, tot,
                                           top=top)
        if inhoud is None:
            flash("Er staat nog niets in de database.", "fout")
            return redirect(url_for("totaal_lijst"))
        naam = LIJSTEN[DECENNIUM_LIJST]["bestand"]
        staart = f"_top{top}" if top else ""
        return _stuur_pdf(inhoud, f"{naam}_Totaal_{van}-{tot}{staart}.pdf")

    @app.route("/download/totaal")
    def download_totaal():
        """De volledige lijst als Excel -- daar past hij wél in zijn geheel in."""
        con = verbinding()
        van, tot = db.alle_jaren(con, DECENNIUM_LIJST)
        top = _gekozen_top()
        wb = excel.bouw_totalen_werkboek(con, DECENNIUM_LIJST, van, tot,
                                         top=top)
        if wb is None:
            flash("Er staat nog niets in de database.", "fout")
            return redirect(url_for("totaal_lijst"))
        naam = LIJSTEN[DECENNIUM_LIJST]["bestand"]
        staart = f"_top{top}" if top else ""
        bestand = f"{naam}_Totaal_{van}-{tot}{staart}.xlsx"
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return send_file(
            buffer, as_attachment=True, download_name=bestand,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # --- wetenswaardigheden ------------------------------------------------

    # Per lijst een eigen ingang: elf lijsten x drie regels is niets, en zo
    # hoeft er niet opnieuw geteld te worden als je heen en weer klikt.
    _weetjes_cache: dict[str, dict] = {}

    @app.route("/wetenswaardigheden")
    def wetenswaardigheden():
        """Tien ranglijsten over de hele historie van een lijst.

        Kost een seconde over 127.000 noteringen, dus gecached tot er nieuwe
        data bij komt -- net als de totaallijst.

        Elke lijst kan hier doorheen, ook de jaarlijkse: een editie ligt als
        een punt op dezelfde kalender. Alleen de woorden verschillen, en die
        kiest `wetenswaardigheden.py` zelf.
        """
        from .. import wetenswaardigheden as weetjes

        lijst = request.args.get("lijst") or DECENNIUM_LIJST
        if lijst not in LIJSTEN:
            lijst = DECENNIUM_LIJST
        con = verbinding()
        # Met het NL-filter rekenen de ranglijsten zichzelf uit over alleen
        # de Nederlandstalige nummers -- knippen in een bestaand klassement
        # zou gaten in de volgorde slaan.
        alleen = _nl_sleutels() if request.args.get("nl") else None
        stempel = tuple(con.execute(
            "SELECT COUNT(*), MAX(opgehaald_op) FROM noteringen"
            " JOIN opgehaald USING (lijst, jaar, week) WHERE lijst=?",
            (lijst,),
        ).fetchone()) + (len(alleen or ()),)
        kaart = _weetjes_cache.setdefault((lijst, alleen is not None), {})
        if kaart.get("stempel") != stempel:
            kaart["stempel"] = stempel
            kaart["blokken"] = weetjes.verzamel(con, lijst, alleen)
            kaart["cijfers"] = weetjes.cijfers(con, lijst, alleen)
        return render_template(
            "wetenswaardigheden.html", lijst=lijst,
            blokken=kaart["blokken"], cijfers=kaart["cijfers"],
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
    def zoek():
        term = (request.args.get("term") or "").strip()
        lijst = request.args.get("lijst") or ""
        waar = request.args.get("waar") or "beide"
        if waar not in ("beide", "artiest", "titel"):
            waar = "beide"
        resultaten = []
        # "abba | fernando" zoekt op artiest EN titel tegelijk. De pipe is
        # geen willekeurige keuze: intern is de sleutel al artiest|titel, dus
        # wie een sleutel plakt uit het beheergedeelte zoekt meteen goed.
        artiest_deel = titel_deel = None
        if "|" in term:
            links, _, rechts = term.partition("|")
            artiest_deel, titel_deel = links.strip(), rechts.strip()
            if not (artiest_deel and titel_deel):
                # Een kant leeg ("abba |") is geen EN-zoekopdracht; zoek dan
                # gewoon op wat er wel staat.
                term = artiest_deel or titel_deel
                artiest_deel = titel_deel = None
        if artiest_deel and titel_deel:
            vraag = (
                "SELECT sleutel, lijst, MAX(titel) titel, MAX(artiest) artiest,"
                " MIN(jaar) van, MAX(jaar) tot, COUNT(*) weken, MIN(positie) hoogste,"
                " (SELECT x.jaar FROM noteringen x WHERE x.sleutel=n.sleutel"
                "  AND x.lijst=n.lijst ORDER BY x.positie, x.jaar LIMIT 1) piekjaar"
                " FROM noteringen n WHERE artiest LIKE ? ESCAPE '\\'"
                " AND titel LIKE ? ESCAPE '\\'"
            )
            waarden = [zoekpatroon(artiest_deel), zoekpatroon(titel_deel)]
            if lijst in LIJSTEN:
                vraag += " AND lijst=?"
                waarden.append(lijst)
            vraag += " GROUP BY sleutel, lijst ORDER BY weken DESC LIMIT 200"
            resultaten = list(verbinding().execute(vraag, waarden))
        elif term:
            patroon = zoekpatroon(term)
            # `piekjaar` is de jaargang waarin het nummer zijn hoogste plek
            # haalde, en bij gelijke hoogte de eerste. Daar springt de link
            # naartoe: dat is de jaargang die naast het resultaat staat, dus je
            # komt uit waar je op klikte.
            vraag = (
                "SELECT sleutel, lijst, MAX(titel) titel, MAX(artiest) artiest,"
                " MIN(jaar) van, MAX(jaar) tot, COUNT(*) weken, MIN(positie) hoogste,"
                " (SELECT x.jaar FROM noteringen x WHERE x.sleutel=n.sleutel"
                "  AND x.lijst=n.lijst ORDER BY x.positie, x.jaar LIMIT 1) piekjaar"
                " FROM noteringen n WHERE "
            )
            # ESCAPE erbij, anders blijft een ingetypt procentteken een joker.
            if waar == "artiest":
                vraag += "artiest LIKE ? ESCAPE '\\'"
                waarden = [patroon]
            elif waar == "titel":
                vraag += "titel LIKE ? ESCAPE '\\'"
                waarden = [patroon]
            else:
                vraag += ("(titel LIKE ? ESCAPE '\\'"
                          " OR artiest LIKE ? ESCAPE '\\')")
                waarden = [patroon, patroon]
            if lijst in LIJSTEN:
                vraag += " AND lijst=?"
                waarden.append(lijst)
            vraag += " GROUP BY sleutel, lijst ORDER BY weken DESC LIMIT 200"
            resultaten = list(verbinding().execute(vraag, waarden))
        # Wie "abba fernando" intypt bedoelt meestal artiest en titel, maar
        # dat matcht geen van beide kolommen. Bij nul treffers en meerdere
        # woorden stellen we de pipe-varianten voor, klikbaar: elke plek
        # tussen twee woorden kan de grens zijn.
        suggesties = []
        woorden = term.split()
        if term and not resultaten and "|" not in term and len(woorden) > 1:
            suggesties = [
                " ".join(woorden[:i]) + " | " + " ".join(woorden[i:])
                for i in range(1, len(woorden))
            ]
        return render_template("zoek.html", term=term, lijst=lijst, waar=waar,
                               resultaten=_alleen_nl(resultaten),
                               suggesties=suggesties)

    @app.route("/nummer/<path:sleutel>")
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
        van = _als_sleutel(request.form.get("van"))
        naar = _als_sleutel(request.form.get("naar"))
        opmerking = (request.form.get("opmerking") or "").strip()
        oude_van = _als_sleutel(request.form.get("oude_van"))

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
            flash(f"Alias bewaard als {van} -> {naar}. Draai 'Sleutels "
                  f"herberekenen' om hem te laten gelden.", "goed")
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
        from .. import momentopnames

        jaren = [r[0] for r in verbinding().execute(
            "SELECT DISTINCT jaar FROM noteringen ORDER BY jaar DESC")]
        opnames = [(p.name, p.stat().st_size / 1024 / 1024)
                   for p in momentopnames.lijst()]
        wacht = db.te_bouwen(verbinding())
        openstaand = ", ".join(
            f"{lijst_naam} {jaar}" for lijst_naam, jaar in wacht[:12])
        if len(wacht) > 12:
            openstaand += f" en nog {len(wacht) - 12}"
        return render_template("beheer.html", jaren=jaren, taak=taken.huidige(),
                               opnames=opnames, openstaand=openstaand)

    @app.route("/beheer/start", methods=["POST"])
    @vereist_aanmelding
    def beheer_start():
        wat = request.form.get("wat")
        jaar = request.form.get("jaar")
        bestand = request.form.get("bestand")
        from .werk import bouw_werk

        naam, werk = bouw_werk(wat, jaar, bestand)
        if werk is None:
            flash(naam, "fout")
        else:
            gestart, melding = taken.start(naam, werk)
            flash(melding, "goed" if gestart else "fout")
        return redirect(url_for("beheer"))

    @app.route("/taak/opruimen", methods=["POST"])
    @vereist_aanmelding
    def taak_opruimen():
        """Een afgeronde of afgebroken taak van de pagina halen.

        Alleen als hij niet meer loopt: een lopende taak wegklikken zou
        suggereren dat het werk weg is terwijl het gewoon doorgaat.
        """
        t = taken.huidige()
        if t is not None and not t.klaar:
            flash("Er loopt nog iets; dat kan niet worden opgeruimd", "fout")
        else:
            verbinding().execute("DELETE FROM taak WHERE id=1")
            verbinding().commit()
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
            "stap": t.stap, "stappen": t.stappen, "stap_naam": t.stap_naam,
            "deel": t.deel, "deel_van": t.deel_van,
        }
