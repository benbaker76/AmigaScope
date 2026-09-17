# gdb and harness gotchas

Condensed from the repo's human docs `docs/GDB.md` (transport, attach, watchpoints,
troubleshooting) and `docs/HARNESS.md` (driving a program from gdb). Read those for the
full walkthroughs.

## Attach and the emulator

- The FS-UAE stub listens from emulator start but only handshakes when the
  `--remote_debugger_trigger` program launches; gdb blocks on it (the daemon allows 90 s).
  A cold A1200 boot to the trigger takes about 30 s.
- One gdb connection per emulator session. Never run a throwaway daemon "to test"; if the
  socket never appears, read the daemon log before relaunching.
- Use the Linux FS-UAE from WSL (the Windows binary's port is unreachable from WSL2).
- Blank FS-UAE window with `[WARN:COPY MODE]` in the title while captures still work:
  WSLg's compositor wedged; from Windows run `wsl.exe --system sh -c "pkill -9 weston"`.
- `--automatic_input_grab=0`: moving the host mouse over the window injects Amiga mouse
  events that can wedge keyboard-driven menus; click once, then keyboard only.
- An agent must start the daemon as a background task of its tool runner, not with
  `nohup ... &` inside a one-shot shell call (it can die with that shell).

## Commands

- `cmd "continue" --timeout 2` then `waitstop N`; the `[TIMEOUT ...]` after continue is
  expected. Nothing else may talk to the daemon while `waitstop` runs.
- Interrupt with `pkill -INT -f '[m]68k-amiga-elf-gdb'` + `waitstop 8` (reports SIGTRAP).
  `raw $'\x03'` does not interrupt.
- Never `pkill -f gdb_proxy` (matches the pkill line itself); use `amiga_gdb.sh down`, a PID
  or a bracketed pattern.
- One client at a time: a second script or probe during a long drive wedges gdb.
- Before blaming WSL for "slow"/DEGRADED: `health`, `cmd "info breakpoints"` (hit count
  climbing = the target runs fine), check for another client, a `continue` with no
  breakpoint into a state that never stops, or a wrong assumed program state.

## Symbols, memory and watchpoints

- Chip-RAM sections (`.MEMF_CHIP`, placed by the hunk loader) can show their ELF address in
  gdb; read a run-time pointer variable to find the real address.
- One-element array globals (`uint16_t x[1]`): write `x[0] = v` (`set variable x = v` fails
  "Invalid cast"); `print (int)x` prints the address.
- Windows DWARF source paths under WSL: `set substitute-path C:/Projects/ /mnt/c/Projects/`.
- Watchpoints fire on value CHANGE: pre-seed a sentinel if the writer may store the same
  value. Hardware watchpoints are few on the m68k stub; a software fallback single-steps.
- Rebuild before debugging if any source is newer than the ELF (stale offsets look like
  struct bugs).

## Writing and calling (driving a program)

- The stock amiga-debug FS-UAE stub is READ-ONLY (silently ignores memory/register writes);
  the benbaker76/vscode-amiga-debug build can write. Verify with a write + read-back before
  trusting any injection. Never `set remote X-packet on`.
- Inject input at one per-frame point after the program reads its inputs: break, write the
  input variables, continue = one single-frame press. Retry until the state changes; never
  hold inputs; navigate by the program's menu structures and labels, screenshots only to
  orient.
- Inferior calls (`call func()`): clean stop required; stage strings with one bulk
  `set {char[N]}addr = "..."`; allow minutes of timeout on the emulated Amiga; check the
  return value and a sentinel field.
- Sample a running program at a per-frame breakpoint rather than delete + continue +
  interrupt. `amiga_gdb.sh up` can install its own breakpoints; a blanket `delete` removes
  them.

## Builds

- WSL + Windows-built `obj/*.d` files: `rm -f obj/*.d` (their `C:` paths break make).
- Toolchain PATH: `<amiga-debug>/bin/linux/opt/bin` (gcc/as/objdump) and
  `<amiga-debug>/bin/linux` (elf2hunk).
- `-O0` debug builds with Bartman GCC 15.1: keep `-fomit-frame-pointer`
  (`-fno-omit-frame-pointer` ICEs the compiler); `-O0` needs real `strncmp`-style helpers in
  `-nostdlib` projects.
- Native SDL builds for harness work: run headless (`SDL_VIDEODRIVER=dummy`), add a switch
  that removes wall-clock frame pacing, and log screen transitions to a flushed text file.
