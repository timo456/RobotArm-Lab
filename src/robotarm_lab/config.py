"""Validated configuration, loaded explicitly with no global environment mutation."""

import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

import numpy as np

from .model import Array


@dataclass(frozen=True)
class Config:
    velocity: Array
    acceleration: Array
    collision_margin: float
    collision_joint_step: float
    control_dt: float
    ik_position_tolerance: float
    ik_orientation_tolerance: float
    ik_restarts: int

    def __post_init__(self) -> None:
        for name in ("velocity", "acceleration"):
            a = np.array(getattr(self, name), dtype=float)
            if a.shape != (6,) or not np.all(np.isfinite(a)) or np.any(a <= 0):
                raise ValueError(f"{name}: expected six finite positive limits")
            a.setflags(write=False)
            object.__setattr__(self, name, a)
        for name in (
            "collision_margin",
            "collision_joint_step",
            "control_dt",
            "ik_position_tolerance",
            "ik_orientation_tolerance",
        ):
            v = getattr(self, name)
            if not np.isfinite(v) or v <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if self.collision_joint_step > 0.02 or self.control_dt > 0.05:
            raise ValueError("Collision step <= 0.02 rad and control_dt <= 0.05 s required")
        if type(self.ik_restarts) is not int or not 1 <= self.ik_restarts <= 32:
            raise ValueError("ik_restarts must be an integer in [1, 32]")


def load_config(path: Path | None = None) -> Config:
    source = path if path else files("robotarm_lab").joinpath("assets/default.json")
    return Config(**json.loads(source.read_text(encoding="utf-8")))
