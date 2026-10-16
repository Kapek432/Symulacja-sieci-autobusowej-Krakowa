"""Komenda `events-quality`: raport jakosci zdarzen dla wybranych dni (domyslnie 3 ostatnie complete)."""

import argparse
import logging

import pandas as pd

from krakbus.config import Config, load_config
from krakbus.ingest.gtfs_versions import load_schedule
from krakbus.ingest.raw import (
    TU_COLS,
    VP_COLS,
    PartitionCache,
    list_partitions,
    window_dates,
)
from krakbus.logger import setup_logging
from krakbus.observed.days import COMPLETE
from krakbus.observed.events import clean_positions
from krakbus.observed.store import load_days, load_events, select_days

PCTL = [0.05, 0.25, 0.5, 0.75, 0.95]
logger = logging.getLogger("events_quality")


def _window(
    feed_dir_name: str, columns: list[str], days: list[str], cfg: Config
) -> pd.DataFrame:
    parts = list_partitions(cfg.data.raw_dir / feed_dir_name)
    dates = sorted({d for day in days for d in window_dates(day)})
    return PartitionCache(parts, columns).window(dates)


def log_delays(ev: pd.DataFrame) -> None:
    good = ev[ev["arr_ok"] & ev["arr_delay_s"].notna()]
    logger.info(
        "opoznienie przyjazdu [s], przystanki posrednie z dobra niepewnoscia, n = %d\n%s",
        len(good),
        good["arr_delay_s"].describe(percentiles=PCTL).round(1).to_string(),
    )
    logger.info(
        "przed rozkladem: < 0 s %.3f, < -60 s %.3f",
        (good["arr_delay_s"] < 0).mean(),
        (good["arr_delay_s"] < -60).mean(),
    )
    first = ev[ev["is_first"] & ev["dep_ok"] & ev["dep_delay_s"].notna()]
    logger.info(
        "odjazd z pierwszego przystanku [s], n = %d\n%s",
        len(first),
        first["dep_delay_s"].describe(percentiles=PCTL).round(1).to_string(),
    )


def log_coverage(ev: pd.DataFrame, vp: pd.DataFrame, stop_times: pd.DataFrame) -> None:
    """Udzial przystankow miedzy pierwszym a ostatnim widzianym w kursie, ktore maja zdarzenie."""
    vp = clean_positions(vp)
    vp = vp[vp["trip_id"].isin(set(ev["trip_id"]))]
    rng = (
        vp.groupby(["vehicle_id", "trip_id"])["current_stop_sequence"]
        .agg(lo="min", hi="max")
        .reset_index()
    )
    inner = rng.merge(stop_times[["trip_id", "stop_sequence"]], on="trip_id")
    inner = inner[
        (inner["stop_sequence"] > inner["lo"]) & (inner["stop_sequence"] < inner["hi"])
    ]
    have = (
        ev[["vehicle_id", "trip_id", "stop_sequence"]]
        .drop_duplicates()
        .assign(seen=True)
    )
    inner = inner.merge(have, on=["vehicle_id", "trip_id", "stop_sequence"], how="left")
    same = (vp.groupby("vehicle_id")["lat"].diff() == 0) & (
        vp.groupby("vehicle_id")["lon"].diff() == 0
    )
    logger.info(
        "pokrycie przystankow zdarzeniem statusu 1: %.3f; kolejne raporty z identyczna pozycja: %.3f",
        inner["seen"].fillna(False).mean(),
        same.mean(),
    )


def log_tripupdates_check(
    ev: pd.DataFrame, tu: pd.DataFrame, stop_times: pd.DataFrame
) -> None:
    """Niezalezna kontrola: zaobserwowany przyjazd minus ostatnia prognoza TripUpdates przed nim."""
    tu = tu[(tu["arr_time"] > 10**9).fillna(False)].copy()
    tu["arr_time"] = tu["arr_time"].astype("int64")
    tu = tu.sort_values("fetched_at")
    # petle: przystanek dwa razy w kursie nie da sie jednoznacznie dopasowac po stop_id
    dup = stop_times.duplicated(["trip_id", "stop_id"], keep=False)
    uniq = stop_times.loc[~dup, ["trip_id", "stop_id"]].drop_duplicates()
    chk = (
        ev[ev["arr_ok"]][["trip_id", "stop_id", "arr_ts", "arr_delay_s"]]
        .merge(uniq, on=["trip_id", "stop_id"])
        .sort_values("arr_ts")
    )
    chk["arr_ts"] = chk["arr_ts"].astype("float64")
    for df in (chk, tu):
        df["trip_id"] = df["trip_id"].astype(str)
        df["stop_id"] = df["stop_id"].astype(str)
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
    m["err_s"] = m["arr_ts"] - m["arr_time"]
    m["bucket"] = pd.cut(m["lead_s"], [-60, 0, 30, 60, 120, 300, 900])
    by_lead = (
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
    by_delay = (
        m.groupby("grupa", observed=True)["err_s"]
        .agg(n="size", mediana="median", mae=lambda s: s.abs().mean())
        .round(1)
    )
    logger.info(
        "TripUpdates vs obserwacja (err = obserwacja - prognoza), n = %d\n%s\n%s",
        len(m),
        by_lead.to_string(),
        by_delay.to_string(),
    )


def log_extremes(ev: pd.DataFrame) -> None:
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
    logger.info(
        "najwieksze przyspieszenia\n%s",
        ev.nsmallest(5, "arr_delay_s")[cols].to_string(),
    )
    logger.info(
        "najwieksze opoznienia\n%s", ev.nlargest(5, "arr_delay_s")[cols].to_string()
    )
    logger.info(
        "|opoznienie| > 6 h: %d zdarzen; rozkladowy czas po 24:00: %d",
        int((ev["arr_delay_s"].abs() > 6 * 3600).sum()),
        int((ev["arr_s"] > 86400).sum()),
    )


def report(cfg: Config, days: list[str]) -> None:
    """Loguje raport jakosci zdarzen z podanych dni."""
    ev = load_events(days, statuses=None, processed_dir=cfg.data.processed_dir)
    logger.info(
        "dni: %s; zdarzen %d, pojazdow %d, kursow %d",
        ", ".join(days),
        len(ev),
        ev["vehicle_id"].nunique(),
        ev["trip_id"].nunique(),
    )
    logger.info(
        "niepewnosc przyjazdu <= 15 s %.3f, <= 30 s %.3f, brak %.3f",
        (ev["arr_unc"] <= 15).mean(),
        (ev["arr_unc"] <= 30).mean(),
        ev["arr_unc"].isna().mean(),
    )
    st = load_schedule(
        cfg.data.raw_dir / "static", ["trip_id", "stop_sequence", "stop_id"]
    ).stop_times
    st["stop_sequence"] = st["stop_sequence"].astype(int)
    log_delays(ev)
    log_coverage(ev, _window("vehicle_positions", VP_COLS, days, cfg), st)
    log_tripupdates_check(ev, _window("trip_updates", TU_COLS, days, cfg), st)
    log_extremes(ev)


def main() -> None:
    """Punkt wejscia `uv run events-quality`."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--days", nargs="*", help="dni YYYY-MM-DD (domyslnie 3 ostatnie complete)"
    )
    parser.add_argument(
        "--last",
        type=int,
        default=3,
        help="ile ostatnich dni complete, gdy brak --days",
    )
    args = parser.parse_args()
    setup_logging()
    cfg = load_config()
    registry = load_days(cfg.data.processed_dir)
    days = args.days or select_days(registry, statuses=(COMPLETE,))[-args.last :]
    if not days:
        raise SystemExit("brak dni do raportu; najpierw uruchom build-events")
    logger.info("rejestr dni\n%s", registry.to_string(index=False))
    report(cfg, days)


if __name__ == "__main__":
    main()
