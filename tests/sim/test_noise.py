import numpy as np

from krakbus.sim.model import base_increments, loop_departure
from krakbus.sim.noise import ar1, draw_noise
from krakbus.sim.params import EtaParams, UParams

from .conftest import row, zero_model


def test_same_seed_same_noise_other_seed_differs(small_net) -> None:
    m = zero_model(eta=EtaParams(df=3.0, scale_s=10.0))
    a, b, c = (draw_noise(small_net, m, s) for s in (1, 1, 2))
    assert np.array_equal(a.eta, b.eta) and np.array_equal(a.u, b.u)
    assert not np.array_equal(a.eta, c.eta)
    assert a.u.shape[0] == len(small_net.segments)
    assert len(a.delta) == len(small_net.trips)


def test_ar1_has_target_sd_and_lag_correlation() -> None:
    x = ar1(np.random.default_rng(0), 4000, 40, sigma=5.0, rho=0.7)
    assert abs(x.std() / 5.0 - 1) < 0.03
    lag = np.corrcoef(x[:, :-1].ravel(), x[:, 1:].ravel())[0, 1]
    assert abs(lag - 0.7) < 0.02


def test_u_shared_by_lines_on_same_segment_and_window(small_net) -> None:
    m = zero_model(u=UParams(spatial="independent", window_s=900, sigma_s=10.0, rho=0.7))
    inc = base_increments(small_net, draw_noise(small_net, m, 3), m)
    assert inc[row(small_net, "A0", "s2")] == inc[row(small_net, "B0", "s2")] != 0
    assert inc[row(small_net, "A0", "s4")] == 0


def test_drift_scales_with_scheduled_minutes_and_period(small_net) -> None:
    m = zero_model(drift_s_per_min={"szczyt_rano": 10.0, "poza": 6.0})
    inc = base_increments(small_net, draw_noise(small_net, m, 0), m)
    assert inc[row(small_net, "A0", "s1")] == 30.0
    assert inc[row(small_net, "A2", "s1")] == 50.0


def test_loop_rule_absorbs_or_carries() -> None:
    assert loop_departure(100.0, 300.0, 60.0, 0.0) == 0.0
    assert loop_departure(500.0, 300.0, 60.0, 0.0) == 260.0
    assert loop_departure(np.array([100.0, 500.0]), 300.0, 60.0, 20.0).tolist() == [20.0, 260.0]
