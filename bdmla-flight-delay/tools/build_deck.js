// Builds the CW1 presentation (.pptx, 14 slides, ~10 minutes, with speaker notes).
//   node build_deck.js [outputsDir] [out.pptx]
// With outputsDir (the notebook's FlightDelay2025_outputs folder) the charts are drawn natively from the
// notebook's CSV tables and every {{PLACEHOLDER}} is filled. Without it, result slots show highlighted placeholders.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const { applyTheme } = require("./apply_theme.js");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = process.argv[2] ? path.resolve(process.argv[2]) : null;
const OUT_FILE = process.argv[3] || path.join(ROOT, "presentation", "BDMLA_CW1_Flight_Delay_Presentation.pptx");
let PH = {};
const phFile = OUT_DIR && path.join(OUT_DIR, "report_placeholders.json");
if (phFile && fs.existsSync(phFile)) PH = JSON.parse(fs.readFileSync(phFile, "utf8"));

function csv(name) {
  const f = OUT_DIR && path.join(OUT_DIR, "tables", name);
  if (!f || !fs.existsSync(f)) return null;
  const [head, ...lines] = fs.readFileSync(f, "utf8").trim().split(/\r?\n/);
  const cols = head.split(",");
  return lines.map((l) => Object.fromEntries(l.split(",").map((v, i) => [cols[i], v])));
}
const has = (k) => PH[k] !== undefined;
const V = (k) => (has(k) ? String(PH[k]) : `[${k}]`);
const num = (k) => parseFloat(String(PH[k]).replace(/[^0-9.\-]/g, ""));

// ---------------------------------------------------------------- theme
const THEME = {
  name: "Flight Delay Spark",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "0B1F3A", lt1: "FFFFFF", dk2: "13315C", lt2: "EEF3F8",
    accent1: "2A78D6", accent2: "EB6834", accent3: "1BAF7A", accent4: "EDA100", accent5: "8DA9C4", accent6: "5C6B7A",
    hlink: "2A78D6", folHlink: "4A3AA7",
  },
};
const HEX = { navy: "0B1F3A", navy2: "13315C", ice: "EEF3F8", sky: "8DA9C4", lr: "2A78D6", rf: "EB6834", gbt: "1BAF7A",
  muted: "5C6B7A", grid: "D9DEE5", white: "FFFFFF", amber: "EDA100" };
const MODEL_HEX = [HEX.lr, HEX.rf, HEX.gbt];
const MODELS = ["Logistic Regression", "Random Forest", "Gradient-Boosted Trees"];
const SHORT = ["LR", "RF", "GBT"];

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.author = "BDMLA student";
pres.title = "Predicting Airline Flight Delays Using Apache Spark";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 13.333, H = 7.5, MX = 0.6;

// ---------------------------------------------------------------- layouts
pres.defineSlideMaster({
  title: "TITLE_DARK", background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 2.0, w: 8.2, h: 2.0, fontSize: 44, bold: true, align: "left",
      color: C.background1, valign: "bottom", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: MX, y: 4.2, w: 8.2, h: 1.6, fontSize: 18, align: "left",
      color: C.accent5, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 0.35, w: W - 2 * MX, h: 0.9, fontSize: 32, bold: true, align: "left",
      color: C.text1, valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "Flight delay prediction with Apache Spark  ·  M33877 BDMLA", options: { x: MX, y: H - 0.42, w: 7, h: 0.3,
      fontSize: 10, color: C.accent6, margin: 0 } } },
  ],
  slideNumber: { x: W - MX - 0.6, y: H - 0.42, w: 0.6, h: 0.3, fontSize: 10, color: C.accent6, align: "right" },
});
pres.defineSlideMaster({
  title: "SECTION_DARK", background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 0.35, w: W - 2 * MX, h: 0.9, fontSize: 32, bold: true, align: "left",
      color: C.background1, valign: "middle", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: W - MX - 0.6, y: H - 0.42, w: 0.6, h: 0.3, fontSize: 10, color: C.accent5, align: "right" },
});

// ---------------------------------------------------------------- helpers
async function icon(Comp, color = "#FFFFFF") {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color, size: 256 }));
  const png = await sharp(Buffer.from(svg)).resize(256, 256).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}
async function iconCircle(slide, Comp, x, y, d, fill, name) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill }, objectName: `${name}-circle` });
  const pad = d * 0.25;
  slide.addImage({ data: await icon(Comp), x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad, objectName: `${name}-icon` });
}
function card(slide, x, y, w, h, name, fill = C.background2) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.08, objectName: name });
}
// text with {{PLACEHOLDER}} support: unfilled values are highlighted yellow
function rich(text, base = {}) {
  const out = [];
  text.split(/(\{\{[A-Z0-9_]+\}\})/).forEach((part) => {
    if (!part) return;
    const m = part.match(/^\{\{([A-Z0-9_]+)\}\}$/);
    if (m) out.push({ text: V(m[1]), options: { ...base, ...(has(m[1]) ? {} : { highlight: "FFFF00", color: "000000" }) } });
    else out.push({ text: part, options: { ...base } });
  });
  return out;
}
function txt(slide, text, opts) {
  const base = { bold: opts.bold, color: opts.color, fontSize: opts.fontSize, italic: opts.italic };
  slide.addText(rich(text, base), { isTextBox: true, margin: 0, valign: "top", ...opts });
}
function bullets(slide, items, opts) {
  // one run per bullet (pptxgenjs starts a new paragraph for every run that carries bullet options)
  const runs = items.map((it, i) => {
    const missing = /\{\{([A-Z0-9_]+)\}\}/.test(it.replace(/\{\{([A-Z0-9_]+)\}\}/g, (m, k) => (has(k) ? "" : m)));
    const text = it.replace(/\{\{([A-Z0-9_]+)\}\}/g, (m, k) => V(k));
    return { text, options: { fontSize: opts.fontSize || 15, color: missing ? "000000" : (opts.color || C.text1),
      ...(missing ? { highlight: "FFFF00" } : {}), bullet: { indent: 16 }, paraSpaceAfter: 6, breakLine: i < items.length - 1 } };
  });
  slide.addText(runs, { isTextBox: true, margin: 0, valign: "top", ...opts });
}
function placeholderBox(slide, x, y, w, h, label, name) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: "FFF8DB" }, line: { color: HEX.amber, dashType: "dash", width: 1.25 },
    rectRadius: 0.06, objectName: name });
  slide.addText(label, { isTextBox: true, x, y, w, h, align: "center", valign: "middle", fontSize: 14, color: "7F6000", margin: 6 });
}
const chartBase = () => ({
  catAxisLabelColor: HEX.muted, valAxisLabelColor: HEX.muted, catAxisLabelFontSize: 11, valAxisLabelFontSize: 10,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt",
  titleFontFace: "+mn-lt", valGridLine: { color: HEX.grid, size: 0.5 }, catGridLine: { style: "none" },
  catAxisLineShow: false, valAxisLineShow: false, dataLabelColor: HEX.navy, dataLabelFontSize: 10,
  showTitle: true, titleColor: HEX.navy, titleFontSize: 13, legendColor: HEX.navy, legendFontSize: 11,
});
// speaker notes: fill [KEY] tokens that the notebook outputs provide; leave [CHECK ...] prompts for the presenter
const notes = (slide, t) => slide.addNotes(t.replace(/\[([A-Z0-9_]+)\]/g, (m, k) => (has(k) ? V(k) : m)));
const SRC = (slide, t) => slide.addText(t, { isTextBox: true, x: MX, y: H - 0.78, w: W - 2 * MX, h: 0.3, fontSize: 10, italic: true, color: C.accent6, margin: 0 });

// ---------------------------------------------------------------- slides
(async () => {
  let s;

  // 1. Title ------------------------------------------------------------------
  pres.addSection({ title: "Introduction" });
  s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Introduction" });
  s.addText("Predicting Airline Flight Delays Using Apache Spark", { placeholder: "title" });
  s.addText([
    { text: "Logistic Regression vs Random Forest vs Gradient-Boosted Trees on the full 2025 U.S. flight record", options: { breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 10 } },
    { text: "[Your name / student ID]  ·  M33877 Big Data and Machine Learning Applications  ·  November 2026", options: { fontSize: 14, color: "000000", highlight: "FFFF00" } },
  ], { placeholder: "body" });
  await iconCircle(s, fa.FaPlaneDeparture, 9.6, 2.1, 2.9, HEX.rf, "hero");
  notes(s, `[0:00-0:20] Good morning. My project asks a simple question with a practical use: can we tell, before a plane leaves the gate, whether it is going to arrive late? I used Apache Spark on every U.S. domestic flight from 2025 and compared three machine learning models.`);

  // 2. Background --------------------------------------------------------------
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
  s.addText("Delays are costly, and mostly a surprise", { placeholder: "title" });
  const stats = [["$32.9B", "cost of U.S. flight delays\nin 2007 (Ball et al., 2010)", HEX.rf], ["15 min", "BTS definition of a\n\"delayed\" arrival", HEX.lr], ["{{RAW_ROWS}}", "flights in 2025 BTS on-time data", HEX.gbt]];
  stats.forEach(([big, label, col], i) => {
    const y = 1.55 + i * 1.65;
    card(s, MX, y, 5.4, 1.4, `stat-${i}`);
    txt(s, big, { x: MX + 0.3, y: y + 0.15, w: 2.6, h: 1.1, fontSize: 36, bold: true, color: col, valign: "middle", fit: "shrink" });
    s.addText(label, { isTextBox: true, x: MX + 2.95, y: y + 0.15, w: 2.3, h: 1.1, fontSize: 13, color: C.text1, valign: "middle", margin: 0 });
  });
  const who = [[fa.FaUserTie, "Airlines", "Re-plan crews, gates and spare aircraft before problems hit"],
    [fa.FaUsers, "Passengers", "Earlier warnings for tight connections"],
    [fa.FaBuilding, "Airports", "Anticipate congestion at peak hours"]];
  for (let i = 0; i < who.length; i++) {
    const y = 1.65 + i * 1.65;
    await iconCircle(s, who[i][0], 6.75, y, 0.9, HEX.navy2, `who-${i}`);
    s.addText(who[i][1], { isTextBox: true, x: 7.9, y: y - 0.05, w: 4.8, h: 0.45, fontSize: 20, bold: true, color: C.text1, margin: 0 });
    s.addText(who[i][2], { isTextBox: true, x: 7.9, y: y + 0.42, w: 4.8, h: 0.6, fontSize: 15, color: C.accent6, margin: 0 });
  }
  notes(s, `[0:20-1:05] Delays are expensive. A U.S. study put the total cost at around 33 billion dollars in 2007 alone, across airlines, passengers and lost demand. The industry uses a simple rule: if you arrive 15 minutes or more after schedule, you are delayed. The Bureau of Transportation Statistics publishes a record for every domestic flight, about [RAW_ROWS] in 2025, which gives us millions of labelled examples. Knowing earlier which flights are at risk helps airlines re-plan crews and aircraft, helps passengers with connections, and helps airports manage peaks.`);

  // 3. Problem & objectives ----------------------------------------------------
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
  s.addText("Problem statement and objectives", { placeholder: "title" });
  card(s, MX, 1.45, W - 2 * MX, 1.35, "question-card", HEX.navy);
  s.addText([
    { text: "Using only information known before departure, ", options: { color: "FFFFFF" } },
    { text: "will this flight arrive 15+ minutes late?", options: { color: "FFB48F", bold: true } },
  ], { isTextBox: true, x: MX + 0.4, y: 1.45, w: W - 2 * MX - 0.8, h: 1.35, fontSize: 24, valign: "middle", margin: 0 });
  const objectives = [[fa.FaDatabase, "Ingest", "Union and clean all 12 monthly files with Spark"], [fa.FaShieldAlt, "No leakage", "Pre-departure features only"],
    [fa.FaProjectDiagram, "Model", "LR, Random Forest and GBT in Spark MLlib"], [fa.FaBalanceScale, "Evaluate", "Imbalance-aware metrics + training time"],
    [fa.FaServer, "Scale", "Show how it scales out to more cores"]];
  const ow = (W - 2 * MX - 4 * 0.3) / 5;
  for (let i = 0; i < objectives.length; i++) {
    const x = MX + i * (ow + 0.3);
    card(s, x, 3.2, ow, 3.15, `obj-${i}`);
    await iconCircle(s, objectives[i][0], x + 0.3, 3.45, 0.75, i === 1 ? HEX.rf : HEX.lr, `obj-icon-${i}`);
    s.addText(`O${i + 1}  ${objectives[i][1]}`, { isTextBox: true, x: x + 0.3, y: 4.35, w: ow - 0.5, h: 0.5, fontSize: 18, bold: true, color: C.text1, margin: 0 });
    s.addText(objectives[i][2], { isTextBox: true, x: x + 0.3, y: 4.9, w: ow - 0.5, h: 1.3, fontSize: 14, color: C.accent6, margin: 0, valign: "top" });
  }
  notes(s, `[1:05-1:45] So the problem is: using only what is known before departure, will this flight arrive 15 or more minutes late? That "before departure" part matters. Many online examples use departure delay as an input, which is basically cheating, because you only know it once the plane has left. I set five objectives: ingest and clean all twelve files in Spark, keep the features leakage-free, train three MLlib models, evaluate them properly for an imbalanced problem, and show how it scales.`);

  // 4. Dataset ----------------------------------------------------------------
  pres.addSection({ title: "Data and architecture" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Data and architecture" });
  s.addText("Dataset: BTS Reporting Carrier On-Time Performance, 2025", { placeholder: "title" });
  const ds = [["12", "monthly CSV files\n(Jan-Dec 2025)"], ["~3 GB", "raw CSV in\nGoogle Drive"], ["{{RAW_ROWS}}", "flights before cleaning"], ["17 / ~110", "columns kept by the\nallow-list"]];
  ds.forEach(([big, label], i) => {
    const x = MX + (i % 2) * 2.95, y = 1.5 + Math.floor(i / 2) * 2.0;
    card(s, x, y, 2.75, 1.8, `ds-${i}`);
    txt(s, big, { x: x + 0.25, y: y + 0.2, w: 2.3, h: 0.75, fontSize: 30, bold: true, color: C.accent1, fit: "shrink" });
    s.addText(label, { isTextBox: true, x: x + 0.25, y: y + 0.95, w: 2.3, h: 0.75, fontSize: 13, color: C.accent6, margin: 0 });
  });
  txt(s, "Target: DELAYED = 1 if ARR_DELAY ≥ 15 min.  Delayed share after cleaning: {{DELAY_RATE}}", { x: MX, y: 5.65, w: 5.7, h: 0.8, fontSize: 14, color: C.text1 });
  const hourly = csv("delay_rate_by_dep_hour.csv");
  if (hourly) {
    s.addChart(pres.charts.LINE, [{ name: "Delay rate", labels: hourly.map((r) => r.DEP_HOUR), values: hourly.map((r) => +(+r.delay_rate).toFixed(4)) }], {
      x: 6.75, y: 1.45, w: 6.0, h: 4.9, ...chartBase(), title: "Delay rate by scheduled departure hour", chartColors: [HEX.rf],
      lineSize: 2.5, lineDataSymbol: "circle", lineDataSymbolSize: 7, showLegend: false, valAxisLabelFormatCode: "0%", catAxisTitle: "Hour of day",
      showCatAxisTitle: true, catAxisTitleColor: HEX.muted, catAxisTitleFontSize: 11, objectName: "chart-hourly" });
  } else placeholderBox(s, 6.75, 1.45, 6.0, 4.9, "Chart: delay rate by departure hour\n(rebuild with notebook outputs: tables/delay_rate_by_dep_hour.csv)", "ph-hourly");
  SRC(s, "Source: Bureau of Transportation Statistics (2026), Reporting Carrier On-Time Performance.");
  notes(s, `[1:45-2:30] The data is the official BTS on-time table. I downloaded all twelve months of 2025, about 3 gigabytes of CSV and [RAW_ROWS] flights. Each file has around 110 columns, but I only load 17, which I'll come back to when I talk about leakage. After cleaning, about [DELAY_RATE] of flights are delayed, so the classes are imbalanced. The chart shows one of the clearest patterns: [CHECK the chart; typically] delays build up through the day, because a late aircraft carries its delay into its next flights.`);

  // 5. Architecture -------------------------------------------------------------
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Data and architecture" });
  s.addText("End-to-end Spark pipeline", { placeholder: "title" });
  s.addImage({ path: path.join(ROOT, "assets", "architecture_pipeline.png"), x: MX, y: 1.4, w: 12.1, h: 12.1 * 0.4, objectName: "pipeline-diagram" });
  s.addText("Google Colab · PySpark " + (has("SPARK_VERSION") ? V("SPARK_VERSION") : "4.0") + " · Spark SQL / DataFrames for processing · Spark MLlib for modelling", { isTextBox: true, x: MX, y: 6.4, w: 12.1, h: 0.4, fontSize: 14, color: C.accent6, margin: 0 });
  notes(s, `[2:30-3:10] Here's the whole pipeline. The twelve files sit in Google Drive. Spark reads each one, maps the column names, keeps only the allowed columns and unions them. Everything is then written once to Parquet, which is the key performance step. Next come the schedule features, cleaning and the label. The second row is the machine learning part: split, encode, train three models, tune them, evaluate, and export all the figures and tables that feed the report.`);

  // 6. Spark & optimisation ---------------------------------------------------------
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Data and architecture" });
  s.addText("Making a full year work on a free Colab machine", { placeholder: "title" });
  s.addImage({ path: path.join(ROOT, "assets", "spark_architecture.png"), x: MX, y: 1.5, w: 6.4, h: 6.4 * 0.42, objectName: "spark-diagram" });
  card(s, MX, 4.45, 3.1, 1.95, "parquet-stat");
  txt(s, "{{PARQUET_SPEEDUP}}", { x: MX + 0.25, y: 4.6, w: 2.6, h: 0.85, fontSize: 36, bold: true, color: C.accent3, fit: "shrink" });
  s.addText("faster scan on Parquet than on the raw CSVs", { isTextBox: true, x: MX + 0.25, y: 5.45, w: 2.6, h: 0.8, fontSize: 13, color: C.accent6, margin: 0 });
  card(s, MX + 3.3, 4.45, 3.1, 1.95, "scale-stat");
  txt(s, "{{SCALE_LR_SPEEDUP}}", { x: MX + 3.55, y: 4.6, w: 2.6, h: 0.85, fontSize: 36, bold: true, color: C.accent1, fit: "shrink" });
  txt(s, "LR training speed-up, 1 → {{SCALE_MAX_CORES}} cores", { x: MX + 3.55, y: 5.45, w: 2.6, h: 0.8, fontSize: 13, color: C.accent6 });
  bullets(s, [
    "Allow-list + Parquet: read 3 GB of text once, then columnar",
    "Shuffle partitions cut from 200 → a few per core, plus AQE",
    "Broadcast joins for small encoding tables",
    "Cache the model-ready data that trees scan repeatedly",
    "Metrics in one Spark aggregation, nothing big collected",
    "Same code on a cluster: change the master URL; GPUs via RAPIDS / XGBoost-Spark",
  ], { x: 7.35, y: 1.55, w: 5.4, h: 4.9, fontSize: 15 });
  notes(s, `[3:10-4:00] A quick look under the hood. Spark breaks the job into stages and tasks, one per data partition. In Colab the driver and executor share one machine, but the same code runs on a cluster just by changing the master URL. The changes that mattered most: converting to Parquet once, which made the same query [PARQUET_SPEEDUP] faster; reducing shuffle partitions; broadcasting small lookup tables; and computing all metrics inside Spark. I also ran a small scaling test: going from 1 to [SCALE_MAX_CORES] cores made logistic regression [SCALE_LR_SPEEDUP] faster.`);

  // 7. Cleaning & leakage ----------------------------------------------------------
  pres.addSection({ title: "Method" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Method" });
  s.addText("Cleaning, and keeping the future out of the features", { placeholder: "title" });
  const funnel = csv("cleaning_funnel.csv");
  if (funnel) {
    s.addChart(pres.charts.BAR, [{ name: "Rows", labels: funnel.map((r) => r.step), values: funnel.map((r) => +r.rows) }], {
      x: MX, y: 1.4, w: 6.1, h: 4.9, ...chartBase(), barDir: "bar", title: "Cleaning funnel (rows remaining)", chartColors: [HEX.lr],
      showLegend: false, showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "#,##0", valAxisHidden: true, valGridLine: { style: "none" },
      catAxisOrientation: "maxMin", barGapWidthPct: 45, objectName: "chart-funnel" });
  } else {
    bullets(s, ["Remove cancelled flights", "Remove diverted flights", "Remove rows with null ARR_DELAY", "Remove duplicate records", "Remove impossible schedule values",
      "Rows: {{FUNNEL_0_ROWS}} → {{FUNNEL_5_ROWS}}"], { x: MX, y: 1.6, w: 6.0, h: 4.6, fontSize: 17 });
  }
  card(s, 7.0, 1.4, 5.73, 4.95, "leak-card");
  await iconCircle(s, fa.FaShieldAlt, 7.3, 1.65, 0.75, HEX.rf, "leak");
  s.addText("Leakage guard", { isTextBox: true, x: 8.25, y: 1.75, w: 4.2, h: 0.55, fontSize: 20, bold: true, color: C.text1, margin: 0 });
  bullets(s, [
    "Allow-list at ingestion: post-flight columns are never loaded",
    "Also excluded: DEP_DELAY, DEP_TIME, TAXI_OUT, DEP_DEL15",
    "ARR_DELAY only builds the label, then it is dropped",
    "Schedule counts use the full schedule, before cancelled flights are removed",
    "Assertion fails the run if a forbidden column reaches the features",
  ], { x: 7.3, y: 2.6, w: 5.2, h: 3.6, fontSize: 15 });
  notes(s, `[4:00-4:50] Cleaning followed the brief: remove cancelled and diverted flights and rows with no arrival delay, plus duplicates and impossible values. The funnel shows how many rows each step removed. The bigger issue is leakage. Columns like wheels-on time or the delay-cause minutes are only known after landing, so they are never loaded. I also removed departure delay and taxi-out, which were not on the original list but would make the model useless in practice. One subtle point: if you count flights per hour after removing cancellations, a stormy day looks quiet, and the feature leaks the outcome. So I compute those counts on the full schedule first.`);

  // 8. Feature engineering --------------------------------------------------------------
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Method" });
  s.addText(rich("Feature engineering: {{N_FEATURES}} pre-departure features"), { placeholder: "title" });
  const groups = [
    [fa.FaCalendarAlt, "Calendar and time", "Month, day, weekday, departure and arrival hour (with sin/cos), days to the nearest federal holiday", HEX.lr],
    [fa.FaPlane, "Flight and airline", "Scheduled duration, distance, airline (one-hot)", HEX.lr],
    [fa.FaTrafficLight, "Airport congestion", "Scheduled departures and arrivals at the airport that hour; daily airport and carrier volume", HEX.lr],
    [fa.FaSyncAlt, "Aircraft rotation", "Leg of the day for this tail number and the scheduled turnaround since its last flight (window function)", HEX.rf],
  ];
  for (let i = 0; i < groups.length; i++) {
    const x = MX + (i % 2) * 6.15, y = 1.45 + Math.floor(i / 2) * 1.85;
    card(s, x, y, 5.95, 1.65, `fg-${i}`);
    await iconCircle(s, groups[i][0], x + 0.25, y + 0.4, 0.85, groups[i][3], `fg-icon-${i}`);
    s.addText(groups[i][1], { isTextBox: true, x: x + 1.35, y: y + 0.18, w: 4.4, h: 0.45, fontSize: 18, bold: true, color: C.text1, margin: 0 });
    s.addText(groups[i][2], { isTextBox: true, x: x + 1.35, y: y + 0.65, w: 4.4, h: 0.9, fontSize: 14, color: C.accent6, margin: 0 });
  }
  card(s, MX, 5.25, W - 2 * MX, 1.15, "te-card", HEX.navy);
  s.addText([
    { text: "High-cardinality categories → smoothed target encoding.  ", options: { bold: true, color: "FFFFFF" } },
    { text: "Origin, destination, route, origin×hour and carrier×origin become their historical delay rate, fitted on the training split only.", options: { color: "C9D6E3" } },
  ], { isTextBox: true, x: MX + 0.35, y: 5.25, w: W - 2 * MX - 0.7, h: 1.15, fontSize: 15, valign: "middle", margin: 0 });
  notes(s, `[4:50-5:35] I built four groups of features, all known in advance. Calendar and time, including how close the date is to a public holiday. Basic flight details. Congestion: how many flights are scheduled at the same airport in the same hour. And the one I think is most interesting: aircraft rotation. Using a Spark window function over each tail number, I know which leg of the day this is and how much scheduled turnaround time it has, because delays roll forward through the day. Airports and routes have thousands of values, so I replaced them with their historical delay rate, fitted on the training data only.`);

  // 9. Models -----------------------------------------------------------------------
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Method" });
  s.addText("Three Spark MLlib classifiers, one fair setup", { placeholder: "title" });
  const mdl = [
    [fa.FaChartLine, "Logistic Regression", "Linear baseline; interpretable coefficients", "Gradient summed across partitions: scales almost linearly"],
    [fa.FaTree, "Random Forest", "Many decorrelated trees, averaged", "Trees are independent: easy to parallelise"],
    [fa.FaLayerGroup, "Gradient-Boosted Trees", "Trees added in sequence, each fixing the last", "Sequential rounds: hardest to scale"],
  ];
  const mw = (W - 2 * MX - 2 * 0.3) / 3;
  for (let i = 0; i < 3; i++) {
    const x = MX + i * (mw + 0.3);
    card(s, x, 1.45, mw, 3.2, `model-${i}`);
    await iconCircle(s, mdl[i][0], x + 0.3, 1.7, 0.8, MODEL_HEX[i], `model-icon-${i}`);
    s.addText(mdl[i][1], { isTextBox: true, x: x + 1.25, y: 1.8, w: mw - 1.45, h: 0.6, fontSize: 19, bold: true, color: C.text1, margin: 0, valign: "middle" });
    s.addText(mdl[i][2], { isTextBox: true, x: x + 0.3, y: 2.75, w: mw - 0.6, h: 0.8, fontSize: 15, color: C.text1, margin: 0 });
    s.addText(mdl[i][3], { isTextBox: true, x: x + 0.3, y: 3.6, w: mw - 0.6, h: 0.9, fontSize: 13, italic: true, color: C.accent6, margin: 0 });
  }
  const method = [["Split", "70 / 10 / 20 train, validation, test; plus a temporal test (Jan-Sep → Oct-Dec)"],
    ["Imbalance", "Class weights via weightCol + decision threshold tuned on validation for F1"],
    ["Tuning", "3-fold CrossValidator optimising PR-AUC; best settings refitted"]];
  method.forEach(([k, v], i) => {
    const y = 4.95 + i * 0.5;
    s.addText(k, { isTextBox: true, x: MX, y, w: 1.6, h: 0.45, fontSize: 15, bold: true, color: C.accent2, margin: 0 });
    s.addText(v, { isTextBox: true, x: MX + 1.7, y, w: 10.4, h: 0.45, fontSize: 15, color: C.text1, margin: 0 });
  });
  notes(s, `[5:35-6:20] I compared three models from Spark MLlib, all using exactly the same features. Logistic regression is the simple, explainable baseline. Random forest builds many trees independently. Gradient-boosted trees build them one after another, each fixing the last one's mistakes. That also affects scaling: boosting is the hardest to parallelise. Because only about one flight in five is delayed, I used class weights and chose the decision threshold on a separate validation set. Each model was tuned with 3-fold cross-validation, optimising PR-AUC.`);

  // 10. Results ------------------------------------------------------------------------
  pres.addSection({ title: "Results" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
  s.addText("Results on the held-out test set", { placeholder: "title" });
  const metricKeys = [["PRECISION", "Precision"], ["RECALL", "Recall"], ["F1", "F1"], ["ROC_AUC", "ROC-AUC"], ["PR_AUC", "PR-AUC"]];
  if (SHORT.every((m) => has(`${m}_F1`))) {
    s.addChart(pres.charts.BAR, SHORT.map((m, i) => ({ name: MODELS[i], labels: metricKeys.map((k) => k[1]), values: metricKeys.map((k) => num(`${m}_${k[0]}`)) })), {
      x: MX, y: 1.4, w: 7.3, h: 5.0, ...chartBase(), barDir: "col", barGrouping: "clustered", title: "Test-set metrics (delayed = positive class)",
      chartColors: MODEL_HEX, showLegend: true, legendPos: "b", valAxisMinVal: 0, valAxisMaxVal: 1, valAxisLabelFormatCode: "0.0",
      barGapWidthPct: 60, objectName: "chart-metrics" });
  } else placeholderBox(s, MX, 1.4, 7.3, 5.0, "Native chart: precision, recall, F1, ROC-AUC, PR-AUC per model\n(rebuild with notebook outputs)", "ph-metrics");
  const rows = [["", "Acc.", "F1", "AUC", "Train"]].concat(SHORT.map((m, i) => [MODELS[i], V(`${m}_ACCURACY`), V(`${m}_F1`), V(`${m}_ROC_AUC`), has(`${m}_TRAIN_S`) ? `${V(`${m}_TRAIN_S`)} s` : V(`${m}_TRAIN_S`)]));
  rows.push(["Always 'on time'", V("BASELINE_ACCURACY"), "0.000", "0.500", "-"]);
  s.addTable(rows.map((r, ri) => r.map((c, ci) => ({ text: c, options: {
    bold: ri === 0 || ci === 0, color: ri === 0 ? "FFFFFF" : (ci === 0 && ri > 0 && ri < 4 ? MODEL_HEX[ri - 1] : HEX.navy),
    fill: { color: ri === 0 ? HEX.navy : (ri % 2 ? "FFFFFF" : HEX.ice) }, align: ci === 0 ? "left" : "right", fontSize: 13,
    highlight: /^\[/.test(c) ? "FFFF00" : undefined } }))), {
    x: 8.15, y: 1.5, w: 4.58, colW: [1.9, 0.68, 0.66, 0.66, 0.68], rowH: 0.48, border: { type: "solid", pt: 0.5, color: HEX.grid }, margin: 0.05, objectName: "results-table" });
  txt(s, "Best F1: {{BEST_F1_MODEL}} ({{BEST_F1_VALUE}})\nFastest to train: {{FASTEST_MODEL}}", { x: 8.15, y: 4.75, w: 4.58, h: 1.4, fontSize: 15, bold: true, color: C.text1 });
  notes(s, `[6:20-7:15] These are the test results. [BEST_F1_MODEL] had the best F1, [BEST_F1_VALUE], and [BEST_AUC_MODEL] the best ROC-AUC. Notice the last row: a "model" that always says on time gets [BASELINE_ACCURACY] accuracy and catches zero delays. That's why accuracy alone is misleading here, and why I focus on recall, F1 and PR-AUC. On training time, [FASTEST_MODEL] was quickest and [SLOWEST_MODEL] slowest. [CHECK: one sentence on whether the extra accuracy of the tree models is worth the training cost.]`);

  // 11. Insights ------------------------------------------------------------------------
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
  s.addText("What drives the predictions, and do they hold up?", { placeholder: "title" });
  const imp = csv("feature_importance.csv");
  if (imp) {
    const top = imp.filter((r) => r.model === "Gradient-Boosted Trees").sort((a, b) => b.importance - a.importance).slice(0, 8);
    s.addChart(pres.charts.BAR, [{ name: "Importance", labels: top.map((r) => r.feature), values: top.map((r) => +(+r.importance).toFixed(3)) }], {
      x: MX, y: 1.4, w: 6.1, h: 5.0, ...chartBase(), barDir: "bar", title: "GBT: top 8 features (impurity importance)", chartColors: [HEX.gbt],
      showLegend: false, showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", catAxisOrientation: "maxMin",
      valAxisHidden: true, valGridLine: { style: "none" }, barGapWidthPct: 40, catAxisLabelFontSize: 10, objectName: "chart-importance" });
  } else placeholderBox(s, MX, 1.4, 6.1, 5.0, "Native chart: GBT top-8 feature importance\n(rebuild with notebook outputs: tables/feature_importance.csv)", "ph-importance");
  if (SHORT.every((m) => has(`${m}_TEMPORAL_ROC_AUC`))) {
    s.addChart(pres.charts.BAR, [
      { name: "Random split", labels: SHORT, values: SHORT.map((m) => num(`${m}_ROC_AUC`)) },
      { name: "Temporal (Oct-Dec)", labels: SHORT, values: SHORT.map((m) => num(`${m}_TEMPORAL_ROC_AUC`)) },
    ], { x: 6.95, y: 1.4, w: 5.78, h: 5.0, ...chartBase(), barDir: "col", barGrouping: "clustered", title: "ROC-AUC: random vs temporal test",
      chartColors: [HEX.navy2, HEX.sky], showLegend: true, legendPos: "b", showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000",
      valAxisMinVal: 0.5, valAxisMaxVal: 1, valAxisLabelFormatCode: "0.0", barGapWidthPct: 60, objectName: "chart-temporal" });
  } else placeholderBox(s, 6.95, 1.4, 5.78, 5.0, "Native chart: ROC-AUC random vs temporal split\n(rebuild with notebook outputs)", "ph-temporal");
  notes(s, `[7:15-8:05] On the left, the features the boosted model relied on most: [GBT_TOP_FEATURE_1], [GBT_TOP_FEATURE_2] and [GBT_TOP_FEATURE_3]. [CHECK: one sentence on why these make sense, e.g. route and time-of-day history, rotation.] I also checked this with permutation importance, which [agrees / partly agrees]. On the right is the stricter test: train on January to September, predict October to December. A random split lets the model see the same storm days in training and test, so the temporal score is the honest one for real use. [Describe the size of the drop.]`);

  // 12. Discussion ----------------------------------------------------------------------
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
  s.addText("Discussion", { placeholder: "title" });
  const disc = [
    [fa.FaExclamationTriangle, "The accuracy trap", "Doing nothing already scores {{BASELINE_ACCURACY}} accuracy. Recall, F1 and PR-AUC are what show real skill.", HEX.rf],
    [fa.FaSlidersH, "Threshold is a business choice", "Spare-crew planning tolerates false alarms; passenger alerts need precision. Tune per use case.", HEX.lr],
    [fa.FaStopwatch, "Accuracy vs cost", "{{FASTEST_MODEL}} trains fastest; {{SLOWEST_MODEL}} is slowest. Boosting is hardest to scale out.", HEX.gbt],
  ];
  for (let i = 0; i < 3; i++) {
    const x = MX + i * (mw + 0.3);
    card(s, x, 1.45, mw, 3.55, `disc-${i}`);
    await iconCircle(s, disc[i][0], x + 0.3, 1.7, 0.8, disc[i][3], `disc-icon-${i}`);
    s.addText(disc[i][1], { isTextBox: true, x: x + 0.3, y: 2.7, w: mw - 0.6, h: 0.55, fontSize: 19, bold: true, color: C.text1, margin: 0 });
    txt(s, disc[i][2], { x: x + 0.3, y: 3.3, w: mw - 0.6, h: 1.6, fontSize: 15, color: C.accent6 });
  }
  s.addText("Limitations", { isTextBox: true, x: MX, y: 5.25, w: 2.0, h: 0.4, fontSize: 16, bold: true, color: C.accent2, margin: 0 });
  s.addText("No weather data  ·  aircraft swaps on the day may leak slightly through tail numbers  ·  in-sample target encoding  ·  trained on a sample, 1 year, Colab-sized grids",
    { isTextBox: true, x: MX, y: 5.65, w: W - 2 * MX, h: 0.75, fontSize: 14, color: C.text1, margin: 0 });
  notes(s, `[8:05-8:55] Three things I took away. First, the accuracy trap: doing nothing already scores [BASELINE_ACCURACY], so you have to look at recall and F1. Second, where you set the threshold is really a business decision. If you're positioning spare crews you can live with false alarms, but if you're texting passengers you need precision. Third, accuracy versus cost: [FASTEST_MODEL] trains fastest, and boosting is the hardest to scale. The main limitations are no weather data, possible small leakage from same-day aircraft swaps, and training on a sample because of Colab limits.`);

  // 13. Conclusion & future work ----------------------------------------------------------
  pres.addSection({ title: "Close" });
  s = pres.addSlide({ masterName: "SECTION_DARK", sectionTitle: "Close" });
  s.addText("Conclusion and future work", { placeholder: "title" });
  s.addText("What I showed", { isTextBox: true, x: MX, y: 1.5, w: 5.8, h: 0.5, fontSize: 20, bold: true, color: "FFB48F", margin: 0 });
  bullets(s, [
    "A leakage-free Spark pipeline over all {{RAW_ROWS}} 2025 flights",
    "{{BEST_F1_MODEL}} gave the best F1 ({{BEST_F1_VALUE}})",
    "Class weights + tuned threshold matter more than raw accuracy",
    "Parquet, broadcast joins and in-Spark evaluation made it run on free Colab",
  ], { x: MX, y: 2.1, w: 5.8, h: 4.2, fontSize: 19, color: "FFFFFF" });
  const fut = [[fa.FaCloudSunRain, "Join NOAA weather forecasts"], [fa.FaMicrochip, "XGBoost / LightGBM on Spark with GPUs"],
    [fa.FaServer, "Full data on a Dataproc cluster, bigger grids"], [fa.FaStream, "Structured Streaming for day-of updates"], [fa.FaFilter, "Out-of-fold target encoding"]];
  s.addText("Next steps", { isTextBox: true, x: 7.2, y: 1.5, w: 5.5, h: 0.5, fontSize: 20, bold: true, color: "FFB48F", margin: 0 });
  for (let i = 0; i < fut.length; i++) {
    const y = 2.15 + i * 0.82;
    await iconCircle(s, fut[i][0], 7.2, y, 0.6, HEX.navy2, `fut-${i}`);
    s.addText(fut[i][1], { isTextBox: true, x: 8.0, y, w: 4.7, h: 0.6, fontSize: 16, color: "FFFFFF", valign: "middle", margin: 0 });
  }
  notes(s, `[8:55-9:40] To wrap up: I built a full, leakage-free Spark pipeline over every 2025 U.S. domestic flight, and [BEST_F1_MODEL] performed best on F1. The biggest lessons were about evaluation, not algorithms: handling the imbalance and choosing the threshold mattered more than chasing accuracy. Next, I would add weather forecasts, which is the biggest missing signal, try XGBoost on GPUs, run the full data on a real cluster, and use Spark streaming to update predictions on the day as earlier flights report delays.`);

  // 14. Questions -----------------------------------------------------------------------
  s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Close" });
  s.addText("Thank you. Questions?", { placeholder: "title" });
  s.addText([
    { text: "Key references", options: { bold: true, color: "FFB48F", breakLine: true } },
    { text: "Ball et al. (2010) Total delay impact study · Bureau of Transportation Statistics (2026) On-Time Performance data · Kaufman et al. (2012) Leakage in data mining · Meng et al. (2016) MLlib · Saito & Rehmsmeier (2015) PR vs ROC · Zaharia et al. (2016) Apache Spark", options: { fontSize: 12, color: "C9D6E3" } },
  ], { placeholder: "body" });
  await iconCircle(s, fa.FaQuestion, 9.9, 2.3, 2.4, HEX.rf, "q");
  notes(s, `[9:40-10:00] Thank you, I'm happy to take questions.

LIKELY QUESTIONS (prepare, don't read):
- Why not use departure delay? It's only known after the plane leaves, so the model would be useless for planning, and it inflates accuracy (leakage).
- Why is accuracy not enough? Always predicting "on time" already gets [BASELINE_ACCURACY]; we care about catching delays (recall) without too many false alarms (precision).
- Why target encoding? Hundreds of airports and thousands of routes; one-hot would explode the feature space and Spark trees need maxBins >= categories. Fitted on training data only.
- Why did you sample the training data? Colab has 2 cores and ~12 GB RAM; validation and test were always scored in full. On a cluster I'd use everything.
- How would this scale? Same code, different master URL; LR and RF parallelise well, GBT is sequential across rounds. GPUs via RAPIDS or XGBoost-Spark.
- Could tail numbers leak? Slightly: aircraft can be swapped on the day. In production you'd use the planned rotation from the airline's schedule.
- Why PR-AUC for tuning? With a rare positive class, PR-AUC reflects performance on delays better than ROC-AUC.`);

  fs.mkdirSync(path.dirname(OUT_FILE), { recursive: true });
  await pres.writeFile({ fileName: OUT_FILE });
  await applyTheme(OUT_FILE, THEME);
  console.log(`wrote ${OUT_FILE}  (placeholders filled: ${Object.keys(PH).length})`);
})();
