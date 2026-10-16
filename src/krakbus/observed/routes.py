"""Komenda `route-ranking`: ranking linii po liczbie dobrych zdarzen (wejscie do batchy toru N)."""

import argparse
import logging

import pandas as pd

from krakbus.config import load_config
from krakbus.logger import setup_logging
from krakbus.observed.days import COMPLETE
from krakbus.observed.manifest import atomic_write_bytes
from krakbus.observed.store import load_chains, load_days, load_events, select_days

RANKING_COLUMNS = [
    "rank",
    "route_id",
    "n_events",
    "events_per_day",
    "cum_share_events",
    "n_days",
    "n_trips",
    "n_vehicles",
    "med_delay_s",
    "p90_delay_s",
    "n_transitions",
    "cross_route_share",
    "carried_share",
]
EVENT_COLUMNS = [
    "service_date",
    "route_id",
    "trip_id",
    "vehicle_id",
    "arr_delay_s",
    "arr_good",
]
CHAIN_COLUMNS = ["route_id", "next_trip_id", "cross_route", "carried"]
logger = logging.getLogger("route_ranking")


def route_ranking(ev: pd.DataFrame, chains: pd.DataFrame) -> pd.DataFrame:
    """Ranking linii po liczbie zdarzen `arr_good`.

    Args:
        ev: zdarzenia z kolumnami `EVENT_COLUMNS`.
        chains: lancuchy kursow z kolumnami `CHAIN_COLUMNS`.

    Returns:
        Tabela `RANKING_COLUMNS` od linii z najwieksza liczba zdarzen. `cum_share_events` to
        udzial zdarzen sieci pokryty przez linie do danej pozycji (cel batchy w M4). Udzialy
        `cross_route` i `carried` licza tylko kursy z zaobserwowanym nastepnym kursem pojazdu.
    """
    good = ev[ev["arr_good"].fillna(False).astype(bool)]
    g = good.groupby("route_id")
    delay = good["arr_delay_s"].astype(float).groupby(good["route_id"])
    t = pd.DataFrame(
        {
            "n_events": g.size(),
            "n_days": g["service_date"].nunique(),
            "n_trips": good.drop_duplicates(["service_date", "trip_id"])
            .groupby("route_id")
            .size(),
            "n_vehicles": g["vehicle_id"].nunique(),
            "med_delay_s": delay.median(),
            "p90_delay_s": delay.quantile(0.9),
        }
    )
    t["events_per_day"] = t["n_events"] / t["n_days"]
    nxt = chains[chains["next_trip_id"].notna()]
    c = nxt.groupby("route_id")
    t = t.join(
        pd.DataFrame(
            {
                "n_transitions": c.size(),
                "cross_route_share": c["cross_route"].mean().astype(float),
                "carried_share": c["carried"].mean().astype(float),
            }
        )
    )
    t["n_transitions"] = t["n_transitions"].fillna(0).astype(int)
    t = t.sort_values(["n_events", "route_id"], ascending=[False, True]).reset_index()
    t["rank"] = range(1, len(t) + 1)
    t["cum_share_events"] = t["n_events"].cumsum() / t["n_events"].sum()
    return t[RANKING_COLUMNS]


def main() -> None:
    """Punkt wejscia `uv run route-ranking`."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--days", nargs="*", help="dni YYYY-MM-DD (domyslnie dni robocze complete)"
    )
    args = parser.parse_args()
    setup_logging()
    cfg = load_config()
    processed = cfg.data.processed_dir
    registry = load_days(processed)
    if args.days:
        days = args.days
    else:
        workdays = registry[pd.to_datetime(registry["service_date"]).dt.dayofweek < 5]
        days = select_days(workdays, statuses=(COMPLETE,))
    if not days:
        raise SystemExit("brak dni; najpierw uruchom build-events")
    ev = load_events(
        days, statuses=None, processed_dir=processed, columns=EVENT_COLUMNS
    )
    chains = load_chains(
        days, statuses=None, processed_dir=processed, columns=CHAIN_COLUMNS
    )
    rank = route_ranking(ev, chains)
    out = processed / "route_ranking.csv"
    atomic_write_bytes(out, rank.to_csv(index=False).encode("utf-8"))
    logger.info(
        "dni: %d (%s .. %s), linii: %d; 50%% / 70%% zdarzen daje %d / %d linii",
        len(days),
        days[0],
        days[-1],
        len(rank),
        int((rank["cum_share_events"] < 0.5).sum()) + 1,
        int((rank["cum_share_events"] < 0.7).sum()) + 1,
    )
    logger.info("top 20\n%s", rank.head(20).round(3).to_string(index=False))
    logger.info("zapisano %s", out)


if __name__ == "__main__":
    main()
