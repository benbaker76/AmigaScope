#!/usr/bin/env python3
"""Decode the Amiga AGA frontbuffer (8 interleaved bitplanes) straight from
emulator memory via the gdb proxy, into a PNG. Bypasses the composited-frame
timing (monitor screenshot returns the last DISPLAYED frame, which lags the
game's just-drawn frame by one vblank) so it shows exactly what the game drew
this frame — the reliable way to see scroll artifacts while halted.

Layout (display.h): line stride ROW_STRIDE=352 B; within a line plane p starts at
p*PLANE_STRIDE(44); each plane row is 44 B = 352 px, MSB-first. Palette
_gamePalette = 256 x uint16 0x0RGB (12-bit).

Usage: fb_capture.py [out.png] [alt]     (alt = decode the DISPLAYED buffer)"""
import subprocess, sys, struct, zlib, os

HERE = os.path.dirname(os.path.abspath(__file__))
PROXY = os.path.join(HERE, "gdb_proxy.py")
PLANE_STRIDE, NPLANES = 48, 8         # AGA widened buffer: 48 B/plane = 384px
ROW_STRIDE = PLANE_STRIDE * NPLANES   # 384
W, H = PLANE_STRIDE * 8, 272          # 384 px wide
SCREEN_WIDTH = 336   # visible DIW width (px)
TMP = os.environ.get("CLAUDE_JOB_DIR", "/tmp")
if os.path.isdir(TMP + "/tmp"): TMP = TMP + "/tmp"

def gdb(cmd, t=30):
    return subprocess.run(["python3", PROXY, "cmd", cmd], capture_output=True,
                          text=True, timeout=t).stdout

def val(expr):
    """Evaluate a gdb expression to an int (handles 0x.. and decimal)."""
    out = gdb(f'printf "%lu\\n", (unsigned long)({expr})')
    for line in out.splitlines():
        line = line.strip()
        if line.isdigit(): return int(line)
    raise RuntimeError(f"could not eval {expr!r}: {out!r}")

def dump(addr, size, path):
    if os.path.exists(path): os.remove(path)
    gdb(f'dump binary memory {path} {addr} {addr}+{size}')
    return open(path, "rb").read() if os.path.exists(path) else b""

def png(path, w, h, rgb):
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    raw = bytearray()
    for y in range(h):
        raw.append(0); raw += rgb[y*w*3:(y+1)*w*3]
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))

COP_BPLPTR_BLOCKA_OFF = 0x498   # AGA copper: block-A 8 plane-ptr MOVEs

def plane_ptr(p):
    """Read the LIVE displayed plane-p address from the copper block-A. Each plane
    is 2 MOVE pairs of 8 bytes: hi word at +2, lo word at +6 within the pair."""
    base = val(f"(unsigned long)(&_copperListBuffer)") + COP_BPLPTR_BLOCKA_OFF + p*8
    hi = val(f"*(unsigned short *)({base}+2)")
    lo = val(f"*(unsigned short *)({base}+6)")
    return (hi << 16) | lo

def plane0_display_ptr():
    """plane-0 fetch pointer (coarse X + Y offset baked in)."""
    return plane_ptr(0)

def live_plane_stride():
    """Derive PLANE_STRIDE from the copper itself (plane1 - plane0), so the decode
    auto-adapts to the build's buffer geometry (44 OCS / 48 / 52 AGA-with-margin)
    instead of a hard-coded constant that rots when display.h widens the stride."""
    return plane_ptr(1) - plane_ptr(0)

def main():
    global PLANE_STRIDE, ROW_STRIDE, W
    out = sys.argv[1] if len(sys.argv) > 1 else f"{TMP}/fb.png"
    # geometry from the LIVE copper (self-adapts to 44/48/52 stride builds)
    PLANE_STRIDE = live_plane_stride()
    ROW_STRIDE   = PLANE_STRIDE * NPLANES
    W            = PLANE_STRIDE * 8
    p0 = plane0_display_ptr()   # DISPLAYED buffer plane-0 ptr, coarse+Y baked in
    # "other" arg → decode the OTHER (draw) buffer at the SAME offset, to expose a
    # double-buffer mismatch (one buffer clean, one with the strip → live flicker).
    base = val("_frontbufferBasePtr"); alt = val("_frontbufferBaseAltPtr")
    which = "DISPLAYED"
    fb = p0
    if len(sys.argv) > 2 and sys.argv[2] == "other":
        # offset of P0 within whichever base it belongs to
        disp_base = base if abs(p0 - base) < abs(p0 - alt) else alt
        draw_base = alt if disp_base == base else base
        fb = draw_base + (p0 - disp_base)
        which = "DRAW(other)"
    print(f"[base=0x{base:x} alt=0x{alt:x} P0=0x{p0:x} -> {which} fb=0x{fb:x}]")
    camxm = val("_cameraXMod320"); camym = val("_cameraYMod320")
    pal_addr = val("&_gamePalette")
    palraw = dump(pal_addr, 512, f"{TMP}/pal.bin")
    pal = []
    for i in range(256):
        v = struct.unpack(">H", palraw[i*2:i*2+2])[0] if len(palraw) >= i*2+2 else 0
        pal.append((((v >> 8) & 0xF)*17, ((v >> 4) & 0xF)*17, (v & 0xF)*17))
    dsize = ROW_STRIDE*H + PLANE_STRIDE*NPLANES   # +1 plane block so plane 7 line 271 is covered
    buf = dump(fb, dsize, f"{TMP}/fb.bin")
    if len(buf) < ROW_STRIDE*H:
        print(f"ERROR: short fb dump ({len(buf)} bytes)"); return
    # DISPLAY-ACCURATE decode: the copper reads plane p starting at
    # base+coarse_byte+p*PLANE_STRIDE and advances +PLANE_STRIDE per plane / +1 per
    # byte LINEARLY (no mid-line X-wrap — block-B was removed), so it OVER-READS
    # into the next plane's region for x beyond the plane-row end. Reproduce that
    # exactly so the PNG matches the live display, not the raw storage.
    #
    # By default render the REAL VISIBLE WINDOW (what's on screen): the plane
    # pointer is coarse_byte (FMODE 4-byte / 32px aligned) and BPLCON1 fine-scroll
    # shifts the leftmost visible pixel to coarse_px + snapped_frac, where
    # snapped_frac = min(camXMod & 0x1F, 16) under the AGA snap. So the visible
    # 336px window starts snapped_frac px into the fetch — the leftmost snapped_frac
    # px (and the plane-row seam that rolls through there) are the DIW-cropped
    # headroom, NOT shown on the real display. Pass "full" to see the whole 352px
    # fetched buffer incl. that off-screen headroom (for debugging the roll seam).
    # Decode straight from P0 (the displayed plane-0 pointer). Plane p, display
    # line y, screen x → byte  P0 + p*PLANE_STRIDE + y*ROW_STRIDE + x/8, MSB-first.
    # This is byte-for-byte the Amiga's block-A fetch: linear, over-reading past
    # the plane row into whatever the next plane region holds. Full 352px fetch.
    wout = W
    rgb = bytearray(wout*H*3)
    for y in range(H):
        lb = y*ROW_STRIDE
        for x in range(wout):
            byte = x >> 3; bit = 7 - (x & 7); idx = 0
            for p in range(NPLANES):
                a = lb + p*PLANE_STRIDE + byte
                idx |= ((buf[a] >> bit) & 1) << p if a < len(buf) else 0
            r, g, b = pal[idx]
            o = (y*wout + x)*3; rgb[o] = r; rgb[o+1] = g; rgb[o+2] = b
    png(out, wout, H, rgb)
    print(f"wrote {out}  P0=0x{fb:x} (DISPLAYED buffer via copper block-A) "
          f"camXMod={camxm} camYMod={camym}  [352px fetch, plane p from P0+p*{PLANE_STRIDE}]")

main()
