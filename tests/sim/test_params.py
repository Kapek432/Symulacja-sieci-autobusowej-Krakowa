from pathlib import Path

import pytest

from krakbus.sim.params import DEFAULT_SIM_CONFIG, OFF_PEAK, load_sim_config


def test_default_config_loads() -> None:
    cfg = load_sim_config()
    assert cfg.scopes["pilot"] == ["179"]
    assert cfg.scopes["city"] is None
    assert cfg.model.u.spatial == "independent"
    assert cfg.model.gamma == 0.0
    assert OFF_PEAK in cfg.model.drift_s_per_min
    assert cfg.boundary in ("observed", "delta")


def test_unknown_spatial_is_rejected(tmp_path: Path) -> None:
    text = DEFAULT_SIM_CONFIG.read_text(encoding="utf-8")
    bad = tmp_path / "sim.yaml"
    bad.write_text(text.replace("spatial: independent", "spatial: neighbors"), encoding="utf-8")
    with pytest.raises(ValueError, match="spatial"):
        load_sim_config(bad)
