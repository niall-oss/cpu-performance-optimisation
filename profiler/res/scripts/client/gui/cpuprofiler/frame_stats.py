def _percentile(ordered, fraction):
    index = int(round(fraction * (len(ordered) - 1)))
    return ordered[index]


def _low_fps(ordered, fraction):
    count = max(1, int(len(ordered) * fraction))
    slowest = ordered[-count:]
    return 1000.0 * len(slowest) / sum(slowest)


def summarize(frame_ms):
    if not frame_ms:
        return {"frames": 0}

    ordered = sorted(frame_ms)
    total = sum(ordered)
    median = _percentile(ordered, 0.5)
    return {
        "frames": len(ordered),
        "seconds": total / 1000.0,
        "avgFps": 1000.0 * len(ordered) / total,
        "avgMs": total / len(ordered),
        "p50Ms": median,
        "p95Ms": _percentile(ordered, 0.95),
        "p99Ms": _percentile(ordered, 0.99),
        "p999Ms": _percentile(ordered, 0.999),
        "maxMs": ordered[-1],
        "onePercentLowFps": _low_fps(ordered, 0.01),
        "pointOnePercentLowFps": _low_fps(ordered, 0.001),
        "spikesOver2xMedian": sum(1 for ms in ordered if ms > 2 * median),
    }
