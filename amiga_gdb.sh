#!/usr/bin/env bash
#
# amiga_gdb.sh — reliable launch + attach orchestration for the SWOS Amiga
# build under FS-UAE's remote-debugger stub.
#
# The FS-UAE remote_debugger port is ONE-SHOT per emulator session: every
# gdb connect->disconnect burns it, and a connect issued before the SWOS2
# entry trigger has settled yields a DEGRADED attach (gdb says "not being
# run" / "No registers"; only ELF-static reads work). That made the manual
# launch+attach dance flaky. This script makes it deterministic by:
#
#   1. tearing down any stale FS-UAE / gdb / daemon (clean slate),
#   2. launching FS-UAE,
#   3. waiting for the "Breakpoint 20 triggered" SWOS2-entry line in the log
#      plus a short settle,
#   4. starting the gdb_proxy daemon,
#   5. HEALTH-CHECKING the attach (target stopped at SIGTRAP, PC readable),
#   6. and if the attach is degraded, doing a FULL restart and retrying
#      (up to ATTACH_RETRIES times) — the only real recovery for the
#      one-shot port.
#
# Usage:
#   amiga_gdb.sh up          # REUSE a live healthy session if present (instant),
#                            #   else clean + launch + attach, retry until healthy
#   amiga_gdb.sh up --fresh  # force a clean restart even if a session is live
#   amiga_gdb.sh down        # tear everything down
#   amiga_gdb.sh status      # health verdict of the current attach
#   amiga_gdb.sh restart     # down + fresh up
#
# Speed notes: `up` skips the ~30s Amiga cold boot when a daemon is already
# attached and healthy (the one-shot port stays valid for that daemon's life,
# so keep it RESIDENT across debugging instead of tearing down each time). The
# launch disables FS-UAE clipboard sharing (--clipboard_sharing=0) to dodge the
# WSLg GLib clipboard crash, and bails fast if FS-UAE dies before the trigger.
#
# After `up` returns SUCCESS, drive gdb with:
#   python3 <DIR>/gdb_proxy.py cmd "info registers"   (etc.)
#
# Config via env (sane defaults below).

set -u

# ---- config ---------------------------------------------------------------
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GDB_PROXY="${GDB_PROXY:-$SELF_DIR/gdb_proxy.py}"

# Per-project config. Point AMIGASCOPE_ENV at a file that exports the vars below for
# your target (DH0/DH1 hard drives, KICKSTART, the entry-symbol TRIGGER, ENTRY_PC,
# FSUAE_BIN, ...). Sourced here so the values below act only as reference defaults.
[ -n "${AMIGASCOPE_ENV:-}" ] && [ -f "$AMIGASCOPE_ENV" ] && . "$AMIGASCOPE_ENV"

# --- reference defaults (the SWOS bring-up project); override via AMIGASCOPE_ENV ---
FSUAE_DIR="${FSUAE_DIR:-/mnt/c/Users/headk/.vscode/extensions/bartmanabyss.amiga-debug-1.8.2/bin/linux/fs-uae}"
FSUAE_BIN="${FSUAE_BIN:-$FSUAE_DIR/fs-uae}"
DH0="${DH0:-/mnt/c/Users/headk/.vscode/extensions/bartmanabyss.amiga-debug-1.8.2/bin/dh0}"
DH1="${DH1:-/mnt/c/Projects/AI/SWOS/SWOS_C/uae/dh0/data}"
KICKSTART="${KICKSTART:-/mnt/c/Projects/Amiga/Kickstarts/KICK31_A1200.rom}"
PORT="${PORT:-2345}"
TRIGGER="${TRIGGER:-:SWOS2}"
ENTRY_PC="${ENTRY_PC:-0x219b10}"     # SWOS2 _start/main; PC here == healthy stop

FSUAE_LOG="${FSUAE_LOG:-/tmp/fs-uae.log}"
# FS-UAE's OWN logfile (separate from the stderr we capture in FSUAE_LOG). The
# remote_debugger_barto build writes its GDBSERVER output here, including the
# "Waiting for connection..." line emitted when the :SWOS2 trigger fires and the
# stub pauses ready for gdb. (The older build printed "Breakpoint 20 triggered"
# to stderr instead.) Default is FS-UAE's standard cache-log path.
FSUAE_NATIVE_LOG="${FSUAE_NATIVE_LOG:-$HOME/FS-UAE/Cache/Logs/fs-uae.log.txt}"
DAEMON_LOG="${DAEMON_LOG:-/tmp/swos_gdb_daemon.log}"
SOCK="${SOCK:-/tmp/swos_gdb.sock}"

ATTACH_RETRIES="${ATTACH_RETRIES:-4}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-60}"   # max secs to wait for the entry trigger
SETTLE="${SETTLE:-4}"                # secs after trigger before attaching (the one-shot
                                     # port needs a moment to settle; too low -> DEGRADED
                                     # attach -> a full-restart retry, which is slower)

log() { echo "[amiga_gdb] $*" >&2; }

# ---- teardown -------------------------------------------------------------
# NOTE: this is a SCRIPT FILE, so its own argv is "bash amiga_gdb.sh" — it does
# NOT contain the FS-UAE arg strings, so pkill -f patterns here can't self-match
# (the inline-command self-kill trap doesn't apply inside a script).
down() {
    pkill -9 -f 'm68k-amiga-elf-gdb' 2>/dev/null
    pkill -9 -f 'gdb_proxy.py daemon' 2>/dev/null
    pkill -9 -f "fs-uae .*remote_debugger_port=${PORT}" 2>/dev/null
    # Also clear FS-UAE's own logfile so wait_for_trigger can't false-positive on
    # a stale "Waiting for connection..." from a previous session.
    rm -f "$SOCK" "$FSUAE_NATIVE_LOG" 2>/dev/null
    # give the OS a moment to release the port / pids
    for _ in 1 2 3 4 5; do
        ss -ltn 2>/dev/null | grep -q ":${PORT} " || break
        sleep 0.5
    done
}

# ---- launch FS-UAE (detached) --------------------------------------------
launch_fsuae() {
    # Launch FS-UAE DIRECTLY — exactly like the VSCode bartman extension spawns
    # it (which is reliable). Do NOT pipe it through `grep` to filter spam: the
    # spam-fixed FS-UAE rebuild no longer emits the g_async_queue / SKIPPED FRAME
    # flood, so the filter is dead weight — and piping a GUI emulator through a
    # `bash -c '... | grep'` wrapper is the cause of the intermittent "FS-UAE
    # exited before the trigger (crash?)" launches (grep exits / the pipe breaks
    # -> FS-UAE gets SIGPIPE on its next write -> dies). Output goes straight to
    # $FSUAE_LOG (small now). --clipboard_sharing=0 drops the WSLg clipboard-sync
    # path (unrelated to spam, but harmless to keep off). pgrep -x fs-uae and the
    # port-pattern pkill in down() match the direct process.
    ( cd "$FSUAE_DIR" && \
      setsid env LD_LIBRARY_PATH=. nohup \
        "$FSUAE_BIN" \
        --amiga_model=a1200 --automatic_input_grab=0 \
        --hard_drive_0="$DH0" --hard_drive_1="$DH1" \
        --remote_debugger=20 --remote_debugger_port="$PORT" \
        --remote_debugger_trigger="$TRIGGER" \
        --ntsc_mode=0 --kickstart_file="$KICKSTART" \
        --chip_memory=2048 --fast_memory=8192 \
        --clipboard_sharing=0 \
        > "$FSUAE_LOG" 2>&1 < /dev/null & disown )
}

# ---- wait for the SWOS2 entry trigger ------------------------------------
wait_for_trigger() {
    local end=$(( SECONDS + BOOT_TIMEOUT ))
    while (( SECONDS < end )); do
        # READINESS = the gdb stub is LISTENING on port 2345. The :SWOS2 trigger
        # opens that port and pauses the target at entry, waiting for gdb. The
        # LISTEN socket is the PRIMARY, build-independent signal — robust to the
        # GDBSERVER log-string churn that kept breaking this (the spam-fix rebuild
        # silently dropped "Waiting for connection..."; "listen() succeeded"
        # replaced it). The native-log greps stay as a secondary cross-build
        # confirmation. (down() clears the native log each attempt, so a log
        # match is always the current session's, never a stale one.)
        if ss -ltn 2>/dev/null | grep -q ":${PORT} " \
           || grep -q 'Breakpoint 20 triggered' "$FSUAE_LOG" 2>/dev/null \
           || grep -qE 'GDBSERVER: (Waiting for connection|listen\(\) succeeded)' "$FSUAE_NATIVE_LOG" 2>/dev/null; then
            return 0
        fi
        # Fail-fast: if FS-UAE has died (e.g. the WSLg clipboard GLib crash),
        # don't sit out the full BOOT_TIMEOUT — bail now so the caller retries
        # with a clean restart immediately.
        pgrep -x fs-uae >/dev/null 2>&1 || {
            log "  FS-UAE exited before the trigger (crash?) — bailing to retry"
            return 1
        }
        sleep 0.25   # finer than 1s so we attach within ~0.25s of the trigger
    done
    return 1
}

# ---- start the proxy daemon ----------------------------------------------
start_daemon() {
    setsid nohup python3 "$GDB_PROXY" daemon --mode amiga --host 127.0.0.1 \
        > "$DAEMON_LOG" 2>&1 < /dev/null & disown
    # The daemon spawns gdb and runs `target remote` with a 90s connect/remote
    # timeout — gdb TCP-connects to FS-UAE's already-listening port early, then
    # blocks for the handshake until the :SWOS2 trigger fires (when SWOS2
    # launches, up to tens of seconds into a cold boot; see gdb_proxy.py). Only
    # THEN does the daemon create $SOCK. So wait long enough to cover a full cold
    # boot + the handshake (~100s worst case). Fail FAST, though, if FS-UAE dies
    # on boot — no point sitting out the timeout when there's nothing to attach.
    local end=$(( SECONDS + 110 ))
    local fsuae_seen=0
    while (( SECONDS < end )); do
        if [ -S "$SOCK" ] && python3 "$GDB_PROXY" ping 2>/dev/null | grep -qi pong; then
            return 0
        fi
        # Once we've seen FS-UAE running, a later disappearance == boot crash.
        if pgrep -x fs-uae >/dev/null 2>&1; then
            fsuae_seen=1
        elif (( fsuae_seen )); then
            log "  FS-UAE exited during boot (crash) — bailing to retry"
            return 1
        fi
        sleep 1
    done
    return 1
}

# ---- health check: target stopped (SIGTRAP) with a readable PC ------------
# Returns 0 healthy, 1 degraded. Drains the attach banner first (the daemon's
# first cmd returns the buffered "target remote" banner, not the real state).
is_healthy() {
    python3 "$GDB_PROXY" ping 2>/dev/null | grep -qi pong || return 1
    python3 "$GDB_PROXY" cmd "print 1" --timeout 5 >/dev/null 2>&1     # drain banner
    local ip pc
    ip="$(python3 "$GDB_PROXY" cmd "info program" --timeout 6 2>&1)"
    echo "$ip" | grep -qi "SIGTRAP" || return 1
    pc="$(python3 "$GDB_PROXY" cmd "print/x \$pc" --timeout 5 2>&1)"
    echo "$pc" | grep -qiE '0x[0-9a-f]+' || return 1
    # PC should be the SWOS2 entry (or at least a real code address, not 0).
    echo "$pc" | grep -qi "0x0\b" && return 1
    return 0
}

# ---- one full attach attempt (clean -> launch -> wait -> daemon -> verify) -
attach_once() {
    down
    log "launching FS-UAE..."
    launch_fsuae
    # Connect IMMEDIATELY, exactly like the VSCode bartman extension: spawn
    # FS-UAE, then gdb `target remote` — gdb auto-retries the TCP connect
    # (connect-timeout 20s, set in gdb_proxy.py) and grabs the stub the instant
    # FS-UAE opens port 2345 at the :SWOS2 trigger. NO log-scraping, NO settle:
    # the old "wait for a GDBSERVER log string, then sleep ${SETTLE}s" connected
    # LATE, leaving a window where FS-UAE ran past entry to the menu (DEGRADED) —
    # and depended on log strings that changed between FS-UAE builds.
    # start_daemon waits out a full cold boot and fails FAST if FS-UAE crashes
    # on boot, so the retry kicks in promptly instead of sitting out the connect.
    log "starting gdb daemon (immediate, auto-retry connect)..."
    if ! start_daemon; then
        log "  attach did not come up (FS-UAE boot crash, or stub never opened)"
        return 1
    fi
    log "health check..."
    if is_healthy; then
        # Harness fast-boot: skip the (slow) loader intro. The target is paused at
        # the SWOS2 entry (before ShowLoaderIntroSequence runs); install a breakpoint
        # that force-returns from the intro, so the next `continue` lands at the menu.
        # (A gdb-set _skipLoaderIntro global can't be used on the Amiga: it is only
        # read there, and the m68k LTO/--gc-sections drops the read-only global.)
        python3 "$GDB_PROXY" cmd "set confirm off" >/dev/null 2>&1 || true
        python3 "$GDB_PROXY" cmd "break ShowLoaderIntroSequence" >/dev/null 2>&1 || true
        python3 "$GDB_PROXY" cmd $'commands\nsilent\nreturn\ncontinue\nend' >/dev/null 2>&1 || true
        return 0
    fi
    log "  attach DEGRADED (target not cleanly stopped)"
    return 1
}

# ---- reuse an already-live session instead of cold-booting -----------------
# The FS-UAE one-shot port stays valid for the lifetime of the daemon that
# attached it, so a resident healthy daemon can simply be reused — instant,
# vs ~30s to cold-boot the Amiga again. Returns 0 if a session is live and
# usable (stopped, or running-and-interruptible), 1 otherwise.
reuse_existing() {
    [ -S "$SOCK" ] || return 1
    python3 "$GDB_PROXY" ping 2>/dev/null | grep -qi pong || return 1
    is_healthy && return 0
    # Daemon answers but the target isn't cleanly stopped — most likely it's
    # just running (mid-game). Interrupt and re-check before discarding the
    # live session (a genuinely-dead FS-UAE connection won't recover here).
    local gpid; gpid="$(pgrep -f 'm68k-amiga-elf-gdb' | head -1)"
    [ -n "$gpid" ] || return 1
    log "  live daemon, target running — interrupting to reuse..."
    kill -INT "$gpid" 2>/dev/null
    sleep 2
    python3 "$GDB_PROXY" poll 3 >/dev/null 2>&1
    is_healthy
}

up() {
    local fresh="${1:-}"
    # Default: reuse a live healthy session (skip the cold boot). `up --fresh`
    # or FORCE_RESTART=1 forces a clean down+boot+attach.
    if [ "$fresh" != "--fresh" ] && [ "${FORCE_RESTART:-0}" != "1" ]; then
        if reuse_existing; then
            local pc; pc="$(python3 "$GDB_PROXY" cmd "print/x \$pc" --timeout 5 2>&1 | grep -oiE '0x[0-9a-f]+' | head -1)"
            log "REUSING live session (PC=$pc) — skipped cold boot. Use 'up --fresh' to force a clean restart."
            echo "OK"
            return 0
        fi
    fi
    local i
    for (( i = 1; i <= ATTACH_RETRIES; i++ )); do
        log "=== attach attempt $i/$ATTACH_RETRIES ==="
        if attach_once; then
            local pc
            pc="$(python3 "$GDB_PROXY" cmd "print/x \$pc" --timeout 5 2>&1 | grep -oiE '0x[0-9a-f]+' | head -1)"
            log "ATTACHED + HEALTHY (PC=$pc). Drive with: python3 $GDB_PROXY cmd \"...\""
            echo "OK"
            return 0
        fi
        log "attempt $i failed; retrying with a full restart..."
        sleep 2
    done
    log "FAILED to get a healthy attach after $ATTACH_RETRIES attempts."
    log "Check $FSUAE_LOG and $DAEMON_LOG. Is the ELF built (uae/dh0/data/SWOS2.elf)?"
    echo "FAIL"
    return 1
}

status() {
    if [ ! -S "$SOCK" ]; then echo "DOWN (no socket)"; return 1; fi
    if is_healthy; then
        local pc; pc="$(python3 "$GDB_PROXY" cmd "print/x \$pc" --timeout 5 2>&1 | grep -oiE '0x[0-9a-f]+' | head -1)"
        echo "HEALTHY (PC=$pc)"; return 0
    fi
    echo "DEGRADED"; return 1
}

case "${1:-up}" in
    up)      up "${2:-}" ;;
    down)    down; log "torn down."; echo "DOWN" ;;
    restart) down; up --fresh ;;
    status)  status ;;
    *) echo "usage: $0 {up [--fresh]|down|restart|status}" >&2; exit 2 ;;
esac
