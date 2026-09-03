"""The static checks, run as tests: flake8 for the style, mypy for the types.

Every check goes through `make test` (see CLAUDE.md), and these two are no exception: a line too
long, an unused name or a type that does not add up fails the suite, with the tool's own report as
the failure message. Both read their configuration from the root - `.flake8`, and `[tool.mypy]` in
`pyproject.toml` - and run over the whole repository, exactly as `make lint` runs them.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def report_of(tool):
    """Runs a checker from the repository root, with the interpreter running the suite."""
    return subprocess.run([sys.executable, "-m", tool], cwd=ROOT, capture_output=True, text=True)


@pytest.mark.parametrize("tool", ["flake8", "mypy"])
def test_the_checker_finds_nothing_to_report(tool):
    report = report_of(tool)
    assert report.returncode == 0, f"{tool} reports:\n{report.stdout}{report.stderr}"
