# Repository guidance

## Blender

For read-only scene summaries, call `get_current_scene_summary` once. Treat it
as the connection check; on failure, report the MCP error without loading
nodebpy, searching memory or the repository, probing, retrying, or falling back.

For node-tree tasks, use `.agents/skills/nodebpy/SKILL.md` and the configured
Blender MCP directly.

Do not inspect these files unless the user explicitly asks about repository or
plugin packaging:

- `sync_skills.py`
- `README.md`
- `.claude/`
- `.claude-plugin/`
- `.codex/`
- `.git/`

Never scan the repository to locate the Blender MCP.
