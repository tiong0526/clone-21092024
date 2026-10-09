"""Draws the architecture diagrams used in the report and the slides (assets/*.png)."""
import pathlib, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = pathlib.Path(__file__).parents[1] / "assets"
INK, INK2, LINE = "#0b0b0b", "#52514e", "#b9b8b2"
BLUE, ORANGE, AQUA, GREY = "#2a78d6", "#eb6834", "#1baf7a", "#f0efec"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})

def box(ax, x, y, w, h, title, lines=(), color=BLUE, fill=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.12",
                                linewidth=1.6, edgecolor=color, facecolor=fill or "white"))
    ax.add_patch(FancyBboxPatch((x, y + h - 0.09), w, 0.09, boxstyle="square,pad=0", linewidth=0, facecolor=color))
    ax.text(x + w / 2, y + h - 0.32, title, ha="center", va="center", fontsize=10.5, fontweight="bold", color=INK)
    for i, l in enumerate(lines):
        ax.text(x + w / 2, y + h - 0.68 - i * 0.3, l, ha="center", va="center", fontsize=8.6, color=INK2)

def arrow(ax, x1, y1, x2, y2, text=None, color=LINE):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14, linewidth=1.6, color=color))
    if text:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.14, text, ha="center", fontsize=8, color=INK2)

# ---- 1. End-to-end pipeline ----------------------------------------------------------------
fig, ax = plt.subplots(figsize=(13, 5.2)); ax.set_xlim(0, 13); ax.set_ylim(0, 5.2); ax.axis("off")
w, h, y1, y2 = 2.25, 1.85, 2.95, 0.35
box(ax, 0.2, y1, w, h, "1  Storage", ["12 BTS monthly CSVs", "~3 GB, Google Drive", "mounted in Colab"], GREY.replace("f0efec", "8a8984"))
box(ax, 2.75, y1, w, h, "2  Ingestion", ["read each month", "header mapping +", "allow-list, unionByName"], BLUE)
box(ax, 5.3, y1, w, h, "3  Parquet stage", ["typed, columnar", "checkpoint to Drive", "re-read for every step"], BLUE)
box(ax, 7.85, y1, w, h, "4  Schedule features", ["window functions on", "full schedule: congestion,", "aircraft rotation"], BLUE)
box(ax, 10.4, y1, w, h, "5  Cleaning + label", ["drop cancelled/diverted,", "null ARR_DELAY, dupes", "DELAYED = ARR_DELAY ≥ 15"], BLUE)
box(ax, 10.4, y2, w, h, "6  Split + encode", ["70/10/20 random split", "target encoding (train)", "OHE, assemble, scale"], ORANGE)
box(ax, 7.85, y2, w, h, "7  Spark MLlib models", ["Logistic Regression", "Random Forest", "Gradient-Boosted Trees"], ORANGE)
box(ax, 5.3, y2, w, h, "8  Tuning", ["3-fold CrossValidator", "(PR-AUC), threshold", "chosen on validation"], ORANGE)
box(ax, 2.75, y2, w, h, "9  Evaluation", ["Acc, P, R, F1, ROC-AUC,", "PR-AUC, training time", "+ temporal hold-out"], AQUA)
box(ax, 0.2, y2, w, h, "10  Outputs", ["figures, CSV tables,", "saved models, JSON", "→ report & slides"], AQUA)
for x in (2.45, 5.0, 7.55, 10.1):
    arrow(ax, x, y1 + h / 2, x + 0.3, y1 + h / 2)
arrow(ax, 11.525, y1, 11.525, y2 + h)
for x in (10.4, 7.85, 5.3, 2.75):
    arrow(ax, x, y2 + h / 2, x - 0.3, y2 + h / 2)
ax.text(0.2, 5.05, "Spark SQL / DataFrame layer", fontsize=9, color=BLUE, fontweight="bold")
ax.text(0.2, 2.55, "Spark MLlib layer", fontsize=9, color=ORANGE, fontweight="bold")
fig.savefig(OUT / "architecture_pipeline.png", dpi=200, bbox_inches="tight", facecolor="white"); plt.close(fig)

# ---- 2. Spark execution model ---------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 5)); ax.set_xlim(0, 12); ax.set_ylim(0, 5); ax.axis("off")
box(ax, 0.3, 1.6, 3.0, 2.3, "Driver (PySpark)", ["SparkSession", "Catalyst optimiser →", "DAG of stages", "Task scheduler"], BLUE)
box(ax, 4.4, 3.35, 2.2, 1.4, "Cluster manager", ["local[*] on Colab", "YARN / K8s on a cluster"], GREY.replace("f0efec", "8a8984"))
for i, y in enumerate([2.75, 1.25, -0.25]):
    if y < 0: break
    box(ax, 7.7, y + 0.35 if i == 0 else y - 0.15, 3.9, 1.35, f"Executor {i + 1}",
        [f"tasks on partitions  ·  cached data", "core 1 | core 2 | …"], AQUA)
arrow(ax, 3.3, 2.75, 4.4, 3.9, "request resources")
arrow(ax, 6.6, 4.05, 7.7, 3.75)
arrow(ax, 3.3, 2.4, 7.7, 1.75, "serialised tasks")
arrow(ax, 7.7, 1.4, 3.3, 2.0, "results / aggregates", color="#d0cfc9")
ax.text(0.3, 0.75, "Colab: driver and executor share one 2-vCPU VM (local mode), one task per core.\n"
        "Cluster: same code, change the master URL; partitions spread across many executors.",
        fontsize=9, color=INK2, va="top")
fig.savefig(OUT / "spark_architecture.png", dpi=200, bbox_inches="tight", facecolor="white"); plt.close(fig)
print("diagrams written to", OUT)
