# Repository guidance

## Default scope

For Blender node-tree tasks, start from the connected Blender session and the
nodebpy skill at `.agents/skills/nodebpy/SKILL.md`.

Do not inspect these files unless the user explicitly asks about repository or
plugin packaging:

- `sync_skills.py`
- `README.md`
- `.claude/`
- `.claude-plugin/`
- `.codex/`
- `.git/`

Do not recursively scan the repository to locate the Blender MCP. Use the
configured MCP server or the active local Blender connection described by the
nodebpy skill.

