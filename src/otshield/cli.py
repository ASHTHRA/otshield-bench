"""Run reproducible benchmarks and export their evidence as JSON."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import platform
import sklearn
from . import __version__
from .core import SCENARIOS, faults, generate
from .detectors import IsolationForestDetector, RuleDetector
from .evaluation import evaluate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=(*SCENARIOS, "all"), default="all")
    parser.add_argument("--detector", choices=("rules", "iforest"), default="rules")
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--loss", type=float, default=0)
    parser.add_argument("--latency-ms", type=float, default=0)
    parser.add_argument("--jitter-ms", type=float, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        detector = RuleDetector() if args.detector == "rules" else IsolationForestDetector(args.seed).fit(
            generate("normal", max(200, args.count), args.seed + 1))
        results = []
        for name in SCENARIOS if args.scenario == "all" else [args.scenario]:
            truth = generate(name, args.count, args.seed)
            observed = faults(truth, args.loss, args.latency_ms, args.jitter_ms, args.seed + 2)
            predictions = detector.predict(observed)
            results.append({"scenario": name, "metrics": evaluate(truth, observed, predictions),
                            "truth": [e.to_dict() for e in truth],
                            "observations": [e.to_dict() for e in observed],
                            "detections": [asdict(d) for d in predictions]})
    except ValueError as exc:
        parser.error(str(exc))
    report = {"version": __version__, "python": platform.python_version(),
              "scikit_learn": sklearn.__version__, "detector": detector.name,
              "seed": args.seed, "count": args.count,
              "faults": {"loss": args.loss, "latency_ms": args.latency_ms, "jitter_ms": args.jitter_ms},
              "results": results}
    content = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
