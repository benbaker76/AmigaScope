# Driving a program from gdb (test harness patterns)

AmigaScope's gdb transport can do more than inspect: an assistant can **drive** a program -
navigate menus, press buttons, load data, capture the screen - by writing its input state
and calling its own functions through gdb, on the Amiga (FS-UAE) and on a native SDL build
alike. This document collects the patterns and the pitfalls. The reference implementation
is the harness of the Sensible World of Soccer port that AmigaScope grew out of
(`harness_lib.py`, `swos_plugin.py`, `swos_harness.py`, kept in that project, not here).

Transport details (daemon, attach, `cmd`/`waitstop`, interrupts) are in [GDB.md](GDB.md).

---

## Architecture: keep the game-specific part in one plugin

```text
gdb_proxy.py      transport: one persistent gdb session; cmd / waitstop / health / watch;
                  --mode amiga (FS-UAE remote) or --mode sdl (native). No program knowledge.
harness_lib.py    generic primitives: read/write variables, breakpoints, input injection
                  (break + set + continue), framebuffer capture.
<prog>_plugin.py  everything program-specific: the input injection point and encoding,
                  menu/state accessors, framebuffer geometry, save/load entry points.
<prog>_harness.py thin CLI over the plugin (where / nav / fire / select / load / cap ...).
```

To drive another program, keep the first two layers and write a new plugin.

## Prerequisite: a write-capable gdb stub

Input injection, inferior calls and string staging all need gdb to **write** target memory
and registers. Native gdb always can. **The stock amiga-debug FS-UAE stub is read-only**: it
answers reads and breakpoints but silently ignores memory/register writes (`M`, `G`, `P`
packets), so `set var` never sticks and every injection does nothing. The
[`benbaker76/vscode-amiga-debug`](https://github.com/benbaker76/vscode-amiga-debug) build
contains the patched stub. The two extensions install into the same directory name and
look identical; the only reliable test is behavioural:

```sh
python3 gdb_proxy.py cmd "set {int}0xADDR = 0x12345678"
python3 gdb_proxy.py cmd "x/1xw 0xADDR"          # must read back 0x12345678
```

What the patch does (in FS-UAE's `barto_gdbserver.cpp`), for anyone rebuilding it:

- Implements `M addr,len:hex` (memory write), `P n=val` (one register) and `G` (all
  registers). `X` (binary write) is deliberately not implemented; gdb probes it, finds it
  unsupported and falls back to `M`. Never `set remote X-packet on` - gdb then hangs.
- **Inferior calls** (`call func()`): after setting PC the emulator must rebuild the CPU
  prefetch (`fill_prefetch()`), because the cycle-exact 68020 executes from the prefetch
  pipeline, not directly from PC; without it the call ran the stale prefetched opcode and
  faulted. FS-UAE's normal breakpoint scan then catches gdb's return breakpoint by itself -
  an earlier version that patched ILLEGAL opcodes into memory caused intermittent SIGILL on
  repeated calls and was removed.

## Injecting input

- Pick **one injection point** in the program's input path: a line that runs every frame
  after the program has read the hardware into its input variables and before it acts on
  them. Break there, write the input variables, continue. Because the program re-reads
  idle hardware on the next frame, one write is one single-frame key press - no release
  needed.
- If menus and game logic are shared code between the Amiga and SDL builds, the same
  injection works on both targets.
- **Retry until the program reacts.** Fire a menu entry, then check that the state changed
  (the active screen or the visible list); re-fire if not. Don't assume one press
  dispatched.
- **Hold nothing.** A held button re-triggers nested modal screens on the next frame.
- **Navigate by state, not by pixels.** Read the program's own menu structures (current
  screen init function, entry list, selected entry, entry labels) - fast and token-light.
  Use screenshots only to orient, and navigate dynamic lists by their displayed labels so
  data changes that renumber entries don't break the drive.
- One-element array globals (`uint16_t fire[1]`) must be written as `fire[0] = 1` - a
  `set variable fire = 1` fails with "Invalid cast" and a wrapper that ignores the error
  silently drops every press.

## Calling the program's own functions

- Load or save data by calling the program's own routine (`call LoadThing(...)`) instead of
  driving its file requester.
- **Stage strings in one bulk write** (`set {char[32]}scratch = "NAME.DAT"`) into a scratch
  global; per-byte writes were unreliable on the Amiga stub.
- **Use long timeouts on the Amiga.** A call that takes seconds natively can take minutes
  on the emulated 68020 (JSON parsing took 1-3 minutes); give `cmd` a timeout of several
  minutes - the daemon returns as soon as the call completes.
- Check the return value AND a sentinel field afterwards: a failed load that silently
  leaves previous in-memory state looks like success.
- A call needs a clean stop (at a breakpoint, not inside an interrupt).

## Daemon discipline

- Launch the daemon once per session and leave it alone; rapid kill/relaunch cycles (stale
  sockets, half-dead gdb) are most of what looks like "flakiness".
- **One client at a time.** The daemon multiplexes a single gdb stdin/stdout; two scripts or
  a stray probe issued while a long drive runs interleave their traffic and wedge gdb.
- To sample while the program runs, keep a breakpoint at a per-frame function and read at
  that clean stop. `delete` all breakpoints + `continue` + interrupt gives racy stops, and a
  `continue` into a state that never stops burns the whole timeout.
- On the Amiga, `amiga_gdb.sh up` may install breakpoints of its own (e.g. a skip for a slow
  intro); a blanket `delete` removes them too.
- Rebuild before debugging: a stale binary produces phantom struct-offset mismatches.
- When something looks slow or wedged, get facts first: `gdb_proxy.py health`,
  `cmd "info breakpoints"` (is the hit count climbing? then the program is running fine and
  only the stop reporting is off), and whether another client is live. "WSL is slow" has
  so far never been the real cause.

## Making native builds harness-friendly

- **Run headless** (`SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy`, set with
  `cmd "set environment ..."` before `run`): no WSLg window churn, and a program that
  renders into its own chunky buffer can still be captured from memory.
- **A turbo switch:** when the program paces frames to wall-clock time (vsync delays, timer
  threads), gdb-driven frame stepping balloons because those waits stretch under the
  debugger. An environment variable that removes the pacing makes each `continue` bound by
  CPU work only.
- **A plain-text trace log** the program flushes line by line (screen activations, entry
  dispatches) shows where a drive stopped even while the inferior is hung, without touching
  gdb.
- Re-boot the inferior inside the same daemon with `kill` then `run`; breakpoints and
  `set environment` persist.

## Screen capture

- **SDL:** read the program's chunky framebuffer and palette straight from memory.
- **Amiga:** decode the interleaved bitplanes (planar -> chunky) with the palette the
  program pushes into the copper list; `fb_capture.py` is an example with a hard-coded
  layout to adapt. This shows the buffer contents, not the live beam - see
  [TOOLKIT.md](TOOLKIT.md) for real-time artifacts.
