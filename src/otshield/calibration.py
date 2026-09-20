"""Predeclared robust timing calibration for OTShield experiments."""

from dataclasses import asdict, dataclass
import math
import statistics


@dataclass(frozen=True)
class RobustIntervalCalibration:
    sample_count: int
    median_ms: float
    mad_ms: float
    robust_sigma_ms: float
    multiplier: float
    scale_factor: float
    threshold_ms: float

    def to_dict(self):
        return asdict(self)


def calibrate_robust_interval_threshold(
    intervals,
    *,
    multiplier: float = 3.5,
    scale_factor: float = 1.4826,
    min_samples: int = 30,
):
    if multiplier != 3.5 or scale_factor != 1.4826 or min_samples != 30:
        raise ValueError("the preregistered calibration formula is fixed")
    values = []

    for value in intervals:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(
                "calibration intervals must be finite and positive"
            )

        values.append(float(value))

    if len(values) < min_samples:
        raise ValueError(
            f"calibration requires at least {min_samples} intervals"
        )

    median_ms = statistics.median(values)

    deviations = [
        abs(value - median_ms)
        for value in values
    ]

    mad_ms = statistics.median(deviations)

    if not math.isfinite(mad_ms) or mad_ms <= 0:
        raise ValueError(
            "calibration MAD must be finite and positive"
        )

    robust_sigma_ms = scale_factor * mad_ms

    threshold_ms = (
        median_ms
        - multiplier * robust_sigma_ms
    )

    if (
        not math.isfinite(threshold_ms)
        or threshold_ms <= 0
    ):
        raise ValueError(
            "calibrated threshold must be finite and positive"
        )

    return RobustIntervalCalibration(
        sample_count=len(values),
        median_ms=median_ms,
        mad_ms=mad_ms,
        robust_sigma_ms=robust_sigma_ms,
        multiplier=float(multiplier),
        scale_factor=float(scale_factor),
        threshold_ms=threshold_ms,
    )
