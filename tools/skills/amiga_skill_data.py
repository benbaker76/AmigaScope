#!/usr/bin/env python3
"""Generate and validate the ground-truth data behind the Amiga agent skills.

The function entries in .agents/skills/amiga-os and amiga-ahi start with a generated
three-line "fact block" (heading, C prototype + LVO, register assignment). The facts come
from the NDK, never from prose, and this tool keeps them honest.

  amiga_skill_data.py gen   --ndk NDK_3.9 [--ahi-sfd ahi_lib.sfd --ahi-sub-sfd ahi_sub_lib.sfd]
      Rebuild amiga-os/reference/data/<lib>.tsv (exec, dos, graphics, intuition, diskfont)
      from the NDK 3.9 SFD files + clib prototypes, and amiga-ahi/reference/data/*.tsv from
      the AHI developer kit SFDs.
  amiga_skill_data.py facts LIB
      Print the fact blocks for LIB (from the committed TSV) - paste them unchanged.
  amiga_skill_data.py check
      Validate every skill Markdown file: relative links and #anchors resolve, every
      function in the TSVs has exactly one entry whose fact block matches byte for byte.

Paths default to the repo layout (run from anywhere).
"""
import argparse, collections, glob, os, re, sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SKILLS = os.path.join(REPO, '.agents', 'skills')
OS_LIBS = ['exec', 'dos', 'graphics', 'intuition', 'diskfont', 'utility', 'layers', 'lowlevel', 'timer', 'input', 'cia', 'potgo']
# lib -> (tsv path, markdown files that must contain its entries)
def targets():
    t = {l: (f'{SKILLS}/amiga-os/reference/data/{l}.tsv',
             glob.glob(f'{SKILLS}/amiga-os/reference/{l}/*.md')) for l in OS_LIBS}
    t['ahi'] = (f'{SKILLS}/amiga-ahi/reference/data/ahi.tsv', [f'{SKILLS}/amiga-ahi/reference/functions.md'])
    t['ahi_sub'] = (f'{SKILLS}/amiga-ahi/reference/data/ahi_sub.tsv', [f'{SKILLS}/amiga-ahi/reference/topics/drivers.md'])
    return t

COLS = ['lvo', 'hex', 'function', 'registers', 'returns', 'prototype', 'aliases', 'visibility']

# ---------------------------------------------------------------- SFD parsing
def parse_sfd(path):
    """Return functions in bias order: name, bias, ret, args [(decl, name, reg)], private, aliases."""
    lines = open(path, encoding='latin-1').read().replace('\r', '').split('\n')
    bias, private, alias_next, out, i = 30, False, False, [], 0
    while i < len(lines):
        l = lines[i]; i += 1
        if l.startswith('==bias'): bias = int(l.split()[1]); continue
        if l.startswith('==reserve'): bias += 6 * int(l.split()[1]); continue
        if l.startswith('==private'): private = True; continue
        if l.startswith('==public'): private = False; continue
        if l.startswith('==varargs') or l.startswith('==alias'): alias_next = True; continue
        if l.startswith('==') or l.startswith('*') or not l.strip(): continue
        while not re.search(r'\)\s*\(([^()]*)\)\s*$', l):
            l += ' ' + lines[i].strip(); i += 1
        m = re.match(r'\s*(.*?)\s*(\w+)\s*\((.*)\)\s*\(([^()]*)\)\s*$', l)
        ret, name, args, regs = m.groups()
        ret = re.sub(r'\s+', ' ', ret)
        if alias_next:
            alias_next = False; out[-1]['aliases'].append(name); continue
        decls = [re.sub(r'\s+', ' ', a.strip()) for a in split_top(args)] if args.strip() else []
        rg = [r.strip().upper() for r in re.split(r'[,/]', regs) if r.strip()]
        out.append({'name': name, 'bias': bias, 'ret': ret.strip(), 'private': private, 'aliases': [],
                    'args': [(d, arg_name(d), r) for d, r in zip(decls, rg)]})
        bias += 6
    return out

def arg_name(decl):
    fp = re.search(r'\(\s*\*\s*(?:CONST\s+|const\s+)?(\w+)\s*\)', decl)   # function pointer: (*name)(...)
    return fp.group(1) if fp else re.findall(r'\w+', decl)[-1]

def split_top(s):
    out, depth, cur = [], 0, ''
    for ch in s:
        depth += ch in '(['; depth -= ch in ')]'
        if ch == ',' and depth == 0: out.append(cur); cur = ''
        else: cur += ch
    return out + [cur]

def clib_protos(path):
    txt = re.sub(r'/\*.*?\*/', '', open(path, encoding='latin-1').read().replace('\r', ''), flags=re.S)
    protos = {}
    for m in re.finditer(r'([A-Za-z_][\w \*]*?[\s\*])(\w+)\s*\(([^;{]*?)\)\s*;', txt):
        p = re.sub(r'\s+', ' ', m.group(1).strip() + ' ' + m.group(2) + '(' + m.group(3) + ')')
        protos[m.group(2)] = re.sub(r'\(\s+', '(', re.sub(r'\s+\)', ')', p))
    return protos

def write_tsv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as o:
        o.write('\t'.join(COLS) + '\n')
        for r in rows: o.write('\t'.join(str(r[c]) for c in COLS) + '\n')

def rows_from_sfd(funcs, protos=None):
    rows = []
    for f in funcs:
        if f['private'] and protos is None: continue          # AHI: public API only
        if protos is not None and f['name'] not in protos: continue  # OS: public = has clib prototype
        proto = protos[f['name']] if protos is not None else f"{f['ret']} {f['name']}({', '.join(d for d, _, _ in f['args'])})"
        rows.append({'lvo': -f['bias'], 'hex': f"-${f['bias']:X}", 'function': f['name'],
                     'registers': ', '.join(f'{n}={r}' for _, n, r in f['args']) or 'none',
                     'returns': f['ret'], 'prototype': proto, 'aliases': ','.join(f['aliases']),
                     'visibility': 'private' if f['private'] else 'public'})
    return rows

def cmd_gen(a):
    t = targets()
    for lib in OS_LIBS:
        funcs = parse_sfd(f'{a.ndk}/Include/sfd/{lib}_lib.sfd')
        protos = clib_protos(f'{a.ndk}/Include/include_h/clib/{lib}_protos.h')
        # C argument names follow the clib prototype, not the SFD
        for f in funcs:
            if f['name'] in protos:
                names = [arg_name(d) for d in split_top(re.search(r'\((.*)\)$', protos[f['name']]).group(1)) if d.strip() and d.strip() != 'VOID']
                if len(names) == len(f['args']):
                    f['args'] = [(d, n, r) for (d, _, r), n in zip(f['args'], names)]
        rows = rows_from_sfd(funcs, protos)
        write_tsv(t[lib][0], rows); print(f'{lib}: {len(rows)} functions -> {t[lib][0]}')
    for lib, sfd in (('ahi', a.ahi_sfd), ('ahi_sub', a.ahi_sub_sfd)):
        if sfd:
            rows = rows_from_sfd(parse_sfd(sfd))
            write_tsv(t[lib][0], rows); print(f'{lib}: {len(rows)} functions -> {t[lib][0]}')

# ---------------------------------------------------------------- fact blocks
def read_tsv(path):
    with open(path, encoding='utf-8') as f:
        hdr = f.readline().rstrip('\n').split('\t')
        return [dict(zip(hdr, l.rstrip('\n').split('\t'))) for l in f if l.strip()]

def fact(r, lib):
    void = r['returns'] in ('void', 'VOID')
    alias = f" (varargs form: {r['aliases'].replace(',', ', ')})" if lib.startswith('ahi') and r['aliases'] else ''
    return (f"## {r['function']}",
            f"`{r['prototype']}` — LVO {r['lvo']} ({r['hex']}){alias}",
            f"Registers: {r['registers']}; {'no result' if void else 'result in D0'}")

def cmd_facts(a):
    for r in sorted(read_tsv(targets()[a.lib][0]), key=lambda r: r['function'].lower()):
        print('\n'.join(fact(r, a.lib)) + '\n')

# ---------------------------------------------------------------- checking
def slug(h):
    h = re.sub(r'[^\w\- ]', '', h.replace('`', '').strip().lower())
    return h.replace(' ', '-')

def code_blanked(text):
    out, fence = [], False
    for line in text.split('\n'):
        if re.match(r'^\s*(```|~~~)', line): fence = not fence; out.append(''); continue
        out.append('' if fence else line)
    return out

def anchors(path, cache={}):
    if path not in cache:
        seen, res = collections.Counter(), set()
        for line in code_blanked(open(path, encoding='utf-8').read()):
            m = re.match(r'^#{1,6}\s+(.*?)\s*#*\s*$', line)
            if m:
                s = slug(m.group(1)); res.add(f'{s}-{seen[s]}' if seen[s] else s); seen[s] += 1
        cache[path] = res
    return cache[path]

def cmd_check(a):
    bad = collections.defaultdict(list)
    files = sorted(glob.glob(f'{SKILLS}/**/*.md', recursive=True))
    for f in files:
        rel = os.path.relpath(f, REPO)
        for i, line in enumerate(code_blanked(open(f, encoding='utf-8').read()), 1):
            for m in re.finditer(r'(?<!!)\[[^\]]*\]\(([^)\s]+)\)', re.sub(r'`[^`]*`', '', line)):
                tgt = m.group(1)
                if re.match(r'^[a-z]+:', tgt): continue
                p, _, anc = tgt.partition('#')
                dest = os.path.normpath(os.path.join(os.path.dirname(f), p)) if p else f
                if not os.path.exists(dest): bad['broken link'].append(f'{rel}:{i} -> {tgt}')
                elif anc and dest.endswith('.md') and anc not in anchors(dest):
                    bad['missing anchor'].append(f'{rel}:{i} -> {tgt}')
                elif not dest.startswith(os.path.join(SKILLS, rel.split(os.sep)[2])):
                    bad['cross-skill path link'].append(f'{rel}:{i} -> {tgt}')
    for lib, (tsv, docs) in targets().items():
        if not os.path.exists(tsv): continue
        want = {r['function']: fact(r, lib) for r in read_tsv(tsv)}
        seen = collections.Counter()
        for d in docs:
            if not os.path.exists(d): continue
            L = open(d, encoding='utf-8').read().split('\n')
            for i, line in enumerate(L):
                m = re.match(r'^## (\w+)\s*$', line)
                if not (m and m.group(1) in want and i + 1 < len(L) and ' — LVO ' in L[i + 1]): continue
                n = m.group(1); seen[n] += 1
                got = tuple(L[i:i + 3])
                if got != want[n]:
                    bad[f'{lib}: fact block differs'].append(f'{os.path.relpath(d, REPO)}:{i + 1} {n}\n      want {want[n][1:]}\n      got  {got[1:]}')
        for n in want:
            if seen[n] == 0: bad[f'{lib}: no entry'].append(n)
            if seen[n] > 1: bad[f'{lib}: duplicate entry'].append(n)
    for k, v in bad.items():
        print(f'{k}: {len(v)}')
        for x in v[:a.limit]: print('  ' + x)
    print(f'{len(files)} files checked, {sum(map(len, bad.values()))} problem(s)')
    return 1 if bad else 0

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    g = sub.add_parser('gen'); g.add_argument('--ndk', required=True)
    g.add_argument('--ahi-sfd'); g.add_argument('--ahi-sub-sfd')
    f = sub.add_parser('facts'); f.add_argument('lib', choices=OS_LIBS + ['ahi', 'ahi_sub'])
    c = sub.add_parser('check'); c.add_argument('--limit', type=int, default=40)
    a = ap.parse_args()
    sys.exit({'gen': cmd_gen, 'facts': cmd_facts, 'check': cmd_check}[a.cmd](a) or 0)

if __name__ == '__main__':
    main()
