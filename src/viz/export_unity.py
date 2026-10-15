"""export_unity.py: eksport pozycji autobusow do odtwarzania w Unity (kontrakt: EXPORT.md).

Wejscie: data/raw_A/vehicle_positions (logger) + rozklad GTFS z data/raw_A/static.
Wyjscie: <out>.jsonl (jeden wiersz = jeden raport pojazdu) oraz <out>.meta.json.

Opoznienie liczymy z pozycji i rozkladu (TripUpdates ZTP nie podaja opoznien):
- STOPPED_AT (1) na przystanku s: veh_ts - rozkladowy przyjazd na s,
- w drodze do s (0, 2): rozkladowy czas interpolowany miedzy odjazdem z s-1 a przyjazdem na s
  wedlug odleglosci w linii prostej do obu przystankow.
Data obslugi: dzis albo wczoraj (czas lokalny), ta, ktora daje mniejsze |opoznienie|.
Pojazd czekajacy na petli przed odjazdem: layover=true, delay_s=null.

Przyklady:
  uv run src/viz/export_unity.py
  uv run src/viz/export_unity.py --from 2026-10-16T07:00 --to 2026-10-16T09:00 --routes 179,169,174
"""

import argparse
import glob
import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

SCHEMA_VERSION = 1
TZ = "Europe/Warsaw"
# poczatek lokalnego ukladu wspolrzednych w Unity: Rynek Glowny
ORIGIN_LAT, ORIGIN_LON = 50.0617, 19.9373
EARTH_R = 6_371_000.0
LAYOVER_RADIUS_M = 150  # tak blisko 1. przystanku = pojazd jeszcze stoi na petli (parkuja dalej od slupka)

ROOT = Path(__file__).resolve().parents[2]


def hms(col):
    p = col.str.split(":", expand=True).astype(int)
    return p[0] * 3600 + p[1] * 60 + p[2]


def to_xz(lat, lon):
    """Metry od ORIGIN: x na wschod, z na polnoc (rzut rownoodleglosciowy, ok. na skale miasta)."""
    x = np.radians(lon - ORIGIN_LON) * EARTH_R * np.cos(np.radians(ORIGIN_LAT))
    z = np.radians(lat - ORIGIN_LAT) * EARTH_R
    return x, z


def pick_gtfs(static_dir, first_ts):
    """Najnowszy ZIP pobrany nie pozniej niz pierwszy raport; jak brak, to najstarszy."""
    zips = sorted(glob.glob(str(static_dir / "GTFS_KRK_A_*.zip")))
    if not zips:
        raise SystemExit(f"brak rozkladu w {static_dir}")
    stamps = [re.search(r"_(\d{8}_\d{6})\.zip$", z).group(1) for z in zips]
    stamps = pd.to_datetime(stamps, format="%Y%m%d_%H%M%S").tz_localize("UTC")
    ok = [z for z, s in zip(zips, stamps) if s <= first_ts]
    return Path(ok[-1] if ok else zips[0])


def load_vp(raw, t_from, t_to, routes):
    vp = pd.read_parquet(
        raw / "vehicle_positions",
        columns=[
            "vehicle_id",
            "trip_id",
            "route_id",
            "lat",
            "lon",
            "bearing",
            "veh_ts",
            "current_stop_sequence",
            "current_status",
        ],
    )
    vp = vp.dropna(subset=["vehicle_id", "trip_id", "lat", "lon", "veh_ts"])
    vp = vp.drop_duplicates(["vehicle_id", "veh_ts"])
    if t_from is not None:
        vp = vp[vp["veh_ts"] >= int(t_from.timestamp())]
    if t_to is not None:
        vp = vp[vp["veh_ts"] < int(t_to.timestamp())]
    if routes:
        vp = vp[vp["route_id"].isin(routes)]
    for c in ("vehicle_id", "trip_id", "route_id"):
        vp[c] = vp[c].astype(str)
    return vp.sort_values(["veh_ts", "vehicle_id"]).reset_index(drop=True)


def load_schedule(zpath, trip_ids):
    with zipfile.ZipFile(zpath) as z:
        st = pd.read_csv(
            z.open("stop_times.txt"),
            dtype=str,
            usecols=[
                "trip_id",
                "stop_sequence",
                "stop_id",
                "arrival_time",
                "departure_time",
            ],
            engine="pyarrow",
        )
        stops = pd.read_csv(
            z.open("stops.txt"), dtype=str, usecols=["stop_id", "stop_lat", "stop_lon"]
        )
    st = st[st["trip_id"].isin(trip_ids)].copy()
    st["stop_sequence"] = st["stop_sequence"].astype(int)
    st["arr_s"] = hms(st["arrival_time"])
    st["dep_s"] = hms(st["departure_time"])
    stops[["stop_lat", "stop_lon"]] = stops[["stop_lat", "stop_lon"]].astype(float)
    st = st.merge(stops, on="stop_id", how="left")
    return st[["trip_id", "stop_sequence", "arr_s", "dep_s", "stop_lat", "stop_lon"]]


def scheduled_offset(vp, st):
    """Rozkladowy czas (sekundy od polnocy dnia obslugi) w miejscu i chwili raportu."""
    cur = st.rename(
        columns={
            "arr_s": "arr_cur",
            "dep_s": "dep_cur",
            "stop_lat": "lat_cur",
            "stop_lon": "lon_cur",
        }
    )
    prev = st.assign(stop_sequence=st["stop_sequence"] + 1).rename(
        columns={
            "arr_s": "arr_prev",
            "dep_s": "dep_prev",
            "stop_lat": "lat_prev",
            "stop_lon": "lon_prev",
        }
    )
    key = ["trip_id", "stop_sequence"]
    df = vp.rename(columns={"current_stop_sequence": "stop_sequence"})[key].copy()
    df["stop_sequence"] = (
        df["stop_sequence"].astype("Int64").astype(float).astype("Int64")
    )
    df = df.merge(cur, on=key, how="left").merge(prev, on=key, how="left")

    x, z = to_xz(vp["lat"].to_numpy(), vp["lon"].to_numpy())
    xc, zc = to_xz(df["lat_cur"].to_numpy(), df["lon_cur"].to_numpy())
    xp, zp = to_xz(df["lat_prev"].to_numpy(), df["lon_prev"].to_numpy())
    d_prev = np.hypot(x - xp, z - zp)
    d_cur = np.hypot(x - xc, z - zc)
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = np.clip(d_prev / (d_prev + d_cur), 0, 1)
    between = df["dep_prev"].to_numpy() + frac * (
        df["arr_cur"].to_numpy() - df["dep_prev"].to_numpy()
    )

    stopped = (vp["current_status"] == 1).fillna(False).to_numpy()
    # pierwszy przystanek kursu nie ma poprzedniego: wtedy tylko rozklad przystanku
    sched = np.where(stopped | np.isnan(between), df["arr_cur"].to_numpy(), between)
    # pojazd na petli poczatkowej: na 1. przystanku albo "w drodze" do 2., ale jeszcze przy 1.
    first = df["trip_id"].map(st.groupby("trip_id")["stop_sequence"].min()).to_numpy()
    seq = df["stop_sequence"].to_numpy(dtype=float)
    at_origin = (seq == first) | ((seq == first + 1) & (d_prev < LAYOVER_RADIUS_M))
    return sched, at_origin


def build(vp, st):
    sched, at_origin = scheduled_offset(vp, st)
    local = pd.to_datetime(
        vp["veh_ts"].astype("int64"), unit="s", utc=True
    ).dt.tz_convert(TZ)
    epoch = pd.Timestamp("1970-01-01", tz="UTC")
    d0 = local.dt.normalize()
    d1 = (local - pd.Timedelta(days=1)).dt.normalize()
    mid0 = (d0 - epoch).dt.total_seconds().to_numpy()
    mid1 = (d1 - epoch).dt.total_seconds().to_numpy()
    ts = vp["veh_ts"].astype("int64").to_numpy()
    use0 = np.abs(ts - (mid0 + sched)) <= np.abs(ts - (mid1 + sched))
    mid = np.where(use0, mid0, mid1)
    delay = ts - (mid + sched)
    # przed odjazdem z petli ujemne "opoznienie" to tylko czas do odjazdu, nie opoznienie
    layover = at_origin & (delay < 0)
    delay = np.where(layover, np.nan, delay)
    sim_time = np.where(np.isnan(sched), np.nan, ts - mid)

    x, z = to_xz(vp["lat"].to_numpy(), vp["lon"].to_numpy())
    service_date = np.where(
        use0, d0.dt.strftime("%Y-%m-%d"), d1.dt.strftime("%Y-%m-%d")
    )
    out = pd.DataFrame(
        {
            "t": ts,
            "sim_time_s": pd.array(sim_time, dtype="Int64"),
            "service_date": service_date,
            "vehicle_id": vp["vehicle_id"],
            "trip_id": vp["trip_id"],
            "route_id": vp["route_id"],
            "lat": vp["lat"].round(6),
            "lon": vp["lon"].round(6),
            "x": np.round(x, 1),
            "z": np.round(z, 1),
            "bearing": vp["bearing"],
            "status": vp["current_status"],
            "delay_s": pd.array(np.round(delay), dtype="Int64"),
            "layover": layover,
            "source": "obs",
        }
    )
    out.loc[np.isnan(sched), "service_date"] = None  # brak kursu w rozkladzie
    return out


def parse_local(s):
    return pd.Timestamp(s).tz_localize(TZ) if s else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raw", type=Path, default=ROOT / "data" / "raw_A")
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "processed" / "unity_samples" / "obs",
    )
    ap.add_argument("--from", dest="t_from", help="czas lokalny, np. 2026-10-16T07:00")
    ap.add_argument("--to", dest="t_to", help="czas lokalny (bez tej chwili)")
    ap.add_argument("--routes", help="linie po przecinku, np. 179,169")
    ap.add_argument("--run-id", default=None, help="domyslnie obs_<pierwsza data>")
    a = ap.parse_args()

    routes = [r.strip() for r in a.routes.split(",")] if a.routes else None
    vp = load_vp(a.raw, parse_local(a.t_from), parse_local(a.t_to), routes)
    if vp.empty:
        raise SystemExit("brak raportow pojazdow w zadanym zakresie")
    first_ts = pd.Timestamp(int(vp["veh_ts"].min()), unit="s", tz="UTC")
    zpath = pick_gtfs(a.raw / "static", first_ts)
    st = load_schedule(zpath, set(vp["trip_id"]))
    out = build(vp, st)

    a.out.parent.mkdir(parents=True, exist_ok=True)
    jsonl = a.out.with_suffix(".jsonl")
    out.to_json(jsonl, orient="records", lines=True, force_ascii=False)
    run_id = a.run_id or f"obs_{first_ts.tz_convert(TZ):%Y%m%d_%H%M}"
    meta = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "seed": None,
        "source": "obs",
        "gtfs": zpath.name,
        "origin": {"lat": ORIGIN_LAT, "lon": ORIGIN_LON, "axes": "x=east m, z=north m"},
        "t_min": int(out["t"].min()),
        "t_max": int(out["t"].max()),
        "rows": len(out),
        "vehicles": int(out["vehicle_id"].nunique()),
        "routes": sorted(out["route_id"].unique().tolist()),
    }
    a.out.with_suffix(".meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False)
    )

    d = out["delay_s"].dropna()
    print(
        f"zapisano {jsonl}: {len(out)} wierszy, {meta['vehicles']} pojazdow, rozklad {zpath.name}"
    )
    print(
        f"opoznienie policzone dla {len(d) / len(out):.1%} wierszy,"
        f" postoj na petli przed odjazdem: {out['layover'].mean():.1%}"
    )
    if len(d):
        print(d.describe(percentiles=[0.05, 0.5, 0.95]).round(0).to_string())


if __name__ == "__main__":
    main()
