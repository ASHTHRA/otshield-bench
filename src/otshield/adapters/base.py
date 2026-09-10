"""Adapter interface for offline telemetry sources."""

from pathlib import Path
from typing import Protocol

from .model import IngestedDataset


class TelemetryAdapter(Protocol):
    """Normalize an offline input file into a versioned ingestion dataset."""

    def load(self, path: Path) -> IngestedDataset:
        """Load and validate *path* without contacting an external system."""
