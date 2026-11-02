"""White-box desktop smoke: real Tk widgets/callbacks, no OS input injection."""

import json
import tkinter as tk
from pathlib import Path

import numpy as np

from robotarm_lab.config import load_config
from robotarm_lab.gui import App
from robotarm_lab.model import HOME


def main() -> None:
    output = Path("outputs/gui-smoke")
    output.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    errors: list[str] = []
    root.report_callback_exception = lambda kind, value, tb: errors.append(str(value))
    app = App(root, load_config(), output, auto_schedule=False)
    checks: dict[str, bool] = {}
    try:
        root.update_idletasks()
        app.tick()
        app.tick()
        root.update_idletasks()
        checks["rendered_tk_image"] = bool(app.viewport.cget("image"))
        checks["controls_within_window"] = all(
            0 <= widget.winfo_rooty() - root.winfo_rooty()
            and widget.winfo_rooty() + widget.winfo_height()
            <= root.winfo_rooty() + root.winfo_height()
            for widget in [*app.sliders, *app.pose_entries]
        )
        app.demo()
        app.controller.run_until_idle()
        checks["demo_completes"] = app.controller.state == "IDLE"
        app.invoke(app.controller.home)
        app.controller.run_until_idle()
        checks["home_completes"] = bool(np.allclose(app.controller.q, HOME))
        app.blocker()
        before = app.controller.q
        app.invoke(app.demo)
        checks["blocker_rejects_demo"] = "REJECTED" in app.status.get()
        checks["rejection_preserves_pose"] = bool(np.array_equal(before, app.controller.q))
        app.invoke(app.world.clear_obstacles)
        app.sliders[0].set(10)
        app.move_joints()
        app.controller.step()
        app.invoke(app.controller.stop)
        checks["stop"] = app.controller.state == "STOPPED"
        app.invoke(app.reset)
        checks["reset"] = bool(np.array_equal(app.controller.q, HOME))
        app.move_pose()
        app.controller.run_until_idle()
        checks["ik_button"] = app.controller.state == "IDLE"
        app.pose_entries[0].delete(0, "end")
        app.pose_entries[0].insert(0, "not-a-number")
        app.move_pose()
        checks["invalid_input_message"] = "REJECTED" in app.status.get()
        app.capture()
        checks["capture"] = (output / "viewport.png").is_file()
        checks["no_callback_errors"] = not errors
        result = {
            "passed": all(checks.values()),
            "checks": checks,
            "callback_errors": errors,
            "method": "Real Tk widgets and application callbacks; no mouse injection",
        }
        (output / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        if not result["passed"]:
            raise SystemExit(1)
    finally:
        app.close()
    root = tk.Tk()
    app = App(root, load_config(), output)

    def finish() -> None:
        checks["scheduled_mainloop_ticks"] = app.frames >= 2
        app.close()

    root.after(500, finish)
    root.mainloop()
    result["passed"] = all(checks.values())
    (output / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Scheduled mainloop:", checks["scheduled_mainloop_ticks"])
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
