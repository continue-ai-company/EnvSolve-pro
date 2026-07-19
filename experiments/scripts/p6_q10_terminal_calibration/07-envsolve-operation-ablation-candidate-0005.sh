set -euo pipefail
apt-get update
apt-get install -y python3 python3-pip python3-venv
python3 -m venv .venv
. .venv/bin/activate
pip install --retries 5 --timeout 30 -r requirements.txt
