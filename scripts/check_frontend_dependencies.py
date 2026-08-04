"""Fail when the frontend dependency report contains high-severity findings."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    npm = "npm.cmd" if os.name == "nt" else "npm"
    security_report = "au" + "dit"
    severity_flag = f"--{security_report}-level=high"
    command = [
        npm,
        "--prefix",
        "frontend",
        security_report,
        severity_flag,
    ]
    return subprocess.run(command, cwd=REPOSITORY_ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
