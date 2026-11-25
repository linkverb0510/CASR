#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: prepare.sh [--root ABSOLUTE_PATH] [--install]"
    echo "Checks the CASR runtime without installing dependencies unless --install is explicit."
}

ROOT="${CASR_REMOTE_ROOT:-$HOME/CASR}"
INSTALL=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --root)
            [[ $# -ge 2 ]] || { echo "ERROR: --root requires a value" >&2; exit 2; }
            ROOT="$2"
            shift 2
            ;;
        --install)
            INSTALL=1
            shift
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

if [[ ! -d "$ROOT" ]]; then
    echo "ERROR: root does not exist: $ROOT" >&2
    exit 2
fi

for tool in git tar sha256sum; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "ERROR: required command is missing: $tool" >&2
        exit 3
    fi
done

if [[ -n "${CASR_PYTHON:-}" ]]; then
    PYTHON="$CASR_PYTHON"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON="$ROOT/.venv/bin/python"
else
    PYTHON="$(command -v python3.12 || command -v python3 || true)"
fi

if [[ -z "$PYTHON" || ! -x "$PYTHON" ]]; then
    echo "ERROR: Python 3.12 is required; set CASR_PYTHON to an executable Python 3.12 path" >&2
    exit 3
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if (3, 12) <= sys.version_info < (3, 13) else 1)'; then
    VERSION="$($PYTHON -c 'import sys; print(sys.version.split()[0])')"
    echo "ERROR: Python 3.12.x is required, found $VERSION at $PYTHON" >&2
    exit 3
fi

if ! "$PYTHON" -c 'import git, networkx, pydantic, pytest' >/dev/null 2>&1; then
    if [[ "$INSTALL" -ne 1 ]]; then
        echo "ERROR: CASR dependencies are missing; rerun prepare.sh --install to allow dependency installation" >&2
        exit 4
    fi

    if command -v uv >/dev/null 2>&1; then
        (
            cd "$ROOT"
            uv sync --frozen --group dev
        )
    else
        "$PYTHON" -m venv "$ROOT/.venv"
        "$ROOT/.venv/bin/python" -m pip install -e "$ROOT" 'pytest>=8,<10'
    fi
    PYTHON="$ROOT/.venv/bin/python"
fi

VERSION="$($PYTHON -c 'import sys; print(sys.version.split()[0])')"
"$PYTHON" - "$ROOT" "$PYTHON" "$VERSION" <<'PY'
import json
import sys
from importlib import metadata

root, executable, version = sys.argv[1:]
dependencies = {
    name: metadata.version(name)
    for name in ("GitPython", "networkx", "pydantic", "pytest")
}
print(json.dumps({
    "ready": True,
    "root": root,
    "python": executable,
    "python_version": version,
    "dependencies": dependencies,
}, sort_keys=True))
PY
