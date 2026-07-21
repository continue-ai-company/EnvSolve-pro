PROJECT_ROOT="$(pwd)"
ls -la /data/project
ls -la ${PROJECT_ROOT}
cat ${PROJECT_ROOT}/pyproject.toml
cat ${PROJECT_ROOT}/poetry.toml
cat ${PROJECT_ROOT}/README.md
cat ${PROJECT_ROOT}/CONTRIBUTING.md
cd ${PROJECT_ROOT} && python --version && pyenv versions
which python && python --version && which python3 && python3 --version
cd ${PROJECT_ROOT} && export PATH="/root/.pyenv/shims:/root/.pyenv/bin:$PATH" && pyenv global 3.10.13 && python --version
cd ${PROJECT_ROOT} && rm -rf .venv && export PATH="/root/.pyenv/shims:/root/.pyenv/bin:$PATH" && poetry env use 3.10.13 && poetry install --with dev 2>&1
cd ${PROJECT_ROOT} && source .venv/bin/activate && python --version && python -c "import futaba; print('futaba imported successfully')" && python -c "import discord; print('discord imported successfully')" && python -c "import sqlalchemy; print('sqlalchemy imported successfully')" && python -c "import aiohttp; print('aiohttp imported successfully')" && python -c "import dateparser; print('dateparser imported successfully')"
cd ${PROJECT_ROOT} && source .venv/bin/activate && python -c "import confusable_homoglyphs; print('confusable_homoglyphs ok')" && python -c "import schema; print('schema ok')" && python -c "import textdistance; print('textdistance ok')" && python -c "import toml; print('toml ok')" && python -c "import tree_format; print('tree_format ok')" && python -c "import jose; print('python-jose ok')" && python -c "import psycopg2; print('psycopg2 ok')"
cd ${PROJECT_ROOT} && source .venv/bin/activate && ruff --version && pylint --version && python -m futaba --help 2>&1 || true
cd ${PROJECT_ROOT} && source .venv/bin/activate && python -c "
import futaba
import discord
import sqlalchemy
import aiohttp
import dateparser
import confusable_homoglyphs
import schema
import textdistance
import toml
import tree_format
import jose
import psycopg2
import ruff
import pylint
print('All imports successful!')
print('futaba version:', futaba.__version__)
"
