set -euo pipefail
apt-get update
apt-get install -y python3.11 python3.11-venv python3.11-dev
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install poetry
poetry install
