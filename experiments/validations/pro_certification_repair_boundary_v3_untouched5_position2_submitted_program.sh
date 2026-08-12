_envsolve_shell_state=$(set +o)
set -e

if [ -x /opt/conda/bin/python ]; then
  _envsolve_base_python=/opt/conda/bin/python
elif command -v python3 >/dev/null 2>&1; then
  _envsolve_base_python=$(command -v python3)
else
  _envsolve_base_python=$(command -v python)
fi

"$_envsolve_base_python" -m venv .envsolve-venv
. "$PWD/.envsolve-venv/bin/activate"

python -m pip install --quiet --upgrade pip setuptools wheel
python -m pip install --quiet \
  pytest pytest-checkdocs pytest-cov pytest-mypy pytest-enabler pytest-ruff \
  jaraco.envs jaraco.path jaraco.text 'path>=10.6' docutils pyfakefs more_itertools

python - <<'PY'
from pathlib import Path
from setuptools import find_packages, setup

wheel_dir = Path('build_output/local-dist')
wheel_dir.mkdir(parents=True, exist_ok=True)
setup(
    name='distutils',
    version='0.0.0+envsolve',
    packages=find_packages(include=['distutils', 'distutils.*']),
    package_data={
        'distutils.command': ['command_template', 'wininst-*.exe'],
        'distutils.tests': ['*.c', '*.rst', 'Setup.sample'],
    },
    script_args=[
        '-q',
        'egg_info', '--egg-base', 'build_output',
        'build', '--build-base', 'build_output/local-build',
        'bdist_wheel', '--dist-dir', str(wheel_dir),
    ],
)
PY

python - <<'PY'
from pathlib import Path
import subprocess
import sys

wheels = sorted(Path('build_output/local-dist').glob('distutils-0.0.0+envsolve-*.whl'))
if not wheels:
    raise SystemExit('local distutils wheel was not built')
subprocess.check_call([
    sys.executable,
    '-m',
    'pip',
    'install',
    '--quiet',
    '--force-reinstall',
    '--no-deps',
    str(wheels[-1]),
])
PY

export SETUPTOOLS_USE_DISTUTILS=stdlib
export PYTHONPATH="$PWD/build_output:$PWD${PYTHONPATH:+:$PYTHONPATH}"

python - <<'PY'
from pathlib import Path
from distutils.core import Distribution
from distutils.command.build_ext import build_ext
from distutils.extension import Extension
from distutils.tests.support import fixup_build_ext

build_output = Path('build_output')
build_output.mkdir(exist_ok=True)
dist = Distribution({'name': 'xx', 'ext_modules': [Extension('xx', ['distutils/tests/xxmodule.c'])]})
cmd = build_ext(dist)
fixup_build_ext(cmd)
cmd.build_lib = str(build_output)
cmd.build_temp = str(build_output / 'temp')
cmd.ensure_finalized()
cmd.run()
PY

eval "$_envsolve_shell_state"
