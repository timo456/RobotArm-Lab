import tracemalloc
from dataclasses import replace
from itertools import islice

import numpy as np
import pytest

from robotarm_lab.config import load_config
from robotarm_lab.controller import Controller
from robotarm_lab.model import HOME, CommandError
from robotarm_lab.simulation import World
from robotarm_lab.trajectory import plan


@pytest.mark.parametrize(
    "step",
    [
        1e-300,
        np.nextafter(0.0, 1.0),
        1e-12,
        0.0,
        -1.0,
        float("inf"),
        float("nan"),
        True,
        [0.01],
        "0.01",
    ],
)
def test_config_rejects_unsupported_steps(step):
    with pytest.raises(ValueError):
        replace(load_config(), collision_joint_step=step)


def test_oversized_sampling_rejects_before_any_allocation(monkeypatch):
    trajectory = plan(HOME, HOME + 0.2, load_config())
    monkeypatch.setattr(np, "linspace", lambda *a, **kw: pytest.fail("Eager allocation attempted"))
    with pytest.raises(CommandError, match="budget|step"):
        trajectory.collision_samples(1e-6)


def test_stream_preserves_precision_and_endpoints():
    trajectory = plan(HOME, HOME + 0.004, load_config())
    samples = trajectory.collision_samples(1e-6)
    assert iter(samples) is samples
    values = list(samples)
    assert len(values) <= 10000
    np.testing.assert_array_equal(values[0], trajectory.start)
    np.testing.assert_array_equal(values[-1], trajectory.goal)
    assert np.max(np.abs(np.diff(values, axis=0))) <= 1e-6 + 1e-14


def test_bounded_peak_allocation():
    trajectory = plan(HOME, HOME + 0.008, load_config())
    tracemalloc.start()
    try:
        for _ in range(1000):
            for _q in islice(trajectory.collision_samples(1e-6), 3):
                pass
        assert tracemalloc.get_traced_memory()[1] < 8 * 1024 * 1024
    finally:
        tracemalloc.stop()


def test_budget_rejection_is_atomic_and_does_not_query_world(monkeypatch):
    with World() as world:
        controller = Controller(world, replace(load_config(), collision_joint_step=1e-6))
        monkeypatch.setattr(
            world, "collisions", lambda *a: pytest.fail("Queried before budget check")
        )
        with pytest.raises(CommandError, match="budget"):
            controller.move(HOME + 0.1)
        np.testing.assert_array_equal(controller.q, HOME)
        assert controller.state == "IDLE" and controller.trajectory is None
