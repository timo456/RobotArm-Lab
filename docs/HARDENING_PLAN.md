# v0.1.1 audit and frozen verification plan

Baseline: `0d4999c` (v0.1.0); clean worktree inspected before changes.
Existing source, tests, reports, GUI and build/CI scripts were read. Historical
`reports/verified`, `reports/first-run`, `reports/pytest.xml`, GUI and wheel evidence
remain unchanged; new evidence goes under `reports/v0.1.1/`.

## Issues and ordered fixes

1. **P1 confirmed by source:** Config permits arbitrarily small positive collision
   steps; Trajectory allocates a full `(ceil(max|dq|/step)+1,6)` linspace without a
   resource cap. A tiny step can overflow or exhaust memory. Fix with validation,
   checked count calculation before division/allocation, bounded lazy iteration and
   fail-closed rejection if the requested precision exceeds the work budget. Preserve
   endpoints and requested maximum spacing. Never silently increase the step.
2. IK currently has eight starts, finite-difference Jacobians and limited branch
   coverage. Add explicit cold/full-range, cold-boundary, singular and unreachable
   cohorts; retain every failed case. Investigate geometric branch coverage and bounded
   solver termination, not success-rate rounding. The cited 79/80 and 45/48 figures have
   no accompanying seeds/targets in source or outputs; do not invent their provenance.
3. Existing collision tests are useful but narrow. Add known-contact thin fixtures,
   seeded random boxes, dense-reference comparison, extreme joint poses, abnormal
   scalar/array inputs and full-range trajectory derivative/limit checks. A dense
   discrete reference is not ground-truth continuous collision detection.
4. Official PyBullet 3.2.7 has no Windows CPython 3.12 wheel. Prefer a compatible cached
   local wheel, expose an explicit source-build path, cache the built wheel in CI and
   enforce binary-only resolution for the Linux 3.11 job. Do not silently substitute an
   unreviewed similarly named fork. Build a fresh isolated environment on E: and test
   the installed project wheel without editable paths or system site packages.
5. GUI callbacks/mainloop were tested but native capture timed out. Attempt actual
   OS interaction again; distinguish it from widget callbacks. Audit file-I/O errors,
   timer lifetime, closed simulator clients, and scene resources. Record unavailable
   capture/external environments without claiming success.
6. Update version, docs, release notes, comparison, notices and release checklist;
   inspect tracked contents, package data, Git diff and history. Local commits only.

## Fixed experiment specification (before fixes)

`acceptance-v0.1.1.json` freezes seeds, counts and gates. The corpus generator will
write explicit target q/poses and obstacle geometry before running the old/new solvers.
80 cold targets uniformly span the full limits; 48 boundary targets cover each joint,
each bound and offsets [0,1e-7,1e-3,1e-2], all seeded from HOME. 24 singular targets use
zero wrist pitch, zero elbow, or both. Targets come from PyBullet. 24 unreachable poses
cover outer reach, excessive wrist-center reach and the inner wrist-center void.
Require all reachable cases to meet 1e-4 m / 1e-3 rad; no threshold relaxation.

32 random box scenes and 16 thin-obstacle scenes are compared against 0.0005-rad
sampling, including deliberate known-contact samples. Report misses only relative to
this finite reference and report false positives separately. Use 100 random full-range
trajectories plus exact limits, malformed inputs and runtime scene changes.

Resource gate: at most 10,000 samples, O(1) streaming storage; unsupported precision
fails before simulator queries. Supported minimum step is 1e-6 rad, so very small
motions can still request that precision. Cap applies to total samples including both
endpoints. Stress 1,000 requests, peak traced allocation <8 MiB, RSS growth <32 MiB,
rejection p95 <10 ms. A rejected high-resolution plan is a rejection, not a collision-free
claim. Explicitly test subnormal floats and division-overflow inputs without performing
the vulnerable baseline allocation.

Release is **NO-GO** if any local mandatory gate fails, if P1 remains, if required
evidence is absent, or if a newly found correctness blocker is unresolved. Missing
remote GitHub/Linux execution must be separately marked unverified; it cannot be
reported as a CI pass. Local readiness and remote verification are separate decisions.
