_env_dir="${ENVSOLVE_UER_PY_ENV:-/tmp/uer-py-5743050-py311}"
if [ ! -x "$_env_dir/bin/python" ]; then
    python3.11 -m venv "$_env_dir"
fi
. "$_env_dir/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install --index-url https://download.pytorch.org/whl/cpu 'torch==2.13.0+cpu'
python -m pip install six packaging numpy regex scipy sentencepiece jieba pytorch-crf lightgbm bayesian-optimization 'tensorflow==2.21.0' pyright

_site_packages="$(python - <<'PY'
import site
print(site.getsitepackages()[0])
PY
)"
_tf_pkg="$_site_packages/tensorflow"
if [ -d "$_tf_pkg/python/keras" ] && [ ! -e "$_tf_pkg/keras" ]; then
    ln -s "$_tf_pkg/python/keras" "$_tf_pkg/keras"
fi

unset PYRIGHT_PYTHON_PYLANCE_VERSION
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
