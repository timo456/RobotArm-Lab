# Known limitations

## v0.2.0 workstation scope

The Qt station uses a dedicated control worker and GPU/software OpenGL renderer.
Planning no longer blocks the GUI event loop. Actual widget/framebuffer captures and
QTest inputs verify layout and interaction; native Windows desktop-capture/input
APIs were unavailable on this host. Qt 100/125/150% scale tests do not claim that
global OS display settings or every multi-monitor transition were tested.

The original control, collision and dynamics limitations below remain. Visual shells,
fingers and the bench are cosmetic and can extend beyond the unchanged collision
proxies. Clearance is measured only for those proxies. There is no gripping/contact
dynamics, payload simulation, calibration, industrial fieldbus or physical brake.

Pause and active speed changes hold and replan from rest; they are not jerk-limited
trajectory blending. Freeze cancels path sampling cooperatively; the original bounded
IK solver is not interruptible inside every numerical operation. Shutdown waits for
the worker; no forced unsafe thread termination is used. Fixed-step execution may
lag wall time under CPU load. FPS/timing results are machine-specific.

Teach storage is a bounded local JSON library, not a versioned industrial program
format. Obstacles are boxes; edits invalidate previews. There is no autonomous path
rerouting or collision avoidance. The 500-row event view is bounded but JSONL files
on disk are append-only; users must archive them when needed. The UI is English;
this repository provides a Traditional Chinese user guide, not a localized Qt UI.

This is an installable Python wheel/source project, not a signed standalone Windows
installer. Fresh Windows Python 3.12 clones require C++ tools or a trusted local
PyBullet wheel. A bundled executable would require additional dependency notices
and redistribution/source handling. See the current workstation validation report
for measured results and remote CI evidence.

## Historical v0.1.1 scope

The GUI/CI statements in this historical section describe the original Tk delivery;
use `WORKSTATION_VALIDATION.md` for v0.2.0 status.

Version 0.1.1 adds fail-closed sampling budgets, geometric IK branches and bounded scene
resources. These improve reliability within the documented model; they do not change
the simulation's physical-safety scope. See `RELEASE_READINESS_v0.1.1.md` for current evidence.

- Kinematic position playback only. No dynamics, gravity compensation, PID tracking,
  friction, actuator saturation, payload calibration, torque limits or hardware I/O.
  URDF inertial values are placeholders. No physical-device safety certification.
- Discrete collision checking with conservative margin, not continuous collision
  detection. Thin obstacles and unsampled configurations may be missed. Adjacent links
  are excluded; primitive geometry omits cables, fixtures and detailed housings.
- Arbitrary scene insertion may intersect the current arm. Runtime checks freeze the
  arm but cannot undo an overlap introduced by the user.
- Straight joint-space PTP only. Blocked paths are rejected, not rerouted. No RRT,
  Cartesian straight-line constraint, via-point blending or jerk bounds.
- Numerical IK is deterministic but not globally complete. Different seeds may find
  different branches. A failed solve may be a local minimum or a singularity, not an
  unreachable pose. Feasible IK is still subject to the collision gate.
- Geometric branch construction assumes the RAL-6 spherical-wrist dimensions. It is
  not a generic IK solution for arbitrary URDFs. Singularities may have infinitely many
  solutions; the frozen corpus cannot prove universal convergence.
- Unsupported sampling precision or over-budget paths are rejected instead of coarsened.
  This is a resource-safety policy, not evidence that rejected paths are collision-free.
- Native keyboard operation was exercised locally. Automated desktop screenshot capture
  and coordinate clicks were unavailable on the host; pixel layout and mouse-only
  end-to-end operation are not claimed verified by that evidence.
- GUI uses CPU rendering and fixed simulation ticks; wall-clock timing is not real-time.
  Synchronous IK/planning can briefly pause the GUI before movement begins.
- STOP and reset are simulation operations. Stop creates an instantaneous velocity
  discontinuity; reset explicitly teleports. Normal accepted PTP motion is smooth.
- The local tested OS/interpreter is recorded in `reports/verified/results.json`.
  GitHub-hosted CI has not run until the user publishes and enables Actions.
- Numerical tolerances, model fidelity and benchmark cases establish only the stated
  test envelope; they are not evidence for all possible robot configurations.
