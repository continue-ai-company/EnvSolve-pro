set -euo pipefail
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"
pyenv install 3.11
pyenv local 3.11
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install poetry-core
python -m pip install -e .
python -m pip install pytest pytest-cov pytest-mock pytest-xdist flake8
