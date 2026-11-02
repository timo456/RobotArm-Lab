# v0.1.1 Engineering Hardening & Release Readiness

Local platform: Windows 10 build 19045, CPython 3.12.3, original PyBullet 3.2.7 built
locally from upstream source in v0.1.0. No replacement fork or proprietary model.

## Decision and authoritative evidence

**Local engineering GO**, subject to the machine-readable
[`decision.json`](../reports/v0.1.1/decision.json) and its underlying results remaining
consistent with the release source. This is permission to review the local candidate,
not a claim that remote CI passed or that a public release occurred. Any failed local
gate makes the candidate **NO-GO**; no acceptance thresholds were relaxed.

| Requirement | Evidence / method |
|---|---|
| P1 allocation fix | `tests/test_resources.py`, before/after JUnit, 1,000-request stress in `final/results.json` |
| IK cold/limits/singular/unreachable | 176 frozen targets, independent PyBullet pose validation, per-attempt diagnostics |
| Thin/random obstacles | 48 explicit scenes, 16 known thin contacts, 0.0005-rad reference comparison |
| Trajectory/input/resource limits | Unit/integration cases, 100 random trajectories, primitive-shape/render bounds |
| Windows / Python 3.12 / PyBullet | Actual native library imports, simulator execution, JSON environment records |
| GUI | Native keyboard action trace plus 16 real-Tk callback/mainloop/fault checks |
| Clean rebuild and wheel | New venv, no system-site packages, no-index binary install, `-I` package-origin check, tests and Demo |
| Existing behavior | Original `acceptance.json` re-executed under v0.1.1 in `legacy-regression/` |
| Traceability | Immutable protocol/corpus commits, baseline source at `0d4999c`, source/protocol/corpus/harness hashes |

All evidence paths in the table are relative to `reports/v0.1.1/` unless otherwise
specified. [Controlled comparison](../reports/v0.1.1/comparison.md) reports success
rates, p50/p95, retained failures and memory separately. Full cases are in
[`final/results.json`](../reports/v0.1.1/final/results.json) and
[`baseline-replay/results.json`](../reports/v0.1.1/baseline-replay/results.json).

## Repairs and observed results

- P1: configuration now rejects unsupported tiny, subnormal and non-scalar steps.
  Sampling checks budget **before** division/allocation and streams at the original
  requested spacing. Accepted paths contain at most 10,000 samples, including endpoints.
  The baseline's unsafe allocation was intercepted in the audit; an actual OOM was
  intentionally not triggered. This intervention is explicit in the baseline report.
- Controlled replay: old cold IK **79/80**, boundary **45/48**; new **80/80** and **48/48**.
  Singular **24/24** and unreachable rejection **24/24**. Failed old case IDs are
  **12, 81, 83, 98**. Their residuals and repaired attempt traces are retained. The old
  eight-start search failed to meet tolerances; shoulder/elbow/wrist geometric branches
  supply alternatives without expanding the eight-attempt budget or weakening errors.
  Geometric enumeration adds a few milliseconds to median solve time; not every latency
  improves. Cold/boundary p95 improves substantially while singular p95 rises modestly;
  the comparison table retains both p50 and p95 rather than reporting only improvements.
- The user-supplied ratios had no original target identities in the checkout. Our new
  frozen corpus reproduces those numerical ratios independently; identity with the
  user's original cases remains unknown and is not claimed.
- 48 collision scenes include 38 reference contacts. No misses relative to the dense
  discrete reference and no pose changes from rejected commands. This does not prove
  continuous collision safety or eliminate geometric-model error.
- Other audit repairs: stale numeric PyBullet client IDs, native shape accumulation,
  log-I/O failure, timer cancellation/recovery, small SO(3) validation slack, render
  allocation bounds, pathological durations and timing arithmetic overflow.

## GUI verification boundaries

Native `sky.press_key` inputs reached the real Windows Tk window. Independent app
events show Demo, Home, obstacle insertion, collision rejection, clear, Stop, Reset and
IK. See [`native-gui.json`](../reports/v0.1.1/native-gui.json).
Escape reached the app after that native motion had completed; **native stopping during
motion is not claimed**. Controller and callback tests separately test stopping while
running. Alt+F4 closed the app and its process exited successfully.

Native window capture returned `window capture timed out: timed out waiting on channel`;
coordinate click returned `coordinate input geometry is unavailable`. Pixel screenshot
and mouse-only end-to-end operation remain unverified. The 3D viewport and GIF are real
PyBullet CPU renders, not fabricated desktop screenshots. Tk tests verify control bounds,
rendered images, messages, scheduling, injected I/O/render failures and recovery.

## Dependencies, CI and reproducibility

Official PyPI has a Linux CPython 3.11 wheel but no Windows CPython 3.12 wheel for
[PyBullet 3.2.7](https://pypi.org/project/pybullet/3.2.7/#files). Linux CI therefore
requires binary resolution. Windows CI uses the wheelhouse cache and compiles only on
a cache miss through an explicit flag. A fresh Windows checkout still needs C++ tools
once or a trusted compatible wheel. The ignored local cache is not part of Git.

The clean reconstruction installed dependencies offline from hashed wheelhouse files,
installed the project wheel without editable metadata, and ran isolated tests and a
rendered demo. Existing runtime `.venv` and other projects were not replaced. Versions
are pinned; wheel hashes are evidence for this build, not a universal cross-platform lock.

Both comparison runs use the same frozen corpus/harness and are finally executed in
sequence with the interactive GUI closed. Earlier runs, including concurrent runs,
are retained separately and are not substituted for the final sequential latency table.

## Unverified / unresolved items

- GitHub-hosted Windows and Linux jobs have not run: no remote repository was created
  or pushed. Linux library execution and a second physical machine remain unverified.
- Native mouse interaction and pixel capture are unavailable through this host's
  automation helper. Keyboard operation was verified; no inference of mouse/pixel pass.
- The original extra-test identities behind the user-supplied rates remain unavailable.
- Numerical IK is not proved globally complete; model-specific analytic branch logic
  must change if robot geometry changes. Singular configurations can have nonunique solutions.
- Simulation remains kinematic. No actuator dynamics, physical braking, hardware
  tracking or safety certification. No unresolved **known local software correctness
  blocker** is claimed only when all local gates and packaged-source checks pass.

## GitHub release preparation checklist

- [x] Prespecify and commit hardening protocol and replay corpus before IK changes.
- [x] Preserve v0.1.0 evidence; retain pre-fix failures and comparative results.
- [x] Run local unit/integration/abnormal/resource/latency tests and installed-wheel tests.
- [x] Provide English README, Traditional Chinese guide, architecture, MIT license,
  third-party notices, actual rendered demo and [release notes](../CHANGELOG.md).
- [x] Keep environment, caches, reports and build output on E:; exclude bulky runtime data from Git.
- [ ] Execute remote GitHub Actions after the owner creates/pushes the repository.
- [ ] Review mouse/pixel behavior on a desktop where capture/input geometry is available.
- [ ] Owner authorizes public release and performs publishing steps in `PUBLISHING.md`.

Nothing was publicly published. Do not change unchecked items into completed checks
without new evidence. For any failed gate, publish a NO-GO report instead of a release.
