# Predicting Airline Flight Delays Using Apache Spark

M33877 Big Data and Machine Learning Applications: **CW1 presentation** and **CW2 Part 2 project report**.

Binary classification (`DELAYED = 1` if `ARR_DELAY ≥ 15`) on all twelve 2025 BTS *Reporting Carrier On-Time Performance* files, with Logistic Regression, Random Forest and Gradient-Boosted Trees in Spark MLlib.

## What's here

| Path | What it is |
|---|---|
| `notebook/BDMLA_Flight_Delay_Spark.ipynb` | **The Colab notebook** (the project's source code). Runs end-to-end from Google Drive. |
| `notebook/executed/BDMLA_Flight_Delay_Spark_full_run.ipynb` | The completed full run on the real data, with all outputs (Spark 4.0.4 on Colab), plus 26 markdown *Interpretation* cells explaining each result (code and outputs unchanged). **Submit this one.** |
| `results/` | Figures, notebook screenshots (`results/screenshots/`, rendered from the executed notebook by `tools/make_screenshots.py`) and `report_placeholders.json`; the report and deck are built from these. |
| `report/BDMLA_CW2_Part2_Flight_Delay_Report.docx` | **CW2 Part 2 report**, filled with the real results (~2,310 words of main text, 15 figures and 6 notebook screenshots, against the brief's 2,000-word target). Only the student ID remains to add. |
| `presentation/BDMLA_CW1_Flight_Delay_Presentation.pptx` | **CW1 deck** on the University of Portsmouth template (from the module's sample deck), filled with the real results: 20 slides incl. a CRISP-DM process model, ~10 min, a full ~10-minute recording script with timings in the speaker notes. Only your name/ID remains to add. Built by `tools/build_deck_uop.py` (python-pptx) from `tools/uop_template.pptx`. |
| `docs/distinction_improvements.md` | What's implemented for each distinction area, optional extras, and a submission checklist. |
| `assets/` | Architecture diagrams used by the report and deck. |
| `tools/` | Generators: notebook source, report and deck builders, a diagram script, and a synthetic-data test fixture. |

## Workflow

1. **Run the notebook in Colab.** The data is expected at `MyDrive/BDMLA/FlightDelay2025/2025_Jan.csv … 2025_Dec.csv`. Use `Runtime → Run all`. On a free Colab runtime, a full run is likely **1.5–3 hours** (I couldn't time it on real Colab hardware). For a quick first pass, set `TRAIN_SAMPLE_FRACTION = 0.1` and `RUN_TUNING = False` in the *Configuration* cell, then do the full run. Keep the browser tab active so Colab doesn't disconnect for idleness. If Colab disconnects, re-run: it resumes from the Parquet checkpoint in Drive.
2. **Download the outputs folder** `MyDrive/BDMLA/FlightDelay2025_outputs/` (figures, tables, `report_placeholders.json`).
3. **Rebuild the report and deck with your real numbers**:
   ```bash
   cd tools && npm install
   node build_report.js /path/to/FlightDelay2025_outputs
   node build_deck.js   /path/to/FlightDelay2025_outputs
   ```
   This fills every `{{PLACEHOLDER}}`, embeds the figures in the report, and draws native PowerPoint charts from your CSV tables. If you'd rather not use Node, the notebook's last export cell prints every placeholder value, so you can paste them into Word by hand.
4. **Finish by hand:** replace the yellow `[CHECK: …]` notes with your own interpretation, add your name/ID, update the Contents field in Word, then export to PDF.

## Design decisions worth knowing for the Q&A

- **Leakage:** columns are loaded through an allow-list. `DEP_DELAY`, `DEP_TIME`, `TAXI_OUT` and `DEP_DEL15` are excluded too, not only the columns on the original list. Schedule-congestion counts are computed *before* cancelled flights are removed.
- **Target encoding** is fitted on the training split only. **Class weights** plus a **validation-tuned threshold** handle the ~1-in-5 imbalance.
- **Evaluation:** a majority-class baseline, PR-AUC, training time, and a **temporal hold-out** (Jan–Sep → Oct–Dec).
- **Scale-out:** a measured 1-core vs N-core experiment, plus the cluster/GPU argument in the report.

## Testing note

The notebook was executed end-to-end against small **synthetic** files in BTS format (`tools/make_synthetic_bts.py`) to check that every cell runs. No results from that test are included anywhere: all result values in the report and deck stay as placeholders until you run on the real data.
