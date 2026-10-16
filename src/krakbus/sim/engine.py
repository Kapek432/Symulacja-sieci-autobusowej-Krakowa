"""Silnik SimPy: jeden proces na lancuch kursow (blok) z zakresu."""

from collections.abc import Generator

import numpy as np
import simpy

from krakbus.sim.model import base_increments, loop_departure
from krakbus.sim.network import Network, chain_order
from krakbus.sim.noise import Noise
from krakbus.sim.params import ModelParams


def run_simpy(
    net: Network,
    sel: np.ndarray,
    noise: Noise,
    model: ModelParams,
    starts: dict[int, float],
) -> np.ndarray:
    """Doba w SimPy dla kursow z wyboru.

    Args:
        net: siec dnia.
        sel: pozycje kursow w zakresie.
        noise: szum przebiegu.
        model: parametry; przy `gamma` != 0 przyrost dostaje skladnik od bledu odstepu do
            poprzedniego autobusu tej samej linii i kierunku na przystanku.
        starts: Δ0 kursow z poprzednikiem spoza zakresu (`boundary_starts`).

    Returns:
        Opoznienie przyjazdu (= odjazdu) dla kazdego wiersza `net.stop_times`; NaN poza wyborem.
    """
    inc = base_increments(net, noise, model)
    st, trips = net.stop_times, net.trips
    arr_s = st["arr_s"].to_numpy(float)
    stop = st["stop_id"].to_numpy()
    row_start = trips["row_start"].to_numpy()
    n_rows = trips["n_rows"].to_numpy()
    line = list(zip(trips["route_id"].to_numpy(), trips["direction_id"].to_numpy()))
    layover = trips["layover_in_s"].to_numpy(float)
    l_min, gamma = model.loop.l_min_s, model.gamma
    delay = np.full(len(st), np.nan)
    last: dict[tuple, tuple[float, float]] = {}
    env = simpy.Environment()

    def vehicle(chain: list[tuple[int, int]]) -> Generator[simpy.Event]:
        end_delay = np.nan
        for p, prev_sel in chain:
            if prev_sel >= 0:
                d = float(loop_departure(end_delay, layover[p], l_min, noise.delta[p]))
            else:
                d = starts.get(p, float(noise.delta[p]))
            for j in range(row_start[p], row_start[p] + n_rows[p]):
                t = arr_s[j] + d
                # ujemne opoznienie moze cofnac czas wzgledem poprzedniego przystanku
                yield env.timeout(max(0.0, t - env.now))
                delay[j] = d
                step = inc[j]
                if gamma:
                    key = (*line[p], stop[j])
                    if key in last:
                        t_prev, s_prev = last[key]
                        step += gamma * ((t - t_prev) - (arr_s[j] - s_prev))
                    last[key] = (t, arr_s[j])
                d = d + step
            end_delay = delay[row_start[p] + n_rows[p] - 1]

    order = chain_order(net, sel)
    block = net.trips["block_key"].to_numpy()[order["trip"].to_numpy()]
    for _, g in order.groupby(block, sort=False):
        env.process(vehicle(list(zip(g["trip"].tolist(), g["prev_sel"].tolist()))))
    env.run()
    return delay
