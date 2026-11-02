"""Run with python -S to prove the wheel works without editable-site .pth files."""

import json
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    target = root / ".tmp/wheel-package"
    sys.path.insert(0, str(target))
    sys.path.append(str(root / ".venv/Lib/site-packages"))
    import pytest
    from PIL import Image

    import robotarm_lab
    from robotarm_lab.config import load_config
    from robotarm_lab.controller import Controller
    from robotarm_lab.model import HOME
    from robotarm_lab.simulation import World

    assert Path(robotarm_lab.__file__).is_relative_to(target)
    code = pytest.main([str(root / "tests"), "-q", "--no-cov"])
    with World() as world:
        controller = Controller(world, load_config())
        controller.move(HOME + 0.1)
        controller.run_until_idle()
        pixels = world.render(320, 240)
        Image.fromarray(pixels).save(root / "outputs/wheel-viewport.png")
    report = {
        "passed": code == 0,
        "pytest_exit_code": int(code),
        "loaded_from_wheel": True,
        "render_shape": list(pixels.shape),
        "editable_site_disabled": bool(sys.flags.no_site),
    }
    (root / "reports/wheel-smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
