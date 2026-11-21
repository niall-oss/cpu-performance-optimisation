# CPU Performance Optimisation

Tools for finding and reducing the CPU cost of World of Tanks' Python script layer.

| Mod | Folder | Status |
|---|---|---|
| CPU Performance Optimisation | `optimisation/` | Local testing |
| CPU Profiler | `profiler/` | Development tool, not for distribution |

## CPU Performance Optimisation

Removes CPU stutters caused by the game's own Python UI code. Average FPS doesn't change; the worst frames do.

### Lazy shell tooltips

With technical info turned on in the game's settings, the ammo panel rebuilds every shell's tooltip whenever the server re-sends your vehicle's attributes. That takes about 25 ms on the main thread, about 15 times a battle, for text you only see when hovering a shell. The mod gives each slot a short placeholder instead and builds the real tooltip the first time you hover that shell after a change.

If the swap ever fails, the tooltip shows just the shell type and name.

### Build and install

```powershell
C:\Python27\python.exe build.py optimisation
```

Copy `build/ANIALLATOR.CPU_Performance_Optimisation_<version>.wotmod` into `World_of_Tanks/mods/<game_version>/`.

### Config

`World_of_Tanks/mods/configs/ANIALLATOR.cpu_performance/config.json`:

| Key | Default | |
|---|---|---|
| `enabled` | `true` | Turns every fix off when `false` |
| `lazyShellTooltips` | `true` | |

## CPU Profiler

Records one report per battle or replay, from the moment the battle starts (after the countdown) until it ends or you leave.

- **Frame times**: average FPS, 1% and 0.1% lows, percentiles and spikes. Each frame is the time between two engine ticks, so it covers everything the CPU does, not just Python.
- **Python by entry point**: self and total time for every function the engine enters Python through, with each frame's outermost Python time:
  - `callback`: functions scheduled with `BigWorld.callback`
  - `event`: every handler run by the game's `Event` and `SafeEvent`, which carry most GUI and battle-controller updates
  - `entity`: the client methods and property setters the server (or replay) calls on entities such as `Vehicle` and `Avatar`, as listed in their `.def` files
  - `engine`: input, camera, streaming and destruction hooks in `game.py`
- **Spike frames**: every frame over `spikeMs`, with the on-screen battle clock so you can find it in the replay, its traced Python time and the slowest calls in it.
- **Python GC**: collections during the battle, and at the end a timed collection of each generation on the battle's heap.
- **Timeline**: per-second frame time, Python time, GC collections, entity count and battle clock.
- **Sampler** (off by default): samples the main thread's Python stack from a background thread. On Python 2.7 it only gets the GIL while the engine is in C++, so it can't show which Python is hot.

Everything is patched only while recording, and put back when the battle ends.

Replay frames that are paused, rewound or played at any speed other than 1x are left out (`realtimeOnly`).

### Build and install

```powershell
C:\Python27\python.exe build.py profiler
```

Copy `build/ANIALLATOR.CPU_Profiler_<version>.wotmod` into `World_of_Tanks/mods/<game_version>/`.

### Reports

Written to `World_of_Tanks/mods/logs/ANIALLATOR.cpu_profiler/` as `<time>_<map>`:

- `.txt`: summary, also printed to `python.log`
- `.json`: full report
- `.folded`: sampled stacks in collapsed format, which [speedscope](https://www.speedscope.app/) opens as a flame graph

### Config

`World_of_Tanks/mods/configs/ANIALLATOR.cpu_profiler/config.json`, created on first launch:

| Key | Default | |
|---|---|---|
| `enabled` | `true` | |
| `realtimeOnly` | `true` | Skip replay frames not played at 1x |
| `traceCallbacks` | `true` | Time `BigWorld.callback` functions |
| `traceEvents` | `true` | Time `Event`/`SafeEvent` handlers |
| `traceEntities` | `true` | Time entity client methods and property setters |
| `traceEngineHooks` | `true` | Time the engine hooks in `game.py` |
| `spikeMs` | `20` | Frames at least this long are recorded as spikes |
| `maxSpikes` | `300` | Only the slowest this many spike frames are kept |
| `sampler` | `false` | Sample the main thread's Python stack |
| `samplerIntervalMs` | `5` | |
| `measureGcAtEnd` | `true` | Time one collection of each generation when the battle ends |
| `topN` | `30` | Rows kept in each top list |

Tracing costs some CPU itself, event tracing most of all. Compare runs with the `trace*` options off before trusting small differences. Options missing from the file are added with their defaults on the next launch.

## Development

```powershell
uv sync
uv run pytest
uv run ruff check
uv run ty check
```

The client sources this is written against are pinned in [docs/DECOMPILED_REFERENCE.md](docs/DECOMPILED_REFERENCE.md).
