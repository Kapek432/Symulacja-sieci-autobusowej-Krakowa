import numpy as np
import pandas as pd

from krakbus.sim.boundary import boundary_starts, observed_end_delays
from krakbus.sim.network import select_trips
from krakbus.sim.noise import draw_noise

from .conftest import pos, zero_model


def test_observed_end_delay_goes_through_loop_rule(small_net) -> None:
    m = zero_model()
    sel = select_trips(small_net, ["A"])
    noise = draw_noise(small_net, m, 0)
    starts = boundary_starts(small_net, sel, noise, m, pd.Series({"B1": 400.0}))
    assert starts == {pos(small_net, "A2"): 160.0}


def test_missing_observation_falls_back_to_delta(small_net) -> None:
    m = zero_model()
    sel = select_trips(small_net, ["A"])
    noise = draw_noise(small_net, m, 0)
    noise.delta[:] = 7.0
    assert boundary_starts(small_net, sel, noise, m, pd.Series(dtype=float)) == {
        pos(small_net, "A2"): 7.0
    }
    assert boundary_starts(small_net, sel, noise, m, None) == {pos(small_net, "A2"): 7.0}


def test_city_scope_has_no_boundary(small_net) -> None:
    m = zero_model()
    sel = select_trips(small_net, None)
    assert boundary_starts(small_net, sel, draw_noise(small_net, m, 0), m, None) == {}


def test_observed_end_delays_median_per_trip() -> None:
    ch = pd.DataFrame(
        {"trip_id": ["t", "t", "u"], "arr_end_delay_s": pd.array([10, 30, None], dtype="Float64")}
    )
    out = observed_end_delays(ch)
    assert out.to_dict() == {"t": 20.0}
    assert np.issubdtype(out.dtype, np.floating)
