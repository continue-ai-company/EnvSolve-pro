if ! command -v java >/dev/null 2>&1; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq default-jre-headless
fi

python3.10 -m venv venv
. "$PWD/venv/bin/activate"

python -m pip install -q --upgrade 'pip<27' 'setuptools<81' wheel
python -m pip install -q --no-build-isolation -r requirements/dev.txt -e . importlib-resources

python - <<'PY'
from pathlib import Path

for path in (Path('hydra/grammar/gen/OverrideLexer.py'), Path('hydra/grammar/gen/OverrideParser.py')):
    text = path.read_text(encoding='utf-8')
    path.write_text(text.replace('from typing.io import TextIO', 'from typing import TextIO'), encoding='utf-8')
PY

python -m pip install -q 'pyright==1.1.402' 'nevergrad>=0.4.3.post9' 'optuna>=2.10.0,<3.0.0' 'sqlalchemy~=1.3.0' boto3 'rq>=1.5.1,<1.12' redis 'submitit>=1.3.3'
python -m pip install -q 'ray[default]<3'
python -m pip install -q --default-timeout=1000 'torch==1.13.1'
