# AmigaScope configuration

## AMIGASCOPE_ENV (sourced by amiga_gdb.sh)

A shell file that exports the launch settings for YOUR target. The script's built-in
defaults are the author's SWOS setup and absolute Windows paths; override every one that
applies.

| Variable | Default / meaning |
|---|---|
| `FSUAE_DIR` | Directory of the FS-UAE build (the script `cd`s here and sets `LD_LIBRARY_PATH=.`). Default: the bartman amiga-debug 1.8.2 extension's `bin/linux/fs-uae`. |
| `FSUAE_BIN` | FS-UAE executable (default `$FSUAE_DIR/fs-uae`). Point it at the cycle-exact build for profiling. |
| `KICKSTART` | Kickstart ROM file (default a 3.1 A1200 ROM path). |
| `DH0`, `DH1` | Host directories mounted as hard drives 0 and 1 (DH1 holds the program). |
| `TRIGGER` | FS-UAE `--remote_debugger_trigger`: the program name (e.g. `:MYPROG`) whose start opens the gdb port and pauses the target. |
| `ENTRY_PC` | Expected PC at the trigger (documentation / sanity). |
| `PORT` | gdb remote port (2345). |
| `ATTACH_RETRIES` | Full restart attempts in `up` (4). |
| `BOOT_TIMEOUT`, `SETTLE` | Boot wait and post-trigger settle seconds (60, 4). |
| `FSUAE_LOG` | FS-UAE stdout/stderr (`/tmp/fs-uae.log`). |
| `FSUAE_NATIVE_LOG` | FS-UAE's own log (`~/FS-UAE/Cache/Logs/fs-uae.log.txt`), deleted on `down`. |
| `DAEMON_LOG` | gdb_proxy daemon log (`/tmp/swos_gdb_daemon.log`) - look here first on a failed `up`. |
| `SOCK` | Daemon socket (`/tmp/swos_gdb.sock`; gdb_proxy.py hard-codes the same path). |
| `GDB_PROXY` | Path to gdb_proxy.py (repo copy). |
| `FORCE_RESTART` | `1` = behave like `up --fresh`. |

Minimal example:

```sh
# myprog.env
export AMIGASCOPE_ELF=/abs/path/build/myprog.elf
export FSUAE_BIN=/abs/path/fs-uae-cycle-exact/fs-uae
export FSUAE_DIR="$(dirname "$FSUAE_BIN")"
export KICKSTART=/abs/path/kick31_a1200.rom
export DH0=/abs/path/wb31-system
export DH1=/abs/path/build/dh1
export TRIGGER=:myprog
```

```sh
AMIGASCOPE_ENV=$PWD/myprog.env ./amiga_gdb.sh up
```

## Other environment variables

| Variable | Used by | Meaning |
|---|---|---|
| `AMIGASCOPE_ELF` | gdb_proxy.py (amiga), cpu_flamegraph.py, size_profile.py, MCP | ELF with symbols (and `.debug_frame` for call stacks). Falls back to `SWOS_ELF` in cpu_flamegraph.py. |
| `AMIGASCOPE_BIN` | gdb_proxy.py (sdl) | Native SDL binary. |
| `M68K_OBJDUMP` | cpu_flamegraph.py, size_profile.py | objdump for symbols (default `m68k-amiga-elf-objdump` on PATH). |
| `FLAMEGRAPH_PY` | cpu_flamegraph.py, size_profile.py | Renderer (default `third_party/FlameGraph/flamegraph.py`; `git submodule update --init`). |
| `AMIGASCOPE_TMP` | amigascope_mcp.py | Temp dir for captures (default `/tmp`). |
| `CLAUDE_JOB_DIR` | dma_profile.py, copper_disasm.py, fb_capture.py | Temp dir override (uses `<dir>/tmp` if present). |

The gdb binary is hard-coded in gdb_proxy.py (`GDB_BIN_AMIGA`, the extension's
`bin/linux/opt/bin/m68k-amiga-elf-gdb`) - edit it if your extension version differs.

## Two FS-UAE builds

| | stock FS-UAE (amiga-debug extension) | cycle-exact build with the DMA recorder |
|---|---|---|
| Debugging via gdb | yes | yes |
| `monitor profile` (DMA + CPU profile) | no | yes |
| `monitor screenshot` of the live (not re-composited) frame | no | yes |

Use the cycle-exact build (benbaker76/vscode-amiga-debug's bundled FS-UAE, or
benbaker76/fs-uae `remote_debugger_barto`) whenever you need profiling or real-time
artifacts.
