import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from robotarm_lab.config import load_config
from robotarm_lab.controller import Controller
from robotarm_lab.model import HOME, LOWER, UPPER, CommandError, Pose
from robotarm_lab.simulation import World
from robotarm_lab.trajectory import Trajectory, plan

SCENES = json.loads((Path(__file__).parent / "data/hardening-corpus.json").read_text())["scenes"]


@pytest.mark.parametrize("scene", SCENES[32:], ids=lambda s: f"thin-{s['id']}")
def test_thin_known_contact_is_rejected(scene):
    with World() as world:
        world.set_q(scene["start"])
        world.add_box(scene["center"], scene["half_extents"])
        assert world.collisions(scene["known_q"], 0)
        before = world.get_q()
        with pytest.raises(CommandError, match="Collision"):
            Controller(world, load_config()).move(scene["goal"])
        np.testing.assert_array_equal(world.get_q(), before)


def test_close_is_idempotent_even_when_client_id_is_reused():
    first = World()
    first.close()
    with World() as second:
        first.close()
        np.testing.assert_array_equal(second.get_q(), HOME)
        with pytest.raises(RuntimeError, match="closed"):
            first.set_q(HOME + 0.1)


def test_shape_resource_cache_and_reset():
    with World() as world:
        for _ in range(1000):
            world.add_box([2, 0, 0], [0.1] * 3)
            world.clear_obstacles()
        assert len(world._box_shapes) == 1
        for i in range(127):
            world.add_box([2, 0, 0], [0.02 + i * 0.0001, 0.03, 0.04])
            world.clear_obstacles()
        assert len(world._box_shapes) == 128
        with pytest.raises(CommandError, match="Shape budget"):
            world.add_box([2, 0, 0], [0.3] * 3)
        Controller(world, load_config()).reset()
        assert not world._box_shapes
        world.add_box([2, 0, 0], [0.3] * 3)


def test_active_obstacle_budget():
    with World() as world:
        for _ in range(128):
            world.add_box([2, 0, 0], [0.1] * 3)
        with pytest.raises(CommandError, match="Obstacle budget"):
            world.add_box([2, 0, 0], [0.1] * 3)


def test_log_io_failure_freezes_without_executing(tmp_path):
    with World() as world:
        controller = Controller(
            world, load_config(), tmp_path
        )  # Directory cannot be an event file.
        with pytest.raises(CommandError, match="Event log unavailable"):
            controller.move(HOME + 0.1)
        assert controller.state == "FAULT" and controller.trajectory is None
        np.testing.assert_array_equal(controller.q, HOME)
        controller.step()
        np.testing.assert_array_equal(controller.q, HOME)


@pytest.mark.parametrize("q", [LOWER, UPPER, *[np.where(np.arange(6) % 2, LOWER, UPPER)]])
def test_extreme_pose_collision_query_restores(q):
    with World() as world:
        world.collisions(q)
        np.testing.assert_array_equal(world.get_q(), HOME)
        trajectory = plan(HOME, q, load_config())
        np.testing.assert_array_equal(trajectory.sample(trajectory.duration)[0], q)


@pytest.mark.parametrize("bad", [True, "0.02", [0.02], float("nan"), float("inf")])
def test_non_scalar_controller_inputs(bad):
    with World() as world:
        controller = Controller(world, load_config())
        with pytest.raises(ValueError):
            controller.step(bad)
        with pytest.raises(ValueError):
            world.collisions(HOME, bad)


@pytest.mark.parametrize("size", [(0, 240), (10**9, 10**9), (True, 240), (320.0, 240)])
def test_renderer_allocation_guard(size):
    with World() as world:
        with pytest.raises(CommandError, match="dimensions"):
            world.render(*size)


@pytest.mark.parametrize("duration", [1e-300, 1e300, True, [1.0], "1"])
def test_pathological_durations_reject(duration):
    with pytest.raises(ValueError):
        Trajectory(HOME, HOME, duration)


def test_huge_finite_sample_times_saturate_without_overflow():
    trajectory = plan(HOME, HOME + 0.1, load_config())
    with np.errstate(all="raise"):
        np.testing.assert_array_equal(trajectory.sample(1e308)[0], trajectory.goal)
        np.testing.assert_array_equal(trajectory.sample(-1e308)[0], trajectory.start)


def test_numeric_timing_overflow_is_a_rejection():
    config = replace(load_config(), velocity=np.full(6, np.nextafter(0.0, 1.0)))
    with pytest.raises(CommandError, match="numeric range"):
        plan(HOME, HOME + 0.1, config)


def test_rotation_validation_does_not_allow_relative_tolerance_slack():
    with pytest.raises(CommandError, match="SO"):
        Pose(np.zeros(3), np.eye(3) * 1.000001)
