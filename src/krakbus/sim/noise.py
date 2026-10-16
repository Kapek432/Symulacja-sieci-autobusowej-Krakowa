"""Skladniki losowe przebiegu losowane z gory, wspolne dla obu silnikow."""

from dataclasses import dataclass

import numpy as np

from krakbus.sim.network import Network
from krakbus.sim.params import ModelParams


@dataclass(frozen=True)
class Noise:
    """Wszystkie liczby losowe jednego przebiegu.

    Attributes:
        e_d: efekt dnia [s na odcinek].
        delta: resztkowe spoznienie odjazdu z petli, po jednym na kurs (kolejnosc `net.trips`).
        eta: szum indywidualny, po jednym na wiersz `net.stop_times` (odcinek wychodzacy).
        u: zaklocenie wspolne [odcinek, okno].
    """

    e_d: float
    delta: np.ndarray
    eta: np.ndarray
    u: np.ndarray


def ar1(
    rng: np.random.Generator, n_series: int, n_steps: int, sigma: float, rho: float
) -> np.ndarray:
    """Niezalezne szeregi AR(1) o wariancji stacjonarnej `sigma**2` i korelacji `rho` miedzy krokami."""
    z = rng.standard_normal((n_series, n_steps))
    out = np.empty_like(z)
    out[:, 0] = sigma * z[:, 0]
    innov = sigma * np.sqrt(1.0 - rho**2)
    for k in range(1, n_steps):
        out[:, k] = rho * out[:, k - 1] + innov * z[:, k]
    return out


def draw_noise(net: Network, model: ModelParams, seed: int) -> Noise:
    """Losuje szum dla calej sieci dnia, wiec kurs dostaje ten sam szum niezaleznie od zakresu.

    Kolejnosc losowan (e_d, delta, eta, u) jest stala; zmiana parametru skali nie zmienia
    pozostalych skladnikow.
    """
    rng = np.random.default_rng(seed)
    e_d = float(rng.normal(0.0, model.day_effect_sd_s))
    delta = rng.normal(model.loop.delta_mean_s, model.loop.delta_sd_s, len(net.trips))
    eta = rng.standard_t(model.eta.df, len(net.stop_times)) * model.eta.scale_s
    n_win = int(net.stop_times["dep_s"].max() // model.u.window_s) + 1
    u = ar1(rng, len(net.segments), n_win, model.u.sigma_s, model.u.rho)
    return Noise(e_d=e_d, delta=delta, eta=eta, u=u)
