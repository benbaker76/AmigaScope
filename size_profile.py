#!/usr/bin/env python3
"""AmigaScope size profiler — where the bytes go in your Amiga executable.

Breaks the binary down by **functions**, **data**, and **references** (relocations),
the way vscode-amiga-debug's Size Profiler does, straight from the ELF symbol table +
relocations (objdump). Text report, folded-by-size stacks, or a size flame-graph SVG
(box width = bytes, via the bundled FlameGraph).

  size_profile.py report <elf> [N]     # section totals + top-N functions + top-N data + relocs
  size_profile.py fold   <elf> [out]   # folded stacks weighted by BYTES (for FlameGraph)
  size_profile.py svg    <elf> [out]   # size flame graph SVG

ELF defaults to $AMIGASCOPE_ELF. Objdump: $M68K_OBJDUMP.
"""
import subprocess, sys, os
from collections import defaultdict

OBJDUMP    = os.environ.get("M68K_OBJDUMP", "m68k-amiga-elf-objdump")
_HERE      = os.path.dirname(os.path.abspath(__file__))
FLAMEGRAPH = os.environ.get("FLAMEGRAPH_PY",
                            os.path.join(_HERE, "third_party", "FlameGraph", "flamegraph.py"))

def _elf(argv_elf):
    return argv_elf or os.environ.get("AMIGASCOPE_ELF") or ""

def symbols(elf):
    """List of (section, size, name, kind) for every sized symbol. kind: func|data|other."""
    out = subprocess.run([OBJDUMP, "-t", elf], capture_output=True, text=True, timeout=120).stdout
    syms = []
    for line in out.splitlines():
        if "\t" not in line:
            continue
        left, right = line.split("\t", 1)                 # left=flags+section, right="SIZE name"
        lt = left.split()
        sec = next((t for t in lt if t.startswith(".")), None)
        if not sec:
            continue
        # C emits F(unction)/O(bject) types; assembler labels are untyped, so fall back
        # to the section: anything in .text is code, everything else is data.
        if "F" in lt:      kind = "func"
        elif "O" in lt:    kind = "data"
        elif sec == ".text": kind = "func"
        else:              kind = "data"
        try:
            size = int(right.split()[0], 16)
            name = right.split(None, 1)[1]
        except (ValueError, IndexError):
            continue
        if size > 0:
            syms.append((sec, size, name, kind))
    return syms

def sections(elf):
    """{name: (vma, size)} from objdump -h."""
    out = subprocess.run([OBJDUMP, "-h", elf], capture_output=True, text=True, timeout=60).stdout
    secs = {}
    for line in out.splitlines():
        p = line.split()
        if len(p) >= 4 and p[1].startswith("."):
            try: secs[p[1]] = (int(p[3], 16), int(p[2], 16))
            except ValueError: pass
    return secs

def relocations(elf):
    """(count, {target_name: count}) across all sections (the 'references')."""
    out = subprocess.run([OBJDUMP, "-r", elf], capture_output=True, text=True, timeout=120).stdout
    per = defaultdict(int); total = 0
    for line in out.splitlines():
        p = line.split()
        # "OFFSET  TYPE  SYMBOL[+addend]"
        if len(p) >= 3 and p[0][:1].isdigit() and p[1].startswith("R_"):
            total += 1
            per[p[2].split("+")[0]] += 1
    return total, per

def report(elf, n=20):
    secs = sections(elf); syms = symbols(elf)
    funcs = sorted([s for s in syms if s[3] == "func"], key=lambda s: -s[1])
    data  = sorted([s for s in syms if s[3] == "data"], key=lambda s: -s[1])
    tot_f = sum(s[1] for s in funcs); tot_d = sum(s[1] for s in data)
    total, per = relocations(elf)
    print(f"{os.path.basename(elf)} — size profile\n")
    print("Sections:")
    for name in (".text", ".rodata", ".data", ".bss"):
        if name in secs:
            print(f"  {name:8} {secs[name][1]:>10,} bytes")
    print(f"\nFunctions: {len(funcs):,} symbols, {tot_f:,} bytes")
    for sec, size, name, _ in funcs[:n]:
        print(f"  {size:>8,}  {name}")
    print(f"\nData: {len(data):,} symbols, {tot_d:,} bytes")
    for sec, size, name, _ in data[:n]:
        print(f"  {size:>8,}  {name}  [{sec}]")
    print(f"\nReferences (relocations): {total:,} total. Most-referenced symbols:")
    for name, c in sorted(per.items(), key=lambda kv: -kv[1])[:n]:
        print(f"  {c:>6}x  {name}")

def fold(elf, out=None):
    syms = symbols(elf)
    lines = []
    for sec, size, name, kind in sorted(syms, key=lambda s: -s[1]):
        bucket = {"func": "functions", "data": "data"}.get(kind, "other")
        lines.append(f"{bucket};{sec};{name} {size}")
    txt = "\n".join(lines) + "\n"
    if out:
        open(out, "w").write(txt); print(f"wrote {out} ({len(lines)} symbols)")
    else:
        sys.stdout.write(txt)

def _bucket(kind):
    return {"func": "functions", "data": "data"}.get(kind, "other")

def svg(elf, out=None):
    out = out or (os.path.splitext(elf)[0] + ".size.svg")
    syms = symbols(elf)
    folded = "".join(f"{_bucket(kind)};{sec};{name} {size}\n"
                     for sec, size, name, kind in sorted(syms, key=lambda s: -s[1]))
    if not os.path.exists(FLAMEGRAPH):
        sys.stderr.write(f"FlameGraph not found: {FLAMEGRAPH}\n"); sys.stdout.write(folded); return
    r = subprocess.run(["python3", FLAMEGRAPH, "--title", f"Size — {os.path.basename(elf)}",
                        "--countname", "bytes", "--width", "1600", "--colors", "mem"],
                       input=folded, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr); return
    open(out, "w").write(r.stdout); print(f"wrote {out}")

def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return
    cmd = a[0]
    if cmd == "report":  report(_elf(a[1] if len(a) > 1 else None), int(a[2]) if len(a) > 2 else 20)
    elif cmd == "fold":  fold(_elf(a[1] if len(a) > 1 else None), a[2] if len(a) > 2 else None)
    elif cmd == "svg":   svg(_elf(a[1] if len(a) > 1 else None), a[2] if len(a) > 2 else None)
    else: print(__doc__)

if __name__ == "__main__":
    main()
