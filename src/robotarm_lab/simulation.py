"""Isolated PyBullet DIRECT client, collision oracle, and deterministic CPU renderer."""

from contextlib import AbstractContextManager
from dataclasses import dataclass
from importlib.resources import files

import numpy as np
import pybullet as pb
from scipy.spatial.transform import Rotation

from .model import HOME, Array, CommandError, Pose, joints
from .validation import scalar


@dataclass(frozen=True)
class Collision:
    kind: str
    link_a: int
    link_b: int
    distance: float


class World(AbstractContextManager):
    def __init__(self) -> None:
        self.closed = False
        self.client = pb.connect(pb.DIRECT)
        self._load_scene()

    def _require_open(self) -> None:
        if self.closed:
            raise RuntimeError("Simulation world is closed")

    def _load_scene(self) -> None:
        self.robot = pb.loadURDF(
            str(files("robotarm_lab").joinpath("assets/ral6.urdf")),
            useFixedBase=True,
            physicsClientId=self.client,
        )
        shape = pb.createCollisionShape(pb.GEOM_PLANE, physicsClientId=self.client)
        self.floor = pb.createMultiBody(0, shape, physicsClientId=self.client)
        self.obstacles: list[int] = []
        self._box_shapes: dict[tuple[float, ...], tuple[int, int]] = {}
        self.revision = 0
        self.set_q(HOME)

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        if not self.closed:
            if pb.isConnected(self.client):
                pb.disconnect(self.client)
            self.closed = True

    def reset_scene(self) -> None:
        """Reclaim native geometry as part of an explicit simulation reset."""
        self._require_open()
        pb.resetSimulation(physicsClientId=self.client)
        self._load_scene()

    def set_q(self, q: object) -> None:
        """Low-level kinematic placement; use Controller for validated user commands."""
        self._require_open()
        for i, angle in enumerate(joints(q)):
            pb.resetJointState(self.robot, i, float(angle), physicsClientId=self.client)

    def get_q(self) -> Array:
        self._require_open()
        return np.array(
            [
                s[0]
                for s in pb.getJointStates(self.robot, list(range(6)), physicsClientId=self.client)
            ]
        )

    def tcp(self) -> Pose:
        self._require_open()
        state = pb.getLinkState(
            self.robot, 6, computeForwardKinematics=True, physicsClientId=self.client
        )
        # Link frame, not center-of-mass frame (entries 0/1).
        return Pose(np.array(state[4]), Rotation.from_quat(state[5]).as_matrix())

    def pose_at(self, q: object) -> Pose:
        previous = self.get_q()
        try:
            self.set_q(q)
            return self.tcp()
        finally:
            self.set_q(previous)

    def add_box(self, center: object, half_extents: object) -> int:
        self._require_open()
        p, h = np.asarray(center, dtype=float), np.asarray(half_extents, dtype=float)
        if p.shape != (3,) or h.shape != (3,) or not np.all(np.isfinite(np.r_[p, h])):
            raise CommandError("Box requires finite xyz and half-extents")
        if np.any(h < 1e-6) or np.any(h > 100) or np.any(np.abs(p) > 100):
            raise CommandError("Box half-extents must be in [1e-6,100] m; center within +/-100 m")
        if len(self.obstacles) >= 128:
            raise CommandError("Obstacle budget reached (128); clear or reset the scene")
        key = tuple(float(v) for v in h)
        if key not in self._box_shapes:
            if len(self._box_shapes) >= 128:
                raise CommandError("Shape budget reached (128); reset the scene to reclaim shapes")
            collision = pb.createCollisionShape(
                pb.GEOM_BOX, halfExtents=h, physicsClientId=self.client
            )
            visual = pb.createVisualShape(
                pb.GEOM_BOX,
                halfExtents=h,
                rgbaColor=[0.8, 0.17, 0.2, 1],
                physicsClientId=self.client,
            )
            self._box_shapes[key] = collision, visual
        collision, visual = self._box_shapes[key]
        body = pb.createMultiBody(0, collision, visual, p, physicsClientId=self.client)
        self.obstacles.append(body)
        self.revision += 1
        return body

    def clear_obstacles(self) -> None:
        self._require_open()
        for body in self.obstacles:
            pb.removeBody(body, physicsClientId=self.client)
        self.obstacles.clear()
        self.revision += 1

    def collisions(self, q: object, margin: float = 0.003) -> list[Collision]:
        self._require_open()
        margin = scalar(margin, "Collision margin")
        if margin < 0 or margin > 1:
            raise CommandError("Collision margin must be finite and nonnegative")
        previous = self.get_q()
        found: list[Collision] = []
        try:
            self.set_q(q)
            # All nonadjacent links, including fixed TCP; adjacent overlaps are structural.
            for a in range(-1, 7):
                for b in range(a + 2, 7):
                    for c in pb.getClosestPoints(
                        self.robot,
                        self.robot,
                        margin,
                        linkIndexA=a,
                        linkIndexB=b,
                        physicsClientId=self.client,
                    ):
                        found.append(Collision("self", a, b, c[8]))
            for body in [self.floor, *self.obstacles]:
                for c in pb.getClosestPoints(self.robot, body, margin, physicsClientId=self.client):
                    if body == self.floor and c[3] == -1:
                        continue  # Fixed mounting base is designed to rest on the floor.
                    found.append(
                        Collision("floor" if body == self.floor else "obstacle", c[3], c[4], c[8])
                    )
        finally:
            self.set_q(previous)
        return found

    def render(self, width: int = 960, height: int = 640, yaw: float = 135) -> np.ndarray:
        self._require_open()
        if (
            type(width) is not int
            or type(height) is not int
            or not (16 <= width <= 1920 and 16 <= height <= 1080)
        ):
            raise CommandError("Render dimensions must be integers within 16..1920 x 16..1080")
        yaw = scalar(yaw, "Camera yaw")
        view = pb.computeViewMatrixFromYawPitchRoll([0.25, 0, 0.3], 1.65, yaw, -25, 0, 2)
        projection = pb.computeProjectionMatrixFOV(48, width / height, 0.02, 5)
        result = pb.getCameraImage(
            width,
            height,
            view,
            projection,
            lightDirection=[-2, -3, 5],
            shadow=1,
            renderer=pb.ER_TINY_RENDERER,
            physicsClientId=self.client,
        )
        return np.asarray(result[2], dtype=np.uint8).reshape(height, width, 4)[..., :3]
