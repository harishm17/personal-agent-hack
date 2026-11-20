"""Runs the screen's pure-function tests (formatting, the figure highlight, the ?sim=1 recompute) under node."""
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def test_screen_model_js():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    run = subprocess.run([node, "--test", "tests/screen/model.test.mjs"], cwd=ROOT, capture_output=True, text=True,
                         timeout=50)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-2000:]
