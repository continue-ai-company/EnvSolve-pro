set -euo pipefail
python -m venv .venv
. .venv/bin/activate
pip install -e .
pip install -r requirements/testing.txt
pip install async-timeout paho-mqtt myhouse-sensors
