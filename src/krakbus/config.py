"""Konfiguracja projektu z `configs/config.yaml`."""

from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "config.yaml"


@dataclass(frozen=True)
class DataConfig:
    raw_dir: Path
    processed_dir: Path
    timezone: str


@dataclass(frozen=True)
class EventsConfig:
    episode_gap_s: int
    unc_ok_s: int


@dataclass(frozen=True)
class ChainsConfig:
    l_min_s: int


@dataclass(frozen=True)
class DaysConfig:
    logger_gap_s: int
    service_hours: tuple[int, int]
    max_gap_min: float
    min_events: int
    night_end_hour: int
    special_days_file: Path
    split_file: Path


@dataclass(frozen=True)
class Config:
    data: DataConfig
    events: EventsConfig
    chains: ChainsConfig
    days: DaysConfig


def _path(value: str, root: Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else root / p


def load_config(path: Path = DEFAULT_CONFIG, root: Path = ROOT) -> Config:
    """Wczytuje konfiguracje; sciezki wzgledne sa liczone od katalogu glownego projektu.

    Args:
        path: plik YAML z sekcjami `data`, `events`, `chains`, `days`.
        root: katalog, wzgledem ktorego rozwijane sa sciezki.

    Returns:
        Niezmienny obiekt konfiguracji.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    d, e, dy = raw["data"], raw["events"], raw["days"]
    return Config(
        data=DataConfig(
            raw_dir=_path(d["raw_dir"], root),
            processed_dir=_path(d["processed_dir"], root),
            timezone=d["timezone"],
        ),
        events=EventsConfig(
            episode_gap_s=int(e["episode_gap_s"]), unc_ok_s=int(e["unc_ok_s"])
        ),
        chains=ChainsConfig(l_min_s=int(raw["chains"]["l_min_s"])),
        days=DaysConfig(
            logger_gap_s=int(dy["logger_gap_s"]),
            service_hours=(int(dy["service_hours"][0]), int(dy["service_hours"][1])),
            max_gap_min=float(dy["max_gap_min"]),
            min_events=int(dy["min_events"]),
            night_end_hour=int(dy["night_end_hour"]),
            special_days_file=_path(dy["special_days_file"], root),
            split_file=_path(dy["split_file"], root),
        ),
    )
