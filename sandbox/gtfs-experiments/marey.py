"""marey.py: wykres Mareya rzeczywistosci (rozklad vs obserwacja) dla jednej linii i jednego dnia.

Uzycie:
  uv run marey.py [linia] [YYYY-MM-DD]      np. uv run marey.py 179 2026-10-14
Domyslnie linia 179 i ostatni dzien roboczy `complete` z data/processed/days.csv.

Os pionowa to odleglosc wzdluz najczestszego wariantu trasy w kierunku (po liniach prostych miedzy
przystankami, bo feed nie ma `shape_dist_traveled`). Szare linie to rozklad kursow, ktore pojechaly,
kolorowe to obserwacja (przyjazdy `arr_ts`, zdarzenia z `delay_class` = ok), kolor wg pojazdu.
Wynik: data/processed/week_report/figures/marey_<linia>_<dzien>.png
"""

import logging
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from krakbus.config import load_config
from krakbus.ingest.gtfs_versions import gtfs_day_start, load_schedule
from krakbus.logger import setup_logging
from krakbus.observed.days import COMPLETE
from krakbus.observed.events import hms
from krakbus.observed.store import load_days, load_events, select_days

EARTH_KM = 6371.0
logger = logging.getLogger("marey")


def _default_day(processed) -> str:
    reg = load_days(processed)
    work = reg[pd.to_datetime(reg["service_date"]).dt.dayofweek < 5]
    days = select_days(work, statuses=(COMPLETE,))
    if not days:
        sys.exit("brak dni roboczych complete; najpierw uv run build-events")
    return days[-1]


def _pattern_km(st: pd.DataFrame, stops: pd.DataFrame) -> pd.Series:
    """Odleglosc [km] przystankow najczestszego wariantu trasy od jego poczatku."""
    seqs = (
        st.sort_values(["trip_id", "stop_sequence"])
        .groupby("trip_id")["stop_id"]
        .agg(tuple)
    )
    pattern = list(seqs.value_counts().idxmax())
    xy = (
        stops.drop_duplicates("stop_id")
        .set_index("stop_id")
        .loc[pattern, ["stop_lat", "stop_lon"]]
    )
    lat = np.radians(xy["stop_lat"].to_numpy(float))
    lon = np.radians(xy["stop_lon"].to_numpy(float))
    dlat, dlon = np.diff(lat), np.diff(lon)
    h = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat[:-1]) * np.cos(lat[1:]) * np.sin(dlon / 2) ** 2
    )
    km = np.r_[0, np.cumsum(2 * EARTH_KM * np.arcsin(np.sqrt(h)))]
    return pd.Series(km, index=pattern).groupby(level=0).first()


def _panel(
    ax, ev: pd.DataFrame, st: pd.DataFrame, stops: pd.DataFrame, t0: float, title: str
) -> None:
    km = _pattern_km(st, stops)
    sch = st[st["stop_id"].isin(km.index)].copy()
    sch["y"] = sch["stop_id"].map(km)
    sch["h"] = hms(sch["arrival_time"]) / 3600
    for _, g in sch.sort_values("stop_sequence").groupby("trip_id"):
        ax.plot(g["h"], g["y"], color="0.75", lw=0.6)
    obs = ev[ev["stop_id"].isin(km.index)].copy()
    obs["y"] = obs["stop_id"].map(km)
    obs["h"] = (obs["arr_ts"].astype(float) - t0) / 3600
    vehicles = sorted(obs["vehicle_id"].unique())
    colors = plt.cm.tab20(np.linspace(0, 1, max(len(vehicles), 1)))
    cmap = dict(zip(vehicles, colors))
    for (veh, _), g in obs.sort_values("stop_sequence").groupby(
        ["vehicle_id", "trip_id"]
    ):
        ax.plot(g["h"], g["y"], color=cmap[veh], lw=1.0, marker=".", ms=2)
    first, last = km.idxmin(), km.idxmax()
    names = stops.drop_duplicates("stop_id").set_index("stop_id")["stop_name"]
    ax.set_yticks(
        [km[first], km[last]], [names.get(first, first), names.get(last, last)]
    )
    ax.set_ylabel("km wzdluz trasy")
    ax.set_title(
        f"{title}: {obs['trip_id'].nunique()} kursow, {len(vehicles)} pojazdow"
    )
    ax.grid(alpha=0.3)


def main() -> None:
    setup_logging()
    cfg = load_config()
    route = sys.argv[1] if len(sys.argv) > 1 else "179"
    day = sys.argv[2] if len(sys.argv) > 2 else _default_day(cfg.data.processed_dir)
    sched = load_schedule(cfg.data.raw_dir / "static")
    sched.stop_times["stop_sequence"] = sched.stop_times["stop_sequence"].astype(int)
    ev = load_events([day], statuses=None, processed_dir=cfg.data.processed_dir)
    ev = ev[
        (ev["route_id"].astype(str) == route) & (ev["delay_class"].fillna("") == "ok")
    ]
    if ev.empty:
        sys.exit(f"brak zdarzen linii {route} w dniu {day}")
    trips = sched.trips.drop_duplicates("trip_id").set_index("trip_id")
    ev = ev.assign(direction_id=ev["trip_id"].map(trips["direction_id"]))
    t0 = float(
        gtfs_day_start(pd.Series([day.replace("-", "")]), cfg.data.timezone).iloc[0]
    )
    dirs = sorted(ev["direction_id"].dropna().unique())
    fig, axes = plt.subplots(len(dirs), 1, figsize=(18, 6 * len(dirs)), squeeze=False)
    for ax, d in zip(axes[:, 0], dirs):
        e = ev[ev["direction_id"] == d]
        st = sched.stop_times[sched.stop_times["trip_id"].isin(set(e["trip_id"]))]
        _panel(ax, e, st, sched.stops, t0, f"linia {route}, {day}, kierunek {d}")
    axes[-1, 0].set_xlabel("godzina (od poczatku doby GTFS)")
    fig.tight_layout()
    out = (
        cfg.data.processed_dir / "week_report" / "figures" / f"marey_{route}_{day}.png"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110)
    logger.info("zapisano %s", out)


if __name__ == "__main__":
    main()
