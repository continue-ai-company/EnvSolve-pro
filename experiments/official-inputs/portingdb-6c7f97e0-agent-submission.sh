DEBIAN_FRONTEND=noninteractive apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends cmake git python3-dnf python3-hawkey python3-libdnf

python -m pip install --quiet -e "$PWD" --no-deps
python -m pip install --quiet PyYAML click flask markdown plotly blessings elsa networkx python-bugzilla redis pytest

rm -rf /tmp/dnf-plugins-core-4.0.24 /tmp/dnf-plugins-core-build
git -c advice.detachedHead=false clone --quiet --depth 1 --branch 4.0.24 https://github.com/rpm-software-management/dnf-plugins-core.git /tmp/dnf-plugins-core-4.0.24
cmake -S /tmp/dnf-plugins-core-4.0.24 -B /tmp/dnf-plugins-core-build -DPYTHON_DESIRED="$(command -v python)"
cmake -P /tmp/dnf-plugins-core-build/plugins/cmake_install.cmake

__portingdb_python_site="$(python - <<'PY'
import sysconfig
print(sysconfig.get_path('purelib'))
PY
)"
export PYTHONPATH="$__portingdb_python_site:/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
unset __portingdb_python_site
