---
name: amigascope-workflow
description: Drive AmigaScope's headless debug loop - bring up FS-UAE + gdb, read/write memory, breakpoints, watchpoints, stepping, then instrument and profile (DMA raster maps, copper disassembly, frontbuffer capture, CPU and size flame graphs). Use whenever debugging, inspecting or profiling a running Amiga (or SDL) program through this repo's scripts or its MCP server, or when a harness command fails, hangs or reports DEGRADED.
---

# AmigaScope workflow

AmigaScope is a CLI pipe: `amiga_gdb.sh` launches FS-UAE and attaches
`m68k-amiga-elf-gdb` through a resident daemon (`gdb_proxy.py`); every other
tool (`dma_profile.py`, `cpu_flamegraph.py`, `copper_disasm.py`,
`fb_capture.py`, `size_profile.py`) talks to the target through that daemon.
`amigascope_mcp.py` exposes the same engine as MCP tools. Scripts live in the
repo root; run them from there.

## The loop

1. **Configure once.** Export `AMIGASCOPE_ENV` (a shell file sourced by
   `amiga_gdb.sh`) and `AMIGASCOPE_ELF` (the ELF with symbols). The built-in
   defaults are the author's SWOS project and WILL be wrong for anything else -
   see `reference/configuration.md`.
2. **Bring it up:** `./amiga_gdb.sh up` -> prints `OK` when the target is
   stopped at the entry trigger with a readable PC. It REUSES a live healthy
   session (instant); `up --fresh` forces a cold boot (~30 s).
3. **Drive it:** `python3 gdb_proxy.py cmd "<any gdb command>"`, one command
   per call. Check state with `python3 gdb_proxy.py health`
   (`OK stopped PC=...` / `DEGRADED ...`).
4. **Run to a stop:** `cmd "continue"` then `python3 gdb_proxy.py waitstop 60`
   (blocks until a breakpoint/watchpoint/signal). Never poll with
   `info program` while it runs.
5. **Instrument / profile** with the target STOPPED and NO breakpoints set.
6. **Leave it resident** between debugging steps; `./amiga_gdb.sh down` only
   when finished.

## Hard rules

- **The FS-UAE gdb port is one-shot per emulator session.** Every
  connect/disconnect burns it. Do not kill the daemon or run a second gdb
  against the port; recovery is always `amiga_gdb.sh up --fresh`.
- **Busy-guard:** while the target runs, read probes (`print`, `x`, `info`,
  `bt`, `frame`, `list`, `display`) are refused with `[BUSY: ...]`. Use
  `waitstop`, or interrupt first (`kill -INT` the gdb pid, as `shot.sh` does).
- A `cmd` that returns `[TIMEOUT after Ns ...]` means the target resumed or
  gdb is busy - the daemon now treats it as running.
- **Interrupt with SIGINT, not bytes:** `pkill -INT -f '[m]68k-amiga-elf-gdb'` then
  `waitstop 8`. `gdb_proxy.py raw $'\x03'` prints `[sent]` but does nothing.
- **One client at a time.** A second script or probe while a long drive or `waitstop`
  runs interleaves gdb traffic and wedges the daemon. Diagnose "slow/DEGRADED" with
  `health` and `cmd "info breakpoints"` before restarting anything.
- **Writes need the write-capable stub** (benbaker76/vscode-amiga-debug's FS-UAE); the
  stock stub silently ignores memory/register writes. Verify with a write + read-back
  before trusting injected input or inferior calls, and give inferior calls minutes of
  timeout on the emulated Amiga.
- **Watchpoints fire on value change**, and symbols in chip-RAM sections may show their
  ELF address rather than the run-time one - see `reference/gdb-and-harness.md`.
- **DEGRADED with no readable PC** is most often a missing/wrong ELF path (the
  daemon exits with `FATAL: Amiga ELF not found` - check the daemon log), not
  an emulator timing fault.
- **Profiling** (`dma_profile.py`, `cpu_flamegraph.py capture`, the MCP
  profiling tools) needs the cycle-exact FS-UAE build that has
  `monitor profile`; a stock FS-UAE has no DMA recorder. `monitor profile`
  acks instantly and writes the file asynchronously (~15-25 s per frame) -
  the tools poll for it; do not assume failure early. Frames showing active
  hardware sprites can stall the recorder entirely.
- Halting or re-compositing erases real-time artifacts (tearing, blitter vs
  beam contention). If `fb_capture.py` shows a clean buffer but the screen is
  wrong, it is a timing/DMA bug: profile it, don't screenshot it.
- Several tools still carry SWOS-specific defaults (`copper_disasm.py` reads
  `_copperListBuffer`; `fb_capture.py` assumes SWOS's 8-plane buffer layout
  and `_gamePalette`; `shot.sh` sets SWOS camera globals; `amiga_gdb.sh` sets
  a `ShowLoaderIntroSequence` skip breakpoint). Pass explicit addresses/symbols
  for other programs and treat `fb_capture.py`/`shot.sh` as templates.

## How to look things up

- Every CLI subcommand, argument and output: `reference/cli.md`.
- MCP tool list and parameters: `reference/mcp-tools.md`.
- `AMIGASCOPE_ENV` keys, environment variables, log/socket paths:
  `reference/configuration.md`.
- Debugging recipes and the "which tool answers which question" decision
  table: `reference/recipes.md`.
- gdb, emulator, build and program-driving gotchas: `reference/gdb-and-harness.md`
  (condensed from `docs/GDB.md` and `docs/HARNESS.md`).
- Background write-up and a worked case study: `docs/TOOLKIT.md`; full gdb walkthrough:
  `docs/GDB.md`; driving a program from gdb: `docs/HARNESS.md`; MCP client registration:
  `docs/MCP.md`.
- The Amiga itself: custom chips and CIAs -> the amiga-hardware skill; AGA
  (A1200/A4000/CD32) -> the amiga-aga skill; 68k instructions and vasm
  directives -> the m68k-asm skill; exec/dos/graphics/intuition/diskfont
  calls -> the amiga-os skill; AHI audio -> the amiga-ahi skill.
