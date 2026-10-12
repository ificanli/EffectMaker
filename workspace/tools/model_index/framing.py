from __future__ import annotations


def frame_parameters(bounds: dict, view: str) -> dict:
    minimum, maximum = bounds["min"], bounds["max"]
    target = [(minimum[i] + maximum[i]) / 2.0 for i in range(3)]
    extents = [maximum[i] - minimum[i] for i in range(3)]
    size = sum(value * value for value in extents) ** 0.5
    directions = {"front": [0.0, -1.0, 0.0], "side": [1.0, 0.0, 0.0], "perspective": [1.0, -1.0, 0.75]}
    direction = directions[view]
    length = sum(value * value for value in direction) ** 0.5
    direction = [value / length for value in direction]
    return {"target": target, "direction": direction, "distance": max(size * 2.2, 1.0), "ortho_scale": max(size * 1.25, 1.0)}
