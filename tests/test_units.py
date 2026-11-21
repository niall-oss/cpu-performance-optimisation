import functools
import sys
import threading

import pytest


@pytest.fixture
def mod(game):
    from gui.cpuprofiler import code_names, frame_stats, gc_watch, sampler

    return code_names, frame_stats, gc_watch, sampler


def test_engine_method_names_follow_interfaces(game):
    from conftest import ENTITY_DEFS
    from gui.cpuprofiler import entity_defs

    names = entity_defs.engine_method_names("Vehicle", ENTITY_DEFS.get)

    assert {"showShooting", "onHealthChanged", "set_health"} <= names
    assert entity_defs.engine_method_names("Missing", ENTITY_DEFS.get) == set()


def test_player_classes_use_their_entity_def(game):
    from gui.cpuprofiler import entity_defs

    class PlayerAvatar:
        pass

    class Vehicle:
        pass

    assert entity_defs.def_name_for(PlayerAvatar) == "Avatar"
    assert entity_defs.def_name_for(Vehicle) == "Vehicle"


def test_weak_method_proxies_are_named_by_their_target(mod):
    code_names = mod[0]
    owner = _Owner()

    class WeakMethodProxy:
        def __init__(self, method):
            self._methodRef = lambda: method

        def __call__(self):
            pass

    key = code_names.callable_key(WeakMethodProxy(owner.method))

    assert key[2:] == ("method", "_Owner")


def test_summary_reports_lows_from_the_slowest_frames(mod):
    _, frame_stats, _, _ = mod
    frames = [10.0] * 990 + [50.0] * 10

    summary = frame_stats.summarize(frames)

    assert summary["frames"] == 1000
    assert summary["p50Ms"] == 10.0
    assert summary["maxMs"] == 50.0
    assert summary["onePercentLowFps"] == pytest.approx(20.0)
    assert summary["avgFps"] == pytest.approx(1000.0 * 1000 / (9900 + 500))
    assert summary["spikesOver2xMedian"] == 10


def test_summary_of_no_frames(mod):
    _, frame_stats, _, _ = mod
    assert frame_stats.summarize([]) == {"frames": 0}


@pytest.mark.parametrize(
    "before, after, generation",
    [
        ((100, 3, 2), (120, 3, 2), -1),
        ((100, 3, 2), (5, 4, 2), 0),
        ((100, 9, 2), (5, 0, 3), 1),
        ((100, 9, 9), (5, 0, 0), 2),
    ],
)
def test_gc_watch_infers_the_oldest_generation_collected(
    mod, before, after, generation
):
    _, _, gc_watch, _ = mod
    counts = iter([before, after])
    watch = gc_watch.GcWatch(get_count=lambda: next(counts))

    assert watch.poll() == generation


def test_gc_watch_counts_collections(mod):
    _, _, gc_watch, _ = mod
    counts = iter([(0, 0, 0), (0, 2, 0), (0, 1, 1), (0, 0, 0)])
    watch = gc_watch.GcWatch(get_count=lambda: next(counts))

    watch.poll()
    watch.poll()
    watch.poll()

    assert watch.collections == [3, 1, 1]


def test_measuring_collections_reports_the_heap(mod):
    _, _, gc_watch, _ = mod
    measured = gc_watch.measure_collections()

    assert measured["trackedObjects"] > 0
    assert len(measured["thresholds"]) == 3


class _Owner:
    def method(self):
        pass

    def __call__(self):
        pass


def test_callable_keys_name_the_function(mod):
    code_names = mod[0]
    owner = _Owner()

    def plain():
        pass

    assert code_names.callable_key(plain)[2] == "plain"
    assert code_names.callable_key(owner.method)[2:] == ("method", "_Owner")
    assert code_names.callable_key(functools.partial(plain))[2] == "plain"
    assert code_names.callable_key(owner)[2:] == ("__call__", "_Owner")
    assert code_names.callable_key(len)[0] == "<native>"
    assert "_Owner.method" in code_names.describe(code_names.callable_key(owner.method))


def test_sampler_records_the_target_threads_stack(mod):
    *_, sampler_module = mod
    sampler = sampler_module.Sampler(0.005, threading.get_ident())

    def busy_function():
        sampler.take()

    busy_function()

    names = {key[2] for key in sampler.inclusive_counts()}
    assert "busy_function" in names
    assert "take" not in names
    assert sampler.samples == 1
    assert sampler.outside_python == 0


def test_sampler_counts_samples_outside_python(mod):
    *_, sampler_module = mod
    sampler = sampler_module.Sampler(0.005, 123456, current_frames=dict)

    sampler.take()

    assert sampler.outside_python == 1
    assert not sampler.stacks


def test_sampler_thread_starts_and_stops(mod):
    *_, sampler_module = mod
    sampler = sampler_module.Sampler(
        0.001, threading.get_ident(), current_frames=sys._current_frames
    )

    sampler.start()
    sampler.stop()

    assert sampler._thread is None
