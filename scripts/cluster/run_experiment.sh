#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: run_experiment.sh --run-id ID [--root ABSOLUTE_PATH]"
    echo "Runs the offline CASR smoke experiment inside an already allocated job."
    echo "This script never submits a job, waits in a loop, or requests GPU resources."
}

ROOT="${CASR_REMOTE_ROOT:-$HOME/CASR}"
RUN_ID=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --root)
            [[ $# -ge 2 ]] || { echo "ERROR: --root requires a value" >&2; exit 2; }
            ROOT="$2"
            shift 2
            ;;
        --run-id)
            [[ $# -ge 2 ]] || { echo "ERROR: --run-id requires a value" >&2; exit 2; }
            RUN_ID="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ ! "$ROOT" =~ ^/[A-Za-z0-9._/-]+$ || "/$ROOT/" == *"/../"* || "/$ROOT/" == *"/./"* ]]; then
    echo "ERROR: root must be an absolute POSIX path without '.' or '..' segments" >&2
    exit 2
fi
if [[ ! "$RUN_ID" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
    echo "ERROR: run-id must start with a letter or digit and contain only letters, digits, dots, underscores, or hyphens" >&2
    exit 2
fi
if [[ ! -d "$ROOT" || ! -f "$ROOT/scripts/cluster/prepare.sh" || ! -f "$ROOT/scripts/check_env.py" || ! -d "$ROOT/tests" ]]; then
    echo "ERROR: root is not a synced CASR project: $ROOT" >&2
    exit 2
fi

LOG_DIR="$ROOT/logs/$RUN_ID"
RESULT_DIR="$ROOT/results/$RUN_ID"
mkdir -p "$LOG_DIR" "$RESULT_DIR"

STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
START_EPOCH="$(date +%s)"
PYTHON="${CASR_PYTHON:-}"
if [[ -z "$PYTHON" && -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON="$ROOT/.venv/bin/python"
fi

set +e
bash "$ROOT/scripts/cluster/prepare.sh" --root "$ROOT" 2>&1 | tee "$LOG_DIR/prepare.log"
PREPARE_CODE="${PIPESTATUS[0]}"
set -e

TEST_CODE=125
ENV_CODE=125
GPU_STATUS="unknown"

if [[ "$PREPARE_CODE" -eq 0 ]]; then
    if [[ -z "$PYTHON" ]]; then
        PYTHON="$(command -v python3)"
    fi

    set +e
    "$PYTHON" -m pytest -q 2>&1 | tee "$LOG_DIR/pytest.log"
    TEST_CODE="${PIPESTATUS[0]}"
    "$PYTHON" "$ROOT/scripts/check_env.py" 2>&1 | tee "$LOG_DIR/environment.json"
    ENV_CODE="${PIPESTATUS[0]}"
    set -e

    if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader >"$LOG_DIR/gpu.csv" 2>"$LOG_DIR/gpu-error.log"; then
        GPU_STATUS="available"
    else
        GPU_STATUS="unavailable"
    fi
fi

FINISHED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
END_EPOCH="$(date +%s)"
DURATION_SECONDS=$((END_EPOCH - START_EPOCH))

if [[ "$PREPARE_CODE" -eq 0 && "$TEST_CODE" -eq 0 && "$ENV_CODE" -eq 0 ]]; then
    STATUS="PASS"
    EXIT_CODE=0
else
    STATUS="FAIL"
    EXIT_CODE=1
fi

SUMMARY_PYTHON="${PYTHON:-python3}"
"$SUMMARY_PYTHON" - "$ROOT" "$RUN_ID" "$STARTED_AT" "$FINISHED_AT" "$DURATION_SECONDS" "$PREPARE_CODE" "$TEST_CODE" "$ENV_CODE" "$GPU_STATUS" "$STATUS" <<'PY'
import json
import os
import socket
import sys

root, run_id, started_at, finished_at, duration, prepare_code, test_code, env_code, gpu_status, status = sys.argv[1:]
result_dir = os.path.join(root, "results", run_id)
summary = {
    "run_id": run_id,
    "status": status,
    "started_at": started_at,
    "finished_at": finished_at,
    "duration_seconds": int(duration),
    "hostname": socket.gethostname(),
    "root": root,
    "exit_codes": {
        "prepare": int(prepare_code),
        "pytest": int(test_code),
        "environment": int(env_code),
    },
    "gpu_visibility": gpu_status,
    "artifacts": {
        "logs": os.path.join(root, "logs", run_id),
        "results": result_dir,
    },
}
with open(os.path.join(result_dir, "summary.json"), "w", encoding="utf-8") as handle:
    json.dump(summary, handle, ensure_ascii=False, indent=2, sort_keys=True)
    handle.write("\n")
print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
PY

exit "$EXIT_CODE"
