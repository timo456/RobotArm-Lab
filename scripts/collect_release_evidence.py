"""Sanitize local test evidence and generate a traceable old/new release comparison."""

import json
import shutil
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "reports/v0.1.1"


def sanitize_xml(source: Path, target: Path) -> None:
    tree = ElementTree.parse(source)
    for element in tree.iter():
        element.attrib.pop("hostname", None)
        if element.text:
            element.text = element.text.replace(str(ROOT), "<project>")
            # Tracebacks refer to the interpreter's base install. Remove local user segments.
            import re

            element.text = re.sub(r"C:[/\\]Users[/\\][^/\\\s]+", "<user-home>", element.text)
            element.text = "\n".join(line.rstrip() for line in element.text.split("\n"))
    tree.write(target, encoding="utf-8", xml_declaration=True)


def main() -> None:
    DEST.mkdir(exist_ok=True)
    for name in ["p1-before", "p1-after", "ik-first", "pytest-first-full", "pytest-final"]:
        source = ROOT / f"outputs/v0.1.1/{name}.xml"
        if source.exists():
            sanitize_xml(source, DEST / f"{name}.xml")
    for name, source in {
        "gui-smoke.json": "outputs/v0.1.1/gui-smoke/results.json",
        "wheelhouse.json": "outputs/v0.1.1/wheelhouse.json",
        "clean-environment.json": "outputs/v0.1.1/clean/results.json",
    }.items():
        shutil.copy2(ROOT / source, DEST / name)
    sanitize_xml(ROOT / "outputs/v0.1.1/clean/pytest.xml", DEST / "clean-pytest.xml")
    events = [
        json.loads(line)
        for line in (ROOT / "outputs/v0.1.1/native-gui/session.jsonl").read_text().splitlines()
    ]
    actions = {r.get("action") for r in events if r["event"] == "keyboard_action"}
    native_checks = dict(
        keyboard_commands={"demo", "home", "blocker", "clear", "stop", "reset", "ik"} <= actions,
        move_completed=any(r["event"] == "completed" for r in events),
        obstacle_rejected=any(
            r["event"] == "rejected" and "Collision" in r.get("reason", "") for r in events
        ),
        ik_solved=any(r["event"] == "ik_solved" for r in events),
        stop_recorded=any(r["event"] == "stopped" for r in events),
        reset_recorded=any(r["event"] == "reset" for r in events),
    )
    native = dict(
        passed=all(native_checks.values()),
        checks=native_checks,
        events=events,
        method="Native Windows sky.press_key input; independent JSONL command evidence",
        screenshots_verified=False,
        mouse_clicks_verified=False,
        stop_during_motion_native_verified=False,
        capture_error="window capture timed out: timed out waiting on channel",
        click_error="coordinate input geometry is unavailable",
        notes="Escape arrived after motion completed; stop-during-motion is separately "
        "verified by controller and Tk callback tests, not this native trace",
    )
    (DEST / "native-gui.json").write_text(json.dumps(native, indent=2), encoding="utf-8")
    baseline = json.loads((DEST / "baseline-replay/results.json").read_text())
    final = json.loads((DEST / "final/results.json").read_text())
    assert baseline["corpus_sha256"] == final["corpus_sha256"]
    assert baseline["protocol_sha256"] == final["protocol_sha256"]
    assert baseline["harness_sha256"] == final["harness_sha256"]
    lines = [
        "# v0.1.0 / v0.1.1 controlled comparison",
        "",
        "Same explicit corpus, environment and harness. Original v0.1.0 reports remain untouched.",
        "",
        "| Cohort | v0.1.0 success | v0.1.1 success | old p50/p95 ms | new p50/p95 ms |",
        "|---|---:|---:|---:|---:|",
    ]
    for group in ("cold", "boundary", "singular", "unreachable"):
        a, b = baseline["summary"][group], final["summary"][group]
        lines.append(
            f"| {group} | {a['successes']}/{a['total']} | {b['successes']}/{b['total']} "
            f"| {a['p50_ms']:.3f}/{a['p95_ms']:.3f} | {b['p50_ms']:.3f}/{b['p95_ms']:.3f} |"
        )
    lines += [
        "",
        "Unreachable success means rejection, not an IK solution.",
        "The extra geometric enumeration adds median overhead; singular-case latency is not",
        "improved in this run. The improvement is branch reliability and tail/unreachable latency,",
        "not a claim that every case became faster. Simulator position quantization can yield",
        "zero reported differences; this does not imply infinite physical accuracy.",
        "",
        "## Failures retained and explained",
        "",
    ]
    for case in baseline["ik_cases"]:
        if not case["success"]:
            repaired = next(c for c in final["ik_cases"] if c["id"] == case["id"])
            lines.append(
                f"- Case {case['id']} ({case['group']}): `{case['reason']}`. "
                f"New success={repaired['success']}, attempts={repaired.get('attempts')}. "
                "The original starts hit local minima/boundary branches; "
                "geometry-derived branches provide a validated alternative."
            )
    lines += [
        "",
        "The user-supplied historical 79/80 and 45/48 rates had no attached case identities.",
        "This new frozen corpus independently reproduces those rates; identical original cases",
        "are not asserted. Explicit target data and hashes make this comparison replayable.",
        "",
        "## Safety and resources",
        "",
        "| Metric | v0.1.0 | v0.1.1 |",
        "|---|---:|---:|",
    ]
    for label, section, key in [
        ("Misses versus dense discrete reference", "collisions", "false_negatives"),
        ("Atomic rejection pose changes", "collisions", "pose_changes"),
        ("Fail-closed stress rejections", "resources", "rejections"),
        ("Peak traced bytes", "resources", "peak_tracemalloc_bytes"),
        ("Stress RSS growth bytes", "resources", "rss_growth_bytes"),
        ("Rejection p95 ms", "resources", "p95_ms"),
    ]:
        lines.append(
            f"| {label} | {baseline['summary'][section][key]} | {final['summary'][section][key]} |"
        )
    lines += [
        "",
        "Legacy oversized allocation calls were intercepted by the audit harness before",
        "allocation; its memory/timing figures do not represent a real OOM run. v0.1.1 uses",
        "normal production rejection. Both reports retain the intervention count.",
        "Dense reference resolution is 0.0005 rad, not continuous collision ground truth.",
        "RSS includes allocator/cache effects; traced allocations and RSS are reported separately.",
    ]
    (DEST / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    unit_suites = list(ElementTree.parse(DEST / "pytest-final.xml").iter("testsuite"))
    unit_pass = bool(unit_suites) and all(
        int(s.get("failures", "0")) == 0
        and int(s.get("errors", "0")) == 0
        and int(s.get("skipped", "0")) == 0
        for s in unit_suites
    )
    legacy = json.loads((DEST / "legacy-regression/results.json").read_text())["passed"]
    decision = dict(
        local_engineering_go=unit_pass
        and legacy
        and final["passed"]
        and native["passed"]
        and json.loads((DEST / "gui-smoke.json").read_text())["passed"]
        and json.loads((DEST / "clean-environment.json").read_text())["passed"],
        unit_tests=sum(int(s.get("tests", "0")) for s in unit_suites),
        unit_tests_passed_without_skips=unit_pass,
        legacy_protocol_passed=legacy,
        remote_ci_verified=False,
        linux_execution_verified=False,
        native_mouse_and_pixel_capture_verified=False,
        published=False,
    )
    (DEST / "decision.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
