import json
import sys
import types
from pathlib import Path

import pytest
from fakes import (
    ARENA_PERIOD,
    FakeBigWorld,
    FakeClock,
    FakeReplayCtrl,
    make_battle_replay_module,
    make_def,
    make_event_module,
    make_resmgr_module,
)

CLIENT_SCRIPTS = (
    Path(__file__).resolve().parents[1] / "profiler" / "res" / "scripts" / "client"
)
MOD_PACKAGES = ("gui.cpuprofiler", "gui.mods")
CONFIG_DIR = Path("mods/configs/ANIALLATOR.cpu_profiler")
REPORT_DIR = Path("mods/logs/ANIALLATOR.cpu_profiler")


def _forget_mod_modules():
    for name in list(sys.modules):
        if any(name == pkg or name.startswith(pkg + ".") for pkg in MOD_PACKAGES):
            del sys.modules[name]


def write_config(**overrides):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / "config.json").write_text(json.dumps(overrides))


def read_config():
    return json.loads((CONFIG_DIR / "config.json").read_text())


def read_reports():
    return [json.loads(path.read_text()) for path in sorted(REPORT_DIR.glob("*.json"))]


def make_vehicle_class(clock):
    class Vehicle:
        def __init__(self):
            self.health = 100

        def showShooting(self, burst):
            clock.advance_ms(2.0)
            return burst

        def set_health(self, previous):
            clock.advance_ms(1.0)

        def onHealthChanged(self, health):
            pass

        def publicHelper(self):
            pass

    return Vehicle


ENTITY_DEFS = {
    "scripts/entity_defs/Vehicle.def": make_def(
        client_methods=["showShooting"], properties=["health"], interfaces=["Harm"]
    ),
    "scripts/entity_defs/interfaces/Harm.def": make_def(
        client_methods=["onHealthChanged"]
    ),
}


def _make_game_module(clock):
    def handleKeyEvent(event):
        clock.advance_ms(0.5)
        return True

    return types.SimpleNamespace(__name__="game", handleKeyEvent=handleKeyEvent)


@pytest.fixture
def game(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    clock = FakeClock()
    bigworld = FakeBigWorld(clock)
    replay = FakeReplayCtrl()
    logged = []
    event_module = make_event_module(logged)
    player_events = types.SimpleNamespace(
        onArenaPeriodChange=event_module.Event(),
        onAvatarReady=event_module.Event(),
        onAvatarBecomeNonPlayer=event_module.Event(),
    )
    notes = []
    exceptions = []
    game_module = _make_game_module(clock)
    Vehicle = make_vehicle_class(clock)

    def module(name, **attrs):
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, mod)
        return mod

    monkeypatch.setitem(sys.modules, "BigWorld", bigworld)
    monkeypatch.setitem(sys.modules, "BattleReplay", make_battle_replay_module(replay))
    monkeypatch.setitem(sys.modules, "Event", event_module)
    monkeypatch.setitem(sys.modules, "ResMgr", make_resmgr_module(ENTITY_DEFS))
    monkeypatch.setitem(sys.modules, "game", game_module)
    module("constants", ARENA_PERIOD=ARENA_PERIOD)
    module(
        "debug_utils",
        LOG_NOTE=notes.append,
        LOG_CURRENT_EXCEPTION=lambda: exceptions.append(sys.exc_info()),
    )
    module("PlayerEvents", g_playerEvents=player_events)
    gui = module("gui")
    gui.__path__ = [str(CLIENT_SCRIPTS / "gui")]

    write_config()
    _forget_mod_modules()
    from gui.cpuprofiler import clock as clock_module

    monkeypatch.setattr(clock_module, "_source", clock)
    import gui.mods.mod_cpuprofiler as entry

    state = types.SimpleNamespace(
        entry=entry,
        clock=clock,
        bigworld=bigworld,
        original_callback=bigworld.callback,
        event_module=event_module,
        original_event_call=vars(event_module.Event)["__call__"],
        original_safe_event_call=vars(event_module.SafeEvent)["__call__"],
        game_module=game_module,
        original_key_handler=game_module.handleKeyEvent,
        Vehicle=Vehicle,
        original_vehicle_methods=dict(vars(Vehicle)),
        replay=replay,
        events=player_events,
        logged=logged,
        notes=notes,
        exceptions=exceptions,
    )

    def set_period(period):
        bigworld.arena.period = period
        player_events.onArenaPeriodChange(period, 0.0, 0.0, None)

    state.set_period = set_period
    entry.init()
    yield state
    entry.fini()
    _forget_mod_modules()
    assert not exceptions, exceptions
