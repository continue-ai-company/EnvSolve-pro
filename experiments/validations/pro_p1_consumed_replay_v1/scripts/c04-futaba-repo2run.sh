PROJECT_ROOT="$(pwd)"
export PATH="${PYENV_ROOT}/shims:${PYENV_ROOT}/bin:${PATH}"
PYTHON_VERSION="$(pyenv versions --bare | grep -E "^3\.10(\.|$)" | sort -V | tail -n1)"
test -n "$PYTHON_VERSION"
pyenv global "$PYTHON_VERSION"
hash -r
ls ${PROJECT_ROOT}
cat ${PROJECT_ROOT}/pyproject.toml
ls -la ${PROJECT_ROOT}
cat ${PROJECT_ROOT}/poetry.toml
cd ${PROJECT_ROOT}
poetry install
source "$(poetry env info --path)/bin/activate"
