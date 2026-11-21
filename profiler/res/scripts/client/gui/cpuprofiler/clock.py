import time

# Python 2.7 on Windows has no perf_counter; its time.clock is the same
# QueryPerformanceCounter source.
_source = getattr(time, "perf_counter", None) or time.clock


def now():
    return _source()
