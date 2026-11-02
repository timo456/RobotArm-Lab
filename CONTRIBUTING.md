# Contributing

Use Python 3.12 on Windows or 3.11 on Linux and the pinned dependency file. Keep changes
small and include tests for mathematical invariants or command rejection behavior.
Run pytest, Ruff and the fixed-seed benchmark before proposing a change. Changes to
acceptance criteria must be versioned prospectively with a technical explanation;
never relax thresholds after seeing results in order to report a pass.

Geometry changes require updating `model.py` and `scripts/generate_model.py`, regenerating
`assets/ral6.urdf`, and running the independent FK checks. Preserve SI/radian conventions.
Avoid sharing a PyBullet client across threads. New GUI actions must use Controller for
movement; `World.set_q` bypasses safety and is only appropriate for explicit reset/tests.

Do not commit build directories, local environment files, secrets or proprietary CAD.
