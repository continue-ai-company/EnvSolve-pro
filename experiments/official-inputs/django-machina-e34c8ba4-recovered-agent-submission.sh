#!/usr/bin/env bash

if command python -m pip install --quiet --root-user-action=ignore \
  . \
  django-debug-toolbar \
  factory-boy \
  faker \
  pytest \
  sphinx-rtd-theme \
  pil-compat \
  x.py \
  pyright==1.1.402; then
  if [ ! -e "$PWD/tests/settings_local.py" ]; then
    : > "$PWD/tests/settings_local.py"
  fi
else
  false
fi
