# nodebpy agent skill

Build and edit Blender Geometry Nodes, shader nodes, and compositor trees with
[nodebpy](https://bradyajohnston.github.io/nodebpy/). The skill gives coding
agents a focused workflow for inspecting node trees, generating nodebpy code,
and executing changes live through the [Blender MCP](https://projects.blender.org/lab/blender_mcp).

## Quick start

1. Download this repository as a ZIP.
2. Open your current project in Codex or Claude.
3. Attach the ZIP and say: **“Load this into my current project.”**

The skill is installed at project level. 
This keeps its behavior, references, and Blender conventions versioned alongside the project that uses them.

## Requirements

- [Blender](https://www.blender.org/)
- [Blender MCP](https://projects.blender.org/lab/blender_mcp)
- [uv](https://docs.astral.sh/uv/)

This repository expects the Blender MCP checkout at `$HOME/blender_mcp/mcp`.
If yours lives elsewhere, update `.mcp.json` for Claude and `.codex/config.toml`
for Codex.

## Claude Code CLI plugin installation

You can also install the repository directly as a Claude Code plugin:

```text
/plugin marketplace add kolibril13/nodebpy-agent-skills
/plugin install nodebpy@nodebpy-agent-skills
```

## Skill development

`.agents/skills` is the canonical source of truth. The Claude-specific skill
directory contains generated relative symlinks to it; do not edit skills through
`.claude/skills`.

After adding, removing, or renaming a skill, regenerate the Claude links:

```bash
uv run sync_skills.py
```
