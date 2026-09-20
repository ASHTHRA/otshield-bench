"""Synthetic reconnect/stale-response regressions, not experimental evidence."""
import copy
import json

import pytest

from otshield.adapters import PcapTelemetryAdapter
from otshield.canonical_v06 import canonicalize_capture
from otshield.lab_resilience import evaluate_resilience_capture
from otshield.paired_v06 import DETECTORS, evaluate_paired_capture, write_paired_capture
from otshield.study_v06 import finalize, write_json
from test_pcap import _pcap, _ethernet_ipv4_tcp, _modbus_request, _modbus_response
from test_v06_study import make_run, seal, CALIBRATION


def reconnect(tmp_path):
    packets = []
    def packet(t, port, payload, response=False):
        src, dst = ('10.0.0.2', '10.0.0.1') if response else ('10.0.0.1', '10.0.0.2')
        packets.append((1 + t // 1000000, t % 1000000, _ethernet_ipv4_tcp(
            src, dst, 502 if response else port, port if response else 502, t, payload)))
    for tid in range(1, 61):
        if tid == 17:
            packet(tid * 10000 - 100, 42384, _modbus_response(60), True)
        packet(tid * 10000, 47088, _modbus_request(tid, (tid - 1) % 10))
        packet(tid * 10000 + 100, 47088, _modbus_response(tid), True)
    path = tmp_path / 'synthetic.pcap'
    path.write_bytes(_pcap(packets))
    return PcapTelemetryAdapter(dataset_id='synthetic-test-1-clean', evidence_type='lab_capture').load(path).to_dict()


def test_reconnect_same_canonical_observations_and_audit(tmp_path):
    normalized = reconnect(tmp_path)
    before = copy.deepcopy(normalized)
    canonical, audit = canonicalize_capture(normalized)
    assert len(normalized['records']) == 61
    assert len(canonical['records']) == 60
    assert audit['decisions'][0]['excluded_record']['telemetry']['event_id'] == 'pcap:0017'
    assert canonical['records'][-1]['telemetry']['interval_ms'] == 10
    root = make_run(tmp_path / 'study')
    protocol = json.loads((root / 'protocol.json').read_text())
    paired = evaluate_paired_capture(normalized, protocol, CALIBRATION)
    a, b = [paired[name] for name in DETECTORS]
    assert [{k: v for k, v in r.items() if k != 'alert'} for r in a[1]] == [
        {k: v for k, v in r.items() if k != 'alert'} for r in b[1]]
    assert a[0].environment['canonicalization'] == b[0].environment['canonicalization'] == audit
    assert normalized == before
    with pytest.raises(ValueError, match='duplicate transaction 60'):
        evaluate_resilience_capture(normalized, protocol)
    # Real file-writing and study validation use the same canonical view.
    write_json(root / 'normalized.json', normalized)
    from otshield.study_v06 import digest
    normalization = json.loads((root / 'normalization.json').read_text())
    normalization.update(output_sha256=digest(root / 'normalized.json'), record_count=61)
    write_json(root / 'normalization.json', normalization)
    write_paired_capture(root / 'normalized.json', root / 'protocol.json', CALIBRATION, root)
    seal(root)
    assert finalize(root.parents[1], 'synthetic')['completed_condition_runs'] == 1
    for name in DETECTORS:
        path = root / f'{name}.observations.json'
        data = json.loads(path.read_text())
        data['canonicalization']['decisions'] = []
        write_json(path, data)
    seal(root)
    assert finalize(root.parents[1], 'synthetic')['completed_condition_runs'] == 0


@pytest.mark.parametrize('case', ['matched', 'request', 'same_connection', 'late', 'missing_endpoint',
                                  'missing_timestamp', 'nan', 'unit', 'foreign_request', 'third'])
def test_ambiguous_duplicates_fail_closed(tmp_path, case):
    data = reconnect(tmp_path)
    orphan, matched = data['records'][16], data['records'][-1]
    meta = orphan['context']['value_metadata']
    if case == 'matched': orphan.update(copy.deepcopy(matched))
    if case == 'request': meta['status'] = 'unmatched_request'
    if case == 'same_connection': orphan['context']['destination_endpoint'] = matched['context']['source_endpoint']
    if case == 'late': meta['response_timestamp_ms'] = 99999
    if case == 'missing_endpoint': del orphan['context']['source_endpoint']
    if case == 'missing_timestamp': del meta['response_timestamp_ms']
    if case == 'nan': meta['response_timestamp_ms'] = float('nan')
    if case == 'unit': meta['unit_id'] = 2
    if case == 'foreign_request': data['records'][0]['context']['source_endpoint'] = '10.0.0.1:42384'
    if case == 'third': data['records'].append(copy.deepcopy(orphan))
    with pytest.raises(ValueError, match='ambiguous duplicate'):
        canonicalize_capture(data)


def test_order_and_labels_do_not_choose_record(tmp_path):
    data = reconnect(tmp_path)
    expected, _ = canonicalize_capture(data)
    data['records'].reverse()
    for record in data['records']:
        record['telemetry']['label'] = True
    actual, audit = canonicalize_capture(data)
    assert [r['telemetry']['event_id'] for r in actual['records']] == [
        r['telemetry']['event_id'] for r in reversed(expected['records'])]
    assert audit['decisions'][0]['retained_record']['telemetry']['event_id'] == 'pcap:0061'
