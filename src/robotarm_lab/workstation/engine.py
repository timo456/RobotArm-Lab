"""Single-owner workstation orchestration, without any Qt or rendering dependency."""

import json
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from time import monotonic, strftime

import numpy as np
import pybullet as pb
from scipy.spatial.transform import Rotation

from ..config import Config
from ..controller import Controller
from ..kinematics import fk, pose_error, solve_ik
from ..model import HOME, CommandError, Pose, joints
from ..simulation import World
from ..trajectory import Trajectory, plan
from ..validation import scalar

DEMO = (
    (-0.65, -0.8, 1.15, 0.35, -0.35, 0.5),
    (0.25, -0.65, 0.9, -0.3, -0.2, -0.4),
    tuple(HOME),
)


@dataclass(frozen=True)
class Snapshot:
    q: tuple[float, ...]
    velocity: tuple[float, ...]
    tcp: tuple[float, ...]
    state: str
    mode: str
    speed: float
    elapsed: float
    duration: float
    preview: Trajectory | None
    preview_path: tuple[tuple[float, ...], ...]
    obstacles: tuple[tuple[int, tuple, tuple], ...]
    clearance_contacts: int
    events: tuple[tuple[int, str, str, str], ...]
    teach: tuple[tuple[str, tuple], ...]
    error: str
    sequence: str
    stamp: float


class InterruptibleController(Controller):
    """Same collision oracle and sampling rules, with cooperative user cancellation."""

    def __init__(
        self,
        world: World,
        config: Config,
        log: Path,
        cancel: threading.Event,
        notify: Callable[[str, str], None],
    ) -> None:
        super().__init__(world, config, log)
        self.cancel, self.notify = cancel, notify

    def event(self, kind: str, **data: object) -> None:
        super().event(kind, **data)
        detail = str(data.get("reason", "")) or "; ".join(
            f"{key}: {value:.3f}" if isinstance(value, float) else f"{key}: {value}"
            for key, value in data.items()
        )
        self.notify(kind, detail)

    def validate_path(self, trajectory: Trajectory) -> None:
        for i, q in enumerate(trajectory.collision_samples(self.config.collision_joint_step)):
            if self.cancel.is_set():
                raise CommandError("Operation cancelled by Freeze")
            hits = self.world.collisions(q, self.config.collision_margin)
            if hits:
                raise CommandError(
                    f"Collision clearance rejected at sample {i}: {hits[0].kind}, "
                    f"link {hits[0].link_a}, distance {hits[0].distance:.4f} m"
                )


class Engine:
    """All methods except setting cancel must be called on the creating thread."""

    def __init__(self, config: Config, output: Path, cancel: threading.Event | None = None) -> None:
        self.owner = threading.get_ident()
        self.config, self.output = config, output
        output.mkdir(parents=True, exist_ok=True)
        self.cancel = cancel or threading.Event()
        self.events: deque = deque(maxlen=500)
        self.serial = 0
        self.mode, self.speed = "MANUAL", 0.5
        self.preview: Trajectory | None = None
        self.preview_path: tuple = ()
        self.preview_revision = -1
        self.paused_goal: np.ndarray | None = None
        self.sequence: deque = deque()
        self.sequence_total = 0
        self.obstacles: list[tuple[int, tuple, tuple]] = []
        self.error = ""
        self.phase = ""
        self.teach: dict[str, list[float]] = {}
        self.world = World()
        self.control = InterruptibleController(
            self.world, self.scaled_config(), output / "session.jsonl", self.cancel, self.notify
        )
        try:
            self.load_teach()
        except (OSError, ValueError, TypeError) as exc:
            self.error = f"Teach library was not loaded: {exc}"
            self.notify("warning", self.error)
        self.notify("ready", "RAL-6 simulation connected · control limits active")

    def own(self) -> None:
        if threading.get_ident() != self.owner:
            raise RuntimeError("Control world accessed from a non-owner thread")

    def scaled_config(self) -> Config:
        return replace(
            self.config,
            velocity=self.config.velocity * self.speed,
            acceleration=self.config.acceleration * self.speed**2,
        )

    def notify(self, kind: str, detail: str = "") -> None:
        self.serial += 1
        self.events.append((self.serial, strftime("%H:%M:%S"), kind, detail))

    def available(self) -> None:
        self.own()
        if self.control.state == "RUNNING" or self.paused_goal is not None:
            raise CommandError("Freeze or finish the active motion before this operation")
        if self.control.state == "FAULT":
            raise CommandError("Reset the workstation after resolving the fault")

    def invalidate(self) -> None:
        self.preview, self.preview_path = None, ()

    def preview_joint(self, target: object) -> None:
        self.available()
        self.invalidate()
        trajectory = plan(self.control.q, target, self.control.config)
        self.control.validate_path(trajectory)
        if self.cancel.is_set():
            raise CommandError("Preview cancelled")
        path = tuple(
            tuple(fk(trajectory.sample(t)[0]).position)
            for t in np.linspace(0, trajectory.duration, 101)
        )
        self.preview, self.preview_path = trajectory, path
        self.preview_revision = self.world.revision
        self.error = ""
        self.control.event("preview_ready", duration=trajectory.duration)

    def preview_pose(self, xyz_rpy: object) -> None:
        self.available()
        self.invalidate()
        values = np.asarray(xyz_rpy, dtype=float)
        if values.shape != (6,) or not np.all(np.isfinite(values)):
            raise CommandError("TCP input requires six finite values")
        target = Pose(values[:3], Rotation.from_euler("xyz", values[3:], degrees=True).as_matrix())
        result = solve_ik(target, self.control.q, self.control.config)
        pe, re = pose_error(self.world.pose_at(result.q), target)
        if pe > self.config.ik_position_tolerance or re > self.config.ik_orientation_tolerance:
            raise CommandError("Independent simulator pose validation failed")
        self.preview_joint(result.q)
        self.control.event("ik_solved", position_error=pe, orientation_error=re)

    def execute(self) -> None:
        self.available()
        if self.preview is None:
            raise CommandError("Preview a valid target before execution")
        if self.preview_revision != self.world.revision or not np.array_equal(
            self.control.q, self.preview.start
        ):
            self.invalidate()
            raise CommandError("Preview is stale; preview again after pose or scene changes")
        self.control.move(self.preview.goal, self.preview.duration)
        self.error = ""

    def move(self, goal: object) -> None:
        self.preview_joint(goal)
        self.execute()

    def jog(self, index: int, degrees: float) -> None:
        if self.mode != "MANUAL":
            raise CommandError("Joint jog requires MANUAL mode")
        if type(index) is not int or not 0 <= index < 6:
            raise CommandError("Joint index must be 0..5")
        increment = scalar(degrees, "Jog increment")
        if not 0 < abs(increment) <= 10:
            raise CommandError("Jog increment must be within +/-10 degrees")
        goal = self.control.q
        goal[index] += np.deg2rad(increment)
        self.move(goal)

    def freeze(self) -> None:
        self.own()
        self.sequence.clear()
        self.sequence_total = 0
        self.paused_goal = None
        self.invalidate()
        self.control.stop()
        self.cancel.clear()
        self.phase = ""

    def pause(self) -> None:
        self.own()
        if self.control.state != "RUNNING" or self.control.trajectory is None:
            raise CommandError("Pause requires a running motion")
        self.paused_goal = self.control.trajectory.goal.copy()
        self.control.stop()
        self.control.event("paused", note="Kinematic simulation hold")

    def resume(self) -> None:
        self.own()
        if self.paused_goal is None:
            raise CommandError("No paused motion")
        target = self.paused_goal.copy()
        self.control.move(target)
        self.paused_goal = None
        self.control.event("resumed")

    def set_speed(self, value: object) -> None:
        self.own()
        speed = scalar(value, "Speed override")
        if not 0.1 <= speed <= 1:
            raise CommandError("Speed override must be 10..100 percent")
        running = self.control.state == "RUNNING"
        if running:
            self.pause()
        self.speed = speed
        self.control.config = self.scaled_config()
        self.invalidate()
        if running:
            self.resume()
        self.control.event("speed", ratio=speed)

    def set_mode(self, mode: str) -> None:
        self.available()
        if mode not in ("MANUAL", "AUTO"):
            raise CommandError("Mode must be MANUAL or AUTO")
        self.mode = mode
        self.control.event("mode", mode=mode)

    def program(self, points: list | tuple) -> None:
        self.available()
        if self.mode != "AUTO":
            raise CommandError("Sequence playback requires AUTO mode")
        targets = [joints(p) for p in points]
        if not 1 <= len(targets) <= 100:
            raise CommandError("Sequence must contain 1..100 points")
        self.sequence_total = len(targets)
        self.sequence = deque(targets[1:])
        try:
            self.move(targets[0])
        except Exception:
            self.sequence.clear()
            raise

    def demo(self) -> None:
        self.set_mode("AUTO")
        self.program(DEMO)

    def add_box(self, center: object, half: object) -> None:
        self.own()
        body = self.world.add_box(center, half)
        self.obstacles.append((body, tuple(center), tuple(half)))
        self.invalidate()
        self.control.event("obstacle_added", body=body)

    def blocker(self) -> None:
        self.add_box(fk(DEMO[0]).position, (0.045, 0.045, 0.045))

    def remove_box(self, body: int) -> None:
        self.own()
        if body not in self.world.obstacles:
            raise CommandError("Select an existing obstacle")
        pb.removeBody(body, physicsClientId=self.world.client)
        self.world.obstacles.remove(body)
        self.world.revision += 1
        self.obstacles = [entry for entry in self.obstacles if entry[0] != body]
        self.invalidate()
        self.control.event("obstacle_removed", body=body)

    def update_box(self, body: int, center: object, half: object) -> None:
        self.own()
        if body not in self.world.obstacles:
            raise CommandError("Select an existing obstacle")
        # Validate/allocate the replacement first; failed input leaves the old box intact.
        self.add_box(center, half)
        self.remove_box(body)
        self.control.event("obstacle_updated", replaced=body)

    def clear_boxes(self) -> None:
        self.own()
        self.world.clear_obstacles()
        self.obstacles.clear()
        self.invalidate()
        self.control.event("obstacles_cleared")

    def reset(self) -> None:
        self.own()
        self.cancel.clear()
        self.sequence.clear()
        self.sequence_total = 0
        self.paused_goal = None
        self.control.reset()
        self.obstacles.clear()
        self.invalidate()
        self.error, self.phase = "", ""

    def load_teach(self) -> None:
        path = self.output / "teach-points.json"
        if not path.exists():
            return
        if path.stat().st_size > 100_000:
            raise CommandError("Teach library exceeds size limit")
        data = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(data, dict)
            or data.get("schema") != 1
            or not isinstance(data.get("points"), dict)
        ):
            raise CommandError("Invalid teach library schema")
        points = data["points"]
        if len(points) > 100:
            raise CommandError("Teach library exceeds 100 points")
        validated = {}
        for name, value in points.items():
            self.validate_name(name)
            validated[name] = joints(value).tolist()
        self.teach = validated

    @staticmethod
    def validate_name(name: str) -> None:
        if (
            not isinstance(name, str)
            or not name.strip()
            or len(name) > 64
            or any(ord(c) < 32 for c in name)
        ):
            raise CommandError("Teach name requires 1..64 printable characters")

    def persist_teach(self, points: dict[str, list[float]]) -> None:
        target = self.output / "teach-points.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"schema": 1, "points": points}, indent=2, allow_nan=False), encoding="utf-8"
        )
        temporary.replace(target)
        self.teach = points

    def teach_save(self, name: str) -> None:
        self.available()
        self.validate_name(name)
        if name not in self.teach and len(self.teach) >= 100:
            raise CommandError("Teach library is full (100 points)")
        self.persist_teach({**self.teach, name: self.control.q.tolist()})
        self.control.event("teach_saved", name=name)

    def teach_delete(self, name: str) -> None:
        self.available()
        if name not in self.teach:
            raise CommandError("Select an existing teach point")
        self.persist_teach({k: v for k, v in self.teach.items() if k != name})
        self.control.event("teach_deleted", name=name)

    def tick(self, dt: float) -> None:
        self.own()
        if self.cancel.is_set():
            self.freeze()
            return
        self.control.step(dt)
        if self.control.state == "IDLE" and self.sequence and self.paused_goal is None:
            try:
                self.move(self.sequence.popleft())
            except (ValueError, OSError) as exc:
                self.sequence.clear()
                self.error = str(exc)
                self.control.stop()
                raise
        if self.control.state in ("BLOCKED", "FAULT"):
            self.sequence.clear()
            self.error = self.control.last_error

    def snapshot(self) -> Snapshot:
        self.own()
        pose = fk(self.control.q)
        state = self.phase or ("PAUSED" if self.paused_goal is not None else self.control.state)
        trajectory = self.control.trajectory
        return Snapshot(
            tuple(self.control.q),
            tuple(self.control.velocity),
            tuple(pose.position)
            + tuple(Rotation.from_matrix(pose.rotation).as_euler("xyz", degrees=True)),
            state,
            self.mode,
            self.speed,
            self.control.elapsed,
            trajectory.duration if trajectory else 0.0,
            self.preview,
            self.preview_path,
            tuple(self.obstacles),
            len(self.world.collisions(self.control.q, self.config.collision_margin)),
            tuple(self.events),
            tuple((k, tuple(v)) for k, v in self.teach.items()),
            self.error,
            f"{self.sequence_total - len(self.sequence)} / {self.sequence_total}"
            if self.sequence_total
            else "—",
            monotonic(),
        )

    def close(self) -> None:
        self.own()
        self.world.close()
