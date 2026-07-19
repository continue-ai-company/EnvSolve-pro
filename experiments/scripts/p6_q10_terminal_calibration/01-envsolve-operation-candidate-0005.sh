set -euo pipefail
apt-get update
apt-get install -y gfortran
python -m venv .venv
. .venv/bin/activate
pip install -e .[covalent,dask,defects,jobflow,mlp,mp,newtonnet,parsl,phonons,prefect,redun,sella,tblite]
