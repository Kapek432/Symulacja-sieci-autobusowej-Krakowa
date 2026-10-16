"""Wykres Mareya linii w dniu: rozklad oraz warstwy obserwacji i symulacji na wspolnej osi.

Os pionowa to odleglosc wzdluz najczestszego wariantu trasy w kierunku (proste miedzy
przystankami, bo feed nie ma `shape_dist_traveled`), pozioma to godziny od poczatku doby GTFS.
Szare linie to rozklad kursow obecnych w warstwach. Jedna warstwa jest kolorowana wg pojazdu,
kilka warstw wg zrodla (z legenda).
"""

import argparse
import logging

import numpy as np
import pandas as pd
from matplotlib import colormaps
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from krakbus.config import load_config
from krakbus.ingest.gtfs_versions import load_schedule
from krakbus.logger import setup_logging
from krakbus.observed.events import index_schedule
from krakbus.observed.store import load_events
from krakbus.sim.network import Network, build_network
from krakbus.viz.layers import last_complete_workday, observed_layer, sim_layer

EARTH_KM = 6371.0
LAYER_COLORS = {"obs": "tab:blue", "sim": "tab:orange"}
OTHER_COLOR = "tab:green"
logger = logging.getLogger("marey")


def pattern_km(st: pd.DataFrame, stops: pd.DataFrame) -> pd.Series:
    """Odleglosc [km] przystankow najczestszego wariantu trasy od jego poczatku.

    Args:
        st: `trip_id`, `stop_sequence` (int), `stop_id` kursow jednego kierunku.
        stops: `stop_id`, `stop_lat`, `stop_lon`.

    Returns:
        Seria km z indeksem `stop_id` w kolejnosci wariantu (przystanek powtorzony: pierwsze
        wystapienie).
    """
    seqs = st.sort_values(["trip_id", "stop_sequence"]).groupby("trip_id")["stop_id"].agg(tuple)
    pattern = list(seqs.value_counts().idxmax())
    xy = (
        stops.drop_duplicates("stop_id")
        .set_index("stop_id")
        .loc[pattern, ["stop_lat", "stop_lon"]]
    )
    lat = np.radians(xy["stop_lat"].to_numpy(float))
    lon = np.radians(xy["stop_lon"].to_numpy(float))
    dlat, dlon = np.diff(lat), np.diff(lon)
    h = np.sin(dlat / 2) ** 2 + np.cos(lat[:-1]) * np.cos(lat[1:]) * np.sin(dlon / 2) ** 2
    km = np.r_[0, np.cumsum(2 * EARTH_KM * np.arcsin(np.sqrt(h)))]
    return pd.Series(km, index=pattern).groupby(level=0, sort=False).first()


def _draw_layers(ax: Axes, layers: dict[str, pd.DataFrame], km: pd.Series, t0: float) -> None:
    by_vehicle = len(layers) == 1
    cmap = colormaps["tab20"]
    for name, ev in layers.items():
        e = ev[ev["stop_id"].isin(km.index)].sort_values("stop_sequence")
        vehicles = sorted(e["vehicle_id"].unique())
        colors = {v: cmap(i % cmap.N) for i, v in enumerate(vehicles)}
        for (veh, _), g in e.groupby(["vehicle_id", "trip_id"]):
            color = colors[veh] if by_vehicle else LAYER_COLORS.get(name, OTHER_COLOR)
            h = (g["arr_ts"] - t0) / 3600
            ax.plot(h, g["stop_id"].map(km), color=color, lw=1.0, marker=".", ms=2)
    if not by_vehicle:
        handles = [Line2D([], [], color=LAYER_COLORS.get(n, OTHER_COLOR), label=n) for n in layers]
        ax.legend(handles=handles, loc="upper left")


def _panel(
    ax: Axes,
    net: Network,
    stops: pd.DataFrame,
    trip_ids: set[str],
    layers: dict[str, pd.DataFrame],
    title: str,
) -> None:
    st = net.stop_times[net.stop_times["trip_id"].isin(trip_ids)]
    km = pattern_km(st, stops)
    for _, g in st[st["stop_id"].isin(km.index)].groupby("trip_id", sort=False):
        ax.plot(g["arr_s"] / 3600, g["stop_id"].map(km), color="0.75", lw=0.6)
    in_panel = {n: ev[ev["trip_id"].isin(trip_ids)] for n, ev in layers.items()}
    _draw_layers(ax, in_panel, km, net.day_start)
    names = stops.drop_duplicates("stop_id").set_index("stop_id")["stop_name"]
    first, last = km.idxmin(), km.idxmax()
    ax.set_yticks([km[first], km[last]], [names.get(first, first), names.get(last, last)])
    ax.set_ylabel("km wzdluz trasy")
    ax.set_title(title)
    ax.grid(alpha=0.3)


def _trip_counts(layers: dict[str, pd.DataFrame], ids: set[str]) -> str:
    return ", ".join(
        f"{n} {ev.loc[ev['trip_id'].isin(ids), 'trip_id'].nunique()}" for n, ev in layers.items()
    )


def marey_figure(
    net: Network, stops: pd.DataFrame, route: str, layers: dict[str, pd.DataFrame]
) -> Figure:
    """Marey linii `route`: panel na kierunek, rozklad kursow z warstw i same warstwy.

    Args:
        net: siec dnia (rozklad, kierunki, poczatek doby).
        stops: przystanki z `stop_lat`, `stop_lon`, `stop_name`.
        route: linia.
        layers: nazwa warstwy (`obs`, `sim`) -> ramka `LAYER_COLUMNS`.

    Returns:
        Figura matplotlib (bez pyplot, do `savefig`).

    Raises:
        ValueError: zadna warstwa nie ma kursow tej linii w sieci dnia.
    """
    in_layers = set().union(*(set(ev["trip_id"]) for ev in layers.values()))
    trips = net.trips[
        (net.trips["route_id"].astype(str) == route) & net.trips.index.isin(in_layers)
    ]
    if trips.empty:
        raise ValueError(f"brak kursow linii {route} w warstwach dnia {net.service_date}")
    dirs = sorted(trips["direction_id"].dropna().unique())
    fig = Figure(figsize=(18, 6 * len(dirs)))
    axes = fig.subplots(len(dirs), 1, squeeze=False)[:, 0]
    for ax, d in zip(axes, dirs):
        ids = set(trips.index[trips["direction_id"] == d])
        title = f"linia {route}, {net.service_date}, kierunek {d}: kursow {_trip_counts(layers, ids)}"
        _panel(ax, net, stops, ids, layers, title)
    axes[-1].set_xlabel("godzina (od poczatku doby GTFS)")
    fig.tight_layout()
    return fig


def main() -> None:
    """Punkt wejscia `uv run marey`."""
    parser = argparse.ArgumentParser(
        description="Wykres Mareya linii: rozklad, obserwacja, symulacja"
    )
    parser.add_argument("route", nargs="?", default="179")
    parser.add_argument(
        "date", nargs="?", help="YYYY-MM-DD; domyslnie dzien przebiegu albo ostatni pelny roboczy"
    )
    parser.add_argument("--sim", help="run_id z data/processed/sim/ (nakladka symulacji)")
    parser.add_argument("--no-obs", action="store_true", help="bez warstwy obserwacji")
    args = parser.parse_args()
    if args.no_obs and not args.sim:
        parser.error("--no-obs bez --sim: nie ma czego rysowac")
    setup_logging()
    cfg = load_config()
    processed = cfg.data.processed_dir
    layers: dict[str, pd.DataFrame] = {}
    sim_ev: pd.DataFrame | None = None
    sim_meta: dict | None = None
    if args.sim:
        sim_ev, sim_meta = sim_layer(processed / "sim" / args.sim, [args.route])
    if args.date and sim_meta and args.date != sim_meta["service_date"]:
        parser.error(f"przebieg {args.sim} jest z dnia {sim_meta['service_date']}, nie {args.date}")
    day = args.date or (sim_meta["service_date"] if sim_meta else last_complete_workday(processed))
    sched = load_schedule(cfg.data.raw_dir / "static")
    net = build_network(index_schedule(sched), day, cfg.data.timezone)
    if not args.no_obs:
        ev = load_events([day], statuses=None, processed_dir=processed)
        layers["obs"] = observed_layer(ev, net, [args.route])
    if sim_ev is not None:
        layers["sim"] = sim_ev
    fig = marey_figure(net, sched.stops, args.route, layers)
    suffix = f"_{args.sim}" if args.sim else ""
    out = processed / "week_report" / "figures" / f"marey_{args.route}_{day}{suffix}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110)
    logger.info("zapisano %s", out)
