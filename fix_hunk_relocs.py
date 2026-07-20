#!/usr/bin/env python3
"""
fix_hunk_relocs.py - Fix elf2hunk PC32 relocation bug

elf2hunk (bundled with Amiga Debug Extension 1.8.1) incorrectly emits
R_68K_PC32 (PC-relative 32-bit) relocations as HUNK_RELOC32 entries.
This causes the Amiga loader to add the hunk base address to PC-relative
displacement fields in BRA.L and BSR.L instructions, corrupting them.

This script post-processes the hunk file to remove these erroneous entries.

Usage: python3 fix_hunk_relocs.py <elf_file> <hunk_file> [output_file]

If output_file is not specified, the hunk_file is modified in place.
"""

import struct
import sys
import os


def read_long(data, pos):
    return struct.unpack('>I', data[pos:pos+4])[0], pos + 4


def get_pc32_offsets(elf_path):
    """Extract section-relative offsets of all R_68K_PC32 relocations from the ELF."""
    with open(elf_path, 'rb') as f:
        elf = f.read()

    # Parse ELF header
    e_type = struct.unpack('>H', elf[16:18])[0]
    e_shoff = struct.unpack('>I', elf[32:36])[0]
    e_shentsize = struct.unpack('>H', elf[46:48])[0]
    e_shnum = struct.unpack('>H', elf[48:50])[0]

    # Find all SHT_RELA sections targeting allocatable sections
    pc32_offsets = set()
    sections = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        sh = struct.unpack('>IIIIIIIIII', elf[off:off+40])
        sections.append(sh)

    for i in range(e_shnum):
        sh_type = sections[i][1]
        if sh_type != 4:  # SHT_RELA
            continue

        target_section = sections[i][7]  # sh_info = target section
        if not (sections[target_section][2] & 2):  # SHF_ALLOC
            continue

        target_addr = sections[target_section][3]  # sh_addr (VMA)
        rela_off = sections[i][4]    # sh_offset
        rela_size = sections[i][5]   # sh_size
        rela_entsize = sections[i][9]  # sh_entsize

        num_rela = rela_size // rela_entsize
        for j in range(num_rela):
            pos = rela_off + j * rela_entsize
            r_offset, r_info, r_addend = struct.unpack('>IIi', elf[pos:pos+12])
            r_type = r_info & 0xff
            if r_type == 4:  # R_68K_PC32
                section_rel_offset = r_offset - target_addr
                pc32_offsets.add(section_rel_offset)

    return pc32_offsets


def fix_hunk_file(hunk_path, pc32_offsets, output_path):
    """Remove PC32 relocation entries from HUNK_RELOC32 blocks."""
    with open(hunk_path, 'rb') as f:
        hunk = f.read()

    output = bytearray()
    pos = 0

    # HUNK_HEADER
    htype, pos = read_long(hunk, pos)
    if htype != 0x3F3:
        print(f"Error: not a valid Amiga hunk file (got 0x{htype:X})", file=sys.stderr)
        return False
    output += hunk[0:4]

    # Resident library names (copy verbatim)
    while True:
        n, new_pos = read_long(hunk, pos)
        if n == 0:
            output += hunk[pos:new_pos]
            pos = new_pos
            break
        pos = new_pos + n * 4
        output += hunk[pos - n * 4 - 4:pos]

    # table_size, first_hunk, last_hunk
    ts, pos = read_long(hunk, pos)
    output += hunk[pos-4:pos]
    fh, pos = read_long(hunk, pos)
    output += hunk[pos-4:pos]
    lh, pos = read_long(hunk, pos)
    output += hunk[pos-4:pos]

    # Hunk sizes
    for i in range(ts):
        sz, pos = read_long(hunk, pos)
        mem = (sz >> 30) & 3
        output += hunk[pos-4:pos]
        if mem == 3:
            _, pos = read_long(hunk, pos)
            output += hunk[pos-4:pos]

    # Process hunks
    hunk_num = 0
    total_removed = 0

    while pos < len(hunk) - 3:
        htype, new_pos = read_long(hunk, pos)
        htype_base = htype & 0x3FFFFFFF

        if htype_base in (0x3E9, 0x3EA):  # HUNK_CODE, HUNK_DATA
            sz, new_pos = read_long(hunk, new_pos)
            data_end = new_pos + sz * 4
            output += hunk[pos:data_end]
            pos = data_end
            hunk_num += 1

        elif htype_base == 0x3EB:  # HUNK_BSS
            sz, new_pos = read_long(hunk, new_pos)
            output += hunk[pos:new_pos]
            pos = new_pos
            hunk_num += 1

        elif htype_base == 0x3EC:  # HUNK_RELOC32
            new_pos = pos + 4
            entries = {}
            while True:
                cnt, new_pos = read_long(hunk, new_pos)
                if cnt == 0:
                    break
                tgt, new_pos = read_long(hunk, new_pos)
                if tgt not in entries:
                    entries[tgt] = []
                for j in range(cnt):
                    off, new_pos = read_long(hunk, new_pos)
                    entries[tgt].append(off)

            # Filter: remove PC32 offsets for same-hunk relocations
            filtered_entries = {}
            for tgt, offsets in entries.items():
                if tgt == hunk_num - 1:  # same-hunk relocation
                    filtered = [off for off in offsets if off not in pc32_offsets]
                    removed = len(offsets) - len(filtered)
                    total_removed += removed
                    if filtered:
                        filtered_entries[tgt] = filtered
                else:
                    filtered_entries[tgt] = offsets

            # Write filtered HUNK_RELOC32
            output += struct.pack('>I', 0x3EC)
            for tgt in sorted(filtered_entries.keys()):
                offsets = filtered_entries[tgt]
                output += struct.pack('>I', len(offsets))
                output += struct.pack('>I', tgt)
                for off in offsets:
                    output += struct.pack('>I', off)
            output += struct.pack('>I', 0)  # terminator

            pos = new_pos

        elif htype_base == 0x3F0:  # HUNK_SYMBOL
            new_pos = pos + 4
            while True:
                n, new_pos = read_long(hunk, new_pos)
                if n == 0:
                    break
                new_pos += n * 4 + 4  # name + value
            output += hunk[pos:new_pos]
            pos = new_pos

        elif htype_base == 0x3F2:  # HUNK_END
            output += hunk[pos:pos+4]
            pos += 4

        else:
            # Unknown hunk type - copy remaining data
            output += hunk[pos:]
            pos = len(hunk)
            break

    with open(output_path, 'wb') as f:
        f.write(output)

    return total_removed


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <elf_file> <hunk_file> [output_file]")
        sys.exit(1)

    elf_path = sys.argv[1]
    hunk_path = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else hunk_path

    pc32_offsets = get_pc32_offsets(elf_path)
    if not pc32_offsets:
        # No PC32 relocations to fix
        if output_path != hunk_path:
            with open(hunk_path, 'rb') as f:
                data = f.read()
            with open(output_path, 'wb') as f:
                f.write(data)
        sys.exit(0)

    removed = fix_hunk_file(hunk_path, pc32_offsets, output_path)
    if removed > 0:
        print(f"fix_hunk_relocs: removed {removed} erroneous PC32 HUNK_RELOC32 entries")
    sys.exit(0)


if __name__ == '__main__':
    main()
