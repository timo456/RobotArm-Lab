"""Original parametric RAL-6 visual assets. No imported CAD or collision mutation."""

from dataclasses import dataclass

import numpy as np

from ..kinematics import axis_rotation
from ..model import AXES, ORIGINS, TOOL, joints


def transform(position=(0, 0, 0), scale=(1, 1, 1), axis=None, angle=0.0):
    matrix = np.eye(4)
    matrix[:3, :3] = (
        np.diag(scale) if axis is None else axis_rotation(np.asarray(axis), angle) @ np.diag(scale)
    )
    matrix[:3, 3] = position
    return matrix


def link_frames(q):
    """Six post-joint link frames and the fixed TCP, using the model's exact axes."""
    result, matrix = [], np.eye(4)
    for origin, axis, angle in zip(ORIGINS, AXES, joints(q), strict=True):
        matrix = matrix @ transform(origin) @ transform(axis=axis, angle=angle)
        result.append(matrix.copy())
    result.append(matrix @ transform(TOOL))
    return result


def lathe(profile, segments=32):
    vertices = []
    for (z0, r0), (z1, r1) in zip(profile[:-1], profile[1:], strict=True):
        for i in range(segments):
            a, b = 2 * np.pi * i / segments, 2 * np.pi * (i + 1) / segments
            p = np.array(
                [
                    [r0 * np.cos(a), r0 * np.sin(a), z0],
                    [r0 * np.cos(b), r0 * np.sin(b), z0],
                    [r1 * np.cos(b), r1 * np.sin(b), z1],
                    [r1 * np.cos(a), r1 * np.sin(a), z1],
                ]
            )
            for tri in ((0, 1, 2), (0, 2, 3)):
                face = p[list(tri)]
                n = np.cross(face[1] - face[0], face[2] - face[0])
                if np.linalg.norm(n) < 1e-12:
                    continue
                n /= np.linalg.norm(n)
                vertices.extend(np.concatenate((v, n)) for v in face)
    return np.asarray(vertices, dtype=np.float32)


def box_mesh():
    data = []
    for axis in range(3):
        for sign in (-1, 1):
            n = np.zeros(3)
            n[axis] = sign
            other = [i for i in range(3) if i != axis]
            p = []
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                v = n.copy() * 0.5
                v[other[0]], v[other[1]] = a * 0.5, b * 0.5
                p.append(v)
            for i in (0, 1, 2, 0, 2, 3):
                data.append(np.r_[p[i], n])
    return np.asarray(data, dtype=np.float32)


MESHES = {
    "box": box_mesh(),
    "housing": lathe([(-0.5, 0), (-0.5, 0.43), (-0.43, 0.5), (0.43, 0.5), (0.5, 0.43), (0.5, 0)]),
    "taper": lathe([(-0.5, 0), (-0.5, 0.38), (-0.42, 0.5), (0.38, 0.35), (0.5, 0.29), (0.5, 0)]),
    "bolt": lathe([(-0.5, 0), (-0.5, 0.5), (0.5, 0.5), (0.5, 0)], 6),
}


@dataclass(frozen=True)
class Part:
    mesh: str
    frame: int
    local: np.ndarray
    color: tuple
    metal: float = 0.0


def robot_parts():
    """Layered cast shells, machined collars, fasteners and a two-finger tool."""
    parts = []
    amber, dark, silver, rubber = (
        (0.95, 0.61, 0.19),
        (0.18, 0.24, 0.29),
        (0.62, 0.7, 0.74),
        (0.055, 0.075, 0.09),
    )

    def add(mesh, frame, pos, size, color, axis=None, angle=0, metal=0):
        parts.append(Part(mesh, frame, transform(pos, size, axis, angle), color, metal))

    add("box", -1, (0, 0, 0.014), (0.25, 0.25, 0.028), dark)
    add("housing", -1, (0, 0, 0.085), (0.21, 0.21, 0.125), dark, metal=0.45)
    add("housing", -1, (0, 0, 0.156), (0.19, 0.19, 0.021), silver, metal=0.85)
    for x in (-0.098, 0.098):
        for y in (-0.098, 0.098):
            add("bolt", -1, (x, y, 0.032), (0.015, 0.015, 0.009), silver, metal=0.8)
    add("housing", 0, (0, 0, 0.012), (0.158, 0.158, 0.025), rubber)
    add("taper", 0, (0, 0, 0.085), (0.11, 0.11, 0.14), amber, metal=0.15)
    add("box", 0, (-0.045, 0, 0.082), (0.018, 0.069, 0.088), dark)
    # Shoulder/elbow drive casings are centered exactly on their rotary axes.
    for frame, length, radius in ((1, 0.32, 0.057), (2, 0.28, 0.045)):
        add(
            "housing",
            frame,
            (0, 0, 0),
            (radius * 2, radius * 2, 0.09),
            amber,
            (1, 0, 0),
            np.pi / 2,
            0.15,
        )
        for y in (-0.049, 0.049):
            add(
                "housing",
                frame,
                (0, y, 0),
                (radius * 1.5, radius * 1.5, 0.012),
                dark,
                (1, 0, 0),
                np.pi / 2,
                0.6,
            )
            add(
                "housing",
                frame,
                (0, y * 1.15, 0),
                (radius, radius, 0.006),
                silver,
                (1, 0, 0),
                np.pi / 2,
                0.8,
            )
            for a in np.linspace(0, 2 * np.pi, 6, endpoint=False):
                add(
                    "bolt",
                    frame,
                    (np.cos(a) * radius * 0.62, y * 1.22, np.sin(a) * radius * 0.62),
                    (0.008, 0.008, 0.004),
                    rubber,
                    (1, 0, 0),
                    np.pi / 2,
                )
        add(
            "taper",
            frame,
            (length * 0.49, 0, 0),
            (0.083, 0.083, length * 0.94),
            amber,
            (0, 1, 0),
            np.pi / 2,
            0.12,
        )
        add(
            "box", frame, (length * 0.48, -0.036, 0), (length * 0.59, 0.008, 0.032), dark, metal=0.4
        )
        add("box", frame, (length * 0.49, 0.036, 0), (length * 0.59, 0.008, 0.032), dark, metal=0.4)
        add(
            "box",
            frame,
            (length * 0.43, -0.042, 0.006),
            (length * 0.23, 0.003, 0.009),
            silver,
            metal=0.7,
        )
    for frame, length, radius in ((3, 0.10, 0.038), (4, 0.10, 0.032), (5, 0.07, 0.026)):
        add(
            "housing",
            frame,
            (length * 0.45, 0, 0),
            (radius * 2, radius * 2, length * 0.82),
            dark if frame == 5 else amber,
            (0, 1, 0),
            np.pi / 2,
            0.45,
        )
        add(
            "housing",
            frame,
            (0, 0, 0),
            (radius * 2.1, radius * 2.1, 0.013),
            silver,
            (0, 1, 0),
            np.pi / 2,
            0.85,
        )
        add(
            "housing",
            frame,
            (length * 0.9, 0, 0),
            (radius * 1.9, radius * 1.9, 0.012),
            rubber,
            (0, 1, 0),
            np.pi / 2,
        )
    add("box", 5, (0.085, 0, 0), (0.035, 0.061, 0.045), dark, metal=0.6)
    for y in (-0.024, 0.024):
        add("box", 5, (0.116, y, 0), (0.043, 0.010, 0.031), silver, metal=0.85)
        add("box", 5, (0.132, y * 0.7, 0), (0.012, 0.012, 0.025), rubber)
    return parts


def collision_parts():
    sizes = [
        (0.22, 0.22, 0.18),
        (0.09, 0.09, 0.15),
        (0.31, 0.065, 0.065),
        (0.27, 0.06, 0.06),
        (0.09, 0.055, 0.055),
        (0.09, 0.05, 0.05),
        (0.12, 0.04, 0.04),
        (0.012, 0.055, 0.055),
    ]
    centers = [
        (0, 0, 0.09),
        (0, 0, 0.08),
        (0.16, 0, 0),
        (0.14, 0, 0),
        (0.05, 0, 0),
        (0.05, 0, 0),
        (0.06, 0, 0),
        (0, 0, 0),
    ]
    return [
        Part("box", i - 1, transform(p, s), (0.2, 0.95, 0.79), 0)
        for i, (p, s) in enumerate(zip(centers, sizes, strict=True))
    ]


def environment_parts():
    parts = [
        Part("box", -1, transform((0.28, 0, -0.031), (1.9, 1.45, 0.06)), (0.16, 0.21, 0.25), 0.4)
    ]
    for x in (-0.53, 1.09):
        for y in (-0.56, 0.56):
            parts.append(
                Part(
                    "box",
                    -1,
                    transform((x, y, -0.32), (0.065, 0.065, 0.57)),
                    (0.11, 0.15, 0.19),
                    0.4,
                )
            )
    parts.append(
        Part("box", -1, transform((0.2, 0, -0.635), (14, 14, 0.02)), (0.075, 0.105, 0.13), 0)
    )
    return parts
