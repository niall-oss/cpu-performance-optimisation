import sys
import threading
import time

from gui.cpuprofiler import clock
from gui.cpuprofiler.code_names import code_key

_OWN_PACKAGE = "cpuprofiler"
MAX_DEPTH = 32


def stack_of(frame):
    """Leaf-first stack, without the profiler's own wrapper frames."""
    stack = []
    while frame is not None and len(stack) < MAX_DEPTH:
        code = frame.f_code
        if _OWN_PACKAGE not in code.co_filename:
            stack.append(code_key(code))
        frame = frame.f_back
    return tuple(stack)


class Sampler(object):
    """Samples the main thread's Python stack from a background thread.

    It can only take a sample when it holds the GIL, so if the engine keeps
    the GIL during its own C++ work the achieved rate drops below the
    requested one. The report shows both.
    """

    def __init__(self, interval_seconds, target_thread_id,
                 current_frames=sys._current_frames, sleep=time.sleep):
        self.interval = interval_seconds
        self.target_thread_id = target_thread_id
        self._current_frames = current_frames
        self._sleep = sleep
        self._stopping = threading.Event()
        self._thread = None
        self.stacks = {}
        self.samples = 0
        self.outside_python = 0
        self.started_at = None
        self.stopped_at = None

    def start(self):
        self.started_at = clock.now()
        self._thread = threading.Thread(target=self._run, name="cpuprofiler-sampler")
        self._thread.daemon = True
        self._thread.start()

    def stop(self):
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(1.0)
            self._thread = None
        self.stopped_at = clock.now()

    def _run(self):
        while not self._stopping.is_set():
            self._sleep(self.interval)
            self.take()

    def take(self):
        frame = self._current_frames().get(self.target_thread_id)
        self.samples += 1
        stack = stack_of(frame) if frame is not None else ()
        if not stack:
            self.outside_python += 1
            return
        self.stacks[stack] = self.stacks.get(stack, 0) + 1

    def self_counts(self):
        counts = {}
        for stack, count in self.stacks.items():
            counts[stack[0]] = counts.get(stack[0], 0) + count
        return counts

    def inclusive_counts(self):
        counts = {}
        for stack, count in self.stacks.items():
            for key in set(stack):
                counts[key] = counts.get(key, 0) + count
        return counts

    def requested_samples(self):
        if self.started_at is None:
            return 0
        end = self.stopped_at if self.stopped_at is not None else clock.now()
        return int((end - self.started_at) / self.interval)
