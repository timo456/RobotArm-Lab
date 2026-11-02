"""Fixed-seed protocol. Every case is retained; failed gates produce nonzero CLI exit."""

import hashlib
import importlib.metadata
import json
import platform
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np

from .config import Config
from .controller import Controller
from .kinematics import fk, pose_error, solve_ik
from .model import HOME, LOWER, UPPER, CommandError, Pose
from .simulation import World
from .trajectory import plan


def benchmark(config: Config, protocol: Path, output: Path) -> dict:
    raw = protocol.read_bytes()
    gates = json.loads(raw)
    rng = np.random.default_rng(gates["seed"])
    cases: list[dict] = []
    fk_times: list[float] = []
    ik_times: list[float] = []
    violation_count = 0
    executed_collisions = 0
    with World() as world:
        for i in range(gates["fk_samples"]):
            q = rng.uniform(LOWER, UPPER)
            start = perf_counter()
            actual = fk(q)
            fk_times.append((perf_counter() - start) * 1000)
            world.set_q(q)
            pe, re = pose_error(actual, world.tcp())
            cases.append(
                dict(
                    group="fk",
                    index=i,
                    q=q.tolist(),
                    position_error=pe,
                    orientation_error=re,
                    elapsed_ms=fk_times[-1],
                )
            )
        for group, count in [
            ("normal_ik", gates["normal_ik_samples"]),
            ("boundary_ik", gates["boundary_ik_samples"]),
        ]:
            for i in range(count):
                q = rng.uniform(LOWER * 0.65, UPPER * 0.65)
                seed = HOME.copy()
                if group == "boundary_ik":
                    j = i % 6
                    q[j] = (LOWER[j] + 1e-5) if i < 6 else (UPPER[j] - 1e-5)
                    seed = np.clip(q + rng.normal(0, 0.04, 6), LOWER, UPPER)
                # Target from the independent simulator, not our FK.
                world.set_q(q)
                target = world.tcp()
                start = perf_counter()
                record = dict(group=group, index=i, target_q=q.tolist(), seed=seed.tolist())
                try:
                    result = solve_ik(target, seed, config)
                    world.set_q(result.q)
                    pe, re = pose_error(world.tcp(), target)
                    violations = int(np.sum((result.q < LOWER) | (result.q > UPPER)))
                    violation_count += violations
                    record.update(
                        success=pe <= gates["ik_position_max_m"]
                        and re <= gates["ik_orientation_max_rad"],
                        q=result.q.tolist(),
                        position_error=pe,
                        orientation_error=re,
                        attempts=result.attempts,
                        joint_limit_violations=violations,
                    )
                except CommandError as exc:
                    record.update(success=False, reason=str(exc))
                ik_times.append((perf_counter() - start) * 1000)
                record["elapsed_ms"] = ik_times[-1]
                cases.append(record)
        for i, xyz in enumerate([[2, 0, 0.4], [0, 0, 2], [-3, 0, 0], [0, -4, 1]]):
            try:
                solve_ik(Pose(np.array(xyz), np.eye(3)), HOME, config)
                rejected = False
            except CommandError:
                rejected = True
            cases.append(dict(group="unreachable", index=i, rejected=rejected))

        world.set_q(HOME)
        control = Controller(world, config)
        # Three blockers at target, with distinct orientations of the arm.
        for i, yaw in enumerate([-0.6, -0.3, 0.4]):
            target = HOME.copy()
            target[0] = yaw
            world.add_box(fk(target).position, [0.035, 0.035, 0.035])
            before = control.q
            try:
                control.move(target)
                rejected = False
                control.stop()
            except CommandError:
                rejected = True
            cases.append(
                dict(
                    group="collision",
                    index=i,
                    rejected=rejected,
                    unchanged=bool(np.array_equal(before, control.q)),
                )
            )
            world.clear_obstacles()

        velocity_ratio = acceleration_ratio = 0.0
        for i in range(8):
            target = HOME + rng.uniform(-0.18, 0.18, 6)
            try:
                trajectory = control.move(target)
            except CommandError as exc:
                cases.append(
                    dict(
                        group="execution",
                        index=i,
                        steps=0,
                        completed=False,
                        target_q=target.tolist(),
                        reason=str(exc),
                        endpoint_error=float(np.max(np.abs(control.q - target))),
                    )
                )
                continue
            delta = np.abs(trajectory.goal - trajectory.start)
            velocity_ratio = max(
                velocity_ratio, float(np.max(1.875 * delta / trajectory.duration / config.velocity))
            )
            acceleration_ratio = max(
                acceleration_ratio,
                float(
                    np.max(
                        (10 * np.sqrt(3) / 3) * delta / trajectory.duration**2 / config.acceleration
                    )
                ),
            )
            steps = 0
            while control.state == "RUNNING":
                control.step()
                steps += 1
                executed_collisions += len(world.collisions(control.q, 0.0))
                violation_count += int(np.sum((control.q < LOWER) | (control.q > UPPER)))
            cases.append(
                dict(
                    group="execution",
                    index=i,
                    target_q=target.tolist(),
                    steps=steps,
                    completed=control.state == "IDLE",
                    endpoint_error=float(np.max(np.abs(control.q - target))),
                )
            )
        # Independently test wide-limit trajectories mathematically, without executing unsafe poses.
        for _ in range(100):
            trajectory = plan(rng.uniform(LOWER, UPPER), rng.uniform(LOWER, UPPER), config)
            delta = np.abs(trajectory.goal - trajectory.start)
            velocity_ratio = max(
                velocity_ratio, float(np.max(1.875 * delta / trajectory.duration / config.velocity))
            )
            acceleration_ratio = max(
                acceleration_ratio,
                float(
                    np.max(
                        (10 * np.sqrt(3) / 3) * delta / trajectory.duration**2 / config.acceleration
                    )
                ),
            )

    def subset(group: str) -> list[dict]:
        return [c for c in cases if c["group"] == group]

    summary = {
        "fk_position_max_m": max(c["position_error"] for c in subset("fk")),
        "fk_orientation_max_rad": max(c["orientation_error"] for c in subset("fk")),
        "normal_ik_success_min": float(np.mean([c["success"] for c in subset("normal_ik")])),
        "boundary_ik_success_min": float(np.mean([c["success"] for c in subset("boundary_ik")])),
        "unreachable_rejection_rate_min": float(
            np.mean([c["rejected"] for c in subset("unreachable")])
        ),
        "collision_rejection_rate_min": float(
            np.mean([c["rejected"] for c in subset("collision")])
        ),
        "executed_collision_count_max": executed_collisions,
        "joint_limit_violations_max": violation_count,
        "fk_p95_ms_max": float(np.percentile(fk_times, 95)),
        "ik_p95_ms_max": float(np.percentile(ik_times, 95)),
        "trajectory_limit_ratio_max": max(velocity_ratio, acceleration_ratio),
    }
    checks = {
        name: value >= gates[name] if name.endswith("_min") else value <= gates[name]
        for name, value in summary.items()
    }
    checks["all_executions_completed"] = all(c["completed"] for c in subset("execution"))
    checks["collision_rejections_atomic"] = all(c["unchanged"] for c in subset("collision"))
    checks["endpoint_error_below_1e-10"] = all(
        c["endpoint_error"] < 1e-10 for c in subset("execution")
    )
    ik_returned = [c for c in cases if c["group"].endswith("_ik") and "position_error" in c]
    summary["ik_position_max_m"] = max((c["position_error"] for c in ik_returned), default=None)
    summary["ik_orientation_max_rad"] = max(
        (c["orientation_error"] for c in ik_returned), default=None
    )
    for name in ("ik_position_max_m", "ik_orientation_max_rad"):
        checks[name] = summary[name] is not None and summary[name] <= gates[name]
    source_hash = hashlib.sha256()
    for path in sorted(Path(__file__).parent.rglob("*")):
        if path.suffix in (".py", ".json", ".urdf"):
            source_hash.update(path.relative_to(Path(__file__).parent).as_posix().encode())
            # Normalize line endings so Git checkouts on Windows/Linux share a digest.
            source_hash.update(path.read_text(encoding="utf-8").encode("utf-8"))
    result = dict(
        passed=all(checks.values()),
        checks=checks,
        summary=summary,
        cases=cases,
        protocol=gates,
        protocol_sha256=hashlib.sha256(raw).hexdigest(),
        source_sha256=source_hash.hexdigest(),
        created_utc=datetime.now(UTC).isoformat(),
        environment={
            "python": platform.python_version(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "packages": {
                p: importlib.metadata.version(p) for p in ["numpy", "scipy", "pybullet", "pillow"]
            },
        },
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(
        json.dumps(result, indent=2, allow_nan=False), encoding="utf-8"
    )
    lines = [
        "# Reproducible engineering experiment",
        "",
        f"Overall: **{'PASS' if result['passed'] else 'FAIL'}**",
        "",
        f"Protocol SHA-256: `{result['protocol_sha256']}`",
        "",
        "| Metric | Measured | Predeclared threshold | Pass |",
        "|---|---:|---:|---|",
    ]
    for name, value in summary.items():
        measured = "n/a" if value is None else f"{value:.8g}"
        lines.append(
            f"| {name} | {measured} | {gates.get(name, '—')} | {checks.get(name, 'per-case')} |"
        )
    lines += [
        "",
        "Normal IK: cold HOME seed, targets from PyBullet. Boundary IK: warm perturbed seed;",
        "one joint within 1e-5 rad of each bound. These cases test IK feasibility, "
        "not collision-free reachability.",
        "Latency is host-dependent and includes failed solves. "
        "Every attempted case is in results.json.",
        "Execution uses eight local collision-free moves; "
        "the collision gate tests three obstructed commands.",
        "Sampled collision checking is not continuous collision detection "
        "or a physical safety guarantee.",
    ]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
