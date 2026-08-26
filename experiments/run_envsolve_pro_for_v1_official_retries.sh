#!/usr/bin/env bash

set -u -o pipefail

case_file="experiments/cases/dev_pro_bad_case_census_v1_209.jsonl"
config="experiments/configs/spark_envsolve_pro_for_v1_openrouter.json"
protocol="experiments/protocols/envbench_python_minimal_integrity_v1.json"
runs_root="runs/envsolve-pro-for-v1-consumed6-openrouter"
model="deepseek/deepseek-v4-flash-0731"

retry_official() {
  local case_id="$1"
  local source_run_id="$2"
  local case_slug="$3"
  local retry_run_id="$4"
  local method="$5"
  local seed="$6"
  local source_root="${runs_root}/${source_run_id}/${case_slug}"

  .venv/bin/python experiments/evaluate_only.py \
    --case-file "${case_file}" \
    --case-id "${case_id}" \
    --script "${source_root}/scripts/bootstrap.sh" \
    --config "${config}" \
    --run-id "${retry_run_id}" \
    --protocol "${protocol}" \
    --method "${method}" \
    --model "${model}" \
    --seed "${seed}" \
    --source-run "${source_root}"
}

retry_official \
  "envbench-python-rollbar__pyrollbar@8493ac03c3468c2349c968726adffa5fd5661d0e" \
  "pro-for-v1-consumed6-04-pyrollbar-FO" \
  "envbench-python-rollbar__pyrollbar__8493ac03c3468c2349c968726adffa5fd5661d0e" \
  "pro-for-v1-consumed6-04-pyrollbar-FO-official-infra-retry1" \
  "free-feedback-search-public-goal" \
  824003

retry_official \
  "envbench-python-rollbar__pyrollbar@8493ac03c3468c2349c968726adffa5fd5661d0e" \
  "pro-for-v1-consumed6-06-pyrollbar-F" \
  "envbench-python-rollbar__pyrollbar__8493ac03c3468c2349c968726adffa5fd5661d0e" \
  "pro-for-v1-consumed6-06-pyrollbar-F-official-infra-retry1" \
  "free-feedback-search-repository-signals" \
  824003

retry_official \
  "envbench-python-langchain-ai__langgraph@070b339b67d64773fbfdf296a52a334fa27af2ac" \
  "pro-for-v1-consumed6-08-langgraph-F" \
  "envbench-python-langchain-ai__langgraph__070b339b67d64773fbfdf296a52a334fa27af2ac" \
  "pro-for-v1-consumed6-08-langgraph-F-official-infra-retry1" \
  "free-feedback-search-repository-signals" \
  824008

retry_official \
  "envbench-python-langchain-ai__langgraph@070b339b67d64773fbfdf296a52a334fa27af2ac" \
  "pro-for-v1-consumed6-09-langgraph-FO" \
  "envbench-python-langchain-ai__langgraph__070b339b67d64773fbfdf296a52a334fa27af2ac" \
  "pro-for-v1-consumed6-09-langgraph-FO-official-infra-retry1" \
  "free-feedback-search-public-goal" \
  824008

retry_official \
  "envbench-python-nonebot__nonebot2@7b724925badfe7133979c3d4d90a15054cdebabd" \
  "pro-for-v1-consumed6-16-nonebot2-FO" \
  "envbench-python-nonebot__nonebot2__7b724925badfe7133979c3d4d90a15054cdebabd" \
  "pro-for-v1-consumed6-16-nonebot2-FO-official-infra-retry1" \
  "free-feedback-search-public-goal" \
  824016

retry_official \
  "envbench-python-nonebot__nonebot2@7b724925badfe7133979c3d4d90a15054cdebabd" \
  "pro-for-v1-consumed6-17-nonebot2-F" \
  "envbench-python-nonebot__nonebot2__7b724925badfe7133979c3d4d90a15054cdebabd" \
  "pro-for-v1-consumed6-17-nonebot2-F-official-infra-retry1" \
  "free-feedback-search-repository-signals" \
  824016
