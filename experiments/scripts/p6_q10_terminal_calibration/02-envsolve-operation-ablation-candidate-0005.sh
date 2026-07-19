set -euo pipefail
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
apt-get update
apt-get install -y gfortran liblapack-dev
pip install -e ".[covalent,dask,defects,jobflow,mlp,mp,newtonnet,parsl,phonons,prefect,redun,sella,tblite,dev]"
