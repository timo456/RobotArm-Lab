# Product acceptance audit — v0.2.0

This checklist maps the full workstation objective to concrete evidence; it does not
replace or relax the frozen numerical protocol. **GO:** local gates and both remote
platform jobs passed. Actual run and source identity are in `WORKSTATION_VALIDATION.md`.

| Requirement | Evidence and scope |
|---|---|
| Installable Windows 10 / Python 3.12 desktop | Actual E: bootstrap; isolated wheel environment; `clean-environment.json`, `clean-workstation.json` |
| Professional usable HMI | Actual five-case size/scale matrix; `docs/media/workstation-home.png`; compact-window QTest suite; no mock screenshots |
| Original six-axis industrial visual model | Procedural profiles, shells, collars, bolts, flange and tool in `geometry.py`; no external CAD; MIT provenance |
| Workbench, grid, axes, trail, ghost and camera | Actual captures; camera orbit/pan/wheel/reset assertions; proxy overlay inspected |
| Continuous joint animation and timeline | Read-only scrub checks; executed quintics; 56-frame real Demo GIF; 30-second GPU and 600-second endurance runs |
| Joint and TCP commands, preview and Execute | `joint_preview_execute`, `tcp_ik_unreachable`, `stale_input`; non-Home TCP executed in software/compact audits |
| Home, Demo, Pause, Resume, speed, Freeze, Reset | Grouped GUI scenarios plus engine tests; actual hold and return-to-Home assertions |
| Teach save/load/delete and restarted persistence | Actual GUI save and a fresh process read; atomic JSON tests; library sequence through GUI |
| Manual/Auto state and feedback | Actual jog/button guards, pending-motion guard, state-derived UI; acceptance/completion telemetry separated |
| Obstacle Add/Update/Remove/Clear and rejection | Actual Scene widget commands; transactional edit regression; unchanged collision oracle |
| Runtime collision blocking | Inserted obstacle while moving; BLOCKED and actual clearance contact assertions |
| Error recovery and shutdown | Invalid/unreachable input preserves pose; actual log-path I/O fault and Reset recovery; planning shutdown joins owner thread |
| Preserve v0.1.1 core and thresholds | Empty Git diff for FK/IK/model/controller/world/config/trajectory/URDF, legacy tests, frozen protocols and corpus |
| Visual/collision separation | Proxy overlay, unchanged URDF; 700 independent link-frame comparisons; explicit cosmetic-shell limitation |
| Engineering performance | Same runtime digest in GPU/soft/compact/soak/clean reports; fixed gates; per-command timings and interval RSS/render samples |
| Stable bounded memory | 600.02 s, 78 Demo starts, 1.84 MiB peak RSS growth; event rows 500, trail 2048; teach limit 100 tested |
| Automated tests and portable CI | 298 unit regressions; actual Qt software GL on Windows and Xvfb on Ubuntu configured; actual remote result required separately |
| English/Traditional Chinese docs | README, `USER_GUIDE.zh-TW.md`, architecture Mermaid, frozen design specification, limitations and publishing steps |
| Licensing and redistributable source | Original meshes/code MIT; separately installed dynamic LGPL Qt; included LGPL/GPL texts and replacement instructions; dependency inventory |
| Packaging and reproducibility | Isolated installed wheel source hash; offline sdist -> wheel identical for 21 package entries; content audit and SHA256SUMS |
| Git hygiene and publishing constraints | Development branch only; stable main remains `b657da5`; no force push, remote deletion or release; secret-pattern scan and whitespace checks |

The local evidence supports a complete software workstation within its stated
kinematic-simulation scope. The UI has deliberate visual hierarchy and real operations,
not placeholder controls. Native Windows screenshot/mouse automation could not be
verified; the user-authorized Qt fallback supplies actual rendered/input evidence.
No physical robot, dynamic payload model, CAD-surface collision fidelity, hard-real-time
control, global Windows DPI configuration change or signed standalone installer is claimed.
These are explicit scope limits, not unreported failures.

Actual Actions run 41508430359 at `9cc029f` passed both Windows/Ubuntu jobs, including
the GUI and clean installed-wheel steps. Downloaded results match the local runtime
digest. The source archive also rebuilds offline to identical package contents.
No named product function remains incomplete in this simulation scope; the explicit
untested native-automation/OS-setting cases and physical-device exclusions remain.
