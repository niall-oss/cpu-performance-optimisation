import gc

from gui.cpuprofiler import clock


class GcWatch(object):
    """Infers which collections ran between polls from gc.get_count().

    Python 2.7 has no gc.callbacks. count[1] goes up by one per gen0
    collection and resets on gen1; count[2] goes up by one per gen1 collection
    and resets on gen2. count[0] also drops when objects are freed, so it
    cannot be used.
    """

    def __init__(self, get_count=gc.get_count):
        self._get_count = get_count
        self._previous = get_count()
        self.collections = [0, 0, 0]

    def poll(self):
        """Returns the oldest generation collected since the last poll, or -1."""
        current = self._get_count()
        previous = self._previous
        self._previous = current

        if current[2] < previous[2]:
            self.collections[2] += 1
            self.collections[0] += current[1]
            return 2
        if current[2] > previous[2]:
            self.collections[1] += current[2] - previous[2]
            self.collections[0] += current[1]
            return 1
        if current[1] > previous[1]:
            self.collections[0] += current[1] - previous[1]
            return 0
        return -1


def _timed_collect(collect, generation):
    start = clock.now()
    unreachable = collect(generation)
    return (clock.now() - start) * 1000.0, unreachable


def measure_collections(collect=gc.collect, get_objects=gc.get_objects):
    gen0_ms, _ = _timed_collect(collect, 0)
    gen1_ms, _ = _timed_collect(collect, 1)
    gen2_ms, unreachable = _timed_collect(collect, 2)
    return {
        "trackedObjects": len(get_objects()),
        "thresholds": list(gc.get_threshold()),
        "enabled": gc.isenabled(),
        "gen0Ms": gen0_ms,
        "gen1Ms": gen1_ms,
        "gen2Ms": gen2_ms,
        "gen2Unreachable": unreachable,
    }
