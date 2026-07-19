set -euo pipefail
python -m venv .venv
. .venv/bin/activate
apt-get update
apt-get install -y cmake pkg-config libfreetype6-dev liblzma-dev libbrotli-dev
python -m pip install --upgrade pip
python -m pip install "protobuf>=3.7.0,<4"
python -m pip install pygit2
python -m pip install absl-py
python -m pip install afdko
python -m pip install axisregistry
python -m pip install babelfont
python -m pip install beautifulsoup4
python -m pip install brotli
python -m pip install bumpfontversion
python -m pip install font-v
python -m pip install fontfeatures
python -m pip install fontmake
python -m pip install fonttools
python -m pip install gflanguages
python -m pip install gfsubsets
python -m pip install glyphsets
python -m pip install glyphslib
python -m pip install jinja2
python -m pip install nanoemoji
python -m pip install networkx
python -m pip install ninja
python -m pip install opentype-sanitizer
python -m pip install packaging
python -m pip install pillow
python -m pip install pygithub
python -m pip install pyyaml
python -m pip install requests
python -m pip install rich
python -m pip install ruamel-yaml
python -m pip install setuptools
python -m pip install skia-pathops
python -m pip install statmake
python -m pip install strictyaml
python -m pip install tabulate
python -m pip install ttfautohint-py
python -m pip install unidecode
python -m pip install vharfbuzz
python -m pip install vttlib
