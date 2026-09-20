import socket
import struct

from otshield.adapters import PcapTelemetryAdapter


def _modbus_request(tid=1, address=10, quantity=1):
    pdu = struct.pack("!BHH", 3, address, quantity)
    return struct.pack("!HHHB", tid, 0, 1 + len(pdu), 1) + pdu


def _modbus_response(tid=1, value=42):
    pdu = struct.pack("!BBH", 3, 2, value)
    return struct.pack("!HHHB", tid, 0, 1 + len(pdu), 1) + pdu


def _ethernet_ipv4_tcp(src_ip, dst_ip, src_port, dst_port, seq, payload):
    ethernet = (
        b"\x00\x11\x22\x33\x44\x55"
        + b"\x66\x77\x88\x99\xaa\xbb"
        + b"\x08\x00"
    )

    total_length = 20 + 20 + len(payload)

    ip = struct.pack(
        "!BBHHHBBH4s4s",
        0x45,
        0,
        total_length,
        1,
        0x4000,
        64,
        6,
        0,
        socket.inet_aton(src_ip),
        socket.inet_aton(dst_ip),
    )

    tcp = struct.pack(
        "!HHIIBBHHH",
        src_port,
        dst_port,
        seq,
        0,
        5 << 4,
        0x18,
        8192,
        0,
        0,
    )

    return ethernet + ip + tcp + payload


def _pcap(packets):
    data = struct.pack(
        "<IHHIIII",
        0xA1B2C3D4,
        2,
        4,
        0,
        0,
        65535,
        1,
    )

    for sec, usec, packet in packets:
        data += struct.pack(
            "<IIII",
            sec,
            usec,
            len(packet),
            len(packet),
        )
        data += packet

    return data


def _request_packet(tid=1, seq=100, address=10):
    return _ethernet_ipv4_tcp(
        "10.0.0.1",
        "10.0.0.2",
        12000,
        502,
        seq,
        _modbus_request(tid, address),
    )


def _response_packet(tid=1, seq=200, value=42):
    return _ethernet_ipv4_tcp(
        "10.0.0.2",
        "10.0.0.1",
        502,
        12000,
        seq,
        _modbus_response(tid, value),
    )


def test_pcap_adapter_parses_request_response(tmp_path):
    path = tmp_path / "matched.pcap"
    path.write_bytes(
        _pcap([
            (1, 100000, _request_packet()),
            (1, 150000, _response_packet()),
        ])
    )

    dataset = PcapTelemetryAdapter().load(path)

    assert dataset.provenance.evidence_type == "sanitized_fixture"
    assert len(dataset.records) == 1

    record = dataset.records[0]
    event = record.telemetry
    meta = record.context.value_metadata

    assert event.function_code == 3
    assert event.address == 10
    assert event.latency_ms == 50.0

    assert meta["transaction_id"] == 1
    assert meta["protocol_id"] == 0
    assert meta["unit_id"] == 1
    assert meta["status"] == "matched"
    assert meta["duplicate_count"] == 0
    assert meta["request_timestamp_ms"] == 1100.0
    assert meta["response_timestamp_ms"] == 1150.0


def test_duplicate_request_does_not_create_false_transaction(tmp_path):
    request = _request_packet()

    path = tmp_path / "duplicate.pcap"
    path.write_bytes(
        _pcap([
            (1, 0, request),
            (1, 10000, request),
            (1, 50000, _response_packet()),
        ])
    )

    dataset = PcapTelemetryAdapter().load(path)

    assert len(dataset.records) == 1
    meta = dataset.records[0].context.value_metadata
    assert meta["status"] == "matched"
    assert meta["duplicate_count"] == 1


def test_unmatched_request(tmp_path):
    path = tmp_path / "unmatched-request.pcap"
    path.write_bytes(_pcap([(2, 0, _request_packet(tid=7))]))

    dataset = PcapTelemetryAdapter().load(path)

    assert len(dataset.records) == 1
    meta = dataset.records[0].context.value_metadata
    assert meta["transaction_id"] == 7
    assert meta["status"] == "unmatched_request"
    assert meta["response_timestamp_ms"] is None


def test_unmatched_response(tmp_path):
    path = tmp_path / "unmatched-response.pcap"
    path.write_bytes(_pcap([(3, 0, _response_packet(tid=8))]))

    dataset = PcapTelemetryAdapter().load(path)

    assert len(dataset.records) == 1
    meta = dataset.records[0].context.value_metadata
    assert meta["transaction_id"] == 8
    assert meta["status"] == "unmatched_response"
    assert meta["request_timestamp_ms"] is None


def test_repeated_loading_is_deterministic(tmp_path):
    path = tmp_path / "deterministic.pcap"
    path.write_bytes(
        _pcap([
            (4, 100000, _request_packet(tid=11)),
            (4, 125000, _response_packet(tid=11)),
        ])
    )

    adapter = PcapTelemetryAdapter()

    first = adapter.load(path).to_dict()
    second = adapter.load(path).to_dict()

    assert first == second


def test_explicit_lab_capture_provenance(tmp_path):
    path = tmp_path / "real-lab.pcap"
    path.write_bytes(
        _pcap([
            (5, 100000, _request_packet(tid=21)),
            (5, 125000, _response_packet(tid=21)),
        ])
    )

    dataset = PcapTelemetryAdapter(
        source="grfics",
        dataset_id="openplc-lab-example",
        evidence_type="lab_capture",
    ).load(path)

    assert dataset.provenance.source == "grfics"
    assert dataset.provenance.dataset_id == "openplc-lab-example"
    assert dataset.provenance.evidence_type == "lab_capture"
