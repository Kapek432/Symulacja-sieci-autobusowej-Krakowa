"""pilot_stats.py: parametry dla modelu z observed_events (dzien roboczy)."""
import sys
import numpy as np
import pandas as pd

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", None)

DAY = "2026-10-05"
ROUTES = sys.argv[1:] or ["179", "704", "144", "169", "164", "173", "174", "310", "494", "194"]

raw = pd.read_parquet("data/processed/observed_events.parquet")
raw = raw[raw["service_date"] == DAY].copy()
for c in ("route_id", "trip_id", "stop_id"):
    raw[c] = raw[c].astype(str)

# reset na petli: opoznienie odjazdu z pierwszego przystanku
dep = raw[raw["is_first"] & raw["dep_ok"].fillna(False).astype(bool)
          & (raw["dep_delay_s"].abs() <= 1800)]
print("ODJAZD Z PIERWSZEGO PRZYSTANKU [s]:")
print(dep.groupby("route_id")["dep_delay_s"].describe(percentiles=[.25, .5, .75])
      .loc[lambda d: d.index.isin(ROUTES), ["count", "25%", "50%", "75%"]].round(1))

ev = raw[raw["arr_ok"].fillna(False).astype(bool) & (raw["arr_delay_s"].abs() <= 1800)].copy()
ev["delay"] = ev["arr_delay_s"].astype(float)
ev["span"] = (ev["last_seq"] - ev["first_seq"]).astype(float)
ev = ev[ev["span"] > 0].copy()
ev["frac"] = (ev["stop_sequence"] - ev["first_seq"]) / ev["span"]
ev["fifth"] = np.minimum((ev["frac"] * 5).astype(int), 4)
ev = ev[ev["route_id"].isin(ROUTES)]

# opoznienie w piatych czesciach trasy
print("\nOPOZNIENIE WG POZYCJI NA TRASIE (mediana / odch. std) [s]:")
t = ev.groupby(["route_id", "fifth"])["delay"].agg(["median", "std", "size"]).round(0)
print(t.unstack("fifth"))

# przyrost opoznienia miedzy sasiednimi przystankami (a_s, eta)
e2 = ev.sort_values(["trip_id", "stop_sequence"]).copy()
g = e2.groupby("trip_id")
e2["dd"] = g["delay"].diff()
e2["dseq"] = g["stop_sequence"].diff()
inc = e2[e2["dseq"] == 1]
print("\nPRZYROST OPOZNIENIA NA ODCINKU [s]:")
print(inc.groupby("route_id")["dd"].agg(mean="mean", std="std", n="size").round(1))

# sprzezenie kolejnych autobusow tej samej linii na tym samym slupku
e3 = ev.sort_values(["route_id", "stop_id", "arr_s"]).copy()
g3 = e3.groupby(["route_id", "stop_id"])
e3["prev_delay"] = g3["delay"].shift(1)
e3["gap"] = e3["arr_s"] - g3["arr_s"].shift(1)
pr = e3[e3["gap"].between(60, 3600)].dropna(subset=["prev_delay"])
print("\nKORELACJA OPOZNIEN KOLEJNYCH AUTOBUSOW (ta sama linia, ten sam slupek):")
print(pr.groupby("route_id").apply(
    lambda x: pd.Series({"n": len(x), "corr": x["delay"].corr(x["prev_delay"]),
                         "gap_med_min": x["gap"].median() / 60}), include_groups=False).round(2))