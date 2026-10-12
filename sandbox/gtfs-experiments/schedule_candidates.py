"""schedule_candidates.py: linie i slupki o duzej czestotliwosci w danym dniu (wg rozkladu)."""
import glob
import sys
import zipfile
from pathlib import Path

import pandas as pd

DATA = Path("data/raw_A")
DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-10-05"       # poniedzialek
WINDOWS = {"szczyt_rano": (7 * 3600, 9 * 3600), "poludnie": (11 * 3600, 14 * 3600),
           "szczyt_pop": (15 * 3600, 18 * 3600)}

zpath = sorted(glob.glob(str(DATA / "static" / "GTFS_KRK_A_*.zip")))[-1]
d = pd.Timestamp(DATE)
ymd = d.strftime("%Y%m%d")
wd = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][d.weekday()]

with zipfile.ZipFile(zpath) as z:
    names = set(z.namelist())
    trips = pd.read_csv(z.open("trips.txt"), dtype=str)
    st = pd.read_csv(z.open("stop_times.txt"), dtype=str,
                     usecols=["trip_id", "stop_id", "arrival_time"])
    stops = pd.read_csv(z.open("stops.txt"), dtype=str, usecols=["stop_id", "stop_name"])
    active = set()
    if "calendar.txt" in names:
        cal = pd.read_csv(z.open("calendar.txt"), dtype=str)
        ok = (cal["start_date"] <= ymd) & (cal["end_date"] >= ymd) & (cal[wd] == "1")
        active |= set(cal.loc[ok, "service_id"])
    if "calendar_dates.txt" in names:
        cd = pd.read_csv(z.open("calendar_dates.txt"), dtype=str)
        cd = cd[cd["date"] == ymd]
        active |= set(cd.loc[cd["exception_type"] == "1", "service_id"])
        active -= set(cd.loc[cd["exception_type"] == "2", "service_id"])

if active:
    tr = trips[trips["service_id"].isin(active)].copy()
else:
    print("UWAGA: brak informacji o kalendarzu, biore wszystkie kursy")
    tr = trips.copy()
dircol = "direction_id" if "direction_id" in tr.columns else None
tr["dir"] = tr[dircol].fillna("?") if dircol else "0"
print(f"data {DATE}: aktywnych kursow {len(tr)} z {len(trips)}")

st = st[~st.duplicated(["trip_id", "stop_id"], keep=False)].merge(
    tr[["trip_id", "route_id", "dir"]], on="trip_id")
p = st["arrival_time"].str.strip().str.split(":", expand=True).astype(int)
st["t"] = p[0] * 3600 + p[1] * 60 + p[2]

# 1. linia/kierunek: odstep na najczesciej obslugiwanym slupku linii
cnt = st.groupby(["route_id", "dir", "stop_id"]).size().rename("n").reset_index()
ref = cnt.sort_values("n", ascending=False).drop_duplicates(["route_id", "dir"])
r = st.merge(ref[["route_id", "dir", "stop_id"]], on=["route_id", "dir", "stop_id"]).sort_values(
    ["route_id", "dir", "t"])
r["h"] = r.groupby(["route_id", "dir"])["t"].diff()
res = pd.DataFrame({name: r[(r["t"] >= a) & (r["t"] < b)].groupby(["route_id", "dir"])["h"].median() / 60
                    for name, (a, b) in WINDOWS.items()})
res = res.join(ref.set_index(["route_id", "dir"])["stop_id"]).reset_index().merge(
    stops, on="stop_id", how="left")
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", None)
print("\nLINIE O NAJKROTSZYM ODSTEPIE W SZCZYCIE RANO [min, mediana]:")
print(res.sort_values("szczyt_rano").head(20).round(1).to_string(index=False))
print("linie z odstepem <= 8 min w szczycie rano:", int((res["szczyt_rano"] <= 8).sum()),
      " <= 6 min:", int((res["szczyt_rano"] <= 6).sum()))

# 2. slupki: przyjazdy na godzine (wszystkie linie razem)
s = st.sort_values(["stop_id", "t"]).copy()
for name, (a, b) in WINDOWS.items():
    w = s[(s["t"] >= a) & (s["t"] < b)]
    g = (w.groupby("stop_id").agg(przyjazdy_na_h=("t", lambda x: len(x) / ((b - a) / 3600)),
                                  linie=("route_id", "nunique"))
         .join(stops.set_index("stop_id")["stop_name"]).sort_values("przyjazdy_na_h", ascending=False))
    print(f"\nSLUPKI WG PRZYJAZDOW NA GODZINE, {name}:")
    print(g.head(12).round(1).to_string())