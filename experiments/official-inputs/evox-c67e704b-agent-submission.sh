python -m pip install --timeout 300 --retries 10 --root-user-action=ignore \
  "jax==0.4.34" \
  "jaxlib==0.4.34" \
  "optax==0.2.4" \
  "chex==0.1.90"
python -m pip install --timeout 300 --retries 10 --root-user-action=ignore -e "$PWD"
python -m pip install --timeout 300 --retries 10 --root-user-action=ignore --no-deps \
  "pytest==9.1.1" \
  "flax==0.12.8" \
  "plotly==6.9.0" \
  "gpjax==0.18.0" \
  "evoxbench==1.0.5" \
  "brax==0.14.2" \
  "gymnasium==1.3.0" \
  "grain==0.2.18" \
  "tensorflow-datasets==4.9.10" \
  "imageio==2.37.4" \
  "gym==0.26.2" \
  "envpool==1.2.5" \
  "ray==2.56.1"
