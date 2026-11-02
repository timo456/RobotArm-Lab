import json
from pathlib import Path

from robotarm_lab.config import load_config
from robotarm_lab.experiments import benchmark
from robotarm_lab.model import CommandError

PROTOCOL = Path(__file__).resolve().parents[1] / "acceptance.json"


def test_real_fixed_seed_protocol_and_report(tmp_path):
    result = benchmark(load_config(), PROTOCOL, tmp_path)
    assert result["passed"]
    assert len(result["cases"]) == 151
    assert json.loads((tmp_path / "results.json").read_text())["checks"] == result["checks"]
    assert (tmp_path / "report.md").is_file()


def test_failed_ik_cases_are_retained_and_fail_gate(tmp_path, monkeypatch):
    def fail(*args):
        raise CommandError("Injected solver failure for reporting test")

    monkeypatch.setattr("robotarm_lab.experiments.solve_ik", fail)
    result = benchmark(load_config(), PROTOCOL, tmp_path)
    assert not result["passed"]
    failed = [c for c in result["cases"] if c.get("success") is False]
    assert len(failed) == 36
    assert all("Injected" in c["reason"] for c in failed)
    assert result["summary"]["ik_position_max_m"] is None
    assert "n/a" in (tmp_path / "report.md").read_text()
