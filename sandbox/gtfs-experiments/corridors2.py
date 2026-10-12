"""corridors2.py: pary miedzy autobusami na tym samym slupku - pasma odstepu, ta sama linia vs rozne, model zerowy."""
import glob
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.max_columns", None)

DATA = Path("data/raw_A")
PROC = Path("data/processed")
ORDER = ["3-5", "5-10", "10-20", "20-30"]
K = 20                      # powtorzenia modelu zerowego
MIN_PAIRS_NAME = 30

pairs = pd.read_parquet(PROC / "corridor_pairs.parquet")
pairs["h_obs"] = pairs["h_obs"].astype(float)
pairs["h_sched"] = pairs["h_sched"].astype(float)

zpath = sorted(glob.glob(str(DATA / "static" / "GTFS_KRK_A_*.zip")))[-1]
with zipfile.ZipFile(zpath) as z:
    trips = pd.read_csv(z.open("trips.txt"), dtype=str, usecols=["trip_id", "route_id"])
    stt = pd.read_csv(z.open("stop_times.txt"), dtype=str, usecols=["trip_id", "stop_id"])
    stops = pd.read_csv(z.open("stops.txt"), dtype=str, usecols=["stop_id", "stop_name"])

route = trips.set_index("trip_id")["route_id"]
pairs["same_route"] = pairs["trip_id"].map(route) == pairs["prev_trip"].map(route)
pairs["e_s"] = pairs["h_obs"] - pairs["h_sched"]
pairs["band"] = pd.cut(pairs["h_sched"], [179, 300, 600, 1200, 1801], labels=ORDER).astype(str)

nroutes = stt.merge(trips, on="trip_id").groupby("stop_id")["route_id"].nunique().rename("n_routes")
pairs = pairs.join(nroutes, on="stop_id")
pairs["hub"] = pd.cut(pairs["n_routes"], [0, 1, 2, 4, 1000], labels=["1", "2", "3-4", "5+"]).astype(str)
pairs = pairs.merge(stops, on="stop_id", how="left")


def w_min(h):
    s = h.sum()
    return (h ** 2).sum() / (2 * s) / 60 if s > 0 else np.nan


def summ(df):
    h = df["h_obs"].clip(lower=0)
    return pd.Series({
        "n": len(df),
        "e_med_s": df["e_s"].median(),
        "e_iqr_s": df["e_s"].quantile(.75) - df["e_s"].quantile(.25),
        "within60s": (df["h_obs"] < 60).mean(),
        "swapped": (df["h_obs"] < 0).mean(),
        "lt_half": (df["h_obs"] < 0.5 * df["h_sched"]).mean(),
        "gt_1.5": (df["h_obs"] > 1.5 * df["h_sched"]).mean(),
        "dW_s": 60 * (w_min(h) - w_min(df["h_sched"])),
    })


pd.set_option("display.width", 200)
print("par:", len(pairs), " ta sama linia:", round(pairs["same_route"].mean(), 3))

print("\nTA SAMA LINIA vs ROZNE LINIE:")
print(pairs.groupby("same_route").apply(summ, include_groups=False).round(3))

print("\nWEDLUG PASMA ODSTEPU ROZKLADOWEGO [min]:")
print(pairs.groupby("band").apply(summ, include_groups=False).reindex(ORDER).round(3))

print("\nWEDLUG LICZBY LINII NA SLUPKU:")
print(pairs.groupby("hub").apply(summ, include_groups=False).reindex(["1", "2", "3-4", "5+"]).round(3))

# model zerowy: opoznienia obu autobusow niezalezne, z empirycznego rozkladu opoznien
ev = pd.read_parquet(PROC / "observed_events.parquet")
d = ev.loc[ev["arr_ok"].fillna(False).astype(bool) & (ev["arr_delay_s"].abs() <= 1800),
           "arr_delay_s"].astype(float).to_numpy()
rng = np.random.default_rng(0)
idx = np.repeat(np.arange(len(pairs)), K)
sim = pd.DataFrame({"band": pairs["band"].to_numpy()[idx],
                    "same_route": pairs["same_route"].to_numpy()[idx]})
sim["h"] = (pairs["h_sched"].to_numpy()[idx]
            + rng.choice(d, len(sim)) - rng.choice(d, len(sim)))


def small(df, col):
    return pd.Series({"n": len(df), "within60s": (df[col] < 60).mean(), "swapped": (df[col] < 0).mean()})


obs_t = pairs.groupby("band").apply(lambda g: small(g, "h_obs"), include_groups=False)
sim_t = sim.groupby("band").apply(lambda g: small(g, "h"), include_groups=False)
cmp_ = obs_t.join(sim_t[["within60s", "swapped"]], rsuffix="_niezalezne")
print("\nOBSERWACJA vs MODEL ZEROWY (niezalezne opoznienia):")
print(cmp_.reindex(ORDER).round(3))

obs_s = pairs.groupby(["band", "same_route"]).apply(lambda g: small(g, "h_obs"), include_groups=False)
sim_s = sim.groupby(["band", "same_route"]).apply(lambda g: small(g, "h"), include_groups=False)
print("\nTO SAMO, Z PODZIALEM NA TA SAMA LINIE:")
print(obs_s.join(sim_s[["within60s", "swapped"]], rsuffix="_niezalezne").round(3))

by_name = (pairs.groupby("stop_name").apply(summ, include_groups=False)
           .query("n >= @MIN_PAIRS_NAME").sort_values("n", ascending=False))
print(f"\nPRZYSTANKI (po nazwie, n >= {MIN_PAIRS_NAME}), liczba:", len(by_name))
print(by_name.head(15).round(3))
print("\nNAJWIEKSZA KOMPRESJA (within60s):")
print(by_name.sort_values("within60s", ascending=False).head(10).round(3))