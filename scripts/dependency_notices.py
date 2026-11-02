"""Record installed dependency license metadata, without local filesystem paths."""

import importlib.metadata
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
records = []
for line in (root / "requirements-lock.txt").read_text().splitlines():
    if "==" not in line or line.startswith("#"):
        continue
    name, _ = line.split("==")
    dist = importlib.metadata.distribution(name)
    records.append(
        {
            "package": dist.metadata["Name"],
            "version": dist.version,
            "license_expression": dist.metadata.get("License-Expression"),
            "license_metadata": dist.metadata.get("License"),
            "license_files": [
                str(p).replace("\\", "/")
                for p in dist.files or []
                if "license" in str(p).lower() or "copying" in str(p).lower()
            ],
        }
    )
(root / "reports/dependency-licenses.json").write_text(
    json.dumps(records, indent=2), encoding="utf-8"
)
