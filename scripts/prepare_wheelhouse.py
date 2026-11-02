"""Prefer compatible cached/upstream wheels; source builds require an explicit flag."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from email.parser import BytesParser
from pathlib import Path

from packaging.tags import sys_tags
from packaging.utils import parse_wheel_filename

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-source-build", action="store_true")
    args = parser.parse_args()
    wheelhouse = ROOT / ".cache/wheelhouse"
    wheelhouse.mkdir(parents=True, exist_ok=True)
    (ROOT / ".tmp").mkdir(exist_ok=True)
    os.environ.update(
        TEMP=str(ROOT / ".tmp"), TMP=str(ROOT / ".tmp"), PIP_CACHE_DIR=str(ROOT / ".cache/pip")
    )
    tags = set(sys_tags())
    reused = []
    for wheel in (ROOT / ".cache/pip/wheels").rglob("pybullet-3.2.7-*.whl"):
        name, version, _, compatible = parse_wheel_filename(wheel.name)
        if name == "pybullet" and str(version) == "3.2.7" and tags.intersection(compatible):
            with zipfile.ZipFile(wheel) as archive:
                metadata = BytesParser().parsebytes(
                    archive.read("pybullet-3.2.7.dist-info/METADATA")
                )
            if metadata["Name"].lower() != "pybullet" or metadata["Version"] != "3.2.7":
                raise RuntimeError("Cached wheel metadata mismatch")
            shutil.copy2(wheel, wheelhouse / wheel.name)
            reused.append(wheel.name)
    command = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--only-binary=:all:",
        "--find-links",
        str(wheelhouse),
        "--dest",
        str(wheelhouse),
        "pybullet==3.2.7",
    ]
    result = subprocess.run(command, check=False)
    built = False
    if result.returncode:
        if not args.allow_source_build:
            raise SystemExit(
                "No compatible PyBullet wheel. Reuse a trusted local wheel or run "
                "prepare_wheelhouse.py --allow-source-build with C++ tools installed. "
                "No silent source build was started."
            )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--wheel-dir",
                str(wheelhouse),
                "pybullet==3.2.7",
            ],
            check=True,
        )
        built = True
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--only-binary=:all:",
            "--find-links",
            str(wheelhouse),
            "--dest",
            str(wheelhouse),
            "-r",
            str(ROOT / "requirements-lock.txt"),
        ],
        check=True,
    )
    evidence = dict(
        python=sys.version.split()[0],
        reused=reused,
        source_build_performed=built,
        wheels=[
            dict(file=p.name, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(wheelhouse.glob("*.whl"))
        ],
    )
    output = ROOT / "outputs/v0.1.1"
    output.mkdir(parents=True, exist_ok=True)
    (output / "wheelhouse.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
