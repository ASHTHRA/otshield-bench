#!/usr/bin/env bash
# OTShield Bench v0.3 - GRFICS/OpenPLC capture pipeline
#
# This script orchestrates the full capture pipeline:
#   1. Start the OpenPLC Docker container
#   2. Wait for it to be healthy
#   3. Poll the Modbus server and capture traffic
#   4. Convert to OTB-INGEST-SOURCE/0.1 JSON
#   5. Normalize with otshield ingest
#   6. Tear down the container
#
# Safety: Passive observation only. No attacks are launched.
#
# Usage:
#   ./scripts/run_grfics_capture.sh [--duration 10] [--output captures/]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCKER_DIR="$REPO_ROOT/docker"

DURATION="${OTSHIELD_CAPTURE_DURATION:-10}"
OUTPUT="${OTSHIELD_CAPTURE_OUTPUT:-$REPO_ROOT/captures/grfics_capture.json}"
POLL_INTERVAL="${OTSHIELD_POLL_INTERVAL:-0.1}"
SEED="${OTSHIELD_SEED:-42}"
HOST="${OTSHIELD_MODBUS_HOST:-127.0.0.1}"
PORT="${OTSHIELD_MODBUS_PORT:-502}"

echo "=== OTShield Bench v0.3 GRFICS Capture Pipeline ==="
echo "Duration: ${DURATION}s | Host: ${HOST}:${PORT} | Output: ${OUTPUT}"
echo ""

# Step 1: Start Docker containers
echo "[1/5] Starting OpenPLC container..."
cd "$DOCKER_DIR"
docker compose -f docker-compose.grfics.yml up -d openplc
echo "Waiting for OpenPLC to become healthy..."
TIMEOUT=120
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' otshield-openplc 2>/dev/null || echo "starting")
    if [ "$STATUS" = "healthy" ]; then
        echo "OpenPLC is healthy."
        break
    fi
    sleep 5
    ELAPSED=$((ELAPSED + 5))
    echo "  Waiting... (${ELAPSED}s/${TIMEOUT}s) status=${STATUS}"
done
if [ $ELAPSED -ge $TIMEOUT ]; then
    echo "ERROR: OpenPLC did not become healthy within ${TIMEOUT}s"
    docker compose -f docker-compose.grfics.yml down -v 2>/dev/null || true
    exit 1
fi

# Step 2: Capture traffic
echo ""
echo "[2/5] Capturing Modbus traffic for ${DURATION}s..."
cd "$REPO_ROOT"
python3 "$SCRIPT_DIR/capture_grfics.py" \
    --host "$HOST" \
    --port "$PORT" \
    --output "$OUTPUT" \
    --duration "$DURATION" \
    --poll-interval "$POLL_INTERVAL" \
    --seed "$SEED" \
    --evidence-type lab_capture

# Step 3: Normalize the capture
echo ""
echo "[3/5] Normalizing capture to OTB-INGEST/0.1..."
NORMALIZED="${OUTPUT%.json}_normalized.json"
python3 -m otshield.cli ingest "$OUTPUT" --output "$NORMALIZED"
echo "Normalized output: $NORMALIZED"

# Step 4: Display summary
echo ""
echo "[4/5] Capture summary:"
python3 -c "
import json
data = json.loads(open('$OUTPUT').read())
print(f\"  Records: {len(data['records'])}\")
print(f\"  Provenance source: {data['provenance']['source']}\")
print(f\"  Evidence type: {data['provenance']['evidence_type']}\")
print(f\"  Dataset ID: {data['provenance']['dataset_id']}\")
meta = data['provenance'].get('metadata', {})
if meta:
    print(f\"  Capture tool: {meta.get('capture_tool', 'unknown')}\")
    print(f\"  OpenPLC host: {meta.get('openplc_host', 'unknown')}:{meta.get('openplc_port', '?')}\")
    print(f\"  Duration: {meta.get('capture_duration_s', '?')}s\")
    print(f\"  Seed: {meta.get('seed', '?')}\")
"

# Step 5: Cleanup
echo ""
echo "[5/5] Tearing down Docker containers..."
cd "$DOCKER_DIR"
docker compose -f docker-compose.grfics.yml down -v 2>/dev/null || true

echo ""
echo "=== Capture pipeline complete ==="
echo "OTB-INGEST-SOURCE JSON: $OUTPUT"
echo "OTB-INGEST/0.1 JSON:    $NORMALIZED"
echo ""
echo "To run detector on captured data, use:"
echo "  otshield ingest $NORMALIZED --output results/detected.json"
