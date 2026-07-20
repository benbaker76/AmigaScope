# Wiring AmigaScope into an MCP client

The AmigaScope MCP server (`amigascope_mcp.py`) exposes the debugging, instrumentation and
profiling tools to any Model Context Protocol client (Claude Code, Claude Desktop, …) over
stdio. It's a thin frontend over the CLI, so nothing here changes how the CLI behaves.

## 1. Install

```sh
pip install -r requirements.txt      # Pillow + mcp
```

## 2. Two environment variables

The server itself is project-agnostic; point it at your project with:

- **`AMIGASCOPE_ENV`** — the harness config file (drives / kickstart / entry trigger). It's
  what `amiga_gdb.sh` sources; e.g. a consuming project's `amigascope.env`. Needed for the
  `harness_up` / `harness_down` tools.
- **`AMIGASCOPE_ELF`** — the ELF with symbols (and `.debug_frame` for hierarchical CPU
  stacks). Needed for `cpu_flamegraph*` and `size_profile`.

## 3a. Claude Code

Project-scoped (checked in): copy `.mcp.json.example` to your project root as `.mcp.json`,
edit the absolute paths, and Claude Code picks it up. Or add it from the CLI:

```sh
claude mcp add amigascope \
  -e AMIGASCOPE_ENV=/abs/path/to/amigascope.env \
  -e AMIGASCOPE_ELF=/abs/path/to/your.elf \
  -- python3 /abs/path/to/AmigaScope/amigascope_mcp.py
```

## 3b. Claude Desktop

Add to `claude_desktop_config.json` (macOS:
`~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`):

```json
{
  "mcpServers": {
    "amigascope": {
      "command": "python3",
      "args": ["/abs/path/to/AmigaScope/amigascope_mcp.py"],
      "env": {
        "AMIGASCOPE_ENV": "/abs/path/to/amigascope.env",
        "AMIGASCOPE_ELF": "/abs/path/to/your.elf"
      }
    }
  }
}
```

Restart the client after editing.

## 4. Use it

Bring the harness up first — either the `harness_up` tool, or `./amiga_gdb.sh up` in a
terminal — then ask the assistant to read a symbol, set a watchpoint, `continue_and_wait`,
capture a DMA map, run a `size_profile`, etc. Debugging tools need the harness up; the
profiling tools additionally need the cycle-exact FS-UAE build; `size_profile` is static
and needs no running target.

## Smoke test (no client needed)

```sh
python3 - <<'PY'
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
    p = StdioServerParameters(command="python3", args=["amigascope_mcp.py"])
    async with stdio_client(p) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            print([t.name for t in (await s.list_tools()).tools])
asyncio.run(main())
PY
```
