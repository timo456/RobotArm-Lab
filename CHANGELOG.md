# Release notes

## 0.1.1 — Engineering hardening (2026-11-03)

### Fixed

- **P1:** collision sampling now validates a finite scalar step in [1e-6,0.02] rad,
  rejects paths requiring over 10,000 samples before allocation/query, and streams
  accepted samples with O(1) storage. Endpoints and requested spacing are preserved.
  Rejection is explicit; it does not claim clearance and never silently coarsens a path.
- IK enumerates shoulder/elbow/XYX wrist branches from the RAL-6 wrist-center geometry,
  retains bounded least-squares refinement and validates every result independently.
  Wrist-center reach-annulus rejection handles geometrically impossible poses quickly.
  Per-attempt residuals, solver termination and active-bound counts are recorded.
- Idempotent world close cannot disconnect a newer client that reused its numeric ID.
  Closed worlds reject operations. Repeated equal-size boxes reuse shapes; 128 active
  obstacles and 128 distinct shapes are bounded; scene reset reclaims native geometry.
- Log-write failure freezes the controller in FAULT rather than silently losing audit
  events. GUI timer lifetime and I/O errors are handled; normal input errors remain visible.
- Scalar/type validation, render allocation bounds, and finite trajectory duration
  [1e-6,3600] s reject pathological inputs before native calls/numerical overflow.

### Added

- Frozen extended protocol and explicit corpus: 80 full-range cold IK, 48 cold boundary,
  24 singular, 24 unreachable, 48 obstacle scenes and 100 trajectories; resource stress
  and abnormal-input regressions. Original v0.1.0 evidence remains unchanged.
- Real keyboard shortcuts: F5 Home, F6 Demo, F7 blocker, F8 clear, F9 reset, Esc freeze,
  Ctrl+L focus TCP X, Ctrl+I solve IK, Ctrl+Enter execute joints.
- Wheelhouse preparation that reuses trusted compatible local wheels, binary-only
  dependency downloads and explicit opt-in source builds. Offline clean-venv verification.
- CI wheel caching, Linux binary-only PyBullet resolution, explicit Windows build on
  cache miss, hardening gates and isolated installed-wheel tests.

### Compatibility / limits

`Trajectory.collision_samples` now returns an iterator; wrap it in `list` only when
small materialization is explicitly needed. Resource-over-budget requests that formerly
attempted allocation now raise CommandError. GUI Reset clears native shape caches.
This remains a kinematic simulator with sampled collision checks, not continuous collision
certification or a hardware safety controller. Official PyBullet 3.2.7 still has no
Windows CPython 3.12 wheel: a trusted cached wheel or one explicit C++ source build is needed.

Read `docs/RELEASE_READINESS_v0.1.1.md` for the measured decision and unverified environments.

## 0.1.0

Initial six-axis kinematics, quintic PTP control, collision rejection, Tk station,
fixed-seed experiment, demo media and local packaging. Historical commit: `0d4999c`.
