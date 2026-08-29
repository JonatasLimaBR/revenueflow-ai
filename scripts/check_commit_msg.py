#!/usr/bin/env python3
"""Validate the commit message against Conventional Commits (the AGENTS.md type set).

Used as a pre-commit `commit-msg` stage hook. Receives the path to the commit
message file as argv[1]. Exits non-zero (blocking the commit) on violation.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TYPES = ("feat", "fix", "test", "docs", "refactor", "chore", "ci")
PATTERN = re.compile(rf"^(?:{'|'.join(TYPES)})(?:\([a-z0-9._-]+\))?!?: .+")


def first_meaningful_line(message: str) -> str:
    for line in message.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def main() -> int:
    if len(sys.argv) < 2:
        print("check_commit_msg: missing commit message file path", file=sys.stderr)
        return 1

    subject = first_meaningful_line(Path(sys.argv[1]).read_text(encoding="utf-8"))

    # Allow merge/revert commits that git or `git revert` generate automatically.
    if subject.startswith(("Merge ", "Revert ", "revert:", "fixup!", "squash!")):
        return 0

    if PATTERN.match(subject):
        return 0

    print(
        "\n"
        "Invalid commit message.\n"
        "Use Conventional Commits: <type>[optional scope][!]: <description>\n"
        f"  type = {', '.join(TYPES)}\n"
        "\n"
        f"  got: {subject!r}\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
