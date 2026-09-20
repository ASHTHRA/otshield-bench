"""Passive, deterministic Modbus/TCP ingestion from classic PCAP files."""

from pathlib import Path
import socket
import struct

from ..core import Event
from .model import IngestedDataset, IngestedEvent, ObservationContext, Provenance


class PcapTelemetryAdapter:
    """Load Ethernet/IPv4/TCP/Modbus-TCP packets from an offline PCAP."""

    def load(self, path: Path) -> IngestedDataset:
        path = Path(path)
        raw = path.read_bytes()

        if len(raw) < 24:
            raise ValueError("invalid PCAP: missing global header")

        magic = raw[:4]
        if magic == b"\xd4\xc3\xb2\xa1":
            endian, divisor = "<", 1000.0
        elif magic == b"\xa1\xb2\xc3\xd4":
            endian, divisor = ">", 1000.0
        elif magic == b"\x4d\x3c\xb2\xa1":
            endian, divisor = "<", 1_000_000.0
        elif magic == b"\xa1\xb2\x3c\x4d":
            endian, divisor = ">", 1_000_000.0
        else:
            raise ValueError("unsupported PCAP magic")

        _, _, _, _, _, network = struct.unpack(
            endian + "HHiIII", raw[4:24]
        )
        if network != 1:
            raise ValueError("only Ethernet classic PCAP is supported")

        transactions = {}
        order = []
        seen_packets = set()

        offset = 24
        while offset + 16 <= len(raw):
            ts_sec, ts_frac, incl_len, _ = struct.unpack(
                endian + "IIII", raw[offset:offset + 16]
            )
            offset += 16

            if offset + incl_len > len(raw):
                raise ValueError("truncated PCAP packet")

            packet = raw[offset:offset + incl_len]
            offset += incl_len

            timestamp_ms = ts_sec * 1000.0 + ts_frac / divisor
            parsed = self._parse_packet(packet)

            if parsed is None:
                continue

            parsed["timestamp_ms"] = timestamp_ms

            connection = tuple(sorted((
                (parsed["src_ip"], parsed["src_port"]),
                (parsed["dst_ip"], parsed["dst_port"]),
            )))
            key = (connection, parsed["transaction_id"])

            if key not in transactions:
                transactions[key] = {
                    "request": None,
                    "response": None,
                    "duplicate_count": 0,
                }
                order.append(key)

            tx = transactions[key]

            fingerprint = (
                parsed["src_ip"],
                parsed["src_port"],
                parsed["dst_ip"],
                parsed["dst_port"],
                parsed["sequence"],
                parsed["payload"],
            )

            if fingerprint in seen_packets:
                tx["duplicate_count"] += 1
                continue

            seen_packets.add(fingerprint)

            direction = parsed["direction"]
            if tx[direction] is not None:
                # Same transaction ID and same direction before completion:
                # conservatively classify it as duplicate/retransmitted traffic.
                tx["duplicate_count"] += 1
                continue

            tx[direction] = parsed

        records = []

        for index, key in enumerate(order, start=1):
            tx = transactions[key]
            request = tx["request"]
            response = tx["response"]

            if request is not None and response is not None:
                primary = request
                status = "matched"
                latency_ms = max(
                    0.0,
                    response["timestamp_ms"] - request["timestamp_ms"],
                )
            elif request is not None:
                primary = request
                status = "unmatched_request"
                latency_ms = 0.0
            else:
                primary = response
                status = "unmatched_response"
                latency_ms = 0.0

            if primary is None:
                continue

            function_code, address, value = self._event_values(primary)

            event = Event(
                event_id=f"pcap:{index:04d}",
                timestamp_ms=primary["timestamp_ms"],
                function_code=function_code,
                address=address,
                value=value,
                interval_ms=0.0,
                latency_ms=latency_ms,
                label=False,
            )

            metadata = {
                "transaction_id": primary["transaction_id"],
                "protocol_id": primary["protocol_id"],
                "unit_id": primary["unit_id"],
                "status": status,
                "duplicate_count": tx["duplicate_count"],
                "request_timestamp_ms": (
                    request["timestamp_ms"] if request else None
                ),
                "response_timestamp_ms": (
                    response["timestamp_ms"] if response else None
                ),
                "request_pdu": request["pdu"].hex() if request else None,
                "response_pdu": response["pdu"].hex() if response else None,
            }

            records.append(
                IngestedEvent(
                    telemetry=event,
                    context=ObservationContext(
                        source_endpoint=(
                            f'{primary["src_ip"]}:{primary["src_port"]}'
                        ),
                        destination_endpoint=(
                            f'{primary["dst_ip"]}:{primary["dst_port"]}'
                        ),
                        protocol="modbus-tcp",
                        operation=status,
                        target_type="register",
                        value_metadata=metadata,
                    ),
                )
            )

        if not records:
            raise ValueError("no supported Modbus/TCP traffic found in PCAP")

        return IngestedDataset(
            provenance=Provenance(
                source="other",
                dataset_id=path.name,
                evidence_type="sanitized_fixture",
            ),
            records=tuple(records),
        )

    @staticmethod
    def _parse_packet(packet: bytes):
        if len(packet) < 14:
            return None

        if struct.unpack("!H", packet[12:14])[0] != 0x0800:
            return None

        ip_start = 14
        if len(packet) < ip_start + 20:
            return None

        version_ihl = packet[ip_start]
        if version_ihl >> 4 != 4:
            return None

        ihl = (version_ihl & 0x0F) * 4
        if ihl < 20 or len(packet) < ip_start + ihl:
            return None

        if packet[ip_start + 9] != 6:
            return None

        total_length = struct.unpack(
            "!H", packet[ip_start + 2:ip_start + 4]
        )[0]
        ip_end = min(len(packet), ip_start + total_length)

        src_ip = socket.inet_ntoa(packet[ip_start + 12:ip_start + 16])
        dst_ip = socket.inet_ntoa(packet[ip_start + 16:ip_start + 20])

        tcp_start = ip_start + ihl
        if ip_end < tcp_start + 20:
            return None

        src_port, dst_port = struct.unpack(
            "!HH", packet[tcp_start:tcp_start + 4]
        )

        if src_port != 502 and dst_port != 502:
            return None

        sequence = struct.unpack(
            "!I", packet[tcp_start + 4:tcp_start + 8]
        )[0]

        tcp_header_len = (packet[tcp_start + 12] >> 4) * 4
        if tcp_header_len < 20:
            return None

        payload_start = tcp_start + tcp_header_len
        if payload_start > ip_end:
            return None

        payload = packet[payload_start:ip_end]
        if len(payload) < 8:
            return None

        transaction_id, protocol_id, length, unit_id = struct.unpack(
            "!HHHB", payload[:7]
        )

        if protocol_id != 0:
            return None

        adu_length = 6 + length
        if length < 2 or adu_length > len(payload):
            return None

        pdu = payload[7:adu_length]
        if not pdu:
            return None

        return {
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "src_port": src_port,
            "dst_port": dst_port,
            "sequence": sequence,
            "transaction_id": transaction_id,
            "protocol_id": protocol_id,
            "unit_id": unit_id,
            "pdu": pdu,
            "payload": payload[:adu_length],
            "direction": "request" if dst_port == 502 else "response",
        }

    @staticmethod
    def _event_values(packet):
        pdu = packet["pdu"]
        function_code = pdu[0] & 0x7F

        address = 0
        value = 0.0

        # Requests and write responses normally contain address + value/quantity.
        if len(pdu) >= 5:
            address = struct.unpack("!H", pdu[1:3])[0]
            value = float(struct.unpack("!H", pdu[3:5])[0])

        # A read response instead contains byte-count followed by register data.
        elif len(pdu) >= 4 and pdu[0] in (1, 2, 3, 4):
            value = float(struct.unpack("!H", pdu[2:4])[0])

        return function_code, address, value
