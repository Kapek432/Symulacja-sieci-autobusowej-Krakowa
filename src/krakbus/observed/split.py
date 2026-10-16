"""Komenda `propose-split`: robocza propozycja podzialu dni na kalibracje i walidacje.

Warstwy to typ dnia (roboczy, sobota, niedziela) razy pokolenie rozkladu, ktore obsluzylo dzien
(dominujacy prefiks `service_id`). W kazdej warstwie dni walidacyjne sa rozlozone rownomiernie
w czasie, zeby obie czesci mialy rozne dni tygodnia, a kazda warstwa z co najmniej dwoma dniami
miala dzien walidacyjny.
Wynik ma format `configs/days_split.yaml`; zamrozenie (skopiowanie do configs) nastepuje w M3.
"""

import argparse
import logging

import pandas as pd
import yaml

from krakbus.config import load_config
from krakbus.logger import setup_logging
from krakbus.observed.days import COMPLETE
from krakbus.observed.manifest import atomic_write_bytes
from krakbus.observed.store import load_days, load_events, select_days

CALIB = "calib"
VALID = "valid"
logger = logging.getLogger("propose_split")


def day_type(service_date: str) -> str:
    dow = pd.Timestamp(service_date).dayofweek
    return "roboczy" if dow < 5 else ("sobota" if dow == 5 else "niedziela")


def day_generations(ev: pd.DataFrame) -> pd.Series:
    """Dominujace pokolenie rozkladu (prefiks daty `service_id`) w kazdym dniu obslugi."""
    gen = ev["service_id"].astype("string").str.split("_").str[0]
    return gen.groupby(ev["service_date"].astype("string")).agg(
        lambda s: s.value_counts().idxmax()
    )


def _valid_positions(n: int, valid_fraction: float) -> set[int]:
    n_valid = int(n * valid_fraction + 0.5)
    return {int((k + 0.5) * n / n_valid) for k in range(n_valid)}


def propose_split(generations: pd.Series, valid_fraction: float) -> pd.DataFrame:
    """Rola (`calib` / `valid`) kazdego dnia w warstwach typ dnia x pokolenie.

    Args:
        generations: pokolenie rozkladu indeksowane data YYYY-MM-DD (tylko dni do podzialu).
        valid_fraction: docelowy udzial dni walidacyjnych w warstwie; warstwa z jednym dniem
            przy udziale < 0.5 trafia w calosci do kalibracji.

    Returns:
        Ramka z kolumnami `service_date`, `day_type`, `generation`, `role`, posortowana po dacie.
    """
    t = pd.DataFrame(
        {
            "service_date": generations.index.astype(str),
            "generation": generations.values,
        }
    )
    t["day_type"] = t["service_date"].map(day_type)
    t = t.sort_values("service_date").reset_index(drop=True)
    t["role"] = CALIB
    for _, g in t.groupby(["day_type", "generation"]):
        pos = _valid_positions(len(g), valid_fraction)
        t.loc[[g.index[i] for i in sorted(pos)], "role"] = VALID
    return t[["service_date", "day_type", "generation", "role"]]


def split_yaml(split: pd.DataFrame, excluded: list[str]) -> str:
    """Tekst w formacie `days_split.yaml` (klucze `calib`, `valid`, `excluded`)."""
    body = {
        CALIB: split.loc[split["role"] == CALIB, "service_date"].tolist(),
        VALID: split.loc[split["role"] == VALID, "service_date"].tolist(),
        "excluded": sorted(excluded),
    }
    header = (
        "# Propozycja z `uv run propose-split` (nie zamrozona). Zamrozenie w M3: skopiowac do\n"
        "# configs/days_split.yaml; dni complete spoza listy calib dostana wtedy role valid.\n"
    )
    return header + yaml.safe_dump(body, sort_keys=False, allow_unicode=True)


def main() -> None:
    """Punkt wejscia `uv run propose-split`."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args()
    setup_logging()
    cfg = load_config()
    processed = cfg.data.processed_dir
    registry = load_days(processed)
    days = select_days(registry, statuses=(COMPLETE,))
    if not days:
        raise SystemExit("brak dni complete; najpierw uruchom build-events")
    ev = load_events(
        days,
        statuses=None,
        processed_dir=processed,
        columns=["service_date", "service_id"],
    )
    split = propose_split(day_generations(ev), cfg.days.valid_fraction)
    out = processed / "days_split_proposal.yaml"
    # Dni bez statusu complete sa wykluczane przez status; wpisanie ich do `excluded` zamroziloby
    # tez dzien provisional, ktory po kolejnym wgraniu stanie sie complete.
    atomic_write_bytes(out, split_yaml(split, []).encode("utf-8"))
    logger.info("propozycja podzialu\n%s", split.to_string(index=False))
    logger.info(
        "calib %d, valid %d, dni bez statusu complete %d; zapisano %s",
        int((split["role"] == CALIB).sum()),
        int((split["role"] == VALID).sum()),
        len(registry) - len(split),
        out,
    )


if __name__ == "__main__":
    main()
