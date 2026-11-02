# Review and publishing

The existing repository is `https://github.com/timo456/RobotArm-Lab`.
The v0.2.0 work belongs to `codex/v0.2.0-workstation`; stable `main` and the existing
v0.1.1 release must remain unchanged during development. Do not create another remote.

Before publishing, read `WORKSTATION_VALIDATION.md`, the frozen acceptance protocols,
`CHANGELOG.md`, `THIRD_PARTY_NOTICES.md` and the actual branch workflow run. A local GO
is not proof of remote CI success. Qt dependencies are separately installed; local
PyBullet wheels and environments are never uploaded as part of the project source.

1. Reproduce the README checks and inspect `git status`, `git diff --check` and the
   source/wheel contents. Review retained failures, exact source hashes and captures.
2. Confirm the baseline robotics modules, URDF, corpus and earlier thresholds are
   unchanged. Check no caches, credentials, private data or unreviewed logs are tracked.
3. Push only the verified development branch, with an ordinary non-force push:

   ```powershell
   git push -u origin codex/v0.2.0-workstation
   ```

4. Inspect the Windows Python 3.12 and Ubuntu Python 3.11 jobs at that exact commit,
   including GUI software-rendering and isolated-wheel steps; download their evidence.
5. The owner may then open a pull request into main, review compatibility/licensing,
   merge with required checks and decide separately whether to create a release.
   This implementation does not authorize main updates or a release.

The wheel/source distribution contains project code, original visual model, license
notices and reviewed evidence. Dependency binaries require their own redistribution
obligations. Do not describe the simulator as certified safety or hardware-ready control.
