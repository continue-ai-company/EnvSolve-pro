python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip 'setuptools<81' wheel
python -m pip install -e "$PWD" --no-deps
python -m pip install check_shapes deprecated multipledispatch numpy packaging scipy tabulate typing_extensions tensorflow-probability tf-nightly tf-keras-nightly pytest ipython pillow py-cpuinfo GitPython jupytext nbclient nbconvert nbformat matplotlib pandas scikit-learn tensorflow-datasets mypy
