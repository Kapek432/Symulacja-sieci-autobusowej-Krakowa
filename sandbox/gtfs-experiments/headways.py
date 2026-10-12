"""headways.py: odstepy miedzy kolejnymi kursami i miary zbijania sie."""
import glob
import zipfile
from pathlib import Path

import pandas as pd

DATA = Path("data/raw_A")
PROC = Path("data/processed")
MAX_H = 3600            # pomijamy odstepy rozkladowe dluzsze niz godzina
MAX_ABS_DELAY = 1800    # wyrzucamy podejrzane przyjazdy (patrz check_outliers.py)
MIN_PAIRS = 50

ev = pd.read_parquet(PROC / "observed_events.parquet")
ev["trip_id"] = ev["trip_id"].astype(str)
ev["stop_id"] = ev["stop_id"].astype(str)

seen = ev[["service_date", "trip_id"]].drop_duplicates()   # kursy, ktore danego dnia jechaly
mask = (ev["arr_ok"] & (ev["arr_delay_s"].abs() <= MAX_ABS_DELAY)).fillna(False).astype(bool)
obs = (ev[mask][["service_date", "trip_id", "stop_id", "arr_ts"]]
       .drop_duplicates(["service_date", "trip_id", "stop_id"])
       .rename(columns={"arr_ts": "t"}))

zpath = sorted(glob.glob(str(DATA / "static" / "GTFS_KRK_A_*.zip")))[-1]
with zipfile.ZipFile(zpath) as z:
    st = pd.read_csv(z.open("stop_times.txt"), dtype=str,
                     usecols=["trip_id", "stop_id", "stop_sequence", "arrival_time"])
    trips = pd.read_csv(z.open("trips.txt"), dtype=str)
p = st["arrival_time"].str.strip().str.split(":", expand=True).astype(int)
st["arr_s"] = p[0] * 3600 + p[1] * 60 + p[2]
st["stop_sequence"] = st["stop_sequence"].astype(int)
dircol = next((c for c in ("direction_id", "trip_headsign") if c in trips.columns), None)
trips["dir"] = trips[dircol].fillna("?") if dircol else "0"
st = st.merge(trips[["trip_id", "route_id", "dir"]], on="trip_id")

rank = st.groupby("trip_id")["stop_sequence"].rank(method="first")
size = st.groupby("trip_id")["stop_sequence"].transform("size")
st["frac"] = (rank - 1) / (size - 1)                       # pozycja wzdluz trasy 0..1
st = st[~st.duplicated(["trip_id", "stop_id"], keep=False)]  # petle pomijamy
st = st.merge(seen, on="trip_id")

st = st.sort_values(["service_date", "route_id", "dir", "stop_id", "arr_s"])
g = st.groupby(["service_date", "route_id", "dir", "stop_id"])
st["prev_trip"] = g["trip_id"].shift(1)
st["h_sched"] = st["arr_s"] - g["arr_s"].shift(1)
pairs = st.dropna(subset=["prev_trip"])
pairs = pairs[(pairs["h_sched"] > 0) & (pairs["h_sched"] <= MAX_H)]
pairs = pairs.merge(obs, on=["service_date", "trip_id", "stop_id"])
pairs = pairs.merge(obs.rename(columns={"trip_id": "prev_trip", "t": "t_prev"}),
                    on=["service_date", "prev_trip", "stop_id"])
pairs["h_obs"] = (pairs["t"] - pairs["t_prev"]).astype(float)
pairs["ratio"] = pairs["h_obs"] / pairs["h_sched"].astype(float)
pairs.to_parquet(PROC / "headway_pairs.parquet", index=False)


def summarize(df):
    h = df["h_obs"].clip(lower=0)
    hs = df["h_sched"].astype(float)
    return pd.Series({
        "n": len(df),
        "ratio_med": df["ratio"].median(),
        "cv_ratio": df["ratio"].std() / df["ratio"].mean(),
        "bunched": (df["ratio"] < 0.25).mean(),    # progi umowne
        "gapped": (df["ratio"] > 1.75).mean(),
        "swapped": (df["h_obs"] < 0).mean(),       # kolejnosc zamieniona (wyprzedzenie)
        "W_obs_min": (h ** 2).sum() / (2 * h.sum()) / 60,
        "W_sched_min": (hs ** 2).sum() / (2 * hs.sum()) / 60,
    })


print("par odstepow:", len(pairs), " linii/kierunkow:", pairs.groupby(["route_id", "dir"]).ngroups)
print("\nCALOSC:\n", summarize(pairs).round(3))

by_line = (pairs.groupby(["route_id", "dir"]).apply(summarize, include_groups=False)
           .query("n >= @MIN_PAIRS").sort_values("n", ascending=False))
print("\nWEDLUG LINII I KIERUNKU (top 15):\n", by_line.head(15).round(3))

top = by_line.head(5).reset_index()[["route_id", "dir"]]
sub = pairs.merge(top, on=["route_id", "dir"])
sub["pos"] = pd.cut(sub["frac"], [-0.001, .25, .5, .75, 1.001],
                    labels=["0-25%", "25-50%", "50-75%", "75-100%"])
print("\nZMIENNOSC WZDLUZ TRASY (5 najliczniejszych linii):")
print(sub.groupby(["route_id", "dir", "pos"], observed=True)
      .apply(summarize, include_groups=False)[["n", "cv_ratio", "bunched", "gapped"]].round(3))

hour = pd.to_datetime(pairs["t"], unit="s", utc=True).dt.tz_convert("Europe/Warsaw").dt.hour
print("\nWEDLUG GODZINY:\n", pairs.groupby(hour).apply(summarize, include_groups=False)
      [["n", "cv_ratio", "bunched", "gapped", "W_obs_min", "W_sched_min"]].round(2))