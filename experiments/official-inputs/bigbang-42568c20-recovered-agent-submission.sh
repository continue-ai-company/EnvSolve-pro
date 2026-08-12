PROJECT_ROOT="$PWD"
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip setuptools setuptools-scm wheel
python -m pip install --no-build-isolation . --no-deps
python -m pip install \
  numpy networkx requests pandas beautifulsoup4 chardet html2text \
  python-dateutil pytz tqdm pyyaml certifi levenshtein ietfdata \
  python-docx GitPython nbformat nbconvert validator-collection markdown \
  spacy transformers contractions email_reply_parser notebook click \
  pytest coverage testfixtures black isort pre-commit m2r2 sphinx-rtd-theme \
  matplotlib colour enlighten pyright
COMPAT_DIR="$(mktemp -d)"
cat > "$COMPAT_DIR/pyproject.toml" <<'EOF'
[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"
EOF
cat > "$COMPAT_DIR/setup.cfg" <<EOF
[metadata]
name = bigbang-listserv-compat
version = 0.0.0

[options]
py_modules = bigbang.listserv
package_dir =
    bigbang = ${PROJECT_ROOT}/bigbang/ingress
EOF
python -m pip install --no-build-isolation "$COMPAT_DIR"
rm -rf "$COMPAT_DIR"
