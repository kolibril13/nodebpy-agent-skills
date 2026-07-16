#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Copy canonical agent skills into Claude's generated skills directory."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT / ".agents" / "skills"
DEFAULT_TARGET = ROOT / ".claude" / "skills"


def validate(source: Path) -> None:
    if not source.is_dir():
        raise ValueError(f"source directory does not exist: {source}")

    skills = sorted(path for path in source.iterdir() if path.is_dir())
    if not skills:
        raise ValueError(f"no skills found in {source}")

    for skill in skills:
        manifest = skill / "SKILL.md"
        if not manifest.is_file():
            raise ValueError(f"missing required file: {manifest}")

        text = manifest.read_text(encoding="utf-8")
        match = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", text, re.DOTALL)
        if not match:
            raise ValueError(f"missing YAML frontmatter: {manifest}")

        frontmatter = match.group(1)
        for field in ("name", "description"):
            if not re.search(rf"(?m)^{field}:\s*\S", frontmatter):
                raise ValueError(f"missing frontmatter field {field!r}: {manifest}")

        name = re.search(r"(?m)^name:\s*([^\n#]+)", frontmatter)
        if name and name.group(1).strip().strip("'\"") != skill.name:
            raise ValueError(
                f"skill name must match its directory: {skill.name!r} ({manifest})"
            )

    symlinks = [path for path in source.rglob("*") if path.is_symlink()]
    if symlinks:
        raise ValueError(f"canonical skills must not contain symlinks: {symlinks[0]}")


def snapshot(directory: Path) -> dict[Path, bytes]:
    if not directory.exists():
        return {}
    return {
        path.relative_to(directory): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero when the generated target is out of date",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    target = args.target.resolve()

    try:
        validate(source)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if snapshot(source) == snapshot(target):
        print(f"Skills are in sync: {target}")
        return 0

    if args.check:
        print(f"Skills are out of sync: {target}", file=sys.stderr)
        return 1

    # The target is generated output; replacing it also removes stale skill files.
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    print(f"Synced {source} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
