"""Detectors receive feature vectors only; labels never enter the model."""
from dataclasses import dataclass
import math
from sklearn.ensemble import IsolationForest
from .core import Event


@dataclass(frozen=True)
class Detection:
    event_id: str
    alert: bool
    score: float
    detector: str
    schema: str = "OTB-DETECT/0.1"

    def __post_init__(self):
        if not self.event_id or not self.detector or type(self.alert) is not bool:
            raise ValueError("invalid detection")
        if not math.isfinite(self.score) or self.schema != "OTB-DETECT/0.1":
            raise ValueError("invalid detection score or schema")


def features(event: Event) -> list[float]:
    return [event.function_code, event.address, event.value, event.interval_ms, event.latency_ms]


class RuleDetector:
    name = "rules-v1"

    def predict(self, events: list[Event]) -> list[Detection]:
        result = []
        for event in events:
            alert = (event.function_code != 3 or event.address > 9 or
                     not 40 <= event.value <= 60 or event.interval_ms < 50)
            result.append(Detection(event.event_id, alert, float(alert), self.name))
        return result


class IsolationForestDetector:
    name = "isolation-forest-v1"

    def __init__(self, seed: int = 42):
        self.model = IsolationForest(n_estimators=100, contamination="auto", random_state=seed, n_jobs=1)
        self.fitted = False

    def fit(self, normal_events: list[Event]):
        if len(normal_events) < 10 or any(event.label for event in normal_events):
            raise ValueError("fit requires at least 10 known-normal events")
        self.model.fit([features(event) for event in normal_events])
        self.fitted = True
        return self

    def predict(self, events: list[Event]) -> list[Detection]:
        if not self.fitted:
            raise ValueError("detector must be fitted before prediction")
        if not events:
            return []
        scores = -self.model.decision_function([features(event) for event in events])
        return [Detection(event.event_id, bool(score > 0), float(score), self.name)
                for event, score in zip(events, scores)]
