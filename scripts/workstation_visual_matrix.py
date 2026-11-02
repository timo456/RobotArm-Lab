"""Reproduce the frozen logical-size / Qt scale capture matrix in fresh processes."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    protocol = json.loads(Path("acceptance-v0.2.0.json").read_text())
    results = []
    for case in protocol["visual_cases"]:
        width, height = case["logical_size"]
        scale = case["qt_scale"]
        folder = args.output / f"{width}x{height}-{scale}"
        folder.mkdir(exist_ok=True)
        env = dict(
            os.environ,
            QT_ENABLE_HIGHDPI_SCALING="0",
            QT_SCALE_FACTOR=str(scale),
            QT_SCREEN_SCALE_FACTORS="1",
        )
        command = [
            sys.executable,
            "scripts/workstation_capture.py",
            "--output",
            str(folder),
            "--width",
            str(width),
            "--height",
            str(height),
        ]
        with (folder / "process.log").open("w", encoding="utf-8") as log:
            process = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        manifest = folder / "capture.json"
        result = json.loads(manifest.read_text()) if manifest.exists() else {"passed": False}
        result["requested"] = case
        result["exit_code"] = process.returncode
        if process.returncode == 0:
            with Image.open(folder / "home.png") as image:
                result["pixel_size"] = list(image.size)
            result["passed"] = (
                result["passed"]
                and result["logical_size"] == [width, height]
                and abs(result["dpr"] - scale) < 1e-6
                and result["pixel_size"] == [round(width * scale), round(height * scale)]
            )
        else:
            result["passed"] = False
        results.append(result)
        print(json.dumps({"case": case, "passed": result["passed"]}), flush=True)
    report = dict(
        method="Qt scaling override in fresh shown-window processes; OS settings unchanged",
        cases=results,
        passed=all(r["passed"] for r in results),
    )
    (args.output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
