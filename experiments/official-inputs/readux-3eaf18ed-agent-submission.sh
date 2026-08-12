READUX_VENV="${READUX_VENV:-/tmp/readux-venv}"
export PIP_NO_INPUT=1

if ! command -v pg_config >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y libpq-dev jq
fi

python3.11 -m venv "$READUX_VENV"
. "$READUX_VENV/bin/activate"
python -m pip install --upgrade pip setuptools wheel
PYTHONPATH= python -m pip install -r "$PWD/requirements/local.txt"
PYTHONPATH= python -m pip install django-users2==0.2.2

if [ ! -e "$PWD/config/settings/local.py" ]; then
    cp "$PWD/config/settings/local.dst" "$PWD/config/settings/local.py"
fi

. "$READUX_VENV/bin/activate"
export PYTHONPATH="$READUX_VENV/src/digitaledition-jekylltheme"
