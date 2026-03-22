"""
Ruff lint enforcement test.

Ensures all production code passes ruff lint checks.
Fails the test suite if any linting violations are found.
"""

import subprocess


def test_ruff_passes():
    """Ensure all code passes ruff lint."""
    result = subprocess.run(
        [
            "ruff",
            "check",
            "apps/",
            "core/",
            "integrations/",
            "config/",
            "--config",
            "ruff.toml",
        ],
        capture_output=True,
        text=True,
        cwd="/root/stepora",
    )
    assert result.returncode == 0, f"Ruff violations:\n{result.stdout}"
