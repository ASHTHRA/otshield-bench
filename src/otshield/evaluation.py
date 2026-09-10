"""Identity-aligned metrics with explicit observation coverage."""
from .core import Event
from .detectors import Detection


def evaluate(truth: list[Event], observed: list[Event], detections: list[Detection]) -> dict:
    source = {e.event_id: e for e in truth}
    seen = {e.event_id: e for e in observed}
    predicted = {d.event_id: d for d in detections}
    if len(source) != len(truth) or len(seen) != len(observed) or len(predicted) != len(detections):
        raise ValueError("duplicate event IDs")
    if not seen.keys() <= source.keys() or seen.keys() != predicted.keys():
        raise ValueError("observation and prediction IDs must align with truth")
    tp = sum(source[k].label and d.alert for k, d in predicted.items())
    fp = sum(not source[k].label and d.alert for k, d in predicted.items())
    fn = sum(source[k].label and not d.alert for k, d in predicted.items())
    tn = len(predicted) - tp - fp - fn
    positives = sum(e.label for e in truth)
    ratio = lambda a, b: a / b if b else 0.0
    return {"schema": "OTB-EVAL/0.1", "total": len(truth), "observed": len(observed),
            "dropped": len(truth) - len(observed), "coverage": ratio(len(observed), len(truth)),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": ratio(tp, tp + fp),
            "recall": ratio(tp, tp + fn), "f1": ratio(2 * tp, 2 * tp + fp + fn),
            "false_positive_rate": ratio(fp, fp + tn),
            "end_to_end_recall": ratio(tp, positives)}
