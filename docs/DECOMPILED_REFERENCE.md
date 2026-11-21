# Decompiled reference

| Source | Pinned version |
|---|---|
| Game client | [StranikS-Scan/WorldOfTanks-Decompiled `2.4.1_EU`](https://github.com/StranikS-Scan/WorldOfTanks-Decompiled/tree/2.4.1_EU) (live client v2.4.1.1 EU) |

Paths are under `source/res/scripts/`.

## Game behaviour the profiler relies on

- **Battle start and end**: `client_common/ClientArena.py` calls `g_playerEvents.onArenaPeriodChange(period, periodEndTime, periodLength, periodAdditionalInfo)`. `common/constants.py` `ARENA_PERIOD`: `BATTLE = 3`, `AFTERBATTLE = 4`. `client/avatar.py` fires `g_playerEvents.onAvatarReady()` with no arguments once the arena is set up, which is how a battle joined mid-way (or a replay already past the countdown) is picked up. `onAvatarBecomeNonPlayer` covers leaving a battle or replay early.
- **Replay state**: `client/BattleReplay.py` `isPlaying()` is true while a replay plays or rewinds. `g_replayCtrl.playbackSpeed` is 0 when paused and one of `0.0625 … 16.0` otherwise; `g_replayCtrl.isTimeWarpInProgress` is true while rewinding.
- **Map name**: `BigWorld.player().arena.arenaType.geometryName`.
- **GC**: the scripts never set GC thresholds or disable the collector outside the debug helpers in `common/GarbageCollectionDebug.py` and `common/debug_utils.py`, but in a 2.4.1.1 replay `gc.isenabled()` was false for the whole battle and no collections ran, so the engine disables it.
- **Events**: `common/Event.py` `Event.__call__` runs each delegate in `self[:]`, logs with `LOG_CURRENT_EXCEPTION` and re-raises; `SafeEvent.__call__` logs and carries on. `LateEvent` inherits `SafeEvent`; `SuspendedEvent` calls `Event.__call__`; `SynchronousEvent` has its own `__call__` and is not traced. `patches.patch_events` copies both loops, so re-check them on every patch.
- **Event delegates**: usually `common/WeakMethod.py` `WeakMethodProxy`, whose `_methodRef()` returns the bound method.
- **Entities**: `client/Vehicle.py` `Vehicle`, `client/Avatar.py` `PlayerAvatar` (entity type `Avatar`). Engine entry points come from `scripts/entity_defs/<Type>.def` `ClientMethods` and `Properties` (as `set_`/`setSlice_`/`setNested_<name>`), following `Implements/Interface` into `scripts/entity_defs/interfaces/`, read with `ResMgr.openSection`. Other public methods are left alone: many are event handlers, and a replaced method no longer equals the bound method a `-=` unsubscribe passes.
- **Engine hooks**: module functions in `client/game.py` listed in `hooks.ENGINE_HOOKS`.
- **Entities collection**: `BigWorld.entities` has no `len()`; use `values()`.
- **Battle clock**: `arena.periodEndTime - BigWorld.serverTime()` is the time left shown on screen.
- **Interpreter**: Python 2.7. `threading`, `sys._current_frames` and `ctypes` are in `common/Lib`. `cProfile.py` is there too, but `WorldOfTanks.exe` 2.4.1.1 contains no `_lsprof`, so cProfile can't be used.

## Game behaviour the optimisation mod relies on

- **Shell tooltips**: `client/gui/Scaleform/daapi/view/battle/shared/consumables_panel.py` `ConsumablesPanel._makeShellTooltip(descriptor, gunSettings)` is the only place shell tooltip text is built. Its callers are `_addShellSlot` (passes the text to `as_addShellSlotS`), `__updateAllShellTooltips` (from `__onVehicleFeedbackReceived` on `FEEDBACK_EVENT_ID.VEHICLE_ATTRS_CHANGED`, and from `__updateMechanicShellMode`), both passing it to `as_updateTooltipS`. With `GUI_SETTINGS.technicalInfo` off it only formats the header, so the mod leaves that case alone. The placeholder uses the module's own `TOOLTIP_FORMAT`, `backport` and `R`.
- **Attribute syncs**: `client/Avatar.py` `syncVehicleAttrs` → `feedback_adaptor.setVehicleAttrs` → `onVehicleFeedbackReceived(VEHICLE_ATTRS_CHANGED, …)`. In a 2.4.1.1 replay each one cost about 25 ms in `__updateAllShellTooltips`.
- **Showing a tooltip**: the `{HEADER}…{/HEADER}{BODY}…{/BODY}` text is a complex tooltip. Flash hands the string back to `client/gui/Scaleform/framework/tooltip_mgr.py` `ToolTip.onCreateComplexTooltip(tooltipId, stateType)`, which parses it with `ComplexBuilder` (`client/gui/shared/tooltips/builders.py`, `complex_formatters.doFormatToolTip`). The battle app uses this `ToolTip` (`client/gui/Scaleform/battle_entry.py`). The mod swaps its placeholder for the real text there. The Flash side was not inspected, but in the 2.4.1.1 client hovering a shell showed its full stats with the mod on.

## Updating for a new patch

1. Find the new branch: `git ls-remote --heads https://github.com/StranikS-Scan/WorldOfTanks-Decompiled.git`.
2. Re-check the events, replay properties and constants above.
3. Update `tests/fakes.py` if any of this changed, then the pin in this file.
