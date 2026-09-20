import pytest
from otshield.adapters import PcapTelemetryAdapter

def test_pcap_adapter_not_implemented(tmp_path):
    adapter = PcapTelemetryAdapter()
    with pytest.raises(NotImplementedError):
        adapter.load(tmp_path / "dummy.pcap")
