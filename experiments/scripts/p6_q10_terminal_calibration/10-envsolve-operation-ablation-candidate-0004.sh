set -euo pipefail
apt-get update
apt-get install -y rustc cargo libgit2-dev build-essential cmake pkg-config python3-dev libbrotli-dev liblz4-dev
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install setuptools "setuptools_scm[toml]"
pip install .
