# v0.2.0 verification record

Status: **local acceptance passed; remote CI verification pending**. The frozen protocol
is `acceptance-v0.2.0.json`, committed in `c79d3dd` before implementation. Baseline
`b657da55899fd20fb1a0958d0684da6edc699027` remains on stable main. No earlier threshold,
corpus or control/kinematics/collision algorithm is changed.

Sanitized evidence is committed under `reports/v0.2.0`; full raw outputs, failure
attempts and capture sequences remain under `outputs/v0.2.0` on E:.

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
| visual-matrix | screen factor 1 retained the native Windows 1.25 DPR; one fixed-delay Pause assertion was premature | Qt testing-only native scaling disable plus explicit global factor; wait for actual state; all five cases rerun |

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

## Final local measurements

Runtime SHA256:
`544d1b07b03a6454211fcc476c83ae5c120f79184584ba34e5eb8138ab18b5b6`.
The final GPU, software, compact UI, endurance and isolated installed-wheel reports
all identify this same source digest. `scripts/workstation_evidence.py` asserts that
match and sanitizes host/user paths without changing the raw evidence.

| Check | Frozen gate | Measured result |
|---|---:|---:|
| Legacy + workstation unit regressions | all pass, at least 277 baseline | 298/298; 12.94 s with coverage |
| Independently installed wheel regressions | all pass | 298/298; 9.28 s |
| Visual link positions, 100 seeded poses × 7 links | <=1e-6 m | 8.14e-8 m maximum |
| Visual link orientation | <=1e-6 rad | 3.94e-7 rad maximum |
| Actual GPU frames over 30.12 s | >=30 FPS | 75.52 FPS |
| CPU rendering p95 | <=25 ms | 4.81 ms |
| GUI heartbeat p95 / maximum | <=50 / 250 ms | 23.22 / 33.88 ms |
| Command acknowledgement p95 | <=150 ms | 51.51 ms |
| Freeze observed in GUI | <=200 ms | 66.72 ms |
| Continuous endurance duration | >=600 s | 600.02 s; 78 Demo starts |
| Peak RSS growth after warm-up | <=64 MiB | 1.84 MiB |
| Endurance lowest interval FPS | >=30 FPS | 70.81 FPS |
| Endurance worst render p95 / heartbeat maximum | <=25 / 250 ms | 7.08 / 133.57 ms |
| Endurance event rows / trail points | <=500 / 2048 | saturated at 500 / 2048 |

All 13 grouped functional scenarios passed on the GPU, the Qt Windows software
renderer, and a 1100x700 logical window at Qt 150% scale. The strengthened software
and compact checks also execute a non-Home TCP target and the Teach library sequence.
Shutdown after observing PLANNING completed in 349 ms in the final GPU run; no forced
thread termination occurred. There is no frozen shutdown-time gate beyond the test's
5-second liveness timeout. No Qt callback errors were observed in accepted runs.

The original benchmark passes with maximum FK position/orientation discrepancies
5.54e-8 m / 3.22e-7 rad, IK errors 2.05e-6 m / 5.53e-6 rad, no executed collisions
and no joint-limit violations. The unchanged hardening corpus has 80/80 cold,
48/48 boundary, 24/24 singular IK successes, 24/24 unreachable rejections and zero
false negatives among 48 collision scenes. Numerical limit ratio is
1.0000000000000002 (floating-point roundoff). See full case records for all timings.

The unit-only coverage report is 44.88% across the enlarged package. This does not
instrument the separately executed GUI/renderer scenarios and is not represented as
whole-product coverage. The functional verifiers and visual evidence are independent
of that number; no coverage acceptance threshold was invented after testing.

## Visual and installation evidence

All five frozen size/scale cases have matching requested logical dimensions, actual
DPR and saved pixel dimensions in `visual-matrix.json`. Each was manually inspected;
TCP/Teach/Scene captures were also checked at compact/high-DPI sizes. Text remains
readable, panels do not overlap and the fixed Preview/Execute footer remains visible.
At compact heights, lower joint/telemetry/scene rows intentionally require scrolling;
the complete interaction suite passes at 1100x700 @1.5.

The matrix uses `QT_ENABLE_HIGHDPI_SCALING=0` and explicit `QT_SCALE_FACTOR` in child
test processes, not in production launch. This avoids multiplying the native 125%
scale by the requested factor. See [Qt's testing documentation](https://doc.qt.io/qt-6.8/highdpi.html).
These are application scaling checks; global Windows settings remain unchanged.

`docs/media/workstation-home.png` is an actual 1536x864 @1.25 capture.
`docs/media/workstation-demo.gif` contains 56 real Qt window captures, resized with
Pillow and timed using recorded capture timestamps; start/middle/end frames were
inspected and the final state is IDLE. No synthetic illustration replaces a screenshot.

The bootstrap script was actually executed using the E: wheelhouse. A new environment
with `system_site_packages=False` installed all dependencies binary-only/offline and
the built project wheel. `python -I` verified installed provenance and runtime source
digest, then ran all tests, the original Demo and actual Qt capture/interactions.
The project wheel includes MIT, third-party notices, LGPLv3 and GPLv3 texts; it contains
no dependency binaries or caches. Separate fresh GUI processes saved and reloaded the
`Restart proof` teach point (`process-restart-write/read.json`).

## Completion audit

Local evidence: `reports/v0.2.0/local-verification.json`, unit XML, original benchmark,
hardening cases, GUI/soak JSON, model alignment, visual manifests, clean installed-wheel
proof and dependency licenses. YAML 1.2 parsing, actionlint 1.7.12, Ruff lint/format
and Git whitespace checks passed. Both Windows 3.12 and Ubuntu 3.11 remain in CI;
Qt correctness uses software GL and Ubuntu Xvfb/display dependencies.

**Local GO for branch review; remote CI is still unverified.** Full completion remains
pending the actual branch workflow evidence and final source archive check. Stable main
and the existing v0.1.1 release are not modified. No release is created.

Known scope limits are in `LIMITATIONS.md`. The product is an installable source/wheel
workstation, not a signed installer, physical robot driver, certified safety system,
complete CAD collision model or localized industrial programming environment.
