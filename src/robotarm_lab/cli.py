"""Command-line entry points; all output destinations are explicit and local."""

import argparse
import json
from pathlib import Path

from .config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="RobotArm-Lab six-axis simulation")
    parser.add_argument("--config", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("gui", "demo", "benchmark"):
        command = sub.add_parser(name)
        command.add_argument("--output", type=Path, default=Path("outputs") / name)
        if name == "benchmark":
            command.add_argument("--protocol", type=Path, default=Path("acceptance.json"))
    args = parser.parse_args()
    config = load_config(args.config)
    if args.command == "gui":
        from .gui import launch

        launch(config, args.output)
    elif args.command == "demo":
        from .demo import render_demo

        print(json.dumps(render_demo(config, args.output), indent=2))
    else:
        from .experiments import benchmark

        result = benchmark(config, args.protocol, args.output)
        print(json.dumps(result["summary"], indent=2))
        return 0 if result["passed"] else 1
    return 0
