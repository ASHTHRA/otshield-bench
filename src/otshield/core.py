"""Versioned telemetry, scenario generation, and observation faults.

No sockets, packet construction, or device interaction are performed.
"""
from dataclasses import asdict, dataclass, replace
from importlib.resources import files
import json
import math
import random

SCENARIOS = ("normal", "unauthorized_write", "register_scan", "polling_burst", "value_spike")


@dataclass(frozen=True)
class Event:
    event_id: str
    timestamp_ms: float
    function_code: int
    address: int
    value: float
    interval_ms: float
    latency_ms: float
    label: bool
    schema: str = "OTB-TELEMETRY/0.1"

    def __post_init__(self):
        if not isinstance(self.event_id, str) or not self.event_id or self.schema != "OTB-TELEMETRY/0.1":
            raise ValueError("invalid telemetry identity or schema")
        if type(self.label) is not bool:
            raise ValueError("label must be boolean")
        for name in ("timestamp_ms", "value", "interval_ms", "latency_ms"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if min(self.timestamp_ms, self.interval_ms, self.latency_ms) < 0:
            raise ValueError("times must be nonnegative")
        if type(self.address) is not int or not 0 <= self.address <= 65535:
            raise ValueError("invalid register address")
        if type(self.function_code) is not int or not 1 <= self.function_code <= 127:
            raise ValueError("invalid function code")

    def to_dict(self):
        return asdict(self)


def generate(name: str, count: int = 200, seed: int = 42) -> list[Event]:
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario: {name}")
    if type(count) is not int or count < 10:
        raise ValueError("count must be an integer >= 10")
    config = json.loads(files("otshield").joinpath("scenarios", name + ".json").read_text())
    rng = random.Random(seed)
    events = []
    timestamp = 0.0
    for i in range(count):
        anomalous = name != "normal" and count // 2 <= i < 3 * count // 4
        interval = rng.uniform(95, 105)
        code, address, value = 3, rng.randrange(10), rng.uniform(45, 55)
        if anomalous:
            code = config.get("function_code", code)
            address = config.get("address", address)
            value = config.get("value", value)
            interval = config.get("interval_ms", interval)
        timestamp += interval
        events.append(Event(f"{name}:{seed}:{i}", timestamp, code, address, value,
                            interval, rng.uniform(1, 3), anomalous))
    return events


def faults(events: list[Event], loss: float = 0, latency_ms: float = 0,
           jitter_ms: float = 0, seed: int = 43) -> list[Event]:
    for value in (loss, latency_ms, jitter_ms):
        if not math.isfinite(value):
            raise ValueError("fault parameters must be finite")
    if not 0 <= loss <= 1 or min(latency_ms, jitter_ms) < 0:
        raise ValueError("loss must be in [0,1]; delays must be nonnegative")
    rng = random.Random(seed)
    observed = []
    for event in events:
        if rng.random() < loss:
            continue
        delay = latency_ms + rng.uniform(0, jitter_ms)
        observed.append(replace(event, timestamp_ms=event.timestamp_ms + delay,
                                latency_ms=event.latency_ms + delay))
    return sorted(observed, key=lambda event: (event.timestamp_ms, event.event_id))
