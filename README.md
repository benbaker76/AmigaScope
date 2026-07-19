# AmigaScope

**Headless, cycle-exact profiling & visualization for real Amiga code.**

AmigaScope is a small suite of Python/shell tools that drive [Bartman's
`amiga-debug`](https://github.com/BartmanAbyss/vscode-amiga-debug) fork of **FS-UAE**
(the one with the WinUAE cycle-exact DMA recorder + CPU profiler) over its gdb stub —
**no IDE, no GUI**. They read live emulator state and turn it into pictures you can
reason about:

| Tool | What you see |
|------|--------------|
| **DMA raster map** | Every colour-clock of every scanline, colour-coded by which DMA channel owned it (bitplane / sprite / blitter / copper / …). *See* the blitter stealing the beam, or a bitplane fetch clobbering a sprite slot. |
| **CPU flame graph** | Where the 68k spends the frame's cycles — flat self-time or full hierarchical call stacks (via a DWARF-derived unwind table), rendered through Brendan Gregg's FlameGraph. |
| **Copper disassembler** | A live copper list decoded to `MOVE`/`WAIT`/`SKIP` with register labels (BPLCON0 planes, FMODE, DDF/DIW, fine-scroll, colours). |
| **Frontbuffer capture** | The displayed bitmap decoded straight from chip RAM. |

It was built to debug AGA rendering on a Sensible World of Soccer port, but the core is
generic Amiga hardware profiling.

## Why

Screenshots tell you *what* went wrong; they can't tell you *why* a sprite lost its
colour or *which* blit corrupted a scanline. AmigaScope answers the cycle-exact
questions — *is the blitter running on display lines? where does the bitplane fetch
start relative to the sprite DMA slots? what function is eating the frame budget?* —
with **measurement, not guesswork.**

![DMA raster map: bitplane fetch vs sprite slots](docs/dma_map_example.png)
![Hierarchical CPU flame graph](docs/flamegraph_example.svg)

## Requirements

- **The cycle-exact FS-UAE fork** with the `monitor profile` command:
  [`benbaker76/fs-uae` @ `remote_debugger_barto`](https://github.com/benbaker76/fs-uae/tree/remote_debugger_barto)
  (Bartman/Abyss' WinUAE cycle-exact recorder ported to FS-UAE). A stock FS-UAE has no DMA
  recorder. Point the harness at it with `FSUAE_BIN`.
- **`m68k-amiga-elf` binutils** (`objdump`) — ships with the amiga-debug extension.
- **Python 3.6+** with **Pillow** (`pip install pillow`) for the PNG raster maps.
- **FlameGraph** — bundled as a git **submodule** (`third_party/FlameGraph`, from
  [`benbaker76/FlameGraph`](https://github.com/benbaker76/FlameGraph)); no extra install if
  you clone recursively. Override the renderer with `$FLAMEGRAPH_PY` if you prefer.
- A gdb-debuggable Amiga ELF with symbols (and `.debug_frame` for hierarchical stacks) —
  set `AMIGASCOPE_ELF`.

## Install

```sh
git clone --recursive git@github.com:benbaker76/AmigaScope.git   # pulls FlameGraph too
# already cloned? grab the submodule:
git submodule update --init --recursive
pip install pillow
```

## Quick start

```sh
# 1. bring up the harness (launches FS-UAE, attaches gdb, waits for your entry trigger)
./amiga_gdb.sh up

# 2. capture + analyse a DMA profile
python3 dma_profile.py 4                    # 4 frames: contention + per-blit spans
python3 dma_profile.py map  out.prof        # -> colour-coded DMA raster-map PNGs
python3 dma_profile.py parse out.prof       # fetch-vs-sprite-slot steal report

# 3. CPU flame graph (from the same .prof)
python3 cpu_flamegraph.py top out.prof            # top functions by cycles
python3 cpu_flamegraph.py capture 8 cpu.prof      # capture WITH unwind (hierarchical)
python3 cpu_flamegraph.py svg cpu.prof flame.svg  # -> interactive flame graph

# 4. peek at the copper list / frontbuffer
python3 copper_disasm.py
python3 fb_capture.py out.png
```

## How it works

`monitor profile <N> <unwind> <out>` runs FS-UAE's cycle-exact recorder for N frames and
writes a binary blob: a `227×313` DMA-record grid per frame **plus** the CPU sample
stream. AmigaScope parses that blob (format reverse-engineered from the amiga-debug
`profile.ts`) and renders it. Hierarchical stacks come from a DWARF `.debug_frame` unwind
table that AmigaScope generates and hands back to FS-UAE.

**Gotchas worth knowing** (documented in `docs/`):
- `monitor profile` replies instantly then writes the file *asynchronously* — poll for it.
- Profile with the target **stopped and no breakpoints set** (a breakpoint hit mid-profile
  stalls the frame).
- Cycle-exact frames are slow (~15–25 s wall-clock each); heavy-DMA frames slower still.

## Configuration

Some defaults are still tuned for the original project (ELF path, `.text` base, display
window). Override via environment:

- `SWOS_ELF` / `M68K_OBJDUMP` / `FLAMEGRAPH_PY` — tool paths.
- `FSUAE_BIN` / `KICKSTART` / `DH0` — harness launch (see `amiga_gdb.sh`).

*(Generalizing these into first-class CLI flags is the top open item — see `TODO`.)*

## Credits

- **Bartman/Abyss** — the cycle-exact FS-UAE fork + amiga-debug extension this is built on.
- **Brendan Gregg** — FlameGraph.
- **FS-UAE** / **WinUAE** — the emulator and its DMA debugger.

## License

TBD (the FlameGraph scripts are CDDL; keep them in their own dir or reference upstream).
