#!/usr/bin/env bash
set -Eeuo pipefail

TRIALS="${TRIALS:-5}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ROOT="$PWD/evidence/repeatability/$STAMP"
CAPTURE_DIR="$PWD/captures/repeatability-$STAMP"

COMPOSE_FILE="docker/docker-compose.grfics.yml"

mkdir -p "$ROOT"
mkdir -p "$CAPTURE_DIR"


cleanup_all() {
    docker rm -f \
      otshield-resilience-client \
      otshield-server-capture \
      >/dev/null 2>&1 || true

    docker compose \
      -f "$COMPOSE_FILE" \
      down -v \
      >/dev/null 2>&1 || true
}


trap cleanup_all EXIT


wait_for_openplc() {
    local ready=0

    for _ in $(seq 1 30); do

        status="$(
            docker inspect \
              --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}running{{end}}' \
              otshield-openplc \
              2>/dev/null \
              || echo missing
        )"

        echo "OpenPLC: $status"

        if [ "$status" = "healthy" ] ||
           [ "$status" = "running" ]; then
            ready=1
            break
        fi

        sleep 5
    done

    if [ "$ready" -ne 1 ]; then
        echo "OpenPLC failed to become ready."
        docker logs --tail 100 otshield-openplc || true
        return 1
    fi
}


write_protocol() {
    local dir="$1"
    local dataset="$2"
    local name="$3"
    local delay="$4"
    local jitter="$5"
    local loss="$6"
    local trial="$7"

    export \
      DIR="$dir" \
      DATASET_ID="$dataset" \
      NAME="$name" \
      DELAY="$delay" \
      JITTER="$jitter" \
      LOSS="$loss" \
      TRIAL="$trial"

    python - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["DIR"])

requests = []

for tid in range(1, 61):

    if tid == 1:
        interval = None
        phase = "normal-pre"
        anomaly = False

    elif 2 <= tid <= 20:
        interval = 100.0
        phase = "normal-pre"
        anomaly = False

    elif 21 <= tid <= 40:
        interval = 10.0
        phase = "controlled-burst"
        anomaly = True

    else:
        interval = 100.0
        phase = "normal-post"
        anomaly = False

    requests.append(
        {
            "transaction_id": tid,
            "phase": phase,
            "address": (tid - 1) % 10,
            "planned_interval_ms": interval,
            "expected_anomaly": anomaly,
        }
    )


document = {
    "schema":
        "OTB-LAB-RESILIENCE-PROTOCOL/0.1",

    "study":
        "OTB-REPEATABILITY/0.1",

    "trial":
        int(os.environ["TRIAL"]),

    "dataset_id":
        os.environ["DATASET_ID"],

    "protocol":
        "modbus-tcp",

    "traffic_policy":
        "read-only function-code-3",

    "condition": {
        "name":
            os.environ["NAME"],

        "delay_ms":
            float(os.environ["DELAY"]),

        "jitter_ms":
            float(os.environ["JITTER"]),

        "loss_percent":
            float(os.environ["LOSS"]),

        "threshold_ms":
            50.0,

        "impairment_direction":
            "client-egress",
    },

    "requests":
        requests,
}


(root / "protocol.json").write_text(
    json.dumps(
        document,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    + "\n"
)

print(
    "Predeclared:",
    os.environ["DATASET_ID"],
)

print(
    "Normal:",
    sum(
        not item["expected_anomaly"]
        for item in requests
    ),
)

print(
    "Anomaly:",
    sum(
        item["expected_anomaly"]
        for item in requests
    ),
)
PY
}


run_client() {
    local network="$1"
    local delay="$2"
    local jitter="$3"
    local loss="$4"

    docker rm -f \
      otshield-resilience-client \
      >/dev/null 2>&1 || true

    docker run --rm \
      --name otshield-resilience-client \
      --network "$network" \
      --cap-add NET_ADMIN \
      -e DELAY_MS="$delay" \
      -e JITTER_MS="$jitter" \
      -e LOSS_PERCENT="$loss" \
      alpine:3.20 \
      sh -lc '
        set -eu

        apk add --no-cache \
          python3 \
          iproute2 \
          >/dev/null

        if [ "$DELAY_MS" != "0" ] ||
           [ "$JITTER_MS" != "0" ] ||
           [ "$LOSS_PERCENT" != "0" ]; then

            tc qdisc replace \
              dev eth0 \
              root netem \
              delay "${DELAY_MS}ms" \
                    "${JITTER_MS}ms" \
              loss "${LOSS_PERCENT}%"

            echo "NETEM:"
            tc qdisc show dev eth0
        else
            echo "NETEM: clean"
        fi


        python3 - <<'"'"'PY'"'"'
import socket
import struct
import time


def recv_exact(sock, size):
    data = b""

    while len(data) < size:
        chunk = sock.recv(size - len(data))

        if not chunk:
            raise RuntimeError(
                "connection closed"
            )

        data += chunk

    return data


def connect():
    try:
        sock = socket.create_connection(
            ("openplc", 502),
            timeout=0.5,
        )

        sock.settimeout(0.5)

        return sock

    except OSError:
        return None


sock = connect()

successful = 0
missed = 0


for tid in range(1, 61):

    if tid > 1:

        if 21 <= tid <= 40:
            time.sleep(0.010)
            phase = "BURST"

        else:
            time.sleep(0.100)
            phase = "NORMAL"

    else:
        phase = "NORMAL"


    if sock is None:
        sock = connect()


    if sock is None:

        print(
            f"{phase} "
            f"tid={tid:02d} "
            "CONNECT_TIMEOUT"
        )

        missed += 1
        continue


    address = (tid - 1) % 10


    pdu = struct.pack(
        "!BHH",
        3,
        address,
        1,
    )

    mbap = struct.pack(
        "!HHHB",
        tid,
        0,
        1 + len(pdu),
        1,
    )


    try:

        sock.sendall(
            mbap + pdu
        )

        header = recv_exact(
            sock,
            7,
        )

        response_tid, protocol_id, length, unit = (
            struct.unpack(
                "!HHHB",
                header,
            )
        )

        body = recv_exact(
            sock,
            length - 1,
        )


        if response_tid != tid:
            raise RuntimeError(
                "transaction-id mismatch"
            )

        if protocol_id != 0:
            raise RuntimeError(
                "unexpected protocol id"
            )


        print(
            f"{phase} "
            f"tid={tid:02d} "
            f"addr={address} "
            f"fc=0x{body[0]:02x}"
        )

        successful += 1


    except (
        OSError,
        RuntimeError,
    ) as exc:

        print(
            f"{phase} "
            f"tid={tid:02d} "
            f"MISS={type(exc).__name__}"
        )

        missed += 1

        try:
            sock.close()
        except OSError:
            pass

        sock = None


if sock is not None:

    try:
        sock.close()
    except OSError:
        pass


print(
    f"REQUESTS_SUCCESSFUL={successful}"
)

print(
    f"REQUESTS_MISSED={missed}"
)
PY
      '
}


normalize_capture() {
    local dir="$1"
    local dataset="$2"
    local image="$3"
    local image_id="$4"
    local name="$5"
    local delay="$6"
    local jitter="$7"
    local loss="$8"
    local trial="$9"

    export \
      DIR="$dir" \
      DATASET_ID="$dataset" \
      IMAGE="$image" \
      IMAGE_ID="$image_id" \
      NAME="$name" \
      DELAY="$delay" \
      JITTER="$jitter" \
      LOSS="$loss" \
      TRIAL="$trial"

    python - <<'PY'
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path

from otshield.adapters import (
    PcapTelemetryAdapter,
)


root = Path(os.environ["DIR"])
dataset_id = os.environ["DATASET_ID"]

raw = root / "raw.pcap"
normalized = root / "normalized.json"


dataset = PcapTelemetryAdapter(
    source="grfics",
    dataset_id=dataset_id,
    evidence_type="lab_capture",
).load(raw)


normalized.write_text(
    json.dumps(
        dataset.to_dict(),
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    + "\n"
)


def digest(path):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


commit = subprocess.check_output(
    [
        "git",
        "rev-parse",
        "HEAD",
    ],
    text=True,
).strip()


provenance = {
    "schema":
        "OTB-LAB-EVIDENCE/0.1",

    "study":
        "OTB-REPEATABILITY/0.1",

    "trial":
        int(os.environ["TRIAL"]),

    "dataset_id":
        dataset_id,

    "evidence_type":
        "lab_capture",

    "source":
        "grfics",

    "lab_scope":
        "OpenPLC read-only resilience repeatability experiment",

    "capture_point":
        "OpenPLC/server network namespace",

    "impairment_direction":
        "client-egress",

    "traffic_policy":
        "function-code-3 reads only",

    "condition": {
        "name":
            os.environ["NAME"],

        "delay_ms":
            float(os.environ["DELAY"]),

        "jitter_ms":
            float(os.environ["JITTER"]),

        "loss_percent":
            float(os.environ["LOSS"]),
    },

    "raw_pcap":
        "raw.pcap",

    "raw_pcap_sha256":
        digest(raw),

    "git_commit":
        commit,

    "openplc_image":
        os.environ["IMAGE"],

    "openplc_image_id":
        os.environ["IMAGE_ID"],

    "docker_version":
        subprocess.check_output(
            [
                "docker",
                "--version",
            ],
            text=True,
        ).strip(),

    "docker_compose_version":
        subprocess.check_output(
            [
                "docker",
                "compose",
                "version",
            ],
            text=True,
        ).strip(),

    "kernel":
        platform.release(),

    "python":
        platform.python_version(),
}


(root / "provenance.json").write_text(
    json.dumps(
        provenance,
        indent=2,
        sort_keys=True,
    )
    + "\n"
)


normalization = {
    "schema":
        "OTB-NORMALIZATION-EVIDENCE/0.1",

    "dataset_id":
        dataset_id,

    "input":
        "raw.pcap",

    "input_sha256":
        digest(raw),

    "output":
        "normalized.json",

    "output_sha256":
        digest(normalized),

    "normalizer":
        "PcapTelemetryAdapter",

    "normalization_git_commit":
        commit,

    "record_count":
        len(dataset.records),
}


(root / "normalization.json").write_text(
    json.dumps(
        normalization,
        indent=2,
        sort_keys=True,
    )
    + "\n"
)


print(
    "NORMALIZED_RECORDS=",
    len(dataset.records),
)
PY
}


CONDITIONS=(
    "clean:0:0:0"
    "delay20:20:0:0"
    "delay20_jitter5_loss5:20:5:5"
    "delay40_jitter10:40:10:0"
    "delay60_jitter10:60:10:0"
)


echo "=============================================="
echo "OTShield repeatability study"
echo "Trials: $TRIALS"
echo "Conditions per trial: ${#CONDITIONS[@]}"
echo "Evidence root:"
echo "$ROOT"
echo "=============================================="


for TRIAL in $(seq 1 "$TRIALS"); do

    echo
    echo "##############################################"
    echo "TRIAL $TRIAL / $TRIALS"
    echo "##############################################"


    cleanup_all


    docker compose \
      -f "$COMPOSE_FILE" \
      up -d openplc


    wait_for_openplc


    NETWORK="$(
        docker inspect \
          otshield-openplc \
          --format '{{range $name,$cfg := .NetworkSettings.Networks}}{{$name}}{{end}}'
    )"


    IMAGE="$(
        docker inspect \
          --format='{{.Config.Image}}' \
          otshield-openplc
    )"


    IMAGE_ID="$(
        docker inspect \
          --format='{{.Image}}' \
          otshield-openplc
    )"


    echo "Network: $NETWORK"
    echo "Image: $IMAGE"
    echo "Image ID: $IMAGE_ID"


    # Rotate condition order between trials to reduce
    # fixed-order drift effects.
    COUNT="${#CONDITIONS[@]}"
    OFFSET=$(( (TRIAL - 1) % COUNT ))


    for STEP in $(seq 0 $((COUNT - 1))); do

        INDEX=$(( (STEP + OFFSET) % COUNT ))

        SPEC="${CONDITIONS[$INDEX]}"

        IFS=: read -r \
          NAME \
          DELAY \
          JITTER \
          LOSS \
          <<< "$SPEC"


        DATASET_ID="$(
          printf \
            'openplc-repeat-%s-t%02d-%s' \
            "$STAMP" \
            "$TRIAL" \
            "$NAME"
        )"


        DIR="$ROOT/trial-$TRIAL/$NAME"

        mkdir -p "$DIR"


        echo
        echo "----------------------------------------------"
        echo "TRIAL=$TRIAL"
        echo "CONDITION=$NAME"
        echo "DELAY=${DELAY}ms"
        echo "JITTER=${JITTER}ms"
        echo "LOSS=${LOSS}%"
        echo "----------------------------------------------"


        write_protocol \
          "$DIR" \
          "$DATASET_ID" \
          "$NAME" \
          "$DELAY" \
          "$JITTER" \
          "$LOSS" \
          "$TRIAL"


        sha256sum \
          "$DIR/protocol.json"


        PCAP_NAME="${DATASET_ID}.pcap"
        HOST_PCAP="$CAPTURE_DIR/$PCAP_NAME"


        docker rm -f \
          otshield-server-capture \
          >/dev/null 2>&1 || true


        docker run -d --rm \
          --name otshield-server-capture \
          --network container:otshield-openplc \
          --cap-add NET_RAW \
          --cap-add NET_ADMIN \
          -e PCAP_NAME="$PCAP_NAME" \
          -v "$CAPTURE_DIR:/captures" \
          alpine:3.20 \
          sh -lc '
            apk add \
              --no-cache \
              tcpdump \
              >/dev/null

            exec tcpdump \
              -i eth0 \
              -U \
              -s 0 \
              -w "/captures/$PCAP_NAME" \
              "tcp port 502"
          ' \
          >/dev/null


        CAPTURE_READY=0

        for _ in $(seq 1 30); do

            if docker logs \
              otshield-server-capture \
              2>&1 |
              grep -q "listening on"; then

                CAPTURE_READY=1
                break
            fi

            sleep 1
        done


        if [ "$CAPTURE_READY" -ne 1 ]; then

            echo "Capture failed to start."

            docker logs \
              otshield-server-capture \
              || true

            exit 1
        fi


        run_client \
          "$NETWORK" \
          "$DELAY" \
          "$JITTER" \
          "$LOSS"


        sleep 1


        docker kill \
          --signal=INT \
          otshield-server-capture \
          >/dev/null 2>&1 || true


        sleep 1


        if [ ! -s "$HOST_PCAP" ]; then

            echo "Missing/empty PCAP:"
            echo "$HOST_PCAP"

            exit 1
        fi


        cp \
          "$HOST_PCAP" \
          "$DIR/raw.pcap"


        echo
        echo "RAW PCAP:"
        sha256sum \
          "$DIR/raw.pcap"


        normalize_capture \
          "$DIR" \
          "$DATASET_ID" \
          "$IMAGE" \
          "$IMAGE_ID" \
          "$NAME" \
          "$DELAY" \
          "$JITTER" \
          "$LOSS" \
          "$TRIAL"


        python \
          scripts/evaluate_resilience.py \
          "$DIR/normalized.json" \
          "$DIR/protocol.json" \
          --result-json \
            "$DIR/result.json" \
          --result-markdown \
            "$DIR/result.md" \
          --observations \
            "$DIR/observations.json"


        (
            cd "$DIR"

            sha256sum \
              raw.pcap \
              protocol.json \
              normalized.json \
              provenance.json \
              normalization.json \
              result.json \
              result.md \
              observations.json \
              > SHA256SUMS
        )


        echo
        echo "CONDITION COMPLETE:"
        echo "trial=$TRIAL condition=$NAME"

        sleep 1
    done


    cleanup_all

    echo
    echo "TRIAL $TRIAL COMPLETE"
done


echo
echo "=============================================="
echo "GENERATE REPLICATE STATISTICS"
echo "=============================================="


python \
  scripts/summarize_resilience_replicates.py \
  "$ROOT" \
  --output "$ROOT/aggregate.json"


export ROOT


python - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["ROOT"])

data = json.loads(
    (root / "aggregate.json").read_text()
)

lines = [
    "# OTShield Resilience Repeatability Study",
    "",
    "Five independent laboratory trials were requested per condition.",
    "",
    "| Condition | N | Coverage mean | Recall mean | Recall SD | Recall 95% CI | F1 mean | End-to-end recall mean |",
    "|---|---:|---:|---:|---:|---:|---:|---:|",
]


for condition, item in data["conditions"].items():

    coverage = item["coverage"]
    recall = item["recall"]
    f1 = item["f1"]
    e2e = item["end_to_end_recall"]

    ci = (
        f'{recall["ci95_low"]:.3f}–'
        f'{recall["ci95_high"]:.3f}'
        if recall["ci95_low"] is not None
        else "n/a"
    )

    sd = (
        f'{recall["sd"]:.3f}'
        if recall["sd"] is not None
        else "n/a"
    )

    lines.append(
        "| "
        + " | ".join(
            [
                condition,
                str(recall["n"]),
                f'{coverage["mean"]:.3f}',
                f'{recall["mean"]:.3f}',
                sd,
                ci,
                f'{f1["mean"]:.3f}',
                f'{e2e["mean"]:.3f}',
            ]
        )
        + " |"
    )


lines.extend(
    [
        "",
        "## Interpretation boundary",
        "",
        "This is an exploratory repeatability analysis with five runs per condition.",
        "",
        "The reported 95% intervals are run-level Student-t intervals and should not be interpreted as population-level production guarantees.",
        "",
        "The experiments use an isolated OpenPLC laboratory, read-only Modbus/TCP Function Code 3 traffic, the polling-burst-v1 detector, and client-egress netem impairment.",
        "",
    ]
)


(root / "aggregate.md").write_text(
    "\n".join(lines)
)


print()
print(
    (root / "aggregate.md").read_text()
)
PY


echo
echo "=============================================="
echo "STUDY MANIFEST"
echo "=============================================="


export \
  STAMP \
  TRIALS


python - <<'PY'
import hashlib
import json
import os
import subprocess
from pathlib import Path

root = Path(os.environ["ROOT"])


results = sorted(
    root.glob(
        "trial-*/*/result.json"
    )
)


manifest = {
    "schema":
        "OTB-REPEATABILITY-STUDY/0.1",

    "study_timestamp":
        os.environ["STAMP"],

    "requested_trials_per_condition":
        int(os.environ["TRIALS"]),

    "condition_count":
        5,

    "planned_transactions_per_condition":
        60,

    "planned_transactions_total":
        int(os.environ["TRIALS"])
        * 5
        * 60,

    "completed_condition_runs":
        len(results),

    "execution_git_commit":
        subprocess.check_output(
            [
                "git",
                "rev-parse",
                "HEAD",
            ],
            text=True,
        ).strip(),

    "result_files": [
        str(
            path.relative_to(root)
        )
        for path in results
    ],
}


(root / "study.json").write_text(
    json.dumps(
        manifest,
        indent=2,
        sort_keys=True,
    )
    + "\n"
)


for name in (
    "aggregate.json",
    "aggregate.md",
    "study.json",
):
    path = root / name

    digest = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()

    print(
        digest,
        name,
    )
PY


(
    cd "$ROOT"

    sha256sum \
      aggregate.json \
      aggregate.md \
      study.json \
      > STUDY_SHA256SUMS
)


echo
echo "=============================================="
echo "FINAL REPOSITORY VERIFICATION"
echo "=============================================="


./scripts/verify_release.sh


echo
echo "=============================================="
echo "COMMIT REPEATABILITY EVIDENCE"
echo "=============================================="


git add \
  "$ROOT"


git commit \
  -m "evidence: add five-trial OpenPLC resilience repeatability study"


git push


echo
echo "===== V0.5 REPEATABILITY STUDY COMPLETE ====="

git status

git log --oneline -7

echo
echo "Evidence root:"
echo "$ROOT"

echo
echo "Aggregate report:"
cat "$ROOT/aggregate.md"
