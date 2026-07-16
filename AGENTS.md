# Repository guidance

## Current-scene read fast path

For generic read-only questions such as "what is in my current Blender scene?"
or "summarize the current scene," call the configured Blender MCP
`get_current_scene_summary` tool directly and exactly once. The MCP call itself
is the connection check. Do not load the nodebpy skill, search memory or the
repository, run a shell command, or run a separate connection probe first.

If that direct MCP call fails, report its MCP error. Do not search the
repository, run a shell connection probe, or try an alternate transport.

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
