import json
import os

CONFIG_DIR = "mods/configs/ANIALLATOR.cpu_performance"
CONFIG_FILE = CONFIG_DIR + "/config.json"

DEFAULTS = {
    "enabled": True,
    "lazyShellTooltips": True,
}

_values = dict(DEFAULTS)


def load():
    _values.clear()
    _values.update(DEFAULTS)

    data = {}
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as handle:
                data = json.load(handle)
        except (IOError, ValueError):
            data = {}
    if not isinstance(data, dict):
        data = {}

    for name in DEFAULTS:
        if name in data:
            _values[name] = bool(data[name])
    # Rewritten so options added by an update show up in the file.
    save()


def save():
    if not os.path.isdir(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
    with open(CONFIG_FILE, "w") as handle:
        json.dump(_values, handle, indent=2, sort_keys=True)


def is_on(name):
    return _values["enabled"] and _values[name]
