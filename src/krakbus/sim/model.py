"""Rownania modelu wspolne dla obu silnikow: przyrost opoznienia na odcinku i regula petli."""

import numpy as np

from krakbus.sim.network import Network
from krakbus.sim.noise import Noise
from krakbus.sim.params import OFF_PEAK, ModelParams


def base_increments(net: Network, noise: Noise, model: ModelParams) -> np.ndarray:
    """Przyrost opoznienia na odcinku wychodzacym z kazdego wiersza `stop_times`, bez skladnika gamma.

    a_p * t_s / 60 + e_d + u[odcinek, okno] + eta; okno i pora dnia wg rozkladowego odjazdu
    z przystanku. Na ostatnim przystanku kursu 0.
    """
    st = net.stop_times
    dep = st["dep_s"].to_numpy(float)
    hour = (dep // 3600) % 24
    drift = np.full(len(st), model.drift_s_per_min[OFF_PEAK])
    for name, (h0, h1) in model.periods.items():
        drift[(hour >= h0) & (hour < h1)] = model.drift_s_per_min[name]
    seg = st["seg_id"].to_numpy()
    has = seg >= 0
    u = np.zeros(len(st))
    u[has] = noise.u[seg[has], (dep[has] // model.u.window_s).astype(int)]
    inc = drift * st["t_s"].to_numpy(float) / 60 + noise.e_d + u + noise.eta
    inc[~has] = 0.0
    return inc


def loop_departure(
    end_delay: np.ndarray | float,
    layover_s: np.ndarray | float,
    l_min_s: float,
    delta: np.ndarray | float,
) -> np.ndarray | float:
    """Opoznienie odjazdu nastepnego kursu: max(opoznienie na koncu + l_min - zapas, delta)."""
    return np.maximum(end_delay + l_min_s - layover_s, delta)
