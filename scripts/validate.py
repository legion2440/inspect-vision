"""Run the complete cross-platform repository validation suite."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str]) -> None:
    print(f"[RUN] {' '.join(command)}", flush=True)
    process = subprocess.run(command, cwd=REPOSITORY_ROOT, check=False)
    if process.returncode != 0:
        raise SystemExit(process.returncode)


def main() -> int:
    npm = "npm.cmd" if os.name == "nt" else "npm"
    commands = (
        [sys.executable, "scripts/validate_structure.py"],
        [sys.executable, "scripts/validate_demo_samples.py"],
        [sys.executable, "scripts/validate_showcase_samples.py"],
        [sys.executable, "scripts/validate_architecture.py"],
        [sys.executable, "scripts/generate_dependency_graph.py", "--check"],
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/unit/backend_api",
            "tests/unit/contracts",
            "tests/unit/detection",
            "tests/unit/history",
            "tests/unit/evidence",
            "tests/integration/api",
        ],
        [npm, "--prefix", "frontend", "test"],
        [npm, "--prefix", "frontend", "run", "build"],
        [sys.executable, "scripts/check_frontend_dependencies.py"],
    )
    for command in commands:
        _run(command)
    print("[OK] Complete repository validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
