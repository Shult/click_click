"""La version affichée doit être celle du projet, pas une valeur oubliée."""

import re
import tomllib
from pathlib import Path

import version

ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_matches_the_module():
    declared = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    assert declared == version.__version__


def test_version_is_semantic():
    assert re.fullmatch(r"\d+\.\d+\.\d+", version.__version__)
