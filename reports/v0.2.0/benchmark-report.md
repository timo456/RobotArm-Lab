# Reproducible engineering experiment

Overall: **PASS**

Protocol SHA-256: `27184d094561048598f120c0ba02490024b2af5f1b1366ad7a7eb0ffca039ee1`

| Metric | Measured | Predeclared threshold | Pass |
|---|---:|---:|---|
| fk_position_max_m | 5.5383994e-08 | 2e-06 | True |
| fk_orientation_max_rad | 3.2214665e-07 | 2e-06 | True |
| normal_ik_success_min | 1 | 0.95 | True |
| boundary_ik_success_min | 1 | 0.9 | True |
| unreachable_rejection_rate_min | 1 | 1.0 | True |
| collision_rejection_rate_min | 1 | 1.0 | True |
| executed_collision_count_max | 0 | 0 | True |
| joint_limit_violations_max | 0 | 0 | True |
| fk_p95_ms_max | 0.089715095 | 20 | True |
| ik_p95_ms_max | 45.9565 | 2000 | True |
| trajectory_limit_ratio_max | 1 | 1.000001 | True |
| ik_position_max_m | 2.0542029e-06 | 0.0001 | True |
| ik_orientation_max_rad | 5.5265221e-06 | 0.001 | True |

Normal IK: cold HOME seed, targets from PyBullet. Boundary IK: warm perturbed seed;
one joint within 1e-5 rad of each bound. These cases test IK feasibility, not collision-free reachability.
Latency is host-dependent and includes failed solves. Every attempted case is in results.json.
Execution uses eight local collision-free moves; the collision gate tests three obstructed commands.
Sampled collision checking is not continuous collision detection or a physical safety guarantee.
