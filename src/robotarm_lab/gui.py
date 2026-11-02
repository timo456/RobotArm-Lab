"""Tk desktop controls with an embedded PyBullet CPU viewport (no OpenGL requirement)."""

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

import numpy as np
from PIL import Image, ImageTk
from scipy.spatial.transform import Rotation

from .config import Config
from .controller import Controller
from .kinematics import fk
from .model import HOME, LOWER, UPPER, Pose
from .simulation import World


class App:
    def __init__(
        self, root: tk.Tk, config: Config, output: Path, auto_schedule: bool = True
    ) -> None:
        self.root, self.output = root, output
        self.auto_schedule = auto_schedule
        self.world = World()
        self.controller = Controller(self.world, config, output / "session.jsonl")
        self.world.add_box([0.40, 0.40, 0.20], [0.08, 0.08, 0.20])
        self.closed = False
        self.frames = 0
        root.title("RobotArm-Lab | RAL-6 Control Station")
        root.geometry("1250x820")
        root.minsize(1100, 780)
        root.configure(bg="#111b2b")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#111b2b")
        style.configure("TLabel", background="#111b2b", foreground="#e4edf5")
        style.configure("TButton", padding=6)
        title = ttk.Frame(root, padding=(20, 12))
        title.pack(fill="x")
        ttk.Label(title, text="ROBOTARM / LAB", font=("Segoe UI", 22, "bold")).pack(side="left")
        ttk.Label(title, text="RAL-6   •   KINEMATIC CONTROL STATION", foreground="#56d7c1").pack(
            side="right"
        )
        body = ttk.Frame(root, padding=(16, 0))
        body.pack(fill="both", expand=True)
        left, right = ttk.Frame(body, width=335), ttk.Frame(body)
        left.pack(side="left", fill="y", padx=(0, 16))
        right.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="01  JOINT TARGETS / degrees", font=("Segoe UI", 11, "bold")).pack(
            anchor="w", pady=(0, 5)
        )
        self.sliders: list[tk.Scale] = []
        for i in range(6):
            row = ttk.Frame(left)
            row.pack(fill="x")
            ttk.Label(row, text=f"J{i + 1}", width=3).pack(side="left")
            slider = tk.Scale(
                row,
                from_=float(np.rad2deg(LOWER[i])),
                to=float(np.rad2deg(UPPER[i])),
                resolution=0.1,
                orient="horizontal",
                length=280,
                bg="#111b2b",
                fg="#e4edf5",
                troughcolor="#293b50",
                highlightthickness=0,
            )
            slider.set(float(np.rad2deg(HOME[i])))
            slider.pack(side="left")
            self.sliders.append(slider)
        ttk.Button(left, text="Execute joint target", command=self.move_joints).pack(
            fill="x", pady=5
        )
        actions = ttk.Frame(left)
        actions.pack(fill="x")
        for label, action in [
            ("Home", self.controller.home),
            ("Reset scene", self.reset),
            ("Demo", self.demo),
        ]:
            ttk.Button(actions, text=label, command=lambda f=action: self.invoke(f)).pack(
                side="left", expand=True, fill="x"
            )
        tk.Button(
            left,
            text="STOP / FREEZE",
            bg="#b93044",
            fg="white",
            relief="flat",
            command=lambda: self.invoke(self.controller.stop),
        ).pack(fill="x", pady=7)
        ttk.Label(left, text="02  TCP TARGET / m, degrees", font=("Segoe UI", 11, "bold")).pack(
            anchor="w", pady=(5, 4)
        )
        self.pose_entries: list[ttk.Entry] = []
        grid = ttk.Frame(left)
        grid.pack(fill="x")
        pose = fk(HOME)
        initial = [
            *pose.position,
            *Rotation.from_matrix(pose.rotation).as_euler("xyz", degrees=True),
        ]
        for i, label in enumerate(["X", "Y", "Z", "Roll", "Pitch", "Yaw"]):
            ttk.Label(grid, text=label).grid(row=i // 3 * 2, column=i % 3, sticky="w")
            entry = ttk.Entry(grid, width=12)
            entry.insert(0, f"{initial[i]:.4f}")
            entry.grid(row=i // 3 * 2 + 1, column=i % 3, padx=(0, 5), pady=(0, 3))
            self.pose_entries.append(entry)
        ttk.Button(left, text="Solve IK + execute", command=self.move_pose).pack(fill="x", pady=4)
        ttk.Label(left, text="03  SCENE & VIEW", font=("Segoe UI", 11, "bold")).pack(
            anchor="w", pady=(7, 4)
        )
        scene = ttk.Frame(left)
        scene.pack(fill="x")
        ttk.Button(scene, text="Add blocker", command=lambda: self.invoke(self.blocker)).pack(
            side="left", expand=True, fill="x"
        )
        ttk.Button(
            scene, text="Clear obstacles", command=lambda: self.invoke(self.world.clear_obstacles)
        ).pack(side="left", expand=True, fill="x")
        self.yaw = tk.DoubleVar(value=135)
        ttk.Scale(left, from_=-180, to=180, variable=self.yaw).pack(fill="x", pady=6)
        ttk.Button(left, text="Save viewport PNG", command=lambda: self.invoke(self.capture)).pack(
            fill="x"
        )
        self.viewport = ttk.Label(right)
        self.viewport.pack(fill="both", expand=True)
        self.telemetry = tk.StringVar()
        ttk.Label(right, textvariable=self.telemetry, font=("Consolas", 11), padding=10).pack(
            fill="x"
        )
        self.status = tk.StringVar(value="Ready. Set targets, then execute. SI units internally.")
        ttk.Label(
            root, textvariable=self.status, foreground="#56d7c1", wraplength=1190, padding=(20, 10)
        ).pack(fill="x")
        ttk.Label(
            root,
            text="SIMULATION ONLY  •  Sampled collision checks  •  "
            "Stop freezes simulation; no physical braking or safety certification",
            foreground="#9daec0",
            padding=(20, 6),
        ).pack(fill="x")
        root.protocol("WM_DELETE_WINDOW", self.close)
        if auto_schedule:
            root.after(30, self.tick)

    def invoke(self, action: Callable[[], object]) -> None:
        try:
            self.status.set("Validating command…")
            self.root.update_idletasks()
            action()
            self.status.set(f"{self.controller.state} — command accepted")
        except (ValueError, RuntimeError) as exc:
            self.status.set(f"REJECTED — {exc}")

    def move_joints(self) -> None:
        self.invoke(lambda: self.controller.move(np.deg2rad([s.get() for s in self.sliders])))

    def move_pose(self) -> None:
        def execute() -> None:
            values = np.array([float(e.get()) for e in self.pose_entries])
            target = Pose(
                values[:3], Rotation.from_euler("xyz", values[3:], degrees=True).as_matrix()
            )
            self.controller.move_pose(target)

        self.invoke(execute)

    def demo(self) -> None:
        target = np.array([-0.65, -0.8, 1.15, 0.35, -0.35, 0.5])
        self.controller.move(target)
        for slider, angle in zip(self.sliders, np.rad2deg(target), strict=True):
            slider.set(float(angle))

    def blocker(self) -> None:
        self.world.add_box([0.48, -0.28, 0.43], [0.10, 0.10, 0.18])

    def reset(self) -> None:
        self.controller.reset()
        for slider, angle in zip(self.sliders, np.rad2deg(HOME), strict=True):
            slider.set(float(angle))

    def capture(self) -> None:
        self.output.mkdir(parents=True, exist_ok=True)
        Image.fromarray(self.world.render()).save(self.output / "viewport.png")
        self.controller.event("viewport_saved", filename="viewport.png")

    def tick(self) -> None:
        if self.closed:
            return
        self.controller.step(0.02)
        if self.controller.state == "BLOCKED":
            self.status.set("BLOCKED — " + self.controller.last_error)
        self.frames += 1
        if self.frames % 2 == 0:
            pixels = self.world.render(820, 560, self.yaw.get())
            self.photo = ImageTk.PhotoImage(Image.fromarray(pixels))
            self.viewport.configure(image=self.photo)
        p = fk(self.controller.q)
        qtext = "  ".join(f"{v:7.2f}" for v in np.rad2deg(self.controller.q))
        self.telemetry.set(
            f"STATE {self.controller.state:<8}  SIM TIME {self.controller.elapsed:6.2f} s\n"
            f"q°   {qtext}\n"
            f"TCP  x={p.position[0]:.4f}  y={p.position[1]:.4f}  z={p.position[2]:.4f} m\n"
            f"peak |qdot|={np.max(np.abs(self.controller.velocity)):.3f} rad/s  "
            f"obstacles={len(self.world.obstacles)}"
        )
        if self.auto_schedule:
            self.root.after(20, self.tick)

    def close(self) -> None:
        self.closed = True
        self.world.close()
        self.root.destroy()


def launch(config: Config, output: Path) -> None:
    root = tk.Tk()
    App(root, config, output)
    root.mainloop()
