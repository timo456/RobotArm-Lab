"""Ten-minute shown-window endurance run with actual RSS and rendering evidence."""

import argparse
import ctypes
import hashlib
import json
import os
import platform
from pathlib import Path
from time import perf_counter

import numpy as np
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from workstation_verify import Audit

from robotarm_lab.config import load_config
from robotarm_lab.model import LOWER, UPPER
from robotarm_lab.workstation.window import Workstation


def rss_mib() -> float:
    if os.name != "nt":
        pages = int(Path("/proc/self/statm").read_text().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE") / 1024**2

    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t)
            for name in (
                "PeakWorkingSetSize",
                "WorkingSetSize",
                "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage",
                "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage",
                "PagefileUsage",
                "PeakPagefileUsage",
            )
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(Counters),
        ctypes.c_ulong,
    ]
    if not psapi.GetProcessMemoryInfo(
        kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return counters.WorkingSetSize / 1024**2


def source_digest() -> str:
    root = Path(__file__).resolve().parents[1] / "src/robotarm_lab"
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.suffix in (".py", ".json", ".urdf"):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_text(encoding="utf-8").encode())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    gates = json.loads(Path("acceptance-v0.2.0.json").read_text())
    initial_digest = source_digest()
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setSamples(4)
    fmt.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(fmt)
    app = QApplication([])
    app.setStyle("Fusion")
    window = Workstation(load_config(), args.output / "session")
    window.resize(1366, 768)
    window.show()
    audit = Audit(window, args.output)
    audit.wait(lambda: window.snapshot is not None)
    samples, failures, intervals = [], [], []
    cycles = 0
    report = {}
    try:
        # Warm up drivers, caches and the bounded trail before the RSS baseline.
        audit.performance(30)
        audit.reset()
        baseline = rss_mib()
        started = last_sample = perf_counter()
        next_checkpoint = 60
        window.viewport.frame_times.clear()
        window.viewport.render_times.clear()
        window.heartbeat.clear()
        audit.responses.clear()
        audit.acknowledgements.clear()
        window.grab().save(str(args.output / "start.png"))
        while perf_counter() - started < gates["soak_duration_seconds"]:
            if window.snapshot.state == "IDLE" and not window.pending_motion:
                audit.action("demo", lambda: audit.click("demo"))
                audit.wait(lambda: window.snapshot.state == "RUNNING")
                cycles += 1
            QTest.qWait(10)
            s = window.snapshot
            if s.error or window.viewport.error or audit.exceptions:
                raise AssertionError((s.error, window.viewport.error, audit.exceptions))
            assert np.all(np.asarray(s.q) >= LOWER) and np.all(np.asarray(s.q) <= UPPER)
            assert not s.clearance_contacts
            assert len(s.events) <= gates["event_log_capacity"]
            assert window.events.rowCount() <= gates["event_log_capacity"]
            assert len(window.viewport.trail) <= gates["trail_point_capacity"]
            now = perf_counter()
            if now - last_sample >= 10:
                stamps = list(window.viewport.frame_times)
                sample = dict(
                    elapsed_s=now - started,
                    rss_mib=rss_mib(),
                    cycles=cycles,
                    events=window.events.rowCount(),
                    trail=len(window.viewport.trail),
                )
                interval = dict(
                    fps=(len(stamps) - 1) / (stamps[-1] - stamps[0]),
                    render_p95_ms=float(np.percentile(window.viewport.render_times, 95)),
                    heartbeat_p95_ms=float(np.percentile(window.heartbeat, 95)),
                    heartbeat_max_ms=max(window.heartbeat),
                )
                samples.append(sample)
                intervals.append(interval)
                window.viewport.frame_times.clear()
                window.viewport.render_times.clear()
                window.heartbeat.clear()
                last_sample = now
            if now - started >= next_checkpoint:
                checkpoint = dict(
                    elapsed_s=now - started,
                    samples=samples,
                    intervals=intervals,
                    source_sha256=initial_digest,
                    status="running",
                )
                (args.output / "checkpoint.json").write_text(json.dumps(checkpoint, indent=2))
                print(json.dumps(samples[-1]), flush=True)
                next_checkpoint += 60
        duration = perf_counter() - started
        final_rss = rss_mib()
        growth = max([final_rss, *[s["rss_mib"] for s in samples]]) - baseline
        ack = float(np.percentile([a[1] for a in audit.acknowledgements], 95))
        checks = dict(
            duration=duration >= gates["soak_duration_seconds"],
            rss_growth=growth <= gates["soak_rss_growth_max_mib"],
            fps=all(i["fps"] >= gates["viewport_fps_min"] for i in intervals),
            render=all(i["render_p95_ms"] <= gates["render_cpu_p95_ms_max"] for i in intervals),
            heartbeat=all(
                i["heartbeat_p95_ms"] <= gates["ui_heartbeat_p95_ms_max"]
                and i["heartbeat_max_ms"] <= gates["ui_heartbeat_max_ms_max"]
                for i in intervals
            ),
            command_feedback=ack <= gates["command_feedback_p95_ms_max"],
            commands=all(not r[2] for r in audit.responses),
            source_unchanged=initial_digest == source_digest(),
        )
        report = dict(
            duration_s=duration,
            cycles=cycles,
            rss_baseline_mib=baseline,
            rss_final_mib=final_rss,
            rss_peak_growth_mib=growth,
            command_feedback_p95_ms=ack,
            samples=samples,
            intervals=intervals,
            checks=checks,
            source_sha256=initial_digest,
            renderer=window.viewport.renderer_info,
            platform=platform.platform(),
            dpr=window.devicePixelRatioF(),
            passed=all(checks.values()),
        )
        window.grab().save(str(args.output / "end.png"))
    except Exception as exc:
        failures.append(repr(exc))
        report.update(passed=False, failures=failures, samples=samples, intervals=intervals)
    finally:
        window.close()
        audit.wait(lambda: not window.worker.isRunning())
        app.processEvents()
        report["worker_closed"] = not window.worker.isRunning()
        (args.output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("samples", "intervals")}))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
