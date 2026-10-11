"""Render selected cells of the executed notebook as screenshot images (real code + real output).

    python make_screenshots.py [executed.ipynb] [out_dir]

Each screenshot shows a notebook-style cell: execution count, syntax-highlighted code excerpt and the
cell's actual output, with key lines boxed in red. Images are captured with headless Chromium (Playwright).
"""
import html, json, subprocess, sys, tempfile
from pathlib import Path
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

ROOT = Path(__file__).resolve().parents[1]
NB = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "notebook" / "executed" / "BDMLA_Flight_Delay_Spark_full_run.ipynb"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "results" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

cells = [c for c in json.load(open(NB))["cells"] if c["cell_type"] == "code"]

def cell(prefix):
    hits = [c for c in cells if "".join(c["source"]).lstrip().startswith(prefix)]
    assert len(hits) == 1, (prefix, len(hits))
    return hits[0]

def output_text(c):
    return "".join("".join(o.get("text", [])) for o in c.get("outputs", []) if o.get("output_type") == "stream")

# Each part: (code-cell prefix, code line ranges to show, output filter, highlight substrings)
SHOTS = {
    "s1_ingestion": ("Reading and unioning the twelve monthly CSV files", [
        ("import time, json", [(13, 15), (36, 44)], lambda t: t, ["Files found : 12 / 12", "Total size"]),
        ("import re", [(62, 71)], lambda t: "\n".join(t.splitlines()[:9] + ["  ..."]), ["17 allow-listed columns are kept"]),
    ]),
    "s2_parquet": ("Rows per monthly file and the CSV-versus-Parquet benchmark", [
        ("rows_per_file = (staged.groupBy", [(0, 6), (15, 20)], lambda t: t, ["Total flights (raw, all 12 files)", "Parquet speed-up"]),
    ]),
    "s3_quality": ("Data-quality profile before cleaning", [
        ("n_raw = staged.count()", [(0, 1), (6, 7), (9, 16)], lambda t: t, ["Cancelled", "Diverted", "ARR_DELAY  "]),
    ]),
    "s4_spark": ("Spark session configuration on Google Colab", [
        ("from pyspark.sql import SparkSession", [(9, 12), (13, 22)], lambda t: t, ["Spark version", "Master", "Shuffle partitions"]),
    ]),
    "s5_encoding": ("Target encoding fitted on the training split, and the leakage check", [
        ("TE_COLUMNS = [\"ORIGIN\", \"DEST\", \"ROUTE\"", [(0, 10), (16, 20)], lambda t: t, ["TE_ROUTE", "TE_ORIGIN_HOUR"]),
        ("from pyspark.ml import Pipeline", [(9, 13)], lambda t: "\n".join(t.splitlines()[:1]), ["Leakage check passed"]),
    ]),
    "s6_tuning": ("Three-fold cross-validation over each model's hyperparameter grid", [
        ("from pyspark.ml.tuning import CrossValidator", [(24, 43), (47, 49)], lambda t: t, [": best {"]),
    ]),
}

# Shorter, wider versions for the CW1 slides (bigger font, fewer lines)
keep = lambda *subs: (lambda t: "\n".join(l for l in t.splitlines() if any(x in l for x in subs)))
SLIDE_SHOTS = {
    "slide_ingestion": ("Reading the twelve monthly files, then the CSV-versus-Parquet benchmark", [
        ("import time, json", [(13, 15), (36, 38)], keep("Files found", "Total size"), ["Files found : 12 / 12", "Total size"]),
        ("rows_per_file = (staged.groupBy", [(5, 6), (15, 16), (18, 20)], keep("Total flights", "CSV (12", "Parquet"),
         ["Total flights (raw, all 12 files)", "Parquet speed-up"]),
    ]),
    "slide_encoding": ("Target encoding fitted on the training split only, then the leakage assertion", [
        ("TE_COLUMNS = [\"ORIGIN\", \"DEST\", \"ROUTE\"", [(0, 1), (2, 7), (16, 17)], keep("TE_ROUTE", "TE_ORIGIN_HOUR", "prior"),
         ["TE_ROUTE", "TE_ORIGIN_HOUR"]),
        ("from pyspark.ml import Pipeline", [(10, 12)], lambda t: t.splitlines()[0], ["Leakage check passed"]),
    ]),
    "slide_tuning": ("Three-fold CrossValidator on PR-AUC for each model", [
        ("from pyspark.ml.tuning import CrossValidator", [(24, 34), (36, 38), (40, 41), (47, 49)], keep(": best {"), [": best {"]),
    ]),
}

CSS = HtmlFormatter(style="default").get_style_defs(".code")
PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
body {{ margin:0; padding:18px; background:#ffffff; font-family: Roboto, Arial, sans-serif; }}
.shot {{ width: 1060px; border:1px solid #dadce0; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.12); }}
.title {{ background:#f1f3f4; color:#3c4043; font-size:13px; padding:7px 12px; border-bottom:1px solid #dadce0; }}
.title b {{ color:#202124; }}
.cell {{ display:flex; border-top:1px solid #eceff1; }}
.cell:first-of-type {{ border-top:none; }}
.count {{ width:56px; flex:none; color:#80868b; font: 12px "DejaVu Sans Mono", monospace; padding:10px 0 0 10px; }}
.body {{ flex:1; min-width:0; padding:8px 12px 10px 0; }}
.code {{ background:#f7f7f7; border-radius:4px; padding:8px 10px; font: 12.5px/1.45 "DejaVu Sans Mono", monospace; white-space:pre; overflow:hidden; }}
.code pre {{ margin:0; font: inherit; }}
.gap {{ color:#9aa0a6; font-style:italic; }}
.big .code, .big .out {{ font-size: 15px; }}
.big .title {{ font-size: 15px; }}
.out {{ font: 12.5px/1.45 "DejaVu Sans Mono", monospace; white-space:pre; color:#202124; padding:8px 10px 2px; overflow:hidden; }}
.hl {{ outline:2px solid #d93025; outline-offset:1px; border-radius:2px; }}
{css}
</style></head><body><div class="shot {cls}" id="shot"><div class="title"><b>BDMLA_Flight_Delay_Spark.ipynb</b> &nbsp;·&nbsp; {title}</div>{cells}</div></body></html>"""

def render_code(src, ranges):
    lines = src.splitlines()
    parts, last = [], 0
    for a, b in ranges:
        if a > last:
            parts.append(None)                    # marks skipped lines
        parts.append("\n".join(lines[a:b]))
        last = b
    out = []
    for p in parts:
        if p is None:
            out.append('<div class="gap">    # ... (lines omitted)</div>')
        else:
            out.append(highlight(p, PythonLexer(), HtmlFormatter(nowrap=True)))
    return "".join(f"<pre>{o}</pre>" if not o.startswith("<div") else o for o in out)

def render_output(text, marks):
    rows = []
    for line in text.rstrip("\n").splitlines():
        esc = html.escape(line)
        if any(m in line for m in marks):
            esc = f'<span class="hl">{esc}</span>'
        rows.append(esc)
    return "\n".join(rows)

html_files = []
tmp = Path(tempfile.mkdtemp())
for name, (title, parts), cls in [(k, v, "") for k, v in SHOTS.items()] + [(k, v, "big") for k, v in SLIDE_SHOTS.items()]:
    blocks = []
    for prefix, ranges, filt, marks in parts:
        c = cell(prefix)
        code = render_code("".join(c["source"]), ranges)
        out = render_output(filt(output_text(c)), marks)
        blocks.append(f'<div class="cell"><div class="count">[{c.get("execution_count") or " "}]</div>'
                      f'<div class="body"><div class="code">{code}</div><div class="out">{out}</div></div></div>')
    page = tmp / f"{name}.html"
    page.write_text(PAGE.format(css=CSS, cls=cls, title=html.escape(title), cells="".join(blocks)), encoding="utf-8")
    html_files.append((page, OUT / f"{name}.png"))

script = tmp / "shoot.js"
script.write_text("""
const { chromium } = require('playwright');
const jobs = JSON.parse(process.argv[2]);
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 2, viewport: { width: 1100, height: 800 } });
  for (const [src, dst] of jobs) {
    await page.goto('file://' + src);
    await (await page.$('#shot')).screenshot({ path: dst });
  }
  await browser.close();
})();
""")
subprocess.run(["node", str(script), json.dumps([[str(a), str(b)] for a, b in html_files])], check=True,
               env={**__import__("os").environ, "NODE_PATH": "/opt/node22/lib/node_modules"})
for _, png in html_files:
    print("wrote", png)
