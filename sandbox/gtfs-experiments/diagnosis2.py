import glob, zipfile
import numpy as np
import pandas as pd

vp = pd.read_parquet("data/raw_A/vehicle_positions")
vp = vp.drop_duplicates(["vehicle_id", "veh_ts"]).dropna(
    subset=["veh_ts", "trip_id", "current_stop_sequence", "current_status"])

zpath = sorted(glob.glob("data/raw_A/static/GTFS_KRK_A_*.zip"))[-1]
with zipfile.ZipFile(zpath) as z:
    stops = pd.read_csv(z.open("stops.txt"), dtype={"stop_id": str},
                        usecols=["stop_id", "stop_lat", "stop_lon"])
    stt = pd.read_csv(z.open("stop_times.txt"), dtype={"trip_id": str, "stop_id": str},
                      usecols=["trip_id", "stop_id", "stop_sequence"])
stt = stt.merge(stops, on="stop_id")


def dist_m(lat1, lon1, lat2, lon2):
    k = 111_320.0
    dy = (lat2 - lat1) * k
    dx = (lon2 - lon1) * k * np.cos(np.radians((lat1 + lat2) / 2))
    return np.hypot(dx, dy)


# --- A. do ktorego przystanku jest blizej pojazd? ---
res = vp[["trip_id", "lat", "lon", "current_status"]].copy()
res["trip_id"] = res["trip_id"].astype(str)
res["cs"] = vp["current_stop_sequence"].astype(int)
for off in (0, 1):
    ref = stt.assign(cs=stt["stop_sequence"] - off)[["trip_id", "cs", "stop_lat", "stop_lon"]]
    m = res.merge(ref, on=["trip_id", "cs"], how="left")
    res[f"d{off}"] = dist_m(m["lat"], m["lon"], m["stop_lat"], m["stop_lon"]).to_numpy()
print("mediana odleglosci [m] od przystanku (current_stop_sequence + 0 / + 1):")
print(res.groupby("current_status")[["d0", "d1"]].median().round(0))
print("udzial obserwacji, gdzie blizej jest przystanek +1:")
print((res["d1"] < res["d0"]).groupby(res["current_status"]).mean().round(3))

# --- B. epizody postoju (status 1) i ich dlugosc ---
v = vp.sort_values(["vehicle_id", "veh_ts"]).copy()
v["stopped"] = v["current_status"] == 1
cols = ["vehicle_id", "trip_id", "current_stop_sequence", "stopped"]
v["ep"] = (v[cols] != v[cols].shift()).any(axis=1).cumsum()
ep = (v[v["stopped"]].groupby("ep")
      .agg(trip_id=("trip_id", "first"), seq=("current_stop_sequence", "first"),
           t0=("veh_ts", "min"), t1=("veh_ts", "max"), n=("veh_ts", "size")))
ep["dwell_s"] = ep["t1"] - ep["t0"]
print("\nliczba epizodow postoju:", len(ep), " z jedna probka:", round((ep["n"] == 1).mean(), 3))
print(ep["dwell_s"].describe(percentiles=[.1, .25, .5, .75, .9, .99]).round(1))
first_seq = stt.groupby("trip_id")["stop_sequence"].min().rename("first_seq")
ep = ep.join(first_seq, on="trip_id")
print("mediana postoju na pierwszym przystanku kursu [s]:",
      ep.loc[ep["seq"] == ep["first_seq"], "dwell_s"].median(),
      " na pozostalych:", ep.loc[ep["seq"] != ep["first_seq"], "dwell_s"].median())