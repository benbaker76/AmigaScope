#!/usr/bin/env python3
"""CPU flame graph from a bartman fs-uae .prof (the SAME file dma_profile.py captures).

The .prof embeds the fs-uae CPU profiler stream (newcpu.cpp get_cpu_profiler_output):
per executed instruction a record

    [pc ...]  (0xffffffff - cycles)  17*u32 registers(D0-D7,A0-A7,SR)

where a word < 0xffff0000 is a call-stack PC and a word >= 0xffff0000 is the cycles
marker that terminates the stack. Code PCs are .text-RELATIVE offsets; kickstart PCs
are absolute (0xf8_0000..0x100_0000); 0x7fffffff = IRQ. With the empty-unwind capture
that dma_profile.py uses, each stack is depth-1 (leaf only), so this yields a FLAT
self-time profile: which functions burn the frame's CPU cycles. (Provide a real unwind
file to fs-uae and the same walk produces full call stacks -> hierarchical flame graph.)

Emits Brendan-Gregg FOLDED stacks ("funcA;funcB count"), then optionally renders SVG
via the owner's FlameGraph port (C:\\Projects\\Python\\FlameGraph\\flamegraph.py).

  cpu_flamegraph.py top   <in.prof> [N]           # text: top-N functions by cycles
  cpu_flamegraph.py fold  <in.prof> [out.folded]  # write folded stacks
  cpu_flamegraph.py svg   <in.prof> [out.svg]     # fold + render flame graph SVG

Env overrides: SWOS_ELF, M68K_OBJDUMP, FLAMEGRAPH_PY.
"""
import subprocess, sys, os, struct, bisect, re, time
from collections import defaultdict

_HERE      = os.path.dirname(os.path.abspath(__file__))
# ELF with symbols (+ .debug_frame for hierarchical stacks). Set AMIGASCOPE_ELF.
ELF        = os.environ.get("AMIGASCOPE_ELF") or os.environ.get("SWOS_ELF", "")
OBJDUMP    = os.environ.get("M68K_OBJDUMP", "m68k-amiga-elf-objdump")
# FlameGraph renderer — bundled as a git submodule; override with FLAMEGRAPH_PY.
FLAMEGRAPH = os.environ.get("FLAMEGRAPH_PY",
                            os.path.join(_HERE, "third_party", "FlameGraph", "flamegraph.py"))
REG_COUNT  = 17                 # D0-D7 A0-A7 SR (types.ts Register._count)
TEXT_VMA   = 0x100000           # SWOS2.elf .text VMA (verified; re-read below if objdump works)

# ---- ELF symbol resolution ---------------------------------------------------
def load_symbols(elf):
    try:
        out = subprocess.run([OBJDUMP, "-t", elf], capture_output=True, text=True, timeout=90).stdout
    except Exception as e:
        sys.stderr.write(f"objdump -t failed: {e}\n"); return [], []
    ents = []
    for line in out.splitlines():
        # Any symbol whose section is .text — C functions are typed `F`, but assembler
        # labels (vasm/vlink) are plain (no `F`), so match the section, not the type.
        # "00139454 l     F .text\t00000402 name"  or  "00001234 l       .text\t0 label"
        if "\t" not in line:
            continue
        left, right = line.split("\t", 1)
        if not left.rstrip().endswith(".text"):
            continue
        try:
            addr = int(left[:8], 16)
            sz, _, name = right.partition(" ")
            size = int(sz, 16)                      # 0 for un-sized asm labels
        except (ValueError, IndexError):
            continue
        if name:
            ents.append((addr, addr + size, name))  # end==addr when size unknown (asm)
    ents.sort()
    return [e[0] for e in ents], ents

def text_vma_size(elf):
    """(vma, size) of .text from objdump -h; falls back to the known SWOS values."""
    try:
        out = subprocess.run([OBJDUMP, "-h", elf], capture_output=True, text=True, timeout=30).stdout
        for line in out.splitlines():
            p = line.split()
            if len(p) >= 4 and p[1] == ".text":
                return int(p[3], 16), int(p[2], 16)   # VMA, Size
    except Exception:
        pass
    return TEXT_VMA, 0xa9cd8

def text_vma(elf):
    return text_vma_size(elf)[0]

# ---- DWARF -> fs-uae unwind table (for hierarchical call stacks) --------------
# fs-uae reads sizeText>>1 entries of struct { u16 cfa=(reg<<12)|ofs; s16 r13; s16 ra; }
# indexed by (pc-baseText)>>1 == (elf_addr - .text VMA)>>1. Built from
# `objdump --dwarf=frames-interp` exactly like vscode-amiga-debug profile.ts.
def gen_unwind(elf, out):
    vma, size = text_vma_size(elf)
    n_slots = size                       # 2x the (size>>1) fs-uae reads: safe over-allocate
    DEFAULT = ((15 << 12) | 4, -1, -4)   # cfa=r15+4, r13 not saved, ra at cfa-4
    tbl = [DEFAULT] * n_slots
    txt = subprocess.run([OBJDUMP, "--dwarf=frames-interp", elf],
                         capture_output=True, text=True, timeout=180).stdout
    lines = txt.replace("\r", "").split("\n")
    L = len(lines); i = 0
    cie = {}                             # cie-offset -> (cfaReg, cfaOfs, r13, ra)
    cfai = rai = r13i = -1

    def parse_header(idx):
        nonlocal cfai, rai, r13i
        cfai = rai = r13i = -1
        if not (0 <= idx < L):
            return
        cols = lines[idx].split()
        cfai = cols.index("CFA") if "CFA" in cols else -1
        rai  = cols.index("ra")  if "ra"  in cols else -1
        r13i = cols.index("r13") if "r13" in cols else -1

    DATA_RE = re.compile(r'^[0-9a-f]{8}\s')       # a rule row starts with an 8-hex LOC + space
    def parse_row(idx):
        cols = lines[idx].split()
        if not cols:
            return None, None
        try:
            loc = int(cols[0], 16)
        except ValueError:
            return None, None                     # header ("LOC ...") or junk
        m = re.match(r'r(\d+)\+(-?\d+)', cols[cfai]) if 0 <= cfai < len(cols) else None
        if not m:
            return loc, None
        cfaReg, cfaOfs = int(m.group(1)), int(m.group(2))
        r13 = int(cols[r13i][1:]) if (0 <= r13i < len(cols) and cols[r13i].startswith("c")) else -1
        ra  = int(cols[rai][1:])  if (0 <= rai < len(cols) and cols[rai].startswith("c")) else -4
        return loc, (cfaReg, cfaOfs, r13, ra)

    def find_header(idx):                          # advance to the "LOC CFA ..." column row
        while idx < L and "CFA" not in lines[idx]:
            if DATA_RE.match(lines[idx]): break     # safety: never skip a data row
            idx += 1
        return idx

    def put(addr, unw):
        k = (addr - vma) >> 1
        if 0 <= k < n_slots and unw:
            tbl[k] = ((unw[0] << 12) | (unw[1] & 0xfff), unw[2], unw[3])

    nset = 0
    while i < L:
        line = lines[i]
        is_cie = re.match(r'[0-9a-f]{8} [0-9a-f]{8} [0-9a-f]{8} CIE', line)
        is_fde = re.match(r'[0-9a-f]{8} [0-9a-f]{8} [0-9a-f]{8} FDE', line)
        if not (is_cie or is_fde):
            i += 1; continue
        if is_cie:
            addr = int(line[:8], 16)
            hi = find_header(i + 1); parse_header(hi); i = hi + 1
            unw = None
            while i < L and DATA_RE.match(lines[i]):
                _, u = parse_row(i); i += 1
                if u: unw = u                       # CIE: single base rule
            if unw: cie[addr] = unw
        else:  # FDE
            m = re.search(r'cie=([0-9a-f]{8}) pc=([0-9a-f]{8})\.\.([0-9a-f]{8})', line)
            if not m: i += 1; continue
            cie_off = int(m.group(1), 16); pc0 = int(m.group(2), 16); pc1 = int(m.group(3), 16)
            hi = find_header(i + 1); parse_header(hi); i = hi + 1
            unw = cie.get(cie_off); pc = pc0
            while i < L and DATA_RE.match(lines[i]):
                loc, nxt = parse_row(i); i += 1
                if loc is None: continue
                while pc < loc:
                    put(pc, unw); nset += 1; pc += 2
                pc = loc
                if nxt: unw = nxt
            while pc < pc1:
                put(pc, unw); nset += 1; pc += 2

    import array
    flat = array.array('h')          # native s16; host is x86 LE == m68k file consumer expects LE
    if sys.byteorder != 'little':
        raise RuntimeError("unwind writer assumes little-endian host")
    for cfa, r13, ra in tbl:
        flat.append(cfa - 0x10000 if cfa >= 0x8000 else cfa)
        flat.append(r13); flat.append(ra)
    with open(out, "wb") as f:
        f.write(flat.tobytes())
    return n_slots, nset

def resolve(pc, tvma, starts, ents):
    if pc == 0x7fffffff:          return "[IRQ]"
    if 0xf80000 <= pc < 0x1000000: return "[Kickstart]"
    addr = tvma + pc
    i = bisect.bisect_right(starts, addr) - 1
    if 0 <= i < len(ents):
        s, e, n = ents[i]
        if e > s and addr >= e:      # known size and we're past it (padding/thunk)
            return n + "_[tail]"
        return n                     # within the symbol, or an un-sized asm label
    return f"[0x{addr:06x}]"

# ---- .prof parse (layout per vscode-amiga-debug profile.ts) -------------------
def parse_prof(path):
    buf = open(path, "rb").read(); o = [0]
    def u32():
        v = struct.unpack_from("<I", buf, o[0])[0]; o[0] += 4; return v
    num_frames = u32(); section_count = u32()
    o[0] += 4 * section_count           # section bases
    o[0] += 16                          # systemStack lo/hi, stack lo/hi
    return _parse_frames(buf, o, num_frames)

def _skip_blob(buf, o):
    n = struct.unpack_from("<I", buf, o[0])[0]; o[0] += 4 + n

def _parse_frames(buf, o, num_frames):
    # frame-0-only memory dump: kick, chipmem, bogomem, then baseclock+cpucycleunit
    _skip_blob(buf, o)                  # kickstart rom
    _skip_blob(buf, o)                  # chip mem
    _skip_blob(buf, o)                  # bogo mem
    o[0] += 8                           # baseClock + cpuCycleUnit
    def u32():
        v = struct.unpack_from("<I", buf, o[0])[0]; o[0] += 4; return v
    frames = []
    for _ in range(num_frames):
        _skip_blob(buf, o)              # custom regs blob (len-prefixed)
        _skip_blob(buf, o)              # aga colors blob (len-prefixed)
        dl = u32(); dc = u32(); o[0] += dl * dc         # dma records
        rl = u32(); rc = u32(); o[0] += rl * rc         # resources
        o[0] += 8                       # profileCycles + idleCycles
        pcount = u32()
        arr = list(struct.unpack_from("<%dI" % pcount, buf, o[0])); o[0] += 4 * pcount
        frames.append(arr)
        ss = u32(); o[0] += 4 + ss      # screenshotType(u32) + screenshot bytes
    return frames

# ---- walk CPU stream into (stack -> cycles) ----------------------------------
def fold(frames, tvma, starts, ents):
    folded = defaultdict(int)
    for arr in frames:
        i, n = 0, len(arr)
        stack = []
        while i < n:
            p = arr[i]
            if p < 0xffff0000:          # a PC (call-stack frame), leaf-first
                stack.append(p); i += 1
            else:                       # cycles marker terminates this sample
                cyc = (0xffffffff - p) & 0xffffffff
                i += 1 + REG_COUNT      # consume marker + 17 register words
                if stack:
                    names = [resolve(pc, tvma, starts, ents) for pc in reversed(stack)]
                    folded[";".join(names)] += cyc
                else:
                    folded["[external]"] += cyc
                stack = []
    return folded

# ---- commands ----------------------------------------------------------------
def _prep(path):
    starts, ents = load_symbols(ELF)
    tvma = text_vma(ELF)
    return fold(parse_prof(path), tvma, starts, ents)

def cmd_fold(path, out=None):
    folded = _prep(path)
    lines = [f"{k} {v}" for k, v in sorted(folded.items(), key=lambda kv: -kv[1])]
    txt = "\n".join(lines) + "\n"
    if out:
        open(out, "w").write(txt); print(f"wrote {out} ({len(lines)} stacks)")
    else:
        sys.stdout.write(txt)

def cmd_top(path, n=25):
    folded = _prep(path)
    total = sum(folded.values()) or 1
    print(f"{os.path.basename(path)}: {total} CPU cycles profiled, top {n} functions:")
    for k, v in sorted(folded.items(), key=lambda kv: -kv[1])[:n]:
        leaf = k.split(";")[-1]
        print(f"  {v:>10}  {100*v/total:5.1f}%  {leaf}")

def cmd_svg(path, out=None):
    out = out or os.path.splitext(path)[0] + ".svg"
    folded = _prep(path)
    lines = "".join(f"{k} {v}\n" for k, v in sorted(folded.items(), key=lambda kv: -kv[1]))
    if not os.path.exists(FLAMEGRAPH):
        sys.stderr.write(f"FlameGraph renderer not found: {FLAMEGRAPH}\n"
                         f"(set FLAMEGRAPH_PY). Wrote folded stacks to stdout instead.\n")
        sys.stdout.write(lines); return
    title = f"SWOS AGA CPU — {os.path.basename(path)}"
    r = subprocess.run(["python3", FLAMEGRAPH, "--title", title,
                        "--countname", "cycles", "--width", "1600"],
                       input=lines, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr); return
    open(out, "w").write(r.stdout); print(f"wrote {out}")

# ---- one-shot capture WITH unwind (hierarchical) -----------------------------
GDB_PROXY  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gdb_proxy.py")
DMA_MARKER = struct.pack("<II", 58, 227 * 313)

def _gdb(cmd, t=30):
    return subprocess.run(["python3", GDB_PROXY, "cmd", cmd],
                          capture_output=True, text=True, timeout=t).stdout

def _blocks(path):
    try: buf = open(path, "rb").read()
    except OSError: return 0
    c = 0; o = 0
    while True:
        i = buf.find(DMA_MARKER, o)
        if i < 0: break
        c += 1; o = i + len(DMA_MARKER)
    return c

def cmd_unwind(out):
    n, nset = gen_unwind(ELF, out)
    print(f"wrote {out}: {n} slots ({nset} covered by DWARF FDEs), {os.path.getsize(out)} bytes")

def cmd_capture(n, out):
    """Stop the target, clear breakpoints, generate the unwind table, then
    `monitor profile N <unwind> <out>` and poll. Requires the harness up and the
    rig in the desired mode (e.g. bob-path). Same async-ack + poll rules as dma_profile."""
    unw = os.path.join(os.path.dirname(out), "swos.unwind")
    cmd_unwind(unw)
    # protocol: stopped + NO breakpoints (a breakpoint mid-profile stalls the frame)
    gdbpid = subprocess.run(["pgrep", "-f", "m68k-amiga-elf-gdb"], capture_output=True, text=True).stdout.split()
    if gdbpid:
        subprocess.run(["kill", "-INT", gdbpid[0]]); time.sleep(2)
    _gdb("delete")
    if os.path.exists(out): os.remove(out)
    _gdb(f'monitor profile {n} "{unw}" "{out}"', t=30)   # instant ack; runs async
    deadline = time.time() + n * 90 + 90
    while time.time() < deadline:
        if _blocks(out) >= n:
            time.sleep(1); print(f"captured {out} ({_blocks(out)} frame block(s))"); return True
        time.sleep(2)
    print(f"capture FAILED/timed out (band path stalls under cycle-exact — use bob path)")
    return False

def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return
    cmd = a[0]
    if cmd == "top":       cmd_top(a[1], int(a[2]) if len(a) > 2 else 25)
    elif cmd == "fold":    cmd_fold(a[1], a[2] if len(a) > 2 else None)
    elif cmd == "svg":     cmd_svg(a[1], a[2] if len(a) > 2 else None)
    elif cmd == "unwind":  cmd_unwind(a[1])
    elif cmd == "capture": cmd_capture(int(a[1]), a[2])
    else: print(__doc__)

main()
