"""Conservative v0.6 lab correlation; generic ingestion remains lossless."""
import math

from .lab_resilience import _hash

RULE = "v06-earlier-foreign-response-only-v1"


def canonicalize_capture(normalized):
    """Resolve only an orphan from a different, request-free TCP connection.

    No protocol labels, planned timings, or detector results are inputs. Keep
    original records and intervals intact; return a separate evaluation view.
    """
    records = normalized["records"]
    groups = {}
    request_connections = set()

    def connection(record):
        context = record["context"]
        source, destination = context.get("source_endpoint"), context.get("destination_endpoint")
        if not isinstance(source, str) or not isinstance(destination, str):
            return None
        return tuple(sorted((source, destination)))

    for index, record in enumerate(records):
        meta = record["context"]["value_metadata"]
        tid = meta["transaction_id"]
        if type(tid) is not int:
            raise ValueError("invalid transaction ID")
        groups.setdefault(tid, []).append(index)
        if meta["status"] in ("matched", "unmatched_request"):
            request_connections.add(connection(record))
    excluded, decisions = set(), []
    for tid, indices in groups.items():
        if len(indices) == 1:
            continue
        error = ValueError(f"ambiguous duplicate transaction {tid} in normalized dataset")
        if len(indices) != 2:
            raise error
        matched = [i for i in indices if records[i]["context"]["value_metadata"]["status"] == "matched"]
        if len(matched) != 1:
            raise error
        keep = matched[0]
        discard = next(i for i in indices if i != keep)
        retained, orphan = records[keep], records[discard]
        m, o = (r["context"]["value_metadata"] for r in (retained, orphan))
        active, foreign = connection(retained), connection(orphan)
        rc, oc = retained["context"], orphan["context"]
        times = (o.get("response_timestamp_ms"), m.get("request_timestamp_ms"), m.get("response_timestamp_ms"))
        if (active is None or foreign is None or request_connections != {active} or foreign == active
                or o.get("status") != "unmatched_response"
                or o.get("request_timestamp_ms") is not None or o.get("request_pdu") is not None
                or not m.get("request_pdu") or not m.get("response_pdu") or not o.get("response_pdu")
                or any(type(t) not in (int, float) or not math.isfinite(t) for t in times)
                or not times[0] < times[1] <= times[2]
                or rc.get("protocol") != "modbus-tcp" or oc.get("protocol") != "modbus-tcp"
                or oc["source_endpoint"] != rc["destination_endpoint"]
                or not rc["destination_endpoint"].endswith(":502")
                or oc["destination_endpoint"].rsplit(":", 1)[0] != rc["source_endpoint"].rsplit(":", 1)[0]
                or m.get("protocol_id") != 0 or o.get("protocol_id") != 0
                or type(m.get("unit_id")) is not int or m["unit_id"] != o.get("unit_id")):
            raise error
        excluded.add(discard)
        decisions.append({"transaction_id": tid, "retained_record_index": keep,
                          "excluded_record_index": discard,
                          "retained_record": retained, "excluded_record": orphan})
    canonical = {**normalized, "records": [r for i, r in enumerate(records) if i not in excluded]}
    audit = {"rule": RULE, "input_record_count": len(records),
             "canonical_record_count": len(canonical["records"]),
             "canonical_capture_sha256": _hash(canonical), "decisions": decisions}
    return canonical, audit
