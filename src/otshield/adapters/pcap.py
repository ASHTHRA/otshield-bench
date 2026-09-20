from .base import TelemetryAdapter

class PcapTelemetryAdapter(TelemetryAdapter):
    """Placeholder for future Modbus/TCP PCAP ingestion."""
    def load(self, path):
        raise NotImplementedError("PCAP ingestion not yet implemented")
