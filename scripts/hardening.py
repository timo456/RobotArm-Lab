"""Compare a chosen source revision using the same environment and frozen corpus."""

import argparse
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--baseline", action="store_true")
args = parser.parse_args()
if args.source:
    sys.path.insert(0, str(args.source.resolve()))
from hardening_suite import run  # noqa: E402

raise SystemExit(run(args.output, args.baseline))
