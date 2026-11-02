"""Rebuild a genuinely isolated environment from the reviewed wheelhouse and project wheel."""

import argparse
import hashlib
import json
import os
import subprocess
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", type=Path, default=ROOT / ".tmp/release-clean-v011")
    args = parser.parse_args()
    destination = args.environment.resolve()
    if destination.exists():
        raise SystemExit("Clean environment already exists; use a new --environment path")
    if not destination.is_relative_to(ROOT):
        raise SystemExit("Clean environment must be inside this checkout")
    output = ROOT / "outputs/v0.1.1/clean"
    output.mkdir(parents=True, exist_ok=True)
    env = dict(
        os.environ,
        TEMP=str(ROOT / ".tmp"),
        TMP=str(ROOT / ".tmp"),
        PIP_CACHE_DIR=str(ROOT / ".cache/pip"),
    )
    env.pop("PYTHONPATH", None)
    os.environ.update(TEMP=env["TEMP"], TMP=env["TMP"], PIP_CACHE_DIR=env["PIP_CACHE_DIR"])
    venv.EnvBuilder(with_pip=True, system_site_packages=False).create(destination)
    python = destination / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    wheels = list((ROOT / "dist").glob("robotarm_lab-0.1.1-*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Build exactly one v0.1.1 wheel first")
    digest = hashlib.sha256()
    package = ROOT / "src/robotarm_lab"
    for path in sorted(package.rglob("*")):
        if path.suffix in (".py", ".json", ".urdf"):
            digest.update(path.relative_to(package).as_posix().encode())
            digest.update(path.read_text(encoding="utf-8").encode())
    expected = digest.hexdigest()
    commands = [
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--only-binary=:all:",
            "--find-links",
            str(ROOT / ".cache/wheelhouse"),
            "-r",
            str(ROOT / "requirements-lock.txt"),
        ],
        [str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheels[0])],
        [str(python), "-m", "pip", "check"],
        [
            str(python),
            "-I",
            "-c",
            "import robotarm_lab,sys,json,hashlib; "
            "from pathlib import Path; "
            "assert Path(robotarm_lab.__file__).is_relative_to(Path(sys.prefix)); "
            "assert robotarm_lab.__version__=='0.1.1'; "
            "root=Path(robotarm_lab.__file__).parent; h=hashlib.sha256(); "
            "[(h.update(p.relative_to(root).as_posix().encode()),"
            "h.update(p.read_text(encoding='utf-8').encode())) for p in sorted(root.rglob('*')) "
            "if p.suffix in ('.py','.json','.urdf')]; "
            "assert h.hexdigest()==sys.argv[1]; "
            "print(json.dumps({'isolated':True,'version':robotarm_lab.__version__,"
            "'source_sha256':h.hexdigest()}))",
            expected,
        ],
        [
            str(python),
            "-I",
            "-m",
            "pytest",
            str(ROOT / "tests"),
            "-q",
            "--no-cov",
            "--basetemp=" + str(ROOT / ".tmp/clean-pytest"),
            "--junitxml=" + str(output / "pytest.xml"),
        ],
        [str(python), "-I", "-m", "robotarm_lab", "demo", "--output", str(output / "demo")],
    ]
    results = []
    for index, command in enumerate(commands):
        with (output / f"step-{index}.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(
                command, cwd=output, env=env, stdout=log, stderr=subprocess.STDOUT
            )
        results.append(dict(step=index, exit_code=result.returncode))
        print(f"Clean step {index}: exit {result.returncode}", flush=True)
        if result.returncode:
            break
    report = dict(
        passed=len(results) == len(commands) and all(r["exit_code"] == 0 for r in results),
        system_site_packages=False,
        isolated_module_test=True,
        binary_only_offline_install=True,
        source_compile_performed=False,
        source_sha256=expected,
        wheel_sha256=hashlib.sha256(wheels[0].read_bytes()).hexdigest(),
        steps=results,
    )
    (output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
