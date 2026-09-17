# Zorro expansion and AUTOCONFIG

Zorro II/III address spaces, the AUTOCONFIG handshake, and how software finds boards.

Expansion boards (RAM, SCSI, graphics, network) are placed in the address space by software at
boot, not by jumpers. **Application code never configures boards and never probes for them:**
ask expansion.library, which already did the work.

## Buses and address spaces

| | Zorro II (A2000; A500/A1000 86-pin side connector is similar) | Zorro III (A3000, A4000) |
|---|---|---|
| Data / address width | 16-bit data, 24-bit address (68000 bus cycle) | 32-bit multiplexed address/data |
| Memory space | `$00200000`-`$009FFFFF` (8 MB) | NDK: `$40000000`-`$7FFFFFFF`; HRM A3000 map: `$10000000`-`$7FFFFFFF` |
| I/O space | `$00E80000`-`$00EFFFFF`; A3000 also `$00A00000`-`$00B7FFFF` | same 32-bit area |
| Configuration area | `$00E80000` (64K) | `$FF000000` (64K), or `$00E80000` in Zorro II style |
| NDK constants (`libraries/configregs.i`) | `E_MEMORYBASE`, `E_EXPANSIONBASE` | `EZ3_EXPANSIONBASE`, `EZ3_CONFIGAREA` |

Zorro III slots also accept Zorro II boards (the bus switches cycle type by address). A
bus-master board can only rely on DMA access to chip RAM; other motherboard resources are
implementation specific.

## The AUTOCONFIG handshake (outline)

1. At reset every board is unconfigured and ignores the bus; its /CFGOUT is negated.
2. Slot 0's /CFGIN is asserted. That one board answers in the configuration area.
3. The OS reads the board's read-only "ExpansionRom" registers: type, size, product,
   manufacturer, serial, optional boot ROM vector.
4. The OS either writes a base address (the write of the final address register configures the
   board) or writes the shut-up register (board disappears until reset, if allowed).
5. The board asserts /CFGOUT, which asserts the next slot's /CFGIN (empty slots pass it
   through). Repeat until no board answers.

Register encoding: every logical register is one byte made of two nibbles at paired addresses
(Zorro II: offset `n` and `n+2`, value in the top 4 bits of each word); all read registers
except `er_Type` are **stored inverted**.

| Logical offset | NDK field | Content |
|---|---|---|
| `$00` | `er_Type` | bits 7-6 board type (`%11` Zorro II, `%10` Zorro III), bit 5 `ERTB_MEMLIST` (link RAM into the free list), bit 4 `ERTB_DIAGVALID` (boot ROM), bit 3 `ERTB_CHAINEDCONFIG` (next board is on the same card), bits 2-0 size code |
| `$04` | `er_Product` | product number (manufacturer's choice) |
| `$08` | `er_Flags` | bit 7 `ERFB_MEMSPACE`, bit 6 `ERFB_NOSHUTUP`, bit 5 `ERFB_EXTENDED` (Z3 size table), bit 4 `ERFB_ZORRO_III`, bits 3-0 Z3 sub-size |
| `$10`-`$14` | `er_Manufacturer` | 16-bit manufacturer ID (assigned by Commodore/Amiga) |
| `$18`-`$24` | `er_SerialNumber` | 32-bit serial |
| `$28`-`$2C` | `er_InitDiagVec` | offset of the DiagArea (boot ROM) from the board base |
| `$44` | `ec_Z3_HighBase` | write: address bits 31-24 (Zorro III) |
| `$48` | `ec_BaseAddress` | write: address bits 23-16 -- configures the board |
| `$4C` | `ec_Shutup` | write anything: shut the board up |

Size code (bits 2-0 of `er_Type`): `000` 8 MB, `001` 64K, `010` 128K, `011` 256K, `100` 512K,
`101` 1 MB, `110` 2 MB, `111` 4 MB. With `ERFB_EXTENDED` (Zorro III) the same codes mean 16 MB
... 1 GB.

## Finding boards the right way: expansion.library

`FindConfigDev(oldConfigDev, manufacturer, product)` -- expansion LVO -72 (`-$48`),
A0 = previous ConfigDev or NULL, D0 = manufacturer, D1 = product; returns a `struct ConfigDev *`
in D0 or NULL. Pass -1 to match any manufacturer/product (unverified: from the standard
autodoc, not in the local sources).

`struct ConfigDev` (`libraries/configvars.i`): `cd_Rom` (a copy of the ExpansionRom, already
de-inverted), `cd_BoardAddr` (APTR), `cd_BoardSize` (ULONG), `cd_Flags` (`CDB_SHUTUP`,
`CDB_CONFIGME`, `CDB_BADMEMORY`), `cd_Driver`.

```asm
        include "libraries/configvars.i"
        include "lvo/exec_lib.i"
        include "lvo/expansion_lib.i"

MANUF   equ     2011                    ; the reserved "hacker" test ID ($7DB)
PROD    equ     1

FindBoard:
        move.l  4.w,a6
        lea     expname(pc),a1
        moveq   #0,d0
        jsr     _LVOOpenLibrary(a6)
        tst.l   d0
        beq.s   .none
        move.l  d0,a6
        sub.l   a0,a0                   ; start of the list
        move.l  #MANUF,d0
        moveq   #PROD,d1
        jsr     _LVOFindConfigDev(a6)
        move.l  d0,d2                   ; ConfigDev or 0
        beq.s   .close
        move.l  d0,a0
        move.l  cd_BoardAddr(a0),boardaddr
.close  move.l  a6,a1
        move.l  4.w,a6
        jsr     _LVOCloseLibrary(a6)
        move.l  d2,d0
.none   rts

expname: dc.b   "expansion.library",0
        even

        section vars,bss
boardaddr: ds.l 1
```

## Rules

- Never write to `$E80000`/`$FF000000` from an application: you would configure or shut up a
  board behind the OS's back.
- Never assume a board's address; it depends on slot order and the other boards.
- Fast RAM from boards is already in the memory lists: allocate it with `AllocMem`.
- Drivers claim boards (clear `CDB_CONFIGME`); an application only reads `cd_BoardAddr` of a
  board it knows how to talk to.
