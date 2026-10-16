import numpy as np
import pytest

from krakbus.sim.network import build_network, chain_order, select_trips

from .conftest import TZ, pos, row


def test_trips_ordered_by_block_with_layovers(small_net) -> None:
    t = small_net.trips
    assert list(t.index) == ["A0", "A1", "B0", "B1", "A2"]
    assert t.loc["A1", "prev_trip"] == "A0"
    assert t.loc["A1", "layover_in_s"] == 300
    assert t.loc["A2", "prev_trip"] == "B1"
    assert np.isnan(t.loc["A0", "layover_in_s"])
    assert t["n_rows"].sum() == len(small_net.stop_times)


def test_shared_segment_has_one_id(small_net) -> None:
    st = small_net.stop_times
    a = st.loc[row(small_net, "A0", "s2"), "seg_id"]
    b = st.loc[row(small_net, "B0", "s2"), "seg_id"]
    assert a == b >= 0
    assert st.loc[row(small_net, "A0", "s4"), "seg_id"] == -1
    assert st.loc[row(small_net, "A0", "s1"), "t_s"] == 300


def test_select_and_chain_order_marks_boundary(small_net) -> None:
    sel = select_trips(small_net, ["A"])
    assert sorted(small_net.trips.index[sel]) == ["A0", "A1", "A2"]
    co = chain_order(small_net, sel).set_index("trip")
    assert co.loc[pos(small_net, "A1"), "prev_sel"] == pos(small_net, "A0")
    assert co.loc[pos(small_net, "A2"), "prev_sel"] == -1
    assert co.loc[pos(small_net, "A2"), "pos"] == 0
    assert len(select_trips(small_net, None)) == 5


def test_day_without_services_raises(small_idx) -> None:
    with pytest.raises(ValueError, match="brak aktywnych"):
        build_network(small_idx, "2026-10-15", TZ)
