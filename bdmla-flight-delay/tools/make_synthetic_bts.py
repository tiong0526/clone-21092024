"""TEST FIXTURE ONLY: writes small fake BTS-format monthly CSVs so the notebook can be smoke-tested
without the real 3 GB download. The numbers are random and must never be reported as results."""
import sys, os, numpy as np, pandas as pd

out_dir = sys.argv[1]; rows_per_month = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
os.makedirs(out_dir, exist_ok=True)
rng = np.random.default_rng(0)
carriers = ["AA", "DL", "UA", "WN", "B6", "AS", "NK", "F9", "OO", "YX", "MQ", "OH", "9E", "G4", "HA"]
airports = [f"A{i:02d}" for i in range(60)]
tails = [f"N{i:04d}" for i in range(900)]
months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
cols = ["Year","Quarter","Month","DayofMonth","DayOfWeek","FlightDate","Reporting_Airline","DOT_ID_Reporting_Airline",
        "IATA_CODE_Reporting_Airline","Tail_Number","Flight_Number_Reporting_Airline","Origin","Dest","CRSDepTime",
        "DepTime","DepDelay","DepDel15","TaxiOut","WheelsOff","WheelsOn","TaxiIn","CRSArrTime","ArrTime","ArrDelay",
        "ArrDel15","Cancelled","CancellationCode","Diverted","CRSElapsedTime","ActualElapsedTime","AirTime","Distance",
        "CarrierDelay","WeatherDelay","NASDelay","SecurityDelay","LateAircraftDelay"]
for mi, mname in enumerate(months, 1):
    n = rows_per_month
    days = pd.Timestamp(2025, mi, 1).days_in_month
    dom = rng.integers(1, days + 1, n)
    date = pd.to_datetime(dict(year=2025, month=mi, day=dom))
    dep_min = rng.integers(300, 1380, n); dur = rng.integers(45, 360, n)
    arr_min = (dep_min + dur) % 1440
    carr = rng.choice(carriers, n); org = rng.choice(airports, n); dst = rng.choice(airports, n)
    logit = -1.8 + 1.2 * (dep_min / 1440) + 0.05 * (np.array([carriers.index(c) for c in carr]) % 5) \
            + 0.4 * (np.array([int(a[1:]) for a in org]) % 7 == 0) + (0.3 if mi in (6, 7, 12) else 0)
    p = 1 / (1 + np.exp(-logit))
    delayed = rng.random(n) < p
    arr_delay = np.where(delayed, rng.integers(15, 240, n), rng.integers(-30, 15, n)).astype(float)
    canc = (rng.random(n) < 0.015).astype(float); div = ((rng.random(n) < 0.003) & (canc == 0)).astype(float)
    arr_delay[(canc == 1) | (div == 1)] = np.nan
    arr_delay[rng.random(n) < 0.001] = np.nan
    hhmm = lambda m: (m // 60) * 100 + m % 60
    df = pd.DataFrame({
        "Year": 2025, "Quarter": (mi - 1) // 3 + 1, "Month": mi, "DayofMonth": dom, "DayOfWeek": date.dt.dayofweek + 1,
        "FlightDate": date.dt.strftime("%Y-%m-%d"), "Reporting_Airline": carr, "DOT_ID_Reporting_Airline": 19805,
        "IATA_CODE_Reporting_Airline": carr, "Tail_Number": np.where(rng.random(n) < 0.02, "", rng.choice(tails, n)),
        "Flight_Number_Reporting_Airline": rng.integers(1, 7000, n), "Origin": org, "Dest": dst,
        "CRSDepTime": [f"{v:04d}" for v in hhmm(dep_min)], "DepTime": "", "DepDelay": arr_delay, "DepDel15": "",
        "TaxiOut": 15, "WheelsOff": "", "WheelsOn": "", "TaxiIn": 7, "CRSArrTime": [f"{v:04d}" for v in hhmm(arr_min)],
        "ArrTime": "", "ArrDelay": arr_delay, "ArrDel15": (arr_delay >= 15).astype(float), "Cancelled": canc,
        "CancellationCode": "", "Diverted": div, "CRSElapsedTime": dur.astype(float), "ActualElapsedTime": "",
        "AirTime": "", "Distance": (dur * 7.5).round(), "CarrierDelay": "", "WeatherDelay": "", "NASDelay": "",
        "SecurityDelay": "", "LateAircraftDelay": ""})[cols]
    df = pd.concat([df, df.head(20)])                       # a few duplicates
    df[""] = ""                                              # trailing comma, like real BTS files
    df.to_csv(f"{out_dir}/2025_{mname}.csv", index=False)
print("synthetic files written to", out_dir)
