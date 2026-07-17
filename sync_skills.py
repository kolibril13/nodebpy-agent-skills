#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///


# run via -> uv run sync_skills.py

"""Link canonical agent skills into Claude's project skill directory."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT / ".agents" / "skills"
DEFAULT_TARGET = ROOT / ".claude" / "skills"


def validate(source: Path) -> list[Path]:
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

    return skills


def relative_link(skill: Path, target: Path) -> Path:
    return Path(os.path.relpath(skill, start=target))


def is_in_sync(skills: list[Path], target: Path) -> bool:
    if not target.is_dir() or target.is_symlink():
        return False

    expected_names = {skill.name for skill in skills}
    if {path.name for path in target.iterdir()} != expected_names:
        return False

    return all(
        (target / skill.name).is_symlink()
        and (target / skill.name).readlink() == relative_link(skill, target)
        for skill in skills
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero when the generated links are out of date",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    target = args.target.resolve()

    try:
        skills = validate(source)
        synced = is_in_sync(skills, target)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if synced:
        print(f"Skill links are in sync: {target}")
        return 0

    if args.check:
        print(f"Skill links are out of sync: {target}", file=sys.stderr)
        return 1

    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)

    target.mkdir(parents=True)
    for skill in skills:
        link = target / skill.name
        link.symlink_to(relative_link(skill, target), target_is_directory=True)

    print(f"Linked {len(skills)} skill(s): {source} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
