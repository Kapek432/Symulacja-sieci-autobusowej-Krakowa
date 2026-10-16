import pandas as pd
import pytest

from krakbus.viz.marey import marey_figure, pattern_km


def test_pattern_km_follows_most_common_stop_sequence(small_stops) -> None:
    st = pd.DataFrame(
        {
            "trip_id": ["t1"] * 3 + ["t2"] * 3 + ["t3"] * 2,
            "stop_sequence": [1, 2, 3, 1, 2, 3, 1, 2],
            "stop_id": ["s1", "s2", "s3", "s1", "s2", "s3", "s1", "x1"],
        }
    )
    km = pattern_km(st, small_stops)
    assert list(km.index) == ["s1", "s2", "s3"]
    assert km["s1"] == 0.0
    assert km["s3"] == pytest.approx(2.2239, rel=1e-3)


def test_single_layer_draws_schedule_and_trips_per_direction(
    small_net, small_stops, sim_events
) -> None:
    fig = marey_figure(small_net, small_stops, "A", {"sim": sim_events})
    axes = fig.get_axes()
    assert len(axes) == 2
    assert len(axes[0].lines) == 4
    assert len(axes[1].lines) == 2
    assert axes[0].get_legend() is None


def test_two_layers_get_legend(small_net, small_stops, sim_events) -> None:
    fig = marey_figure(small_net, small_stops, "A", {"obs": sim_events, "sim": sim_events})
    ax = fig.get_axes()[0]
    assert len(ax.lines) == 6
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["obs", "sim"]


def test_route_without_trips_raises(small_net, small_stops, sim_events) -> None:
    with pytest.raises(ValueError, match="brak kursow"):
        marey_figure(small_net, small_stops, "Z", {"sim": sim_events})
