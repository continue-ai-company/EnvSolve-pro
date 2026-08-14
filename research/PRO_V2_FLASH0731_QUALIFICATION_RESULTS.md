# EnvSolve-Pro V2: DeepSeek V4 Flash 0731 Qualification

Status: qualified on one consumed development case; not effectiveness evidence.

## Decision

Subsequent API experiments use the pinned model ID
`deepseek/deepseek-v4-flash-0731` on the frozen Cloudflare provider. We do not use the
moving `flash-latest` alias. The prior V4 Pro Dev-12 remains a historical pilot and is
never pooled with Flash outcomes.

## Evidence

The API catalog exposed the required reasoning and tool parameters, and a synthetic
canary returned the requested function call. The full B-FSR qualification then ran 53
continuous model requests and 49 construction-shell calls without a provider error.
Clean replay rejected programs at requests 35 and 50; the session repaired the complete
program, passed replay at request 52, and submitted the exact certified hash at request
53. The unchanged script passed the Official evaluator with `issues_count=0`.

The source Official attempt was a non-executed host preflight because detached `PATH`
did not contain `uv`. A preregistered exact-script retry added the existing Spark
`.venv/bin` to host `PATH`; it did not rerun the model or change the script.

## Resource Signal

On the same consumed `mov-cli` case, Flash B used 53 requests, 1,153,483 tokens, and
about 649 seconds, versus 15 requests, 158,559 tokens, and about 172 seconds for the
prior Pro B run. Flash therefore used 7.27x the tokens, while its provider-reported
cost was 66.7% lower. One case cannot rank models, but it proves that token, time,
dollar cost, and success must remain separate axes.

## Boundary

This qualification supports model-interface compatibility, feedback-conditioned repair,
and one Official success. It does not show that Flash is more accurate or more efficient
than Pro. The next effectiveness batch must be frozen before execution and must compare
A and B on the same Flash snapshot.
