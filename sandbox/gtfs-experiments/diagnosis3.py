import glob, zipfile
import numpy as np
import pandas as pd

vp = pd.read_parquet("data/raw_A/vehicle_positions")
vp = vp.dropna(subset=["veh_ts", "trip_id", "current_stop_sequence", "current_status"])
vp = vp.drop_duplicates(["vehicle_id", "veh_ts"]).sort_values(["vehicle_id", "veh_ts"])
vp["cs"] = vp["current_stop_sequence"].astype(int)
vp["status"] = vp["current_status"].astype(int)
vp["trip_id"] = vp["trip_id"].astype(str)

# 1. prawdziwy rytm raportowania pojedynczego pojazdu
d = vp.groupby("vehicle_id")["veh_ts"].diff().dropna().astype(int)
print("odstep miedzy roznymi raportami pojazdu [s]:")
print(d.describe(percentiles=[.1, .25, .5, .75, .9]).round(1))
print(d.value_counts().head(10))

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


# 2. kierunek ruchu wzgledem przystanku cs przy statusie 2
ref = stt[["trip_id", "stop_sequence", "stop_lat", "stop_lon"]].rename(
    columns={"stop_sequence": "cs"})
m = vp.merge(ref, on=["trip_id", "cs"], how="left")
m = m.sort_values(["vehicle_id", "veh_ts"]).reset_index(drop=True)
m["d0"] = dist_m(m["lat"], m["lon"], m["stop_lat"], m["stop_lon"])
g = m.groupby(["vehicle_id", "trip_id", "cs"])
m["dd0"] = g["d0"].diff()
m["dt"] = g["veh_ts"].diff()
s2 = m[(m["status"] == 2) & (m["dt"] > 0)]
print("\nstatus 2, kolejne raporty z tym samym cs: n =", len(s2))
print("  odleglosc do cs maleje:", round((s2["dd0"] < 0).mean(), 3),
      " rosnie:", round((s2["dd0"] > 0).mean(), 3))
s0 = m[(m["status"] == 0) & (m["dt"] > 0)]
print("status 0: maleje:", round((s0["dd0"] < 0).mean(), 3),
      " rosnie:", round((s0["dd0"] > 0).mean(), 3))

# 3. pokrycie: dla ilu przystankow miedzy pierwszym i ostatnim zaobserwowanym jest probka postoju
seqs = stt.groupby("trip_id")["stop_sequence"].apply(lambda s: np.sort(s.to_numpy())).to_dict()
rng = m.groupby(["vehicle_id", "trip_id"])["cs"].agg(["min", "max"])
st1 = set(map(tuple, m.loc[m["status"] == 1, ["vehicle_id", "trip_id", "cs"]].to_numpy()))
tot = hit = 0
for (veh, trip), r in rng.iterrows():
    arr = seqs.get(trip)
    if arr is None:
        continue
    for s in arr[(arr > r["min"]) & (arr < r["max"])]:   # bez skrajnych, moga byc obciete
        tot += 1
        hit += (veh, trip, int(s)) in st1
print("\nprzystanki miedzy pierwszym a ostatnim zaobserwowanym:", tot,
      " z probka postoju (status 1):", round(hit / tot, 3) if tot else None)