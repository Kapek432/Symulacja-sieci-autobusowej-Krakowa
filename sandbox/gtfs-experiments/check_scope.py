"""check_scope.py: (1) block_id i lancuchy kursow, (2) korytarz wokol linii pilotowej.
Uzycie: uv run check_scope.py [linia] [direction_id]    np. uv run check_scope.py 179 1
"""
import glob
import sys
import zipfile

import pandas as pd

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", None)

PILOT = sys.argv[1] if len(sys.argv) > 1 else "179"
PILOT_DIR = sys.argv[2] if len(sys.argv) > 2 else None
DAY = "2026-10-05"
TZ = "Europe/Warsaw"


def hms(col):
    p = col.astype("string").str.strip().str.split(":", expand=True)
    return pd.to_numeric(p[0]) * 3600 + pd.to_numeric(p[1]) * 60 + pd.to_numeric(p[2])


zpath = sorted(glob.glob("data/raw_A/static/GTFS_KRK_A_*.zip"))[-1]
print("GTFS:", zpath)
with zipfile.ZipFile(zpath) as z:
    names = z.namelist()
    trips = pd.read_csv(z.open("trips.txt"), dtype=str)
    st = pd.read_csv(z.open("stop_times.txt"), dtype=str,
                     usecols=["trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"])
    stops = pd.read_csv(z.open("stops.txt"), dtype=str, usecols=["stop_id", "stop_name"])
    blocks_head = pd.read_csv(z.open("blocks.txt"), dtype=str, nrows=5) if "blocks.txt" in names else None

print("\n=== 1. BLOCK_ID ===")
print("pliki w GTFS:", names)
print("kolumny trips.txt:", list(trips.columns))
has_block = "block_id" in trips.columns and trips["block_id"].notna().any()
print("block_id w trips.txt i wypelniony:", has_block)
if blocks_head is not None:
    print("blocks.txt (poczatek):\n", blocks_head)

st["stop_sequence"] = st["stop_sequence"].astype(int)
st = st.sort_values(["trip_id", "stop_sequence"])
first = st.groupby("trip_id").first()
last = st.groupby("trip_id").last()
name = stops.drop_duplicates("stop_id").set_index("stop_id")["stop_name"]
tt = pd.DataFrame({"start_s": hms(first["departure_time"]), "end_s": hms(last["arrival_time"]),
                   "first_name": first["stop_id"].map(name), "last_name": last["stop_id"].map(name)})
tr = trips.drop_duplicates("trip_id").set_index("trip_id").join(tt)
dir_col = "direction_id" if "direction_id" in tr.columns else None

if has_block:
    keys = [c for c in ("service_id", "block_id") if c in tr.columns]
    t = tr.dropna(subset=["block_id"]).sort_values(keys + ["start_s"]).copy()
    g = t.groupby(keys)
    t["next_route"] = g["route_id"].shift(-1)
    t["next_start"] = g["start_s"].shift(-1)
    t["next_first_name"] = g["first_name"].shift(-1)
    if dir_col:
        t["next_dir"] = g[dir_col].shift(-1)
    pr = t.dropna(subset=["next_route"]).copy()
    pr["layover_min"] = (pr["next_start"] - pr["end_s"]) / 60
    print(f"\nblokow (wg {keys}): {g.ngroups}, kursow w blokach: {len(t)}, "
          f"srednio kursow w bloku: {len(t) / g.ngroups:.1f}")
    print("pary kolejnych kursow w blokach:", len(pr))
    print("  zmiana linii:", round((pr["route_id"] != pr["next_route"]).mean(), 3))
    if dir_col:
        print("  zmiana kierunku:", round((pr[dir_col] != pr["next_dir"]).mean(), 3))
    print("  nastepny kurs zaczyna sie na przystanku o tej samej nazwie co koniec poprzedniego:",
          round((pr["last_name"] == pr["next_first_name"]).mean(), 3))
    print("  zapas na petli [min] (poczatek nastepnego - koniec poprzedniego):")
    print(pr["layover_min"].describe(percentiles=[.05, .25, .5, .75, .95]).round(1))
    print("  udzial zapasow < 3 min:", round((pr["layover_min"] < 3).mean(), 3),
          " ujemnych:", round((pr["layover_min"] < 0).mean(), 3))
    sub = pr[pr["route_id"] == PILOT]
    if len(sub):
        print(f"\nlinia {PILOT}: par {len(sub)}, zmiana linii {round((sub['route_id'] != sub['next_route']).mean(), 3)}, "
              f"mediana zapasu [min] {round(sub['layover_min'].median(), 1)}")

print("\n=== 1b. LANCUCHY Z LOGOW (pojazd -> kolejne kursy), dzien", DAY, "===")
vp = pd.read_parquet("data/raw_A/vehicle_positions", columns=["vehicle_id", "trip_id", "veh_ts"])
vp = vp.dropna(subset=["vehicle_id", "trip_id", "veh_ts"]).copy()
vp["vehicle_id"] = vp["vehicle_id"].astype(str)
vp["trip_id"] = vp["trip_id"].astype(str)
day = pd.to_datetime(vp["veh_ts"].astype("int64"), unit="s", utc=True).dt.tz_convert(TZ).dt.strftime("%Y-%m-%d")
vp = vp[day == DAY]
seen = (vp.groupby(["vehicle_id", "trip_id"])["veh_ts"].min().reset_index()
        .sort_values(["vehicle_id", "veh_ts"]))
seen["next_trip"] = seen.groupby("vehicle_id")["trip_id"].shift(-1)
ch = seen.dropna(subset=["next_trip"]).copy()
cols = ["route_id", "start_s", "end_s", "first_name", "last_name"] + ([dir_col] if dir_col else []) \
       + (["block_id"] if has_block else [])
ch = ch.join(tr[cols].add_prefix("a_"), on="trip_id").join(tr[cols].add_prefix("b_"), on="next_trip")
ch = ch.dropna(subset=["a_route_id", "b_route_id"])
print("obserwowanych par kolejnych kursow tego samego pojazdu:", len(ch), " pojazdow:", ch["vehicle_id"].nunique())
print("  ta sama linia:", round((ch["a_route_id"] == ch["b_route_id"]).mean(), 3))
if dir_col:
    print("  zmiana kierunku:", round((ch[f"a_{dir_col}"] != ch[f"b_{dir_col}"]).mean(), 3))
if has_block:
    print("  ten sam block_id:", round((ch["a_block_id"] == ch["b_block_id"]).mean(), 3))
ch["layover_min"] = (ch["b_start_s"] - ch["a_end_s"]) / 60
print("  zapas rozkladowy miedzy kursami [min] (ujemne lub bardzo duze = pary niekolejne):")
print(ch["layover_min"].describe(percentiles=[.05, .25, .5, .75, .95]).round(1))
print("  nastepny kurs zaczyna sie na przystanku o tej samej nazwie co koniec poprzedniego:",
      round((ch["a_last_name"] == ch["b_first_name"]).mean(), 3))
sub = ch[ch["a_route_id"] == PILOT]
if len(sub):
    print(f"\nlinia {PILOT}: par {len(sub)}, ta sama linia {round((sub['a_route_id'] == sub['b_route_id']).mean(), 3)}, "
          f"mediana zapasu [min] {round(sub['layover_min'].median(), 1)}")

print("\n=== 2. KORYTARZ WOKOL LINII", PILOT, "===")
tp = trips[["trip_id", "route_id"] + ([dir_col] if dir_col else [])].drop_duplicates("trip_id")
s2 = st.merge(tp, on="trip_id").sort_values(["trip_id", "stop_sequence"])
s2["b"] = s2.groupby("trip_id")["stop_id"].shift(-1)
seg = s2.dropna(subset=["b"]).rename(columns={"stop_id": "a"})
pil_trips = seg[seg["route_id"] == PILOT]
if PILOT_DIR is not None and dir_col:
    pil_trips = pil_trips[pil_trips[dir_col] == PILOT_DIR]
pil = pil_trips[["a", "b"]].drop_duplicates()
if pil.empty:
    sys.exit(f"brak odcinkow dla linii {PILOT} (kierunek {PILOT_DIR})")
others = seg[seg["route_id"] != PILOT][["route_id", "a", "b"]].drop_duplicates()
shared = others.merge(pil, on=["a", "b"])
res = shared.groupby("route_id").size().rename("wspolne_odcinki").to_frame()
res["udzial_odcinkow_pilota"] = res["wspolne_odcinki"] / len(pil)
pil_stops = set(pil["a"]) | set(pil["b"])
res["wspolne_slupki"] = (s2[(s2["route_id"] != PILOT) & s2["stop_id"].isin(pil_stops)]
                         .groupby("route_id")["stop_id"].nunique())

pilot_events = None
try:
    ev = pd.read_parquet("data/processed/observed_events.parquet", columns=["route_id", "service_date", "arr_ok"])
    ev = ev[ev["service_date"] == DAY].copy()
    ev["route_id"] = ev["route_id"].astype(str)
    ev["arr_ok"] = ev["arr_ok"].fillna(False).astype(bool)
    cnt = ev.groupby("route_id").agg(zdarzenia=("arr_ok", "size"), zdarzenia_ok=("arr_ok", "sum"))
    res = res.join(cnt)
    pilot_events = cnt.loc[PILOT].to_dict() if PILOT in cnt.index else None
except Exception as e:
    print("brak observed_events:", e)

res = res.sort_values("wspolne_odcinki", ascending=False)
print(f"odcinkow pilota {PILOT}" + (f" (kierunek {PILOT_DIR})" if PILOT_DIR else "")
      + f": {len(pil)}, slupkow: {len(pil_stops)}, zdarzenia pilota w dniu {DAY}: {pilot_events}")
print(res.head(20).round(3))
print("\nlinie pokrywajace >= 30% odcinkow pilota:", list(res.index[res["udzial_odcinkow_pilota"] >= 0.3]))
print("linie pokrywajace >= 10% odcinkow pilota:", list(res.index[res["udzial_odcinkow_pilota"] >= 0.1]))