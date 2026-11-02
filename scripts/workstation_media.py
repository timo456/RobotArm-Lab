"""Capture an actual workstation demonstration as PNG frames and an animated GIF."""

import argparse
import json
from pathlib import Path
from time import perf_counter

from PIL import Image
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from workstation_verify import Audit

from robotarm_lab.config import load_config
from robotarm_lab.workstation.window import Workstation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
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
    frames, stamps = [], []
    try:
        audit.action("demo", lambda: audit.click("demo"))
        audit.wait(lambda: window.snapshot.state == "RUNNING")
        started = perf_counter()
        for index in range(100):
            path = args.output / f"frame-{index:03d}.png"
            assert window.grab().save(str(path))
            stamps.append(perf_counter() - started)
            frames.append(path)
            if window.snapshot.state == "IDLE" and index > 20:
                break
            QTest.qWait(100)
        assert not window.viewport.error and not audit.exceptions
        images = []
        for path in frames:
            with Image.open(path) as source:
                image = source.convert("RGB")
                image.thumbnail((1280, 720), Image.Resampling.LANCZOS)
                images.append(image.copy())
        durations = [
            max(20, round((b - a) * 1000)) for a, b in zip(stamps, stamps[1:], strict=False)
        ]
        durations.append(1200)
        images[0].save(
            args.output / "workstation-demo.gif",
            save_all=True,
            append_images=images[1:],
            duration=durations,
            loop=0,
            optimize=True,
        )
        report = dict(
            method="Actual shown QWidget.grab frames; resized and GIF-encoded with Pillow",
            frames=len(frames),
            timestamps_s=stamps,
            final_state=window.snapshot.state,
            renderer=window.viewport.renderer_info,
            passed=True,
        )
        (args.output / "media.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
    finally:
        window.close()
        audit.wait(lambda: not window.worker.isRunning())
        app.processEvents()


if __name__ == "__main__":
    main()
