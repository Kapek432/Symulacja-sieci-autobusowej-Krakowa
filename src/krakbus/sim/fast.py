"""Szybka sciezka doby (numpy) dla gamma = 0: rekursja po pozycji kursu w lancuchu."""

import numpy as np

from krakbus.sim.model import base_increments, loop_departure
from krakbus.sim.network import Network, chain_order
from krakbus.sim.noise import Noise
from krakbus.sim.params import ModelParams


def _offsets(inc: np.ndarray, trip_of_row: np.ndarray, row_start: np.ndarray) -> np.ndarray:
    """Suma przyrostow od poczatku kursu do wiersza, bez przyrostu z samego wiersza."""
    before = np.cumsum(inc) - inc
    return before - before[row_start[trip_of_row]]


def run_fast(
    net: Network,
    sel: np.ndarray,
    noise: Noise,
    model: ModelParams,
    starts: dict[int, float],
) -> np.ndarray:
    """Doba dla kursow z wyboru bez SimPy; wynik jak `run_simpy` przy gamma = 0.

    Przy gamma = 0 kurs zalezy od innych tylko przez poprzednika w lancuchu, wiec opoznienie
    w wierszu to opoznienie odjazdu kursu plus suma przyrostow od jego poczatku. Petla idzie
    po pozycji w lancuchu: na pozycji k wszystkie kursy dostaja odjazd z reguly petli
    zastosowanej do kursow z pozycji k - 1.

    Args:
        net: siec dnia.
        sel: pozycje kursow w zakresie.
        noise: szum przebiegu.
        model: parametry modelu.
        starts: Δ0 kursow z poprzednikiem spoza zakresu (`boundary_starts`).

    Returns:
        Opoznienie przyjazdu (= odjazdu) dla kazdego wiersza `net.stop_times`; NaN poza wyborem.

    Raises:
        ValueError: gamma != 0.
    """
    if model.gamma != 0:
        raise ValueError("szybka sciezka liczy tylko gamma = 0; dla gamma != 0 silnik simpy")
    trips = net.trips
    row_start = trips["row_start"].to_numpy()
    n_rows = trips["n_rows"].to_numpy()
    trip_of_row = np.repeat(np.arange(len(trips)), n_rows)
    off = _offsets(base_increments(net, noise, model), trip_of_row, row_start)
    last_row = row_start + n_rows - 1
    layover = trips["layover_in_s"].to_numpy(float)
    start = noise.delta.astype(float).copy()
    for p, d0 in starts.items():
        start[p] = d0
    order = chain_order(net, sel)
    trip = order["trip"].to_numpy()
    at_pos = order["pos"].to_numpy()
    prev = order["prev_sel"].to_numpy()
    dep = np.full(len(trips), np.nan)
    for k in range(int(at_pos.max()) + 1 if len(at_pos) else 0):
        here = at_pos == k
        p, q = trip[here], prev[here]
        d = start[p]
        inner = q >= 0
        end = dep[q[inner]] + off[last_row[q[inner]]]
        d[inner] = loop_departure(end, layover[p[inner]], model.loop.l_min_s, noise.delta[p[inner]])
        dep[p] = d
    delay = np.full(len(net.stop_times), np.nan)
    simulated = ~np.isnan(dep)[trip_of_row]
    delay[simulated] = dep[trip_of_row[simulated]] + off[simulated]
    return delay
