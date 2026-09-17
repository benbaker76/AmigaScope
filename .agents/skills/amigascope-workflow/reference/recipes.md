# AmigaScope recipes

`gp` below is `python3 gdb_proxy.py`.

## Which tool answers which question

| Question | Tool |
|---|---|
| What value does X have right now? | `gp cmd "print X"` / `x/...` |
| Who writes X (and when)? | `gp cmd "watch X"`, `gp cmd continue`, `gp waitstop 120`, `gp cmd bt` |
| Is my display set up right (planes, DIW/DDF, FMODE, colours)? | `copper_disasm.py ADDR` on the list in COP1LC |
| Is the wrong pixel IN my buffer? | `fb_capture.py` (halted buffer decode) |
| It only glitches while running / vanishes when halted | cycle-exact `dma_profile.py N`, `blits`, `map` |
| Is the blitter running on display lines? | `dma_profile.py parse` -> `CONTENTION`; `blits` -> which blit overruns |
| Why is a hardware sprite missing on AGA? | `dma_profile.py parse` -> `STEAL` (fetch start vs sprite DMA slots) |
| Where do the CPU cycles go? | `cpu_flamegraph.py capture 4 cpu.prof` + `top` / `svg` |
| Why is my executable so big? | `size_profile.py report` (static) |
| Hunk exe crashes on long branches that work in the ELF | `analyze_pc32.py`, `fix_hunk_relocs.py` |

## Start a session

```sh
AMIGASCOPE_ENV=/abs/myprog.env ./amiga_gdb.sh up     # -> OK
gp() { python3 gdb_proxy.py "$@"; }
gp health                                             # OK stopped PC=0x...
```

If `up` prints FAIL: read `$DAEMON_LOG` (ELF missing -> `FATAL: Amiga ELF not found`),
then `$FSUAE_LOG` (ROM/drive paths, crash), and confirm `TRIGGER` matches the program name
FS-UAE starts.

## Break at a function and inspect

```sh
gp cmd "break UpdatePlayer"
gp cmd "continue"; gp waitstop 60
gp cmd "info registers"
gp cmd "x/8i \$pc"
gp cmd "print *player"
gp cmd "finish"          # run until return (may time out on long calls -> waitstop)
```

## Catch a memory scribble

```sh
gp cmd "watch -l g_state.lives"     # -l watches the location, survives scope changes
gp cmd "continue"; gp waitstop 300
gp cmd "backtrace"; gp cmd "x/6i \$pc-12"
```

## Step assembler code

```sh
gp cmd "break *0x21a004"
gp cmd "continue"; gp waitstop 30
gp cmd "stepi"; gp cmd "info registers d0 d1 a0 a6"
gp cmd "x/4i \$pc"
```

## Read/write chip RAM and structures

```sh
gp cmd "x/64xh 0x1218f0"                    # copper list as 16-bit words
gp cmd "set {short}0x1218f6 = 0x0f00"       # patch a colour value in the list
gp cmd "dump binary memory /tmp/plane0.bin 0x40000 0x40000+40*256"
```

## Profile a frame (cycle-exact build)

```sh
kill -INT "$(pgrep -f m68k-amiga-elf-gdb | head -1)"; gp health   # stopped
gp cmd "delete"                                                    # NO breakpoints
python3 dma_profile.py profile 2 /tmp/f.prof                       # wait: ~20 s/frame
python3 dma_profile.py parse /tmp/f.prof
python3 dma_profile.py blits /tmp/f.prof
python3 dma_profile.py map /tmp/f.prof /tmp/f                      # PNGs
```

Success criterion for a blitter-overrun fix: `dma_profile.py` shows no blitter cell on
display lines. Profile the same program state before and after, then `compare`.

## Real-time artifact triage (from docs/TOOLKIT.md)

1. `fb_capture.py` clean -> not a draw bug in the buffer.
2. Stock (re-composited) screenshot clean -> the artifact only exists while running.
3. Live capture on the cycle-exact build shows it -> real-time.
4. `dma_profile.py` -> blitter on display lines / DMA steal: the mechanism.
5. `dma_profile.py blits` -> the specific blit(s) overrunning vertical blank.
6. `copper_disasm.py` -> rule out display configuration.

## SDL build

```sh
AMIGASCOPE_BIN=/abs/bin/MyProg setsid nohup python3 gdb_proxy.py daemon --mode sdl \
    > /tmp/sdl_daemon.log 2>&1 < /dev/null &
gp cmd "break main"; gp cmd "run" --timeout 5; gp waitstop 60
```

The same `cmd`/`waitstop`/`watch` recipes then apply to the native process. Profiling
tools are Amiga-only.
