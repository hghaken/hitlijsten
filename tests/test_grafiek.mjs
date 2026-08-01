/* Toets de grafiek van de positie per week uit templates/jaar.html.
 *
 *     node tests\test_grafiek.mjs
 *
 * De grafiek draait in de browser, dus staat hier een DOM-stub die precies
 * genoeg kan voor dat ene script: een tabel met een kop en rijen, elementen die
 * je kenmerken kunt geven, en een dialoogvenster. Dat is geen browser en
 * bewijst dus niets over de opmaak -- wel over de rekenkant, en daar zitten de
 * fouten: de schaal, het verschil met de vorige week, en wat er gebeurt met een
 * week waarin een nummer niet noteerde.
 *
 * Het script wordt uit de template geknipt in plaats van gekopieerd, zodat deze
 * test niet stilletjes een oude versie blijft goedkeuren.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const HIER = dirname(fileURLToPath(import.meta.url));
const TEMPLATE = join(HIER, "..", "hitlijsten", "web", "templates", "jaar.html");

// Uit de template geknipt: het laatste <script>-blok is de grafiek.
function grafiekscript() {
  const bron = readFileSync(TEMPLATE, "utf8");
  const blokken = [...bron.matchAll(/<script>([\s\S]*?)<\/script>/g)];
  if (!blokken.length) throw new Error("geen <script> in jaar.html gevonden");
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
  getAttribute(sleutel) { return this.kenmerken[sleutel] ?? null; }
  appendChild(kind) { kind.ouder = this; this.kinderen.push(kind); return kind; }
  replaceChildren(...kinderen) {
    this.kinderen = [];
    kinderen.forEach((k) => this.appendChild(k));
  }
  addEventListener(soort, afhandelaar) {
    (this.luisteraars ??= {})[soort] = afhandelaar;
  }
  get parentElement() { return this.ouder; }
  get textContent() { return this._tekst; }
  set textContent(waarde) { this._tekst = String(waarde); }
  get klasse() { return this.kenmerken.class || ""; }
  // Alleen wat het script vraagt: closest("td.klikbaar") op een cel.
  closest(kies) { return kies === "td.klikbaar" && this.klikbaar ? this : null; }
}

function cel(tekst, klikbaar = false) {
  const c = new Knoop("td");
  c.textContent = tekst;
  c.klikbaar = klikbaar;
  return c;
}

/** Een matrix zoals de template hem rendert: kopcel + een kolom per week. */
function maakMatrix(weken, nummers) {
  const kop = new Knoop("tr");
  kop.cells = [cel("Artiest — titel"), ...weken.map((w) => cel(String(w)))];

  const rijen = nummers.map(function (n) {
    const r = new Knoop("tr");
    r.dataset = {
      sleutel: n.sleutel, artiest: n.artiest, titel: n.titel,
      punten: String(n.punten ?? 0),
      hoogste: String(Math.min(...n.posities.filter((p) => p !== null))),
      weken: String(n.posities.filter((p) => p !== null).length),
      eerste: n.eerste ?? "", laatste: n.laatste ?? "",
      eerder: n.eerder ? "1" : "0", door: n.door ? "1" : "0",
    };
    const label = cel(n.artiest + " — " + n.titel, true);
    label.ouder = r;
    r.cells = [label, ...n.posities.map((p) => cel(p === null ? "" : String(p)))];
    r.cells.forEach((c) => (c.ouder = r));
    return r;
  });

  const tabel = new Knoop("table");
  tabel.tHead = { rows: [kop] };
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
    ".samenvatting": new Knoop("div"), ".plaat": new Knoop("div"),
    ".sluit": new Knoop("button"),
  };
  d.querySelector = (kies) => vakken[kies];
  d.vakken = vakken;
  return d;
}

/** Draai het script tegen deze matrix en geef een klik-functie terug. */
function draai(tabel, dialoog) {
  const document = {
    getElementById: (id) => (id === "matrix" ? tabel : id === "grafiek" ? dialoog : null),
    querySelectorAll: (kies) => (kies === ".tabelvak table" ? [tabel] : []),
    createElementNS: (_ruimte, naam) => new Knoop(naam),
  };
  vm.runInNewContext(grafiekscript(), { document });
  return function klik(rij) {
    tabel.luisteraars.click({ target: rij.cells[0] });
  };
}

/** Alle tekstelementen van de svg, per klasse gegroepeerd. */
function teksten(svg, klasse) {
  return svg.kinderen
    .filter((k) => k.naam === "text" && (k.kenmerken.class || "").split(" ").includes(klasse))
    .map((k) => k.textContent);
}

// --- tests ------------------------------------------------------------------

const tests = {};

tests.normale_reeks_krijgt_week_positie_en_verschil = () => {
  const tabel = maakMatrix([1, 2, 3, 4, 5, 6], [{
    sleutel: "a|b", artiest: "A", titel: "B", punten: 100,
    posities: [30, 20, 10, 5, 8, 15],
  }]);
  const dialoog = maakDialoog();
  draai(tabel, dialoog)(tabel.tBodies[0].rows[0]);

  const svg = dialoog.vakken[".plaat"].kinderen[0];
  gelijk(teksten(svg, "week"), ["1", "2", "3", "4", "5", "6"]);
  gelijk(teksten(svg, "positie"), ["30", "20", "10", "5", "8", "15"]);
  // Een LAGERE positie is beter, dus vorige - huidige: positief = geklommen.
  gelijk(teksten(svg, "verschil"), ["N", "+10", "+10", "+5", "-3", "-7"]);
  waar(dialoog.open, "venster hoort open te staan");
  gelijk(dialoog.vakken[".artiest"].textContent, "A");
};

tests.lege_weken_ervoor_en_erna_vallen_weg = () => {
  const tabel = maakMatrix([1, 2, 3, 4, 5, 6], [{
    sleutel: "a|b", artiest: "A", titel: "B",
    posities: [null, null, 12, 9, null, null],
  }]);
  const dialoog = maakDialoog();
  draai(tabel, dialoog)(tabel.tBodies[0].rows[0]);
  const svg = dialoog.vakken[".plaat"].kinderen[0];
  gelijk(teksten(svg, "week"), ["3", "4"]);
  gelijk(teksten(svg, "positie"), ["12", "9"]);
};

tests.gat_in_de_reeks_wordt_gestippeld_overbrugd = () => {
  const tabel = maakMatrix([1, 2, 3, 4], [{
    sleutel: "a|b", artiest: "A", titel: "B",
    posities: [10, null, null, 25],
  }]);
  const dialoog = maakDialoog();
  draai(tabel, dialoog)(tabel.tBodies[0].rows[0]);
  const svg = dialoog.vakken[".plaat"].kinderen[0];

  const sporen = svg.kinderen.filter((k) => k.naam === "path");
  gelijk(sporen.length, 1, "alleen de overbrugging, geen doorgetrokken lijn");
  waar(sporen[0].kenmerken.class.includes("onderbroken"), "moet gestippeld zijn");
  // De lege weken houden hun kolom, zodat de afstand klopt met de tijd.
  gelijk(teksten(svg, "week"), ["1", "2", "3", "4"]);
  gelijk(teksten(svg, "positie"), ["10", "25"]);
  // Het verschil kijkt naar de vorige week WAARIN het nummer noteerde.
  gelijk(teksten(svg, "verschil"), ["N", "-15"]);
};

tests.schaal_loopt_van_1_tot_de_langste_lijst = () => {
  // Twee nummers: het tweede haalt positie 40, dus de schaal loopt tot 40 --
  // ook in de grafiek van het eerste nummer, dat niet verder komt dan 3.
  const tabel = maakMatrix([1, 2], [
    { sleutel: "a|b", artiest: "A", titel: "B", posities: [1, 3] },
    { sleutel: "c|d", artiest: "C", titel: "D", posities: [40, 20] },
  ]);
  const dialoog = maakDialoog();
  draai(tabel, dialoog)(tabel.tBodies[0].rows[0]);
  const svg = dialoog.vakken[".plaat"].kinderen[0];

  const aslabels = teksten(svg, "as");
  gelijk(aslabels, ["1", "40"], "hulplijnen op 1 en op de lijstlengte");

  const punten = svg.kinderen.filter((k) => k.naam === "circle");
  const y1 = Number(punten[0].kenmerken.cy);
  const y3 = Number(punten[1].kenmerken.cy);
  waar(y1 < y3, "positie 1 hoort boven positie 3 te staan");
  // Positie 1 valt op de bovenste hulplijn.
  const bovenlijn = svg.kinderen.find((k) => k.naam === "line");
  gelijk(Number(bovenlijn.kenmerken.y1), y1, "positie 1 ligt op de bovenste lijn");
};

tests.hoogste_notering_wordt_uitgelicht = () => {
  const tabel = maakMatrix([1, 2, 3], [{
    sleutel: "a|b", artiest: "A", titel: "B", posities: [7, 2, 5],
  }]);
  const dialoog = maakDialoog();
  draai(tabel, dialoog)(tabel.tBodies[0].rows[0]);
  const svg = dialoog.vakken[".plaat"].kinderen[0];
  const beste = svg.kinderen.filter(
    (k) => k.naam === "circle" && k.kenmerken.class.includes("beste"));
  gelijk(beste.length, 1);
  const cijfers = svg.kinderen.filter(
    (k) => k.naam === "text" && k.kenmerken.class === "positie beste");
  gelijk(cijfers.map((k) => k.textContent), ["2"]);
};

tests.samenvatting_toont_de_jaargrensmarkering = () => {
  const tabel = maakMatrix([1, 2], [{
    sleutel: "a|b", artiest: "A", titel: "B", punten: 55,
    posities: [4, 6], eerste: "06/12/1974", laatste: "10/01/1975",
    eerder: true, door: false,
  }]);
  const dialoog = maakDialoog();
  draai(tabel, dialoog)(tabel.tBodies[0].rows[0]);
  const tekst = dialoog.vakken[".samenvatting"].textContent;
  waar(tekst.includes("Hoogste positie 4"), tekst);
  waar(tekst.includes("55 punten"), tekst);
  waar(tekst.includes("◀ 06/12/1974 t/m 10/01/1975"), tekst);
};

tests.gelijke_positie_geeft_geen_plus_of_min = () => {
  const tabel = maakMatrix([1, 2], [{
    sleutel: "a|b", artiest: "A", titel: "B", posities: [9, 9],
  }]);
  const dialoog = maakDialoog();
  draai(tabel, dialoog)(tabel.tBodies[0].rows[0]);
  const svg = dialoog.vakken[".plaat"].kinderen[0];
  gelijk(teksten(svg, "verschil"), ["N", "0"]);
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
    test();
    console.log("ok       " + naam);
  } catch (fout) {
    mislukt++;
    console.log("MISLUKT  " + naam + ": " + fout.message);
  }
}
const totaal = Object.keys(tests).length;
console.log(`\n${totaal - mislukt}/${totaal} geslaagd`);
process.exit(mislukt ? 1 : 0);
