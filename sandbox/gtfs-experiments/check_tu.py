import glob, zipfile
import numpy as np
import pandas as pd

DATA = "data/raw_A"
TZ = "Europe/Warsaw"
vp = pd.read_parquet(f"{DATA}/vehicle_positions")
tu = pd.read_parquet(f"{DATA}/trip_updates")
tu["trip_id"] = tu["trip_id"].astype(str)
vp["trip_id"] = vp["trip_id"].astype(str)

zpath = sorted(glob.glob(f"{DATA}/static/GTFS_KRK_A_*.zip"))[-1]
with zipfile.ZipFile(zpath) as z:
    st = pd.read_csv(z.open("stop_times.txt"), dtype=str,
                     usecols=["trip_id", "stop_id", "arrival_time"])
p = st["arrival_time"].str.split(":", expand=True).astype(int)
st["arr_s"] = p[0] * 3600 + p[1] * 60 + p[2]
dup = st.duplicated(["trip_id", "stop_id"], keep=False)
st = st.loc[~dup, ["trip_id", "stop_id", "arr_s"]]

# czy kurs ma pojazd w najblizszej migawce pozycji?
vsnap = np.sort(vp["fetched_at"].unique())
tsnap = np.sort(tu["fetched_at"].unique())
idx = np.clip(np.searchsorted(vsnap, tsnap), 1, len(vsnap) - 1)
nearest = np.where(np.abs(vsnap[idx] - tsnap) < np.abs(vsnap[idx - 1] - tsnap),
                   vsnap[idx], vsnap[idx - 1])
snap = dict(zip(tsnap, nearest))
pairs = set(zip(vp["fetched_at"], vp["trip_id"]))
tu["has_veh"] = [(snap[f], t) in pairs for f, t in zip(tu["fetched_at"], tu["trip_id"])]

# opoznienie z arr_time, bez przystankow powtarzajacych sie w kursie
c = tu[(tu["arr_time"] > 10**9).fillna(False)].merge(st, on=["trip_id", "stop_id"], how="inner")
local = pd.to_datetime(c["fetched_at"], unit="s", utc=True).dt.tz_convert(TZ)
epoch = pd.Timestamp("1970-01-01", tz="UTC")
mid0 = (local.dt.normalize() - epoch).dt.total_seconds()
mid1 = ((local - pd.Timedelta(days=1)).dt.normalize() - epoch).dt.total_seconds()
a0 = c["arr_time"] - (mid0 + c["arr_s"])
a1 = c["arr_time"] - (mid1 + c["arr_s"])
c["delay_s"] = a0.where(a0.abs() <= a1.abs(), a1)

print("udzial wpisow TripUpdates z pojazdem:", round(tu["has_veh"].mean(), 3))
print(c.groupby("has_veh")["delay_s"].agg(
    n="size", zero=lambda s: (s == 0).mean(), mediana="median",
    q25=lambda s: s.quantile(.25), q75=lambda s: s.quantile(.75)).round(3))