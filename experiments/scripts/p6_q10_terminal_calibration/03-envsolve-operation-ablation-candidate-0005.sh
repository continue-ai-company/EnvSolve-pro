set -euo pipefail
python -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -e .
pip install -r requirements/testing.txt
pip install async-timeout paho-mqtt
pip install https://github.com/XKNX/myhouse-sensors-mqtt/archive/main.zip
