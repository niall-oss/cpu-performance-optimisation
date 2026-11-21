"""Stand-ins for the game modules the profiler talks to.

Behaviour mirrors the sources pinned in docs/DECOMPILED_REFERENCE.md.
"""

import types


def make_event_module(logged):
    """common/Event.py: Event re-raises handler errors, SafeEvent swallows them."""

    def log_exception():
        logged.append("exception")

    class Event(list):
        def __call__(self, *args, **kwargs):
            for delegate in self[:]:
                try:
                    delegate(*args, **kwargs)
                except:
                    log_exception()
                    raise

        def __iadd__(self, delegate):
            if delegate not in self:
                self.append(delegate)
            return self

        def __isub__(self, delegate):
            if delegate in self:
                self.remove(delegate)
            return self

    class SafeEvent(Event):
        def __call__(self, *args, **kwargs):
            for delegate in self[:]:
                try:
                    delegate(*args, **kwargs)
                except:  # noqa: E722 - same as the game
                    log_exception()

    return types.SimpleNamespace(
        __name__="Event",
        Event=Event,
        SafeEvent=SafeEvent,
        LOG_CURRENT_EXCEPTION=log_exception,
    )


class FakeClock:
    def __init__(self):
        self.seconds = 1000.0

    def __call__(self):
        return self.seconds

    def advance_ms(self, ms):
        self.seconds += ms / 1000.0


class FakeEntities(dict):
    """BigWorld.entities has no len() in the real client."""

    def __len__(self):
        raise TypeError("object of type 'PyEntities' has no len()")


class FakeBigWorld(types.ModuleType):
    """BigWorld.callback(0, fn) runs fn on the next engine tick."""

    def __init__(self, clock):
        super().__init__("BigWorld")
        self._clock = clock
        self._pending = []
        self.entities = FakeEntities()
        self.arena = types.SimpleNamespace(
            period=0,
            periodEndTime=1600.0,
            arenaType=types.SimpleNamespace(geometryName="05_prohorovka"),
        )
        self.callback = self._callback

    def _callback(self, delay, fn):
        self._pending.append(fn)
        return len(self._pending)

    def serverTime(self):
        return self._clock.seconds

    def player(self):
        return types.SimpleNamespace(arena=self.arena)

    def run_frame(self, ms):
        """Advances the clock by one frame, then runs everything due."""
        self._clock.advance_ms(ms)
        due, self._pending = self._pending, []
        for fn in due:
            fn()


class FakeSection:
    """ResMgr DataSection: missing children are None."""

    def __init__(self, children=None, text=""):
        self._children = children or []
        self.asString = text

    def __getitem__(self, name):
        for child_name, child in self._children:
            if child_name == name:
                return child
        return None

    def keys(self):
        return [name for name, _ in self._children]

    def values(self):
        return [child for _, child in self._children]


def make_def(client_methods=(), properties=(), interfaces=()):
    children = [
        (
            "ClientMethods",
            FakeSection([(name, FakeSection()) for name in client_methods]),
        ),
        ("Properties", FakeSection([(name, FakeSection()) for name in properties])),
    ]
    if interfaces:
        children.append(
            (
                "Implements",
                FakeSection(
                    [
                        ("Interface", FakeSection(text=f"\t{name}\t"))
                        for name in interfaces
                    ]
                ),
            )
        )
    return FakeSection(children)


def make_resmgr_module(files):
    return types.SimpleNamespace(__name__="ResMgr", openSection=files.get)


class FakeReplayCtrl:
    def __init__(self):
        self.playing = False
        self.isTimeWarpInProgress = False
        self.playbackSpeed = 1.0


def make_battle_replay_module(ctrl):
    return types.SimpleNamespace(
        g_replayCtrl=ctrl,
        isPlaying=lambda: ctrl.playing or ctrl.isTimeWarpInProgress,
    )


ARENA_PERIOD = types.SimpleNamespace(
    IDLE=0, WAITING=1, PREBATTLE=2, BATTLE=3, AFTERBATTLE=4
)
