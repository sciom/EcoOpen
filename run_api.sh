#!/usr/bin/env bash
set -euo pipefail

# Prefer explicit override via PYEXEC, then active Conda environment's Python, else fall back to PATH
if [[ -n "${PYEXEC:-}" && -x "${PYEXEC}" ]]; then
	PYEXEC="${PYEXEC}"
elif [[ -n "${CONDA_PREFIX:-}" && -x "${CONDA_PREFIX}/bin/python" ]]; then
	PYEXEC="${CONDA_PREFIX}/bin/python"
else
	PYEXEC="$(command -v python)"
fi

echo "Using Python: ${PYEXEC}"
"${PYEXEC}" - <<'PY'
import sys
print('sys.executable:', sys.executable)
print('sys.version:', sys.version)
PY

# Allow disabling reload if a shim/mise is hijacking the reloader interpreter
RELOAD_FLAG="--reload"
if [[ "${NO_RELOAD:-0}" == "1" ]]; then
	RELOAD_FLAG=""
fi

exec "${PYEXEC}" -m uvicorn app.main:app ${RELOAD_FLAG} --host 127.0.0.1 --port 3290
