import json
import os

from gui.cpuprofiler.code_names import describe
from gui.cpuprofiler.frame_stats import summarize

KINDS = ("callback", "event", "entity", "engine")


def _label(kind_key):
    kind, key = kind_key
    return "[%s] %s" % (kind, describe(key))


def _gc_frames_summary(frame_ms):
    if not frame_ms:
        return {"frames": 0}
    ordered = sorted(frame_ms)
    return {
        "frames": len(ordered),
        "medianMs": ordered[len(ordered) // 2],
        "maxMs": ordered[-1],
    }


def _python_rows(stats, column, frame_count, top_n):
    rows = sorted(stats.items(), key=lambda item: item[1][column], reverse=True)
    return [
        {
            "function": _label(kind_key),
            "calls": calls,
            "totalMs": total * 1000.0,
            "selfMs": own * 1000.0,
            "maxMs": worst * 1000.0,
            "selfMsPerFrame": own * 1000.0 / frame_count if frame_count else 0.0,
        }
        for kind_key, (calls, total, own, worst) in rows[:top_n]
    ]


def _python(session, frame_total_ms, top_n):
    tracer = session.tracer
    frame_count = len(session.frames)
    result = {
        "msPerFrame": session.python_ms_total / frame_count if frame_count else 0.0,
        "shareOfFrameTime": session.python_ms_total / frame_total_ms if frame_total_ms else 0.0,
        "selfMsPerFrameByKind": {},
        "topSelf": [],
        "topTotal": [],
    }
    if tracer is None or not frame_count:
        return result
    by_kind = dict((kind, 0.0) for kind in KINDS)
    for (kind, _), entry in tracer.stats.items():
        by_kind[kind] = by_kind.get(kind, 0.0) + entry[2] * 1000.0 / frame_count
    result["selfMsPerFrameByKind"] = by_kind
    result["topSelf"] = _python_rows(tracer.stats, 2, frame_count, top_n)
    result["topTotal"] = _python_rows(tracer.stats, 1, frame_count, top_n)
    return result


def _spikes(session):
    spikes = sorted(session.spikes, key=lambda spike: spike["second"])
    return {
        "thresholdMs": session.spike_ms,
        "count": session.spike_count,
        "recorded": [
            dict(spike, calls=[{"function": _label(key), "ms": ms} for key, ms in spike["calls"]])
            for spike in spikes
        ],
    }


def _top_samples(counts, total, top_n):
    rows = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [
        {"function": describe(key), "samples": count, "percent": 100.0 * count / total}
        for key, count in rows[:top_n]
    ]


def _sampler(sampler, top_n):
    if sampler is None:
        return None
    in_python = sampler.samples - sampler.outside_python
    return {
        "intervalMs": sampler.interval * 1000.0,
        "requestedSamples": sampler.requested_samples(),
        "samples": sampler.samples,
        "outsidePython": sampler.outside_python,
        "topSelf": _top_samples(sampler.self_counts(), in_python, top_n) if in_python else [],
        "topInclusive": _top_samples(sampler.inclusive_counts(), in_python, top_n) if in_python else [],
    }


def _timeline(session):
    rows = []
    for second in sorted(session.timeline):
        bucket = session.timeline[second]
        row = dict(bucket)
        row["second"] = second
        row["avgMs"] = bucket["totalMs"] / bucket["frames"]
        del row["totalMs"]
        rows.append(row)
    return rows


def build(session, meta, gc_measured, top_n):
    frame_total_ms = sum(session.frames)
    collections = session.gc_watch.collections if session.gc_watch else None
    return {
        "meta": meta,
        "frames": summarize(session.frames),
        "excludedFrames": session.excluded,
        "python": _python(session, frame_total_ms, top_n),
        "spikes": _spikes(session),
        "gc": {
            "collectionsDuringRun": collections,
            "gen1Frames": _gc_frames_summary(session.gc_frames[1]),
            "gen2Frames": _gc_frames_summary(session.gc_frames[2]),
            "measuredAtEnd": gc_measured,
        },
        "sampler": _sampler(session.sampler, top_n),
        "timeline": _timeline(session),
    }


def folded_stacks(sampler):
    lines = []
    for stack, count in sorted(sampler.stacks.items(), key=lambda item: -item[1]):
        names = [describe(key) for key in reversed(stack)]
        lines.append("%s %d" % (";".join(name.replace(";", ",") for name in names), count))
    return lines


def _fmt(value, digits=2):
    return ("%." + str(digits) + "f") % value


def _frame_lines(report):
    frames = report["frames"]
    lines = [
        "  %d frames over %ss: avg %s fps, 1%% low %s fps, 0.1%% low %s fps"
        % (frames["frames"], _fmt(frames["seconds"], 0), _fmt(frames["avgFps"], 1),
           _fmt(frames["onePercentLowFps"], 1), _fmt(frames["pointOnePercentLowFps"], 1)),
        "  frame ms: p50 %s, p99 %s, max %s, spikes >2x median: %d"
        % (_fmt(frames["p50Ms"]), _fmt(frames["p99Ms"]), _fmt(frames["maxMs"]),
           frames["spikesOver2xMedian"]),
    ]
    if report["excludedFrames"]:
        lines.append("  excluded frames: %s" % ", ".join(
            "%s %d" % item for item in sorted(report["excludedFrames"].items())))
    return lines


def _python_lines(report):
    python = report["python"]
    lines = ["  traced Python: %s ms/frame (%s%% of frame time)"
             % (_fmt(python["msPerFrame"], 3), _fmt(100.0 * python["shareOfFrameTime"], 1))]
    by_kind = python["selfMsPerFrameByKind"]
    if by_kind:
        lines.append("    by entry point: " + ", ".join(
            "%s %s" % (kind, _fmt(by_kind.get(kind, 0.0), 3)) for kind in KINDS))
    for row in python["topSelf"][:8]:
        lines.append("    %s ms/frame self  %s" % (_fmt(row["selfMsPerFrame"], 3), row["function"]))
    return lines


def _spike_lines(report):
    spikes = report["spikes"]
    lines = ["  frames over %s ms: %d" % (_fmt(spikes["thresholdMs"], 0), spikes["count"])]
    worst = sorted(spikes["recorded"], key=lambda spike: -spike["frameMs"])[:10]
    for spike in sorted(worst, key=lambda spike: spike["second"]):
        top = spike["calls"][0] if spike["calls"] else None
        lines.append(
            "    clock %s (+%ds): %s ms, Python %s ms%s%s"
            % (spike["battleClock"] or "?", spike["second"], _fmt(spike["frameMs"], 1),
               _fmt(spike["pythonMs"], 1),
               ", GC gen%d" % spike["gcGeneration"] if spike["gcGeneration"] >= 0 else "",
               "; slowest %s ms %s" % (_fmt(top["ms"], 1), top["function"]) if top else ""))
    return lines


def _gc_lines(report):
    gc = report["gc"]
    lines = []
    if gc["collectionsDuringRun"] is not None:
        lines.append("  GC collections gen0/gen1/gen2: %d/%d/%d" % tuple(gc["collectionsDuringRun"]))
    measured = gc["measuredAtEnd"]
    if measured:
        lines.append(
            "  GC at end (%s): %d tracked objects, gen0 %s ms, gen1 %s ms, gen2 %s ms"
            % ("enabled" if measured["enabled"] else "disabled by the game",
               measured["trackedObjects"], _fmt(measured["gen0Ms"]),
               _fmt(measured["gen1Ms"]), _fmt(measured["gen2Ms"])))
    return lines


def _sampler_lines(report):
    sampler = report["sampler"]
    if not sampler:
        return []
    lines = ["  sampler: %d of %d requested samples, %d outside Python"
             % (sampler["samples"], sampler["requestedSamples"], sampler["outsidePython"])]
    for row in sampler["topInclusive"][:5]:
        lines.append("    %s%%  %s" % (_fmt(row["percent"], 1), row["function"]))
    return lines


def summary_lines(report):
    lines = ["CPU Profiler: %s" % report["meta"].get("map", "?")]
    if not report["frames"].get("frames"):
        lines.append("  no realtime frames recorded")
        return lines
    for section in (_frame_lines, _python_lines, _spike_lines, _gc_lines, _sampler_lines):
        lines.extend(section(report))
    return lines


def write(report, folded, directory, basename):
    if not os.path.isdir(directory):
        os.makedirs(directory)
    base = os.path.join(directory, basename)
    with open(base + ".json", "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    with open(base + ".txt", "w") as handle:
        handle.write("\n".join(summary_lines(report)) + "\n")
    if folded:
        with open(base + ".folded", "w") as handle:
            handle.write("\n".join(folded) + "\n")
    return base
