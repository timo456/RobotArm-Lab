"""Development launcher; all workstation state is rooted in an explicit output folder."""

import argparse
from pathlib import Path

from robotarm_lab.config import load_config
from robotarm_lab.workstation.window import launch

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, default=Path("outputs/workstation"))
args = parser.parse_args()
raise SystemExit(launch(load_config(), args.output))
