#!/usr/bin/env bash
set -euo pipefail

# Conda environment setup for EcoOpen LLM API
# - Creates/activates a conda env and installs pip requirements
# - Defaults: env name 'ecoopen-llm', Python 3.11

usage() {
  cat <<'EOF'
Usage: ./setup_conda.sh [-n ENV_NAME] [-p PYTHON_VERSION]

Options:
  -n ENV_NAME        Conda environment name (default: ecoopen-llm)
  -p PYTHON_VERSION  Python version to install (default: 3.11)

Examples:
  ./setup_conda.sh
  ./setup_conda.sh -n ecoopen-llm -p 3.11
EOF
}

ENV_NAME="ecoopen-llm"
PYVER="3.11"

while getopts ":n:p:h" opt; do
  case ${opt} in
    n) ENV_NAME="$OPTARG" ;;
    p) PYVER="$OPTARG" ;;
    h) usage; exit 0 ;;
    :) echo "Option -$OPTARG requires an argument" >&2; usage; exit 1 ;;
    \?) echo "Invalid option: -$OPTARG" >&2; usage; exit 1 ;;
  esac
done

if ! command -v conda >/dev/null 2>&1; then
  echo "Conda not found. Please install Miniconda or Anaconda first:" >&2
  echo "  https://docs.conda.io/en/latest/miniconda.html" >&2
  exit 1
fi

# Prefer mamba if available for speed
if command -v mamba >/dev/null 2>&1; then
  CONDA_CMD="mamba"
else
  CONDA_CMD="conda"
fi

# Ensure conda.sh is sourced for 'conda activate'
CONDA_BASE="$(conda info --base)"
# shellcheck source=/dev/null
source "$CONDA_BASE/etc/profile.d/conda.sh"

echo "Creating conda env '$ENV_NAME' with Python $PYVER (if missing)..."
$CONDA_CMD create -y -n "$ENV_NAME" python="$PYVER" >/dev/null 2>&1 || true

echo "Activating env '$ENV_NAME'..."
conda activate "$ENV_NAME"

# Ensure latest pip/setuptools/wheel inside env
python -m pip install -U pip setuptools wheel

if [ ! -f requirements.txt ]; then
  echo "requirements.txt not found at repo root. Run from the project root." >&2
  exit 1
fi

echo "Installing Python dependencies from requirements.txt..."
pip install -r requirements.txt

echo ""
echo "Setup complete!"
echo "To use the environment in this shell:"
echo "  conda activate $ENV_NAME"
echo "Then run the API:"
echo "  ./run_api.sh"
echo ""
echo "Notes:"
echo "- Configure optional settings in a .env file (see app/core/config.py for keys)."
echo "- Ensure Ollama is running locally if you rely on local embeddings (OLLAMA_HOST)."
