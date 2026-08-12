set -e

VENV_DIR="${BAYBE_BOOTSTRAP_VENV:-/tmp/envsolve-baybe-8afb0ff99655d34176fa7dc52ec488e3773103d3-py311}"
python3.11 -m venv "$VENV_DIR"
. "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install --no-deps -e "$PWD"
python -m pip install --no-deps \
  attrs==26.1.0 \
  cattrs==26.1.0 \
  exceptiongroup==1.3.1 \
  funcy==2.0 \
  numpy==1.26.4 \
  pandas==3.0.5 \
  protobuf==3.20.3 \
  scipy==1.17.1 \
  scikit-learn==1.9.0 \
  scikit-learn-extra==0.3.0 \
  torch==2.1.2 \
  botorch==0.18.1 \
  gpytorch==1.15.2 \
  ngboost==0.5.11 \
  setuptools-scm==10.2.1 \
  opentelemetry-api==1.44.0 \
  opentelemetry-sdk==1.44.0 \
  opentelemetry-proto==1.44.0 \
  opentelemetry-exporter-otlp==1.44.0 \
  opentelemetry-exporter-otlp-proto-common==1.44.0 \
  opentelemetry-exporter-otlp-proto-grpc==1.44.0 \
  opentelemetry-propagator-aws-xray==1.0.2 \
  opentelemetry-sdk-extension-aws==2.1.0 \
  pytest==9.1.1 \
  hypothesis==6.165.2 \
  matplotlib==3.11.1 \
  plotly==6.9.0 \
  sphinx==9.0.4 \
  skl2onnx==1.20.0 \
  onnx==1.22.0 \
  onnxruntime==1.28.0 \
  rdkit==2026.3.5 \
  mordredcommunity==2.0.7 \
  xyzpy==1.3.4 \
  xarray==2026.7.0 \
  joblib==1.5.3
