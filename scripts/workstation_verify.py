"""Exercise the actual shown Qt workstation and retain every scenario outcome."""

import argparse
import hashlib
import json
import os
import platform
import sys
import traceback
from pathlib import Path
from time import perf_counter

import numpy as np
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QSurfaceFormat, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea

from robotarm_lab.config import load_config
from robotarm_lab.kinematics import fk
from robotarm_lab.model import HOME
from robotarm_lab.workstation.window import Workstation


class Audit:
    def __init__(self, window, output):
        self.window, self.output = window, output
        self.results, self.responses = [], []
        self.exceptions = []
        self.acknowledgements = []
        window.worker.acknowledged.connect(
            lambda name, requested: self.acknowledgements.append(
                (name, (perf_counter() - requested) * 1000)
            )
        )
        window.worker.responded.connect(lambda *args: self.responses.append(args))
        sys.excepthook = lambda kind, value, trace: self.exceptions.append(
            f"{kind.__name__}: {value}"
        )

    def wait(self, predicate, timeout=10):
        deadline = perf_counter() + timeout
        while not predicate() and perf_counter() < deadline:
            QTest.qWait(5)
        assert predicate(), "Timed out waiting for workstation state"
        assert not self.exceptions, self.exceptions

    def click(self, name):
        button = self.window.buttons[name]
        assert button.isEnabled(), f"Disabled button: {name}"
        parent = button.parentWidget()
        while parent:
            if isinstance(parent, QScrollArea):
                parent.ensureWidgetVisible(button)
            parent = parent.parentWidget()
        QTest.qWait(20)
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)

    def action(self, name, callback, allow_error=False):
        count = len(self.responses)
        callback()
        self.wait(lambda: len(self.responses) > count)
        matches = [r for r in self.responses[count:] if r[0] == name]
        self.wait(lambda: any(r[0] == name for r in self.responses[count:]))
        matches = [r for r in self.responses[count:] if r[0] == name]
        if not allow_error:
            assert not matches[-1][2], matches[-1]
        return matches[-1]

    def still(self):
        self.wait(lambda: self.window.snapshot.state not in ("RUNNING", "PLANNING"), 20)

    def reset(self):
        self.action("reset", lambda: self.click("reset"))
        self.wait(lambda: self.window.snapshot.state == "IDLE")
        if self.window.snapshot.mode != "MANUAL":
            self.action("set_mode", lambda: self.window.mode.setCurrentText("MANUAL"))

    def scenario(self, name, function):
        started = perf_counter()
        try:
            self.reset()
            function()
            assert not self.exceptions, self.exceptions
            assert not self.window.viewport.error, self.window.viewport.error
            result = {"name": name, "passed": True}
        except Exception as exc:
            result = {
                "name": name,
                "passed": False,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        result["elapsed_ms"] = (perf_counter() - started) * 1000
        self.window.grab().save(str(self.output / f"{name}.png"))
        self.results.append(result)
        print(json.dumps(result), flush=True)

    def joint(self):
        self.window.tabs.setCurrentIndex(0)
        q = np.array(HOME) + [0.2, -0.05, 0.05, 0.1, 0, 0]
        for field, v in zip(self.window.joint_targets, np.rad2deg(q), strict=True):
            field.setValue(float(v))
        before = np.array(self.window.snapshot.q)
        self.action("preview_joint", lambda: self.click("preview"))
        np.testing.assert_array_equal(self.window.snapshot.q, before)
        assert self.window.buttons["execute"].isEnabled()
        self.window.timeline.setValue(350)
        QTest.qWait(50)
        np.testing.assert_array_equal(self.window.snapshot.q, before)
        self.action("execute", lambda: self.click("execute"))
        self.still()
        np.testing.assert_allclose(self.window.snapshot.q, q, atol=1e-4)
        self.action("home", lambda: self.click("home"))
        self.still()
        np.testing.assert_array_equal(self.window.snapshot.q, HOME)

    def stale_edit(self):
        self.window.tabs.setCurrentIndex(0)
        self.window.copy_joints()
        self.action("preview_joint", lambda: self.click("preview"))
        self.window.joint_targets[0].setValue(10)
        assert not self.window.buttons["execute"].isEnabled()
        self.wait(lambda: self.window.snapshot.preview is None)

    def jog(self):
        self.window.tabs.setCurrentIndex(0)
        self.action("jog", lambda: self.click("jog_plus_0"))
        self.still()
        assert abs(self.window.snapshot.q[0] - np.deg2rad(1)) < 1e-10
        self.action("set_mode", lambda: self.window.mode.setCurrentText("AUTO"))
        assert not self.window.buttons["jog_plus_0"].isEnabled()

    def ik(self):
        self.window.tabs.setCurrentIndex(1)
        self.window.copy_tcp()
        self.action("preview_pose", lambda: self.click("preview"))
        self.action("execute", lambda: self.click("execute"))
        self.still()
        before = np.array(self.window.snapshot.q)
        self.window.tcp_targets[0].setValue(2000)
        self.action("preview_pose", lambda: self.click("preview"), allow_error=True)
        assert "IK" in self.window.snapshot.error or "reachable" in self.window.snapshot.error
        np.testing.assert_array_equal(self.window.snapshot.q, before)
        assert not self.window.buttons["execute"].isEnabled()

    def playback(self):
        self.action("demo", lambda: self.click("demo"))
        self.wait(lambda: self.window.snapshot.state == "RUNNING")
        QTest.qWait(200)
        self.action("pause", lambda: self.click("pause"))
        self.wait(lambda: self.window.snapshot.state == "PAUSED")
        before = self.window.snapshot.q
        QTest.qWait(150)
        np.testing.assert_array_equal(self.window.snapshot.q, before)
        self.action("set_speed", lambda: self.window.speed.setCurrentText("75%"))
        self.action("resume", lambda: self.click("pause"))
        self.wait(lambda: self.window.snapshot.state == "RUNNING")
        start = perf_counter()
        self.click("freeze")
        self.wait(lambda: self.window.snapshot.state == "STOPPED", 1)
        self.freeze_ms = (perf_counter() - start) * 1000
        assert self.freeze_ms <= 200, self.freeze_ms
        before = self.window.snapshot.q
        QTest.qWait(150)
        np.testing.assert_array_equal(self.window.snapshot.q, before)

    def demo_complete(self):
        self.action("demo", lambda: self.click("demo"))
        self.still()
        np.testing.assert_array_equal(self.window.snapshot.q, HOME)
        completed = [e for e in self.window.snapshot.events if e[2] == "completed"]
        assert len(completed) >= 3

    def teach(self):
        self.window.tabs.setCurrentIndex(2)
        self.window.teach_name.setText("QA Home")
        self.action("teach_save", lambda: self.click("teach_save"))
        assert "QA Home" in dict(self.window.snapshot.teach)
        disk = json.loads((self.window.output / "teach-points.json").read_text())
        np.testing.assert_array_equal(disk["points"]["QA Home"], HOME)
        self.window.teach_list.setCurrentRow(0)
        self.action("teach_preview", lambda: self.click("preview"))
        assert self.window.snapshot.preview is not None
        self.action("teach_delete", lambda: self.click("teach_delete"))
        assert "QA Home" not in dict(self.window.snapshot.teach)

    def obstacles(self):
        self.window.monitor_tabs.setCurrentIndex(1)
        for field, value in zip(
            self.window.box_fields, (1200, 1200, 200, 100, 120, 140), strict=True
        ):
            field.setValue(value)
        self.action("add_box", lambda: self.click("add_box"))
        assert len(self.window.snapshot.obstacles) == 1
        self.window.box_fields[0].setValue(1500)
        self.action("update_box", lambda: self.click("update_box"))
        assert self.window.snapshot.obstacles[0][1][0] == 1.5
        self.action("remove_box", lambda: self.click("remove_box"))
        assert not self.window.snapshot.obstacles
        self.action("blocker", lambda: self.click("blocker"))
        before = self.window.snapshot.q
        self.action("demo", lambda: self.click("demo"), allow_error=True)
        assert "Collision" in self.window.snapshot.error
        np.testing.assert_array_equal(self.window.snapshot.q, before)
        self.action("clear_boxes", lambda: self.click("clear_boxes"))
        assert not self.window.snapshot.obstacles
        self.action("demo", lambda: self.click("demo"))
        self.wait(lambda: self.window.snapshot.state == "RUNNING")
        point = fk(self.window.snapshot.q).position.tolist()
        self.action("add_box", lambda: self.window.command("add_box", point, [0.08] * 3))
        self.wait(lambda: self.window.snapshot.state == "BLOCKED")
        assert self.window.snapshot.clearance_contacts > 0
        self.window.monitor_tabs.setCurrentIndex(0)

    def log_recovery(self):
        path = self.window.output / "session.jsonl"
        backup = path.with_suffix(".preserved.jsonl")
        path.replace(backup)
        path.mkdir()
        try:
            self.action("home", lambda: self.click("home"), allow_error=True)
            self.wait(lambda: self.window.snapshot.state == "FAULT")
            assert "Event log unavailable" in self.window.notice.text()
            assert not self.window.buttons["execute"].isEnabled()
        finally:
            path.rmdir()
            backup.replace(path)
        self.reset()
        self.action("home", lambda: self.click("home"))
        self.still()

    def invalid_command(self):
        before = self.window.snapshot.q
        self.action("preview_joint", lambda: self.window.command("preview_joint", [999] * 6), True)
        assert self.window.snapshot.error
        np.testing.assert_array_equal(before, self.window.snapshot.q)
        assert not self.window.buttons["execute"].isEnabled()

    def restart_persistence(self):
        self.window.tabs.setCurrentIndex(2)
        self.window.teach_name.setText("Restart checkpoint")
        self.action("teach_save", lambda: self.click("teach_save"))
        # A second real workstation creates an independent worker/world and reads the disk file.
        second = Workstation(load_config(), self.window.output)
        second.show()
        try:
            self.wait(lambda: second.snapshot is not None)
            assert "Restart checkpoint" in dict(second.snapshot.teach)
            second.grab().save(str(self.output / "teach-reopened.png"))
        finally:
            second.close()
            self.wait(lambda: not second.worker.isRunning())
        self.window.activateWindow()
        self.window.teach_list.setCurrentRow(0)
        self.action("teach_delete", lambda: self.click("teach_delete"))

    def shutdown_planning(self):
        second = Workstation(load_config(), self.output / "shutdown-session")
        phases = []
        second.worker.changed.connect(lambda s: phases.append(s.state))
        second.show()
        self.wait(lambda: second.snapshot is not None)
        second.command("demo")
        self.wait(lambda: "PLANNING" in phases)
        started = perf_counter()
        second.close()
        self.wait(lambda: not second.worker.isRunning(), 5)
        assert second.closing
        self.shutdown_ms = (perf_counter() - started) * 1000

    def camera(self):
        view = self.window.viewport
        initial = (view.yaw, view.elevation)
        p = view.rect().center()
        QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=p)
        QTest.mouseMove(view, p + QPoint(40, 25), delay=30)
        QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=p + QPoint(40, 25))
        assert (view.yaw, view.elevation) != initial
        target = view.target.copy()
        QTest.mousePress(view, Qt.MouseButton.RightButton, pos=p)
        QTest.mouseMove(view, p + QPoint(20, 10), delay=30)
        QTest.mouseRelease(view, Qt.MouseButton.RightButton, pos=p + QPoint(20, 10))
        assert not np.array_equal(target, view.target)
        distance = view.distance
        event = QWheelEvent(
            QPointF(p),
            QPointF(view.mapToGlobal(p)),
            QPoint(),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        QApplication.sendEvent(view, event)
        assert view.distance < distance
        self.click("view")
        assert view.yaw == -65 and view.distance == 1.55
        self.window.proxies.setChecked(True)
        QTest.qWait(100)
        self.window.grab().save(str(self.output / "collision-proxies.png"))
        self.window.proxies.setChecked(False)
        self.click("capture")
        assert list(self.window.output.glob("workstation-*.png"))

    def performance(self, seconds):
        self.reset()
        self.window.tabs.setCurrentIndex(0)
        self.action("demo", lambda: self.click("demo"))
        QTest.qWait(1500)
        self.window.viewport.frame_times.clear()
        self.window.viewport.render_times.clear()
        self.window.heartbeat.clear()
        started = perf_counter()
        while perf_counter() - started < seconds:
            if self.window.snapshot.state == "IDLE":
                self.action("demo", lambda: self.click("demo"))
                self.wait(lambda: self.window.snapshot.state == "RUNNING")
            QTest.qWait(10)
        timestamps = list(self.window.viewport.frame_times)
        return dict(
            seconds=perf_counter() - started,
            frames=len(timestamps),
            fps=(len(timestamps) - 1) / (timestamps[-1] - timestamps[0]),
            render_cpu_p95_ms=float(np.percentile(self.window.viewport.render_times, 95)),
            ui_heartbeat_p95_ms=float(np.percentile(self.window.heartbeat, 95)),
            ui_heartbeat_max_ms=max(self.window.heartbeat),
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--performance-seconds", type=float, default=30)
    parser.add_argument(
        "--functional-only",
        action="store_true",
        help="CI correctness run; does not claim local hardware performance acceptance",
    )
    args = parser.parse_args()

    def source_digest():
        root = Path(__file__).resolve().parents[1] / "src/robotarm_lab"
        digest = hashlib.sha256()
        for path in sorted(root.rglob("*")):
            if path.suffix in (".py", ".json", ".urdf"):
                digest.update(path.relative_to(root).as_posix().encode())
                digest.update(path.read_text(encoding="utf-8").encode())
        return digest.hexdigest()

    start_digest = source_digest()
    args.output.mkdir(parents=True, exist_ok=True)
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
    QTest.qWait(1000)
    try:
        for name, func in (
            ("joint_preview_execute", audit.joint),
            ("stale_input", audit.stale_edit),
            ("joint_jog_mode", audit.jog),
            ("tcp_ik_unreachable", audit.ik),
            ("pause_resume_speed_freeze", audit.playback),
            ("demo_complete", audit.demo_complete),
            ("teach_persistence", audit.teach),
            ("collision_blocking", audit.obstacles),
            ("camera_capture", audit.camera),
            ("invalid_command", audit.invalid_command),
            ("log_io_failure_recovery", audit.log_recovery),
            ("teach_restart_persistence", audit.restart_persistence),
            ("shutdown_during_planning", audit.shutdown_planning),
        ):
            audit.scenario(name, func)
        metrics = None if args.functional_only else audit.performance(args.performance_seconds)
        gates = json.loads(Path("acceptance-v0.2.0.json").read_text())
        checks = (
            {}
            if args.functional_only
            else {
                "fps": metrics["fps"] >= gates["viewport_fps_min"],
                "render": metrics["render_cpu_p95_ms"] <= gates["render_cpu_p95_ms_max"],
                "heartbeat_p95": metrics["ui_heartbeat_p95_ms"] <= gates["ui_heartbeat_p95_ms_max"],
                "heartbeat_max": metrics["ui_heartbeat_max_ms"] <= gates["ui_heartbeat_max_ms_max"],
                "command_feedback": float(np.percentile([a[1] for a in audit.acknowledgements], 95))
                <= gates["command_feedback_p95_ms_max"],
                "freeze": audit.freeze_ms <= gates["freeze_latency_ms_max"],
            }
        )
        report = dict(
            scenarios=audit.results,
            metrics=metrics,
            checks=checks,
            qt_errors=audit.exceptions,
            scope="CI correctness only"
            if args.functional_only
            else "functional and local performance",
            renderer=window.viewport.renderer_info,
            platform=platform.platform(),
            dpr=window.devicePixelRatioF(),
            scale_env=os.environ.get("QT_SCREEN_SCALE_FACTORS"),
            freeze_latency_ms=getattr(audit, "freeze_ms", None),
            responses=audit.responses,
            command_acknowledgements_ms=audit.acknowledgements,
            command_feedback_p95_ms=float(
                np.percentile([a[1] for a in audit.acknowledgements], 95)
            ),
            command_feedback_definition=(
                "Submission to worker acceptance received by GUI event loop; "
                "completion latency is separately reported in responses"
            ),
            shutdown_latency_ms=getattr(audit, "shutdown_ms", None),
            method="Shown Qt workstation with QTest widget input, no mock rendering",
            passed=all(r["passed"] for r in audit.results)
            and all(checks.values())
            and not audit.exceptions,
        )
        window.grab().save(str(args.output / "performance.png"))
    finally:
        window.close()
        audit.wait(lambda: not window.worker.isRunning())
        app.processEvents()
    report["source_sha256"] = start_digest
    report["source_unchanged_during_run"] = start_digest == source_digest()
    report["passed"] = report["passed"] and report["source_unchanged_during_run"]
    (args.output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "metrics": metrics, "checks": checks}, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
