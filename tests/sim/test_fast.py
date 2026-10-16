import numpy as np
import pandas as pd
import pytest

from krakbus.observed.events import index_schedule
from krakbus.sim.boundary import boundary_starts
from krakbus.sim.engine import run_simpy
from krakbus.sim.fast import run_fast
from krakbus.sim.network import Network, build_network, select_trips
from krakbus.sim.noise import draw_noise
from krakbus.sim.params import EtaParams, LoopParams, ModelParams, UParams

from .conftest import DATE, TZ, make_schedule, row, zero_model

NOISY = zero_model(
    drift_s_per_min={"szczyt_rano": 4.0, "poza": 3.0},
    day_effect_sd_s=5.0,
    u=UParams(spatial="independent", window_s=900, sigma_s=10.0, rho=0.7),
    eta=EtaParams(df=3.0, scale_s=40.0),
    loop=LoopParams(l_min_s=60.0, delta_mean_s=20.0, delta_sd_s=20.0),
)


def _hhmm(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _loop_network() -> Network:
    """40 blokow po 6 kursow, zapas 2 min, co trzeci kurs na linii B (przejscia miedzy liniami).

    Zapas minus l_min to 60 s, wiec przy szumie z `NOISY` czesc kursow przenosi opoznienie
    na nastepny, a czesc startuje z delta.
    """
    stops = [f"p{k}" for k in range(5)]
    trips = []
    for b in range(40):
        for k in range(6):
            seq = stops if k % 2 == 0 else stops[::-1]
            t0 = 300 + 2 * b + 14 * k
            times = [(s, _hhmm(t0 + 3 * j)) for j, s in enumerate(seq)]
            route = "B" if k % 3 == 2 else "A"
            trips.append((f"b{b}k{k}", route, str(k % 2), f"blk{b}", times))
    return build_network(index_schedule(make_schedule(trips)), DATE, TZ)


def _both(
    net: Network,
    model: ModelParams,
    seed: int,
    routes: list[str] | None,
    obs: pd.Series | None,
) -> tuple[np.ndarray, np.ndarray]:
    sel = select_trips(net, routes)
    noise = draw_noise(net, model, seed)
    starts = boundary_starts(net, sel, noise, model, obs)
    return run_simpy(net, sel, noise, model, starts), run_fast(net, sel, noise, model, starts)


@pytest.mark.parametrize("routes", [["A"], ["B"], None])
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_fast_equals_simpy_on_small_net(small_net, routes, seed) -> None:
    obs = pd.Series({"B1": 400.0, "A0": 30.0})
    a, b = _both(small_net, NOISY, seed, routes, obs)
    np.testing.assert_allclose(b, a, atol=1e-6, equal_nan=True)


@pytest.mark.parametrize("routes", [["A"], None])
def test_fast_equals_simpy_with_loops_and_cross_route(routes) -> None:
    net = _loop_network()
    obs = pd.Series(250.0, index=net.trips.index)
    a, b = _both(net, NOISY, 7, routes, obs)
    np.testing.assert_allclose(b, a, atol=1e-6, equal_nan=True)
    assert np.isnan(a).any() == (routes is not None)


def test_fast_carries_and_absorbs_like_loop_rule(small_net) -> None:
    m = zero_model()
    sel = select_trips(small_net, None)
    for shock, expected in ((100.0, 0.0), (500.0, 260.0)):
        noise = draw_noise(small_net, m, 0)
        noise.eta[row(small_net, "A0", "s3")] = shock
        d = run_fast(small_net, sel, noise, m, {})
        assert d[row(small_net, "A0", "s4")] == shock
        assert d[row(small_net, "A1", "s1")] == expected


def test_fast_refuses_gamma(small_net) -> None:
    m = zero_model(gamma=0.5)
    sel = select_trips(small_net, None)
    with pytest.raises(ValueError, match="gamma"):
        run_fast(small_net, sel, draw_noise(small_net, m, 0), m, {})
