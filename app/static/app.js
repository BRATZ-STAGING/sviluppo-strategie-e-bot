/* Grafico XAUUSD: KLineChart 10 + disegni salvati + backtest sopra il grafico. */
"use strict";

// in ordine di durata, come in server.py (M33 e M66 sono del progetto)
const TF = {
  M1: { type: "minute", span: 1 }, M2: { type: "minute", span: 2 },
  M3: { type: "minute", span: 3 }, M5: { type: "minute", span: 5 },
  M6: { type: "minute", span: 6 }, M10: { type: "minute", span: 10 },
  M12: { type: "minute", span: 12 }, M15: { type: "minute", span: 15 },
  M20: { type: "minute", span: 20 }, M30: { type: "minute", span: 30 },
  M33: { type: "minute", span: 33 }, H1: { type: "hour", span: 1 },
  M66: { type: "minute", span: 66 }, H2: { type: "hour", span: 2 },
  H3: { type: "hour", span: 3 }, H4: { type: "hour", span: 4 },
  H6: { type: "hour", span: 6 }, H8: { type: "hour", span: 8 },
  H12: { type: "hour", span: 12 }, D1: { type: "day", span: 1 },
  W1: { type: "week", span: 1 }, MN1: { type: "month", span: 1 },
};
// quelli nella barra in alto; gli altri sono nell'elenco, da cui si aggiungono con la stella
const PREFERITI_BASE = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"];
const GRUPPI_TF = [
  ["Minuti", (k) => TF[k].type === "minute"],
  ["Ore", (k) => TF[k].type === "hour"],
  ["Giorni e oltre", (k) => !["minute", "hour"].includes(TF[k].type)],
];
const durata = (k) => {
  const { type, span } = TF[k];
  if (type === "minute") return span === 1 ? "1 minuto" : `${span} minuti`;
  if (type === "hour") return span === 1 ? "1 ora" : `${span} ore`;
  return { day: "giorno", week: "settimana", month: "mese" }[type];
};
const NOME_TF = (p) => Object.keys(TF).find((k) => TF[k].type === p.type && TF[k].span === p.span);

const STRUMENTI = [
  ["segment", "Trendline"], ["rayLine", "Semiretta"], ["straightLine", "Retta"],
  ["horizontalStraightLine", "Orizzontale"], ["horizontalRayLine", "Orizz. da un punto"],
  ["verticalStraightLine", "Verticale"], ["parallelStraightLine", "Canale"],
  null,
  ["zona", "Zona"], ["nota", "Nota"], ["fibonacciLine", "Fibonacci"],
  ["rischio", "Rischio/rendimento"],
];
const NOMI_STRUMENTI = Object.fromEntries(STRUMENTI.filter(Boolean));

const INDICATORI = [
  ["MA", "Medie mobili (MA)", true], ["EMA", "Medie esponenziali (EMA)", true],
  ["BOLL", "Bande di Bollinger", true], ["SAR", "Parabolic SAR", true],
  ["VOL", "Volume", false], ["RSI", "RSI", false], ["MACD", "MACD", false],
];

const memoria = {
  leggi(k, def) { try { const v = localStorage.getItem(k); return v === null ? def : JSON.parse(v); } catch { return def; } },
  scrivi(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage non disponibile */ } },
};

const $ = (id) => document.getElementById(id);
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

let tfAttivo = memoria.leggi("tf", "M15");
if (!TF[tfAttivo]) tfAttivo = "M15";
let preferiti = memoria.leggi("tfPreferiti", PREFERITI_BASE).filter((k) => TF[k]);
let disegni = [];            // [{id, name, points:[{timestamp,value}], extendData:{testo, nascosto:[]}}]
let selezionato = null;
let primoCaricamento = true;
let timerVivo = null;

// ----------------------------------------------------------------- stili
function stiliGrafico() {
  const testo = css("--tenue"), bordo = css("--bordo"), griglia = css("--griglia");
  const su = css("--su"), giu = css("--giu");
  const asse = { axisLine: { color: bordo }, tickLine: { color: bordo }, tickText: { color: testo } };
  return {
    grid: { horizontal: { color: griglia }, vertical: { color: griglia } },
    candle: {
      bar: {
        upColor: su, downColor: giu, noChangeColor: testo,
        upBorderColor: su, downBorderColor: giu, noChangeBorderColor: testo,
        upWickColor: su, downWickColor: giu, noChangeWickColor: testo,
      },
      tooltip: { title: { color: testo }, legend: { color: testo } },
    },
    indicator: { tooltip: { title: { color: testo }, legend: { color: testo } } },
    xAxis: asse, yAxis: asse,
    separator: { color: bordo },
    crosshair: {
      horizontal: { line: { color: testo }, text: { backgroundColor: "#505669" } },
      vertical: { line: { color: testo }, text: { backgroundColor: "#505669" } },
    },
  };
}

function applicaTema(t) {
  if (t) document.documentElement.dataset.theme = t;
  else delete document.documentElement.dataset.theme;
  chart.setStyles(stiliGrafico());
}

// ----------------------------------------------------- disegni su misura
function prezzo(v) { return Number(v).toFixed(2); }

klinecharts.registerOverlay({
  name: "zona",
  totalStep: 3,
  needDefaultPointFigure: true,
  needDefaultXAxisFigure: true,
  needDefaultYAxisFigure: true,
  createPointFigures: ({ coordinates, overlay }) => {
    if (coordinates.length < 2) return [];
    const [a, b] = coordinates;
    const x = Math.min(a.x, b.x), y = Math.min(a.y, b.y);
    const figure = [{
      type: "rect",
      attrs: { x, y, width: Math.abs(b.x - a.x), height: Math.abs(b.y - a.y) },
      styles: { style: "stroke_fill", color: "rgba(41,98,255,0.14)", borderColor: "#2962ff", borderSize: 1 },
    }];
    const testo = overlay.extendData?.testo;
    if (testo) {
      figure.push({ type: "text", ignoreEvent: true,
        attrs: { x: x + 4, y: y + 4, text: testo, align: "left", baseline: "top" },
        styles: { style: "fill", color: "#2962ff", backgroundColor: "transparent", size: 12 } });
    }
    return figure;
  },
});

klinecharts.registerOverlay({
  name: "nota",
  totalStep: 2,
  needDefaultPointFigure: false,
  createPointFigures: ({ coordinates, overlay }) => [{
    type: "text",
    attrs: { x: coordinates[0].x, y: coordinates[0].y, text: overlay.extendData?.testo || "Nota", align: "left", baseline: "bottom" },
    styles: { style: "fill", color: "#ffffff", backgroundColor: "rgba(41,98,255,0.9)", borderRadius: 3,
      paddingLeft: 5, paddingRight: 5, paddingTop: 3, paddingBottom: 3, size: 12 },
  }],
});

// Rischio/rendimento: tre clic = ingresso, stop, obiettivo. Il verso si deduce
// dall'obiettivo: sopra l'ingresso e' un long, sotto uno short.
klinecharts.registerOverlay({
  name: "rischio",
  totalStep: 4,
  needDefaultPointFigure: true,
  needDefaultYAxisFigure: true,
  createPointFigures: ({ coordinates, overlay }) => {
    const c = coordinates, p = overlay.points;
    if (c.length < 2) return [];
    const sinistra = c[0].x;
    const destra = Math.max(sinistra + 90, ...c.map((k) => k.x));
    const larg = destra - sinistra;
    const box = (y1, y2, colore) => ({
      type: "rect",
      attrs: { x: sinistra, y: Math.min(y1, y2), width: larg, height: Math.abs(y2 - y1) },
      styles: { style: "fill", color: colore },
    });
    const etichetta = (y, testo, sfondo, base) => ({
      type: "text", ignoreEvent: true,
      attrs: { x: sinistra + larg / 2, y, text: testo, align: "center", baseline: base },
      styles: { style: "fill", color: "#fff", backgroundColor: sfondo, borderRadius: 2, size: 11,
        paddingLeft: 4, paddingRight: 4, paddingTop: 2, paddingBottom: 2 },
    });
    const ingresso = p[0].value, stop = p[1]?.value;
    const rischio = Math.abs(ingresso - stop);
    const f = [box(c[0].y, c[1].y, "rgba(242,54,69,0.22)")];
    f.push({ type: "line", attrs: { coordinates: [{ x: sinistra, y: c[0].y }, { x: destra, y: c[0].y }] },
      styles: { color: "#9598a1", size: 1 } });
    if (c.length >= 3 && p[2]?.value !== undefined) {
      const obiettivo = p[2].value;
      const rr = rischio > 0 ? Math.abs(obiettivo - ingresso) / rischio : 0;
      f.push(box(c[0].y, c[2].y, "rgba(8,153,129,0.22)"));
      const long = obiettivo > ingresso;
      f.push(etichetta(c[2].y, `Obiettivo ${prezzo(obiettivo)} (+${prezzo(Math.abs(obiettivo - ingresso))} $) · 1:${rr.toFixed(1)}`,
        "#089981", long ? "bottom" : "top"));
      f.push(etichetta(c[1].y, `Stop ${prezzo(stop)} (-${prezzo(rischio)} $)`, "#f23645", long ? "top" : "bottom"));
    } else {
      f.push(etichetta(c[1].y, `Stop -${prezzo(rischio)} $`, "#f23645", c[1].y > c[0].y ? "top" : "bottom"));
    }
    return f;
  },
});

// Operazione di backtest: freccia all'ingresso, stop e obiettivo tratteggiati,
// linea fino all'uscita se il file la contiene. Bloccata: non si sposta.
klinecharts.registerOverlay({
  name: "operazione",
  totalStep: 2,
  needDefaultPointFigure: false,
  createPointFigures: ({ coordinates, overlay, chart }) => {
    const op = overlay.extendData;
    const c = coordinates[0];
    const long = String(op.lato).toLowerCase().startsWith("l");
    const colore = long ? "#089981" : "#f23645";
    const d = long ? 1 : -1;
    const punta = c.y + d * 4;
    const f = [{
      type: "polygon",
      attrs: { coordinates: [{ x: c.x, y: punta }, { x: c.x - 6, y: punta + d * 10 }, { x: c.x + 6, y: punta + d * 10 }] },
      styles: { style: "fill", color: colore },
    }];
    const lungo = 40;
    const linea = (valore, col) => {
      const [k] = chart.convertToPixel([{ timestamp: overlay.points[0].timestamp, value: valore }],
        { paneId: overlay.paneId });
      if (k?.y === undefined) return null;
      return { type: "line", attrs: { coordinates: [{ x: c.x, y: k.y }, { x: c.x + lungo, y: k.y }] },
        styles: { style: "dashed", color: col, size: 1, dashedValue: [3, 3] } };
    };
    if (op.stop !== undefined) f.push(linea(op.stop, "#f23645"));
    if (op.target !== undefined) f.push(linea(op.target, "#089981"));
    if (coordinates.length > 1) {
      const e = coordinates[1];
      const vinta = (op.R ?? 0) > 0;
      f.push({ type: "line", attrs: { coordinates: [c, e] },
        styles: { style: "dashed", color: vinta ? "#089981" : "#f23645", size: 1, dashedValue: [4, 3] } });
      if (op.R !== undefined) {
        f.push({ type: "text", ignoreEvent: true, attrs: { x: e.x + 4, y: e.y, text: `${op.R > 0 ? "+" : ""}${op.R.toFixed(2)}R`, align: "left", baseline: "middle" },
          styles: { style: "fill", color: "#fff", backgroundColor: vinta ? "#089981" : "#f23645", size: 11, borderRadius: 2,
            paddingLeft: 3, paddingRight: 3, paddingTop: 1, paddingBottom: 1 } });
      }
    }
    return f.filter(Boolean);
  },
});

// ----------------------------------------------------------------- grafico
const chart = klinecharts.init("grafico", { timezone: memoria.leggi("fuso", "UTC") });
// D1 e W1 iniziano alle 17:00 di New York del giorno prima (vedi server.py):
// +7 ore portano alla data della giornata di contrattazione, come la scrive
// il broker, sia in UTC sia in ora italiana
chart.setFormatter({
  formatDate: ({ dateTimeFormat, timestamp, template }) => {
    const p = chart.getPeriod();
    const lungo = p && ["day", "week", "month"].includes(p.type);
    return klinecharts.utils.formatDate(dateTimeFormat, lungo ? timestamp + 7 * 3600e3 : timestamp, template);
  },
});
$("fuso").value = memoria.leggi("fuso", "UTC");
chart.setSymbol({ ticker: "XAUUSD", pricePrecision: 2, volumePrecision: 2 });

async function api(percorso, opzioni) {
  const r = await fetch(percorso, opzioni);
  const j = await r.json();
  if (!r.ok) throw new Error(j.errore || r.statusText);
  return j;
}

chart.setDataLoader({
  getBars: async ({ type, timestamp, period, callback }) => {
    const tf = NOME_TF(period);
    try {
      if (type === "init") {
        const j = await api(`/api/candele?tf=${tf}&n=1500`);
        callback(j.barre, { forward: j.altre, backward: false });
        if (primoCaricamento) { primoCaricamento = false; ricreaDisegni(); }
        applicaVisibilita();
      } else if (type === "forward") {
        const j = await api(`/api/candele?tf=${tf}&n=1500&prima=${timestamp}`);
        callback(j.barre, { forward: j.altre, backward: false });
      } else {
        callback([], false);
      }
    } catch (e) {
      $("stato").textContent = `errore: ${e.message}`;
      callback([], false);
    }
  },
  // l'ultima candela si aggiorna ogni 3 secondi (dal terminale MT5, se c'e')
  subscribeBar: ({ period, callback }) => {
    clearInterval(timerVivo);
    const tf = NOME_TF(period);
    timerVivo = setInterval(async () => {
      try {
        const j = await api(`/api/candele?tf=${tf}&n=2`);
        j.barre.forEach((b) => callback(b));
      } catch { /* il server riprova da solo */ }
    }, 3000);
  },
  unsubscribeBar: () => clearInterval(timerVivo),
});

// ------------------------------------------------------------- timeframe
// Nella barra: i preferiti, piu' quello attivo se non lo e'. Accanto, l'elenco
// di tutti: clic sul nome per aprirlo, sulla stella per metterlo o toglierlo
// dalla barra (scelta ricordata dal browser).
function disegnaTf() {
  const nav = $("tf");
  const aperto = nav.querySelector("details")?.open;   // la stella non chiude l'elenco
  nav.innerHTML = "";
  Object.keys(TF).filter((k) => preferiti.includes(k) || k === tfAttivo).forEach((k) => {
    const b = document.createElement("button");
    b.textContent = k;
    b.title = durata(k);
    b.setAttribute("aria-pressed", String(k === tfAttivo));
    b.onclick = () => cambiaTf(k);
    nav.appendChild(b);
  });
  const menu = document.createElement("details");
  menu.className = "menu";
  menu.open = Boolean(aperto);
  const titolo = document.createElement("summary");
  titolo.textContent = "▾";
  titolo.title = "Tutti i timeframe";
  const tendina = document.createElement("div");
  tendina.className = "tendina elenco-tf";
  GRUPPI_TF.forEach(([nomeGruppo, delGruppo]) => {
    const h = document.createElement("div");
    h.className = "gruppo-tf";
    h.textContent = nomeGruppo;
    tendina.appendChild(h);
    Object.keys(TF).filter(delGruppo).forEach((k) => {
      const riga = document.createElement("div");
      riga.className = "riga-tf";
      const pref = preferiti.includes(k);
      const stella = document.createElement("button");
      stella.className = "stella";
      stella.textContent = pref ? "★" : "☆";
      stella.title = pref ? "Togli dalla barra" : "Metti nella barra";
      stella.setAttribute("aria-pressed", String(pref));
      stella.onclick = () => {
        // nell'ordine dell'elenco, non in quello dei clic
        preferiti = Object.keys(TF).filter((x) => (x === k ? !pref : preferiti.includes(x)));
        memoria.scrivi("tfPreferiti", preferiti);
        disegnaTf();
      };
      const nome = document.createElement("button");
      nome.className = "nome-tf";
      nome.innerHTML = `<b>${k}</b> <span>${durata(k)}</span>`;
      nome.setAttribute("aria-pressed", String(k === tfAttivo));
      nome.onclick = () => { menu.open = false; cambiaTf(k); };
      riga.append(stella, nome);
      tendina.appendChild(riga);
    });
  });
  menu.append(titolo, tendina);
  nav.appendChild(menu);
}
// l'elenco si chiude cliccando fuori (la stella ridisegna la barra: il suo
// pulsante, ormai staccato dalla pagina, non conta come "fuori")
document.addEventListener("click", (e) => {
  const m = $("tf").querySelector("details");
  if (m?.open && e.target.isConnected && !m.contains(e.target)) m.open = false;
});
function cambiaTf(k) {
  tfAttivo = k;
  memoria.scrivi("tf", k);
  disegnaTf();
  chart.setPeriod(TF[k]);
  applicaVisibilita();
  if (selezionato) mostraSelezione(selezionato);
}

// ------------------------------------------------------------------ zoom
// La libreria zooma gia' da sola: rotellina = in largo, trascinare la scala
// dei tempi = in largo, trascinare la scala dei prezzi = in alto, doppio clic
// su di essa = scala automatica. Qui si aggiungono la rotellina in alto, lo
// zoom generale e i pulsanti.
//
// Per lo zoom in alto la libreria non ha un comando: si simula il
// trascinamento della scala dei prezzi. Cosi' lo stato resta uno solo, il
// suo, e il doppio clic sulla scala continua a riportarlo in automatico.
// La libreria moltiplica l'intervallo dei prezzi per (y finale / y iniziale),
// in coordinate di pagina: per ingrandire di f basta arrivare a y0 / f. Il
// trascinamento deve restare dentro la scala, altrimenti la libreria lo
// ignora: si parte (o si arriva) in fondo, dove la precisione e' massima.
function zoomAlto(f) {               // f > 1 ingrandisce le candele
  const asse = chart.getDom("candle_pane", "yAxis");
  if (!asse) return;
  const r = asse.getBoundingClientRect();
  const x = r.left + r.width / 2, fondo = r.bottom - 4 + window.scrollY;
  const [p0, p1] = f >= 1 ? [fondo, fondo / f] : [fondo * f, fondo];
  const y0 = p0 - window.scrollY, y1 = p1 - window.scrollY;
  const ev = (tipo, y) => asse.dispatchEvent(new MouseEvent(tipo, {
    bubbles: true, cancelable: true, view: window, clientX: x, clientY: y,
    button: 0, buttons: tipo === "mouseup" ? 0 : 1,
  }));
  ev("mousedown", y0); ev("mousemove", y1); ev("mouseup", y1);
}
function zoomLargo(f, punto) { chart.zoomAtCoordinate(f, punto); }
function adatta() {
  // reimpostare il timeframe (un oggetto nuovo) e' l'unico modo pubblico per
  // tornare alla scala automatica; ricarica le candele, ma e' questione di un attimo
  chart.setPeriod({ ...TF[tfAttivo] });
}
function disegnaZoom() {
  const P = 1.25;
  const pulsanti = [
    ["−", "Zoom indietro, in largo e in alto", () => { zoomLargo(1 / P); zoomAlto(1 / P); }],
    ["+", "Zoom avanti, in largo e in alto", () => { zoomLargo(P); zoomAlto(P); }],
    ["↔−", "Piu' candele (in largo)", () => zoomLargo(1 / P)],
    ["↔+", "Meno candele, piu' larghe (in largo)", () => zoomLargo(P)],
    ["↕−", "Scala dei prezzi piu' corta (in alto)", () => zoomAlto(1 / P)],
    ["↕+", "Scala dei prezzi piu' lunga (in alto)", () => zoomAlto(P)],
    ["Adatta", "Scala automatica e ultime candele", adatta],
  ];
  const nav = $("zoom");
  pulsanti.forEach(([testo, titolo, fai]) => {
    const b = document.createElement("button");
    b.textContent = testo;
    b.title = titolo;
    b.onclick = fai;
    nav.appendChild(b);
  });
  // rotellina: MAIUSC o sopra la scala dei prezzi = in alto, CTRL = tutti e
  // due (e niente zoom della pagina). Senza tasti sul grafico resta quella
  // della libreria. Il gestore e' in cattura sul contenitore, quindi arriva
  // prima della libreria e la puo' fermare.
  $("grafico").addEventListener("wheel", (e) => {
    const asse = chart.getDom("candle_pane", "yAxis");
    const r = asse ? asse.getBoundingClientRect() : null;
    const sullaScala = r && e.clientX >= r.left && e.clientX <= r.right
      && e.clientY >= r.top && e.clientY <= r.bottom;
    if (!e.shiftKey && !e.ctrlKey && !sullaScala) return;
    e.preventDefault();
    e.stopPropagation();
    const d = e.deltaY || e.deltaX;               // con MAIUSC alcuni browser girano su deltaX
    if (!d) return;
    const f = d < 0 ? 1.12 : 1 / 1.12;
    if (e.ctrlKey) {
      const g = $("grafico").getBoundingClientRect();
      zoomLargo(f, { x: e.clientX - g.left, y: e.clientY - g.top });
    }
    zoomAlto(f);
  }, { capture: true, passive: false });
}

// ------------------------------------------------------------ indicatori
function disegnaIndicatori() {
  const attivi = memoria.leggi("indicatori", ["MA"]);
  const box = $("indicatori");
  INDICATORI.forEach(([nome, etichetta, sulPrezzo]) => {
    const l = document.createElement("label");
    const c = document.createElement("input");
    c.type = "checkbox";
    c.checked = attivi.includes(nome);
    c.onchange = () => {
      const ora = memoria.leggi("indicatori", ["MA"]).filter((n) => n !== nome);
      if (c.checked) { mettiIndicatore(nome, sulPrezzo); ora.push(nome); }
      else chart.removeIndicator({ name: nome });
      memoria.scrivi("indicatori", ora);
    };
    l.append(c, etichetta);
    box.appendChild(l);
    if (c.checked) mettiIndicatore(nome, sulPrezzo);
  });
}
function mettiIndicatore(nome, sulPrezzo) {
  if (sulPrezzo) chart.createIndicator({ name: nome, paneId: "candle_pane" }, true);
  else chart.createIndicator({ name: nome });
}

// ---------------------------------------------------------------- disegni
let timerSalva = null;
function salva() {
  clearTimeout(timerSalva);
  timerSalva = setTimeout(() => {
    api("/api/disegni", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(disegni) })
      .catch((e) => { $("stato").textContent = `disegni NON salvati: ${e.message}`; });
  }, 400);
}

const puntiDi = (o) => o.points.map((p) => ({ timestamp: p.timestamp, value: p.value }));

function gestori() {
  return {
    onDrawEnd: ({ overlay }) => {
      const d = { id: overlay.id, name: overlay.name, points: puntiDi(overlay),
        extendData: { ...(overlay.extendData || {}), nascosto: [] } };
      disegni.push(d);
      salva();
      strumentoAttivo(null);
      // il testo di note e zone si scrive nel riquadro a destra, gia' pronto
      if (overlay.name === "nota" || overlay.name === "zona") {
        mostraSelezione(overlay.id);
        $("sel-testo").focus();
      }
    },
    onPressedMoveEnd: ({ overlay }) => {
      const d = disegni.find((x) => x.id === overlay.id);
      if (d) { d.points = puntiDi(overlay); salva(); }
    },
    onRemoved: ({ overlay }) => {
      const prima = disegni.length;
      disegni = disegni.filter((x) => x.id !== overlay.id);
      if (disegni.length !== prima) salva();
      if (selezionato === overlay.id) nascondiSelezione();
    },
    onSelected: ({ overlay }) => mostraSelezione(overlay.id),
    onDeselected: () => nascondiSelezione(),
  };
}

function modoMagnete() { return memoria.leggi("magnete", false) ? "weak_magnet" : "normal"; }

function nuovoDisegno(nome) {
  strumentoAttivo(nome);
  chart.createOverlay({ name: nome, mode: modoMagnete(), extendData: { nascosto: [] }, ...gestori() });
}

function ricreaDisegni() {
  api("/api/disegni").then((lista) => {
    disegni = lista;
    lista.forEach((d) => chart.createOverlay({
      id: d.id, name: d.name, points: d.points, extendData: d.extendData,
      visible: !(d.extendData?.nascosto || []).includes(tfAttivo), ...gestori(),
    }));
  }).catch((e) => { $("stato").textContent = `disegni non letti: ${e.message}`; });
}

function applicaVisibilita() {
  disegni.forEach((d) => chart.overrideOverlay({ id: d.id, visible: !(d.extendData?.nascosto || []).includes(tfAttivo) }));
}

function strumentoAttivo(nome) {
  document.querySelectorAll("#strumenti button[data-nome]").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.nome === nome)));
}

function disegnaStrumenti() {
  const box = $("strumenti");
  STRUMENTI.forEach((s) => {
    if (!s) { box.appendChild(document.createElement("hr")); return; }
    const b = document.createElement("button");
    b.textContent = s[1];
    b.dataset.nome = s[0];
    b.onclick = () => nuovoDisegno(s[0]);
    box.appendChild(b);
  });
  box.appendChild(document.createElement("hr"));
  const m = document.createElement("button");
  const aggiornaM = () => { m.textContent = `Magnete: ${memoria.leggi("magnete", false) ? "sì" : "no"}`; };
  m.title = "Aggancia i punti a apertura/massimo/minimo/chiusura";
  m.onclick = () => { memoria.scrivi("magnete", !memoria.leggi("magnete", false)); aggiornaM(); };
  aggiornaM();
  box.appendChild(m);
  const tutto = document.createElement("button");
  tutto.textContent = "Cancella tutti";
  tutto.className = "pericolo";
  tutto.onclick = () => {
    if (!disegni.length || !confirm(`Eliminare tutti i ${disegni.length} disegni?`)) return;
    disegni.map((d) => d.id).forEach((id) => chart.removeOverlay({ id }));
    disegni = [];
    salva();
  };
  box.appendChild(tutto);
}

// ------------------------------------------------------ pannello disegno
function mostraSelezione(id) {
  const d = disegni.find((x) => x.id === id);
  if (!d) return;
  selezionato = id;
  $("sel").hidden = false;
  $("sel-tipo").textContent = NOMI_STRUMENTI[d.name] || d.name;
  const conTesto = d.name === "nota" || d.name === "zona";
  $("sel-testo-riga").hidden = !conTesto;
  $("sel-testo").value = d.extendData?.testo || "";
  const box = $("sel-tf");
  box.innerHTML = "";
  Object.keys(TF).forEach((k) => {
    const l = document.createElement("label");
    const c = document.createElement("input");
    c.type = "checkbox";
    c.checked = !(d.extendData.nascosto || []).includes(k);
    c.onchange = () => {
      const n = new Set(d.extendData.nascosto || []);
      if (c.checked) n.delete(k); else n.add(k);
      d.extendData.nascosto = [...n];
      chart.overrideOverlay({ id: d.id, extendData: d.extendData, visible: !n.has(tfAttivo) });
      salva();
    };
    l.append(c, k);
    box.appendChild(l);
  });
}
function nascondiSelezione() { selezionato = null; $("sel").hidden = true; }

$("sel-testo").addEventListener("input", () => {
  const d = disegni.find((x) => x.id === selezionato);
  if (!d) return;
  d.extendData.testo = $("sel-testo").value;
  chart.overrideOverlay({ id: d.id, extendData: d.extendData });
  salva();
});
$("sel-elimina").onclick = () => { if (selezionato) chart.removeOverlay({ id: selezionato }); };

document.addEventListener("keydown", (e) => {
  if (e.target.matches("input, select, textarea")) return;
  if ((e.key === "Delete" || e.key === "Backspace") && selezionato) chart.removeOverlay({ id: selezionato });
  if (e.key === "Escape") {
    // un disegno a meta' non ha ancora onDrawEnd: non e' in `disegni`
    const noti = new Set(disegni.map((d) => d.id));
    chart.getOverlays().filter((o) => o.groupId !== "backtest" && !noti.has(o.id))
      .forEach((o) => chart.removeOverlay({ id: o.id }));
    strumentoAttivo(null);
  }
});

// --------------------------------------------------------------- backtest
async function caricaCatalogo() {
  const sel = $("bt-scelta");
  try {
    const voci = await api("/api/backtest");
    voci.forEach((v) => { const o = document.createElement("option"); o.value = v.id; o.textContent = v.nome; sel.appendChild(o); });
  } catch (e) { $("bt-riepilogo").textContent = `catalogo non letto: ${e.message}`; }
  sel.onchange = () => mostraBacktest(sel.value);
}

async function mostraBacktest(id) {
  chart.removeOverlay({ groupId: "backtest" });
  $("bt-riepilogo").innerHTML = "";
  $("bt-elenco").innerHTML = "";
  if (!id) return;
  const j = await api(`/api/backtest/${encodeURIComponent(id)}`);
  const r = j.riepilogo;
  const righe = [["operazioni", r.operazioni], ["periodo", `${r.dal} → ${r.al}`]];
  if (r.R_totale !== undefined) righe.push(["R totale", r.R_totale], ["R medio", r.R_medio], ["vinte", `${(r.vinte * 100).toFixed(1)}%`]);
  const t = document.createElement("table");
  righe.forEach(([a, b]) => { const tr = t.insertRow(); tr.insertCell().textContent = a; tr.insertCell().textContent = b; });
  $("bt-riepilogo").appendChild(t);
  if (j.voce.nota) { const p = document.createElement("p"); p.className = "tipo"; p.textContent = j.voce.nota; $("bt-riepilogo").appendChild(p); }

  chart.createOverlay(j.operazioni.map((op) => ({
    name: "operazione", groupId: "backtest", lock: true, extendData: op,
    points: op.t_uscita !== undefined && op.exit_price !== undefined
      ? [{ timestamp: op.t, value: op.entry }, { timestamp: op.t_uscita, value: op.exit_price }]
      : [{ timestamp: op.t, value: op.entry }],
  })));

  const fmt = new Intl.DateTimeFormat("it-IT", { dateStyle: "short", timeStyle: "short", timeZone: $("fuso").value });
  const elenco = $("bt-elenco");
  j.operazioni.slice().reverse().forEach((op) => {
    const li = document.createElement("li");
    const long = String(op.lato).toLowerCase().startsWith("l");
    const a = document.createElement("span");
    a.textContent = `${fmt.format(op.t)} ${long ? "▲" : "▼"}`;
    a.className = long ? "su" : "giu";
    const b = document.createElement("span");
    b.textContent = op.R !== undefined ? `${op.R > 0 ? "+" : ""}${op.R.toFixed(2)}R` : prezzo(op.entry);
    li.append(a, b);
    // scrollToTimestamp mette l'operazione sul bordo destro: la si porta al centro
    li.onclick = () => { chart.scrollToTimestamp(op.t); chart.scrollByDistance(-chart.getSize().width / 2, 200); };
    elenco.appendChild(li);
  });
}

// ------------------------------------------------------------------ stato
async function aggiornaStato() {
  try {
    const s = await api("/api/stato");
    const arch = s.archivio ? `archivio ${s.archivio} (fino al ${s.archivio_al.slice(0, 10)})` : "archivio assente";
    let vivo = "MT5 spento";
    if (s.mt5) vivo = s.vivo_al ? `${s.simbolo} dal vivo, ultimo ${s.vivo_al.slice(0, 16)} UTC` : `MT5 non collegato${s.errore ? `: ${s.errore}` : ""}`;
    $("stato").textContent = `${arch} · ${vivo}`;
  } catch (e) { $("stato").textContent = `server non raggiungibile: ${e.message}`; }
}

// ------------------------------------------------------------------ avvio
$("fuso").onchange = () => { memoria.scrivi("fuso", $("fuso").value); chart.setTimezone($("fuso").value); };
$("tema").onclick = () => {
  const scuro = getComputedStyle(document.documentElement).getPropertyValue("--sfondo").trim() === "#131722";
  const t = scuro ? "light" : "dark";
  memoria.scrivi("tema", t);
  applicaTema(t);
};
window.addEventListener("resize", () => chart.resize());

applicaTema(memoria.leggi("tema", null));
disegnaTf();
disegnaZoom();
disegnaStrumenti();
disegnaIndicatori();
caricaCatalogo();
aggiornaStato();
setInterval(aggiornaStato, 15000);
chart.setPeriod(TF[tfAttivo]);
