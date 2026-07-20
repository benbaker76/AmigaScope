#!/usr/bin/env python3
"""AmigaScope MCP server — the AI-native frontend.

Exposes AmigaScope's debugging, instrumentation and profiling capabilities as
Model Context Protocol tools, so an MCP client (Claude Code, Claude Desktop, ...)
can drive a live Amiga (or the SDL/x86 build) directly: read/write memory, set
breakpoints and watchpoints, run and inspect, capture DMA/CPU profiles.

Design: this is a THIN frontend. Every tool shells out to the same CLI that a
human or a shell script uses (gdb_proxy.py, dma_profile.py, cpu_flamegraph.py,
copper_disasm.py, fb_capture.py) — the CLI stays the engine, MCP is one of two
faces. Nothing here is lost when you use the CLI directly.

Run (stdio transport):   python3 amigascope_mcp.py
Register it in your MCP client as a stdio server pointing at this file.

The debugging tools need the harness daemon up (`amiga_gdb.sh up`, or the `harness_up`
tool). Profiling tools additionally need the cycle-exact FS-UAE build. Project-specific
launch config comes from $AMIGASCOPE_ENV (see amiga_gdb.sh).
"""
import os, sys, subprocess
from mcp.server.fastmcp import FastMCP, Image

HERE    = os.path.dirname(os.path.abspath(__file__))
PY      = sys.executable
GDB     = os.path.join(HERE, "gdb_proxy.py")
DMA     = os.path.join(HERE, "dma_profile.py")
FLAME   = os.path.join(HERE, "cpu_flamegraph.py")
COPPER  = os.path.join(HERE, "copper_disasm.py")
FB      = os.path.join(HERE, "fb_capture.py")
SIZE    = os.path.join(HERE, "size_profile.py")
HARNESS = os.path.join(HERE, "amiga_gdb.sh")
TMP     = os.environ.get("AMIGASCOPE_TMP", "/tmp")

mcp = FastMCP("AmigaScope")

def _run(argv, timeout):
    r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip()

def _gp(*args, timeout=60):
    return _run([PY, GDB, *args], timeout)

def _gcmd(command, timeout=30):
    """One gdb command against the running daemon."""
    return _gp("cmd", command, "--timeout", str(timeout), timeout=timeout + 15)

# ============================ debugging (the core) ============================

@mcp.tool()
def status() -> str:
    """Harness/target health: is gdb attached, and is the target stopped or running
    (with the current PC)? Use this first to confirm the debug session is live."""
    return _gp("health")

@mcp.tool()
def read_memory(address: str, count: int = 16, size: str = "w") -> str:
    """Read memory. `address` is hex (0x219b10) or a symbol/expression. `count` units,
    `size` = b(yte)/h(alfword)/w(ord,32)/g(iant,64). Returns gdb's `x/` dump."""
    size = size if size in "bhwg" else "w"
    return _gcmd(f"x/{count}x{size} {address}")

@mcp.tool()
def read_symbol(name: str) -> str:
    """Read a symbol or C expression (a global, `*ptr`, `struct.field`, `arr[3]`, ...)."""
    return _gcmd(f"print {name}")

@mcp.tool()
def write_memory(address: str, value: str, size: str = "w") -> str:
    """Write `value` to raw memory at `address`. `size` = b/h/w/g -> char/short/int/long long."""
    ctype = {"b": "char", "h": "short", "w": "int", "g": "long long"}.get(size, "int")
    return _gcmd(f"set {{{ctype}}}{address} = {value}")

@mcp.tool()
def write_symbol(name: str, value: str) -> str:
    """Write a value to a variable/symbol (gdb `set variable name = value`)."""
    return _gcmd(f"set variable {name} = {value}")

@mcp.tool()
def registers() -> str:
    """Dump the CPU registers (gdb `info registers`)."""
    return _gcmd("info registers")

@mcp.tool()
def set_breakpoint(location: str) -> str:
    """Set a breakpoint at a function name, `file:line`, or `*address`."""
    return _gcmd(f"break {location}")

@mcp.tool()
def set_watchpoint(expression: str) -> str:
    """Set a write-watchpoint on a variable/expression (halts when it changes)."""
    return _gcmd(f"watch {expression}")

@mcp.tool()
def clear_breakpoints() -> str:
    """Delete all breakpoints and watchpoints."""
    return _gcmd("delete")

@mcp.tool()
def continue_and_wait(timeout: int = 30) -> str:
    """Resume the target and BLOCK until it next stops (breakpoint / watchpoint / signal)
    or `timeout` seconds elapse. Returns the stop location. This is how you 'run to' a
    breakpoint from a request/response tool call."""
    _gp("cmd", "continue", "--timeout", "2", timeout=8)
    return _gp("waitstop", str(timeout), timeout=timeout + 15)

@mcp.tool()
def step_instruction(count: int = 1) -> str:
    """Single-step `count` machine instructions (gdb `stepi`)."""
    return _gcmd(f"stepi {count}")

@mcp.tool()
def backtrace(depth: int = 8) -> str:
    """Show the call stack (gdb `backtrace N`)."""
    return _gcmd(f"backtrace {depth}")

@mcp.tool()
def disassemble(location: str = "$pc", count: int = 8) -> str:
    """Disassemble `count` instructions at `location` (a symbol, address, or $pc)."""
    return _gcmd(f"x/{count}i {location}")

@mcp.tool()
def gdb_raw(command: str) -> str:
    """Escape hatch: run an arbitrary gdb command and return its output."""
    return _gcmd(command)

# ===================== instrumentation / profiling ==========================

@mcp.tool()
def dma_profile(frames: int = 1) -> str:
    """Capture `frames` frames of cycle-exact DMA and report contention + the
    bitplane-fetch-vs-sprite-slot steal. Target must be stopped with NO breakpoints."""
    out = os.path.join(TMP, "amigascope_dma.prof")
    _run([PY, DMA, "profile", str(frames), out], timeout=frames * 120 + 120)
    return _run([PY, DMA, "parse", out], timeout=120) or "no output (capture may have stalled)"

@mcp.tool()
def dma_map() -> Image:
    """Render the DMA raster-map PNG for one freshly captured frame (each colour-clock
    coloured by which DMA channel owned it; annotated sprite-slot vs fetch-start)."""
    prof = os.path.join(TMP, "amigascope_dma.prof")
    _run([PY, DMA, "profile", "1", prof], timeout=180)
    _run([PY, DMA, "map", prof, os.path.join(TMP, "amigascope_dma")], timeout=60)
    return Image(path=os.path.join(TMP, "amigascope_dma_f0_left.png"))

@mcp.tool()
def cpu_flamegraph_top(frames: int = 4, n: int = 20) -> str:
    """CPU profile: top-`n` functions by self-cycles over `frames` frames (flat leaf view —
    quick 'what's hot'). Captures with the DWARF unwind, then aggregates by leaf."""
    prof = os.path.join(TMP, "amigascope_cpu.prof")
    _run([PY, FLAME, "capture", str(frames), prof], timeout=frames * 120 + 180)
    return _run([PY, FLAME, "top", prof, str(n)], timeout=120) or "no output (capture may have stalled)"

@mcp.tool()
def cpu_flamegraph(frames: int = 8) -> str:
    """CPU flame graph with FULL call stacks (DWARF .debug_frame deep-stack unwind).
    Captures `frames` frames WITH the generated unwind table, returns the hottest
    hierarchical stacks (root;...;leaf cycles), and writes the interactive SVG. Use this
    to see the call TREE (who called the hot leaf), not just the leaves."""
    prof = os.path.join(TMP, "amigascope_cpu.prof")
    svg  = os.path.join(TMP, "amigascope_cpu.svg")
    _run([PY, FLAME, "capture", str(frames), prof], timeout=frames * 120 + 180)
    stacks = _run([PY, FLAME, "fold", prof], timeout=120)
    _run([PY, FLAME, "svg", prof, svg], timeout=120)
    top = "\n".join(stacks.splitlines()[:25]) or "no stacks (capture may have stalled)"
    return f"Hierarchical call stacks (top 25 by cycles):\n{top}\n\nInteractive flame-graph SVG: {svg}"

@mcp.tool()
def size_profile(top: int = 20) -> str:
    """Static size profile of the executable ($AMIGASCOPE_ELF): section totals plus the
    top-`top` functions and data objects by bytes, and the reference (relocation) counts —
    where every byte of the binary goes. Also writes a size flame-graph SVG. Static, so it
    needs no running target."""
    elf = os.environ.get("AMIGASCOPE_ELF", "")
    rep = _run([PY, SIZE, "report", elf, str(top)], timeout=180)
    svg = os.path.join(TMP, "amigascope_size.svg")
    _run([PY, SIZE, "svg", elf, svg], timeout=180)
    return rep + f"\n\nSize flame-graph SVG: {svg}"

@mcp.tool()
def disasm_copper() -> str:
    """Disassemble the live copper list (MOVE/WAIT/SKIP with decoded registers)."""
    return _run([PY, COPPER], timeout=60)

@mcp.tool()
def capture_frontbuffer() -> Image:
    """Decode and return the displayed frontbuffer straight from chip RAM as a PNG."""
    png = os.path.join(TMP, "amigascope_fb.png")
    _run([PY, FB, png], timeout=60)
    return Image(path=png)

# ============================ harness lifecycle =============================

@mcp.tool()
def harness_up() -> str:
    """Bring the debug harness up: launch FS-UAE, attach gdb, wait for the entry
    trigger. Uses the project's $AMIGASCOPE_ENV launch config."""
    return _run(["bash", HARNESS, "up"], timeout=200)[-800:]

@mcp.tool()
def harness_down() -> str:
    """Tear the debug harness down (stop gdb + FS-UAE)."""
    return _run(["bash", HARNESS, "down"], timeout=60)

if __name__ == "__main__":
    mcp.run()
