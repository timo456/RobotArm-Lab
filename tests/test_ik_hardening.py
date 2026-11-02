import json
from pathlib import Path

import numpy as np
import pytest

from robotarm_lab.config import load_config
from robotarm_lab.kinematics import pose_error, solve_ik
from robotarm_lab.model import LOWER, UPPER, CommandError, Pose
from robotarm_lab.simulation import World

CASES = json.loads((Path(__file__).parent / "data/hardening-corpus.json").read_text())["ik"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['group']}-{c['id']}")
def test_frozen_ik_corpus(case):
    target = Pose(np.array(case["position"]), np.array(case["rotation"]))
    if case["group"] == "unreachable":
        with pytest.raises(CommandError, match="Unreachable"):
            solve_ik(target, case["seed"], load_config())
        return
    result = solve_ik(target, case["seed"], load_config())
    assert np.all(result.q >= LOWER) and np.all(result.q <= UPPER)
    with World() as world:
        pe, re = pose_error(world.pose_at(result.q), target)
    assert pe <= 1e-4 and re <= 1e-3
    assert result.attempts <= 8 and result.diagnostics


def test_multistart_is_deterministic_and_records_bounded_attempts():
    case = CASES[12]  # Failed baseline cold-start case; not a hand-picked new target.
    target = Pose(np.array(case["position"]), np.array(case["rotation"]))
    a = solve_ik(target, case["seed"], load_config())
    b = solve_ik(target, case["seed"], load_config())
    np.testing.assert_array_equal(a.q, b.q)
    assert a.attempts == b.attempts
    assert a.attempts > 1
    assert a.diagnostics[0]["position_error"] > 1e-4
