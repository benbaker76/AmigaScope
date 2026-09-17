# gdb workflow (Amiga under FS-UAE, and native SDL builds)

How to build, attach and debug with AmigaScope's gdb transport from WSL2 (or Linux). Both
targets use the same `gdb_proxy.py` daemon, so the command interface is identical: start
the daemon once, then send one gdb command per call with `gdb_proxy.py cmd "<command>"`.

- **Amiga** — `m68k-amiga-elf-gdb` remote-debugs the program inside FS-UAE through the
  emulator's gdb stub.
- **SDL** — host `/usr/bin/gdb` runs a native Linux build of the same program.

For the tools built on top (DMA profiler, copper disassembler, frontbuffer capture) see
[TOOLKIT.md](TOOLKIT.md); for driving a program's UI and state from gdb see
[HARNESS.md](HARNESS.md).

---

## Prerequisites

- **WSL2 with WSLg** (`echo $DISPLAY` prints something); FS-UAE's window renders through
  WSLg with no X server setup. Plain Linux works the same way.
- **The amiga-debug VS Code extension** — use the
  [`benbaker76/vscode-amiga-debug`](https://github.com/benbaker76/vscode-amiga-debug) build
  (its FS-UAE has the write-capable gdb stub and the cycle-exact DMA recorder). It bundles
  Linux binaries you can run from WSL:
  - FS-UAE: `<extension>/bin/linux/fs-uae/fs-uae` (run with `LD_LIBRARY_PATH=.` from that
    directory)
  - gdb: `<extension>/bin/linux/opt/bin/m68k-amiga-elf-gdb`
  - toolchain: `<extension>/bin/linux/opt/bin` (gcc, as, objdump) and `<extension>/bin/linux`
    (`elf2hunk`)
  - a Workbench boot drive: `<extension>/bin/dh0`
- A Kickstart ROM and your program built as an ELF with symbols (plus the hunk executable
  FS-UAE runs).

Quick check that the Linux FS-UAE runs under WSLg:

```sh
cd <extension>/bin/linux/fs-uae && LD_LIBRARY_PATH=. ./fs-uae --help | head -3
```

## Building from WSL

The toolchain is not on PATH by default:

```sh
TCDIR=<extension>/bin/linux
export PATH="$TCDIR/opt/bin:$TCDIR:$PATH"   # opt/bin = gcc/as/objdump, $TCDIR = elf2hunk
```

- **Dependency files from a Windows build break GNU make under WSL** (`obj/X.d:1: *** target
  pattern contains no '%'`): the `.d` files embed `C:/...` paths whose colon looks like a
  rule separator. Delete them (`rm -f obj/*.d`); the `.o` files stay, make falls back to
  timestamps and regenerates the `.d` files with this host's paths. Don't `sed` them - the
  assembler `.d` files use backslashes that collide with make's line continuation.
- gdb loads the **ELF** for symbols; FS-UAE runs the **hunk** file made from it by
  `elf2hunk`. If long branches crash only in the hunk file, see `fix_hunk_relocs.py`.
- **Debug builds:** `-O0` gives precise line breakpoints and live locals (struct layout is
  unchanged). With Bartman's GCC 15.1, keep `-fomit-frame-pointer` even at `-O0`:
  `-fno-omit-frame-pointer` crashes the compiler (ICE in `dwarf2out_frame_debug_adjust_cfa`),
  and `-g` still emits the CFI gdb needs to unwind. `-O0` also emits real calls to helpers
  such as `strncmp` that `-O2`/`-Ofast` inlined, so a `-nostdlib` project must provide them.

---

## Attach: the one-command path

```sh
AMIGASCOPE_ENV=/abs/path/myprog.env ./amiga_gdb.sh up    # prints OK or FAIL
python3 gdb_proxy.py health                              # OK stopped PC=0x...
./amiga_gdb.sh status                                    # HEALTHY / DEGRADED / DOWN
./amiga_gdb.sh down                                      # tear everything down
```

`up` reuses a healthy live session, otherwise it tears down stale processes, launches
FS-UAE directly (never through a pipe - a `| grep` filter caused SIGPIPE early exits),
starts the daemon immediately, health-checks the attach (stopped at SIGTRAP with a real
PC) and retries with a full restart if the attach is degraded. The daemon logs its own
verdict to its log file (`[daemon] attach health: OK|DEGRADED (...)`).

**Why gdb waits up to 90 s:** the FS-UAE stub opens its listening port when the emulator
starts but only accepts and handshakes when the `--remote_debugger_trigger` program is
launched, which can be tens of seconds into a cold boot. gdb connects early and blocks on
the handshake; the daemon sets `tcp connect-timeout` and `remotetimeout` to 90 s so a slow
boot doesn't make gdb give up first. A cold A1200 boot to the trigger takes about 30 s;
only a savestate at the entry point would skip that.

### The manual path (what `up` does)

FS-UAE must be listening before the daemon starts:

```sh
cd <extension>/bin/linux/fs-uae && \
  setsid env LD_LIBRARY_PATH=. nohup ./fs-uae \
    --amiga_model=a1200 --automatic_input_grab=0 \
    --hard_drive_0=<extension>/bin/dh0 --hard_drive_1=/abs/path/to/program/dir \
    --remote_debugger=20 --remote_debugger_port=2345 \
    --remote_debugger_trigger=:MYPROG \
    --ntsc_mode=0 --kickstart_file=/abs/path/kick31_a1200.rom \
    --chip_memory=2048 --fast_memory=8192 \
    > /tmp/fs-uae.log 2>&1 < /dev/null &
disown
ss -ltn | grep :2345                       # LISTEN 127.0.0.1:2345

setsid nohup python3 gdb_proxy.py daemon --mode amiga --host 127.0.0.1 \
    > /tmp/amigascope_daemon.log 2>&1 < /dev/null &
disown
python3 gdb_proxy.py ping                  # pong
```

- `--remote_debugger=20 --remote_debugger_port=2345` enables the stub on
  `127.0.0.1:2345`; `--remote_debugger_trigger=:MYPROG` pauses the target at the entry of
  the program named `MYPROG` so breakpoints can be set before it runs.
- `setsid nohup ... & disown` with redirected stdio keeps FS-UAE and the daemon alive after
  the launching shell exits. (An AI agent should start the daemon as a background task of
  its tool runner instead: a `nohup ... &` inside a one-shot shell call can die with that
  shell.)
- Use the **Linux** FS-UAE from WSL. The Windows binary binds to Windows loopback, which
  WSL2 cannot reach.

### The one-shot port (read this)

The stub accepts **one gdb connection per emulator session**. Every connect/disconnect
burns it:

1. Start FS-UAE once, start the daemon once, and keep the daemon resident.
2. Never run a throwaway foreground daemon "just to test" - it connects, disconnects and
   kills the port for the real one.
3. If the socket never appears, read the daemon log (or run the daemon in the foreground)
   before relaunching - each blind retry may burn the port again.
4. A burned port (daemon log shows an attach failure, or `info program` says "not being
   run") has exactly one recovery: restart FS-UAE and the daemon (`amiga_gdb.sh up --fresh`).

Common attach failures:

| Symptom | Cause | Fix |
|---|---|---|
| `Connection refused` | FS-UAE not running, or its port already used by an earlier gdb | restart FS-UAE (one-shot port) |
| DEGRADED, no readable PC | the ELF path is wrong - gdb starts happily with no executable | fix `AMIGASCOPE_ELF`; the daemon now exits with `FATAL: Amiga ELF not found` |
| `up` retries until FAIL, FS-UAE stays up | the trigger program never started (wrong `TRIGGER` name, program not on the drive, boot error) | watch the FS-UAE window; check `TRIGGER`, `DH1` and `$FSUAE_LOG`; `grep GDBSERVER ~/FS-UAE/Cache/Logs/fs-uae.log.txt` shows the stub's state |
| daemon hangs on a simple `print` after an inferior `call` faulted | gdb left in a bad state | restart the daemon AND FS-UAE |

---

## Issuing commands

```sh
python3 gdb_proxy.py cmd "info program"          # where stopped
python3 gdb_proxy.py cmd "bt"
python3 gdb_proxy.py cmd "info registers"
python3 gdb_proxy.py cmd "print/x someVar"
python3 gdb_proxy.py cmd "x/16xw 0xADDR"
python3 gdb_proxy.py cmd "break someFunc"         # or file.c:123, or *0xADDR
python3 gdb_proxy.py cmd "watch *(unsigned char *)0xADDR"
python3 gdb_proxy.py cmd "continue" --timeout 2   # returns ~2 s later, target running
python3 gdb_proxy.py waitstop 300                  # blocks until a stop
```

- A `cmd "continue"` never gets a prompt back while the target runs, so it returns a
  `[TIMEOUT ...]` marker after its timeout. That is expected: pass a short `--timeout`,
  then `waitstop`.
- `waitstop` returns the moment gdb prints a stop (`Breakpoint N,`, `Watchpoint N`,
  `received signal`), or immediately if the target is already stopped. It holds the
  single-socket daemon while it waits: fire no other commands in parallel.
- While the target runs, read probes (`print`, `x`, `info`, `bt`, `frame`, `list`,
  `display`) are refused with `[BUSY: ...]` instead of queueing inside gdb and wedging the
  socket. `health` reports `DEGRADED target running (busy ...)` without probing - normal,
  not a dead session.
- `gdb_proxy.py watch` prints one line per running->stopped transition (with function and
  `file:line`), for hands-free notification.

### Interrupting a running target

`gdb_proxy.py raw $'\x03'` prints `[sent]` but does **not** stop the target: the byte never
reaches a controlling terminal. Send SIGINT to gdb instead, then wait:

```sh
pkill -INT -f '[m]68k-amiga-elf-gdb'     # the [m] stops pkill matching its own command line
python3 gdb_proxy.py waitstop 8
```

The stop reports as `SIGTRAP` (not SIGINT) wherever the target was - typically its idle or
vsync-wait loop.

### Reading state after acting in the emulator by hand

```sh
python3 gdb_proxy.py cmd "continue" --timeout 2    # let it run, do the thing in the window
pkill -INT -f '[m]68k-amiga-elf-gdb'; python3 gdb_proxy.py waitstop 8
python3 gdb_proxy.py cmd "p someGlobal.field"
python3 gdb_proxy.py cmd "p ((SomeType *)0xADDR)->field"   # when the symbol's type is narrower
python3 gdb_proxy.py cmd "continue" --timeout 2
```

- Prefer symbolic access; a `set $v = (T *)&sym` convenience cast sometimes fails with
  "not a structure pointer" - cast the literal address inline instead.
- **Mouse desync with `--automatic_input_grab=0`:** moving the host mouse over or out of the
  FS-UAE window injects Amiga mouse events, which can wedge keyboard/joystick-driven menus.
  Click once into the window, then use only the keyboard. If it is already wedged, restart.

---

## Address and symbol quirks (Amiga)

- With Bartman's toolchain, sections placed in chip RAM (`.MEMF_CHIP` sections, allocated
  by the hunk loader at run time) can show their **ELF address** in gdb (`info address sym`,
  `print &sym`) instead of where the data really is. Read a pointer variable the program
  sets at run time (or evaluate inside a function that took the address) to get the real
  chip RAM address.
- Globals declared as one-element arrays (`uint16_t flag[1]`, common in code ported from
  assembler) are not scalars to gdb: `set variable flag = 1` fails with "Invalid cast"
  (write `flag[0] = 1`), and `print (int)flag` prints the ADDRESS (read `flag[0]`).
- Windows source paths in the DWARF info (`C:/Projects/...`) make `list` fail under WSL:
  `set substitute-path C:/Projects/ /mnt/c/Projects/`.

## Watchpoints

- `watch *(unsigned char *)0xADDR` fires on a **value change**, not on every write. If the
  writer may store the value that is already there, pre-seed a sentinel first
  (`set *(unsigned char *)0xADDR = 0xff`).
- `rwatch` = reads, `awatch` = reads or writes (slower).
- Hardware watchpoints are scarce on the m68k stub (a handful at once). If gdb falls back to
  a software watchpoint it single-steps the target: orders of magnitude slower.

## Shutting down

The port is one-shot, so don't disconnect gdb mid-session unless you also restart FS-UAE.
Clean teardown: `./amiga_gdb.sh down`. Never `pkill -f gdb_proxy` (the pattern matches the
pkill command itself and kills your shell); use `amiga_gdb.sh down`, a PID, or a bracketed
pattern such as `[g]db_proxy`.

---

## Troubleshooting

- **FS-UAE window blank, title shows `[WARN:COPY MODE]`,** while `monitor screenshot` and
  `fb_capture.py` still return correct frames: WSLg's weston compositor has wedged (usually
  after many FS-UAE boot/kill cycles in one session). From Windows PowerShell:
  `wsl.exe --system sh -c "pkill -9 weston"`; WSLg respawns it and the next FS-UAE launch
  renders normally. Launching once and leaving FS-UAE up avoids it.
- **`call func()` hangs:** inferior calls need a clean stop (not inside an interrupt or a
  signal frame), a write-capable stub (see HARNESS.md) and a long timeout on the emulated
  Amiga. Otherwise restart the daemon and FS-UAE.
- **"Slow" or DEGRADED daemon:** before blaming WSL or gdb, check for a second client
  talking to the daemon, rapid daemon relaunches (stale sockets, half-dead gdb), a
  `continue` with no breakpoint into a state that never stops, or a target that is not in
  the state you assumed. `gdb_proxy.py health` and `cmd "info breakpoints"` (is the hit
  count climbing?) answer this in seconds.
- **Debugging against a stale binary** gives phantom struct mismatches: rebuild when any
  source file is newer than the ELF (`find src -newer build/prog.elf | head`).

---

## SDL (native) workflow

```sh
setsid nohup python3 gdb_proxy.py daemon --mode sdl --bin /abs/path/bin/myprog \
    > /tmp/amigascope_daemon.log 2>&1 < /dev/null &
disown
python3 gdb_proxy.py ping
python3 gdb_proxy.py cmd "set environment SDL_VIDEODRIVER dummy"   # optional: headless
python3 gdb_proxy.py cmd "start"      # halts at main() so breakpoints can be set
python3 gdb_proxy.py cmd "continue" --timeout 2; python3 gdb_proxy.py waitstop 60
```

- `--bin` is resolved to an absolute path and gdb runs with the binary's directory as cwd
  (so relative data paths work). A relative path used to make `run` silently do nothing.
- Running the inferior headless (`SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy`) avoids
  WSLg window churn over long sessions; a program that renders into its own buffer can
  still be captured from memory.

| Aspect | Amiga | SDL |
|---|---|---|
| gdb | m68k-amiga-elf-gdb (extension) | host gdb |
| Start | FS-UAE runs the program; gdb attaches at the trigger | gdb launches it (`start`/`run`) |
| Reconnect after quitting gdb | restart FS-UAE (one-shot port) | just restart the daemon |
| Hardware watchpoints | scarce | DR0-DR3 per process |
| Chip-RAM symbol addresses | may show ELF address, not run-time | ELF address == run-time |

## Files

```text
/tmp/swos_gdb.sock          daemon socket (name kept for compatibility)
$DAEMON_LOG                 daemon stdio (default /tmp/swos_gdb_daemon.log)
$FSUAE_LOG                  FS-UAE stdout/stderr (default /tmp/fs-uae.log)
~/FS-UAE/Cache/Logs/fs-uae.log.txt   FS-UAE's own log (GDBSERVER lines)
```
