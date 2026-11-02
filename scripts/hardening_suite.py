"""Finite, auditable stress/IK/collision experiments with per-case retained evidence."""

import ctypes
import hashlib
import json
import os
import platform
import time
import tracemalloc
from dataclasses import replace
from pathlib import Path

import numpy as np

import robotarm_lab
from robotarm_lab.config import load_config
from robotarm_lab.controller import Controller
from robotarm_lab.kinematics import pose_error, solve_ik
from robotarm_lab.model import HOME, LOWER, UPPER, CommandError, Pose
from robotarm_lab.simulation import World
from robotarm_lab.trajectory import plan

ROOT = Path(__file__).resolve().parents[1]


def rss_bytes() -> int:
    if os.name == "nt":
        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                        *[(name, ctypes.c_size_t) for name in (
                            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                            "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                            "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess
        handle.restype = ctypes.c_void_p
        query = ctypes.windll.psapi.GetProcessMemoryInfo
        query.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
        if not query(handle(), ctypes.byref(counters), counters.cb):
            raise OSError("Unable to measure working set")
        return int(counters.WorkingSetSize)
    return int(Path("/proc/self/statm").read_text().split()[1])*os.sysconf("SC_PAGE_SIZE")


def stats(values: list[float]) -> dict:
    return dict(p50_ms=float(np.percentile(values, 50)), p95_ms=float(np.percentile(values, 95)),
                max_ms=max(values))


def run(output: Path, baseline: bool = False) -> int:
    output.mkdir(parents=True, exist_ok=True)
    protocol_bytes = (ROOT / "acceptance-v0.1.1.json").read_bytes()
    corpus_bytes = (ROOT / "tests/data/hardening-corpus.json").read_bytes()
    gates, corpus = json.loads(protocol_bytes), json.loads(corpus_bytes)
    config = load_config()
    records, collision_records = [], []
    start_rss = rss_bytes()
    with World() as world:
        for case in corpus["ik"]:
            target = Pose(np.array(case["position"]), np.array(case["rotation"]))
            record = dict(id=case["id"], group=case["group"])
            start = time.perf_counter()
            try:
                result = solve_ik(target, case["seed"], config)
                pe, re = pose_error(world.pose_at(result.q), target)
                violation = int(np.sum((result.q < LOWER) | (result.q > UPPER)))
                record.update(returned=True, position_error_m=pe, orientation_error_rad=re,
                              q=result.q.tolist(), attempts=result.attempts, violations=violation,
                              success=case["group"] != "unreachable" and violation == 0 and
                              pe <= gates["ik_position_max_m"] and
                              re <= gates["ik_orientation_max_rad"])
            except CommandError as exc:
                record.update(returned=False, reason=str(exc),
                              success=case["group"] == "unreachable")
            record["elapsed_ms"] = (time.perf_counter()-start)*1000
            records.append(record)
        for scene in corpus["scenes"]:
            world.clear_obstacles()
            world.set_q(scene["start"])
            world.add_box(scene["center"], scene["half_extents"])
            trajectory = plan(scene["start"], scene["goal"], config)
            known_contact = bool(world.collisions(scene["known_q"], 0))
            dense_contact = any(world.collisions(q, 0) for q in
                                trajectory.collision_samples(gates["collision_reference_joint_step"]))
            controller = Controller(world, config)
            before = controller.q
            start = time.perf_counter()
            try:
                controller.move(scene["goal"])
                rejected = False
                controller.stop()
            except CommandError:
                rejected = True
            collision_records.append(dict(id=scene["id"], group=scene["group"],
                                          reference_contact=dense_contact,
                                          known_contact=known_contact, rejected=rejected,
                                          unchanged=bool(np.array_equal(controller.q,before)),
                                          elapsed_ms=(time.perf_counter()-start)*1000))

    trajectory_ratio, violations = 0., 0
    for case in corpus["trajectories"]:
        trajectory = plan(case["start"], case["goal"], config)
        delta = np.abs(trajectory.goal-trajectory.start)
        trajectory_ratio = max(trajectory_ratio,
                               float(np.max(1.875*delta/trajectory.duration/config.velocity)),
                               float(np.max((10*np.sqrt(3)/3)*delta /
                                            trajectory.duration**2/config.acceleration)))
        for t in np.linspace(0, trajectory.duration, 101):
            q,_,_ = trajectory.sample(t)
            violations += int(np.sum((q < LOWER) | (q > UPPER)))

    # Instrument the vulnerable revision to record a dangerous allocation request without OOM.
    trajectory = plan(HOME, HOME+.1, config)
    unsafe_allocations = []
    original_linspace = np.linspace

    def allocation_guard(start, stop, num=50, *args, **kwargs):
        if num > gates["resource_max_samples"]:
            unsafe_allocations.append(int(num))
            raise RuntimeError("Audit prevented unsafe legacy allocation")
        return original_linspace(start, stop, num, *args, **kwargs)

    rejects, resource_cases, latencies = 0, [], []
    if baseline:
        np.linspace = allocation_guard
    stress_start_rss = rss_bytes()
    tracemalloc.start()
    try:
        for i in range(gates["resource_stress_repetitions"]):
            step = [1e-300, float(np.nextafter(0., 1.)), 1e-12, 1e-6][i % 4]
            start = time.perf_counter()
            try:
                # Force consumption too, to detect implementations deferring validation.
                for _ in trajectory.collision_samples(step):
                    pass
                reason, rejected = "accepted", False
            except CommandError as exc:
                reason, rejected = str(exc), True
            except (RuntimeError, OverflowError, ValueError) as exc:
                reason, rejected = str(exc), False
            elapsed = (time.perf_counter()-start)*1000
            rejects += rejected
            latencies.append(elapsed)
            if i < 4:
                resource_cases.append(dict(step=step, rejected=rejected, reason=reason))
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
        np.linspace = original_linspace
    stress_rss_growth = max(0,rss_bytes()-stress_start_rss)
    fine = plan(HOME, HOME+.008, config)
    start = time.perf_counter()
    previous, spacing, count = None, 0., 0
    for q in fine.collision_samples(1e-6):
        if previous is not None:
            spacing = max(spacing, float(np.max(np.abs(q-previous))))
        previous, count = q, count+1
    scan_ms = (time.perf_counter()-start)*1000
    summary = {}
    for group in ("cold", "boundary", "singular", "unreachable"):
        selected = [r for r in records if r["group"] == group]
        returned = [r for r in selected if r["returned"]]
        summary[group] = dict(total=len(selected), successes=sum(r["success"] for r in selected),
                              success_rate=sum(r["success"] for r in selected)/len(selected),
                              **stats([r["elapsed_ms"] for r in selected]),
                              max_position_error_m=max((r["position_error_m"] for r in returned),
                                                       default=None),
                              max_orientation_error_rad=max((r["orientation_error_rad"]
                                                             for r in returned),default=None))
    summary["collisions"] = dict(
        total=len(collision_records),
        reference_contacts=sum(r["reference_contact"] for r in collision_records),
        false_negatives=sum(r["reference_contact"] and not r["rejected"] for r in collision_records),
        conservative_rejections=sum(not r["reference_contact"] and r["rejected"]
                                    for r in collision_records),
        pose_changes=sum(not r["unchanged"] for r in collision_records),
        **stats([r["elapsed_ms"] for r in collision_records]))
    summary["resources"] = dict(rejections=rejects, requests=len(latencies),
                                peak_tracemalloc_bytes=peak, rss_growth_bytes=stress_rss_growth,
                                process_rss_bytes=rss_bytes(), initial_rss_bytes=start_rss,
                                audit_prevented_allocations=len(unsafe_allocations),
                                supported_samples=count, supported_max_spacing=spacing,
                                supported_scan_ms=scan_ms, **stats(latencies))
    summary["trajectory_limit_ratio"] = trajectory_ratio
    summary["joint_limit_violations"] = violations+sum(r.get("violations",0) for r in records)
    checks = {f"{g}_success": summary[g]["success_rate"] >= gates["ik_success_min"]
              for g in ("cold", "boundary", "singular", "unreachable")}
    checks.update({f"{g}_latency": summary[g]["p95_ms"] <= gates["ik_p95_ms_max"] and
                   summary[g]["max_ms"] <= gates["ik_max_ms_max"]
                   for g in ("cold", "boundary", "singular", "unreachable")})
    checks.update(
        collision_misses=summary["collisions"]["false_negatives"] == 0,
        collision_atomic=summary["collisions"]["pose_changes"] == 0,
        thin_fixtures_contact=all(r["known_contact"] for r in collision_records if r["group"] == "thin"),
        trajectory_limits=trajectory_ratio <= gates["trajectory_limit_ratio_max"],
        joint_limits=summary["joint_limit_violations"] == 0,
        resource_fail_closed=rejects == len(latencies),
        resource_memory=peak <= gates["resource_peak_tracemalloc_bytes_max"],
        resource_rss=stress_rss_growth <= gates["resource_stress_rss_growth_bytes_max"],
        resource_latency=stats(latencies)["p95_ms"] <= gates["resource_rejection_p95_ms_max"],
        resource_supported_precision=count <= gates["resource_max_samples"] and spacing <= 1e-6+1e-14,
        resource_supported_time=scan_ms <= gates["resource_supported_scan_ms_max"])
    result = dict(passed=all(checks.values()), baseline=baseline, checks=checks, summary=summary,
                  ik_cases=records, collision_cases=collision_records, resource_cases=resource_cases,
                  corpus_sha256=hashlib.sha256(corpus_bytes).hexdigest(),
                  protocol_sha256=hashlib.sha256(protocol_bytes).hexdigest(),
                  version=robotarm_lab.__version__, environment=dict(python=platform.python_version(),
                  system=platform.system(), release=platform.release()),
                  limitations="Dense discrete collision reference, not continuous ground truth; "
                  "RSS includes allocator/cache effects; legacy OOM allocation instrumented, not executed")
    (output / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"passed":result["passed"],"summary":summary,"checks":checks},indent=2))
    return 0 if result["passed"] or baseline else 1
