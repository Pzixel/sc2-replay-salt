from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sc2_replay_salt import cli
from sc2_replay_salt.build_order import BuildOrderItem, PlayerRef


@dataclass
class FakeReplay:
    filename: str


@dataclass
class FakePlayer:
    pid: int
    name: str
    play_race: str


def test_max_seconds_defaults_to_nine_minutes() -> None:
    assert cli._max_seconds(None, False) == 540
    assert cli._max_seconds(7, False) == 420
    assert cli._max_seconds(None, True) is None


def test_format_combined_output_includes_table_and_salt() -> None:
    output = cli.format_combined_output(
        "game.SC2Replay",
        PlayerRef(pid=2, name="GABE", race="Terran"),
        [BuildOrderItem(frame=16, seconds=1, name="Supply Depot", supply_used=14)],
        "game",
    )

    assert "Player: 2: GABE, Terran" in output
    assert " 14\t0:01\tSupply Depot" in output
    assert "\n\nSALT:\n$game~*   /" in output


def test_easy_mode_writes_combined_output_and_remembers_player(tmp_path, monkeypatch) -> None:
    replay_path = tmp_path / "practice.SC2Replay"
    replay_path.write_bytes(b"")
    saved_defaults: dict[str, object] = {}
    captured: dict[str, object] = {}

    def fake_build_order_for_replay(path: Path, player_selector: str | None, options: object) -> tuple[FakeReplay, PlayerRef, list[BuildOrderItem]]:
        captured["path"] = path
        captured["player_selector"] = player_selector
        captured["max_seconds"] = getattr(options, "max_seconds", None)
        return (
            FakeReplay(filename=str(path)),
            PlayerRef(pid=2, name="GABE", race="Terran"),
            [BuildOrderItem(frame=16, seconds=1, name="Supply Depot", supply_used=14)],
        )

    monkeypatch.setattr(cli, "load_defaults", lambda: saved_defaults)
    monkeypatch.setattr(cli, "save_defaults", lambda defaults: captured.update(saved=dict(defaults)))
    monkeypatch.setattr(cli, "_player_selector", lambda path, no_prompt, defaults, all_on_no_prompt=False: None)
    monkeypatch.setattr(cli, "build_order_for_replay", fake_build_order_for_replay)

    assert cli.main(["--easy", "--no-prompt", str(replay_path)]) == 0

    output_path = tmp_path / "practice build order.txt"
    output = output_path.read_text(encoding="utf-8")
    assert captured["path"] == replay_path
    assert captured["player_selector"] is None
    assert captured["max_seconds"] == 540
    assert captured["saved"] == {"player": "GABE"}
    assert "Player: 2: GABE, Terran" in output
    assert "\n\nSALT:\n$practice~*   /" in output


def test_remember_player_is_best_effort(monkeypatch) -> None:
    monkeypatch.setattr(cli, "save_defaults", lambda defaults: (_ for _ in ()).throw(OSError("nope")))
    defaults: dict[str, object] = {}

    cli._remember_player(defaults, "GABE")

    assert defaults == {"player": "GABE"}


def test_easy_mode_writes_all_players_when_prompt_has_no_input(tmp_path, monkeypatch) -> None:
    replay_path = tmp_path / "practice.SC2Replay"
    replay_path.write_bytes(b"")
    fake_players = [FakePlayer(1, "Alpha", "Zerg"), FakePlayer(2, "GABE", "Terran")]

    def fake_build_order_for_replay(path: Path, player_selector: str | None, options: object) -> tuple[FakeReplay, PlayerRef, list[BuildOrderItem]]:
        player = fake_players[int(player_selector or "1") - 1]
        return (
            FakeReplay(filename=str(path)),
            PlayerRef(pid=player.pid, name=player.name, race=player.play_race),
            [BuildOrderItem(frame=16, seconds=1, name="Supply Depot", supply_used=14)],
        )

    monkeypatch.setattr(cli, "load_defaults", lambda: {})
    monkeypatch.setattr(cli, "load_replay", lambda path: FakeReplay(filename=str(path)))
    monkeypatch.setattr(cli, "replay_players", lambda replay: fake_players)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: (_ for _ in ()).throw(EOFError()))
    monkeypatch.setattr(cli, "build_order_for_replay", fake_build_order_for_replay)

    assert cli.main(["--easy", str(replay_path)]) == 0

    assert (tmp_path / "practice - Alpha build order.txt").exists()
    assert (tmp_path / "practice - GABE build order.txt").exists()


def test_easy_no_prompt_writes_all_players_when_no_player_is_remembered(tmp_path, monkeypatch) -> None:
    replay_path = tmp_path / "practice.SC2Replay"
    replay_path.write_bytes(b"")
    fake_players = [FakePlayer(1, "Alpha", "Zerg"), FakePlayer(2, "GABE", "Terran")]

    def fake_build_order_for_replay(path: Path, player_selector: str | None, options: object) -> tuple[FakeReplay, PlayerRef, list[BuildOrderItem]]:
        player = fake_players[int(player_selector or "1") - 1]
        return (
            FakeReplay(filename=str(path)),
            PlayerRef(pid=player.pid, name=player.name, race=player.play_race),
            [BuildOrderItem(frame=16, seconds=1, name="Supply Depot", supply_used=14)],
        )

    monkeypatch.setattr(cli, "load_defaults", lambda: {})
    monkeypatch.setattr(cli, "load_replay", lambda path: FakeReplay(filename=str(path)))
    monkeypatch.setattr(cli, "replay_players", lambda replay: fake_players)
    monkeypatch.setattr(cli, "build_order_for_replay", fake_build_order_for_replay)

    assert cli.main(["--easy", "--no-prompt", str(replay_path)]) == 0

    assert (tmp_path / "practice - Alpha build order.txt").exists()
    assert (tmp_path / "practice - GABE build order.txt").exists()
