from dataclasses import replace

import pandas as pd
import pytest

from krakbus.observed.events import index_schedule
from krakbus.sim.network import Network, build_network
from krakbus.sim.params import load_sim_config
from krakbus.sim.run import simulate

from ..sim.conftest import DATE, TRIPS, TZ, make_schedule

COORDS = {
    "s1": (50.00, 19.90),
    "s2": (50.01, 19.90),
    "s3": (50.02, 19.90),
    "s4": (50.03, 19.90),
    "x1": (50.01, 19.80),
    "x2": (50.02, 19.95),
}


@pytest.fixture
def small_net() -> Network:
    return build_network(index_schedule(make_schedule(TRIPS)), DATE, TZ)


@pytest.fixture
def small_stops() -> pd.DataFrame:
    return pd.DataFrame(
        [(s, str(lat), str(lon), s.upper()) for s, (lat, lon) in COORDS.items()],
        columns=["stop_id", "stop_lat", "stop_lon", "stop_name"],
    )


@pytest.fixture
def sim_events(small_net: Network) -> pd.DataFrame:
    cfg = replace(load_sim_config(), boundary="delta")
    ev, _ = simulate(small_net, cfg, None, "city", seed=0, engine="simpy", end_delays=None)
    return ev
