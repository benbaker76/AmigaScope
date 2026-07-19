#!/usr/bin/env bash
# shot.sh CAMX CAMY OUT.png  — set the pitch-scroll-test camera to (CAMX,CAMY),
# capture the REAL composited FS-UAE frame (monitor screenshot on the accurate
# vscode binary is async → schedule then run a frame so it writes), copy to OUT.
# Ground truth for the AGA scroll (my fb_capture buffer decode proved unreliable
# — it read the draw buffer, not the displayed one). Requires a HEALTHY harness.
set +e +o pipefail 2>/dev/null
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
CAMX="${1:-0}"; CAMY="${2:-150}"; OUT="${3:-/tmp/shot.png}"
gp="$(pgrep -f 'm68k-amiga-elf-gdb' | head -1)"
kill -INT "$gp" 2>/dev/null; timeout 10 python3 gdb_proxy.py health >/dev/null 2>&1
timeout 6  python3 gdb_proxy.py cmd 'set variable g_pstSpeed=0'       >/dev/null 2>&1
timeout 6  python3 gdb_proxy.py cmd 'set variable g_pstAutoScrollX=0' >/dev/null 2>&1
timeout 6  python3 gdb_proxy.py cmd 'set variable g_pstShowOverlay=0' >/dev/null 2>&1
timeout 12 python3 gdb_proxy.py cmd "call (void)ReplayUpdateCameraAndSwapBuffers($CAMX, $CAMY)" >/dev/null 2>&1
timeout 6  python3 gdb_proxy.py cmd "set variable g_pstCamX=$CAMX"    >/dev/null 2>&1
timeout 6  python3 gdb_proxy.py cmd "set variable g_pstCamY=$CAMY"    >/dev/null 2>&1
# SETTLE first (frozen camera, several loop frames stabilise both buffers), THEN
# schedule the async shot and run ONE more frame to write it — otherwise the shot
# captures the transient frame right after the redraw, not the steady display.
timeout 4  python3 gdb_proxy.py cmd continue                         >/dev/null 2>&1
kill -INT "$gp" 2>/dev/null; timeout 10 python3 gdb_proxy.py health >/dev/null 2>&1
timeout 8  python3 gdb_proxy.py cmd 'monitor screenshot'             >/dev/null 2>&1
timeout 4  python3 gdb_proxy.py cmd continue                         >/dev/null 2>&1
kill -INT "$gp" 2>/dev/null; timeout 10 python3 gdb_proxy.py health >/dev/null 2>&1
newest="$(ls -t "$HOME/FS-UAE/Screenshots/"*.png 2>/dev/null | head -1)"
cp "$newest" "$OUT" 2>/dev/null && echo "wrote $OUT  (camX=$CAMX camY=$CAMY  src=$(basename "$newest"))"
