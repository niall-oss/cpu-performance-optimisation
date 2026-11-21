import json
import os

CONFIG_DIR = "mods/configs/ANIALLATOR.cpu_profiler"
CONFIG_FILE = CONFIG_DIR + "/config.json"
REPORT_DIR = "mods/logs/ANIALLATOR.cpu_profiler"

DEFAULTS = {
    "enabled": True,
    # Frames played back paused, sped up, slowed down or rewound do not
    # represent live gameplay load.
    "realtimeOnly": True,
    "traceCallbacks": True,
    "traceEvents": True,
    "traceEntities": True,
    "traceEngineHooks": True,
    "spikeMs": 20.0,
    "maxSpikes": 300,
    # On Python 2.7 the sampler only gets the GIL while the engine is in C++,
    # so it cannot see which Python is hot.
    "sampler": False,
    "samplerIntervalMs": 5,
    "measureGcAtEnd": True,
    "topN": 30,
}

_values = dict(DEFAULTS)


def _coerce(name, value):
    default = DEFAULTS[name]
    if isinstance(default, bool):
        return bool(value)
    try:
        number = type(default)(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def load():
    _values.clear()
    _values.update(DEFAULTS)

    if not os.path.isfile(CONFIG_FILE):
        save()
        return

    try:
        with open(CONFIG_FILE, "r") as handle:
            data = json.load(handle)
    except (IOError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}

    for name in DEFAULTS:
        if name in data:
            _values[name] = _coerce(name, data[name])
    # Rewritten so options added by an update show up in the file.
    save()


def save():
    if not os.path.isdir(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
    with open(CONFIG_FILE, "w") as handle:
        json.dump(_values, handle, indent=2, sort_keys=True)


def get(name):
    return _values[name]


def snapshot():
    return dict(_values)
