# Distinction-level improvements: what's done, and what you could add

This maps each improvement area onto the **CW2 Part 2 marking scheme** and the notebook section that implements it. Use it to (a) know exactly where your marks come from, and (b) pick extras if you have time.

| Brief criterion | Weight | Where it is covered |
|---|---|---|
| Background & problem definition | 5% | Report §1–2, slides 2–3 |
| Dataset selection, exploration, preparation | 25% | Notebook §4–8, report §3, slides 4 and 7 |
| Methodology & implementation (3 algorithms, comparison, tuning) | **50%** | Notebook §9–16, report §4–6, slides 5–6 and 8–11 |
| Screenshots & supporting visuals | 15% | 14 notebook figures + 2 architecture diagrams, tables 1–4 |
| Conclusions & future implications | 5% | Report §7–8, slides 12–13 |

---

## 1. Feature engineering

**Implemented (notebook §6–7, §10):**
- Cyclical sin/cos encodings for hour and month, so the linear model knows 23:00 is next to 00:00.
- Days to the nearest U.S. federal holiday.
- **Airport congestion** from the *schedule*: departures per origin-hour, arrivals per destination-hour, daily airport and carrier volume.
- **Aircraft rotation** with window functions: leg of the day per tail number and the scheduled turnaround since the previous leg. Delay propagation is the main mechanism behind late-day delays.
- **Smoothed target encoding** for origin, destination, route, origin×hour and carrier×origin, fitted on training data only.
- Schedule counts are computed **before** removing cancellations, which avoids a subtle leak.

**Could add:**
- Weather: NOAA hourly observations or forecasts joined on airport and hour. This is the biggest missing signal. Use *forecasts*, not observations, to stay pre-departure.
- Airport hub flags (top-30 by volume) and route competition (number of carriers on the route).
- Out-of-fold target encoding (k-fold within training) instead of in-sample encoding.
- Network features: rolling delay rate at the origin in the previous 7 days (shifted so it excludes the flight's own day).

## 2. Class imbalance

**Implemented (§11–12):**
- Class weights `w = N / (2·N_class)` via `weightCol` for all three models.
- Decision threshold tuned on the **validation** set to maximise F1. Results at the 0.5 default are also saved (`model_results_all.csv`), so you can show the difference.
- A majority-class baseline row in every results table.

**Could add:**
- Random under-sampling of the majority class, compared against class weights (one extra row in the results table).
- A cost-based threshold, e.g. "a missed delay costs 3× a false alarm", which gives a nice business angle for the discussion.

## 3. Hyperparameter tuning & cross-validation

**Implemented (§13.4):** a 3-fold `CrossValidator` per model, optimising **PR-AUC**, on a sample of the training data, with `parallelism` set so folds run concurrently. The best parameters are refitted on the full training sample. The grid and the score for every combination are saved in `tables/cross_validation_grid.csv`, which makes a good appendix table.

**Could add (if you have Colab Pro or more time):**
- Wider grids: `numTrees` up to 200, `maxDepth` up to 15 for RF; `maxIter` up to 150 for GBT; `minInstancesPerNode`.
- `TrainValidationSplit` on the full training set as a faster alternative to k-fold, with a sentence explaining the trade-off.

## 4. Evaluation rigour

**Implemented:**
- Accuracy, precision, recall, F1, specificity, ROC-AUC, **PR-AUC**, training time and scoring time.
- A **temporal hold-out** (train Jan–Sep, test Oct–Dec), with the full pipeline refitted. This is the honest estimate for real use, and markers like seeing it.

**Could add:** a calibration plot (reliability curve) for the best model, and per-airline or per-airport error breakdowns.

## 5. Spark optimisation & scale-out

**Implemented (§3–4, §18):**
- Column allow-list pushed down to the scan.
- CSV → **Parquet** checkpoint, with a measured CSV-vs-Parquet benchmark.
- Shuffle partitions tuned to the core count, AQE, Kryo.
- Broadcast joins for target-encoding tables.
- Caching of model-ready data.
- All metrics computed in a single aggregation per model (37 thresholds in one pass).
- A **1-core vs N-core scaling experiment**, which directly answers the brief's "demonstrate or convincingly argue scale-out".

**Could add:**
- Run the same notebook on Google Dataproc (free trial credit) with 2–4 workers and add the timing to the scaling chart. This is the strongest possible scale-out evidence.
- A screenshot of the Spark UI (Jobs/Stages tab) showing parallel tasks. The brief rewards selective screenshots. In Colab, use `ngrok` or run a short job and screenshot `spark.sparkContext.uiWebUrl` through a local tunnel.
- Partition the Parquet by `MONTH` and show partition pruning in `explain()`.

## 6. Model interpretation & feature importance

**Implemented (§15):**
- LR standardised coefficients, shown with their sign.
- RF and GBT impurity importances.
- **Permutation importance** for GBT (drop in ROC-AUC when a feature is shuffled), as a robustness check against impurity bias.

**Could add:** SHAP values on a ~10k-row sample using the `shap` package (convert the GBT to pandas predictions via a wrapper), or partial-dependence-style plots of delay probability vs scheduled turnaround.

---

## Presentation tips (CW1, 20% of the module)

- The deck is paced for **10:00**; the timings are at the start of each slide's notes. Rehearse with a timer twice. Timing is 20% of the mark.
- 20% of the mark is for **questions**. The last slide's notes list the seven questions you're most likely to get, with short answers.
- Don't read the notes. Know the three numbers that matter (best F1, baseline accuracy, temporal-vs-random drop) by heart.

## Before you submit CW2 (checklist)

- [ ] All yellow `[PLACEHOLDERS]` replaced (rebuild with `node tools/build_report.js <outputs>`, then search the .docx for `[`).
- [ ] Every `[CHECK: …]` note replaced with your own sentence, in your own words.
- [ ] Word count updated on the title page (main text ≈ 2,000; the brief tolerates small overruns, but stay close).
- [ ] Contents table refreshed in Word (right-click → Update field).
- [ ] Export to **one PDF**. Zip the **uncompiled source** (`.ipynb`, plus the `tools/` folder if you like). Run Turnitin.
- [ ] Remember Part 1 (the lab book, 50% of CW2) is a separate deliverable and isn't covered here.
