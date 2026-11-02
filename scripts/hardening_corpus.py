"""Generate the prespecified v0.1.1 cases once, before comparing solver revisions."""

import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from robotarm_lab.kinematics import fk
from robotarm_lab.model import HOME, LOWER, UPPER
from robotarm_lab.simulation import World

ROOT = Path(__file__).resolve().parents[1]
protocol = json.loads((ROOT / "acceptance-v0.1.1.json").read_text())
rng = np.random.default_rng(protocol["seed"])
cases = []
with World() as world:
    targets = [("cold", q) for q in rng.uniform(LOWER, UPPER, (80, 6))]
    for joint in range(6):
        for bound, sign in [(LOWER, 1), (UPPER, -1)]:
            for offset in protocol["boundary_offsets_rad"]:
                q = rng.uniform(LOWER*.8, UPPER*.8)
                q[joint] = bound[joint] + sign*offset
                targets.append(("boundary", q))
    for i in range(24):
        q = rng.uniform(LOWER*.7, UPPER*.7)
        if i % 3 != 1:
            q[4] = 0
        if i % 3 != 0:
            q[2] = 0
        targets.append(("singular", q))
    for index, (group, q) in enumerate(targets):
        pose = world.pose_at(q)
        cases.append(dict(id=index, group=group, source_q=q.tolist(), seed=HOME.tolist(),
                          position=pose.position.tolist(), rotation=pose.rotation.tolist()))
    for i in range(24):
        rotation = np.eye(3)
        if i < 8:
            p = np.array([2.0+i*.1, 0, .34])
            reason = "outside_outer_bound"
        elif i < 16:
            p = np.array([.9+(i-8)*.01, 0, .34])
            rotation = Rotation.from_euler("z", np.pi).as_matrix()
            reason = "wrist_center_too_far"
        else:
            p = np.array([.22+(i-16)*.002, 0, .34])
            reason = "wrist_center_inner_void"
        cases.append(dict(id=len(cases), group="unreachable", expected_reason=reason,
                          seed=HOME.tolist(), position=p.tolist(), rotation=rotation.tolist()))

scenes = []
for i in range(48):
    q0 = HOME + rng.uniform(-.1, .1, 6)
    q1 = q0.copy()
    q0[0], q1[0] = -.8, .8
    alpha = float(rng.uniform(.25, .75))
    known_q = q0+(q1-q0)*alpha
    p = fk(known_q).position
    if i < 32:
        extents = rng.uniform(.005, .06, 3)
        p = p + rng.uniform(-.03, .03, 3)
        if i % 4 == 0:
            p = np.array([1.5, float(rng.uniform(-1, 1)), .5])
    else:
        extents = np.array([.00025, .008, .08])
    scenes.append(dict(id=i, group="random" if i < 32 else "thin", start=q0.tolist(),
                       goal=q1.tolist(), center=p.tolist(), half_extents=extents.tolist(),
                       known_q=known_q.tolist()))

trajectories = [dict(start=a.tolist(), goal=b.tolist())
                for a,b in rng.uniform(LOWER, UPPER, (100, 2, 6))]
result = dict(protocol="acceptance-v0.1.1.json", seed=protocol["seed"], ik=cases,
              scenes=scenes, trajectories=trajectories)
destination = ROOT / "tests/data/hardening-corpus.json"
destination.parent.mkdir(exist_ok=True)
if destination.exists():
    raise SystemExit("Corpus already exists; refusing to replace frozen cases")
destination.write_text(json.dumps(result, indent=2), encoding="utf-8", newline="\n")
print(f"Frozen {len(cases)} IK cases, {len(scenes)} scenes and 100 trajectories")
