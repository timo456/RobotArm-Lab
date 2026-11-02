# v0.2.0 Professional Workstation — frozen design and acceptance

Baseline: `b657da5`, main/v0.1.1 retained. Development branch:
`codex/v0.2.0-workstation`. The adjacent JSON protocol is committed before implementation.

## Audit

- Core: independently implemented FK, validated multi-branch IK, bounded collision
  sampling and quintic time parameterization; 277 existing tests and two frozen protocols.
- HMI: Tk, synchronous planning and CPU image refresh. No teach library, timeline,
  camera orbit/pan, persistent workstation session or deliberate visual hierarchy.
- Model: original box URDF. Collision semantics are verified and will remain intact.
- CI: Windows 3.12 and Linux 3.11 passed at baseline. Qt brings display/GL requirements.

## Product and interaction design

Dark graphite workstation; teal operational accents, amber caution, coral blocked/fault.
Font: native Segoe UI with a system sans fallback; monospaced numeric telemetry.
Header: RAL / RobotArm Lab identity, connection/mode, simulation state and live health.
Toolbar: Home, Demo, Pause/Resume, Freeze, Reset, view reset and screenshot export.
Three regions: scrollable Joint/TCP/Teach command panel; dominant 3D viewport with
timeline; telemetry/scene controls. Bottom event log is bounded and collapsible.
At small sizes, splitters and scroll areas preserve access rather than overlapping controls.

Commands follow preview -> explicit execute. Preview is a collision-validated,
read-only ghost and TCP path. Never teleport the actual robot during preview or scrubbing.
Jog means a bounded increment followed by the same safe motion planner, not unbounded
streaming. Manual mode supports jog and individual moves; Auto supports taught/demo
sequences. Mode changes during execution are rejected. No enabled inert buttons.

## Architecture

1. Existing Control Core / PyBullet World remain authoritative, owned by one worker.
2. Workstation service adds orchestration, snapshots, mode/playback state, validation,
   teach persistence and bounded events. No GUI widget calls PyBullet.
3. A dedicated worker consumes queued commands. Stop requests can cancel preview
   results; immutable snapshots cross the thread boundary. No concurrent world mutation.
4. OpenGL visualization independently constructs transforms from the original model
   constants, verified against every PyBullet link. Original procedural machined
   housings, collars, bolts, base, tool, table, grid, axes and ghost path are visual only.
   Collision proxy overlay makes the distinction inspectable. TCP stays at the same tool frame.
5. Qt Widgets HMI renders snapshots; planning cannot block the Qt event loop.

Speed changes alter future time parameterization; an active change freezes and replans
the remaining rest-to-rest segment. Pause is an explicit kinematic hold and resume
replans safely. Neither is a physical acceleration-limited emergency brake.
Scene changes invalidate previews. Trajectories are revalidated on execution and
incremental execution retains the existing collision checks. No bypass for demos.

## Verification and deliverables

Run all old tests/protocols unchanged. New tests cover transforms, preview atomicity,
worker ownership/cancellation, persistence, UI enablement, playback and recovery.
Capture actual shown Qt widgets and GL framebuffers at all protocol sizes/scales;
retain first failures and revised captures. Qt QTest and QWidget.grab are valid fallback
evidence if native capture/input fail. Distinguish Qt scaling from OS-setting tests.
Inspect every final capture manually. Measure 30-second frame/event-loop/command
latencies and 10-minute bounded-memory soak, with machine/renderer details.
Package a wheel and source archive; reconstruct a separate environment and execute
it. Update Linux/Windows CI with display requirements; push only the development branch
after local verification. Do not change main or create a release.

Dependencies: use Qt Widgets/OpenGL modules from PySide6-Essentials 6.8.3 (LGPLv3
dynamic Python import), shiboken6 6.8.3, and PyOpenGL 3.1.9 (BSD-style license).
Keep Qt license texts/notices and replacement/relinking instructions in distribution;
no proprietary CAD, external robot meshes, fonts or generated reference illustrations.
Qt 6.8 supports Windows 10; this version is selected for the explicit target, not newest-version marketing.

Sources: [Qt 6.8 Windows](https://doc.qt.io/qt-6.8/windows.html),
[PySide6 Essentials](https://pypi.org/project/PySide6-Essentials/6.8.3/),
[Qt licensing](https://doc.qt.io/qt-6.8/licensing.html),
[PyOpenGL](https://pypi.org/project/PyOpenGL/3.1.9/).

Release decision remains unproven until every requirement has direct evidence. An
operational window alone does not constitute product completion.

## Evidence-driven renderer revision (2026-11-03)

The first PyOpenGL implementation worked with NVIDIA but failed with Qt's Windows
software context: its system OpenGL DLL did not share the Qt Mesa context. Qt's bundled
software driver reports OpenGL 3.0 / Mesa 11.2.2, not 3.3. The renderer now resolves all
functions through Qt, uses GLSL 1.30, Qt-owned buffers/shaders and supports both the
hardware core context and this software context. Actual software-rendered captures and
Demo/Pause interactions passed after retained failed attempts. PyOpenGL is no longer a
runtime dependency. No performance or correctness gate was changed.
