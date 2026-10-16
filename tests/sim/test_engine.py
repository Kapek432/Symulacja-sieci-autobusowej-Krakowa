import numpy as np

from krakbus.observed.events import index_schedule
from krakbus.sim.engine import run_simpy
from krakbus.sim.network import Network, build_network, select_trips
from krakbus.sim.noise import Noise, draw_noise
from krakbus.sim.params import EtaParams, ModelParams

from .conftest import DATE, TZ, make_schedule, pos, row, zero_model


def _run(
    net: Network,
    model: ModelParams,
    noise: Noise | None = None,
    routes: list[str] | None = None,
    starts: dict[int, float] | None = None,
) -> np.ndarray:
    noise = noise or draw_noise(net, model, 0)
    return run_simpy(net, select_trips(net, routes), noise, model, starts or {})


def test_zero_noise_reproduces_schedule(small_net) -> None:
    d = _run(small_net, zero_model())
    assert np.all(d == 0.0)


def test_loop_absorbs_small_and_carries_large_delay(small_net) -> None:
    m = zero_model()
    for shock, expected in ((100.0, 0.0), (500.0, 260.0)):
        noise = draw_noise(small_net, m, 0)
        noise.eta[row(small_net, "A0", "s3")] = shock
        d = _run(small_net, m, noise)
        assert d[row(small_net, "A0", "s4")] == shock
        assert d[row(small_net, "A1", "s4")] == expected
        assert d[row(small_net, "A1", "s1")] == expected


def test_drift_only_accumulates_along_trip(small_net) -> None:
    m = zero_model(drift_s_per_min={"szczyt_rano": 0.0, "poza": 6.0})
    d = _run(small_net, m)
    rows = [row(small_net, "A0", s) for s in ("s1", "s2", "s3", "s4")]
    assert d[rows].tolist() == [0.0, 30.0, 60.0, 90.0]


def test_without_u_and_gamma_other_chains_are_independent(small_net) -> None:
    m = zero_model(eta=EtaParams(df=3.0, scale_s=20.0))
    noise = draw_noise(small_net, m, 5)
    base = _run(small_net, m, noise)
    noise.eta[row(small_net, "B0", "x1")] += 1000.0
    moved = _run(small_net, m, noise)
    a_rows = small_net.stop_times["trip_id"].isin(["A0", "A1"]).to_numpy()
    assert np.array_equal(base[a_rows], moved[a_rows])
    assert not np.array_equal(base, moved)


def test_eta_spread_grows_along_route() -> None:
    stops = [(f"s{k}", f"06:{2 * k:02d}") for k in range(1, 9)]
    trips = [(f"t{i}", "A", "0", f"b{i}", stops) for i in range(400)]
    net = build_network(index_schedule(make_schedule(trips)), DATE, TZ)
    m = zero_model(eta=EtaParams(df=5.0, scale_s=10.0))
    d = _run(net, m).reshape(400, 8)
    sd = d.std(axis=0)
    assert sd[0] == 0.0
    assert np.all(np.diff(sd[1:]) > -1.0)
    assert sd[-1] > 2 * sd[1]


def test_gamma_feeds_headway_error_to_next_bus(small_net) -> None:
    m = zero_model(gamma=0.5)
    noise = draw_noise(small_net, m, 0)
    noise.eta[row(small_net, "A0", "s1")] = 100.0
    d = _run(small_net, m, noise)
    assert d[row(small_net, "A2", "s3")] == -50.0
    assert d[row(small_net, "A0", "s4")] == 100.0


def test_boundary_start_is_used(small_net) -> None:
    m = zero_model()
    d = _run(small_net, m, routes=["A"], starts={pos(small_net, "A2"): 160.0})
    assert d[row(small_net, "A2", "s1")] == 160.0
    assert np.isnan(d[row(small_net, "B0", "x1")])
