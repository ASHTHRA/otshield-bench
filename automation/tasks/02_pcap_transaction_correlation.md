Add an offline, defensive Modbus/TCP PCAP ingestion path with request/response transaction correlation.

Constraints:
- Local capture files only.
- Correlate using defensible fields such as connection tuple and Modbus transaction identifier.
- Handle retransmission, duplicates, and unmatched requests/responses explicitly.
- Preserve timestamps and provenance.
- Use small generated/sanitized test fixtures only.
- If packet decoding needs an optional dependency, document it.
- No active scanning, exploitation, packet injection, or control commands.
