ENV_DIR="/tmp/envsolve-citationhunt-53d3975373b51c22a805cb2a07d12e3d8cfb21c7-py39"
CONDA_BASE="$(conda info --base)"
source "$CONDA_BASE/etc/profile.d/conda.sh"

if [ ! -x "$ENV_DIR/bin/python" ]; then
    conda create -y -q -p "$ENV_DIR" -c conda-forge python=3.9 pip mysqlclient=2.1.1
fi

conda activate "$ENV_DIR"
python -m pip install --root-user-action=ignore --no-build-isolation -r <(grep -v -E '^mysqlclient==' requirements.txt)
python -m pip install --root-user-action=ignore --quiet pyright
export PYTHONPATH="$PWD:$PWD/scripts${PYTHONPATH:+:$PYTHONPATH}"
