from dataclasses import replace

import numpy as np
import pytest

from krakbus.config import load_config
from krakbus.ingest.gtfs_versions import load_schedule
from krakbus.observed.events import index_schedule
from krakbus.sim.network import Network, build_network
from krakbus.sim.params import load_sim_config
from krakbus.sim.run import scope_routes, simulate

from .conftest import zero_model

CFG = load_config()
STATIC = CFG.data.raw_dir / "static"
pytestmark = pytest.mark.skipif(not STATIC.exists(), reason="brak data/raw_A/static")


@pytest.fixture(scope="module")
def net() -> Network:
    return build_network(index_schedule(load_schedule(STATIC)), "2026-10-14", CFG.data.timezone)


def test_pilot_zero_noise_is_schedule(net) -> None:
    sim = replace(load_sim_config(), model=zero_model(), boundary="delta")
    ev, meta = simulate(net, sim, scope_routes(sim, "pilot", None), "pilot", 0, "simpy", None)
    assert meta["n_trips"] > 200 and meta["n_boundary"] == 0
    assert np.all(ev["arr_delay_s"] == 0)


def test_corridor_has_boundary_trips_and_city_runs(net) -> None:
    sim = replace(load_sim_config(), boundary="delta")
    _, meta = simulate(net, sim, scope_routes(sim, "corridor", None), "corridor", 0, "simpy", None)
    assert meta["n_boundary"] > 0
    ev, meta = simulate(net, sim, None, "city", 0, "simpy", None)
    assert meta["n_boundary"] == 0 and meta["n_trips"] == len(net.trips)
    assert ev["arr_delay_s"].notna().all()
