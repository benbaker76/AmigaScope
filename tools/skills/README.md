# Skill maintenance tools

Scripts that keep the generated parts of `.agents/skills/` correct. Python 3.6+, no
dependencies.

## amiga_skill_data.py

```sh
# regenerate the LVO/register tables from an NDK 3.9 checkout (and the AHI SDK SFDs)
python3 tools/skills/amiga_skill_data.py gen --ndk /path/to/NDK_3.9 \
    --ahi-sfd /path/to/AHI/Developer/Include/SFD/ahi_lib.sfd \
    --ahi-sub-sfd /path/to/AHI/Developer/Include/SFD/ahi_sub_lib.sfd

# print the fact blocks for a library (paste them unchanged at the top of each entry)
python3 tools/skills/amiga_skill_data.py facts graphics

# validate everything: links, anchors, and that every function has exactly one entry
# whose three-line fact block matches the TSV byte for byte (exit status 1 on problems)
python3 tools/skills/amiga_skill_data.py check
```

`gen` writes `amiga-os/reference/data/<lib>.tsv` (exec, dos, graphics, intuition, diskfont,
utility, layers, lowlevel, timer, input, cia, potgo - see `OS_LIBS`) from the
NDK 3.9 `Include/sfd/*_lib.sfd` (LVO, registers, aliases, private slots) and
`Include/include_h/clib/*_protos.h` (C prototype and argument names), and
`amiga-ahi/reference/data/{ahi,ahi_sub}.tsv` from the AHI SFDs. Only functions with a clib
prototype are public; aliases (e.g. `System` for `SystemTagList`) share an LVO and are
listed in the `aliases` column instead of getting their own entry.

A function entry always starts with its fact block:

```markdown
## AllocMem
`APTR AllocMem(ULONG byteSize, ULONG requirements)` — LVO -198 (-$C6)
Registers: byteSize=D0, requirements=D1; result in D0
```

## build_indexes.py

```sh
python3 tools/skills/build_indexes.py
```

Rewrites every `reference/index.md`, the function tables at the end of
`amiga-os/reference/<lib>/index.md` (everything above their `<!-- FUNCTION TABLE -->`
marker is hand-written and kept), and refreshes the chipset/access/description/entry
columns of `amiga-hardware/reference/data/registers.tsv` from the register entries.
Summaries come from the first prose sentence after each `##` heading, so keep that
sentence short. Run it after editing entries, then run `amiga_skill_data.py check`.

## Authoring conventions

- Entries are `## Name` headings; series use a lowercase `x` placeholder (`SPRxPOS`,
  `BPLxPTH, BPLxPTL`, `COLORxx`, `Bcc`).
- Links stay inside a skill (relative paths); refer to another skill by name only.
- Rewrite sources in your own words; reproduce only facts (names, addresses, bits, LVOs,
  syntax). Record source conflicts and unverifiable claims in `reference/errata.md` and mark
  the claim `(unverified)` in the entry.
