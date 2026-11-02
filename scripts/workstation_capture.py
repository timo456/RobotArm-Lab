"""Shown-window Qt captures, never a mockup or reconstructed screenshot."""

import argparse
import json
import os
import platform
import sys
from pathlib import Path
from time import perf_counter

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from robotarm_lab.config import load_config
from robotarm_lab.workstation.window import Workstation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=1540)
    parser.add_argument("--height", type=int, default=940)
    parser.add_argument("--expect-teach", help="Verify a point persisted by a previous process")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    errors = []
    sys.excepthook = lambda kind, value, trace: errors.append(f"{kind.__name__}: {value}")
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setSamples(4)
    fmt.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(fmt)
    app = QApplication([])
    app.setStyle("Fusion")
    window = Workstation(load_config(), args.output / "session")
    window.resize(args.width, args.height)
    window.show()
    window.raise_()
    window.activateWindow()
    deadline = perf_counter() + 10
    while window.snapshot is None and perf_counter() < deadline:
        QTest.qWait(20)
    QTest.qWait(2000)
    try:
        if window.snapshot is None:
            raise RuntimeError("No control snapshot")
        if args.expect_teach:
            assert args.expect_teach in dict(window.snapshot.teach), "Persisted teach point missing"
        if window.viewport.error:
            raise RuntimeError(window.viewport.error)
        if not window.viewport.isValid():
            raise RuntimeError("Invalid OpenGL context")
        assert window.grab().save(str(args.output / "home.png"))
        assert window.viewport.grabFramebuffer().save(str(args.output / "viewport.png"))
        QTest.mouseClick(window.buttons["demo"], Qt.MouseButton.LeftButton)
        QTest.qWait(1000)
        assert window.snapshot.state == "RUNNING", window.snapshot.state
        assert window.grab().save(str(args.output / "demo-running.png"))
        QTest.mouseClick(window.buttons["pause"], Qt.MouseButton.LeftButton)
        QTest.qWait(300)
        assert window.snapshot.state == "PAUSED", window.snapshot.state
        assert window.grab().save(str(args.output / "paused.png"))
        report = dict(
            method="Actual shown Qt Widgets / QOpenGLWidget; "
            "QWidget.grab and grabFramebuffer; QTest input",
            platform=platform.platform(),
            qt_scale=os.environ.get("QT_SCALE_FACTOR", "1"),
            screen_scale=os.environ.get("QT_SCREEN_SCALE_FACTORS"),
            logical_size=[window.width(), window.height()],
            dpr=window.devicePixelRatioF(),
            renderer=window.viewport.renderer_info,
            render_error=window.viewport.error,
            render_cpu_p95_ms=float(np.percentile(window.viewport.render_times, 95)),
            heartbeat_p95_ms=float(np.percentile(window.heartbeat, 95)),
            fps=window.viewport.fps,
            final_state=window.snapshot.state,
            expected_teach=args.expect_teach,
            loaded_teach=[name for name, _ in window.snapshot.teach],
            events=list(window.snapshot.events),
        )
    except Exception as exc:
        errors.append(str(exc))
        report = {"error": str(exc)}
    finally:
        window.close()
        deadline = perf_counter() + 10
        while window.worker.isRunning() and perf_counter() < deadline:
            QTest.qWait(20)
        report["worker_closed"] = not window.worker.isRunning()
        report["qt_callback_errors"] = errors
        report["passed"] = not errors and report["worker_closed"]
        (args.output / "capture.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        if window.worker.isRunning():
            raise RuntimeError("Worker did not close")
        app.processEvents()
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
