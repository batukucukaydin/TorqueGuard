"""Timed external input changes; plant state is never overwritten by events."""

from dataclasses import dataclass, asdict
import math


@dataclass(frozen=True)
class SignalEvent:
    time_s: float
    label: str = "Input change"
    throttle: float | None = None
    brake: float | None = None
    wet: bool | None = None
    restricted_sector: bool | None = None
    sector: int | None = None
    deployment_limit_kw: float | None = None
    grip: float | None = None
    clutch_engaged: bool | None = None
    engine_available: bool | None = None

    def __post_init__(self):
        if isinstance(self.time_s, bool) or not isinstance(self.time_s, (int, float)) or not math.isfinite(self.time_s) or self.time_s < 0:
            raise ValueError("Event time_s must be a finite nonnegative number")
        if not isinstance(self.label, str) or not 1 <= len(self.label) <= 80:
            raise ValueError("Event label must contain 1–80 characters")
        for field in ("wet", "restricted_sector", "clutch_engaged", "engine_available"):
            value = getattr(self, field)
            if value is not None and type(value) is not bool:
                raise ValueError(f"Event {field} must be boolean")
        for field, maximum in (("throttle", 1), ("brake", 1), ("grip", 1), ("deployment_limit_kw", 350)):
            value = getattr(self, field)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= maximum):
                raise ValueError(f"Event {field} must be a finite number between 0 and {maximum}")
        if self.sector is not None and (type(self.sector) is not int or not 0 <= self.sector <= 99):
            raise ValueError("Event sector must be an integer in [0, 99]")
        if not self.changes():
            raise ValueError("An event must change at least one external input")

    def changes(self):
        return {key: value for key, value in asdict(self).items()
                if key not in ("time_s", "label") and value is not None}

    def to_dict(self):
        return {"time_s": self.time_s, "label": self.label, **self.changes()}


@dataclass(frozen=True)
class Inputs:
    throttle: float
    brake: float
    wet: bool
    restricted_sector: bool
    sector: int
    deployment_limit_kw: float
    grip: float
    clutch_engaged: bool
    engine_available: bool


def normalize_events(events, duration_s, dt_s):
    if not isinstance(events, (tuple, list)) or len(events) > 32:
        raise ValueError("events must be a list of at most 32 input events")
    normalized = []
    previous = -1
    for raw in events:
        if isinstance(raw, SignalEvent):
            event = raw
        elif isinstance(raw, dict):
            event = SignalEvent(**raw)
        else:
            raise ValueError("Each event must be an object")
        tick = event.time_s / dt_s
        if not math.isclose(tick, round(tick), abs_tol=1e-8, rel_tol=0):
            raise ValueError(f"Event '{event.label}' must align to the {dt_s:.2f} s sample grid")
        if event.time_s <= previous or event.time_s >= duration_s:
            raise ValueError("Event times must be strictly increasing and earlier than duration_s")
        normalized.append(event)
        previous = event.time_s
    return tuple(normalized)


class InputSchedule:
    """Cached immutable patches; event changes persist over the base driver schedule."""
    def __init__(self, scenario):
        self.scenario = scenario
        self.patches = tuple((event.time_s, event.changes()) for event in scenario.events)

    def at(self, time_s):
        s = self.scenario
        values = {"throttle": s.throttle if time_s + 1e-9 >= s.hold_s else 0.0,
                  "brake": 0.8 if time_s < s.hold_s - 1e-9 or s.brake_overlap else 0.0,
                  "wet": s.wet, "restricted_sector": s.restricted_sector, "sector": s.sector,
                  "deployment_limit_kw": s.deployment_limit_kw, "grip": s.grip,
                  "clutch_engaged": s.clutch_engaged, "engine_available": s.engine_available}
        for event_time, patch in self.patches:
            if event_time > time_s + 1e-9:
                break
            values.update(patch)
        return Inputs(**values)
