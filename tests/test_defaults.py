from __future__ import annotations

from sc2_replay_salt.defaults import CONFIG_ENV, config_path, load_defaults, save_defaults


def test_defaults_round_trip_with_env_override(tmp_path, monkeypatch) -> None:
    path = tmp_path / "defaults.json"
    monkeypatch.setenv(CONFIG_ENV, str(path))

    assert config_path() == path
    assert load_defaults() == {}

    save_defaults({"player": "GABE"})

    assert load_defaults() == {"player": "GABE"}
