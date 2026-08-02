/* Toets de grafiek uit templates/_grafiek.html.
 *
 *     node tests/test_grafiek.mjs        (node staat niet op de NAS)
 *
 * De grafiek draait in de browser, dus staat hier een DOM-stub die precies
 * genoeg kan voor dat ene script: een tabel met rijen, elementen die je
 * kenmerken kunt geven, een dialoogvenster en een fetch die de reeks teruggeeft
 * zoals /reeks dat doet. Dat is geen browser en bewijst dus niets over de
 * opmaak -- wel over de rekenkant, en daar zitten de fouten: de schaal, het
 * verschil met de vorige week, de gaten, en de streep bij de jaarwisseling.
 *
 * Het script wordt uit de template geknipt in plaats van gekopieerd, zodat deze
 * test niet stilletjes een oude versie blijft goedkeuren. Wat de server
 * aanlevert wordt aan de Python-kant getoetst (test_datums.py, reeks_van).
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const HIER = dirname(fileURLToPath(import.meta.url));
const TEMPLATE = join(HIER, "..", "hitlijsten", "web", "templates", "_grafiek.html");

function grafiekscript() {
  const bron = readFileSync(TEMPLATE, "utf8");
  const blokken = [...bron.matchAll(/<script>([\s\S]*?)<\/script>/g)];
  if (!blokken.length) throw new Error("geen <script> in _grafiek.html gevonden");
  return blokken[blokken.length - 1][1];
}

// --- DOM-stub ---------------------------------------------------------------

class Knoop {
  constructor(naam) {
    this.naam = naam;
    this.kinderen = [];
    this.kenmerken = {};
    this.dataset = {};
    this.ouder = null;
    this._tekst = "";
  }
  setAttribute(sleutel, waarde) { this.kenmerken[sleutel] = String(waarde); }
  appendChild(kind) { kind.ouder = this; this.kinderen.push(kind); return kind; }
  replaceChildren(...kinderen) {
    this.kinderen = [];
    kinderen.forEach((k) => this.appendChild(k));
  }
  addEventListener(soort, afhandelaar) {
    (this.luisteraars ??= {})[soort] = afhandelaar;
  }
  get parentElement() { return this.ouder; }
  get classList() {
    const klassen = (this.klassen ??= new Set());
    return { add: (k) => klassen.add(k), has: (k) => klassen.has(k) };
  }
  scrollIntoView() { this.inBeeld = true; }
  get textContent() { return this._tekst; }
  set textContent(waarde) { this._tekst = String(waarde); }
  // Alleen wat het script vraagt: closest("td.klikbaar") op een cel.
  closest(kies) { return kies === "td.klikbaar" && this.klikbaar ? this : null; }
}

/** De rijen van de matrix; de posities komen tegenwoordig van de server. */
function maakMatrix(nummers, lijst = "top40", jaar = "2023", markeer = "") {
  const rijen = nummers.map(function (n) {
    const r = new Knoop("tr");
    r.dataset = {
      sleutel: n.sleutel, artiest: n.artiest, titel: n.titel,
      punten: String(n.punten ?? 0), weken: String(n.weken ?? 0),
    };
    const label = new Knoop("td");
    label.textContent = n.artiest + " — " + n.titel;
    label.klikbaar = true;
    label.ouder = r;
    r.cells = [label];
    return r;
  });
  const tabel = new Knoop("table");
  tabel.id = "matrix";
  tabel.dataset = { lijst: lijst, jaar: jaar, markeer: markeer };
  tabel.tBodies = [{ rows: rijen }];
  tabel.contains = (k) => rijen.includes(k.ouder);
  return tabel;
}

function maakDialoog() {
  const d = new Knoop("dialog");
  d.showModal = () => { d.open = true; };
  d.close = () => { d.open = false; };
  const vakken = {
    ".artiest": new Knoop("div"), ".titel": new Knoop("div"),
    ".samenvatting": new Knoop("div"), ".jaardeel": new Knoop("div"),
    ".plaat": new Knoop("div"), ".sluit": new Knoop("button"),
  };
  d.querySelector = (kies) => vakken[kies];
  d.vakken = vakken;
  return d;
}

/** Wat /reeks teruggeeft, opgebouwd uit een lijstje posities. */
function antwoord(posities, { jaar = 2023, eersteWeek = 1, lengte = 40 } = {}) {
  const reeks = posities.map(function (p, i) {
    const week = eersteWeek + i;
    return { jaar: jaar, week: week, positie: p, datum: "" };
  });
  const genoteerd = posities.filter((p) => p !== null);
  return {
    as: "week",
    reeks: reeks, lengte: lengte, hoogste: Math.min(...genoteerd),
    weken: genoteerd.length, punten: 0, van: "01/01", tot: "31/12",
  };
}

/** Draai het script en geef een functie terug die klikt en het venster afmaakt. */
function draai(tabel, dialoog, payload) {
  let gevraagd = null;
  const context = {
    document: {
      getElementById: (id) =>
        (id === tabel.id ? tabel : id === "grafiek" ? dialoog : null),
      querySelectorAll: function (kies) {
        if (kies === ".tabelvak table") return [tabel];
        if (kies === ".tabelvak table tr[data-sleutel]") return tabel.tBodies[0].rows;
        return [];
      },
      createElementNS: (_ruimte, naam) => new Knoop(naam),
    },
    fetch: function (adres) {
      gevraagd = adres;
      return Promise.resolve({ ok: payload !== null, json: () => Promise.resolve(payload) });
    },
  };
  vm.runInNewContext(grafiekscript(), context);
  return {
    klik: async function (rij) {
      tabel.luisteraars.click({ target: rij.cells[0] });
      // De afhandelaar gooit de belofte weg, dus even de microtaken laten lopen.
      await new Promise((r) => setTimeout(r, 0));
      await new Promise((r) => setTimeout(r, 0));
    },
    adres: () => gevraagd,
  };
}

function svgVan(dialoog) { return dialoog.vakken[".plaat"].kinderen[0]; }

function teksten(svg, klasse) {
  return svg.kinderen
    .filter((k) => k.naam === "text" && (k.kenmerken.class || "").split(" ").includes(klasse))
    .map((k) => k.textContent);
}

/** Eén nummer aanklikken en de svg teruggeven. */
async function grafiek(payload, nummer = {}) {
  const tabel = maakMatrix([{
    sleutel: "a|b", artiest: "A", titel: "B", ...nummer,
  }], "top40", String(nummer.jaar ?? 2023));
  const dialoog = maakDialoog();
  const loop = draai(tabel, dialoog, payload);
  await loop.klik(tabel.tBodies[0].rows[0]);
  return { svg: svgVan(dialoog), dialoog: dialoog, adres: loop.adres() };
}

// --- tests ------------------------------------------------------------------

const tests = {};

tests.normale_reeks_krijgt_week_positie_en_verschil = async () => {
  const { svg, dialoog } = await grafiek(antwoord([30, 20, 10, 5, 8, 15]));
  gelijk(teksten(svg, "week"), ["1", "2", "3", "4", "5", "6"]);
  gelijk(teksten(svg, "positie"), ["30", "20", "10", "5", "8", "15"]);
  // Een LAGERE positie is beter, dus vorige - huidige: positief = geklommen.
  gelijk(teksten(svg, "verschil"), ["N", "+10", "+10", "+5", "-3", "-7"]);
  waar(dialoog.open, "venster hoort open te staan");
  gelijk(dialoog.vakken[".artiest"].textContent, "A");
};

tests.sleutel_lijst_en_jaar_gaan_mee_in_het_verzoek = async () => {
  const { adres } = await grafiek(antwoord([1]), { sleutel: "queen|killer queen" });
  waar(adres.startsWith("/reeks?"), adres);
  waar(adres.includes("lijst=top40"), adres);
  waar(adres.includes("jaar=2023"), adres);
  waar(adres.includes("sleutel=queen%7Ckiller%20queen"), adres);
};

tests.gat_in_de_reeks_wordt_gestippeld_overbrugd = async () => {
  const { svg } = await grafiek(antwoord([10, null, null, 25]));
  const sporen = svg.kinderen.filter((k) => k.naam === "path");
  gelijk(sporen.length, 1, "alleen de overbrugging, geen doorgetrokken lijn");
  waar(sporen[0].kenmerken.class.includes("onderbroken"), "moet gestippeld zijn");
  // De lege weken houden hun kolom, zodat de afstand klopt met de tijd.
  gelijk(teksten(svg, "week"), ["1", "2", "3", "4"]);
  gelijk(teksten(svg, "positie"), ["10", "25"]);
  // Het verschil kijkt naar de vorige week WAARIN het nummer noteerde.
  gelijk(teksten(svg, "verschil"), ["N", "-15"]);
};

tests.schaal_komt_van_de_server_niet_uit_het_nummer = async () => {
  // Het nummer komt niet verder dan 3, maar de lijst is 40 lang. Anders lijkt
  // een nummer dat tussen 1 en 3 schommelde net zo grillig als een dat zakte.
  const { svg } = await grafiek(antwoord([1, 3], { lengte: 40 }));
  gelijk(teksten(svg, "as"), ["1", "40"], "hulplijnen op 1 en op de lijstlengte");

  const punten = svg.kinderen.filter((k) => k.naam === "circle");
  const y1 = Number(punten[0].kenmerken.cy), y3 = Number(punten[1].kenmerken.cy);
  waar(y1 < y3, "positie 1 hoort boven positie 3 te staan");
  const bovenlijn = svg.kinderen.find((k) => k.naam === "line");
  gelijk(Number(bovenlijn.kenmerken.y1), y1, "positie 1 ligt op de bovenste lijn");
};

tests.hoogste_notering_wordt_uitgelicht = async () => {
  const { svg } = await grafiek(antwoord([7, 2, 5]));
  const beste = svg.kinderen.filter(
    (k) => k.naam === "circle" && k.kenmerken.class.includes("beste"));
  gelijk(beste.length, 1);
  const cijfers = svg.kinderen.filter(
    (k) => k.naam === "text" && k.kenmerken.class === "positie beste");
  gelijk(cijfers.map((k) => k.textContent), ["2"]);
};

tests.gelijke_positie_geeft_geen_plus_of_min = async () => {
  const { svg } = await grafiek(antwoord([9, 9]));
  gelijk(teksten(svg, "verschil"), ["N", "0"]);
};

// --- over de jaarwisseling --------------------------------------------------

tests.jaarwisseling_krijgt_een_streep_en_twee_jaartallen = async () => {
  // Week 51 en 52 van 2022, dan week 1 en 2 van 2023.
  const payload = antwoord([13, 5, 3, 2]);
  payload.reeks = [
    { jaar: 2022, week: 51, positie: 13, datum: "" },
    { jaar: 2022, week: 52, positie: 5, datum: "" },
    { jaar: 2023, week: 1, positie: 3, datum: "" },
    { jaar: 2023, week: 2, positie: 2, datum: "" },
  ];
  const { svg } = await grafiek(payload);

  gelijk(teksten(svg, "jaar"), ["2022", "2023"]);
  const grenzen = svg.kinderen.filter(
    (k) => k.naam === "line" && k.kenmerken.class === "jaargrens");
  gelijk(grenzen.length, 1, "één streep tussen de twee jaargangen");

  // De streep hoort tussen de laatste kolom van 2022 en de eerste van 2023.
  const punten = svg.kinderen.filter((k) => k.naam === "circle");
  const grens = Number(grenzen[0].kenmerken.x1);
  waar(grens > Number(punten[1].kenmerken.cx), "streep hoort na week 52");
  waar(grens < Number(punten[2].kenmerken.cx), "streep hoort voor week 1");

  // De weken lopen gewoon door; het verschil telt over de jaarwisseling heen.
  gelijk(teksten(svg, "week"), ["51", "52", "1", "2"]);
  gelijk(teksten(svg, "verschil"), ["N", "+8", "+2", "+1"]);
};

tests.binnen_een_jaar_geen_streep_maar_wel_het_jaartal = async () => {
  const { svg } = await grafiek(antwoord([4, 6]));
  gelijk(teksten(svg, "jaar"), ["2023"]);
  gelijk(svg.kinderen.filter(
    (k) => k.naam === "line" && k.kenmerken.class === "jaargrens").length, 0);
};

tests.jaardeel_verschijnt_alleen_bij_een_reeks_over_de_grens = async () => {
  const payload = antwoord([13, 5]);
  payload.reeks = [
    { jaar: 2022, week: 52, positie: 13, datum: "" },
    { jaar: 2023, week: 1, positie: 5, datum: "" },
  ];
  payload.weken = 2; payload.punten = 1000; payload.hoogste = 5;
  payload.van = "30/12/2022"; payload.tot = "06/01/2023";
  const over = await grafiek(payload, { weken: 1, punten: 36 });
  waar(over.dialoog.vakken[".samenvatting"].textContent.includes("1000 punten"),
       over.dialoog.vakken[".samenvatting"].textContent);
  gelijk(over.dialoog.vakken[".jaardeel"].textContent,
         "Waarvan in 2023: 1 weken · 36 punten");

  // Blijft alles binnen het jaar, dan is die regel alleen maar ruis.
  const binnen = await grafiek(antwoord([4, 6]), { weken: 2, punten: 70 });
  gelijk(binnen.dialoog.vakken[".jaardeel"].textContent, "");
};

tests.mislukte_oproep_zegt_dat_eerlijk = async () => {
  const { dialoog } = await grafiek(null);
  gelijk(dialoog.vakken[".samenvatting"].textContent,
         "De reeks kon niet worden opgehaald.");
};

tests.pijltje_licht_het_nummer_op_de_doelpagina_op = async () => {
  const tabel = maakMatrix([
    { sleutel: "a|b", artiest: "A", titel: "B" },
    { sleutel: "c|d", artiest: "C", titel: "D" },
  ], "top40", "2023", "c|d");
  draai(tabel, maakDialoog(), antwoord([1]));
  const [eerste, tweede] = tabel.tBodies[0].rows;
  waar(!eerste.classList.has("opgelicht"), "het andere nummer blijft ongemoeid");
  waar(tweede.classList.has("opgelicht"), "het gevraagde nummer wordt opgelicht");
  waar(tweede.inBeeld, "en in beeld geschoven");
};

tests.zonder_markeer_wordt_er_niets_opgelicht = async () => {
  const tabel = maakMatrix([{ sleutel: "a|b", artiest: "A", titel: "B" }]);
  draai(tabel, maakDialoog(), antwoord([1]));
  waar(!tabel.tBodies[0].rows[0].classList.has("opgelicht"), "niets opgelicht");
};

// --- de editie-as (Top 2000) ------------------------------------------------

tests.editie_as_zet_het_jaartal_onder_elk_punt = async () => {
  const payload = {
    as: "editie", lengte: 2000, hoogste: 1, weken: 3, punten: 0,
    van: "2023", tot: "2025",
    reeks: [{ jaar: 2023, week: null, positie: 4, datum: "2023" },
            { jaar: 2024, week: null, positie: 2, datum: "2024" },
            { jaar: 2025, week: null, positie: 1, datum: "2025" }],
  };
  const { svg, dialoog } = await grafiek(payload);
  // Het label onder de punt is het jaartal, niet een weeknummer.
  gelijk(teksten(svg, "week"), ["2023", "2024", "2025"]);
  gelijk(teksten(svg, "positie"), ["4", "2", "1"]);
  gelijk(teksten(svg, "verschil"), ["N", "+2", "+1"]);
  // Geen jaargangstrepen: elk punt is al een eigen jaar.
  gelijk(svg.kinderen.filter(
    (k) => k.naam === "line" && k.kenmerken.class === "jaargrens").length, 0);
  gelijk(teksten(svg, "jaar"), []);
  waar(dialoog.vakken[".samenvatting"].textContent.includes("3 edities"),
       dialoog.vakken[".samenvatting"].textContent);
};

tests.editie_as_toont_geen_waarvan_in_dit_jaar = async () => {
  const payload = {
    as: "editie", lengte: 2000, hoogste: 1, weken: 2, punten: 0,
    van: "2024", tot: "2025",
    reeks: [{ jaar: 2024, week: null, positie: 3, datum: "2024" },
            { jaar: 2025, week: null, positie: 1, datum: "2025" }],
  };
  const { dialoog } = await grafiek(payload, { weken: 1, punten: 0 });
  gelijk(dialoog.vakken[".jaardeel"].textContent, "",
         "die regel gaat over een jaargang binnen een weeklijst");
};

tests.gat_tussen_twee_edities_wordt_gestippeld = async () => {
  const payload = {
    as: "editie", lengte: 2000, hoogste: 5, weken: 2, punten: 0,
    van: "2023", tot: "2025",
    reeks: [{ jaar: 2023, week: null, positie: 5, datum: "2023" },
            { jaar: 2024, week: null, positie: null, datum: "2024" },
            { jaar: 2025, week: null, positie: 9, datum: "2025" }],
  };
  const { svg } = await grafiek(payload);
  const sporen = svg.kinderen.filter((k) => k.naam === "path");
  gelijk(sporen.length, 1);
  waar(sporen[0].kenmerken.class.includes("onderbroken"),
       "een overgeslagen editie hoort gestippeld te zijn");
  gelijk(teksten(svg, "week"), ["2023", "2024", "2025"]);
};

// --- de verticale schaal -----------------------------------------------------

tests.korte_lijst_krijgt_een_lineaire_schaal = async () => {
  // Top 40: elke plek is een stap. Positie 2 hoort vlak onder 1 te staan,
  // niet op een vijfde van de hoogte.
  const { svg } = await grafiek(antwoord([1, 2, 40], { lengte: 40 }));
  gelijk(teksten(svg, "as"), ["1", "40"], "twee hulplijnen: boven en onder");
  const p = svg.kinderen.filter((k) => k.naam === "circle").map((k) => Number(k.kenmerken.cy));
  const hoogte = p[2] - p[0];
  const stap = (p[1] - p[0]) / hoogte;
  waar(stap > 0.02 && stap < 0.04, `positie 2 op ${(stap * 100).toFixed(1)}% is niet lineair`);
};

tests.lange_lijst_schaalt_op_het_bereik_van_het_nummer = async () => {
  // Top 4000, een nummer dat tussen 4 en 252 beweegt. Op een schaal van 1 tot
  // 4000 zou dat een streep bovenin zijn; nu vult het de hele hoogte.
  const { svg } = await grafiek(antwoord([4, 30, 252], { lengte: 4000 }));
  gelijk(teksten(svg, "as"), ["4", "10", "100", "252"],
         "de randen van het bereik, met de machten van tien ertussen");
  const p = svg.kinderen.filter((k) => k.naam === "circle").map((k) => Number(k.kenmerken.cy));
  waar(Math.abs(p[0] - p[2]) > 100,
       `4 en 252 staan maar ${Math.abs(p[0] - p[2]).toFixed(0)} punten uit elkaar`);
  // De beste positie staat bovenaan, de slechtste onderaan.
  waar(p[0] < p[1] && p[1] < p[2], "de volgorde klopt niet");
};

tests.gelijkblijvend_nummer_krijgt_toch_een_bereik = async () => {
  // Elke editie op dezelfde plek: zonder bereik zou er door nul gedeeld worden.
  const { svg } = await grafiek(antwoord([500, 500, 500], { lengte: 4000 }));
  const p = svg.kinderen.filter((k) => k.naam === "circle").map((k) => Number(k.kenmerken.cy));
  waar(p.every((y) => Number.isFinite(y)), "een vlakke reeks levert geen getal op");
  gelijk(new Set(p).size, 1, "drie keer dezelfde positie hoort een rechte lijn te zijn");
};

tests.korte_lijst_blijft_wel_vergelijkbaar = async () => {
  // Bij de weeklijsten hangt de schaal aan de LIJST, niet aan het nummer: een
  // nummer dat tussen 1 en 3 schommelde hoort niet net zo grillig te ogen als
  // een dat van 1 naar 40 zakte. Bij de lange lijsten is dat losgelaten om de
  // hoogte te kunnen gebruiken.
  const een = await grafiek(antwoord([1, 3], { lengte: 40 }));
  const twee = await grafiek(antwoord([1, 40], { lengte: 40 }));
  const y = (r) => Number(r.svg.kinderen.filter((k) => k.naam === "circle")[1].kenmerken.cy);
  waar(y(een) < y(twee), "positie 3 hoort hoger te staan dan positie 40");
  gelijk(teksten(een.svg, "as"), ["1", "40"]);
  gelijk(teksten(twee.svg, "as"), ["1", "40"]);
};

// --- loper ------------------------------------------------------------------

function gelijk(gekregen, verwacht, bericht = "") {
  const a = JSON.stringify(gekregen), b = JSON.stringify(verwacht);
  if (a !== b) throw new Error(`${bericht}\n   gekregen: ${a}\n   verwacht: ${b}`);
}
function waar(voorwaarde, bericht) {
  if (!voorwaarde) throw new Error(bericht);
}

let mislukt = 0;
for (const [naam, test] of Object.entries(tests)) {
  try {
    await test();
    console.log("ok       " + naam);
  } catch (fout) {
    mislukt++;
    console.log("MISLUKT  " + naam + ": " + fout.message);
  }
}
const totaal = Object.keys(tests).length;
console.log(`\n${totaal - mislukt}/${totaal} geslaagd`);
process.exit(mislukt ? 1 : 0);
