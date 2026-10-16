"""build_events.py: zdarzenia przystankowe z VehiclePositions (status 1) + kontrola jakosci."""

from pathlib import Path

import pandas as pd
from gtfs_versions import assign_service_date, load_schedule

HERE = Path(__file__).resolve()
ROOT = next((p for p in HERE.parents if (p / "data" / "raw_A").is_dir()), HERE.parent)
DATA = ROOT / "data" / "raw_A"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)
TZ = "Europe/Warsaw"
EPISODE_GAP_S = 600  # przerwa dluzsza niz to = nowy epizod postoju
UNC_OK_S = 30  # maks. niepewnosc czasu uznawana za dobra


def hms(col):
    p = col.astype("string").str.strip().str.split(":", expand=True)
    return pd.to_numeric(p[0]) * 3600 + pd.to_numeric(p[1]) * 60 + pd.to_numeric(p[2])


# ---------- dane ----------
vp = pd.read_parquet(DATA / "vehicle_positions")
vp = vp.dropna(subset=["veh_ts", "trip_id", "current_stop_sequence", "current_status"])
vp = vp.astype(
    {"veh_ts": "int64", "current_stop_sequence": "int64", "current_status": "int64"}
)
vp["vehicle_id"] = vp["vehicle_id"].astype(str)
vp["trip_id"] = vp["trip_id"].astype(str)
vp = (
    vp.drop_duplicates(["vehicle_id", "veh_ts"])
    .sort_values(["vehicle_id", "veh_ts"])
    .copy()
)

sched = load_schedule(DATA / "static")
st = sched.stop_times
trips = sched.trips
print("wersje rozkladu (laczone po trip_id):", ", ".join(sched.versions))
st["stop_sequence"] = st["stop_sequence"].astype(int)
st["arr_s"] = hms(st["arrival_time"])
st["dep_s"] = hms(st["departure_time"])
bounds = st.groupby("trip_id")["stop_sequence"].agg(first_seq="min", last_seq="max")

# ---------- niepewnosc czasu: odstep do sasiednich raportow pojazdu ----------
vp["prev_ts"] = vp.groupby("vehicle_id")["veh_ts"].shift(1)
vp["next_ts"] = vp.groupby("vehicle_id")["veh_ts"].shift(-1)

# ---------- epizody postoju ze statusu 1 ----------
s1 = (
    vp[vp["current_status"] == 1]
    .sort_values(["vehicle_id", "trip_id", "current_stop_sequence", "veh_ts"])
    .copy()
)
key = ["vehicle_id", "trip_id", "current_stop_sequence"]
gap = s1.groupby(key)["veh_ts"].diff()
s1["ep"] = (gap.isna() | (gap > EPISODE_GAP_S)).cumsum()
ev = (
    s1.groupby("ep")
    .agg(
        vehicle_id=("vehicle_id", "first"),
        trip_id=("trip_id", "first"),
        stop_sequence=("current_stop_sequence", "first"),
        arr_ts=("veh_ts", "min"),
        dep_ts=("veh_ts", "max"),
        n=("veh_ts", "size"),
        lat=("lat", "first"),
        lon=("lon", "first"),
    )
    .reset_index(drop=True)
)

ev = ev.merge(
    vp[["vehicle_id", "veh_ts", "prev_ts"]].rename(columns={"veh_ts": "arr_ts"}),
    on=["vehicle_id", "arr_ts"],
    how="left",
)
ev = ev.merge(
    vp[["vehicle_id", "veh_ts", "next_ts"]].rename(columns={"veh_ts": "dep_ts"}),
    on=["vehicle_id", "dep_ts"],
    how="left",
)
ev["arr_unc"] = (
    ev["arr_ts"] - ev["prev_ts"]
)  # NaN = pierwszy raport pojazdu (przyjazd niewidziany)
ev["dep_unc"] = ev["next_ts"] - ev["dep_ts"]  # NaN = ostatni raport pojazdu

# ---------- rozklad i opoznienia ----------
ev = ev.merge(
    st[["trip_id", "stop_sequence", "stop_id", "arr_s", "dep_s"]],
    on=["trip_id", "stop_sequence"],
    how="left",
)
ev = ev.merge(
    trips[["trip_id", "route_id", "service_id", "gtfs_stamp"]], on="trip_id", how="left"
)
ev = ev.join(bounds, on="trip_id")
ev["is_first"] = ev["stop_sequence"] == ev["first_seq"]
ev["is_last"] = ev["stop_sequence"] == ev["last_seq"]

ev["service_date"], mid = assign_service_date(
    ev["arr_ts"], ev["arr_s"], ev["service_id"], sched.calendar, TZ
)
ev["arr_delay_s"] = ev["arr_ts"] - (mid + ev["arr_s"])
ev["dep_delay_s"] = ev["dep_ts"] - (
    mid + ev["dep_s"]
)  # dep_ts to dolne ograniczenie odjazdu
ev["arr_ok"] = (ev["arr_unc"] <= UNC_OK_S) & ~ev["is_first"]
ev["dep_ok"] = ev["dep_unc"] <= UNC_OK_S

ev.to_parquet(OUT / "observed_events.parquet", index=False)

# ---------- raport jakosci ----------
print(
    "zdarzen:",
    len(ev),
    " pojazdow:",
    ev["vehicle_id"].nunique(),
    " kursow:",
    ev["trip_id"].nunique(),
)
print(
    "niepewnosc przyjazdu <= 15 s:",
    round((ev["arr_unc"] <= 15).mean(), 3),
    " <= 30 s:",
    round((ev["arr_unc"] <= 30).mean(), 3),
    " brak (NaN):",
    round(ev["arr_unc"].isna().mean(), 3),
)
print("dopasowane do rozkladu:", round(ev["arr_s"].notna().mean(), 3))
print(
    "z data obslugi (usluga aktywna w kalendarzu):",
    round(ev["service_date"].notna().mean(), 3),
)

# kontrola: liczba zdarzen na date obslugi vs lokalna data przyjazdu (rozjazd = zle przypisanie dnia)
_loc_date = (
    pd.to_datetime(ev["arr_ts"], unit="s", utc=True)
    .dt.tz_convert(TZ)
    .dt.strftime("%Y-%m-%d")
)
per_day = (
    pd.DataFrame(
        {
            "wg_daty_obslugi": ev.groupby("service_date").size(),
            "wg_daty_lokalnej": ev.groupby(_loc_date).size(),
            "bez_daty_obslugi": ev[ev["service_date"].isna()].groupby(_loc_date).size(),
            "linii": ev.groupby("service_date")["route_id"].nunique(),
        }
    )
    .fillna(0)
    .astype(int)
)
per_day["wersja_kalendarza"] = (
    sched.calendar.assign(
        d=pd.to_datetime(sched.calendar["date"]).dt.strftime("%Y-%m-%d")
    )
    .groupby("d")["gtfs_stamp"]
    .first()
)
print("\nzdarzenia dzien po dniu:")
print(per_day.to_string())

good = ev[ev["arr_ok"] & ev["arr_delay_s"].notna()]
print(
    "\nopoznienie przyjazdu [s], przystanki posrednie z dobra niepewnoscia: n =",
    len(good),
)
print(good["arr_delay_s"].describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95]).round(1))
print(
    "udzial przyjazdow przed rozkladem (< 0 s):",
    round((good["arr_delay_s"] < 0).mean(), 3),
    " (< -60 s):",
    round((good["arr_delay_s"] < -60).mean(), 3),
)

first = ev[ev["is_first"] & ev["dep_ok"] & ev["dep_delay_s"].notna()]
print("\nodjazdy z pierwszego przystanku, opoznienie [s]: n =", len(first))
print(first["dep_delay_s"].describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95]).round(1))

# pokrycie przystankow miedzy pierwszym a ostatnim zaobserwowanym w kursie
rng = (
    vp.groupby(["vehicle_id", "trip_id"])["current_stop_sequence"]
    .agg(lo="min", hi="max")
    .reset_index()
)
inner = rng.merge(st[["trip_id", "stop_sequence"]], on="trip_id")
inner = inner[
    (inner["stop_sequence"] > inner["lo"]) & (inner["stop_sequence"] < inner["hi"])
]
have = (
    ev[["vehicle_id", "trip_id", "stop_sequence"]].drop_duplicates().assign(seen=True)
)
inner = inner.merge(have, on=["vehicle_id", "trip_id", "stop_sequence"], how="left")
print(
    "\npokrycie przystankow zdarzeniem statusu 1:",
    round(inner["seen"].fillna(False).mean(), 3),
)

same = (vp.groupby("vehicle_id")["lat"].diff() == 0) & (
    vp.groupby("vehicle_id")["lon"].diff() == 0
)
print("udzial kolejnych raportow z identyczna pozycja:", round(same.mean(), 3))

# ---------- niezalezna kontrola: czas przyjazdu vs prognoza z TripUpdates ----------
tu = pd.read_parquet(DATA / "trip_updates")
tu = tu[(tu["arr_time"] > 10**9).fillna(False)][
    ["fetched_at", "trip_id", "stop_id", "arr_time"]
].copy()
tu["trip_id"] = tu["trip_id"].astype(str)
tu["stop_id"] = tu["stop_id"].astype(str)
tu["arr_time"] = tu["arr_time"].astype("int64")
tu = tu.sort_values("fetched_at")

dup = st.duplicated(
    ["trip_id", "stop_id"], keep=False
)  # petle: przystanek dwa razy w kursie
uniq = st.loc[~dup, ["trip_id", "stop_id"]].drop_duplicates()
chk = (
    ev[ev["arr_ok"]][["trip_id", "stop_id", "arr_ts", "arr_delay_s"]]
    .merge(uniq, on=["trip_id", "stop_id"])
    .sort_values("arr_ts")
)
chk["arr_ts"] = chk["arr_ts"].astype("float64")
for df_ in (chk, tu):
    df_["trip_id"] = df_["trip_id"].astype(str)
    df_["stop_id"] = df_["stop_id"].astype(str)
m = pd.merge_asof(
    chk,
    tu,
    left_on="arr_ts",
    right_on="fetched_at",
    by=["trip_id", "stop_id"],
    direction="backward",
    tolerance=900,
).dropna(subset=["fetched_at"])
m["lead_s"] = m["arr_ts"] - m["fetched_at"]
m["err_s"] = m["arr_ts"] - m["arr_time"]  # zaobserwowany minus prognozowany
m["bucket"] = pd.cut(m["lead_s"], [-60, 0, 30, 60, 120, 300, 900])
print(
    "\nprognoza TripUpdates vs zaobserwowany przyjazd (err = obserwacja - prognoza), n =",
    len(m),
)
print(
    m.groupby("bucket", observed=True)["err_s"]
    .agg(
        n="size",
        mediana="median",
        q25=lambda s: s.quantile(0.25),
        q75=lambda s: s.quantile(0.75),
        mae=lambda s: s.abs().mean(),
    )
    .round(1)
)
m["grupa"] = pd.cut(m["arr_delay_s"], [-5000, -60, -20, 0, 60, 5000])
print(
    m.groupby("grupa", observed=True)["err_s"]
    .agg(n="size", mediana="median", mae=lambda s: s.abs().mean())
    .round(1)
)
cols = [
    "vehicle_id",
    "trip_id",
    "route_id",
    "service_date",
    "stop_sequence",
    "arr_s",
    "arr_ts",
    "arr_delay_s",
    "n",
]
print(ev.nsmallest(5, "arr_delay_s")[cols])
print(ev.nlargest(5, "arr_delay_s")[cols])
print(ev[(ev["arr_s"] > 86400)].shape[0], "zdarzen z rozkladowym czasem po 24:00")
