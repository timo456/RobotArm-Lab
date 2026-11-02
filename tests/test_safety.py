import json

import numpy as np
import pytest

from robotarm_lab.config import load_config
from robotarm_lab.controller import Controller
from robotarm_lab.kinematics import fk
from robotarm_lab.model import HOME, CommandError
from robotarm_lab.simulation import World


@pytest.fixture
def control(tmp_path):
    with World() as world:
        yield Controller(world, load_config(), tmp_path / "events.jsonl")


def test_normal_home_stop_reset_and_log(control):
    target = HOME + [0.2, -0.1, 0.05, 0.1, -0.1, 0.2]
    control.move(target)
    with pytest.raises(CommandError, match="Busy"):
        control.home()
    control.run_until_idle()
    np.testing.assert_allclose(control.q, target, atol=1e-12)
    control.home()
    control.step()
    control.stop()
    q = control.q
    control.step()
    np.testing.assert_array_equal(control.q, q)
    control.world.add_box([2, 0, 0], [0.1] * 3)
    control.reset()
    assert control.state == "IDLE" and not control.world.obstacles
    np.testing.assert_array_equal(control.q, HOME)
    events = [json.loads(line)["event"] for line in control.log.read_text().splitlines()]
    assert {"accepted", "completed", "rejected", "stopped", "reset"} <= set(events)


def test_endpoint_collision_rejects_atomically(control):
    target = HOME.copy()
    target[0] = -0.7
    control.world.add_box(fk(target).position, [0.04] * 3)
    before = control.q
    with pytest.raises(CommandError, match="Collision"):
        control.move(target)
    np.testing.assert_array_equal(control.q, before)
    assert control.state == "IDLE"


def test_path_collision_with_clear_endpoints(control):
    start, goal = HOME.copy(), HOME.copy()
    start[0], goal[0] = -0.7, 0.7
    control.world.set_q(start)
    control.world.add_box(fk(HOME).position, [0.025] * 3)
    assert not control.world.collisions(start)
    assert not control.world.collisions(goal)
    with pytest.raises(CommandError, match="Collision"):
        control.move(goal)
    np.testing.assert_array_equal(control.q, start)


def test_scene_change_blocks_execution(control):
    control.move(HOME + [0.3, 0, 0, 0, 0, 0])
    control.step()
    before = control.q
    control.world.add_box(fk(before).position, [0.03] * 3)
    control.step()
    assert control.state == "BLOCKED"
    np.testing.assert_array_equal(control.q, before)


def test_floor_and_self_collision_detection(control):
    q = np.zeros(6)
    q[1] = 1.4
    assert any(c.kind == "floor" for c in control.world.collisions(q))
    # Fold the upper arm toward its mounting pedestal.
    q = np.array([0, 1.8, 2.2, 0, 0, 0])
    assert any(c.kind == "self" for c in control.world.collisions(q))


def test_worlds_are_isolated_and_query_restores(control):
    before = control.q
    with World() as other:
        other.set_q(HOME + 0.1)
        control.world.collisions(HOME + 0.2)
        np.testing.assert_array_equal(control.q, before)
        np.testing.assert_allclose(other.get_q(), HOME + 0.1)


@pytest.mark.parametrize("dt", [0, -0.1, 0.1, float("nan")])
def test_bad_step(control, dt):
    with pytest.raises(CommandError):
        control.step(dt)


def test_bad_obstacles_and_commands(control):
    for center, half in [([0, 0], [0.1] * 3), ([0] * 3, [-1] * 3), ([np.nan] * 3, [1] * 3)]:
        with pytest.raises(CommandError):
            control.world.add_box(center, half)
    with pytest.raises(CommandError):
        control.move([8] * 6)
    assert not control.world.obstacles
    np.testing.assert_array_equal(control.q, HOME)


def test_move_pose(control):
    target = fk(HOME + [0.15, -0.1, 0.1, 0.1, 0.1, 0.1])
    control.move_pose(target)
    control.run_until_idle()
    np.testing.assert_allclose(fk(control.q).position, target.position, atol=1e-4)


def test_independent_pose_validator_rejects_model_mismatch(control, monkeypatch):
    monkeypatch.setattr(control.world, "pose_at", lambda q: fk(HOME + 0.3))
    with pytest.raises(CommandError, match="Independent simulator"):
        control.move_pose(fk(HOME))
    np.testing.assert_array_equal(control.q, HOME)


def test_busy_pose_command_cannot_replace_active_trajectory(control):
    trajectory = control.move(HOME + 0.1)
    with pytest.raises(CommandError, match="Busy"):
        control.move_pose(fk(HOME))
    assert control.trajectory is trajectory and control.state == "RUNNING"
