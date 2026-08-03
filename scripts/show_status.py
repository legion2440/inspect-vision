"""Print the live Git SHA together with recorded limitations."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with (REPOSITORY_ROOT / "docs/project-status.json").open(encoding="utf-8") as status_file:
        status = json.load(status_file)

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    print(f"Current commit: {head}")
    print(f"Frontend baseline: {status['frontend_baseline_commit']}")
    print(f"State: {status['state']}")
    print("Known limitations:")
    for limitation in status["known_limitations"]:
        print(f"- [{limitation['area']}] {limitation['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
