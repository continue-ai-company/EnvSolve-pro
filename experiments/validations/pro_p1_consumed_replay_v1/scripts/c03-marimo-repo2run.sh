PROJECT_ROOT="$(pwd)"
export PATH="${PYENV_ROOT}/shims:${PYENV_ROOT}/bin:${PATH}"
PYTHON_VERSION="$(pyenv versions --bare | grep -E "^3\.10(\.|$)" | sort -V | tail -n1)"
test -n "$PYTHON_VERSION"
pyenv global "$PYTHON_VERSION"
hash -r
ls ${PROJECT_ROOT}
cat ${PROJECT_ROOT}/pyproject.toml
ls ${PROJECT_ROOT}/poetry.lock 2>/dev/null || echo "No poetry.lock found"
cd ${PROJECT_ROOT}
pip install -e ".[testcore]" -q
mkdir -p ${PROJECT_ROOT}/marimo/_static/assets
