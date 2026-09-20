Add a real offline, defensive Modbus/TCP PCAP ingestion path with request/response transaction correlation.

Required behavior:
- Local capture files only.
- PcapTelemetryAdapter.load(path) must actually parse a small offline PCAP and return normalized ingestion data.
- Do NOT leave Placeholder, NotImplementedError, TODO-only behavior, or a stub implementation.
- Correlate requests and responses using the TCP connection tuple plus Modbus transaction identifier.
- Preserve packet/request/response timestamps and provenance.
- Explicitly represent or report matched transactions, retransmissions/duplicates, unmatched requests, and unmatched responses.
- Duplicate/retransmitted packets must not silently create false independent transactions.
- Use only passive parsing. No sockets, active scanning, exploitation, packet injection, or control commands.
- Tests must exercise a real generated/sanitized PCAP fixture, not merely mock load().
- Tests must cover:
  1. one matched request/response;
  2. duplicate or retransmitted packet handling;
  3. unmatched request;
  4. unmatched response;
  5. deterministic repeated loading.
- Documentation must explain supported PCAP/Modbus behavior, provenance, limitations, and any optional packet-decoding dependency.
- Prefer a small deterministic implementation. Never claim real GRFICS/OpenPLC capture execution unless evidence exists.
