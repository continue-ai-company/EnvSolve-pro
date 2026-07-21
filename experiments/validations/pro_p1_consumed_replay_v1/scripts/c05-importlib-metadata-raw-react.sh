PROJECT_ROOT="$(pwd)"
ls -la /data/project
cd /data/project && ls -la
cd /data/project && find . -maxdepth 1 -type d
cd /data/project && find . -maxdepth 1 -type d -exec ls -la {} \;
cd "${PROJECT_ROOT}" && cat pyproject.toml
cd "${PROJECT_ROOT}" && cat README.rst
cd "${PROJECT_ROOT}" && cat tox.ini
cd "${PROJECT_ROOT}" && python --version && which python
cd "${PROJECT_ROOT}" && cat setup.py 2>/dev/null || echo "No setup.py"; cat setup.cfg 2>/dev/null || echo "No setup.cfg"
cd "${PROJECT_ROOT}" && ls -la importlib_metadata/
cd "${PROJECT_ROOT}" && pip install -e .
cd "${PROJECT_ROOT}" && python -c "import importlib_metadata; print(importlib_metadata.version('importlib_metadata')); print('Success!')"
cd "${PROJECT_ROOT}" && pip install -e ".[test]"
cd "${PROJECT_ROOT}" && python -c "
import importlib_metadata
print('importlib_metadata version:', importlib_metadata.version('pip'))
print('Package metadata example:')
md = importlib_metadata.metadata('pip')
print('Name:', md['Name'])
print('Version:', md['Version'])
print('Test import successful!')
"
cd "${PROJECT_ROOT}" && python -m pytest --collect-only 2>&1 | head -50
cd "${PROJECT_ROOT}" && python -m pytest tests/ -x --timeout=60 2>&1 | tail -30
cd "${PROJECT_ROOT}" && python -m pytest tests/ -x 2>&1 | tail -30
