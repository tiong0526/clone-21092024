// Builds the CW2 Part 2 technical report (.docx).
//   node build_report.js [outputsDir] [out.docx]
// outputsDir = the notebook's FlightDelay2025_outputs folder (downloaded from Drive). When given, every
// {{PLACEHOLDER}} is filled from report_placeholders.json and the notebook figures are embedded.
// Anything not available stays as a yellow-highlighted [PLACEHOLDER] so it is easy to spot.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell, WidthType,
  ShadingType, BorderStyle, ImageRun, LevelFormat, PageBreak, Footer, PageNumber, TableOfContents,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = process.argv[2] ? path.resolve(process.argv[2]) : null;
const OUT_FILE = process.argv[3] || path.join(ROOT, "report", "BDMLA_CW2_Part2_Flight_Delay_Report.docx");
let PH = {};
if (OUT_DIR && fs.existsSync(path.join(OUT_DIR, "report_placeholders.json"))) {
  PH = JSON.parse(fs.readFileSync(path.join(OUT_DIR, "report_placeholders.json"), "utf8"));
}
const PAGE_W = 11906, MARGIN = 1300, CONTENT_W = PAGE_W - 2 * MARGIN; // A4, DXA
const FONT = "Calibri", MONO = "Courier New";
const BLUE = "1F4E79", MUTED = "595959", LIGHT = "F2F2F2", HEAD_FILL = "DCE6F2";
let MAIN_WORDS = 0, COUNTING = false;

// ---------- inline parser: **bold**, *italic*, {{PLACEHOLDER}}, [[CHECK: note]] ----------
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|\{\{[A-Z0-9_]+\}\}|\[\[[^\]]+\]\])/g;
  let last = 0, m;
  const push = (t, o = {}) => { if (t) out.push(new TextRun({ text: t, font: FONT, ...base, ...o })); };
  while ((m = re.exec(text))) {
    push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) push(tok.slice(2, -2), { bold: true });
    else if (tok.startsWith("{{")) {
      const key = tok.slice(2, -2);
      if (PH[key] !== undefined) push(String(PH[key]));
      else push(`[${key}]`, { highlight: "yellow" });
    } else if (tok.startsWith("[[")) push(`[${tok.slice(2, -2)}]`, { highlight: "yellow", italics: true, color: "7F6000" });
    else push(tok.slice(1, -1), { italics: true });
    last = m.index + tok.length;
  }
  push(text.slice(last));
  if (COUNTING) MAIN_WORDS += text.replace(/\[\[[^\]]+\]\]/g, "").split(/\s+/).filter(Boolean).length;
  return out;
}
const P = (t, o = {}) => new Paragraph({ children: runs(t), spacing: { after: 140, line: 288 }, alignment: AlignmentType.JUSTIFIED, ...o });
const H1 = (t) => { if (COUNTING) MAIN_WORDS += t.split(/\s+/).length; return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t, font: FONT })] }); };
const H2 = (t) => { if (COUNTING) MAIN_WORDS += t.split(/\s+/).length; return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t, font: FONT })] }); };
const B = (t, level = 0) => new Paragraph({ numbering: { reference: "bullets", level }, children: runs(t), spacing: { after: 60, line: 276 } });
const N = (t) => new Paragraph({ numbering: { reference: "numbers", level: 0 }, children: runs(t), spacing: { after: 60, line: 276 } });
const caption = (t) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 60, after: 200 },
  children: (() => { const c = COUNTING; COUNTING = false; const r = runs(t, { size: 18, color: MUTED, italics: true }); COUNTING = c; return r; })() });

function code(lines) {
  const c = COUNTING; COUNTING = false; // code extracts are not counted as prose
  const paras = lines.map((l, i) => new Paragraph({
    shading: { type: ShadingType.CLEAR, fill: LIGHT, color: "auto" },
    spacing: { after: 0, before: i === 0 ? 80 : 0, line: 240 }, indent: { left: 200, right: 200 },
    children: [new TextRun({ text: l || " ", font: MONO, size: 16 })],
  }));
  paras.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
  COUNTING = c;
  return paras;
}

const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };
function table(headers, rows, widths, opts = {}) {
  const c = COUNTING; COUNTING = false; // tables are excluded from the word count
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (text, w, head, i) => new TableCell({
    borders, width: { size: w, type: WidthType.DXA },
    shading: head ? { type: ShadingType.CLEAR, fill: HEAD_FILL, color: "auto" }
      : (opts.highlightRow === i ? { type: ShadingType.CLEAR, fill: "F7F7F7", color: "auto" } : undefined),
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ keepNext: true, keepLines: true, alignment: (!head && /^[\d\[{]/.test(text) && opts.numericRight !== false) ? AlignmentType.RIGHT : AlignmentType.LEFT,
      children: runs(text, { size: 18, bold: head })})],
  });
  const t = new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, cantSplit: true, children: headers.map((h, i) => cell(h, widths[i], true)) }),
      ...rows.map((r, ri) => new TableRow({ cantSplit: true, children: r.map((v, i) => cell(String(v), widths[i], false, ri)) }))],
  });
  COUNTING = c;
  return t;
}

function figure(file, cap, widthIn = 6.2) {
  const candidates = [path.join(ROOT, "assets", file), OUT_DIR && path.join(OUT_DIR, "figures", file)].filter(Boolean);
  const found = candidates.find((p) => fs.existsSync(p));
  if (!found) {
    return [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120 },
      border: { top: border, bottom: border, left: border, right: border },
      shading: { type: ShadingType.CLEAR, fill: "FFF9E6", color: "auto" },
      children: [new TextRun({ text: `[Insert figure: outputs/figures/${file}]`, font: FONT, highlight: "yellow" })] }), caption(cap)];
  }
  const buf = fs.readFileSync(found);
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20); // PNG header
  const px = widthIn * 96;
  return [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120 }, keepNext: true,
    children: [new ImageRun({ type: "png", data: buf, transformation: { width: px, height: px * h / w },
      altText: { title: cap, description: cap, name: file } })] }), caption(cap)];
}

// =====================================================================================
function buildBody() {
const body = [];
const add = (...x) => x.flat().forEach((e) => body.push(e));

// ---------- title page ----------
add(
  new Paragraph({ spacing: { before: 1800, after: 200 }, alignment: AlignmentType.LEFT,
    children: [new TextRun({ text: "Predicting Airline Flight Delays Using Apache Spark", font: FONT, size: 48, bold: true, color: BLUE })] }),
  new Paragraph({ spacing: { after: 600 }, children: [new TextRun({ text: "A Comparative Study of Machine Learning Classifiers on the 2025 BTS On-Time Performance Data", font: FONT, size: 28, color: MUTED })] }),
  P("**Module:** M33877 Big Data and Machine Learning Applications", { alignment: AlignmentType.LEFT }),
  P("**Assessment:** Coursework Item 2, Part 2: Big Data Applications Project (technical report)", { alignment: AlignmentType.LEFT }),
  P("**Student:** Kelvin Soh      **Student ID:** {{STUDENT_ID}}", { alignment: AlignmentType.LEFT }),
  P("**Lecturer:** Ms Aarushi Vadhavkar", { alignment: AlignmentType.LEFT }),
  P("**Word count (main text, sections 1 to 8):** {{WORD_COUNT}} words, excluding tables, figure captions, code extracts, references and appendices", { alignment: AlignmentType.LEFT }),
  P("**Source code:** BDMLA_Flight_Delay_Spark.ipynb (Google Colab, PySpark {{SPARK_VERSION}}), submitted in the accompanying .zip file", { alignment: AlignmentType.LEFT }),
  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ children: [new TextRun({ text: "Contents", font: FONT, size: 28, bold: true, color: BLUE })], spacing: { after: 120 } }),
  new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
  new Paragraph({ children: [new PageBreak()] }),
);

// ---------- Abstract ----------
add(H1("Abstract"),
  P("Flight delays are costly for airlines and passengers, and much of that cost comes from not knowing in advance which flights will run late. In this project I used Apache Spark to process all twelve monthly 2025 files of the U.S. Bureau of Transportation Statistics on-time dataset ({{RAW_ROWS}} flights) and to predict whether a flight will arrive at least 15 minutes late using schedule information only. Columns recorded during or after the flight were excluded, and Logistic Regression, Random Forest and Gradient-Boosted Trees were trained and tuned with Spark MLlib. On a random test split, {{BEST_F1_MODEL}} gave the best F1 ({{BEST_F1_VALUE}}) and ROC-AUC ({{GBT_ROC_AUC}}). On a stricter test using later months, all models dropped and Random Forest had the highest F1, which shows that the preferred model depends on how it is evaluated."),
);

COUNTING = true;
// ---------- 1 Introduction ----------
add(H1("1. Introduction"),
  H2("1.1 Background"),
  P("Flight delays cost the U.S. economy an estimated $32.9 billion in 2007 (Ball et al., 2010); this historical figure gives context rather than a current cost. The Bureau of Transportation Statistics (BTS) counts a flight as *delayed* when it arrives 15 or more minutes late, and publishes a record for every domestic flight of the larger U.S. carriers. I selected this dataset because it contains several million flight records, giving me the opportunity to apply Spark to a substantial data-processing task rather than a sample that would fit comfortably in pandas."),
  H2("1.2 Problem statement"),
  P("The question is: **using only information known before the aircraft leaves the gate, can we predict whether a flight will arrive 15 or more minutes late?** This is binary classification (DELAYED = 1 if ARR_DELAY ≥ 15). Many public notebooks on this data report high accuracy only because they use departure delay or other post-flight columns, which makes the model useless in practice (Kaufman et al., 2012). A schedule-only model could be run the evening before to help plan crews and spare aircraft."),
  H2("1.3 Objectives"),
  N("Build a scalable Spark pipeline that ingests, unions and cleans all twelve monthly files for 2025."),
  N("Engineer features from schedule information only, excluding columns recorded during or after the flight."),
  N("Train, tune and compare three Spark MLlib classifiers: Logistic Regression, Random Forest and Gradient-Boosted Trees."),
  N("Evaluate them with metrics that are suitable for an imbalanced target, together with training time."),
  N("Show how the approach would scale out to more processors, a cluster or GPUs."),
);

// ---------- 2 Related work ----------
add(H1("2. Related Work"),
  P("Sternberg et al. (2017) found that most delay studies use classification, with tree models and congestion features recurring. Rebollo and Balakrishnan (2014) and Gui et al. (2020) found random forests strong, and Belcastro et al. (2016) built a scalable MapReduce pipeline joining flight and weather data. Both random forests (Breiman, 2001) and gradient boosting (Friedman, 2001) are available in Spark MLlib (Meng et al., 2016). This project adds a strict pre-departure feature policy, aircraft-rotation features and a temporal evaluation on the latest full year."),
);

// ---------- 3 Dataset ----------
add(H1("3. Dataset Selection, Exploration and Preparation"),
  H2("3.1 Source and rationale"),
  P("The data is the BTS *Reporting Carrier On-Time Performance* table (Bureau of Transportation Statistics, 2026): one row per domestic flight, with date, carrier, tail number, airports, scheduled and actual times, cancellation and diversion flags, and delay minutes by cause. I downloaded the twelve 2025 monthly CSVs (220 to 280 MB each, about 3 GB) to Google Drive. At {{RAW_ROWS}} rows with an industry-standard label, it is large enough to justify Spark while remaining workable in Colab."),
  ...figure("01_class_balance.png", "Figure 1. Class balance after cleaning (DELAYED = 1 when ARR_DELAY ≥ 15 minutes).", 4.6),
  H2("3.2 Exploration"),
  P("After cleaning, {{DELAY_RATE}} of flights are delayed (Figure 1), so the data is imbalanced: always predicting \"on time\" would score {{BASELINE_ACCURACY}} accuracy. Delays peak in July (about 29%) and December and are lowest in September (about 17%); Sundays are worst, and airlines range from about 17% to 28% (Figure 2). The clearest pattern is by hour: about 9% of 5am departures arrive late, against about 33% at 7pm, consistent with delays carrying over to later legs. Figure 3 supports this: an aircraft's first leg is late about 15% of the time and its seventh about 34%, and turnarounds under 40 minutes have a 38% delay rate, against about 21% for 60 to 179 minutes."),
  ...figure("03_delay_rate_patterns.png", "Figure 2. Delay rate by month, day of week, scheduled departure hour and reporting airline."),
  ...figure("04_airport_and_rotation_patterns.png", "Figure 3. Delay rate at the 20 busiest origin airports, by scheduled turnaround, and by aircraft leg of the day."),
  H2("3.3 Cleaning"),
  P("Cancelled and diverted flights were removed because they have no arrival-delay label, then null ARR_DELAY rows, duplicates and impossible schedule values (Table 1). Missing tail numbers were kept, with a neutral rotation value and a HAS_PREV_LEG flag."),
  table(["Step", "Rows remaining", "Rows removed"], [
    ["Raw flights (12 files)", "{{FUNNEL_0_ROWS}}", "-"],
    ["Remove cancelled", "{{FUNNEL_1_ROWS}}", "{{FUNNEL_1_REMOVED}}"],
    ["Remove diverted", "{{FUNNEL_2_ROWS}}", "{{FUNNEL_2_REMOVED}}"],
    ["Remove null ARR_DELAY", "{{FUNNEL_3_ROWS}}", "{{FUNNEL_3_REMOVED}}"],
    ["Remove duplicates", "{{FUNNEL_4_ROWS}}", "{{FUNNEL_4_REMOVED}}"],
    ["Remove invalid schedule values", "{{FUNNEL_5_ROWS}}", "{{FUNNEL_5_REMOVED}}"],
  ], [4300, 2300, 2300]),
  caption("Table 1. Cleaning funnel (from tables/cleaning_funnel.csv)."),
  H2("3.4 Reducing target leakage"),
  P("Leakage was the main risk, so I tried to control it at three levels. First, an **allow-list** loads only 17 of the 110 raw columns, so post-flight fields never enter the DataFrame; I also excluded **DEP_TIME, DEP_DELAY, TAXI_OUT and DEP_DEL15**, which are unknown before departure, and ARR_DELAY is dropped once the label is built. Second, an assertion checks the features against the forbidden columns (Appendix C). Third, schedule counts such as flights per hour are computed **before cancellations are removed**; otherwise a stormy day would look quiet and the feature would encode the outcome. This removes direct post-flight predictors, but does not make the features completely leakage-free (Section 7.1)."),
);

// ---------- 4 Framework ----------
add(H1("4. Big Data Framework and Architecture"),
  P("Figure 4 shows the pipeline. Everything runs in Google Colab with PySpark {{SPARK_VERSION}}, using the DataFrame/Spark SQL API for data processing and Spark MLlib for modelling."),
  ...figure("architecture_pipeline.png", "Figure 4. End-to-end architecture of the Spark pipeline."),
  P("Spark turns a job into a DAG of stages, each made of parallel tasks, one per data partition (Zaharia et al., 2016). Because transformations are lazy, the Catalyst optimiser sees the whole query and can push the column allow-list down to the file scan (Armbrust et al., 2015). In Colab the driver and executor share one VM ({{N_CORES}} cores) in *local mode* (Figure 5). The same code runs on a YARN or Kubernetes cluster by changing the master URL."),
  ...figure("spark_architecture.png", "Figure 5. Spark execution model: in Colab the driver and executor share one VM; on a cluster, tasks are spread across executors.", 5.6),
  P("These optimisations made a full year practical on free Colab:"),
  B("**CSV to Parquet once:** the same aggregation took {{CSV_SECONDS}} s on CSV and {{PARQUET_SECONDS}} s on Parquet ({{PARQUET_SPEEDUP}} faster), and the Drive copy acts as a checkpoint."),
  B("**Fewer shuffle partitions** plus Adaptive Query Execution, **broadcast joins** for the encoding tables and **caching** of model-ready data."),
  B("**Single-pass evaluation:** confusion matrices and F1 for 37 thresholds are each one Spark aggregation."),
  H2("4.1 Scale-out"),
  P("As an exploratory local benchmark, the notebook times the same workload once with 1 and {{SCALE_MAX_CORES}} cores. A full aggregation went from {{SCALE_AGG_1CORE_S}} s to {{SCALE_AGG_NCORE_S}} s ({{SCALE_AGG_SPEEDUP}}), but the 1-core run went first, so warmer caches probably explain part of this; repeated runs with median timings would be needed for a firm claim. A Logistic Regression fit on a cached 20% sample barely changed ({{SCALE_LR_SPEEDUP}}), as each iteration is a short, overhead-dominated job. On Dataproc or Databricks the notebook would run unchanged with more executors, and RAPIDS and XGBoost's Spark integration offer GPU acceleration (Chen & Guestrin, 2016)."),
);

// ---------- 5 Methodology ----------
add(H1("5. Methodology and Implementation"),
  H2("5.1 Feature engineering"),
  P("I ended up with {{N_FEATURES}} features in four groups (the full list is in Appendix B):"),
  B("**Calendar and time:** month, day, weekday, weekend flag, scheduled departure and arrival hour (with sine/cosine encodings) and days to the nearest federal holiday."),
  B("**Flight:** scheduled elapsed time, distance and airline (one-hot, about 15 carriers)."),
  B("**Congestion (from the schedule):** scheduled departures and arrivals at the airport in the same hour, and daily airport and carrier volume."),
  B("**Aircraft rotation:** the leg of the day for that tail number and the scheduled turnaround time since its previous leg, computed with a window function:"),
  ...code([
    'w_tail = Window.partitionBy("TAIL_NUM", "FLIGHT_DATE").orderBy("CRS_DEP_MIN")',
    'df = (df.withColumn("TAIL_LEG_OF_DAY", F.row_number().over(w_tail))',
    '        .withColumn("SCHED_TURNAROUND_MIN",',
    '                    F.col("CRS_DEP_MIN") - F.lag("CRS_ARR_MIN").over(w_tail)))',
  ]),
  P("The turnaround is the difference between two scheduled times at the same airport (the previous arrival and the next departure), so both are in that airport's local time, as BTS records them. Legs are ordered by local departure time within each calendar day. This could misorder rare cases with large time-zone differences, it does not check that the previous destination matches the current origin, and a leg whose previous arrival crosses midnight is treated as having no previous leg."),
  P("ORIGIN, DEST, ROUTE (thousands of pairs), origin-by-hour and carrier-by-origin have too many categories for one-hot encoding under Spark's maxBins limit, so each became a **smoothed target encoding** (Micci-Barreca, 2001), TE = (n·mean + m·prior)/(n + m) with m = 100, fitted on the training split only."),
  H2("5.2 Splitting, imbalance and evaluation"),
  P("The data was split randomly 70/10/20 into train, validation and test. Because of Colab limits, models were fitted on a {{TRAIN_SAMPLE_PCT}} sample of the training split ({{TRAIN_ROWS_USED}} rows); validation and test ({{TEST_ROWS}} rows) were scored in full. For the imbalance (He & Garcia, 2009) I used **class weights** w = N/(2·N_class) and tuned the **decision threshold** on validation to maximise F1."),
  P("**Accuracy alone is misleading here**, so a majority-class baseline is reported. The useful measures are **precision** (the cost of false alarms), **recall** (delays caught) and **F1**, their balance, plus **ROC-AUC** for ranking across thresholds and **PR-AUC**, which is more informative when positives are rare (Saito & Rehmsmeier, 2015). Training time is included because scalability is part of the brief."),
  H2("5.3 Models and tuning"),
  P("All three models share one standardised feature vector. **Logistic Regression** is the interpretable linear baseline, **Random Forest** averages decorrelated trees, and **Gradient-Boosted Trees** add trees sequentially, each correcting the last. Each was tuned with CrossValidator (3-fold, PR-AUC) on a training sample (Table 2) and refitted on the full training sample. The target encoders were fitted on the whole training split before cross-validation, so the held-out folds were not fully independent of the encoding; CV scores may be slightly optimistic, although the test set was not affected."),
  table(["Model", "Grid searched (3-fold CV)", "Selected", "CV PR-AUC"], [
    ["Logistic Regression", "regParam {0.0001, 0.001, 0.01} × elasticNet {0, 0.5}", "{{LR_TUNED_PARAMS}}", "{{LR_CV_PR_AUC}}"],
    ["Random Forest", "maxDepth {8, 12} × numTrees {60, 120}", "{{RF_TUNED_PARAMS}}", "{{RF_CV_PR_AUC}}"],
    ["Gradient-Boosted Trees", "maxDepth {4, 6} × stepSize {0.05, 0.1}, 60 iterations", "{{GBT_TUNED_PARAMS}}", "{{GBT_CV_PR_AUC}}"],
  ], [2100, 3700, 2000, 1100], { numericRight: false }),
  caption("Table 2. Hyperparameter grids (searched on a 5% training sample), selected values and mean cross-validated PR-AUC."),
);

// ---------- 6 Results ----------
add(H1("6. Results"),
  P("Table 3 shows the test-set results of the tuned models at the validation-tuned threshold."),
  table(["Model", "Accuracy", "Precision", "Recall", "F1", "ROC-AUC", "PR-AUC", "Train (s)"], [
    ["Majority baseline", "{{BASELINE_ACCURACY}}", "0.000", "0.000", "0.000", "0.500", "-", "-"],
    ["Logistic Regression", "{{LR_ACCURACY}}", "{{LR_PRECISION}}", "{{LR_RECALL}}", "{{LR_F1}}", "{{LR_ROC_AUC}}", "{{LR_PR_AUC}}", "{{LR_TRAIN_S}}"],
    ["Random Forest", "{{RF_ACCURACY}}", "{{RF_PRECISION}}", "{{RF_RECALL}}", "{{RF_F1}}", "{{RF_ROC_AUC}}", "{{RF_PR_AUC}}", "{{RF_TRAIN_S}}"],
    ["Gradient-Boosted Trees", "{{GBT_ACCURACY}}", "{{GBT_PRECISION}}", "{{GBT_RECALL}}", "{{GBT_F1}}", "{{GBT_ROC_AUC}}", "{{GBT_PR_AUC}}", "{{GBT_TRAIN_S}}"],
  ], [2180, 1000, 1000, 900, 850, 1000, 950, 1020]),
  caption("Table 3. Test-set performance (delayed = positive class). Thresholds: LR {{LR_THRESHOLD}}, RF {{RF_THRESHOLD}}, GBT {{GBT_THRESHOLD}}."),
  P("On the random test split, {{BEST_F1_MODEL}} achieved the highest F1 and ROC-AUC; {{FASTEST_MODEL}} was fastest and {{SLOWEST_MODEL}} slowest to train. Both tree models achieved higher ROC-AUC than Logistic Regression ({{LR_ROC_AUC}}), which suggests that feature interactions help to predict delays. GBT beat Random Forest on every threshold-free metric in under a quarter of the training time; tuning lifted Random Forest from {{RF_BASE_ROC_AUC}} to {{RF_ROC_AUC}} but doubled its training time. In practical terms, GBT identifies about 60% of delayed flights (recall {{GBT_RECALL}}), but with a precision of {{GBT_PRECISION}} roughly six in ten of its alerts are false alarms, and it misses about 40% of delays."),
  ...figure("06_model_metrics.png", "Figure 6. Test-set metrics for the three models; the dashed line is the majority-class accuracy."),
  ...figure("08_roc_pr_curves.png", "Figure 7. ROC and precision-recall curves on the test set."),
  ...figure("09_confusion_matrices.png", "Figure 8. Confusion matrices at each model's validation-tuned threshold."),
  ...figure("07_training_time.png", "Figure 9. Training time on the training sample.", 4.8),
  P("Figure 10 shows the most important features; in GBT the top three were {{GBT_TOP_FEATURE_1}}, {{GBT_TOP_FEATURE_2}} and {{GBT_TOP_FEATURE_3}}. Because impurity importance can favour continuous features, I also ran a permutation test (Figure 11). It partly agrees: the origin-airport-by-hour delay rate (TE_ORIGIN_HOUR) and the scheduled turnaround matter most. Importance does not establish causation."),
  ...figure("11_feature_importance.png", "Figure 10. Top features: Logistic Regression coefficients (left), Random Forest and GBT importances."),
  ...figure("12_gbt_permutation_importance.png", "Figure 11. GBT permutation importance: drop in test ROC-AUC when each feature is shuffled.", 4.6),
  P("Finally, Table 4 compares the random split with a stricter **temporal** split, where everything (including the target encoders) is refitted on January to September and tested on October to December. The decision thresholds were reused from the random-split validation set, which includes some October to December flights, so this test is not completely independent; selecting thresholds on September only would be cleaner."),
  table(["Model", "ROC-AUC random", "ROC-AUC temporal", "F1 random", "F1 temporal"], [
    ["Logistic Regression", "{{LR_ROC_AUC}}", "{{LR_TEMPORAL_ROC_AUC}}", "{{LR_F1}}", "{{LR_TEMPORAL_F1}}"],
    ["Random Forest", "{{RF_ROC_AUC}}", "{{RF_TEMPORAL_ROC_AUC}}", "{{RF_F1}}", "{{RF_TEMPORAL_F1}}"],
    ["Gradient-Boosted Trees", "{{GBT_ROC_AUC}}", "{{GBT_TEMPORAL_ROC_AUC}}", "{{GBT_F1}}", "{{GBT_TEMPORAL_F1}}"],
  ], [2500, 1600, 1700, 1500, 1600]),
  caption("Table 4. Random versus temporal (train Jan to Sep, test Oct to Dec) evaluation."),
);

// ---------- 7 Discussion ----------
add(H1("7. Discussion"),
  P("First, the baseline matters: doing nothing gives {{BASELINE_ACCURACY}} accuracy, so F1, recall and PR-AUC are more informative here. Second, the threshold is a business decision: spare-crew planning can accept more false alarms to catch more delays, while a passenger alert needs higher precision."),
  P("I consider the temporal test more relevant to practical use because it evaluates the models on later months excluded from training. ROC-AUC fell to {{GBT_TEMPORAL_ROC_AUC}} for GBT and {{RF_TEMPORAL_ROC_AUC}} for Random Forest, and Random Forest had the higher temporal F1 ({{RF_TEMPORAL_F1}} against {{GBT_TEMPORAL_F1}}), so the preferred model depends on the metric and the setting. Logistic Regression collapsed (recall {{LR_TEMPORAL_RECALL}}); seasonal change and the way its linear month terms extrapolate to unseen months are possible explanations, but an ablation test would be needed to confirm the cause. The high impurity importance of day-of-month and holiday distance suggests the trees partly learned specific bad days under the random split, which does not carry over."),
  P("Schedule-only prediction is possible but limited: most delay causes (weather, air traffic control, knock-on delays) are invisible in the schedule, which caps what any model here can achieve."),
  H2("7.1 Limitations"),
  B("**No weather data.** Weather is a known cause of delay, and earlier work found that adding it improves accuracy (Belcastro et al., 2016)."),
  B("**Tail numbers** record the aircraft that actually flew; same-day aircraft swaps may leak a little information into the rotation features."),
  B("**Rotation features** rely on local scheduled times without a destination-origin check (Section 5.1)."),
  B("**Temporal thresholds** were chosen on a validation set that overlaps October to December."),
  B("**Target encoding and cross-validation:** the encoders were fitted on the training split before cross-validation, so CV scores may be optimistic, and training rows use in-sample encodings. Out-of-fold encoding inside the CV pipeline would address both."),
  B("**Compute limits:** a training sample, small tuning grids and {{N_CORES}} cores."),
  B("**One year** of data, so year-to-year changes (new routes, fleet changes) are not tested."),
  H2("7.2 What I learnt"),
  P("The main things I learnt were about evaluation rather than algorithms. Accuracy was misleading on its own, since predicting \"on time\" for every flight beats every model on it. Leakage was harder to avoid than I expected: excluding post-flight columns was easy, but subtler issues, such as counting flights after removing cancellations or fitting encoders before cross-validation, only became clear on closer inspection. The temporal test also changed my view of which model is best. Practically, my first full run stopped after more than three hours, which taught me to checkpoint results, and a difference in how Spark 3.5 and 4.0 order feature metadata shifted my feature-importance labels until a chart that did not make sense was investigated."),
);

// ---------- 8 Conclusion ----------
add(H1("8. Conclusions and Future Work"),
  P("This project built a Spark pipeline over {{RAW_ROWS}} flights from 2025 that excludes post-flight information. On the random test split, {{BEST_F1_MODEL}} performed best on F1 ({{BEST_F1_VALUE}}) and ROC-AUC, while on later, unseen months Random Forest had the higher F1 and GBT a slightly higher ROC-AUC, so the choice of model depends on how it will be used. Parquet, broadcast joins and in-Spark evaluation made a full year workable on free Colab."),
  P("Before adding complexity, I would validate the existing method: use out-of-fold target encoding inside the CV pipeline, select temporal thresholds on an earlier month, audit the rotation features, and compare runs with and without class weights and threshold tuning. Only then would I add weather forecasts available at the prediction time and repeat the timing runs on a Dataproc cluster."),
);
COUNTING = false;

// ---------- References ----------
const refs = [
  "Armbrust, M., Xin, R. S., Lian, C., Huai, Y., Liu, D., Bradley, J. K., Meng, X., Kaftan, T., Franklin, M. J., Ghodsi, A., & Zaharia, M. (2015). Spark SQL: Relational data processing in Spark. In *Proceedings of the 2015 ACM SIGMOD International Conference on Management of Data* (pp. 1383–1394). https://doi.org/10.1145/2723372.2742797",
  "Ball, M., Barnhart, C., Dresner, M., Hansen, M., Neels, K., Odoni, A., Peterson, E., Sherry, L., Trani, A., & Zou, B. (2010). *Total delay impact study: A comprehensive assessment of the costs and impacts of flight delay in the United States*. NEXTOR.",
  "Belcastro, L., Marozzo, F., Talia, D., & Trunfio, P. (2016). Using scalable data mining for predicting flight delays. *ACM Transactions on Intelligent Systems and Technology, 8*(1), Article 5. https://doi.org/10.1145/2888402",
  "Breiman, L. (2001). Random forests. *Machine Learning, 45*(1), 5–32. https://doi.org/10.1023/A:1010933404324",
  "Bureau of Transportation Statistics. (2026). *Reporting carrier on-time performance (1987–present)* [Data set]. U.S. Department of Transportation. https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ",
  "Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system. In *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining* (pp. 785–794). https://doi.org/10.1145/2939672.2939785",
  "Friedman, J. H. (2001). Greedy function approximation: A gradient boosting machine. *The Annals of Statistics, 29*(5), 1189–1232. https://doi.org/10.1214/aos/1013203451",
  "Gui, G., Liu, F., Sun, J., Yang, J., Zhou, Z., & Zhao, D. (2020). Flight delay prediction based on aviation big data and machine learning. *IEEE Transactions on Vehicular Technology, 69*(1), 140–150. https://doi.org/10.1109/TVT.2019.2954094",
  "He, H., & Garcia, E. A. (2009). Learning from imbalanced data. *IEEE Transactions on Knowledge and Data Engineering, 21*(9), 1263–1284. https://doi.org/10.1109/TKDE.2008.239",
  "Kaufman, S., Rosset, S., Perlich, C., & Stitelman, O. (2012). Leakage in data mining: Formulation, detection, and avoidance. *ACM Transactions on Knowledge Discovery from Data, 6*(4), Article 15. https://doi.org/10.1145/2382577.2382579",
  "Meng, X., Bradley, J., Yavuz, B., Sparks, E., Venkataraman, S., Liu, D., Freeman, J., Tsai, D. B., Amde, M., Owen, S., Xin, D., Xin, R., Franklin, M. J., Zadeh, R., Zaharia, M., & Talwalkar, A. (2016). MLlib: Machine learning in Apache Spark. *Journal of Machine Learning Research, 17*(34), 1–7.",
  "Micci-Barreca, D. (2001). A preprocessing scheme for high-cardinality categorical attributes in classification and prediction problems. *ACM SIGKDD Explorations Newsletter, 3*(1), 27–32. https://doi.org/10.1145/507533.507538",
  "Rebollo, J. J., & Balakrishnan, H. (2014). Characterization and prediction of air traffic delays. *Transportation Research Part C: Emerging Technologies, 44*, 231–241. https://doi.org/10.1016/j.trc.2014.04.007",
  "Saito, T., & Rehmsmeier, M. (2015). The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets. *PLoS ONE, 10*(3), e0118432. https://doi.org/10.1371/journal.pone.0118432",
  "Sternberg, A., Soares, J., Carvalho, D., & Ogasawara, E. (2017). *A review on flight delay prediction* (arXiv:1703.06118). arXiv. https://doi.org/10.48550/arXiv.1703.06118",
  "Zaharia, M., Xin, R. S., Wendell, P., Das, T., Armbrust, M., Dave, A., Meng, X., Rosen, J., Venkataraman, S., Franklin, M. J., Ghodsi, A., Gonzalez, J., Shenker, S., & Stoica, I. (2016). Apache Spark: A unified engine for big data processing. *Communications of the ACM, 59*(11), 56–65. https://doi.org/10.1145/2934664",
];
add(new Paragraph({ children: [new PageBreak()] }), H1("References"),
  refs.map((r) => new Paragraph({ children: runs(r, { size: 20 }), indent: { left: 720, hanging: 720 }, spacing: { after: 120, line: 264 } })));

// ---------- Appendices ----------
add(new Paragraph({ children: [new PageBreak()] }), H1("Appendix A. Notebook structure and reproduction"),
  P("The full source code is the Colab notebook BDMLA_Flight_Delay_Spark.ipynb in the submitted .zip file. To reproduce: place the twelve CSV files in MyDrive/BDMLA/FlightDelay2025/, open the notebook in Colab and choose Runtime → Run all. All figures, tables, saved models and the values used in this report are written to MyDrive/BDMLA/FlightDelay2025_outputs/."),
  table(["Section", "What it does"], [
    ["1–3", "Environment (Java, PySpark), Drive mount, configuration, SparkSession tuning"],
    ["4", "Read 12 CSVs, header normalisation, column allow-list, unionByName, CSV → Parquet checkpoint, CSV vs Parquet benchmark"],
    ["5–7", "Data-quality profile, schedule features on full schedule (window functions), cleaning funnel, label creation"],
    ["8", "Exploratory analysis (Figures 1–3 and supporting tables)"],
    ["9–11", "70/10/20 split, smoothed target encoding (train only), feature pipeline, class weights"],
    ["12–13", "Evaluation helpers, majority baseline, Logistic Regression, Random Forest, GBT, 3-fold CrossValidator"],
    ["14–15", "Model comparison charts, ROC/PR curves, confusion matrices, threshold tuning, feature and permutation importance"],
    ["16–18", "Temporal hold-out (Jan–Sep → Oct–Dec), export of results and models, 1-core vs N-core scaling experiment"],
  ], [1400, 7500], { numericRight: false }),
  caption("Table A1. Notebook sections."),
  H1("Appendix B. Feature dictionary"),
  table(["Feature", "Type", "Definition (from the published schedule)"], [
    ["MONTH, DAY_OF_MONTH, DAY_OF_WEEK, IS_WEEKEND", "numeric", "Calendar fields of the scheduled flight date"],
    ["MONTH_SIN/COS, DEP_HOUR_SIN/COS", "numeric", "Cyclical encodings of month and scheduled departure time"],
    ["DEP_HOUR, ARR_HOUR", "numeric", "Scheduled departure / arrival hour (local)"],
    ["CRS_ELAPSED_TIME, DISTANCE", "numeric", "Scheduled block time (min) and great-circle distance (miles)"],
    ["DAYS_TO_HOLIDAY", "numeric", "Days to the nearest U.S. federal holiday"],
    ["ORIGIN_HOURLY_DEPS, DEST_HOURLY_ARRS", "numeric", "Scheduled departures (arrivals) at the airport in the same hour, incl. later-cancelled flights"],
    ["ORIGIN_DAILY_DEPS, CARRIER_DAILY_FLIGHTS", "numeric", "Scheduled daily volume at the origin and for the carrier"],
    ["TAIL_LEG_OF_DAY, SCHED_TURNAROUND_MIN, HAS_PREV_LEG", "numeric", "Aircraft rotation: leg number of the day, scheduled minutes since the previous leg's scheduled arrival (capped at 720)"],
    ["TE_ORIGIN, TE_DEST, TE_ROUTE, TE_ORIGIN_HOUR, TE_CARRIER_ORIGIN", "numeric", "Smoothed training-set delay rate of the category (m = 100)"],
    ["CARRIER=…", "one-hot", "Reporting airline"],
  ], [3300, 1000, 4600], { numericRight: false }),
  caption("Table B1. Features used by all three models."),
  H1("Appendix C. Excluded (leakage) columns"),
  P("Never loaded into the feature set: ARR_DELAY (label source only), ARR_DELAY_NEW, ARR_DEL15, ARR_TIME, ACTUAL_ELAPSED_TIME, AIR_TIME, WHEELS_ON, WHEELS_OFF, TAXI_IN, TAXI_OUT, DEP_TIME, DEP_DELAY, DEP_DELAY_NEW, DEP_DEL15, CARRIER_DELAY, WEATHER_DELAY, NAS_DELAY, SECURITY_DELAY, LATE_AIRCRAFT_DELAY, CANCELLATION_CODE."),
);

return body;
}

buildBody();                                   // pass 1: count words in sections 1-8
if (!PH.WORD_COUNT) PH.WORD_COUNT = `${MAIN_WORDS.toLocaleString("en-GB")}`;
const WORDS = MAIN_WORDS; MAIN_WORDS = 0;
const body = buildBody();                      // pass 2: real document

// =====================================================================================
const doc = new Document({
  creator: "{{STUDENT_ID}}", title: "Predicting Airline Flight Delays Using Apache Spark",
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: FONT, color: BLUE }, paragraph: { spacing: { before: 320, after: 140 }, outlineLevel: 0, keepNext: true, keepLines: true } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: FONT, color: "2E74B5" }, paragraph: { spacing: { before: 220, after: 100 }, outlineLevel: 1, keepNext: true, keepLines: true } },
    ],
  },
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 640, hanging: 320 } } } }] },
    { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "O%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 720, hanging: 400 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: 16838 }, margin: { top: 1300, bottom: 1300, left: MARGIN, right: MARGIN } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18, color: MUTED })] })] }) },
    children: body,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.mkdirSync(path.dirname(OUT_FILE), { recursive: true });
  fs.writeFileSync(OUT_FILE, buf);
  console.log(`wrote ${OUT_FILE}`);
  console.log(`main-text words (sections 1-8, excl. tables/captions/code): ${WORDS}`);
   const missing = Object.keys(PH).length > 1 ? "" : " (no outputs folder given: all result values are placeholders)";
  console.log(`placeholders filled from outputs: ${Object.keys(PH).length - 1}${missing}`);
});
