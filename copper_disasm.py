#!/usr/bin/env python3
"""Headless Amiga copper-list disassembler for the fs-uae gdb harness.

Reads a copper list straight out of emulator memory (via the gdb proxy) and
disassembles it into MOVE / WAIT / SKIP with custom-register labels and decoded
values — the copper equivalent of `disassemble` for the beam. Handy for checking
the display setup (bitplane pointers, BPLCONx, DDF/DIW, FMODE, colours) the same
way the vscode-amiga-debug plugin's Copper view does, but from the terminal.

Disassembly logic ported from vscode-amiga-debug/src/client/copperDisassembler.ts.

Usage:
  copper_disasm.py                     # disasm &_copperListBuffer (COPPERLIST_SIZE_BYTES)
  copper_disasm.py <addr> [bytes]      # disasm an explicit copper list
  copper_disasm.py --sym <symbol> [bytes]
Examples:
  copper_disasm.py                     # the live SWOS copper list
  copper_disasm.py 0x1218f0 1316
"""
import subprocess, sys, os, struct

HERE = os.path.dirname(os.path.abspath(__file__))
PROXY = os.path.join(HERE, "gdb_proxy.py")
TMP = os.environ.get("CLAUDE_JOB_DIR", "/tmp")
if os.path.isdir(TMP + "/tmp"): TMP = TMP + "/tmp"

def gdb(cmd, t=30):
    return subprocess.run(["python3", PROXY, "cmd", cmd], capture_output=True,
                          text=True, timeout=t).stdout

def val(expr):
    out = gdb(f'printf "%lu\\n", (unsigned long)({expr})')
    for line in out.splitlines():
        s = line.strip()
        if s.isdigit(): return int(s)
    raise RuntimeError(f"could not eval {expr!r}: {out!r}")

def dump(addr, size):
    path = f"{TMP}/copper.bin"
    if os.path.exists(path): os.remove(path)
    gdb(f'dump binary memory {path} {addr} {addr}+{size}')
    return open(path, "rb").read() if os.path.exists(path) else b""

# ---- Amiga custom register names by offset (0x000..0x1FE), OCS/ECS/AGA ----
def build_regmap():
    r = {
        0x000:"BLTDDAT",0x002:"DMACONR",0x004:"VPOSR",0x006:"VHPOSR",0x008:"DSKDATR",
        0x00A:"JOY0DAT",0x00C:"JOY1DAT",0x00E:"CLXDAT",0x010:"ADKCONR",0x012:"POT0DAT",
        0x014:"POT1DAT",0x016:"POTGOR",0x018:"SERDATR",0x01A:"DSKBYTR",0x01C:"INTENAR",
        0x01E:"INTREQR",0x020:"DSKPTH",0x022:"DSKPTL",0x024:"DSKLEN",0x026:"DSKDAT",
        0x028:"REFPTR",0x02A:"VPOSW",0x02C:"VHPOSW",0x02E:"COPCON",0x030:"SERDAT",
        0x032:"SERPER",0x034:"POTGO",0x036:"JOYTEST",0x038:"STREQU",0x03A:"STRVBL",
        0x03C:"STRHOR",0x03E:"STRLONG",0x040:"BLTCON0",0x042:"BLTCON1",0x044:"BLTAFWM",
        0x046:"BLTALWM",0x048:"BLTCPTH",0x04A:"BLTCPTL",0x04C:"BLTBPTH",0x04E:"BLTBPTL",
        0x050:"BLTAPTH",0x052:"BLTAPTL",0x054:"BLTDPTH",0x056:"BLTDPTL",0x058:"BLTSIZE",
        0x05A:"BLTCON0L",0x05C:"BLTSIZV",0x05E:"BLTSIZH",0x060:"BLTCMOD",0x062:"BLTBMOD",
        0x064:"BLTAMOD",0x066:"BLTDMOD",0x070:"BLTCDAT",0x072:"BLTBDAT",0x074:"BLTADAT",
        0x07C:"DENISEID",0x07E:"DSKSYNC",0x080:"COP1LCH",0x082:"COP1LCL",0x084:"COP2LCH",
        0x086:"COP2LCL",0x088:"COPJMP1",0x08A:"COPJMP2",0x08C:"COPINS",0x08E:"DIWSTRT",
        0x090:"DIWSTOP",0x092:"DDFSTRT",0x094:"DDFSTOP",0x096:"DMACON",0x098:"CLXCON",
        0x09A:"INTENA",0x09C:"INTREQ",0x09E:"ADKCON",0x100:"BPLCON0",0x102:"BPLCON1",
        0x104:"BPLCON2",0x106:"BPLCON3",0x108:"BPL1MOD",0x10A:"BPL2MOD",0x10C:"BPLCON4",
        0x10E:"CLXCON2",0x1FC:"FMODE",0x1FE:"NO-OP",
        0x05A:"BLTCON0L",0x1DC:"BEAMCON0",0x1E4:"DIWHIGH",
    }
    # audio 0x0A0..0x0DF
    for i,ch in enumerate(range(0x0A0,0x0E0,0x10)):
        r[ch+0]="AUD%dLCH"%i; r[ch+2]="AUD%dLCL"%i; r[ch+4]="AUD%dLEN"%i
        r[ch+6]="AUD%dPER"%i; r[ch+8]="AUD%dVOL"%i; r[ch+0xA]="AUD%dDAT"%i
    # bitplane pointers 0x0E0..0x0FE (BPL1..8 PTH/PTL)
    for i in range(8):
        r[0x0E0+i*4]="BPL%dPTH"%(i+1); r[0x0E0+i*4+2]="BPL%dPTL"%(i+1)
    # bitplane data 0x110..0x11E
    for i in range(8): r[0x110+i*2]="BPL%dDAT"%(i+1)
    # sprite pointers 0x120..0x13E, sprite data 0x140..0x17E
    for i in range(8):
        r[0x120+i*4]="SPR%dPTH"%i; r[0x120+i*4+2]="SPR%dPTL"%i
        r[0x140+i*8]="SPR%dPOS"%i; r[0x140+i*8+2]="SPR%dCTL"%i
        r[0x140+i*8+4]="SPR%dDATA"%i; r[0x140+i*8+6]="SPR%dDATB"%i
    # colours 0x180..0x1BE
    for i in range(32): r[0x180+i*2]="COLOR%02d"%i
    return r
REG = build_regmap()

def reg_name(off):
    return REG.get(off, "$%03X" % off)

def _lores_px(steps):
    """AGA scroll steps are 35ns = 1/4 lores pixel; print whole pixels when exact."""
    return "%d" % (steps // 4) if steps % 4 == 0 else "%.2f" % (steps / 4.0)

def _scroll_steps(v, pf):
    """One playfield's 8-bit BPLCON1 scroll value (AA layout, 35ns steps).

    Bits are split: H5-H2 in the OCS nibble (3-0 PF1 / 7-4 PF2), H1-H0 in 9-8 / 13-12,
    H7-H6 in 11-10 / 15-14. An OCS value (bits 15-8 zero) is H5-H2 only, i.e. whole
    lores pixels, so the same decode is right on every chipset."""
    sh = 0 if pf == 1 else 4
    return (((v >> (10 + sh)) & 3) << 6) | (((v >> sh) & 0xF) << 2) | ((v >> (8 + sh)) & 3)

FETCH_STEP = {0: "1x 16-bit fetch", 1: "2x BPL32", 2: "2x BPAGEM", 3: "4x BPL32+BPAGEM"}
SPRES = {0: "ECS-default", 1: "lores", 2: "hires", 3: "shres"}

def decode_value(off, v, state):
    """Human-readable decode of notable MOVE targets.

    `state` carries register values seen earlier in the same list (BPLCON3 bank/LOCT
    select which of the 256 AGA colours a COLORxx MOVE loads)."""
    name = REG.get(off, "")
    if name == "BPLCON0":
        bpu = ((v>>12)&7) | (((v>>4)&1)<<3)   # AGA: BPU3 = bit4 (8 planes = $x010)
        res = "shres" if (v>>6)&1 else "hires" if (v>>15)&1 else "lores"
        flags = [f for bit, f in ((11,"HAM"),(10,"DPF"),(2,"LACE"),(0,"ECSENA")) if (v>>bit)&1]
        return "BPU=%d %s%s" % (bpu, res, "".join(" "+f for f in flags))
    if name == "BPLCON1":
        p1, p2 = _scroll_steps(v, 1), _scroll_steps(v, 2)
        return "PF1=%s PF2=%s lores px (%d/%d x 35ns)" % (_lores_px(p1), _lores_px(p2), p1, p2)
    if name == "BPLCON2":
        out = "PF1P=%d PF2P=%d" % (v&7, (v>>3)&7)
        if (v>>6)&1: out += " PF2PRI"
        if (v>>9)&1: out += " KILLEHB"
        return out
    if name == "BPLCON3":
        state["bplcon3"] = v
        pf2of = (0, 2, 4, 8, 16, 32, 64, 128)[(v>>10)&7]
        out = "BANK=%d PF2OF=%d LOCT=%d SPRES=%s" % ((v>>13)&7, pf2of, (v>>9)&1, SPRES[(v>>6)&3])
        border = [f for bit, f in ((5,"BRDRBLNK"),(4,"BRDNTRAN"),(1,"BRDSPRT")) if (v>>bit)&1]
        return out + "".join(" "+f for f in border)
    if name == "BPLCON4":
        return "BPLAM=$%02X ESPRM=%d OSPRM=%d (sprite colours %d+/%d+)" % (
            v>>8, (v>>4)&0xF, v&0xF, ((v>>4)&0xF)*16, (v&0xF)*16)
    if name == "FMODE":
        out = "bitplanes %s, sprites %s" % (FETCH_STEP[v&3], FETCH_STEP[(v>>2)&3].replace("BPL","SPR").replace("BPAGEM","SPAGEM"))
        if (v>>14)&1: out += " BSCAN2"
        if (v>>15)&1: out += " SSCAN2"
        return out
    if name in ("DDFSTRT","DDFSTOP"):
        # colour clocks; lores DIW x = 2*DDF + 17, hires = 2*DDF + 9 (HRM formulas)
        return "cck=$%02X (lores DIW x=%d)" % (v & 0xFF, 2*(v & 0xFF) + 17)
    if name == "DIWSTRT":
        return "V=%d H=%d" % (v>>8, v&0xFF)
    if name == "DIWSTOP":
        vstop = v >> 8
        if not vstop & 0x80: vstop |= 0x100      # OCS: V8 = NOT V7
        return "V=%d H=%d" % (vstop, (v&0xFF)|0x100)
    if name == "DIWHIGH":
        return "start V8-10=%d H10/H1/H0=%d%d%d  stop V8-10=%d H10/H1/H0=%d%d%d" % (
            v&7, (v>>5)&1, (v>>4)&1, (v>>3)&1, (v>>8)&7, (v>>13)&1, (v>>12)&1, (v>>11)&1)
    if name.startswith("COLOR"):
        rgb = "#%X%X%X" % ((v>>8)&0xF,(v>>4)&0xF,v&0xF)
        b3 = state.get("bplcon3")
        if b3 is None or (b3 & 0xE200) == 0:
            return rgb                             # OCS/ECS, or AGA bank 0 high nibbles
        entry = ((b3>>13)&7)*32 + int(name[5:])
        return "%s -> colour %d %s nibbles" % (rgb, entry, "low" if (b3>>9)&1 else "high")
    return ""

def disasm(mem, base_addr):
    out = []
    off = 0
    state = {}
    while off + 4 <= len(mem):
        first  = (mem[off] << 8) | mem[off+1]
        second = (mem[off+2] << 8) | mem[off+3]
        a = base_addr + off
        if first & 1:
            # WAIT or SKIP
            vp=first>>8; hp=first&0xFE; bfd=(second>>15)&1
            ve=((second)|0x8000)>>8; he=second&0xFE
            vert=vp & ve; horiz=hp & he
            if first==0xFFFF and second==0xFFFE:
                out.append("%08X: %04X %04X   END OF COPPERLIST" % (a,first,second)); break
            if second & 1:
                out.append("%08X: %04X %04X   SKIP  if vpos>=%d hpos>=%d%s" %
                           (a,first,second,vert,horiz,"" if bfd else " (blitter-finished)"))
            else:
                cond=[]
                cond.append("vpos>=%d"%vert)
                if horiz: cond.append("hpos>=%d"%horiz)
                if bfd==0: cond.append("blitter-finished")
                out.append("%08X: %04X %04X   WAIT  %s" % (a,first,second," & ".join(cond)))
        else:
            da=first & 0x1FE
            nm=reg_name(da); dec=decode_value(da, second, state)
            out.append("%08X: %04X %04X   MOVE  %-9s = $%04X%s" %
                       (a,first,second,nm,second, ("  ; "+dec) if dec else ""))
        off += 4
    return "\n".join(out)

def main():
    a = sys.argv[1:]
    if a and a[0] == "--sym":
        addr = val("(unsigned long)(&%s)" % a[1])
        size = int(a[2]) if len(a)>2 else 1316
    elif a:
        addr = int(a[0],0); size = int(a[1],0) if len(a)>1 else 1316
    else:
        addr = val("(unsigned long)(&_copperListBuffer)")
        try: size = val("(int)COPPERLIST_SIZE_BYTES")
        except Exception: size = 1316
    mem = dump(addr, size)
    if not mem:
        print("ERROR: could not read copper list at 0x%X" % addr); return
    print("; copper list @ 0x%X (%d bytes)\n" % (addr, len(mem)))
    print(disasm(mem, addr))

if __name__ == "__main__":
    main()
