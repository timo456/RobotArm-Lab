from dataclasses import replace

import numpy as np
import pytest

from robotarm_lab.config import load_config
from robotarm_lab.model import HOME, LOWER, UPPER, CommandError
from robotarm_lab.trajectory import plan


def test_analytic_and_sampled_limits():
    config = load_config()
    rng = np.random.default_rng(19)
    for _ in range(20):
        q0, q1 = rng.uniform(LOWER, UPPER, (2, 6))
        t = plan(q0, q1, config)
        for time in np.linspace(0, t.duration, 101):
            q, v, a = t.sample(time)
            assert np.all(q >= LOWER) and np.all(q <= UPPER)
            assert np.all(np.abs(v) <= config.velocity + 1e-9)
            assert np.all(np.abs(a) <= config.acceleration + 1e-9)
        for time, endpoint in [(0, q0), (t.duration, q1)]:
            q, v, a = t.sample(time)
            np.testing.assert_allclose(q, endpoint, atol=1e-12)
            np.testing.assert_allclose(v, 0, atol=1e-12)
            np.testing.assert_allclose(a, 0, atol=1e-12)
        samples = list(t.collision_samples(0.01))
        assert np.max(np.abs(np.diff(samples, axis=0))) <= 0.010000001


def test_derivatives_match_finite_differences():
    trajectory = plan(HOME, HOME + 0.3, load_config())
    t, h = trajectory.duration * 0.3, 1e-5
    q0, v0, _ = trajectory.sample(t - h)
    q1, v1, _ = trajectory.sample(t + h)
    _, v, a = trajectory.sample(t)
    np.testing.assert_allclose((q1 - q0) / (2 * h), v, atol=1e-8)
    np.testing.assert_allclose((v1 - v0) / (2 * h), a, atol=1e-8)


@pytest.mark.parametrize("duration", [0, -1, float("nan"), float("inf"), 0.0001])
def test_invalid_duration(duration):
    with pytest.raises(CommandError):
        plan(HOME, HOME + 0.2, load_config(), duration)


def test_zero_move_and_long_duration():
    trajectory = plan(HOME, HOME, load_config())
    np.testing.assert_array_equal(trajectory.sample(100)[0], HOME)
    assert plan(HOME, HOME + 0.1, load_config(), 10).duration == 10
    with pytest.raises(CommandError):
        trajectory.sample(float("nan"))


@pytest.mark.parametrize(
    "change",
    [
        {"velocity": [0] * 6},
        {"acceleration": [1] * 5},
        {"control_dt": 0.1},
        {"collision_margin": -1},
        {"ik_restarts": 0},
        {"collision_joint_step": float("nan")},
    ],
)
def test_config_rejects_invalid(change):
    with pytest.raises(ValueError):
        replace(load_config(), **change)


def test_exact_limit_endpoints_and_invalid_sampling():
    trajectory = plan(LOWER, UPPER, load_config())
    np.testing.assert_array_equal(trajectory.sample(trajectory.duration)[0], UPPER)
    np.testing.assert_array_equal(trajectory.sample(0)[0], LOWER)
    for u in [1 - 1e-7, 1 - 1e-12, 1]:
        q = trajectory.sample(u * trajectory.duration)[0]
        assert np.all(q >= LOWER) and np.all(q <= UPPER)
    for step in [0, -1, float("nan")]:
        with pytest.raises(CommandError):
            trajectory.collision_samples(step)
