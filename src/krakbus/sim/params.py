"""Parametry symulacji z `configs/sim.yaml`."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from krakbus.config import ROOT

DEFAULT_SIM_CONFIG = ROOT / "configs" / "sim.yaml"
OFF_PEAK = "poza"
SPATIAL = ("independent",)
BOUNDARY = ("observed", "delta")


@dataclass(frozen=True)
class UParams:
    spatial: str
    window_s: int
    sigma_s: float
    rho: float


@dataclass(frozen=True)
class EtaParams:
    df: float
    scale_s: float


@dataclass(frozen=True)
class LoopParams:
    l_min_s: float
    delta_mean_s: float
    delta_sd_s: float


@dataclass(frozen=True)
class ModelParams:
    periods: dict[str, tuple[int, int]]
    drift_s_per_min: dict[str, float]
    day_effect_sd_s: float
    u: UParams
    eta: EtaParams
    loop: LoopParams
    gamma: float


@dataclass(frozen=True)
class SimConfig:
    scopes: dict[str, list[str] | None]
    model: ModelParams
    boundary: str
    seed: int


def _model(raw: dict, periods: dict[str, tuple[int, int]]) -> ModelParams:
    u, eta, loop = raw["u"], raw["eta"], raw["loop"]
    return ModelParams(
        periods=periods,
        drift_s_per_min={k: float(v) for k, v in raw["drift_s_per_min"].items()},
        day_effect_sd_s=float(raw["day_effect_sd_s"]),
        u=UParams(
            spatial=str(u["spatial"]),
            window_s=int(u["window_s"]),
            sigma_s=float(u["sigma_s"]),
            rho=float(u["rho"]),
        ),
        eta=EtaParams(df=float(eta["df"]), scale_s=float(eta["scale_s"])),
        loop=LoopParams(
            l_min_s=float(loop["l_min_s"]),
            delta_mean_s=float(loop["delta_mean_s"]),
            delta_sd_s=float(loop["delta_sd_s"]),
        ),
        gamma=float(raw["gamma"]),
    )


def load_sim_config(path: Path = DEFAULT_SIM_CONFIG) -> SimConfig:
    """Wczytuje i sprawdza config symulacji.

    Args:
        path: plik YAML z sekcjami `scopes`, `periods`, `model`, `boundary`, `seed`.

    Returns:
        Niezmienny obiekt configu.

    Raises:
        ValueError: nieznany wariant `u.spatial` albo `boundary`, brak dryfu dla pory dnia.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    periods = {k: (int(v[0]), int(v[1])) for k, v in raw["periods"].items()}
    model = _model(raw["model"], periods)
    if model.u.spatial not in SPATIAL:
        raise ValueError(f"u.spatial = {model.u.spatial}; dostepne: {SPATIAL}")
    if raw["boundary"] not in BOUNDARY:
        raise ValueError(f"boundary = {raw['boundary']}; dostepne: {BOUNDARY}")
    missing = (set(periods) | {OFF_PEAK}) - set(model.drift_s_per_min)
    if missing:
        raise ValueError(f"brak drift_s_per_min dla por: {sorted(missing)}")
    scopes = {
        k: None if v is None else [str(r) for r in v] for k, v in raw["scopes"].items()
    }
    return SimConfig(scopes=scopes, model=model, boundary=raw["boundary"], seed=int(raw["seed"]))
