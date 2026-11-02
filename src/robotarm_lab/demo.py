"""Actual executed simulation frames and per-step CSV telemetry."""

import csv
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .config import Config
from .controller import Controller
from .kinematics import fk
from .simulation import World


def render_demo(config: Config, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    frames: list[Image.Image] = []
    with (
        World() as world,
        (output / "telemetry.csv").open("w", newline="", encoding="utf-8") as stream,
    ):
        controller = Controller(world, config, output / "demo.jsonl")
        world.add_box([0.40, 0.40, 0.20], [0.08, 0.08, 0.20])
        writer = csv.writer(stream)
        writer.writerow(
            [
                "sim_time_s",
                *[f"q{i + 1}_rad" for i in range(6)],
                "x_m",
                "y_m",
                "z_m",
                "collision_count",
            ]
        )
        total_time, steps, collision_count = 0.0, 0, 0
        for target in [
            np.array([-0.65, -0.8, 1.15, 0.35, -0.35, 0.5]),
            np.array([0.25, -0.65, 0.9, -0.3, -0.2, -0.4]),
        ]:
            controller.move(target)
            while controller.state == "RUNNING":
                controller.step()
                total_time += config.control_dt
                steps += 1
                hits = len(world.collisions(controller.q, 0.0))
                collision_count += hits
                writer.writerow([total_time, *controller.q, *fk(controller.q).position, hits])
                if steps % 8 == 0 or controller.state == "IDLE":
                    frame = Image.fromarray(world.render(800, 540))
                    draw = ImageDraw.Draw(frame)
                    draw.rectangle([0, 0, 800, 62], fill="#111b2b")
                    draw.text((22, 12), "ROBOTARM / LAB     |     RAL-6", fill="#56d7c1")
                    draw.text(
                        (22, 36),
                        f"t={total_time:.2f}s   {controller.state}   "
                        f"collision contacts={collision_count}",
                        fill="white",
                    )
                    frames.append(frame)
            if controller.state != "IDLE":
                raise RuntimeError(controller.last_error)
        frames[len(frames) // 2].save(output / "demo.png")
        frames[0].save(
            output / "demo.gif", save_all=True, append_images=frames[1:], duration=80, loop=0
        )
    return {"steps": steps, "frames": len(frames), "collision_contacts": collision_count}
