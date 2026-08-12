#!/usr/bin/env bash
ENV_DIR="$PWD/.envsolve-py310"
python3.10 -m venv "$ENV_DIR"
. "$ENV_DIR/bin/activate"

python -m pip install --upgrade 'pip==26.2.1' 'setuptools==80.10.2' 'wheel==0.47.0'
python -m pip install -e "$PWD" \
  'fake-bpy-module-3.3==20260730' \
  'importlib-metadata==9.0.0' \
  'importlib-resources==7.1.0' \
  'pillow==12.3.0' \
  'lxml==6.1.1' \
  'pybullet==3.2.7' \
  'meshlabxml==2018.3' \
  'pyright==1.1.411'

python - <<'PY'
from pathlib import Path
import site

site_dir = Path(site.getsitepackages()[0])

(site_dir / "hyrodyn-stubs").mkdir(parents=True, exist_ok=True)
(site_dir / "hyrodyn-stubs" / "py.typed").write_text("partial\n", encoding="utf-8")
(site_dir / "hyrodyn-stubs" / "__init__.pyi").write_text("class RobotModel: ...\n", encoding="utf-8")

(site_dir / "phobos-stubs" / "blender" / "model").mkdir(parents=True, exist_ok=True)
(site_dir / "phobos-stubs" / "py.typed").write_text("partial\n", encoding="utf-8")
(site_dir / "phobos-stubs" / "blender" / "model" / "motors.pyi").write_text(
    "def createMotor(*args, **kwargs): ...\n",
    encoding="utf-8",
)
PY
