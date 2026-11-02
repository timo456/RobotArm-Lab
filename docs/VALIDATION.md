# Validation record

Validated locally on Windows 10, CPython 3.12.3, using the project's independent
`.venv`. PyBullet 3.2.7 was compiled locally with existing Visual Studio 2022 Build
Tools. No system-wide installation was performed. Exact numerical dependency versions,
source digest and protocol digest are in [results.json](../reports/verified/results.json).
The source digest uses LF-normalized UTF-8 text to remain stable across Git platforms.

## Prespecified acceptance

`acceptance.json` was committed as the initial Git commit before the first test run.
Its bytes and thresholds were not changed after testing. Seed: 20261102. The experiment
contains 100 FK configurations, 24 cold-seeded normal IK targets, 12 warm-seeded
near-bound IK targets, four far-unreachable poses, three obstructed commands, and
eight executed paths. It also checks analytic limits on 100 wider joint-space paths.

| Measurement | Final result | Gate |
|---|---:|---:|
| FK position error, maximum | 5.5384e-8 m | <= 2e-6 m |
| FK orientation error, maximum | 3.2215e-7 rad | <= 2e-6 rad |
| Normal IK, cold Home seed | 24/24 | >= 95% |
| Near-bound IK, warm perturbed seed | 12/12 | >= 90% |
| IK position error, returned solutions | 2.0543e-6 m | <= 1e-4 m |
| IK orientation error, returned solutions | 5.5266e-6 rad | <= 1e-3 rad |
| Unreachable / obstructed rejection | 4/4 and 3/3 | 100% |
| Executed contacts / joint violations | 0 / 0 | 0 / 0 |
| FK / IK p95 latency | 0.136 / 17.56 ms | <= 20 / 2000 ms |
| Analytic velocity/acceleration limit ratio | 1.0000000000000002 | <= 1.000001 |

These values are from the committed final experiment, not promises for other hosts or
unseen configurations. Both IK errors are measured using the independent PyBullet link
frame. The 12 boundary targets are deliberately warm-seeded and must not be presented
as cold-start success. IK feasibility and collision-free motion are separate checks.

## Failure analysis and corrections

The [first run](../reports/first-run/results.json) met the aggregate gates but had one
IK failure: normal case 21 returned a best residual of 0.0164359 m / 0.209363 rad after
eight attempts. The target was known reachable from the simulator. Random-only restarts
had not covered the appropriate elbow/wrist branch. The fix adds seeds oriented toward
the target's bearing with both elbow and wrist branches, within the unchanged eight-
attempt budget. A specific independent-target regression test now covers this case.
The original failed record remains; it was not deleted or relabeled as unreachable.

During GUI smoke development, calling `tick` directly while its automatic scheduling
was enabled created duplicate timers in the **test harness**. The smoke script now
disables automatic scheduling for callback tests and tests the real scheduled mainloop
separately. No production timer behavior was removed.

## Verified execution and tooling

- 46 pytest cases passed, including floor/self/obstacle collision detection, blocked
  mid-path with safe endpoints, runtime scene changes, independent pose mismatch,
  invalid inputs, limits, singular straight-arm IK, derivatives and failure-report retention.
- Unit/integration coverage: approximately 67% of all package statements. Core controller
  coverage is 99%; FK/IK and trajectory coverage are 98%. GUI, CLI and demo are exercised
  separately and are not counted in that pytest coverage figure.
- Real Tk smoke passed 13 checks: rendered widget, control bounds, demo, Home,
  obstacle rejection and pose preservation, Stop, Reset, IK, invalid input messages,
  saved viewport, callback errors and scheduled mainloop ticks. See
  [GUI evidence](../reports/gui-smoke.json). This uses real widgets/application callbacks,
  not injected mouse clicks.
- The actual renderer produced `docs/media/demo.gif` (36 frames), `demo.png`, and
  274 executed-step telemetry rows with zero detected contacts. Raw demo telemetry is
  retained under `reports/demo/`.
- README bootstrap, CLI, dependency consistency, Ruff, source/wheel build and wheel
  package smoke are checked locally. Build assets are under ignored `dist/`.

## Not measured or not completed

- OS mouse/keyboard end-to-end automation and a captured desktop-window screenshot:
  Windows Computer Use capture returned `FrameArrived timed out` / `window capture timed out`
  on this host. GUI callbacks/mainloop and the actual 3D image were tested independently.
- GitHub Actions execution, Linux execution and a second clean machine: the workflow is
  configured for Ubuntu/Python 3.11 and Windows/Python 3.12, but has not run remotely.
- Physical dynamics, hardware feedback, braking and certified safety are outside this
  implementation's scope; see [limitations](LIMITATIONS.md).
- Publishing is intentionally not performed. No GitHub repository or remote was created.

Re-run the README commands to reproduce; latency will vary. Protocol and full case
records are more authoritative than this rounded narrative table.
