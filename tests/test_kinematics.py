import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from robotarm_lab.config import load_config
from robotarm_lab.kinematics import fk, pose_error, solve_ik
from robotarm_lab.model import HOME, LOWER, UPPER, CommandError, Pose, joints
from robotarm_lab.simulation import World


def test_zero_geometry():
    pose = fk(np.zeros(6))
    np.testing.assert_allclose(pose.position, [0.92, 0, 0.34], atol=1e-12)
    np.testing.assert_allclose(pose.rotation, np.eye(3), atol=1e-12)


def test_fk_against_bullet_random_and_limits():
    rng = np.random.default_rng(82)
    with World() as world:
        for q in [LOWER, UPPER, HOME, *rng.uniform(LOWER, UPPER, (50, 6))]:
            world.set_q(q)
            pe, re = pose_error(fk(q), world.tcp())
            assert pe < 2e-6
            assert re < 2e-6


@pytest.mark.parametrize("bad", [[0] * 5, [0] * 7, [np.nan] * 6, [np.inf] * 6, [4] * 6])
def test_joint_validation(bad):
    with pytest.raises(CommandError):
        joints(bad)


@pytest.mark.parametrize("rotation", [np.zeros((3, 3)), np.diag([1, 1, -1]), np.ones((2, 2))])
def test_invalid_pose(rotation):
    with pytest.raises(CommandError):
        Pose(np.zeros(3), rotation)


def test_ik_independent_target_and_orientation():
    q = np.array([0.4, -0.8, 1.2, 0.5, -0.6, 0.7])
    with World() as world:
        world.set_q(q)
        target = world.tcp()
        result = solve_ik(target, HOME, load_config())
        world.set_q(result.q)
        pe, re = pose_error(world.tcp(), target)
        assert pe < 1e-4 and re < 1e-3


def test_unreachable_and_bad_seed():
    with pytest.raises(CommandError, match="Unreachable"):
        solve_ik(Pose(np.array([5.0, 0, 0]), np.eye(3)), HOME, load_config())
    with pytest.raises(CommandError):
        solve_ik(fk(HOME), [9] * 6, load_config())


def test_orientation_error_near_pi():
    p = Pose(np.zeros(3), np.eye(3))
    other = Pose(np.zeros(3), Rotation.from_rotvec([0, 0, np.pi - 1e-8]).as_matrix())
    assert pose_error(p, other)[1] == pytest.approx(np.pi - 1e-8)


def test_cold_start_elbow_branch_regression():
    # First fixed-seed run case 21: random-only restarts missed this reachable branch.
    q = np.array(
        [-0.533722386, -0.038542575, -1.331570574, 0.291978607, -1.258928129, -0.246432036]
    )
    with World() as world:
        target = world.pose_at(q)
        result = solve_ik(target, HOME, load_config())
        pe, re = pose_error(world.pose_at(result.q), target)
        assert pe < 1e-4 and re < 1e-3


def test_singular_straight_arm_is_validated():
    result = solve_ik(fk(np.zeros(6)), HOME, load_config())
    pe, re = pose_error(fk(result.q), fk(np.zeros(6)))
    assert pe < 1e-4 and re < 1e-3
