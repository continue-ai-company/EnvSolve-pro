envsolve_artifact_tmp="$(mktemp -d)"
mv -- "build_output" "$envsolve_artifact_tmp/build_output"
python -m pip install --no-build-isolation -e .
mv -- "$envsolve_artifact_tmp/build_output" "build_output"
rmdir -- "$envsolve_artifact_tmp"

