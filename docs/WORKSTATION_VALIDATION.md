# v0.2.0 verification record

Status: **acceptance in progress; completion remains unproven**. The frozen protocol
is `acceptance-v0.2.0.json`, committed in `c79d3dd` before implementation. Baseline
`b657da55899fd20fb1a0958d0684da6edc699027` remains on stable main. No earlier threshold,
corpus or control/kinematics/collision algorithm is changed.

This document is completed with final evidence after the remaining runs. Current
facts are linked to raw local outputs; final sanitized copies belong in `reports/v0.2.0`.

## Method and environment

Windows 10 22H2 / build 19045, CPython 3.12.3, isolated `.venv-workstation`,
PySide6-Essentials and shiboken 6.8.3, RTX 3080 with NVIDIA driver 610.88.
Native application DPR is 1.25. All outputs and package environments reside on E:.

The tests launch actual Qt Widgets/QOpenGLWidget windows, operate them through QTest
and capture QWidget.grab / grabFramebuffer output. These are rendered application
pixels, not mockups. Native Windows capture returned `window capture timed out:
timed out waiting on channel`; native coordinate click returned `coordinate input
geometry is unavailable`. Native keyboard close worked. The accepted Qt fallback is
used for visual and interaction evidence. OS-wide DPI-setting changes and general
multi-monitor transitions are not claimed verified.

The fixed visual matrix is 1920x1080 @1.0, 1366x768 @1.0, 1536x864 @1.25,
1280x720 @1.5, and 1100x700 @1.0 logical pixels. Qt scaling is recorded separately
from OS settings. Screenshots are inspected for readable text, overlap, model
alignment, usable scroll areas, persistent Preview/Execute controls and status feedback.

The 30-second performance test repeats validated Demo programs. A separate endurance
run warms up for 30 seconds and then samples 600 seconds, measuring actual process
working set and 10-second render/event-loop windows. This is one local machine's
performance, not a cross-platform hardware guarantee. CI uses actual software GL
for correctness and does not claim to reproduce the workstation's GPU FPS.

Command feedback measures submission -> worker acceptance -> GUI event-loop delivery.
Completion latency, which includes IK/path planning and audit I/O, is separately
reported for every command and can exceed 150 ms. Freeze latency measures input to
observed STOPPED. Neither metric is physical actuator response or a real-time guarantee.

## Development failures retained

| Evidence directory under outputs/v0.2.0 | Observed issue | Resolution |
|---|---|---|
| visual-first | Qt clicked(bool) became an unintended command argument; initial capture script failed to assert RUNNING | callbacks discard checked; captures assert RUNNING/PAUSED |
| visual-compact | low-height command panel left Preview/Execute beneath scroll | persistent action footer; scrollable input panels |
| software-gl-first | PyOpenGL used a different system DLL/context from Qt software GL | use only Qt-resolved OpenGL functions/buffers |
| software-gl-qt | software context was Mesa OpenGL 3.0, not requested 3.3 | supported 3.0 Qt function wrapper and GLSL 1.30 |
| software-gl-qt30 | raw pointer binding rejected vertex-attribute arguments | Qt buffer attribute API |
| software-gl-qt30-second | raw matrix binding rejected Python list | Qt QMatrix4x4 shader uniform API |
| gui-audit-qt | successful worker reply arrived before updated snapshot; assertions saw stale state | publish snapshot before completion signal |
| gui-audit-qt-second | performance harness requeued Demo during stale IDLE snapshots | wait for response/RUNNING; pending-motion guard |

No failed assertion was removed or acceptance threshold relaxed. Historical early
captures that lacked sufficient state assertions are not counted as final acceptance.
Raw failure outputs remain on E:; selected sanitized manifests will be committed.

## Functional coverage

- All 277 baseline tests plus workstation tests; FK and every rendered link frame
  independently compared to PyBullet at 100 seeded full-range configurations.
- Joint target preview/execute/Home; read-only ghost scrubbing; target edit invalidation.
- Manual jog and Auto guard; TCP IK and unreachable rejection; invalid command atomicity.
- Full three-segment Demo; pause holds; resume and speed override; Freeze clears motion.
- Teach atomic save, preview/load/delete and a newly created worker/window loading disk.
- Actual Scene Add/Update/Remove/Clear; demo blocker rejects before movement; inserted
  runtime obstacle leads to BLOCKED and actual clearance contacts.
- Actual log path replaced by a directory to induce I/O fault; FAULT feedback, storage
  restoration, Reset and a subsequent valid command.
- Camera orbit/pan/wheel/reset, proxy display, actual screenshot export.
- Close while PLANNING has been observed; cooperative worker exit without destruction races.

The 13 grouped Qt scenarios cover the 21 named protocol requirements; baseline/unit
regressions independently verify bounds, transform conventions, persistence, cancellation
and collision atomicity. Scenario groups are reported individually, with tracebacks on failure.

## Preliminary measured run

`gui-audit-expanded/results.json`: all 13 scenarios passed; 30.003 s, 75.59 FPS,
render CPU p95 4.49 ms, heartbeat p95 23.11 ms/max 34.55 ms, acknowledgement p95
59.68 ms, Freeze 80.40 ms, planning shutdown 149.24 ms. Source unchanged during run.
`regression-expanded.xml`: 298 tests passed in 9.23 s. Final type-annotation-only
source refinements and packaging still require the final run identified below.

These preliminary numbers do not replace the final source-matched result, 600-second
soak, five-case visual matrix, installed-wheel run or actual remote CI evidence.

## Completion audit

Final artifacts are recorded here after measurement: source digest, unit XML,
original benchmark, hardening corpus, final GUI JSON, soak JSON, visual-case manifests,
clean installed-wheel proof, dependency licenses, wheel/source SHA256 and remote run URL.
Until those are present and reviewed, the project remains **NO-GO for declaring full
v0.2.0 completion**. Stable main and the v0.1.1 release are not modified.

Known scope limits are in `LIMITATIONS.md`. The product is an installable source/wheel
workstation, not a signed installer, physical robot driver, certified safety system,
complete CAD collision model or localized industrial programming environment.
