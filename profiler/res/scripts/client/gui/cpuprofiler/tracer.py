from gui.cpuprofiler import clock

MAX_FRAME_ENTRIES = 256


class Tracer(object):
    """Times Python entered through the patched entry points.

    Calls nest (a callback fires an event whose handler calls an entity
    method), so each key gets inclusive and self time, and only outermost
    calls count towards the frame's Python time.
    """

    def __init__(self):
        self.active = False
        self.stats = {}
        self._frame_stats = {}
        self._child_seconds = []
        self._frame_seconds = 0.0
        self._frame_entries = []

    def run(self, kind, key, fn, args, kwargs):
        if not self.active:
            return fn(*args, **kwargs)
        children = self._child_seconds
        children.append(0.0)
        start = clock.now()
        try:
            return fn(*args, **kwargs)
        finally:
            elapsed = clock.now() - start
            inner = children.pop()
            self._record((kind, key), elapsed, elapsed - inner)
            if children:
                children[-1] += elapsed
            else:
                self._frame_seconds += elapsed
                if len(self._frame_entries) < MAX_FRAME_ENTRIES:
                    self._frame_entries.append(((kind, key), elapsed))

    def _record(self, key, total, own):
        entry = self._frame_stats.get(key)
        if entry is None:
            self._frame_stats[key] = [1, total, own, total]
            return
        entry[0] += 1
        entry[1] += total
        entry[2] += own
        if total > entry[3]:
            entry[3] = total

    def take_frame(self, keep):
        """Ends the frame: returns its outermost Python ms and (key, seconds) calls.

        Only kept frames count towards stats, so per-frame figures exclude
        paused or fast-forwarded replay frames.
        """
        seconds, entries, frame_stats = (
            self._frame_seconds, self._frame_entries, self._frame_stats)
        self._frame_seconds = 0.0
        self._frame_entries = []
        self._frame_stats = {}
        if keep:
            self._merge(frame_stats)
        return seconds * 1000.0, entries

    def _merge(self, frame_stats):
        stats = self.stats
        for key, (calls, total, own, worst) in frame_stats.items():
            entry = stats.get(key)
            if entry is None:
                stats[key] = [calls, total, own, worst]
                continue
            entry[0] += calls
            entry[1] += total
            entry[2] += own
            if worst > entry[3]:
                entry[3] = worst
