"""Builds the CW1 presentation on the University of Portsmouth template (from the module's sample deck).

    python build_deck_uop.py [resultsDir] [out.pptx]

resultsDir defaults to ../results (figures + report_placeholders.json from the Colab run).
Uses the template's own title slide, '4a_Content slide' layout and end slide, so logo, sidebar and
fonts come from the real UoP master. Charts are native PowerPoint charts; speaker notes carry timings.
"""
import io, json, sys
from pathlib import Path
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RES = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "presentation" / "BDMLA_CW1_Flight_Delay_Presentation.pptx"
PH = json.loads((RES / "report_placeholders.json").read_text()) if (RES / "report_placeholders.json").exists() else {}

def V(k):
    return PH.get(k, f"[{k}]")

def num(k):
    return float(str(PH[k]).replace(",", "").replace("%", "").replace("x", ""))

# UoP template palette
PURPLE, PLUM, BLUE = RGBColor(0x62, 0x13, 0x60), RGBColor(0x3C, 0x02, 0x3C), RGBColor(0x00, 0xA0, 0xFF)
INK, MUTED, GREY, LIGHT = RGBColor(0x1F, 0x1F, 0x1F), RGBColor(0x5A, 0x5A, 0x5A), RGBColor(0xD1, 0xD1, 0xD1), RGBColor(0xF4, 0xEF, 0xF4)
CARD_NUM = RGBColor(0x69, 0x97, 0xAF)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
MODEL = {"Logistic Regression": RGBColor(0x00, 0xA0, 0xFF), "Random Forest": PURPLE, "Gradient-Boosted Trees": RGBColor(0x1B, 0xAF, 0x7A)}
MODELS = list(MODEL)
SHORT = {"Logistic Regression": "LR", "Random Forest": "RF", "Gradient-Boosted Trees": "GBT"}

# content area inside the template (logo bottom-left, purple sidebar on the right edge)
X0, Y0, W, BOTTOM = 0.4, 1.75, 9.05, 6.75

prs = Presentation(str(HERE / "uop_template.pptx"))
CONTENT = next(l for l in prs.slide_layouts if l.name == "4a_Content slide")
title_slide, end_slide = prs.slides[0], prs.slides[1]


# ------------------------------------------------------------------ helpers
def new_slide(title):
    s = prs.slides.add_slide(CONTENT)
    s.shapes.title.text = title
    for ph in list(s.placeholders):           # we place our own content; drop the empty body placeholder
        if ph.placeholder_format.idx != 0:
            ph._element.getparent().remove(ph._element)
    return s

def notes(s, text):
    if s.has_notes_slide and s.notes_slide.notes_text_frame is None:
        # template slides carry notes pages without a body placeholder: replace them with fresh ones
        for rId, rel in list(s.part.rels.items()):
            if rel.reltype.endswith("/notesSlide"):
                s.part.drop_rel(rId)
    s.notes_slide.notes_text_frame.text = text

def text(s, x, y, w, h, paras, size=16, color=INK, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, bullets=False):
    """paras: list of str or (str, {bold, color, size}) tuples; '**x**' marks a bold lead-in."""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, p in enumerate(paras):
        opts = {}
        if isinstance(p, tuple):
            p, opts = p
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        para.space_after = Pt(opts.get("space", 8 if bullets else 4))
        lead, rest = "", p
        if p.startswith("**") and "**" in p[2:]:
            lead, rest = p[2:].split("**", 1)
        if bullets:
            pPr = para._p.get_or_add_pPr()
            pPr.set("marL", str(int(Inches(0.25)))); pPr.set("indent", str(int(-Inches(0.2))))
            bu = pPr.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}buChar", {"char": "•"})
            pPr.append(bu)
        for t, b in ((lead, True), (rest, opts.get("bold", bold))):
            if not t:
                continue
            r = para.add_run()
            r.text = t
            r.font.size = Pt(opts.get("size", size))
            r.font.bold = b
            r.font.color.rgb = opts.get("color", color)
    return tb

def box(s, x, y, w, h, fill=LIGHT, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08):
    shp = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line; shp.line.width = Pt(1)
    shp.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        shp.adjustments[0] = radius
    shp.text_frame.text = ""
    return shp

def label_box(s, x, y, w, h, label, fill=BLUE, color=WHITE, size=13):
    shp = box(s, x, y, w, h, fill=fill, radius=0.12)
    tf = shp.text_frame
    tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Inches(0.08)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = label; r.font.size = Pt(size); r.font.color.rgb = color; r.font.bold = True
    return shp

def arrow(s, x1, y1, x2, y2):
    c = s.shapes.add_connector(1, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = MUTED; c.line.width = Pt(1.5)
    ln = c.line._get_or_add_ln()
    ln.append(ln.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd", {"type": "triangle"}))

def picture(s, path, x, y, w, h, crop=None):
    """Fit an image (optionally cropped: (l, t, r, b) as fractions) inside a box, centred."""
    if path is None or not Path(path).exists():
        box(s, x, y, w, h, fill=RGBColor(0xFF, 0xF8, 0xDB), line=RGBColor(0xED, 0xA1, 0x00))
        text(s, x, y, w, h, [f"[missing figure: {Path(str(path)).name}]"], size=12, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        return
    img = Image.open(path)
    if crop:
        W0, H0 = img.size
        img = img.crop((int(crop[0] * W0), int(crop[1] * H0), int(crop[2] * W0), int(crop[3] * H0)))
    buf = io.BytesIO(); img.save(buf, "PNG"); buf.seek(0)
    r = min(w / img.width, h / img.height)
    iw, ih = img.width * r, img.height * r
    s.shapes.add_picture(buf, Inches(x + (w - iw) / 2), Inches(y + (h - ih) / 2), Inches(iw), Inches(ih))

def style_chart(chart, legend=True, size=11):
    chart.font.size = Pt(size); chart.font.color.rgb = MUTED
    chart.has_legend = legend
    if legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM; chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(size)
    va = chart.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = GREY; va.major_gridlines.format.line.width = Pt(0.5)
    va.format.line.fill.background(); chart.category_axis.format.line.color.rgb = GREY
    va.tick_labels.font.size = Pt(size - 1)

def chart_title(chart, t):
    chart.has_title = True
    chart.chart_title.text_frame.text = t
    p = chart.chart_title.text_frame.paragraphs[0]
    p.runs[0].font.size = Pt(13); p.runs[0].font.bold = True; p.runs[0].font.color.rgb = INK

def fig(name):
    return RES / "figures" / name


# ------------------------------------------------------------------ 1. title (template slide)
tb = next(sh for sh in title_slide.shapes if sh.name == "TextBox 17")
paras = tb.text_frame.paragraphs
paras[0].runs[0].text = "– BDMLA Coursework 1"
paras[1].runs[0].text = "Big Data and Machine Learning Application:"
paras[2].runs[0].text = "Predicting Airline Flight Delays with Apache Spark"
for p, size in zip(paras, (24, 24, 30)):
    for r in p.runs:
        r.font.size = Pt(size)
sub = next(sh for sh in title_slide.shapes if sh.name == "Text Placeholder 7")
sub.text_frame.text = "[Your name]  ·  [Student ID]  ·  M33877  ·  November 2026"

# ------------------------------------------------------------------ 2. background
s = new_slide("BACKGROUND")
text(s, X0, Y0, 5.3, 4.6, [
    "**Costly. **Flight delays cost the U.S. economy an estimated $32.9 billion in 2007, shared between airlines, passengers and lost demand (Ball et al., 2010).",
    "**Clearly defined. **The Bureau of Transportation Statistics (BTS) counts a flight as delayed when it arrives 15 or more minutes late.",
    "**Big data. **BTS publishes a record for every domestic flight of the larger U.S. carriers: millions of labelled rows every year.",
    "**Useful if predicted early. **Airlines can re-plan crews, gates and spare aircraft; passengers with tight connections can be warned.",
], size=15, bullets=True)
for i, (big, lab, col) in enumerate([("$32.9B", "cost of U.S. delays in 2007", PURPLE), ("15 min", "BTS delay threshold", BLUE), (V("RAW_ROWS"), "flights in 2025", MODEL["Gradient-Boosted Trees"])]):
    y = Y0 + i * 1.6
    box(s, 6.0, y, 3.4, 1.4, fill=LIGHT)
    text(s, 6.2, y + 0.15, 3.0, 0.7, [big], size=30, bold=True, color=col)
    text(s, 6.2, y + 0.85, 3.0, 0.45, [lab], size=13, color=MUTED)

# ------------------------------------------------------------------ 3. project proposal
s = new_slide("PROJECT PROPOSAL")
box(s, X0, Y0, W, 1.15, fill=PLUM)
text(s, X0 + 0.3, Y0, W - 0.6, 1.15, [("Using only information known before departure, will this flight arrive 15+ minutes late?", {"color": WHITE, "bold": True})],
     size=20, anchor=MSO_ANCHOR.MIDDLE)
text(s, X0, Y0 + 1.45, W, 3.4, [
    "**Binary classification: **DELAYED = 1 if ARR_DELAY ≥ 15 minutes, otherwise 0.",
    "**Before departure only: **many public notebooks use departure delay as an input, which is only known once the plane has left. That inflates accuracy and makes the model useless in practice (Kaufman et al., 2012).",
    "**Approach: **ingest all twelve 2025 monthly files with Apache Spark, engineer schedule-based features, and compare three Spark MLlib classifiers.",
], size=16, bullets=True)

# ------------------------------------------------------------------ 4. objectives and scope
s = new_slide("OBJECTIVES AND SCOPE")
text(s, X0, Y0, 4.4, 0.4, [("Objectives", {"color": PURPLE, "bold": True})], size=18)
objs = ["Ingest, union and clean all 12 monthly files in Spark", "Engineer features from schedule information only",
        "Train LR, Random Forest and GBT in Spark MLlib", "Evaluate with imbalance-aware metrics + training time",
        "Show how the pipeline scales out"]
for i, o in enumerate(objs):
    y = Y0 + 0.55 + i * 0.8
    label_box(s, X0, y, 0.6, 0.6, f"O{i + 1}", fill=PURPLE if i != 1 else BLUE, size=14)
    text(s, X0 + 0.8, y, 3.8, 0.6, [o], size=14, anchor=MSO_ANCHOR.MIDDLE)
box(s, 5.3, Y0, 4.15, 4.6, fill=LIGHT)
text(s, 5.55, Y0 + 0.2, 3.7, 0.4, [("Scope", {"color": PURPLE, "bold": True})], size=18)
text(s, 5.55, Y0 + 0.75, 3.7, 3.7, [
    "U.S. domestic flights, January–December 2025",
    "Arrival delay ≥ 15 min as the target",
    "Schedule information only: no departure delay, no weather",
    "Google Colab (2 cores, ~12 GB RAM) with PySpark",
], size=14, bullets=True)

# ------------------------------------------------------------------ 5. data set used
s = new_slide("DATA SET USED")
text(s, X0, Y0, 4.5, 2.2, [
    "**Source: **BTS Reporting Carrier On-Time Performance, Jan–Dec 2025 (12 monthly CSVs, 3.17 GB, ~110 columns each).",
    f"**Size: **{V('RAW_ROWS')} flights; {V('CLEAN_ROWS')} after cleaning.",
    f"**Imbalanced: **{V('DELAY_RATE')} of flights are delayed, so always predicting 'on time' already scores {V('BASELINE_ACCURACY')} accuracy.",
], size=14, bullets=True)
for i, (big, lab) in enumerate([("12", "monthly files"), ("3.17 GB", "raw CSV"), ("17 / 110", "columns kept"), (V("PARQUET_SPEEDUP"), "faster on Parquet")]):
    x = X0 + (i % 2) * 2.25; y = Y0 + 2.6 + (i // 2) * 1.05
    box(s, x, y, 2.1, 0.9, fill=LIGHT)
    text(s, x + 0.15, y + 0.06, 1.85, 0.5, [big], size=20, bold=True, color=PURPLE)
    text(s, x + 0.15, y + 0.55, 1.85, 0.3, [lab], size=11, color=MUTED)
if "CLEAN_ROWS" in PH:
    clean = num("CLEAN_ROWS"); rate = num("DELAY_RATE") / 100
    cd = CategoryChartData(); cd.categories = ["On time (<15 min)", "Delayed (≥15 min)"]
    cd.add_series("Flights", (round(clean * (1 - rate)), round(clean * rate)))
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(5.1), Inches(Y0), Inches(4.35), Inches(4.7), cd)
    ch = gf.chart; style_chart(ch, legend=False); chart_title(ch, "Class balance after cleaning")
    plot = ch.plots[0]; plot.gap_width = 70; plot.has_data_labels = True
    plot.data_labels.number_format = "#,##0"; plot.data_labels.number_format_is_linked = False
    plot.data_labels.font.size = Pt(11); plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
    pts = plot.series[0].points
    for i, c in enumerate((BLUE, PURPLE)):
        pts[i].format.fill.solid(); pts[i].format.fill.fore_color.rgb = c
    ch.value_axis.tick_labels.number_format = '#,##0,,"M"'; ch.value_axis.tick_labels.number_format_is_linked = False
text(s, 2.2, 6.95, 7.2, 0.3, ["Source: Bureau of Transportation Statistics (2026), Reporting Carrier On-Time Performance."], size=9, color=MUTED)

# ------------------------------------------------------------------ 6. exploratory analysis
s = new_slide("EXPLORATORY ANALYSIS")
picture(s, fig("03_delay_rate_patterns.png"), X0, Y0, 4.45, 3.3, crop=(0, 0.5, 0.5, 1.0))
picture(s, fig("04_airport_and_rotation_patterns.png"), 4.95, Y0, 4.5, 3.3, crop=(0.385, 0, 1.0, 1.0))
text(s, X0, Y0 + 3.45, W, 1.5, [
    "**Delays build through the day: **about 9% of 5am departures arrive late, rising to about 33% at 7pm.",
    "**Delays propagate along the aircraft: **an aircraft's 1st leg is late ~15% of the time, its 7th ~34%; turnarounds under 40 minutes give a 38% delay rate.",
], size=14, bullets=True)

# ------------------------------------------------------------------ 7. architecture design
s = new_slide("ARCHITECTURE DESIGN")
picture(s, ROOT / "assets" / "architecture_pipeline.png", X0, Y0 - 0.05, W, 4.3)
text(s, X0, Y0 + 4.35, W, 0.6, [f"Google Colab · PySpark {V('SPARK_VERSION')} · Spark SQL / DataFrames for processing · Spark MLlib for modelling · Parquet checkpoint in Google Drive"],
     size=12, color=MUTED, align=PP_ALIGN.CENTER)

# ------------------------------------------------------------------ 8. technology used
s = new_slide("TECHNOLOGY USED")
tech = [("01", "Apache Spark", f"PySpark {V('SPARK_VERSION')}"), ("02", "Spark MLlib", "LR · RF · GBT"), ("03", "Spark SQL", "+ Parquet"),
        ("04", "Python", "pandas · matplotlib"), ("05", "Google Colab", "2 vCPU · ~12 GB"), ("06", "Google Drive", "data + checkpoints")]
for i, (n, name, sub) in enumerate(tech):
    x = X0 + 0.15 + (i % 3) * 3.0; y = Y0 + 0.3 + (i // 3) * 2.2
    card = box(s, x, y, 2.7, 1.9, fill=WHITE, line=GREY, radius=0.06)
    text(s, x + 0.25, y + 0.2, 2.2, 0.7, [n], size=30, color=CARD_NUM)
    text(s, x + 0.25, y + 0.95, 2.2, 0.45, [name], size=17, bold=True, color=INK)
    text(s, x + 0.25, y + 1.4, 2.2, 0.35, [sub], size=12, color=MUTED)

# ------------------------------------------------------------------ 9. data cleaning and leakage
s = new_slide("CLEANING AND LEAKAGE")
if "FUNNEL_0_ROWS" in PH:
    steps = ["Raw flights", "− cancelled", "− diverted", "− null ARR_DELAY", "− duplicates", "− invalid values"]
    cd = CategoryChartData(); cd.categories = steps
    cd.add_series("Rows", [num(f"FUNNEL_{i}_ROWS") for i in range(6)])
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(X0), Inches(Y0), Inches(4.5), Inches(4.7), cd)
    ch = gf.chart; style_chart(ch, legend=False); chart_title(ch, "Cleaning funnel (rows remaining)")
    ch.category_axis.reverse_order = True
    ch.value_axis.minimum_scale = 6_000_000
    ch.value_axis.tick_labels.number_format = '0.0,,"M"'; ch.value_axis.tick_labels.number_format_is_linked = False
    plot = ch.plots[0]; plot.gap_width = 50; plot.has_data_labels = True
    plot.data_labels.number_format = "#,##0"; plot.data_labels.number_format_is_linked = False; plot.data_labels.font.size = Pt(10)
    plot.series[0].format.fill.solid(); plot.series[0].format.fill.fore_color.rgb = BLUE
box(s, 5.15, Y0, 4.3, 4.7, fill=LIGHT)
text(s, 5.4, Y0 + 0.15, 3.9, 0.4, [("Leakage guard", {"color": PURPLE, "bold": True})], size=18)
text(s, 5.4, Y0 + 0.7, 3.85, 3.9, [
    "Allow-list at ingestion: post-flight columns are never loaded",
    "Also excluded: DEP_DELAY, DEP_TIME, TAXI_OUT, DEP_DEL15",
    "ARR_DELAY only builds the label, then it is dropped",
    "Schedule counts use the full schedule, before cancelled flights are removed",
    "An assertion stops the run if a forbidden column reaches the features",
    "Remaining risks: same-day aircraft swaps, in-sample target encoding",
], size=13, bullets=True)

# ------------------------------------------------------------------ 10. feature engineering
s = new_slide("FEATURE ENGINEERING")
groups = [("Calendar and time", "Month, day, weekday, departure/arrival hour (with sin/cos), days to the nearest federal holiday", BLUE),
          ("Flight and airline", "Scheduled duration, distance, airline (one-hot)", BLUE),
          ("Airport congestion", "Scheduled departures/arrivals at the airport that hour; daily airport and carrier volume", BLUE),
          ("Aircraft rotation", "Leg of the day for the tail number; scheduled turnaround since its last flight (window function)", PURPLE)]
for i, (t, d, c) in enumerate(groups):
    x = X0 + (i % 2) * 4.6; y = Y0 + (i // 2) * 1.7
    box(s, x, y, 4.4, 1.5, fill=LIGHT)
    label_box(s, x + 0.2, y + 0.2, 0.18, 1.1, "", fill=c)
    text(s, x + 0.55, y + 0.15, 3.7, 0.4, [t], size=16, bold=True)
    text(s, x + 0.55, y + 0.58, 3.7, 0.85, [d], size=12, color=MUTED)
text(s, X0, Y0 - 0.3, W, 0.3, [f"{V('N_FEATURES')} features, built from the published schedule"], size=13, color=MUTED)
box(s, X0, Y0 + 3.55, W, 1.1, fill=PLUM)
text(s, X0 + 0.3, Y0 + 3.55, W - 0.6, 1.1, [("High-cardinality categories → smoothed target encoding. ", {"color": WHITE, "bold": True}),
     ("Origin, destination, route, origin×hour and carrier×origin become their historical delay rate, fitted on the training split only.", {"color": WHITE})],
     size=13, anchor=MSO_ANCHOR.MIDDLE)

# ------------------------------------------------------------------ 11. model training pipeline
s = new_slide("MODEL TRAINING PIPELINE")
flow = [("Split 70/10/20\ntrain · valid · test", BLUE), ("Target-encode\n(train only)", BLUE), ("Assemble +\nstandardise", BLUE),
        ("Class weights\nN / (2·N_class)", BLUE), ("3-fold CV\n(PR-AUC)", PURPLE), ("Train LR · RF · GBT\n(Spark MLlib)", PURPLE),
        ("Tune threshold\non validation", PURPLE), ("Evaluate on test\n+ temporal test", PLUM)]
bw, bh = 2.0, 1.0
coords = [(X0 + 0.1 + c * 2.3, Y0 + 0.2) for c in range(4)] + [(X0 + 0.1 + (3 - c) * 2.3, Y0 + 2.0) for c in range(4)]
for (x, y), (t, c) in zip(coords, flow):
    label_box(s, x, y, bw, bh, t, fill=c, size=12)
for i in range(3):
    arrow(s, coords[i][0] + bw, coords[i][1] + bh / 2, coords[i + 1][0], coords[i + 1][1] + bh / 2)
arrow(s, coords[3][0] + bw / 2, coords[3][1] + bh, coords[4][0] + bw / 2, coords[4][1])
for i in range(4, 7):
    arrow(s, coords[i][0], coords[i][1] + bh / 2, coords[i + 1][0] + bw, coords[i + 1][1] + bh / 2)
text(s, X0, Y0 + 3.45, W, 1.4, [
    "**Logistic Regression: **interpretable linear baseline.",
    "**Random Forest: **many independent trees, easy to parallelise.",
    "**Gradient-Boosted Trees: **trees added in sequence, each fixing the last; sequential rounds make it hardest to scale.",
], size=13, bullets=True)

# ------------------------------------------------------------------ 12. results
s = new_slide("RESULTS ON THE TEST SET")
if all(f"{SHORT[m]}_F1" in PH for m in MODELS):
    metrics = [("PRECISION", "Precision"), ("RECALL", "Recall"), ("F1", "F1"), ("ROC_AUC", "ROC-AUC"), ("PR_AUC", "PR-AUC")]
    cd = CategoryChartData(); cd.categories = [m[1] for m in metrics]
    for m in MODELS:
        cd.add_series(m, [num(f"{SHORT[m]}_{k}") for k, _ in metrics])
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(X0), Inches(Y0), Inches(5.1), Inches(4.7), cd)
    ch = gf.chart; style_chart(ch); chart_title(ch, "Test-set metrics (delayed = positive class)")
    ch.value_axis.maximum_scale = 1.0; ch.value_axis.minimum_scale = 0
    ch.plots[0].gap_width = 60; ch.plots[0].overlap = -5
    for ser, m in zip(ch.plots[0].series, MODELS):
        ser.format.fill.solid(); ser.format.fill.fore_color.rgb = MODEL[m]
rows = [("", "Acc.", "F1", "AUC", "Train")] + [(m.replace("Gradient-Boosted Trees", "GBT"), V(f"{SHORT[m]}_ACCURACY"), V(f"{SHORT[m]}_F1"),
        V(f"{SHORT[m]}_ROC_AUC"), f"{V(f'{SHORT[m]}_TRAIN_S')} s") for m in MODELS] + [("Always 'on time'", V("BASELINE_ACCURACY"), "0.000", "0.500", "-")]
tbl = s.shapes.add_table(len(rows), 5, Inches(5.7), Inches(Y0 + 0.1), Inches(3.75), Inches(0.42 * len(rows))).table
for ci, wd in enumerate((1.45, 0.62, 0.52, 0.52, 0.64)):
    tbl.columns[ci].width = Inches(wd)
for ri, row in enumerate(rows):
    for ci, val in enumerate(row):
        cell = tbl.cell(ri, ci)
        p = cell.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.LEFT if ci == 0 else PP_ALIGN.RIGHT
        r = p.add_run(); r.text = val; r.font.size = Pt(11); r.font.bold = ri == 0 or ci == 0
        cell.margin_left = cell.margin_right = Inches(0.05)
        cell.fill.solid()
        cell.fill.fore_color.rgb = PURPLE if ri == 0 else (WHITE if ri % 2 else LIGHT)
        r.font.color.rgb = WHITE if ri == 0 else (MODEL[MODELS[ri - 1]] if ci == 0 and 1 <= ri <= 3 else INK)
text(s, 5.7, Y0 + 2.45, 3.75, 2.3, [
    f"**Best (random split): **{V('BEST_F1_MODEL')}, F1 {V('BEST_F1_VALUE')}, ROC-AUC {V('GBT_ROC_AUC')}",
    f"**In plain terms: **GBT catches ~60% of delays, but ~6 in 10 of its alerts are false alarms",
    "**Accuracy trap: **doing nothing scores higher accuracy than every model",
], size=12, bullets=True)

# ------------------------------------------------------------------ 13. what drives it / temporal test
s = new_slide("WHAT DRIVES DELAYS")
picture(s, fig("12_gbt_permutation_importance.png"), X0, Y0, 4.5, 3.1)
if all(f"{SHORT[m]}_TEMPORAL_ROC_AUC" in PH for m in MODELS):
    hdr = ("", "ROC-AUC\nrandom", "ROC-AUC\nOct–Dec", "F1\nrandom", "F1\nOct–Dec")
    trows = [hdr] + [(SHORT[m], V(f"{SHORT[m]}_ROC_AUC"), V(f"{SHORT[m]}_TEMPORAL_ROC_AUC"), V(f"{SHORT[m]}_F1"), V(f"{SHORT[m]}_TEMPORAL_F1")) for m in MODELS]
    tbl = s.shapes.add_table(len(trows), 5, Inches(5.1), Inches(Y0 + 0.35), Inches(4.35), Inches(2.4)).table
    for ci, wd in enumerate((0.75, 0.9, 0.9, 0.9, 0.9)):
        tbl.columns[ci].width = Inches(wd)
    # best value per evaluation column (bold + purple fill) so RF's higher temporal F1 is visible
    best = {ci: max(range(1, 4), key=lambda ri: float(trows[ri][ci])) for ci in range(1, 5)}
    for ri, row in enumerate(trows):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci); cell.margin_left = cell.margin_right = Inches(0.04)
            tf = cell.text_frame
            for k, part in enumerate(val.split("\n")):
                para = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
                para.alignment = PP_ALIGN.LEFT if ci == 0 else PP_ALIGN.CENTER
                r = para.add_run(); r.text = part; r.font.size = Pt(11 if ri else 10)
                is_best = ri > 0 and ci > 0 and best[ci] == ri
                r.font.bold = ri == 0 or ci == 0 or is_best
                r.font.color.rgb = WHITE if ri == 0 or is_best else (MODEL[MODELS[ri - 1]] if ci == 0 else INK)
            cell.fill.solid()
            cell.fill.fore_color.rgb = PURPLE if ri == 0 else (RGBColor(0x8E, 0x4A, 0x8C) if best.get(ci) == ri and ci > 0 else (WHITE if ri % 2 else LIGHT))
    text(s, 5.1, Y0, 4.35, 0.3, [("Random split vs temporal test (train Jan–Sep, test Oct–Dec)", {"bold": True})], size=12)
text(s, X0, Y0 + 3.3, W, 1.6, [
    "**Top drivers: **the airport's historical delay rate at that hour, and the scheduled turnaround time.",
    f"**Temporal test: **all models drop; RF has the higher F1 ({V('RF_TEMPORAL_F1')} vs {V('GBT_TEMPORAL_F1')}), GBT a slightly higher ROC-AUC, so the best model depends on the metric.",
    "**Caveat: **thresholds came from a validation set that includes some Oct–Dec flights.",
], size=12, bullets=True)

# ------------------------------------------------------------------ 14. challenges
s = new_slide("CHALLENGES")
chal = [("First full run stopped after 3+ hours", "Most likely a Colab session limit; added Parquet checkpoints, saved results after every model, and a resume option"),
        ("Feature labels shifted between Spark versions", "My code assumed Spark 3.5's metadata order; Colab's Spark 4.0 orders it differently. Spotted when a chart made no sense; fixed by sorting on vector index plus an assertion"),
        ("Target leakage", "Allow-list ingestion and schedule counts computed before cancellations are removed"),
        ("Class imbalance (22% delayed)", "Class weights plus a validation-tuned threshold instead of chasing accuracy"),
        ("3 GB of CSV on a 12 GB machine", "Only 17 columns loaded, then columnar Parquet: same query 25× faster")]
for i, (t, d) in enumerate(chal):
    y = Y0 - 0.1 + i * 1.0
    label_box(s, X0, y + 0.05, 0.5, 0.75, str(i + 1), fill=PURPLE, size=16)
    text(s, X0 + 0.7, y, 8.3, 0.4, [t], size=15, bold=True)
    text(s, X0 + 0.7, y + 0.38, 8.3, 0.55, [d], size=12, color=MUTED)

# ------------------------------------------------------------------ 15. future scope
s = new_slide("FUTURE SCOPE")
fut = [("Weather", "Join hourly NOAA weather forecasts; earlier work found weather improves accuracy"),
       ("Cleaner validation", "Out-of-fold target encoding inside the CV pipeline; temporal thresholds on a separate month"),
       ("Ablations", "Compare runs with and without class weights and threshold tuning"),
       ("Real cluster", "Full data on Google Dataproc, with repeated timing runs"),
       ("Stronger models", "XGBoost or LightGBM on Spark with GPU acceleration")]
for i, (t, d) in enumerate(fut):
    x = X0 + (i % 2) * 4.6 if i < 4 else X0 + 2.3; y = Y0 + (i // 2) * 1.6
    box(s, x, y, 4.4, 1.35, fill=LIGHT)
    text(s, x + 0.25, y + 0.15, 3.9, 0.4, [t], size=16, bold=True, color=PURPLE)
    text(s, x + 0.25, y + 0.58, 3.9, 0.7, [d], size=13, color=MUTED)

# ------------------------------------------------------------------ 16. what I learnt
s = new_slide("WHAT I LEARNT")
learnt = [("Accuracy can mislead", "Predicting 'on time' for every flight beats every model on accuracy; recall, precision and PR-AUC tell the real story"),
          ("Leakage is subtle", "Dropping post-flight columns was easy; counting flights after cancellations or encoding before CV were not"),
          ("Evaluate on the future", "The temporal test changed which model looks best"),
          ("Engineering matters", "Checkpointing, version differences and memory limits took as much effort as modelling")]
for i, (t, d) in enumerate(learnt):
    y = Y0 + i * 1.18
    box(s, X0, y, W, 1.02, fill=LIGHT)
    label_box(s, X0 + 0.2, y + 0.16, 0.18, 0.7, "", fill=PURPLE if i % 2 else BLUE)
    text(s, X0 + 0.6, y + 0.1, 8.2, 0.4, [t], size=16, bold=True)
    text(s, X0 + 0.6, y + 0.5, 8.2, 0.5, [d], size=13, color=MUTED)

# ------------------------------------------------------------------ 17. conclusion
s = new_slide("CONCLUSION")
text(s, X0, Y0, W, 4.8, [
    f"Built an Apache Spark pipeline over {V('RAW_ROWS')} U.S. domestic flights of 2025 that excludes post-flight information.",
    f"On the random test split, {V('BEST_F1_MODEL')} performed best (F1 {V('BEST_F1_VALUE')}, ROC-AUC {V('GBT_ROC_AUC')}); on later, unseen months Random Forest had the higher F1, so the best model depends on how it is used.",
    "Accuracy is misleading on imbalanced data; recall, precision, PR-AUC and a temporal test give a fairer picture.",
    "Big data tooling made it feasible on free Colab: Parquet, broadcast joins and keeping evaluation inside Spark.",
    "Schedule-only prediction is possible but limited; weather data and cleaner validation are the next steps.",
], size=16, bullets=True)

# ------------------------------------------------------------------ 18. references
s = new_slide("REFERENCES")
refs = [
    "Ball, M., et al. (2010). Total delay impact study. NEXTOR.",
    "Belcastro, L., Marozzo, F., Talia, D., & Trunfio, P. (2016). Using scalable data mining for predicting flight delays. ACM TIST, 8(1), 5.",
    "Breiman, L. (2001). Random forests. Machine Learning, 45(1), 5–32.",
    "Bureau of Transportation Statistics. (2026). Reporting carrier on-time performance (1987–present) [Data set]. U.S. DOT.",
    "Friedman, J. H. (2001). Greedy function approximation: A gradient boosting machine. Annals of Statistics, 29(5), 1189–1232.",
    "Kaufman, S., Rosset, S., Perlich, C., & Stitelman, O. (2012). Leakage in data mining. ACM TKDD, 6(4), 15.",
    "Meng, X., et al. (2016). MLlib: Machine learning in Apache Spark. JMLR, 17(34), 1–7.",
    "Micci-Barreca, D. (2001). A preprocessing scheme for high-cardinality categorical attributes. SIGKDD Explorations, 3(1), 27–32.",
    "Saito, T., & Rehmsmeier, M. (2015). The precision-recall plot is more informative than the ROC plot. PLoS ONE, 10(3), e0118432.",
    "Zaharia, M., et al. (2016). Apache Spark: A unified engine for big data processing. CACM, 59(11), 56–65.",
]
text(s, X0, Y0 - 0.1, W, 4.9, refs, size=11, bullets=False)

# ------------------------------------------------------------------ 17. end slide (template) moved last
lst = prs.slides._sldIdLst
end_id = lst[1]
lst.remove(end_id); lst.append(end_id)
ph = next(sh for sh in end_slide.shapes if sh.name == "Text Placeholder 5")
ph.text_frame.text = "Thank you"

# ------------------------------------------------------------------ speaker script (pre-recorded talk, ~10 min)
# One entry per slide, in order. Timings are derived from the word count at a relaxed recording pace.
WPM = 138
SCRIPT = [
    # 1 title
    "Hello, my name is [your name], and this is my Big Data and Machine Learning Applications project: predicting airline flight delays "
    f"with Apache Spark. I used every U.S. domestic flight from 2025, {V('RAW_ROWS')} of them, to test one practical question: "
    "can we tell, before a plane even leaves the gate, that it is going to arrive late?",
    # 2 background
    "Delays matter because they are expensive. A major U.S. study estimated the cost at around 33 billion dollars in 2007 alone, shared "
    "between airlines, passengers and lost demand. The industry uses a simple rule: a flight that arrives 15 minutes or more after "
    "schedule counts as delayed. The Bureau of Transportation Statistics publishes a record for every domestic flight, which gives us "
    "millions of labelled examples. If risky flights can be flagged early, airlines can re-plan crews and spare aircraft, and passengers "
    "with tight connections can be warned.",
    # 3 proposal
    "So the problem statement is: using only information known before departure, will this flight arrive 15 or more minutes late? "
    "That makes it a binary classification problem. The 'before departure' condition is the important part. Many online examples use "
    "the departure delay as an input, but you only know that once the plane has left, so the model looks accurate but is useless in "
    "practice. My approach is to process the whole year with Spark, build features from the schedule only, and compare three Spark "
    "MLlib classifiers fairly.",
    # 4 objectives and scope
    "I set five objectives: ingest and clean all twelve monthly files in Spark; engineer features with no target leakage; train "
    "Logistic Regression, Random Forest and Gradient-Boosted Trees; evaluate them with metrics that suit an imbalanced problem, plus "
    "training time; and show how the pipeline scales out. The scope is all 2025 U.S. domestic flights, using schedule information "
    "only, running on a free Google Colab machine.",
    # 5 data set
    f"The data is the official BTS on-time performance table: twelve monthly CSV files, 3.17 gigabytes, and {V('RAW_ROWS')} flights. "
    "Each file has about 110 columns, but I only load 17 of them, for leakage reasons I'll come back to. After cleaning, "
    f"{V('DELAY_RATE')} of flights are delayed. So the classes are imbalanced: a model that always says 'on time' would already score "
    f"{V('BASELINE_ACCURACY')} accuracy. One early optimisation was converting the CSVs to Parquet once; after that, the same query "
    f"ran {V('PARQUET_SPEEDUP')} faster.",
    # 6 exploratory analysis
    "Exploring the data showed two patterns that shaped my features. On the left, the delay rate by scheduled departure hour: only "
    "about 9 percent of 5am departures arrive late, but by 7pm it's around a third. On the right, the later the leg of the day for an "
    "aircraft, the more likely it is to be late, and very tight turnarounds under 40 minutes have a 38 percent delay rate. Delays roll "
    "forward through an aircraft's day, so I built features that capture exactly that.",
    # 7 architecture
    "This is the whole pipeline. The twelve files sit in Google Drive. Spark reads each month, maps the column names, keeps only the "
    "allowed columns and unions them into one DataFrame. That is written once to Parquet, which also acts as a checkpoint. Then come "
    "the schedule features, cleaning and the label. The second row is the machine learning layer: split, encode, train, tune and "
    "evaluate, and finally export every chart and table used in my report.",
    # 8 technology
    "The stack is Spark through PySpark, with MLlib for the models, Spark SQL and Parquet for the data, Python for plotting, and Google "
    "Colab for compute, with data and checkpoints in Google Drive.",
    # 9 cleaning and leakage
    f"Cleaning followed the brief: remove cancelled and diverted flights and rows with no arrival delay, then duplicates and impossible "
    f"values, which leaves {V('CLEAN_ROWS')} flights. The bigger issue is leakage. Columns such as wheels-on time or the delay-cause "
    "minutes are only known after landing, so they are never loaded. I also excluded departure delay and taxi-out time. There's a "
    "subtle trap too: if you count flights per hour after removing cancellations, a stormy day looks quiet, and the feature leaks the "
    "outcome. So those counts are calculated on the full schedule first.",
    # 10 feature engineering
    f"I ended up with {V('N_FEATURES')} features in four groups, all built from the published schedule: calendar and time, including how "
    "close the date is to a public holiday; basic flight details; airport congestion, meaning how many flights are scheduled at the same "
    "airport in the same hour; and aircraft rotation, built with a Spark window function over each tail number. Airports and routes have "
    "thousands of values, which would explode the feature space and break Spark's tree limits, so I replaced each with its smoothed "
    "historical delay rate, fitted on the training data only.",
    # 11 model pipeline
    "Here is the training pipeline. The data is split 70, 10 and 20 percent into train, validation and test sets. Because Colab only has "
    f"two cores, models were trained on a {V('TRAIN_SAMPLE_PCT')} sample of the training set, but validation and test were always scored "
    "in full. Every model gets class weights, so delayed flights count as much as on-time ones. Each model is tuned with three-fold "
    "cross-validation on PR-AUC, the decision threshold is chosen on the validation set, and the test set is used once, at the end.",
    # 12 results
    f"These are the results on the random test split. Gradient-Boosted Trees came out best, with an F1 of {V('BEST_F1_VALUE')} and a "
    f"ROC-AUC of {V('GBT_ROC_AUC')}. In plain terms, it catches about 60 percent of delayed flights, but about six in ten of its delay "
    f"alerts are false alarms. Notice the last row: a 'model' that always says on time gets {V('BASELINE_ACCURACY')} accuracy and catches "
    "zero delays, which is why accuracy alone is misleading here. Both tree models achieved a higher ROC-AUC than Logistic Regression, "
    "which suggests that interactions between the features help.",
    # 13 drivers and temporal test
    "What is the model using? Permutation importance, on the left, shows the two features that matter most: the historical delay rate "
    "of that airport at that hour, and the scheduled turnaround time. On the right is a stricter test: train on January to September, "
    "then predict October to December. All models drop, and the ranking changes: Random Forest has the higher F1, while boosting keeps a "
    "slightly higher ROC-AUC. So the preferred model depends on the metric and on how it is evaluated. I consider this temporal test more "
    "relevant to practical use, with one caveat: the thresholds came from a validation set that includes some autumn flights.",
    # 14 challenges
    "There were some practical challenges. My first full run stopped after more than three hours, most likely because of a Colab session "
    "limit, so I added checkpoints and a resume option. Feature-importance labels were also shifted: my code assumed the metadata order "
    "used by Spark 3.5, but Colab ran Spark 4.0, which orders it differently. It was spotted because one chart ranked day-of-week as the "
    "strongest feature, which made no sense, and it is now fixed with an explicit check. Leakage, imbalance and memory limits also needed care.",
    # 15 future scope
    "For future work, I would add weather forecasts, which earlier studies found improve accuracy; use out-of-fold target encoding inside "
    "cross-validation; measure the effect of class weights directly; and repeat the training and timing on a real cluster.",
    # 16 what I learnt
    "So what did I learn? First, accuracy can be misleading on imbalanced data. Second, leakage is subtle: removing post-flight columns "
    "was easy, but problems like counting flights after cancellations, or encoding categories before cross-validation, only showed up on "
    "closer inspection. Third, evaluating on future months changed my view of which model is best. And finally, the engineering side, "
    "checkpointing, version differences and memory, took as much effort as the modelling.",
    # 17 conclusion
    "To conclude: I built a Spark pipeline over every U.S. domestic flight in 2025 that excludes post-flight information. On the random "
    "split, Gradient-Boosted Trees performed best; on later months, Random Forest had the higher F1. Schedule-only prediction works, but "
    "it has a ceiling, and weather data and cleaner validation are the natural next steps.",
    # 18 references
    "The main references I used are listed here.",
    # 19 thank you
    "Thank you very much for watching. The full code, results and report are included in my submission.",
]
assert len(SCRIPT) == len(prs.slides), (len(SCRIPT), len(prs.slides))
elapsed = 0.0
for s, line in zip(prs.slides, SCRIPT):
    secs = len(line.split()) / WPM * 60
    a, b = elapsed, elapsed + secs
    notes(s, f"[{int(a // 60)}:{int(a % 60):02d}-{int(b // 60)}:{int(b % 60):02d}]  {line}")
    elapsed = b
print(f"script: {sum(len(l.split()) for l in SCRIPT)} words, about {elapsed / 60:.1f} min at {WPM} wpm")

OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(str(OUT))
print(f"wrote {OUT} ({len(prs.slides)} slides, {len(PH)} values filled)")
