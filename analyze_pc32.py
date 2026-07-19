#!/usr/bin/env python3
"""Analyze R_68K_PC32 relocations in the ELF to understand why elf2hunk's
fix doesn't filter them out. Checks sym.shindex vs shrel->info."""

import struct
import sys

R_68K_PC32 = 4

def read_elf(path):
    with open(path, 'rb') as f:
        data = f.read()

    # ELF header (32-bit big-endian), 52 bytes total
    # e_ident[16], e_type(2), e_machine(2), e_version(4),
    # e_entry(4), e_phoff(4), e_shoff(4), e_flags(4),
    # e_ehsize(2), e_phentsize(2), e_phnum(2),
    # e_shentsize(2), e_shnum(2), e_shstrndx(2)
    (e_type, e_machine, e_version, e_entry, e_phoff, e_shoff, e_flags,
     e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx
    ) = struct.unpack_from('>HHIIIIIHHHHHH', data, 16)

    print(f"ELF type: {e_type} ({'ET_EXEC' if e_type == 2 else 'ET_REL' if e_type == 1 else '?'})")
    print(f"Section headers: {e_shnum} at offset 0x{e_shoff:x}, entry size {e_shentsize}")

    # Parse section headers
    # sh_name(4), sh_type(4), sh_flags(4), sh_addr(4),
    # sh_offset(4), sh_size(4), sh_link(4), sh_info(4),
    # sh_addralign(4), sh_entsize(4)
    sections = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        sh = struct.unpack_from('>IIIIIIIIII', data, off)
        sections.append({
            'name_idx': sh[0],
            'type': sh[1],
            'flags': sh[2],
            'addr': sh[3],
            'offset': sh[4],
            'size': sh[5],
            'link': sh[6],
            'info': sh[7],
            'addralign': sh[8],
            'entsize': sh[9],
        })

    # Get section name string table
    shstrtab_sec = sections[e_shstrndx]
    shstrtab_off = shstrtab_sec['offset']
    shstrtab_data = data[shstrtab_off:shstrtab_off + shstrtab_sec['size']]

    def get_shname(idx):
        end = shstrtab_data.index(b'\0', idx)
        return shstrtab_data[idx:end].decode('ascii', errors='replace')

    for i, s in enumerate(sections):
        s['name'] = get_shname(s['name_idx'])

    # Print all sections
    print("\nSections:")
    for i, s in enumerate(sections):
        if s['type'] != 0:
            print(f"  [{i:3d}] {s['name']:30s}  type={s['type']:2d}  addr=0x{s['addr']:08x}  size=0x{s['size']:06x}  link={s['link']}  info={s['info']}")

    # Find RELA sections (type 4)
    rela_sections = [(i, s) for i, s in enumerate(sections) if s['type'] == 4]
    print(f"\nFound {len(rela_sections)} RELA sections")

    # Find symtab
    symtab_sections = [(i, s) for i, s in enumerate(sections) if s['type'] == 2]
    if not symtab_sections:
        print("ERROR: No symtab found")
        return
    symtab_idx, symtab_sec = symtab_sections[0]
    print(f"Symtab: section [{symtab_idx}] '{symtab_sec['name']}', link={symtab_sec['link']} (strtab)")

    # Load string table for symbols
    strtab_sec = sections[symtab_sec['link']]
    strtab_data = data[strtab_sec['offset']:strtab_sec['offset'] + strtab_sec['size']]

    def get_symname(idx):
        if idx >= len(strtab_data):
            return f"<invalid:{idx}>"
        end = strtab_data.index(b'\0', idx)
        return strtab_data[idx:end].decode('ascii', errors='replace')

    # Load symbol table
    # struct symbol: name(4), value(4), size(4), info(1), other(1), shindex(2) = 16 bytes
    sym_count = symtab_sec['size'] // 16
    symbols = []
    for i in range(sym_count):
        off = symtab_sec['offset'] + i * 16
        s = struct.unpack_from('>IIIBBH', data, off)
        symbols.append({
            'name_idx': s[0],
            'value': s[1],
            'size': s[2],
            'info': s[3],
            'other': s[4],
            'shindex': s[5],
            'name': get_symname(s[0]),
        })

    # Now scan all RELA sections for R_68K_PC32
    pc32_count = 0
    same_section_count = 0
    diff_section_count = 0

    print(f"\n{'='*80}")
    print("R_68K_PC32 relocations analysis:")
    print(f"{'='*80}")

    # Track unique shindex values seen
    shindex_values = {}

    for rela_idx, rela_sec in rela_sections:
        target_section = rela_sec['info']  # This is shrel->info in elf2hunk
        target_name = sections[target_section]['name'] if target_section < len(sections) else '?'

        num_entries = rela_sec['size'] // rela_sec['entsize']

        for j in range(num_entries):
            off = rela_sec['offset'] + j * rela_sec['entsize']
            # RELA entry: r_offset(4), r_info(4), r_addend(4)
            r_offset, r_info, r_addend = struct.unpack_from('>IiI', data, off)
            r_type = r_info & 0xFF
            r_sym = (r_info >> 8) & 0xFFFFFF

            if r_type != R_68K_PC32:
                continue

            pc32_count += 1
            sym = symbols[r_sym]
            shindex = sym['shindex']

            if shindex not in shindex_values:
                sec_name = sections[shindex]['name'] if shindex < len(sections) else f'SPECIAL:0x{shindex:x}'
                shindex_values[shindex] = sec_name

            if shindex == target_section:
                same_section_count += 1
            else:
                diff_section_count += 1
                if diff_section_count <= 20:
                    sec_name = sections[shindex]['name'] if shindex < len(sections) else f'0x{shindex:x}'
                    print(f"  DIFF: r_offset=0x{r_offset:08x} sym='{sym['name'][:50]}' "
                          f"sym.shindex={shindex}({sec_name}) vs shrel->info={target_section}({target_name})")

    print(f"\n{'='*80}")
    print(f"Summary:")
    print(f"  Total R_68K_PC32 relocations: {pc32_count}")
    print(f"  Same section (shindex == shrel->info): {same_section_count}")
    print(f"  Different section (shindex != shrel->info): {diff_section_count}")
    print(f"\n  Unique sym.shindex values seen:")
    for idx, name in sorted(shindex_values.items()):
        print(f"    shindex={idx}: {name}")
    print(f"\n  RELA target sections (shrel->info):")
    for rela_idx, rela_sec in rela_sections:
        target_section = rela_sec['info']
        target_name = sections[target_section]['name'] if target_section < len(sections) else '?'
        # Count PC32 in this RELA
        num_entries = rela_sec['size'] // rela_sec['entsize']
        pc32_in_rela = 0
        for j in range(num_entries):
            off = rela_sec['offset'] + j * rela_sec['entsize']
            r_info = struct.unpack_from('>I', data, off + 4)[0]
            if (r_info & 0xFF) == R_68K_PC32:
                pc32_in_rela += 1
        if pc32_in_rela > 0:
            print(f"    RELA [{rela_idx}] '{rela_sec['name']}' -> target section [{target_section}] '{target_name}' ({pc32_in_rela} PC32 entries)")

    print(f"\n{'='*80}")
    if diff_section_count > 0:
        print("CONCLUSION: elf2hunk's fix CATCHES the cross-section PC32 relocs")
        print("  but it ERRORS OUT instead of silently skipping them!")
        print("  The 'same section' PC32 entries are the ones that should be")
        print("  skipped (no relocation needed) — and those ARE handled correctly.")
    elif same_section_count == pc32_count and same_section_count > 0:
        print("CONCLUSION: ALL PC32 relocs have shindex == shrel->info (same section)")
        print("  elf2hunk's fix should SKIP all of them (no hunk relocation).")
        print("  If they still appear in the hunk file, the fix is not being reached!")
        print("  Check: is the code compiled with the fix? Is there a different code path?")
    else:
        print("No PC32 relocations found.")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <elf-file>")
        sys.exit(1)
    read_elf(sys.argv[1])
