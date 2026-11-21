from gui.cpuprofiler import clock

REALTIME_STATES = ("live", "realtime")
SPIKE_TOP_CALLS = 8


class Session(object):
    """Collects one battle's worth of frame data.

    A zero-delay callback runs once per engine tick, so the time between two
    runs is the whole frame: engine, rendering submit and every script.
    """

    def __init__(self, schedule, replay_state, entity_count, battle_clock,
                 tracer=None, sampler=None, gc_watch=None, realtime_only=True,
                 spike_ms=20.0, max_spikes=300, on_new_second=None):
        self._schedule = schedule
        self._replay_state = replay_state
        self._entity_count = entity_count
        self._battle_clock = battle_clock
        self.tracer = tracer
        self.sampler = sampler
        self.gc_watch = gc_watch
        self.realtime_only = realtime_only
        self.spike_ms = spike_ms
        self.max_spikes = max_spikes
        self._on_new_second = on_new_second

        self.running = False
        self.started_at = None
        self.stopped_at = None
        self._last_tick = None
        self.frames = []
        self.python_ms_total = 0.0
        self.excluded = {}
        self.gc_frames = ([], [], [])
        self.timeline = {}
        self.spikes = []
        self.spike_count = 0

    def start(self):
        self.running = True
        self.started_at = clock.now()
        if self.tracer is not None:
            self.tracer.active = True
        if self.sampler is not None:
            self.sampler.start()
        self._schedule(0.0, self._tick)

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.stopped_at = clock.now()
        if self.tracer is not None:
            self.tracer.active = False
        if self.sampler is not None:
            self.sampler.stop()

    def _tick(self):
        if not self.running:
            return
        self._schedule(0.0, self._tick)

        now = clock.now()
        last = self._last_tick
        self._last_tick = now
        state = self._replay_state()
        excluded = self.realtime_only and state not in REALTIME_STATES
        keep = last is not None and not excluded
        python_ms, calls = self.tracer.take_frame(keep) if self.tracer else (0.0, [])
        generation = self.gc_watch.poll() if self.gc_watch else -1
        if last is None:
            return
        if excluded:
            self.excluded[state] = self.excluded.get(state, 0) + 1
            return

        frame_ms = (now - last) * 1000.0
        second = int(now - self.started_at)
        self.frames.append(frame_ms)
        self.python_ms_total += python_ms
        if generation >= 0:
            self.gc_frames[generation].append(frame_ms)
        self._add_to_timeline(second, frame_ms, python_ms, generation)
        if frame_ms >= self.spike_ms:
            self._add_spike(second, frame_ms, python_ms, generation, calls)

    def _add_spike(self, second, frame_ms, python_ms, generation, calls):
        self.spike_count += 1
        slowest = sorted(calls, key=lambda call: call[1], reverse=True)[:SPIKE_TOP_CALLS]
        spike = {
            "second": second,
            "battleClock": self._battle_clock(),
            "frameMs": frame_ms,
            "pythonMs": python_ms,
            "gcGeneration": generation,
            "calls": [(key, seconds * 1000.0) for key, seconds in slowest],
        }
        if len(self.spikes) < self.max_spikes:
            self.spikes.append(spike)
            return
        smallest = min(range(len(self.spikes)), key=lambda i: self.spikes[i]["frameMs"])
        if frame_ms > self.spikes[smallest]["frameMs"]:
            self.spikes[smallest] = spike

    def _add_to_timeline(self, second, frame_ms, python_ms, generation):
        bucket = self.timeline.get(second)
        if bucket is None:
            if self._on_new_second is not None:
                self._on_new_second()
            bucket = self.timeline[second] = {
                "frames": 0,
                "totalMs": 0.0,
                "maxMs": 0.0,
                "pythonMs": 0.0,
                "gen1": 0,
                "gen2": 0,
                "entities": self._entity_count(),
                "battleClock": self._battle_clock(),
            }
        bucket["frames"] += 1
        bucket["totalMs"] += frame_ms
        bucket["pythonMs"] += python_ms
        if frame_ms > bucket["maxMs"]:
            bucket["maxMs"] = frame_ms
        if generation == 1:
            bucket["gen1"] += 1
        elif generation == 2:
            bucket["gen2"] += 1
