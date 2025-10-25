#!/usr/bin/env bash
set -euo pipefail

# Flags (can override via env):
# - SKIP_FRONTEND=1   → skip building frontend
# - INSTALL_BACKEND=1 → ensure venv + pip install (default 1)
# - DISABLE_CONFLICTING_SITES=1 → remove other nginx sites with same server_name (default 1)
# - PUBLIC_BASE=https://ecoopen.sciom.net → public base URL for health check
SKIP_FRONTEND="${SKIP_FRONTEND:-0}"
INSTALL_BACKEND="${INSTALL_BACKEND:-1}"
DISABLE_CONFLICTING_SITES="${DISABLE_CONFLICTING_SITES:-1}"
PUBLIC_BASE="${PUBLIC_BASE:-https://ecoopen.sciom.net}"

echo "Deploying EcoOpen services..."

# Ensure running from repo root
if [[ ! -f "ecoopen.service" || ! -d "frontend" ]]; then
  echo "Please run from the repository root (where ecoopen.service and frontend/ exist)."
  exit 1
fi

# Optionally build frontend
if [[ "${SKIP_FRONTEND}" != "1" ]]; then
  echo "Building frontend (vite)..."
  if ! command -v node >/dev/null 2>&1; then
    echo "Error: Node.js not found. Install Node >=18."; exit 1
  fi
  if ! command -v npm >/dev/null 2>&1; then
    echo "Error: npm not found. Install Node.js (includes npm)."; exit 1
  fi
  # Check Node version (require >=18.x)
  NODE_VER_RAW="$(node --version | sed 's/^v//')"
  NODE_MAJOR="${NODE_VER_RAW%%.*}"
  if (( NODE_MAJOR < 18 )); then
    echo "Error: Node ${NODE_VER_RAW} detected. Require Node >=18."; exit 1
  fi
  ( 
    set -e
    cd frontend
    echo "Running npm ci (fallback to npm install if needed)..."
    npm ci --no-audit --no-fund || npm install --no-audit --no-fund
    npm run build
  )
else
  echo "Skipping frontend build (SKIP_FRONTEND=${SKIP_FRONTEND})."
fi

# Copy systemd service
echo "Copying systemd service..."
sudo cp ecoopen.service /etc/systemd/system/

# Reload systemd
echo "Reloading systemd..."
sudo systemctl daemon-reload

# Restart ecoopen service
echo "Restarting ecoopen service..."
sudo systemctl restart ecoopen

# Check status (non-fatal)
echo "Checking ecoopen service status..."
sudo systemctl --no-pager --full status ecoopen || true

# Copy nginx config and enable site
echo "Copying nginx config..."
sudo cp ecoopen-nginx.conf /etc/nginx/sites-available/ecoopen
sudo ln -sf /etc/nginx/sites-available/ecoopen /etc/nginx/sites-enabled/

# Disable potential conflicting server_name configs (non-fatal)
if [[ "${DISABLE_CONFLICTING_SITES}" == "1" ]]; then
  echo "Disabling conflicting nginx site entries (if any)..."
  for f in /etc/nginx/sites-enabled/*; do
    if [[ -L "$f" && "$f" != "/etc/nginx/sites-enabled/ecoopen" ]]; then
      if sudo grep -qE "server_name\s+.*(ecoopen\.sciom\.net|www\.ecoopen\.sciom\.net)" "$f" >/dev/null 2>&1; then
        echo "  disabling $f"
        sudo rm -f "$f"
      fi
    fi
  done
else
  echo "Keeping existing nginx site entries (DISABLE_CONFLICTING_SITES=${DISABLE_CONFLICTING_SITES})."
fi

# Test nginx config
echo "Testing nginx config..."
sudo nginx -t

# Reload nginx
echo "Reloading nginx..."
sudo systemctl reload nginx

# Optionally install backend deps
if [[ "${INSTALL_BACKEND}" == "1" ]]; then
  echo "Ensuring venv and installing backend dependencies..."
  VENV_DIR="${VENV_DIR:-/home/server/services/EcoOpen/venv}"
  PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || command -v python)}"
  if [[ ! -d "${VENV_DIR}" ]]; then
    echo "Creating virtualenv at ${VENV_DIR}..."
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  fi
  VENV_BIN="${VENV_DIR}/bin"
  if [[ ! -x "${VENV_BIN}/python" ]]; then
    echo "Error: venv python not found at ${VENV_BIN}/python"
    exit 1
  fi
  "${VENV_BIN}/python" -m pip install -U pip wheel
  "${VENV_BIN}/pip" install -r requirements.txt
  echo "Restarting ecoopen after dependency install..."
  sudo systemctl restart ecoopen
else
  echo "Skipping backend dependency install (INSTALL_BACKEND=${INSTALL_BACKEND})."
fi

# Basic health checks with retries (non-fatal)
echo "Waiting for backend to become ready (http://127.0.0.1:3290/health)..."
set +e
LOCAL_STATUS="000"
for i in {1..30}; do
  LOCAL_STATUS="$(curl -fsS -o /dev/null -w '%{http_code}' http://127.0.0.1:3290/health || true)"
  if [[ "${LOCAL_STATUS}" == "200" ]]; then
    break
  fi
  sleep 1
  if (( i % 5 == 0 )); then echo "  still waiting... (${i}s)"; fi
 done
echo "Local health status: ${LOCAL_STATUS:-none}"

# If local is bad, show service logs and sockets for debugging
echo "\n=== ecoopen service logs (last 200 lines) ==="
sudo journalctl -u ecoopen -n 200 --no-pager || true

echo "\n=== systemd status ecoopen ==="
sudo systemctl --no-pager --full status ecoopen || true

echo "\n=== Listening sockets (grep 3290) ==="
sudo ss -tlnp | grep -E 3290 || sudo ss -tlnp || true

# Public health via nginx
echo "\nWaiting for public health via nginx (${PUBLIC_BASE}/api/health)..."
PUBLIC_STATUS="000"
for i in {1..20}; do
  PUBLIC_STATUS="$(curl -fsS -o /dev/null -w '%{http_code}' "${PUBLIC_BASE}/api/health" || true)"
  if [[ "${PUBLIC_STATUS}" == "200" ]]; then
    break
  fi
  sleep 1
  if (( i % 5 == 0 )); then echo "  still waiting... (${i}s)"; fi
 done
echo "Public health status: ${PUBLIC_STATUS:-none}"
set -e

if [[ "${PUBLIC_STATUS:-}" != "200" ]]; then
  echo "Warning: Public health endpoint not returning 200. Check nginx/service logs above."
else
  echo "Success: Public health endpoint OK."
fi

echo "Deployment complete. Visit ${PUBLIC_BASE}"

