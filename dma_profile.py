#!/usr/bin/env python3
"""Headless Amiga DMA profiler for the bartman fs-uae gdb harness.

Drives `monitor profile <N> "" <out>` on the modified fs-uae binary (which has a
cycle-exact DMA recorder), then parses the per-frame DMA record grid
(227 hpos x 313 vpos, one entry per colour-clock per scanline) and reports which
DMA channel owned each cycle. The point: SEE, cycle-exact, whether the blitter is
running on the same scanlines the bitplanes are being fetched — i.e. real
blitter-vs-display DMA contention — instead of guessing from screenshots.

Record + file format reverse-engineered from the authoritative parser in
  vscode-amiga-debug/src/backend/profile.ts   (sizeofDmaRec = 58)
  vscode-amiga-debug/src/client/dma.ts        (DmaTypes / DmaEvents)

Usage:
  dma_profile.py profile <N> <out.prof>   # capture N frames via the running harness
  dma_profile.py parse <out.prof>         # parse + report contention per frame
  dma_profile.py <N>                      # profile N frames to a temp file, then parse
"""
import subprocess, sys, os, struct, time

HERE = os.path.dirname(os.path.abspath(__file__))
PROXY = os.path.join(HERE, "gdb_proxy.py")
TMP = os.environ.get("CLAUDE_JOB_DIR", "/tmp")
if os.path.isdir(TMP + "/tmp"): TMP = TMP + "/tmp"

NR_HPOS, NR_VPOS = 227, 313
SIZEOF_DMAREC = 58
DMACOUNT = NR_HPOS * NR_VPOS            # 71051
MARKER = struct.pack("<II", SIZEOF_DMAREC, DMACOUNT)   # dmaLen, dmaCount

# DmaTypes (dma.ts)
T = {1: "refresh", 2: "cpu", 3: "copper", 4: "audio", 5: "BLITTER",
     6: "bitplane", 7: "sprite", 8: "disk", 9: "CONFLICT"}
# DmaEvents (dma.ts) — contention-relevant bits of the per-cell evt word
EV_NOONEGETS       = 256
EV_CPUBLITTERSTEAL = 512
EV_CPUBLITTERSTOLEN = 1024
EV_VB              = 0x10000       # vertical blank
EV_VDIW            = 0x1000000     # inside vertical display window (a display line)

def gdb(cmd, t=60):
    return subprocess.run(["python3", PROXY, "cmd", cmd], capture_output=True,
                          text=True, timeout=t).stdout

def _count_blocks(path):
    """Number of complete DMA frame blocks written so far (one MARKER per frame)."""
    try:
        with open(path, "rb") as f: buf = f.read()
    except OSError:
        return 0
    c = 0; off = 0
    while True:
        i = buf.find(MARKER, off)
        if i < 0: break
        c += 1; off = i + len(MARKER)
    return c

def do_profile(n, out, wait=None):
    """Capture N frames of cycle-exact DMA/CPU into `out`.

    `monitor profile` returns an INSTANT benign ack ("Protocol error with Rcmd: 01") and
    writes the file ASYNCHRONOUSLY — completion = N MARKER blocks present; never test
    os.path.exists right after the ack (the historic always-FAILED bug). Each cycle-exact
    frame costs ~1-5 s (light steady frame) up to much longer (DMA-heavy frames), so poll.

    NOTE: the output path is QUOTED. An UNQUOTED path used to lose its leading char in
    fs-uae's `monitor profile` parser (fopen then failed and froze the target) — fixed in
    the fork, but quoting is correct regardless."""
    if os.path.exists(out):
        try: os.remove(out)
        except OSError: pass
    gdb(f'monitor profile {n} "" "{out}"', t=30)
    deadline = time.time() + (wait if wait is not None else n * 90 + 60)
    while time.time() < deadline:
        if _count_blocks(out) >= n:
            time.sleep(1)   # let trailing resource/screenshot bytes flush
            return True
        time.sleep(2)
    return _count_blocks(out) >= n

def parse(path):
    with open(path, "rb") as f:
        buf = f.read()
    # find every DMA block (one per profiled frame) by its (dmaLen,dmaCount) marker
    blocks = []
    off = 0
    while True:
        i = buf.find(MARKER, off)
        if i < 0: break
        start = i + len(MARKER)
        end = start + SIZEOF_DMAREC * DMACOUNT
        if end <= len(buf):
            blocks.append((start, buf[start:end]))
        off = i + 1
    print(f"{os.path.basename(path)}: {len(blocks)} DMA frame block(s)")
    for fi, (start, blk) in enumerate(blocks):
        analyze_frame(fi, blk)
        analyze_budget(fi, blk)
        analyze_fetch(fi, blk)

FETCH_DISPLAY_VLO, FETCH_DISPLAY_VHI = 36, 307   # SWOS AGA pitch vertical window

def analyze_fetch(fi, blk):
    """Cycle-exact DDFSTRT-vs-sprite steal check. The 8 hardware sprites each own
    a FIXED pair of DMA slots (measured from the control-word fetch, whatever line
    it lands on). AGA disables a sprite whose slots fall AT/AFTER the bitplane fetch
    start (early DDFSTRT). So: measure the bitplane fetch start (typ 6, on display
    lines) and flag every sprite slot >= that start as stolen. SWOS uses spr0..spr3
    (planes01=spr0/1, planes23=spr2/3). This is the proof of the steal now, and the
    proof FMODE=3 clears it later (fetch start should move past the spr0..3 slots)."""
    bpl_min = 999; bpl_max = -1
    spr_slots = {}   # hpos -> count (sprite DMA slots, wherever they appear)
    for idx in range(DMACOUNT):
        b = idx * SIZEOF_DMAREC
        typ = struct.unpack_from("<h", blk, b+29)[0]
        vpos = idx // NR_HPOS; hpos = idx % NR_HPOS
        if typ == 7:
            spr_slots[hpos] = spr_slots.get(hpos, 0) + 1
        elif typ == 6 and FETCH_DISPLAY_VLO <= vpos <= FETCH_DISPLAY_VHI:
            if hpos < bpl_min: bpl_min = hpos
            if hpos > bpl_max: bpl_max = hpos
    if bpl_max < 0:
        print("    fetch: no bitplane DMA on display lines (unexpected)"); return
    print(f"    fetch: bitplane DMA hpos on display lines = "
          f"0x{bpl_min:02x}..0x{bpl_max:02x} (starts @0x{bpl_min:02x})")
    slots = sorted(spr_slots)
    if slots:
        # pair consecutive slots into sprites spr0,spr1,... (2 DMA words each)
        pairs = [slots[i:i+2] for i in range(0, len(slots), 2)]
        stolen = [n for n, pr in enumerate(pairs) if any(h >= bpl_min for h in pr)]
        print(f"    sprite DMA slots: " +
              "  ".join(f"spr{n}=0x{pr[0]:02x}" + (f"/0x{pr[1]:02x}" if len(pr) > 1 else "")
                        for n, pr in enumerate(pairs)))
        if stolen:
            print(f"    >>> STEAL: fetch start 0x{bpl_min:02x} lands on slots of "
                  f"spr{stolen} -> those sprites are DISABLED by AGA")
            swos = [n for n in stolen if n <= 3]
            if swos:
                print(f"        of the SWOS sprites (spr0..3): spr{swos} LOST")
        else:
            print(f"    CLEAR: fetch start 0x{bpl_min:02x} is past all sprite slots -> sprites safe")
    else:
        print("    (no sprite DMA slots recorded this frame)")

# vscode-amiga-debug-style DMA channel breakdown: every colour-clock categorised by
# channel (type at rec+29) and subtype (extra at rec+31), as % of the frame raster.
DMA_GROUP   = {1: "Refresh", 2: "CPU", 3: "Copper", 4: "Audio", 5: "Blitter",
               6: "Bitplane", 7: "Sprite", 8: "Disk", 9: "Conflict"}
_CPU_SUB    = {0: "Code", 1: "Data"}
_COPPER_SUB = {0: "Copper", 1: "Wait", 2: "Special"}

def analyze_budget(fi, blk):
    """Frame DMA budget: every colour-clock by channel (+ CPU Code/Data and Copper
    Copper/Wait/Special subtypes), as % of the frame raster — the breakdown the
    vscode-amiga-debug frame profiler shows beside the flame graph."""
    cat = {}; used = 0
    for idx in range(DMACOUNT):
        b = idx * SIZEOF_DMAREC
        typ = struct.unpack_from("<h", blk, b + 29)[0]
        if typ <= 0:
            continue
        used += 1
        extra = struct.unpack_from("<H", blk, b + 31)[0]
        if typ == 2:                                    # CPU -> Code/Data
            key = ("CPU", _CPU_SUB.get(extra & 1, "?"))
        elif typ == 3:                                  # Copper -> Copper/Wait/Special
            key = ("Copper", _COPPER_SUB.get(extra, "Copper"))
        else:
            key = (DMA_GROUP.get(typ, str(typ)), None)
        cat[key] = cat.get(key, 0) + 1
    pct = lambda c: 100.0 * c / DMACOUNT
    print(f"    DMA budget — {used:,}/{DMACOUNT:,} colour-clocks used ({pct(used):.1f}% of frame):")
    for grp in ("CPU", "Blitter", "Bitplane", "Copper", "Sprite", "Refresh", "Audio", "Disk", "Conflict"):
        subs = {k[1]: v for k, v in cat.items() if k[0] == grp}
        if not subs:
            continue
        tot = sum(subs.values())
        print(f"      {grp:9} {pct(tot):6.2f}%  ({tot:,} cc)")
        for sub, v in sorted(subs.items(), key=lambda kv: -kv[1]):
            if sub is not None:
                print(f"        {sub:7} {pct(v):6.2f}%  ({v:,} cc)")

def analyze_frame(fi, blk):
    # per-scanline channel tallies
    bpl_lines = set(); blt_lines = set(); conflict_cells = 0
    steal = 0; blitter_cells = 0; bitplane_cells = 0
    blt_on_display_line = {}   # vpos -> list of hpos where blitter ran on a bitplane line
    per_line_bpl = [0]*NR_VPOS
    per_line_blt = [0]*NR_VPOS
    for idx in range(DMACOUNT):
        b = idx * SIZEOF_DMAREC
        reg  = blk[b] | (blk[b+1] << 8)
        evt  = struct.unpack_from("<I", blk, b+16)[0]
        typ  = struct.unpack_from("<h", blk, b+29)[0]
        vpos = idx // NR_HPOS
        hpos = idx % NR_HPOS
        if typ == 6:  # bitplane
            bitplane_cells += 1; bpl_lines.add(vpos); per_line_bpl[vpos]+=1
        elif typ == 5:  # blitter
            blitter_cells += 1; blt_lines.add(vpos); per_line_blt[vpos]+=1
        elif typ == 9:  # conflict
            conflict_cells += 1
        if evt & (EV_CPUBLITTERSTEAL | EV_CPUBLITTERSTOLEN):
            steal += 1
    # display lines = lines with bitplane DMA. contention lines = those w/ blitter too.
    contention_lines = sorted(l for l in bpl_lines if per_line_blt[l] > 0)
    disp_lo = min(bpl_lines) if bpl_lines else -1
    disp_hi = max(bpl_lines) if bpl_lines else -1
    blt_lo = min(blt_lines) if blt_lines else -1
    blt_hi = max(blt_lines) if blt_lines else -1
    print(f"  frame {fi}: bitplane_cells={bitplane_cells} blitter_cells={blitter_cells} "
          f"conflict_cells={conflict_cells} steal_evt={steal}")
    print(f"    display lines (bitplane DMA): vpos {disp_lo}..{disp_hi} "
          f"({len(bpl_lines)} lines)")
    if blt_lines:
        print(f"    blitter active:            vpos {blt_lo}..{blt_hi} "
              f"({len(blt_lines)} lines)")
        if contention_lines:
            print(f"    >>> CONTENTION: blitter runs on {len(contention_lines)} "
                  f"DISPLAY lines (blitter + bitplane same scanline)")
            print(f"        contention vpos: {contention_lines[:12]}"
                  f"{'...' if len(contention_lines)>12 else ''}")
        else:
            print(f"    blitter stays OUT of display lines (clean: blanking-only blit)")
    else:
        print(f"    no blitter DMA this frame (no tile-cross)")

# custom-register offsets used for blit reconstruction
R_BLTCON0=0x40; R_BLTAFWM=0x44; R_BLTALWM=0x46
R_BLTDPTH=0x54; R_BLTSIZE=0x58; R_BLTSIZV=0x5C; R_BLTSIZH=0x5E
DISPLAY_VLO, DISPLAY_VHI = 36, 307     # SWOS AGA pitch DIW vertical window

def blit_blocks(path):
    with open(path, "rb") as f: buf = f.read()
    out=[]; off=0
    while True:
        i = buf.find(MARKER, off)
        if i < 0: break
        s = i+len(MARKER); e = s+SIZEOF_DMAREC*DMACOUNT
        if e<=len(buf): out.append(buf[s:e])
        off=i+1
    return out

def analyze_blits(fi, blk):
    """Reconstruct each blit from the DMA stream (port of dma.ts GetBlits):
    track custom-reg writes, a BLTSIZE/BLTSIZH write starts a blit, a BLITIRQ
    (evt bit0) ends the last one. Report raster span + size + channels + dest."""
    reg_shadow = {}
    blits = []
    for idx in range(DMACOUNT):
        b = idx*SIZEOF_DMAREC
        reg  = blk[b] | (blk[b+1]<<8)
        dat  = struct.unpack_from("<H", blk, b+2)[0]     # low word = written value
        addr = struct.unpack_from("<I", blk, b+12)[0]
        evt  = struct.unpack_from("<I", blk, b+16)[0]
        vpos = idx // NR_HPOS; hpos = idx % NR_HPOS
        # resolve a register write (by reg field or by 0xdffxxx addr), dma.ts-style
        r = reg if (reg != 0xffff and reg < 0x200) else \
            (addr-0xdff000 if 0xdff000<=addr<0xdff200 else None)
        if r is not None:
            reg_shadow[r] = dat
            if r in (R_BLTSIZE, R_BLTSIZH):
                if r == R_BLTSIZE:                      # OCS-style pack
                    w = dat & 0x3f or 64; h = (dat>>6) & 0x3ff or 1024
                else:                                    # ECS/AGA
                    w = dat & 0x7ff or 2048; h = reg_shadow.get(R_BLTSIZV,0) & 0x7fff or 32768
                con0 = reg_shadow.get(R_BLTCON0, 0)
                chan = "".join(c for k,c in enumerate("ABCD") if con0 & (1<<(11-k)))
                dptr = (reg_shadow.get(R_BLTDPTH,0)<<16) | reg_shadow.get(R_BLTDPTH+2,0)
                blits.append({"v0":vpos,"h0":hpos,"w":w,"h":h,"chan":chan,
                              "dst":dptr & 0x1ffffe,"v1":None,"h1":None})
        if (evt & 1) and blits and blits[-1]["v1"] is None:  # BLITIRQ
            blits[-1]["v1"]=vpos; blits[-1]["h1"]=hpos
    if not blits:
        print(f"  frame {fi}: no blits"); return
    print(f"  frame {fi}: {len(blits)} blit(s)")
    for bl in blits:
        v1 = bl["v1"] if bl["v1"] is not None else "?"
        # a blit overruns if its raster span touches the display window
        over = ""
        if isinstance(v1,int) and v1 >= DISPLAY_VLO and bl["v0"] <= DISPLAY_VHI:
            first_disp = max(bl["v0"], DISPLAY_VLO)
            over = f"  <<< OVERRUNS DISPLAY (blitter on display lines {first_disp}..{min(v1,DISPLAY_VHI)})"
        print(f"    L{bl['v0']:>3}->L{str(v1):>3}  {bl['w']*16:>3}x{bl['h']:<4}px  "
              f"chan={bl['chan']:<4} D=${bl['dst']:06x}{over}")

def parse_blits(path):
    blks = blit_blocks(path)
    print(f"{os.path.basename(path)}: {len(blks)} frame block(s)  "
          f"[display window vpos {DISPLAY_VLO}..{DISPLAY_VHI}]")
    for fi,blk in enumerate(blks): analyze_blits(fi, blk)

# ---- DMA raster-map visualisation --------------------------------------------
# One cell per colour-clock (hpos) per scanline (vpos); colour = which DMA channel
# owned that cycle. Lets a human SEE the sprite slots vs the bitplane fetch overlap
# instead of reading hpos numbers. PNG out, PIL only (no external deps at import).
CHANNEL_COLORS = {1:(70,70,70), 2:(45,45,75), 3:(70,130,235), 4:(0,190,190),
                  5:(225,55,55), 6:(55,195,70), 7:(245,225,55), 8:(235,150,40),
                  9:(240,60,240)}
CHANNEL_NAMES = {1:"refresh",2:"cpu",3:"copper",4:"audio",5:"blitter",
                 6:"bitplane",7:"sprite",8:"disk",9:"conflict"}
BG = (14,14,18)
# sprite spr_n owns the two DMA slots 0x19+4n / 0x1b+4n (measured, SWOS AGA lores)
SPR_SLOTS = {0x19+2*i: f"s{i//2}" for i in range(16)}

def _frame_cells(blk):
    cells = {}
    for idx in range(DMACOUNT):
        typ = struct.unpack_from("<h", blk, idx*SIZEOF_DMAREC + 29)[0]
        if typ > 0:
            cells[(idx % NR_HPOS, idx // NR_HPOS)] = typ
    return cells

def _fetch_start(cells):
    bpl = [h for (h,v),t in cells.items() if t == 6 and DISPLAY_VLO <= v <= DISPLAY_VHI]
    return min(bpl) if bpl else None

def _grid(cells, hlo, hhi, sx, sy):
    from PIL import Image
    w, h = hhi-hlo, NR_VPOS
    img = Image.new("RGB", (w, h), BG); px = img.load()
    for (hp,vp),t in cells.items():
        if hlo <= hp < hhi:
            px[hp-hlo, vp] = CHANNEL_COLORS.get(t, (255,255,255))
    return img.resize((w*sx, h*sy), Image.NEAREST)

def _legend(d, x, y, types):
    for t in [t for t in (6,7,5,3,9,4,1,2,8) if t in types]:
        d.rectangle([x,y,x+9,y+9], fill=CHANNEL_COLORS[t])
        d.text((x+12,y), CHANNEL_NAMES[t], fill=(210,210,210))
        x += 12 + 6*len(CHANNEL_NAMES[t]) + 12
    return x

def _left_panel(cells, title, sx=11, sy=2):
    """Annotated left-edge (hpos 0x10..0x48): sprite slots (yellow ticks + labels)
    vs the red bitplane-fetch-start line. The 'steal' picture. Rows top-to-bottom:
    title / legend / sprite-slot labels / grid / fetch caption."""
    from PIL import Image, ImageDraw
    hlo, hhi = 0x10, 0x48
    grid = _grid(cells, hlo, hhi, sx, sy); gw, gh = grid.size
    ML, MT, MB = 8, 50, 30
    cv = Image.new("RGB", (gw+ML+8, gh+MT+MB), BG)
    cv.paste(grid, (ML, MT)); d = ImageDraw.Draw(cv)
    d.text((ML, 4), title, fill=(235,235,235))
    _legend(d, ML, 17, set(cells.values()))
    # sprite-slot ticks (into the grid top) + one label per sprite on its own row
    seen=set()
    for hp,lab in SPR_SLOTS.items():
        if hlo <= hp < hhi:
            x = ML + (hp-hlo)*sx
            d.line([(x,MT-6),(x,MT)], fill=CHANNEL_COLORS[7])
            if lab not in seen:
                d.text((x-2, MT-16), "spr"+lab[1], fill=CHANNEL_COLORS[7]); seen.add(lab)
    # bitplane fetch-start line down the whole grid
    fs = _fetch_start(cells)
    if fs is not None and hlo <= fs < hhi:
        x = ML + (fs-hlo)*sx
        d.line([(x,MT-6),(x,MT+gh)], fill=(255,80,80), width=2)
        stolen = sorted({int(SPR_SLOTS[h][1]) for h in SPR_SLOTS if h >= fs and hlo<=h<hhi})
        d.text((ML, MT+gh+4), f"fetch@0x{fs:02x}  ->  steals spr{stolen}", fill=(255,130,130))
    return cv

def _full_panel(cells, title, sx=3, sy=2):
    from PIL import Image, ImageDraw
    grid = _grid(cells, 0, NR_HPOS, sx, sy); gw, gh = grid.size
    MT = 32
    cv = Image.new("RGB", (max(gw,360), gh+MT), BG)
    cv.paste(grid, (0, MT)); d = ImageDraw.Draw(cv)
    d.text((6,4), title, fill=(235,235,235))
    _legend(d, 6, 17, set(cells.values()))
    return cv

def map_cmd(path, prefix=None):
    blks = blit_blocks(path)
    prefix = prefix or os.path.splitext(path)[0]
    outs = []
    for fi, blk in enumerate(blks):
        cells = _frame_cells(blk)
        base = os.path.basename(path)
        full = f"{prefix}_f{fi}_full.png"; left = f"{prefix}_f{fi}_left.png"
        _full_panel(cells, f"{base} frame {fi}: full DMA raster (227x313 cycles)").save(full)
        _left_panel(cells, f"{base} frame {fi}: sprite slots vs bitplane fetch").save(left)
        outs += [full, left]
        print(f"  frame {fi}: wrote {full}  and  {left}")
    return outs

def compare_cmd(pathA, pathB, out):
    """Side-by-side left-edge panels of two profiles (e.g. DDFSTRT=$20 steal vs
    $30 clear) — the before/after of the fix in one image."""
    from PIL import Image
    a = _frame_cells(blit_blocks(pathA)[0]); b = _frame_cells(blit_blocks(pathB)[0])
    pa = _left_panel(a, os.path.basename(pathA)); pb = _left_panel(b, os.path.basename(pathB))
    W = pa.width + pb.width + 12; H = max(pa.height, pb.height)
    cv = Image.new("RGB", (W, H), BG)
    cv.paste(pa, (0,0)); cv.paste(pb, (pa.width+12, 0))
    cv.save(out); print(f"wrote {out}"); return out

def main():
    a = sys.argv[1:]
    if a and a[0] == "profile":
        n = int(a[1]); out = a[2]
        print("OK" if do_profile(n, out) else "FAILED"); return
    if a and a[0] == "parse":
        parse(a[1]); return
    if a and a[0] == "blits":                 # per-blit raster-span view (overrun finder)
        parse_blits(a[1]); return
    if a and a[0] == "map":                    # render DMA raster-map PNG(s)
        map_cmd(a[1], a[2] if len(a) > 2 else None); return
    if a and a[0] == "compare":                # side-by-side left-edge (steal vs clear)
        compare_cmd(a[1], a[2], a[3] if len(a) > 3 else f"{TMP}/dma_compare.png"); return
    n = int(a[0]) if a else 10
    out = f"{TMP}/dma_{n}f.prof"
    if do_profile(n, out): parse(out); parse_blits(out)
    else: print("profile FAILED")

main()
