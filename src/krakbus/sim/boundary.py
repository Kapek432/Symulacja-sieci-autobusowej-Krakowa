"""Warunek brzegowy: opoznienie startowe kursu, ktorego poprzednik w bloku jest spoza zakresu."""

import numpy as np
import pandas as pd

from krakbus.sim.model import loop_departure
from krakbus.sim.network import Network
from krakbus.sim.noise import Noise
from krakbus.sim.params import ModelParams


def observed_end_delays(chains: pd.DataFrame) -> pd.Series:
    """Opoznienie przyjazdu na koniec kursu z lancuchow dnia (mediana, gdy kilka pojazdow)."""
    c = chains.dropna(subset=["arr_end_delay_s"])
    return c.groupby("trip_id")["arr_end_delay_s"].median().astype(float)


def boundary_starts(
    net: Network,
    sel: np.ndarray,
    noise: Noise,
    model: ModelParams,
    end_delays: pd.Series | None,
) -> dict[int, float]:
    """Opoznienie odjazdu kursow z wyboru, ktorych poprzednik w bloku jest spoza wyboru.

    Args:
        net: siec dnia.
        sel: pozycje kursow w zakresie.
        noise: szum przebiegu (`delta` dla kursow bez obserwacji).
        model: parametry (regula petli).
        end_delays: obserwowane opoznienie na koncu kursu wg `trip_id`; None = zawsze `delta`.

    Returns:
        Pozycja kursu -> Δ0 z reguly petli zastosowanej do obserwacji poprzednika albo `delta`.
    """
    trips = net.trips
    at = pd.Series(np.arange(len(trips)), index=trips.index)
    prev = trips["prev_trip"].map(at).to_numpy(float)
    chosen = np.zeros(len(trips), dtype=bool)
    chosen[sel] = True
    has_prev = ~np.isnan(prev)
    outside = np.zeros(len(trips), dtype=bool)
    outside[has_prev] = ~chosen[prev[has_prev].astype(int)]
    cand = np.flatnonzero(chosen & outside)
    delta = noise.delta[cand]
    if end_delays is None or end_delays.empty:
        return dict(zip(cand.tolist(), delta.tolist()))
    obs = trips["prev_trip"].iloc[cand].map(end_delays).to_numpy(float)
    lay = trips["layover_in_s"].to_numpy(float)[cand]
    start = np.where(np.isnan(obs), delta, loop_departure(obs, lay, model.loop.l_min_s, delta))
    return dict(zip(cand.tolist(), start.tolist()))
