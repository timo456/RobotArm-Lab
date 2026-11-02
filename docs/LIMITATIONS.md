# Known limitations

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
- GUI uses CPU rendering and fixed simulation ticks; wall-clock timing is not real-time.
  Synchronous IK/planning can briefly pause the GUI before movement begins.
- STOP and reset are simulation operations. Stop creates an instantaneous velocity
  discontinuity; reset explicitly teleports. Normal accepted PTP motion is smooth.
- The local tested OS/interpreter is recorded in `reports/verified/results.json`.
  GitHub-hosted CI has not run until the user publishes and enables Actions.
- Numerical tolerances, model fidelity and benchmark cases establish only the stated
  test envelope; they are not evidence for all possible robot configurations.
