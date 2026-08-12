_project_root="$PWD"
_had_build=0
_had_egg_info=0
[ -e "$_project_root/build" ] && _had_build=1
[ -e "$_project_root/src/androidviewclient.egg-info" ] && _had_egg_info=1

python -m venv --system-site-packages "$_project_root/.venv"
. "$_project_root/.venv/bin/activate"
hash -r

python -m pip install --no-build-isolation --use-pep517 "$_project_root"
python -m pip install pytesseract pytest unittest-xml-reporting pyright

_legacy_pkg_dir=$(mktemp -d)
mkdir -p "$_legacy_pkg_dir/com/android/monkeyrunner"
cat > "$_legacy_pkg_dir/setup.py" <<'PY'
from setuptools import setup

setup(
    name="androidviewclient-envbench-legacy-imports",
    version="0.0.0",
    py_modules=[
        "Tkinter",
        "tkSimpleDialog",
        "tkFileDialog",
        "tkFont",
        "ScrolledText",
        "ttk",
        "Tkconstants",
    ],
    packages=["com.android", "com.android.monkeyrunner"],
)
PY
for _module in Tkinter tkSimpleDialog tkFileDialog tkFont ScrolledText ttk; do
    : > "$_legacy_pkg_dir/${_module}.py"
done
cat > "$_legacy_pkg_dir/Tkconstants.py" <<'PY'
DISABLED = "disabled"
NORMAL = "normal"
PY
: > "$_legacy_pkg_dir/com/android/__init__.py"
: > "$_legacy_pkg_dir/com/android/monkeyrunner/__init__.py"
cat > "$_legacy_pkg_dir/com/android/monkeyrunner/easy.py" <<'PY'
class EasyMonkeyDevice:
    pass

class By:
    pass
PY
python -m pip install "$_legacy_pkg_dir"
rm -rf "$_legacy_pkg_dir"

if [ "$_had_build" -eq 0 ]; then
    rm -rf "$_project_root/build"
fi
if [ "$_had_egg_info" -eq 0 ]; then
    rm -rf "$_project_root/src/androidviewclient.egg-info"
fi
