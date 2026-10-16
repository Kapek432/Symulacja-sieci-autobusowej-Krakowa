from dataclasses import replace

import numpy as np
import pytest

from krakbus.sim.params import load_sim_config
from krakbus.sim.run import SIM_COLUMNS, scope_routes, simulate

from .conftest import zero_model


def test_scope_routes_from_config_or_explicit() -> None:
    cfg = load_sim_config()
    assert scope_routes(cfg, "pilot", None) == ["179"]
    assert scope_routes(cfg, "city", None) is None
    assert scope_routes(cfg, "pilot", ["704"]) == ["704"]
    with pytest.raises(ValueError, match="zakres"):
        scope_routes(cfg, "nieznany", None)


def test_simulate_writes_observed_like_schema(small_net) -> None:
    cfg = replace(load_sim_config(), model=zero_model(), boundary="delta")
    ev, meta = simulate(small_net, cfg, ["A"], "A", seed=1, engine="simpy", end_delays=None)
    assert list(ev.columns) == SIM_COLUMNS
    assert set(ev["trip_id"]) == {"A0", "A1", "A2"}
    assert np.allclose(ev["arr_ts"], small_net.day_start + ev["arr_s"])
    assert (ev["source"] == "sim").all()
    assert meta["n_trips"] == 3 and meta["n_boundary"] == 1
    assert meta["n_events"] == len(ev)
    assert meta["run_id"] == "2026-10-14_A_simpy_s1"


def test_fast_engine_gives_same_events_as_simpy(small_net) -> None:
    cfg = replace(load_sim_config(), boundary="delta")
    a, ma = simulate(small_net, cfg, None, "city", seed=4, engine="simpy", end_delays=None)
    b, mb = simulate(small_net, cfg, None, "city", seed=4, engine="fast", end_delays=None)
    np.testing.assert_allclose(b["arr_delay_s"], a["arr_delay_s"], atol=1e-6)
    assert mb["run_id"] == "2026-10-14_city_fast_s4"
    assert mb["engine_s"] >= 0 and ma["engine_s"] >= 0


def test_simulate_rejects_empty_scope(small_net) -> None:
    with pytest.raises(ValueError, match="brak kursow"):
        simulate(small_net, load_sim_config(), ["999"], "999", 0, "simpy", None)
