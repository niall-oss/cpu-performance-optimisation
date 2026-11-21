import pytest
from conftest import REPORT_DIR, read_config, read_reports, write_config
from fakes import ARENA_PERIOD


def _play(game, frames, ms=16.0):
    for _ in range(frames):
        game.bigworld.run_frame(ms)


def _self_ms(report, name):
    for row in report["python"]["topSelf"]:
        if name in row["function"]:
            return row["selfMsPerFrame"]
    raise AssertionError(f"{name} not in {report['python']['topSelf']}")


def _assert_unpatched(game):
    assert game.bigworld.callback is game.original_callback
    assert vars(game.event_module.Event)["__call__"] is game.original_event_call
    assert (
        vars(game.event_module.SafeEvent)["__call__"] is game.original_safe_event_call
    )
    assert game.game_module.handleKeyEvent is game.original_key_handler
    assert dict(vars(game.Vehicle)) == game.original_vehicle_methods


def test_nothing_is_recorded_or_patched_outside_battle(game):
    _play(game, 10)
    game.events.onAvatarBecomeNonPlayer()

    assert not REPORT_DIR.exists()
    _assert_unpatched(game)


def test_config_gains_new_options_and_keeps_the_players(game):
    game.entry.fini()
    write_config(sampler=True, callbackTiming=False)

    game.entry.init()

    config = read_config()
    assert config["sampler"] is True
    assert config["traceEvents"] is True
    assert "callbackTiming" not in config


def test_battle_frames_are_reported(game):
    game.set_period(ARENA_PERIOD.BATTLE)
    _play(game, 1)  # first tick only sets the baseline
    _play(game, 99, ms=16.0)
    _play(game, 1, ms=50.0)
    game.set_period(ARENA_PERIOD.AFTERBATTLE)

    [report] = read_reports()
    assert report["meta"]["map"] == "05_prohorovka"
    assert report["frames"]["frames"] == 100
    assert report["frames"]["p50Ms"] == pytest.approx(16.0)
    assert report["frames"]["maxMs"] == pytest.approx(50.0)
    assert report["timeline"][0]["entities"] == 0
    assert report["timeline"][0]["battleClock"] == "9:59"
    assert report["gc"]["measuredAtEnd"]["trackedObjects"] > 0
    assert report["sampler"] is None
    assert list(REPORT_DIR.glob("*.txt"))
    assert any("avg" in note and "fps" in note for note in game.notes)
    _assert_unpatched(game)


def test_nested_python_gets_self_and_frame_time(game):
    game.set_period(ARENA_PERIOD.BATTLE)
    on_update = game.event_module.Event()

    def slow_gui_handler():
        game.clock.advance_ms(3.0)

    def game_update():
        game.clock.advance_ms(1.0)
        on_update()
        game.bigworld.callback(0.0, game_update)

    on_update += slow_gui_handler
    game.bigworld.callback(0.0, game_update)
    _play(game, 11)
    game.set_period(ARENA_PERIOD.AFTERBATTLE)

    [report] = read_reports()
    assert _self_ms(report, "[event] slow_gui_handler") == pytest.approx(3.0, rel=0.1)
    assert _self_ms(report, "[callback] game_update") == pytest.approx(1.0, rel=0.1)
    assert report["python"]["msPerFrame"] == pytest.approx(4.0)
    by_kind = report["python"]["selfMsPerFrameByKind"]
    assert by_kind["event"] == pytest.approx(3.0, rel=0.1)


def test_entity_engine_methods_are_timed_and_restored(game):
    vehicle = game.Vehicle()
    game.bigworld.entities[7] = vehicle
    game.set_period(ARENA_PERIOD.BATTLE)

    def network_update():
        vehicle.showShooting(3)
        vehicle.set_health(90)
        vehicle.onHealthChanged(90)
        vehicle.publicHelper()
        game.game_module.handleKeyEvent(None)
        game.bigworld.callback(0.0, network_update)

    game.bigworld.callback(0.0, network_update)
    _play(game, 11)
    assert vehicle.showShooting(5) == 5
    game.set_period(ARENA_PERIOD.AFTERBATTLE)

    [report] = read_reports()
    names = [row["function"] for row in report["python"]["topSelf"]]
    assert any("[entity] Vehicle.showShooting" in name for name in names)
    assert any("[entity] Vehicle.set_health" in name for name in names)
    assert any("[entity] Vehicle.onHealthChanged" in name for name in names)
    assert not any("publicHelper" in name for name in names)
    assert any("[engine] game.handleKeyEvent" in name for name in names)
    assert _self_ms(report, "showShooting") == pytest.approx(2.0, rel=0.1)
    assert report["meta"]["patchedEntryPoints"] >= 7
    assert report["timeline"][0]["entities"] == 1
    _assert_unpatched(game)


def test_spike_frames_record_the_slowest_python(game):
    game.set_period(ARENA_PERIOD.BATTLE)
    _play(game, 5)

    def tank_destroyed_effects():
        game.clock.advance_ms(30.0)

    game.bigworld.callback(0.0, tank_destroyed_effects)
    _play(game, 1)
    _play(game, 5)
    game.set_period(ARENA_PERIOD.AFTERBATTLE)

    [report] = read_reports()
    spikes = report["spikes"]
    assert spikes["count"] == 1
    [spike] = spikes["recorded"]
    assert spike["frameMs"] == pytest.approx(46.0)
    assert spike["pythonMs"] == pytest.approx(30.0)
    assert spike["battleClock"] == "9:59"
    assert "tank_destroyed_effects" in spike["calls"][0]["function"]
    assert any("tank_destroyed_effects" in note for note in game.notes)


def test_only_the_worst_spikes_are_kept(game):
    game.entry.fini()
    write_config(maxSpikes=2)
    game.entry.init()
    game.set_period(ARENA_PERIOD.BATTLE)
    _play(game, 1)
    for ms in (30.0, 60.0, 25.0, 40.0):
        _play(game, 1, ms=ms)
    game.set_period(ARENA_PERIOD.AFTERBATTLE)

    [report] = read_reports()
    assert report["spikes"]["count"] == 4
    assert sorted(s["frameMs"] for s in report["spikes"]["recorded"]) == [
        pytest.approx(40.0),
        pytest.approx(60.0),
    ]


def test_patched_events_keep_their_error_handling(game):
    game.set_period(ARENA_PERIOD.BATTLE)

    def broken():
        raise ValueError("handler failed")

    reached = []
    strict = game.event_module.Event()
    strict += broken
    strict += lambda: reached.append("strict")
    safe = game.event_module.SafeEvent()
    safe += broken
    safe += lambda: reached.append("safe")

    with pytest.raises(ValueError):
        strict()
    safe()

    assert reached == ["safe"]
    assert game.logged == ["exception", "exception"]
    game.set_period(ARENA_PERIOD.AFTERBATTLE)


def test_paused_and_fast_replay_frames_are_excluded(game):
    game.replay.playing = True
    game.set_period(ARENA_PERIOD.BATTLE)
    _play(game, 11)
    game.replay.playbackSpeed = 0
    _play(game, 5)
    game.replay.playbackSpeed = 4.0
    _play(game, 3)
    game.set_period(ARENA_PERIOD.AFTERBATTLE)

    [report] = read_reports()
    assert report["meta"]["replay"] is True
    assert report["frames"]["frames"] == 10
    assert report["excludedFrames"] == {"paused": 5, "speed_4": 3}


def test_joining_a_battle_in_progress_starts_recording(game):
    game.bigworld.arena.period = ARENA_PERIOD.BATTLE
    game.events.onAvatarReady()
    _play(game, 6)
    game.events.onAvatarBecomeNonPlayer()

    [report] = read_reports()
    assert report["frames"]["frames"] == 5


def test_shutting_down_mid_battle_writes_the_report(game):
    game.set_period(ARENA_PERIOD.BATTLE)
    _play(game, 6)
    game.entry.fini()

    [report] = read_reports()
    assert report["frames"]["frames"] == 5
    assert not game.events.onArenaPeriodChange
    _assert_unpatched(game)
