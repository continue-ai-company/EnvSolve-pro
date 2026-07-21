PROJECT_ROOT="$(pwd)"
ls -la
cat pyproject.toml
cat README.md
cat Makefile
cat CONTRIBUTING.md
python --version && pyenv versions
ls marimo/_static 2>/dev/null && echo "Static exists" || echo "Static does not exist"
ls marimo/
node --version && pnpm --version 2>/dev/null || echo "pnpm not found"
which make && make --version | head -1
npm install -g pnpm@8
ls frontend/
cat frontend/package.json | head -30
cat scripts/buildfrontend.sh
cat marimo/__init__.py
ls lsp/
cat scripts/buildlsp.sh
pwd && ls -la
cd ${PROJECT_ROOT} && pwd && ls -la
cd ${PROJECT_ROOT} && NODE_OPTIONS=--max_old_space_size=8192 make fe -B
pyenv global 3.12.0 && python --version
pyenv versions && which python
export PATH="/root/.pyenv/shims:$PATH" && python --version
