# EnvSolve-Pro Annotated Incremental Program V2

## Why V2 Exists

V1 exposed two shell-like actions: one for diagnosis and one for persistent changes. In
the fixed consumed qualification, the Agent made 69 ordinary shell calls and one program
operation call. HARK performed a real editable install through the ordinary shell. The
incremental-program hypothesis was therefore not tested because its action interface did
not activate naturally.

V2 changes only that interface. The Agent keeps one familiar arbitrary-Bash action,
`envbench_shell`, and declares the intended effect of every call:

- `effect=inspect`: execute in the construction environment, but do not add the command to
  the deployment program.
- `effect=persist`: execute in the same environment and, on success, append the exact
  command to the ordered deployment program.

The annotation is not a command classifier or permission boundary. The Agent may run any
Bash command under either value, and the harness does not infer packages or override the
choice. A wrong `inspect` annotation can still lose a required operation and is measured
as semantic bypass, not silently repaired by a rule.

## Three-Layer Algorithm

The Observation layer returns ordinary command output. After each successful `persist`,
it also executes the complete public goal. The Constraint layer is the current goal
residual or a clean-replay counterexample. The Operation layer is the same continuous
strong Agent using one arbitrary-Bash channel while deciding whether each action belongs
to the replayable program.

When the public goal passes, the harness immediately replays the accumulated program from
the target initial state. Replay failure returns to the same session for another
model-selected `persist` repair; replay success delivers the exact accumulated program.
Inspection, failed persistent attempts, and commands declared `inspect` are excluded.

V2 adds no package rule, command filter, checkpoint, cross-case memory, fixed observation
cadence, candidate graph, hash mechanism, frozen contract, or safety gate. Minimal B's
existing integrity boundary and clean-replay semantics are unchanged.

## Qualification

The first V2 run reuses the same three consumed cases as V1. This is a mechanism
qualification, not an effect estimate. It reports inspect/persist counts, the first
persist request, successful recorded steps, human-audited semantic bypasses, automatic
goal observations, replay outcomes, delivered program identity, Official outcome if
reached, and resources.

V2 qualifies its interface only if real deployment mutations use `persist` naturally and
every sufficient state reached after a recorded step triggers replay in the same tool
turn. It is rejected if the Agent still labels required deployment mutations as
`inspect`, if successful persistent commands are not recorded exactly, or if goal Pass
does not trigger replay. No success-rate claim is permitted from these cases.
