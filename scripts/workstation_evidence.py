"""Collect source-matched, sanitized workstation evidence without altering raw outputs."""

import hashlib
import json
import re
import shutil
from pathlib import Path
from xml.etree import ElementTree

import numpy as np
import pybullet as pb
from scipy.spatial.transform import Rotation

from robotarm_lab.config import load_config
from robotarm_lab.model import LOWER, UPPER
from robotarm_lab.workstation.engine import Engine
from robotarm_lab.workstation.geometry import link_frames

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/v0.2.0"
DEST = ROOT / "reports/v0.2.0"


def sanitize(value):
    if isinstance(value, str):
        value = value.replace(str(ROOT), "<project>").replace(ROOT.as_posix(), "<project>")
        return re.sub(r"C:[/\\]Users[/\\][^/\\\s]+", "<user-home>", value)
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items()}
    return value


def save_json(source: Path, target: Path):
    value = sanitize(json.loads(source.read_text(encoding="utf-8")))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return value


def save_xml(source: Path, target: Path) -> None:
    tree = ElementTree.parse(source)
    for node in tree.iter():
        node.attrib.pop("hostname", None)
        if node.text:
            node.text = sanitize(node.text)
    tree.write(target, encoding="utf-8", xml_declaration=True)


def main() -> None:
    DEST.mkdir(exist_ok=True)
    sources = {
        "gui-final": "gui-timing-final/results.json",
        "software-functional": "software-functional-final/results.json",
        "small-functional": "small-functional-final/results.json",
        "soak": "soak-first/results.json",
        "visual-matrix": "visual-matrix-v2/results.json",
        "clean-environment": "clean/results.json",
        "clean-workstation": "clean/workstation/capture.json",
        "process-restart-write": "process-restart/write-process.json",
        "process-restart-read": "process-restart/capture.json",
        "demo-media": "media/media.json",
        "benchmark": "benchmark/results.json",
        "hardening": "hardening/results.json",
    }
    collected = {
        name: save_json(OUT / path, DEST / f"{name}.json") for name, path in sources.items()
    }
    assert all(item["passed"] for item in collected.values())
    hashes = {
        collected[name]["source_sha256"]
        for name in (
            "gui-final",
            "software-functional",
            "small-functional",
            "soak",
            "clean-environment",
        )
    }
    assert len(hashes) == 1, "Evidence must describe the same runtime source"
    save_json(OUT / "wheelhouse.json", DEST / "wheelhouse.json")
    save_xml(OUT / "pytest-final.xml", DEST / "pytest.xml")
    save_xml(OUT / "clean/pytest.xml", DEST / "clean-pytest.xml")
    for folder in OUT.iterdir():
        if not folder.is_dir() or folder.name in {"clean", "benchmark", "hardening"}:
            continue
        for filename in ("results.json", "capture.json"):
            source = folder / filename
            if source.exists() and folder.name not in {
                "gui-timing-final",
                "soak-first",
                "visual-matrix-v2",
            }:
                save_json(source, DEST / "attempts" / f"{folder.name}-{filename}")
    shutil.copy2(OUT / "benchmark/report.md", DEST / "benchmark-report.md")
    protocol = json.loads((ROOT / "acceptance-v0.2.0.json").read_text())
    rng = np.random.default_rng(protocol["seed"])
    records = []
    engine = Engine(load_config(), OUT / "alignment")
    try:
        for sample, q in enumerate(
            rng.uniform(LOWER, UPPER, (protocol["link_alignment_samples"], 6))
        ):
            engine.world.set_q(q)
            for link, frame in enumerate(link_frames(q)):
                state = pb.getLinkState(
                    engine.world.robot,
                    link,
                    computeForwardKinematics=True,
                    physicsClientId=engine.world.client,
                )
                records.append(
                    dict(
                        sample=sample,
                        link=link,
                        position_error_m=float(np.linalg.norm(frame[:3, 3] - state[4])),
                        orientation_error_rad=float(
                            Rotation.from_matrix(
                                Rotation.from_quat(state[5]).as_matrix() @ frame[:3, :3].T
                            ).magnitude()
                        ),
                    )
                )
    finally:
        engine.close()
    alignment = dict(
        seed=protocol["seed"],
        samples=protocol["link_alignment_samples"],
        comparisons=len(records),
        records=records,
        max_position_error_m=max(r["position_error_m"] for r in records),
        max_orientation_error_rad=max(r["orientation_error_rad"] for r in records),
    )
    alignment["passed"] = (
        alignment["max_position_error_m"] <= protocol["link_alignment_position_max_m"]
        and alignment["max_orientation_error_rad"] <= protocol["link_alignment_rotation_max_rad"]
    )
    assert alignment["passed"]
    (DEST / "model-alignment.json").write_text(json.dumps(alignment, indent=2))
    coverage = json.loads((OUT / "coverage.json").read_text())
    summary = dict(
        totals=coverage["totals"],
        scope="pytest only; separate actual GUI runs are not coverage-instrumented",
    )
    (DEST / "coverage-summary.json").write_text(json.dumps(summary, indent=2))
    manifest = dict(
        source_sha256=hashes.pop(),
        local_checks_passed=True,
        remote_ci_evidence="Recorded separately in remote-ci.json; inspect its tested commit",
        evidence=sources,
        media=[
            dict(
                path=p.relative_to(ROOT).as_posix(),
                sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
            )
            for p in sorted((ROOT / "docs/media").rglob("workstation*"))
            if p.is_file()
        ],
    )
    (DEST / "local-verification.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
