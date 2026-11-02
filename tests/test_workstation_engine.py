"""Workstation orchestration must preserve the verified control semantics."""

import json
import threading

import numpy as np
import pybullet as pb
import pytest
from scipy.spatial.transform import Rotation

from robotarm_lab.config import load_config
from robotarm_lab.kinematics import fk
from robotarm_lab.model import HOME, LOWER, UPPER, CommandError
from robotarm_lab.workstation.engine import DEMO, Engine
from robotarm_lab.workstation.geometry import MESHES, collision_parts, link_frames, robot_parts


@pytest.fixture
def engine(tmp_path):
    item = Engine(load_config(), tmp_path)
    yield item
    item.close()


def finish(engine):
    for _ in range(10000):
        engine.tick(engine.config.control_dt)
        if engine.control.state != "RUNNING" and not engine.sequence:
            return
    raise AssertionError("Execution did not terminate")


def test_visual_frames_crosscheck_every_link(engine):
    rng = np.random.default_rng(20261103)
    for q in rng.uniform(LOWER, UPPER, (100, 6)):
        engine.world.set_q(q)
        frames = link_frames(q)
        for i, frame in enumerate(frames):
            state = pb.getLinkState(
                engine.world.robot,
                i,
                computeForwardKinematics=True,
                physicsClientId=engine.world.client,
            )
            assert np.linalg.norm(frame[:3, 3] - state[4]) < 1e-6
            error = Rotation.from_matrix(
                Rotation.from_quat(state[5]).as_matrix() @ frame[:3, :3].T
            ).magnitude()
            assert error < 1e-6
        np.testing.assert_allclose(frames[-1][:3, 3], fk(q).position, atol=1e-12)


def test_original_mesh_integrity():
    for mesh in MESHES.values():
        assert mesh.ndim == 2 and mesh.shape[1] == 6 and len(mesh) % 3 == 0
        assert np.isfinite(mesh).all()
        np.testing.assert_allclose(np.linalg.norm(mesh[:, 3:], axis=1), 1, atol=1e-6)
    assert len(robot_parts()) > 50
    assert len(collision_parts()) == 8
    for part in robot_parts():
        assert part.mesh in MESHES and -1 <= part.frame <= 6
        assert np.linalg.det(part.local[:3, :3]) > 0


def test_preview_atomic_execute_limits(engine):
    before = engine.control.q
    engine.preview_joint(DEMO[0])
    np.testing.assert_array_equal(before, engine.control.q)
    assert engine.control.state == "IDLE" and len(engine.preview_path) == 101
    engine.execute()
    finish(engine)
    np.testing.assert_allclose(engine.control.q, DEMO[0], atol=1e-12)
    assert not engine.world.collisions(engine.control.q)


def test_failed_preview_invalidates_previous(engine):
    engine.preview_joint(DEMO[0])
    with pytest.raises(CommandError):
        engine.preview_joint([99] * 6)
    assert engine.preview is None
    with pytest.raises(CommandError, match="Preview"):
        engine.execute()


def test_pose_ik_preview_independent(engine):
    target = fk(DEMO[0])
    rpy = Rotation.from_matrix(target.rotation).as_euler("xyz", degrees=True)
    engine.preview_pose([*target.position, *rpy])
    np.testing.assert_array_equal(engine.control.q, HOME)
    engine.execute()
    finish(engine)
    np.testing.assert_allclose(fk(engine.control.q).position, target.position, atol=1e-4)


def test_pause_resume_speed_freeze(engine):
    engine.move(DEMO[0])
    for _ in range(30):
        engine.tick(0.01)
    engine.pause()
    before = engine.control.q
    for _ in range(20):
        engine.tick(0.01)
    np.testing.assert_array_equal(engine.control.q, before)
    assert engine.snapshot().state == "PAUSED"
    engine.set_speed(0.25)
    engine.resume()
    finish(engine)
    np.testing.assert_array_equal(engine.control.q, np.array(DEMO[0]))
    engine.move(HOME)
    engine.set_speed(0.75)
    engine.cancel.set()
    engine.tick(0.01)
    assert engine.snapshot().state == "STOPPED" and engine.preview is None
    before = engine.control.q
    engine.tick(0.01)
    np.testing.assert_array_equal(before, engine.control.q)


def test_modes_jog_and_program(engine):
    engine.jog(0, 1)
    finish(engine)
    assert engine.control.q[0] == pytest.approx(np.deg2rad(1))
    with pytest.raises(CommandError, match="AUTO"):
        engine.program(DEMO)
    engine.set_mode("AUTO")
    with pytest.raises(CommandError, match="MANUAL"):
        engine.jog(0, 1)
    engine.program(DEMO)
    with pytest.raises(CommandError):
        engine.set_mode("MANUAL")
    finish(engine)
    np.testing.assert_array_equal(engine.control.q, HOME)


def test_obstacles_block_preview_and_runtime(engine):
    engine.blocker()
    before = engine.control.q
    with pytest.raises(CommandError, match="Collision"):
        engine.preview_joint(DEMO[0])
    np.testing.assert_array_equal(before, engine.control.q)
    engine.clear_boxes()
    engine.preview_joint(DEMO[0])
    engine.execute()
    engine.tick(0.01)
    before = engine.control.q
    engine.add_box(fk(before).position, [0.025] * 3)
    engine.tick(0.01)
    assert engine.snapshot().state == "BLOCKED"
    np.testing.assert_array_equal(before, engine.control.q)
    engine.reset()
    assert not engine.obstacles
    np.testing.assert_array_equal(engine.control.q, HOME)


def test_stale_scene_preview_cannot_execute(engine):
    engine.preview_joint(DEMO[0])
    engine.add_box([2, 2, 2], [0.1] * 3)
    with pytest.raises(CommandError):
        engine.execute()


def test_teach_atomic_persistence(engine, monkeypatch):
    engine.teach_save("Inspection A")
    disk = json.loads((engine.output / "teach-points.json").read_text())
    assert disk["points"]["Inspection A"] == HOME.tolist()
    engine.teach = {}
    engine.load_teach()
    assert "Inspection A" in engine.teach
    with pytest.raises(CommandError):
        engine.teach_save("\n")
    engine.teach_delete("Inspection A")
    assert engine.teach == {}


def test_teach_corrupt_and_bounded(engine):
    path = engine.output / "teach-points.json"
    path.write_text('{"schema":1,"points":{"bad":[100,0,0,0,0,0]}}')
    with pytest.raises(CommandError):
        engine.load_teach()
    assert engine.teach == {}
    engine.teach = {f"Point {i}": HOME.tolist() for i in range(100)}
    with pytest.raises(CommandError, match="full"):
        engine.teach_save("extra")


def test_log_fault_recovery(engine):
    log = engine.control.log
    engine.control.log = engine.output  # directory: deterministic I/O failure
    with pytest.raises(CommandError, match="Event log"):
        engine.move(DEMO[0])
    assert engine.control.state == "FAULT"
    engine.control.log = log
    engine.reset()
    assert engine.control.state == "IDLE"


def test_cancel_path_before_execution(engine):
    engine.cancel.set()
    with pytest.raises(CommandError, match="cancelled"):
        engine.preview_joint(DEMO[0])
    np.testing.assert_array_equal(engine.control.q, HOME)
    engine.freeze()
    assert not engine.cancel.is_set()


def test_worker_world_ownership(engine):
    errors = []

    def wrong_thread():
        try:
            engine.snapshot()
        except RuntimeError as exc:
            errors.append(str(exc))

    thread = threading.Thread(target=wrong_thread)
    thread.start()
    thread.join()
    assert errors and "non-owner" in errors[0]


@pytest.mark.parametrize("speed", [0, 1.1, float("nan"), True, "fast"])
def test_invalid_speed(engine, speed):
    with pytest.raises(CommandError):
        engine.set_speed(speed)


def test_event_history_bounded(engine):
    for i in range(1500):
        engine.notify("test", str(i))
    assert len(engine.events) == 500
    assert engine.events[-1][3] == "1499"


def test_obstacle_edit_is_transactional(engine):
    engine.add_box([1, 1, 1], [0.1] * 3)
    before = engine.snapshot().obstacles
    body = before[0][0]
    with pytest.raises(CommandError):
        engine.update_box(body, [2, 2, 2], [-1] * 3)
    assert engine.snapshot().obstacles == before
    engine.preview_joint(DEMO[0])
    engine.update_box(body, [2, 2, 2], [0.2] * 3)
    assert engine.preview is None
    assert len(engine.obstacles) == len(engine.world.obstacles) == 1
    assert engine.obstacles[0][1] == (2, 2, 2)
    engine.remove_box(engine.obstacles[0][0])
    assert not engine.world.obstacles and not engine.obstacles
    with pytest.raises(CommandError):
        engine.remove_box(9999)
