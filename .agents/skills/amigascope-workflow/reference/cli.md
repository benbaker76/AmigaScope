# AmigaScope CLI reference

All scripts are in the repo root. Python tools need Python 3.6+; `dma_profile.py map/compare`
need Pillow. Tools that touch the target go through the `gdb_proxy.py` daemon, so the
harness must be up (`amiga_gdb.sh up`) unless noted as static.

## amiga_gdb.sh

Launch FS-UAE, attach gdb through the daemon, and health-check the attach.

| Command | Effect |
|---|---|
| `up` | Reuse a live healthy session if one exists (interrupting a running target to check); otherwise down, launch, attach, health-check, retrying up to `ATTACH_RETRIES` full restarts. Prints `OK` or `FAIL`. |
| `up --fresh` | Force a clean restart even if a session is live (`FORCE_RESTART=1` does the same). |
| `down` | Kill gdb, the daemon and the FS-UAE on `PORT`; remove the socket and FS-UAE's native log. Prints `DOWN`. |
| `restart` | `down` then `up --fresh`. |
| `status` | `HEALTHY (PC=...)`, `DEGRADED`, or `DOWN (no socket)`. |

Healthy = daemon answers `pong`, `info program` reports SIGTRAP, `$pc` is a non-zero
address. FS-UAE is launched as `--amiga_model=a1200`, 2 MB chip, 8 MB fast, PAL,
`--remote_debugger=20 --remote_debugger_trigger=$TRIGGER`, clipboard sharing off (WSLg
crash workaround). Change the model/memory in the script if your target differs.

## gdb_proxy.py

A daemon that owns one gdb process and serves requests on a Unix socket
(`/tmp/swos_gdb.sock`), plus client subcommands.

| Subcommand | Use |
|---|---|
| `daemon [--mode amiga\|sdl] [--elf P] [--bin P] [--host H] [--port N]` | Start the proxy in the foreground (amiga_gdb.sh backgrounds it). amiga: m68k gdb + `target remote` to FS-UAE (host auto-detected from WSL2 resolv.conf if omitted). sdl: `/usr/bin/gdb` on the native binary, cwd = its directory; start it with `cmd "run"`. Exits 2 if the ELF/binary is missing. |
| `cmd "<gdb command>" [--timeout S]` | Run one gdb command, return output up to the next prompt (default timeout 10 s). Flushes pending async output first so halts are not lost. |
| `waitstop [SECONDS]` | Block until a breakpoint / watchpoint / signal stop (default 300 s). Returns immediately if the target is already stopped. Use right after `cmd "continue"`. |
| `poll [SECONDS]` | Return buffered output after SECONDS of inactivity, without sending a command. |
| `health` | `OK stopped ...` / `DEGRADED target running (busy ...)` / `DEGRADED ...` / `DOWN (socket missing)`. Non-draining, safe while running. |
| `watch [--interval S] [--timeout S] [--label TXT] [--once] [--no-frame]` | Print one line per running->stopped transition (with frame location). Pipe into a notifier. |
| `raw "<bytes>"` | Write raw bytes to gdb's stdin (no newline). A `$'\x03'` byte does NOT interrupt the target (no tty) even though it prints `[sent]`. |
| `ping` / `status` / `stop` | Round trip / reachability / shut the daemon down (shutting down burns the one-shot FS-UAE port). |

Output markers to recognise:
- `[BUSY: target running — read-probes refused; wait_stop or interrupt first]` — a
  read probe (`print p inspect info x bt backtrace where display frame f list l`) was
  refused because the target is running. Control commands still pass.
- `[TIMEOUT after Ns — partial output below]` — no prompt; the daemon now considers the
  target running.
- `[WAITSTOP timeout after Ns — target still running]`.

Interrupting a running target: `pkill -INT -f '[m]68k-amiga-elf-gdb'` (the `[m]` keeps
pkill from matching its own command line) or `kill -INT $(pgrep -f m68k-amiga-elf-gdb | head -1)`,
then `gdb_proxy.py waitstop 8`. The stop reports as SIGTRAP.

Useful gdb commands through `cmd`: `print sym`, `print/x $pc`, `x/16xw ADDR`,
`set variable g = 1`, `set {short}ADDR = 0x1234`, `break Func` / `break *0xADDR`,
`watch g`, `rwatch`/`awatch`, `delete`, `stepi N`, `x/8i $pc`, `info registers`,
`backtrace`, `dump binary memory FILE START END`, `monitor screenshot`,
`monitor profile N "UNWIND" "OUT"`.

## dma_profile.py (cycle-exact FS-UAE only)

| Command | Output |
|---|---|
| `profile N OUT.prof` | Issue `monitor profile N "" "OUT"` and poll until N frame blocks exist. Prints `OK`/`FAILED`. Stop the target and delete breakpoints first. |
| `parse OUT.prof` | Per frame: bitplane/blitter/conflict cell counts, display lines vs blitter-active lines (`>>> CONTENTION` when the blitter runs on display lines), per-channel frame budget, and the bitplane-fetch start vs the eight sprite DMA slots (`>>> STEAL`). |
| `blits OUT.prof` | One line per reconstructed blit: raster span, size, channels, destination, `<<< OVERRUNS DISPLAY` flag. |
| `map OUT.prof [PREFIX]` | PNGs per frame: `PREFIX_fN_full.png` (227x313 DMA raster) and `PREFIX_fN_left.png` (sprite slots vs fetch start). Colours: bitplane green, sprite yellow, blitter red, copper blue, conflict magenta. |
| `compare A.prof B.prof [OUT.png]` | Side-by-side left-edge panels of frame 0 (before/after a fix). |
| `N` | Profile N frames to a temp file, then `parse` + `blits`. |

The record grid is 227 hpos x 313 vpos colour clocks per frame (58-byte records). The
display window used by `parse` (vpos 36..307) and the sprite-slot map are the SWOS AGA
lores values - adjust in the script for another display.

## cpu_flamegraph.py

| Command | Output |
|---|---|
| `capture N OUT.prof` | Interrupt gdb, `delete` breakpoints, generate a DWARF unwind table next to OUT, `monitor profile N UNWIND OUT`, poll. Needs cycle-exact FS-UAE. |
| `top IN.prof [N]` | Top-N functions by self cycles (default 25). |
| `fold IN.prof [OUT.folded]` | Brendan Gregg folded stacks. |
| `svg IN.prof [OUT.svg]` | Folded stacks rendered with `third_party/FlameGraph` (`$FLAMEGRAPH_PY`). |
| `unwind OUT` | Only generate the unwind table from the ELF's `.debug_frame`. |

Symbols come from `$AMIGASCOPE_ELF` via `m68k-amiga-elf-objdump` (`$M68K_OBJDUMP`). Without
`.debug_frame` (typical for pure assembler) stacks are depth 1: a flat self-time profile.
Kickstart PCs ($F80000-$FFFFFF) are absolute; `0x7fffffff` marks interrupt time.

## size_profile.py (static, no target)

`report [ELF] [N]` section totals, top-N functions and data, relocation counts;
`fold [ELF] [OUT]` byte-weighted folded stacks; `svg [ELF] [OUT]` size flame graph.
ELF defaults to `$AMIGASCOPE_ELF`. Untyped assembler labels count as code in `.text`,
data elsewhere.

## copper_disasm.py

`copper_disasm.py` (reads `&_copperListBuffer`, size `COPPERLIST_SIZE_BYTES` or 1316),
`copper_disasm.py ADDR [BYTES]`, `copper_disasm.py --sym SYMBOL [BYTES]`.
Prints `MOVE REG = $VAL ; decoded fields` / `WAIT` / `SKIP` with OCS/ECS/AGA register
names. Decodes BPLCON0 (plane count incl. AGA BPU3, hires/shres, HAM/DPF/LACE), BPLCON1
(both playfields in lores pixels using the AGA split-bit layout, e.g. `$8822` = 34 px),
BPLCON2/3/4, FMODE (fetch width per bitplanes/sprites, scan doubling), DDFSTRT/DDFSTOP (colour
clocks and lores DIW x), DIWSTRT/DIWSTOP (OCS V8 rule), DIWHIGH, and COLORxx - tracking the
last BPLCON3 so AGA bank/LOCT colour loads show the real 0-255 entry and nibble half.
For programs without that symbol always pass an address or `--sym`; the address of the
list the hardware is running is what you wrote to COP1LC.

## fb_capture.py

`fb_capture.py [OUT.png] [other]` decodes the frontbuffer from chip RAM via the copper
list's first bitplane pointer, with the program palette. Layout constants (8 planes,
48 bytes/plane row, 272 lines, `_gamePalette` 12-bit) are SWOS-specific: edit them for
another program. Halt-only: shows what is IN the buffer, not what the beam displayed.

## shot.sh

`shot.sh CAMX CAMY OUT.png` - SWOS example of a settled composited screenshot: sets
program globals, runs a frame, `monitor screenshot`, copies the newest file from
`~/FS-UAE/Screenshots/`. A template for your own settle-then-shoot script.

## analyze_pc32.py / fix_hunk_relocs.py

`analyze_pc32.py ELF` lists `R_68K_PC32` relocations and why elf2hunk keeps them.
`fix_hunk_relocs.py ELF HUNK [OUT]` removes the bogus HUNK_RELOC32 entries elf2hunk (from
the 1.8.1 extension) emits for PC-relative 32-bit relocations, which corrupt `BRA.L`/`BSR.L`
displacements at load time. Run it when a hunk executable crashes on long branches that
are fine in the ELF.
