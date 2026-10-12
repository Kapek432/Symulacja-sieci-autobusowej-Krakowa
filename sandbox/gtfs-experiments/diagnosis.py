import glob, zipfile
import pandas as pd
from zoneinfo import ZoneInfo

tz = ZoneInfo("Europe/Warsaw")
vp = pd.read_parquet("data/raw_A/vehicle_positions")
tu = pd.read_parquet("data/raw_A/trip_updates")
keys = ["fetched_at", "trip_id"]
tu["rank"] = tu.groupby(keys).cumcount()

print("zakres czasu:", pd.to_datetime(vp["fetched_at"].min(), unit="s", utc=True),
      "->", pd.to_datetime(vp["fetched_at"].max(), unit="s", utc=True))
print("migawek pozycji:", vp["fetched_at"].nunique(),
      " migawek prognoz:", tu["fetched_at"].nunique())

zpath = sorted(glob.glob("data/raw_A/static/GTFS_KRK_A_*.zip"))[-1]
with zipfile.ZipFile(zpath) as z:
    st = pd.read_csv(z.open("stop_times.txt"), dtype={"trip_id": str, "stop_id": str},
                     usecols=["trip_id", "stop_id", "stop_sequence", "departure_time"])
p = st["departure_time"].str.split(":", expand=True).astype(int)
st["dep_s"] = p[0] * 3600 + p[1] * 60 + p[2]

# A. skad biora sie czasy rowne 0
print(tu["sched_rel"].value_counts(dropna=False))
print("dep_time == 0:", int((tu["dep_time"] == 0).sum()),
      " arr_time == 0:", int((tu["arr_time"] == 0).sum()))

# B. opoznienie tylko z poprawnych czasow, bez przystankow powtarzajacych sie w kursie
dup = st.duplicated(["trip_id", "stop_id"], keep=False)
c = tu[(tu["dep_time"] > 10**9).fillna(False)].merge(
    st.loc[~dup, ["trip_id", "stop_id", "dep_s"]], on=["trip_id", "stop_id"], how="inner")
local = pd.to_datetime(c["fetched_at"], unit="s", utc=True).dt.tz_convert(tz)
mid = (local.dt.normalize().dt.tz_convert("UTC")
       - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()
d0 = c["dep_time"] - (mid + c["dep_s"])
d1 = c["dep_time"] - (mid - 86400 + c["dep_s"])
c["delay_s"] = d0.where(d0.abs() <= d1.abs(), d1)
print(c["delay_s"].describe(percentiles=[.01, .05, .25, .5, .75, .95, .99]).round(1))
print("udzial dokladnie 0 s:", round((c["delay_s"] == 0).mean(), 3))

# C. czy arr_delay oznacza kursy "z opoznieniem"?
has = c["arr_delay"].notna()
print("udzial 0 s przy wypelnionym arr_delay:", round((c.loc[has, "delay_s"] == 0).mean(), 3),
      " przy pustym:", round((c.loc[~has, "delay_s"] == 0).mean(), 3))
print((c.loc[has, "arr_delay"] - c.loc[has, "delay_s"]).describe().round(1))

# D. czy opoznienie jest stale wzdluz kursu (tylko kursy z niezerowym opoznieniem)?
grp = c.groupby(keys)["delay_s"]
nz = grp.agg(lambda s: bool((s != 0).any()))
print("kursy z niezerowym opoznieniem:", round(nz.mean(), 3))
print("mediana odchylenia w kursie, tylko te kursy [s]:", round(grp.std()[nz].median(), 1))

# E. czy prognoza dla tego samego kursu zmienia sie w czasie?
r1 = c[c["rank"] == 1].groupby("trip_id")["delay_s"].agg(["nunique", "count"])
r1 = r1[r1["count"] >= 5]
print("kursy obserwowane >= 5 razy:", len(r1),
      " z >= 2 roznymi prognozami:", round((r1["nunique"] > 1).mean(), 3))

# F. czy pierwszy przystanek prognozy odpowiada pozycji z VehiclePositions?
v = vp.drop_duplicates(keys)[keys + ["current_stop_sequence"]]
r0 = tu[tu["rank"] == 0][keys + ["stop_id"]].merge(v, on=keys)
for off in (0, 1):
    s = st[["trip_id", "stop_sequence", "stop_id"]].copy()
    s["current_stop_sequence"] = s["stop_sequence"] - off
    s = s.drop(columns="stop_sequence").rename(columns={"stop_id": "stop_ref"})
    m = r0.merge(s, on=["trip_id", "current_stop_sequence"], how="left")
    print(f"pierwszy przystanek prognozy == przystanek (current_stop_sequence + {off}):",
          round((m["stop_id"] == m["stop_ref"]).mean(), 3))

print("\nudzial ujemnych opoznien:", round((c["delay_s"] < 0).mean(), 4))

# regula: przesuniecie pierwszego przystanku prognozy wzgledem current_stop_sequence
v = vp.drop_duplicates(keys)[keys + ["current_stop_sequence", "current_status"]]
r0 = tu[tu["rank"] == 0][keys + ["stop_id"]].merge(v, on=keys)
s = st[["trip_id", "stop_sequence", "stop_id"]].rename(columns={"stop_id": "stop_ref"})
for off in (0, 1):
    ref = s.assign(current_stop_sequence=s["stop_sequence"] - off).drop(columns="stop_sequence")
    m = r0.merge(ref, on=["trip_id", "current_stop_sequence"], how="left")
    r0[f"match_{off}"] = (m["stop_id"] == m["stop_ref"]).fillna(False).to_numpy(dtype=bool)
print(r0["current_status"].value_counts())
print(r0.groupby("current_status")[["match_0", "match_1"]].mean().round(3))