---
name: nodebpy
description: Build Blender node trees (geometry nodes, shader nodes, compositor) programmatically with the nodebpy Python library, executed live in Blender via the Blender MCP. Use when the user wants to create or modify Blender node setups, geometry nodes, shaders, or compositor trees from code.
---

# nodebpy — Blender node trees from Python

nodebpy (https://bradyajohnston.github.io/nodebpy/) builds Blender node trees in code
instead of the GUI, with type hints and IDE completion.

## Prerequisites

- The Blender MCP server must be connected (Blender running with the addon enabled).
- nodebpy must be installed in Blender's Python. Check and install if missing by
  executing this in Blender via the MCP:

```python
import sys, subprocess
try:
    import nodebpy
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "nodebpy"])
    import nodebpy
print(nodebpy.__version__)
```

## Core workflow

1. Write nodebpy code that builds the node tree.
2. Execute it in Blender through the Blender MCP code-execution tool.
3. Verify the result (inspect the tree, take a viewport screenshot if available).

## API basics

Trees are built inside a context manager; nodes are chained with `>>`; the tree
interface is declared through `tree.inputs` / `tree.outputs`. Python math operators
(`+`, `*`, comparisons, …) automatically create matching Math/Compare nodes.

```python
from nodebpy import geometry as g

with g.tree("MyTree") as tree:
    result = (tree.inputs.integer("Count", 10)
              >> g.Points()
              >> tree.outputs.geometry("Output"))
```

Node tree types: `nodebpy.geometry`, `nodebpy.shader`, `nodebpy.compositor`.

## References

<!-- TODO: propagate content into references/ and link it here, e.g.
- references/geometry-nodes.md — geometry node patterns and examples
- references/shader-nodes.md — shader node patterns
- references/compositor.md — compositor setups
- references/nodes-to-code.md — converting existing trees to nodebpy code
-->
