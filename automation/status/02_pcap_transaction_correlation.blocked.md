# Blocked: 02_pcap_transaction_correlation.md

Post-run semantic audit failed.

The current PcapTelemetryAdapter is only a placeholder that raises
NotImplementedError. The current test merely verifies that exception and
docs/pcap-ingestion.md is empty.

Task 02 is not complete until real offline Modbus/TCP PCAP ingestion and
request/response correlation are implemented, including transaction IDs,
connection tuples, duplicates/retransmissions, unmatched transactions,
timestamps, provenance, tests, and documentation.
