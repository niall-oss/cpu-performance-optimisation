import os
import re
import threading
import time

import BattleReplay
import BigWorld
import Event
import ResMgr
import game
from constants import ARENA_PERIOD
from debug_utils import LOG_CURRENT_EXCEPTION, LOG_NOTE
from PlayerEvents import g_playerEvents

from gui.cpuprofiler import config, report
from gui.cpuprofiler.entity_defs import def_name_for, engine_method_names
from gui.cpuprofiler.gc_watch import GcWatch, measure_collections
from gui.cpuprofiler.patches import (
    Patches,
    patch_callback,
    patch_entity_methods,
    patch_events,
    patch_module_functions,
)
from gui.cpuprofiler.sampler import Sampler
from gui.cpuprofiler.session import Session
from gui.cpuprofiler.tracer import Tracer

# Functions in scripts/client/game.py the engine calls directly.
ENGINE_HOOKS = (
    "handleKeyEvent",
    "handleMouseEvent",
    "handleAxisEvent",
    "onCameraChange",
    "onStreamComplete",
    "onGeometryMapped",
    "onMemoryCritical",
    "wg_onChunkLoad",
    "wg_onChunkLoose",
    "wg_playModuleDestructionAnimation",
)

_installed = False
_session = None
_meta = None
_patches = None
_entity_patcher = None


class _EntityPatcher(object):
    """Patches each entity class the first time one of its entities is seen."""

    def __init__(self, patches, tracer):
        self._patches = patches
        self._tracer = tracer
        self._seen_classes = set()
        self._patched = set()
        self._names_by_def = {}

    def scan(self):
        for entity in _entities():
            cls = type(entity)
            if cls in self._seen_classes:
                continue
            self._seen_classes.add(cls)
            def_name = def_name_for(cls)
            names = self._names_by_def.get(def_name)
            if names is None:
                names = self._names_by_def[def_name] = engine_method_names(
                    def_name, ResMgr.openSection)
            patch_entity_methods(self._patches, self._tracer, cls, names, self._patched)


def _entities():
    try:
        return list(BigWorld.entities.values())
    except Exception:
        return []


def _entity_count():
    return len(_entities())


def _battle_clock():
    try:
        arena = BigWorld.player().arena
        remaining = int(arena.periodEndTime - BigWorld.serverTime())
    except Exception:
        return None
    if remaining < 0:
        return None
    return "%d:%02d" % (remaining // 60, remaining % 60)


def _replay_state():
    if not BattleReplay.isPlaying():
        return "live"
    ctrl = BattleReplay.g_replayCtrl
    if ctrl.isTimeWarpInProgress:
        return "rewinding"
    speed = ctrl.playbackSpeed
    if speed == 0:
        return "paused"
    if speed != 1.0:
        return "speed_%g" % speed
    return "realtime"


def _client_version():
    try:
        with open("version.xml", "r") as handle:
            match = re.search(r"<version>\s*([^<]+?)\s*</version>", handle.read())
    except IOError:
        return None
    return match.group(1) if match else None


def _installed_mods():
    mods = []
    if not os.path.isdir("mods"):
        return mods
    for folder in sorted(os.listdir("mods")):
        path = os.path.join("mods", folder)
        if folder[:1].isdigit() and os.path.isdir(path):
            mods.extend(sorted(os.listdir(path)))
    return mods


def _map_name():
    try:
        return BigWorld.player().arena.arenaType.geometryName
    except Exception:
        return "unknown"


def _apply_patches(tracer):
    global _patches, _entity_patcher
    _patches = Patches()
    _entity_patcher = None
    if config.get("traceCallbacks"):
        patch_callback(_patches, tracer, BigWorld)
    if config.get("traceEvents"):
        patch_events(_patches, tracer, Event)
    if config.get("traceEngineHooks"):
        patch_module_functions(_patches, tracer, game, ENGINE_HOOKS)
    if config.get("traceEntities"):
        _entity_patcher = _EntityPatcher(_patches, tracer)
        _entity_patcher.scan()


def _restore_patches():
    global _patches, _entity_patcher
    if _patches is not None:
        _patches.restore_all()
    _patches = None
    _entity_patcher = None


def _scan_entities():
    if _entity_patcher is not None:
        _entity_patcher.scan()


def _start():
    global _session, _meta
    if _session is not None:
        return

    schedule = BigWorld.callback
    tracer = Tracer()
    _apply_patches(tracer)
    sampler = None
    if config.get("sampler"):
        sampler = Sampler(config.get("samplerIntervalMs") / 1000.0,
                          threading.current_thread().ident)

    _meta = {
        "map": _map_name(),
        "replay": BattleReplay.isPlaying(),
        "startedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "clientVersion": _client_version(),
        "mods": _installed_mods(),
        "config": config.snapshot(),
        "patchedEntryPoints": len(_patches),
    }
    _session = Session(
        schedule, _replay_state, _entity_count, _battle_clock,
        tracer=tracer, sampler=sampler, gc_watch=GcWatch(),
        realtime_only=config.get("realtimeOnly"),
        spike_ms=config.get("spikeMs"), max_spikes=config.get("maxSpikes"),
        on_new_second=_scan_entities,
    )
    _session.start()
    LOG_NOTE("CPU Profiler: recording started on %s" % _meta["map"])


def _finish():
    global _session
    session = _session
    if session is None:
        return
    _session = None
    session.stop()
    _meta["patchedEntryPoints"] = len(_patches) if _patches is not None else 0
    _restore_patches()

    try:
        measured = measure_collections() if config.get("measureGcAtEnd") else None
        result = report.build(session, _meta, measured, config.get("topN"))
        folded = report.folded_stacks(session.sampler) if session.sampler else []
        basename = time.strftime("%Y%m%d_%H%M%S_") + _meta["map"]
        base = report.write(result, folded, config.REPORT_DIR, basename)
        for line in report.summary_lines(result):
            LOG_NOTE(line)
        LOG_NOTE("CPU Profiler: report written to %s.json" % base)
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _on_arena_period_change(period, *args):
    if period == ARENA_PERIOD.BATTLE:
        _start()
    elif period == ARENA_PERIOD.AFTERBATTLE:
        _finish()


def _on_avatar_ready():
    try:
        period = BigWorld.player().arena.period
    except AttributeError:
        return
    if period == ARENA_PERIOD.BATTLE:
        _start()


def _on_avatar_become_non_player(*args):
    _finish()


_SUBSCRIPTIONS = (
    ("onArenaPeriodChange", _on_arena_period_change),
    ("onAvatarReady", _on_avatar_ready),
    ("onAvatarBecomeNonPlayer", _on_avatar_become_non_player),
)


def install():
    global _installed
    if _installed:
        return
    for name, handler in _SUBSCRIPTIONS:
        event = getattr(g_playerEvents, name)
        event += handler
    _installed = True


def uninstall():
    global _installed
    if not _installed:
        return
    _finish()
    for name, handler in _SUBSCRIPTIONS:
        event = getattr(g_playerEvents, name)
        event -= handler
    _installed = False
