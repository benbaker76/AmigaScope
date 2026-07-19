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

def decode_value(off, v):
    """Human-readable decode of notable MOVE targets."""
    name = REG.get(off, "")
    if name == "BPLCON0":
        bpu = ((v>>12)&7) | (((v>>4)&1)<<3)   # AGA: BPU3 = bit4
        hires = (v>>15)&1
        return "BPU=%d %s%s" % (bpu, "hires" if hires else "lores",
                                " HAM" if (v>>11)&1 else "")
    if name == "BPLCON1":
        return "PF1H=%d PF2H=%d (fine scroll)" % (v & 0x3F, (v>>4)&0x3F)
    if name == "FMODE":
        bpl = v & 3; spr=(v>>2)&3
        return "BPL32=%d SPR=%d %s" % (bpl, spr, "(2x/4x fetch)" if bpl else "")
    if name in ("DDFSTRT","DDFSTOP"):
        return "hpos=%d" % (v*2)
    if name in ("DIWSTRT",):
        return "V=%d H=%d" % (v>>8, v&0xFF)
    if name in ("DIWSTOP",):
        return "V=%d H=%d" % ((v>>8)|0x100, (v&0xFF)|0x100)
    if name.startswith("COLOR"):
        return "#%X%X%X" % ((v>>8)&0xF,(v>>4)&0xF,v&0xF)
    return ""

def disasm(mem, base_addr):
    out = []
    off = 0
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
            nm=reg_name(da); dec=decode_value(da, second)
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

main()
