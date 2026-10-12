"""corridors.py: odstepy miedzy kolejnymi autobusami DOWOLNEJ linii na tym samym slupku."""
import glob
import zipfile
from pathlib import Path

import pandas as pd

DATA = Path("data/raw_A")
PROC = Path("data/processed")
MIN_H, MAX_H = 180, 1800      # zakres odstepow rozkladowych branych pod uwage [s]
MAX_ABS_DELAY = 1800
MIN_PAIRS = 100

ev = pd.read_parquet(PROC / "observed_events.parquet")
ev["trip_id"] = ev["trip_id"].astype(str)
ev["stop_id"] = ev["stop_id"].astype(str)
seen = ev[["service_date", "trip_id"]].drop_duplicates()
mask = (ev["arr_ok"] & (ev["arr_delay_s"].abs() <= MAX_ABS_DELAY)).fillna(False).astype(bool)
obs = (ev[mask][["service_date", "trip_id", "stop_id", "arr_ts"]]
       .drop_duplicates(["service_date", "trip_id", "stop_id"])
       .rename(columns={"arr_ts": "t"}))

zpath = sorted(glob.glob(str(DATA / "static" / "GTFS_KRK_A_*.zip")))[-1]
with zipfile.ZipFile(zpath) as z:
    st = pd.read_csv(z.open("stop_times.txt"), dtype=str,
                     usecols=["trip_id", "stop_id", "arrival_time"])
    stops = pd.read_csv(z.open("stops.txt"), dtype=str, usecols=["stop_id", "stop_name"])
p = st["arrival_time"].str.strip().str.split(":", expand=True).astype(int)
st["arr_s"] = p[0] * 3600 + p[1] * 60 + p[2]
st = st[~st.duplicated(["trip_id", "stop_id"], keep=False)].merge(seen, on="trip_id")

st = st.sort_values(["service_date", "stop_id", "arr_s"])
g = st.groupby(["service_date", "stop_id"])
st["prev_trip"] = g["trip_id"].shift(1)
st["h_sched"] = st["arr_s"] - g["arr_s"].shift(1)
pairs = st.dropna(subset=["prev_trip"])
pairs = pairs[(pairs["h_sched"] >= MIN_H) & (pairs["h_sched"] <= MAX_H)]
pairs = pairs.merge(obs, on=["service_date", "trip_id", "stop_id"])
pairs = pairs.merge(obs.rename(columns={"trip_id": "prev_trip", "t": "t_prev"}),
                    on=["service_date", "prev_trip", "stop_id"])
pairs["h_obs"] = (pairs["t"] - pairs["t_prev"]).astype(float)
pairs["h_sched"] = pairs["h_sched"].astype(float)
pairs["ratio"] = pairs["h_obs"] / pairs["h_sched"]
pairs.to_parquet(PROC / "corridor_pairs.parquet", index=False)


def summarize(df):
    h = df["h_obs"].clip(lower=0)
    return pd.Series({
        "n": len(df),
        "h_sched_med_min": df["h_sched"].median() / 60,
        "cv_ratio": df["ratio"].std() / df["ratio"].mean(),
        "within60s": (df["h_obs"] < 60).mean(),      # prawie jednoczesny przyjazd mimo >= 3 min w rozkladzie
        "ratio_lt_0.5": (df["ratio"] < 0.5).mean(),
        "ratio_gt_1.5": (df["ratio"] > 1.5).mean(),
        "swapped": (df["h_obs"] < 0).mean(),
        "W_obs_min": (h ** 2).sum() / (2 * h.sum()) / 60,
        "W_sched_min": (df["h_sched"] ** 2).sum() / (2 * df["h_sched"].sum()) / 60,
    })


print("par:", len(pairs), " slupkow:", pairs["stop_id"].nunique())
print("\nCALOSC:\n", summarize(pairs).round(3))

by_stop = (pairs.groupby("stop_id").apply(summarize, include_groups=False)
           .query("n >= @MIN_PAIRS").sort_values("n", ascending=False)
           .join(stops.set_index("stop_id")["stop_name"]))
print("\nNAJLICZNIEJSZE SLUPKI:\n", by_stop.head(15).round(3).to_string())
print("\nNAJGORSZA REGULARNOSC (wg cv_ratio):\n",
      by_stop.sort_values("cv_ratio", ascending=False).head(10).round(3).to_string())

hour = pd.to_datetime(pairs["t"], unit="s", utc=True).dt.tz_convert("Europe/Warsaw").dt.hour
print("\nWEDLUG GODZINY:\n", pairs.groupby(hour).apply(summarize, include_groups=False)
      [["n", "cv_ratio", "within60s", "ratio_lt_0.5", "W_obs_min", "W_sched_min"]].round(3))