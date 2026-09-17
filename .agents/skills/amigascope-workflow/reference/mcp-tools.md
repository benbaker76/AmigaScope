# AmigaScope MCP tools

`amigascope_mcp.py` (stdio, FastMCP) is a thin frontend: each tool shells out to the CLI in
`reference/cli.md`, so behaviour and gotchas are identical. Register it per `docs/MCP.md`
(`.mcp.json.example`). Needs `pip install mcp`; temp files go to `$AMIGASCOPE_TMP`
(default `/tmp`).

## Debugging (harness must be up)

| Tool | Parameters | Does |
|---|---|---|
| `status` | - | `gdb_proxy.py health`: attached? stopped or running? PC. Call first. |
| `read_memory` | `address`, `count=16`, `size=w` | `x/{count}x{size} address`; size b/h/w(32-bit)/g(64-bit). |
| `read_symbol` | `name` | `print name` (any C expression). |
| `write_memory` | `address`, `value`, `size=w` | `set {char/short/int/long long}address = value`. |
| `write_symbol` | `name`, `value` | `set variable name = value`. |
| `registers` | - | `info registers`. |
| `set_breakpoint` | `location` | `break location` (function, `file:line`, `*0xADDR`). |
| `set_watchpoint` | `expression` | `watch expression` (write watchpoint). |
| `clear_breakpoints` | - | `delete`. |
| `continue_and_wait` | `timeout=30` | `continue`, then `waitstop timeout`; returns the stop location. |
| `step_instruction` | `count=1` | `stepi count`. |
| `backtrace` | `depth=8` | `backtrace depth`. |
| `disassemble` | `location=$pc`, `count=8` | `x/{count}i location`. |
| `gdb_raw` | `command` | Any gdb command. |

Note the gdb size letters: `w` is a 32-bit word and `h` a 16-bit half-word — the opposite
of 68k `.w`/`.l` naming.

## Instrumentation and profiling (cycle-exact FS-UAE; target stopped, no breakpoints)

| Tool | Parameters | Does |
|---|---|---|
| `dma_profile` | `frames=1` | `dma_profile.py profile` + `parse`: contention, budget, sprite-slot steal. |
| `dma_map` | - | Capture 1 frame, return the left-edge DMA raster PNG inline. |
| `cpu_flamegraph_top` | `frames=4`, `n=20` | Capture with unwind, return top-n leaf functions. |
| `cpu_flamegraph` | `frames=8` | Capture with unwind, return the 25 hottest folded stacks and write an SVG path. |
| `disasm_copper` | - | `copper_disasm.py` with its default symbol (SWOS `_copperListBuffer`); use `gdb_raw` + the CLI for other lists. |
| `capture_frontbuffer` | - | `fb_capture.py` PNG inline (SWOS buffer layout). |
| `size_profile` | `top=20` | Static size report of `$AMIGASCOPE_ELF` + SVG path. No target needed. |

## Lifecycle

| Tool | Does |
|---|---|
| `harness_up` | `amiga_gdb.sh up` using `$AMIGASCOPE_ENV` (timeout 200 s; returns the last 800 chars). |
| `harness_down` | `amiga_gdb.sh down`. |

Each capture frame costs tens of seconds of wall-clock; request few frames. If a profiling
tool returns "no output (capture may have stalled)", check whether hardware sprites were
active in the profiled frames and that no breakpoint was set.
