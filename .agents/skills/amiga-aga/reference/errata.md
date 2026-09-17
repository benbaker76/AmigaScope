# amiga-aga errata

Discrepancies found while distilling the AGA reference: disagreements between sources,
OCR ambiguities, toolchain behaviour that contradicts documentation, and statements that
could not be verified locally (these are marked "(unverified)" in the entries). Each item
records the resolution used in the reference. When sources conflict, the NDK 3.9 includes
and SFD files win for names, offsets and registers; the Commodore documentation wins for
behaviour unless a test with the bundled toolchain showed otherwise.

## AGA registers and topics

### Sources

- **mysterious-ways.txt** — the capture contains only "MYSQL Error: Unable to query database / Too many connections"; resolution: ignored, no content used.
- **aga.guide.txt** — a 1993 re-typing (Fireflash/Sponge of C18, TFA AmigaGuide) of the Commodore "Specification for the Advanced Amiga (AA) Chip Set"; treated as the AA spec. aga-registers-pdf.txt (Solo) is the same text with the same typos.

### Register layout and names

- **CLXCON2 address** — Solo PDF and the aga.guide alphabetical node say $10C (= BPLCON4); aga.guide address list, prb28 and NDK custom.i (`clxcon2 EQU $10E`) say $10E; resolution: $10E.
- **BPLCON0 plane count (BPU3)** — NDK graphics/display.h: `PLNCNTMSK` $7, "7 = reserved" (OCS view); prb28 "BPU 000-110"; Action's guide table "bits 4-7 unused"; AA spec: BPU2-0 at 14-12 plus BPU3 at bit 4, code "0000-1000"; RandyAGA: "set bit 4, bits 12-14 zero"; AmigaScope copper_disasm.py decodes BPU3 = bit 4 and SWOS AGA uses $0210 for 8-plane lores; resolution: 8 planes = bit 4 with bits 14-12 clear; 7 planes = 111. No NDK symbol for BPU3.
- **BPLCON0 bit 5** — RandyAGA labels it "BPLHWRM - screen black and white, no copcolors"; AA spec: BYPASS (BPLHWRM is BPLHSTOP bit 15); resolution: BYPASS, write 0.
- **BPLCON1 low-bit names** — RandyAGA's bit list uses OCS names PF1H0-PF1H3/PF2H0-PF2H3 for bits 3-0/7-4 and howtocode calls the playfields "0" and "1"; AA spec renamed them PF1H2-PF1H5/PF2H2-PF2H5 with PFxH1/H0 at bits 9-8/13-12 and PFxH7/H6 at 11-10/15-14; resolution: AA spec names. Verified against SWOS's $8822 (= 136 steps = 34 lores px on both playfields).
- **BPLCON2 bit 7** — RandyAGA: "SOGEN (ZDCLKEN) Enable 14Mhz clock"; AA spec: SOGEN drives the SOG pin, ZDCLKEN is BPLCON3 bit 2; resolution: AA spec.
- **BPLCON2 ZDCTEN transparency bit** — AA spec BPLCON2 table: "bit #15 of the active entry"; AA spec genlock paragraph: "the bit31 position of each color"; resolution: the T bit is bit 15 of the LOCT=0 COLORxx word (COLORxx table).
- **BPLCON2 ZDBPSEL text** — "000 selects BB1", "ZDBBPEN" (spec, prb28); resolution: plane 1, ZDBPEN.
- **BPLCON3 bit order** — RandyAGA's comment lists 10-12 = PF2OF2..PF2OF0, 13-15 = BANK0..BANK2, 6 = SPRES1, 7 = SPRES0 (all reversed); AA spec: 15-13 BANK2-0, 12-10 PF2OF2-0, 7-6 SPRES1-0; Randy's own $0C00 default, bank table (bits 15-13) and sprite table (bit 7, bit 6) agree with the spec; resolution: AA spec.
- **BPLCON3 NDK names** — hardware/custom.h (`#ifdef ECS_SPECIFIC`): bit 1 `BPLCON3_EXTBLKZD` ("external blank ored into transparency"), bit 5 `BPLCON3_BRDNBLNK` (comment "border is opaque", same comment as bit 4); AA spec: bit 1 BRDSPRT, bit 5 BRDRBLNK (border blanked); RandyAGA merges them ("BRDSPRT - EXTBLKZD"); resolution: AA meaning documented for AGA, NDK names listed as ECS-era. OS side: `CMF_BRDRSPRT`, `VTAG_BORDERSPRITE_SET`.
- **PF2OF "affected bitplane" column** — aga.guide, Solo PDF, RandyAGA and prb28 show plane 3 for both 010 and 011; resolution: 011 (offset 8) is plane 4.
- **PF2OF scope** — AA spec register text: offset applies "when playfield 2 has priority in dual playfield mode"; AA spec feature text and RandyAGA: "second playfield's offset into the color table"; resolution: documented as PF2's colour offset; whether PF2PRI must be set is unverified. The spec table shows one colour-index bit per code (OR vs ADD not stated; identical for 4-bit PF2 values with offset >= 16).
- **BPLCON3/BPLCON4 defaults** — AA spec marks PF2OF=011 and ESPRM4=OSPRM4=1 as defaults, but also says the reset input clears every bit of BPLCON3, BPLCON4, CLXCON2, DIWHIGH, FMODE; resolution: tell code to write $0C00 and $0011 explicitly (RandyAGA's reset lines).
- **BPLCON4 bit order** — RandyAGA's bplcon4 comment lists bits 0-3 as ESPRM7-4 and 4-7 as "OSPRM4" x4, and his second Yragael table swaps even/odd; AA spec: 7-4 ESPRM7-4 (even sprites), 3-0 OSPRM7-4 (odd); Randy's first Yragael table agrees with the spec; resolution: AA spec.
- **CLXCON2 text** — spec and RandyAGA: "ENBP7 and ENBP6 are the enable bits for bitplanes 7 and 8", "MPBP8"; Randy's comment "6 ENBP8 enable bitplane 7"; resolution: ENBP7 (bit 6), ENBP8 (bit 7), MVBP7 (bit 0), MVBP8 (bit 1).
- **CLXCON table (OCS register)** — spec/PDF name the plane enable/match bits ENSP1-6; they are ENBP/MVBP. Not in this skill; flagged for amiga-hardware.
- **FMODE bit 0 name** — AA spec bit table "BLP32", fetch table "BPL32"; resolution: BPL32 (doc name; no NDK symbol).
- **FMODE values** — RandyAGA: "$0003 = FULL AGA 64 bit fetch", "BANDWIDTH 2: MOVE.W #2", "if 64-bit aligned then $11"; howtocode (in Randy) lists "$00/$01/$10/$11"; AA spec: bits 1-0, 01 or 10 = 4-byte step, 11 = 8-byte step; resolution: the howtocode/Randy "$10/$11" are binary for bits 1-0; 2x = $0001 or $0002, 4x = $0003.
- **HAM8 table** — aga.guide first row "BP2=0 BP1=1 select new base register" (duplicates the blue row); RandyAGA's copy has 00; resolution: 00 = base register.
- **EHB resolutions** — AA spec: EHB "whenever SHRES = HIRES = HAMEN = DPF = 0 and BPU = 6"; AA mode tables and RandyAGA list hires and superhires EHB; NDK modeid.h has V39 `HIRESEHB_KEY`, `SUPEREHB_KEY`; resolution: EHB works in all resolutions on AGA, the HIRES/SHRES condition is OCS-era wording.
- **HBSTRT/HBSTOP fine bits** — spec table labels bit 10 "H1 140nS", bit 9 "H1 70nS", bit 8 "H0 35nS"; resolution: bit 10 = H2 (140ns), 9 = H1, 8 = H0; bits 7-0 = H10-H3 in 280ns steps.
- **LISAID "maintain as 1" bits** — AA spec: bits 3 and 0 "maintain as a 1"; same spec: ECS Denise returns $FC, Lisa $F8 (bit 0 = 0); resolution: document the returned values, do not test bit 0.
- **AGA flag bit in LISAID** — RandyAGA comment "BIT 3=AGA"; AA spec: bit 2 low = AA feature set; resolution: bit 2; the $F8 compare after OR $F0 is correct either way.
- **LISAID byte read** — RandyAGA warns against `CMPI.B #$F8,$DFF07C` for a different reason (future revisions); resolution: documented that a byte access at $DFF07C reads the high (mouse bus) byte on the big-endian 68k (standard 68k/custom-chip behaviour, not stated in the sources).
- **Detection loop count** — RandyAGA: `MOVEQ #30` + DBRA (31 compares); prb28: `moveq #31-1` + dbf (31); resolution: no required count; skill uses 32.
- **VPOSR Agnus IDs** — all sources (spec, Solo PDF, RandyAGA, prb28) print "8372 rev 5 = 22 PAL, 31 NTSC" and "Alice thru rev 2 = 22 PAL, 32 NTSC", so $22 is listed twice; the commonly quoted 8372 rev 5 PAL value $21 is not in the source set (unverified); resolution: table printed as in sources with a note; do not use the Agnus ID alone for AGA detection.
- **BEAMCON0 bit 3** — AA spec: "(unused, formerly BLANKEN)"; NDK hardware/custom.h `CSBLANK` $0008 ("Composite blank out to CSY* pin"), used by graphics/monitor.h `SPECIAL_BEAMCON`/`BROADCAST_BEAMCON`; RandyAGA "BLANKEN-CSBLANK"; resolution: both documented; write 0 for standard displays.
- **BEAMCON0 names** — AA doc names VARVBEN, CSCBEN, VARVSYEN, VARHSYEN, VARBEAMEN, DUAL, PAL, VARCSYEN, CSYTRUE, VSYTRUE, HSYTRUE vs NDK `VARVBLANK`, `CSCBLANKEN`, `VARVSYNC`, `VARHSYNC`, `VARBEAM`, `DISPLAYDUAL`, `DISPLAYPAL`, `VARCSYNC`, `CSYNCTRUE`, `VSYNCTRUE`, `HSYNCTRUE`; HARDDIS/LPENDIS have no NDK symbol; the NDK names exist only in C (custom.h under `#ifdef ECS_SPECIFIC`), not in custom.i; resolution: table gives both.
- **BEAMCON0 VARVSYEN text** — Solo PDF: VSY "set vertically on HSSTRT"; aga.guide/prb28: "on VSSTRT"; resolution: VSSTRT.
- **Sprite scan doubling** — aga.guide: when SPRxPOS V0 matches the beam V0 "the sprite's DMA is allowed to proceed", otherwise DMA is disabled and Lisa reuses the previous line; RandyAGA's copy drops a clause and says DMA is disabled on a match; resolution: aga.guide.
- **ECS register typos (not AGA, for amiga-hardware)** — PDF "VBSRTR" (VBSTRT); PDF/guide VSSTOP "Vert position for VSYNC start" (stop); BPLHSTRT described as "UHRES bit plane vertical stop" (start); prb28 page/registers.tsv name `BLTHSTRT` at $1D4 where NDK has `bplhstrt`.
- **aga.guide DDFSTRT bit table** — only 15 columns for 16 bits (typing error); not used.

### A1200 functional spec (OCR)

- **Memory map row "A80000 to B7FFFF 1 MB System ROM selected"** — conflicts with the same table's ROM rows ($E00000-$E7FFFF, $F80000-$FFFFFF); resolution: row omitted as doubtful.
- **Chip RAM** — spec: "1MB standard ... expandable to 2MB" and "(Systems are currently configured with 2MB Chip Memory standard.)"; resolution: 2MB, with a note.
- **"25~imultaneous colors"**, "Al2OOMemoryMap", "8Ons DRAM" — OCR garble of 256 simultaneous, A1200 Memory Map, 80ns.

### RandyAGA claims not adopted or flagged

- **Wide sprites** — RandyAGA: SPR32/SPAGEM give 32/64-pixel sprites with specific control-long layouts and "64-pixel sprite address multiple of 16"; AA spec only says sprite fetch is 16/32/64 bits (NDK gfxbase has `SpriteWidth` "in words"); resolution: layout marked unverified, skill advises FMODE bits 3-2 = 0 for normal sprites.
- **"70ns sprites may not be available unless the lace bit in BPLCON0 is set"** — not in the AA spec; unverified, not used.
- **Modulo rule "FMODE=3 -> modulo-8, FMODE=2 -> modulo-4"** — RandyAGA only; unverified in general, documented as his rule of thumb.
- **Alignment "16/32/64-bit boundaries for 1x/2x/4x"** (RandyAGA quoting Commodore) vs his "64-bit sprite address multiple of 16" — inconsistent; skill uses 2/4/8-byte alignment and CNOP 0,8.
- **"You can no longer use AllocMem() for bitplanes"** — NDK exec/memory.i `MEM_BLOCKSIZE` = 8 means exec rounds blocks to 8 bytes; guaranteed alignment unverified; skill recommends AllocBitMap(BMF_DISPLAYABLE) and mentions both.

### Unverified / derived statements in the skill

- **DDFSTRT for wide fetches** — only the hires 16-bit ((STARTX-9)/2) and 32-bit ((STARTX-17)/2) formulas are sourced (Yragael & Junkie via RandyAGA); lores/superhires/64-bit rows are derived from the same reasoning and marked unverified.
- **Copper MOVE rate** — "about 56 MOVEs per line, 256-colour load ~10 lines" derived from the AA spec's "4 memory cycles per instruction ... 280 ns" and 227 colour clocks per line.
- **Writing AGA registers on OCS/ECS** — common practice that the writes are harmless; ECS Denise has part of BPLCON3; unverified.
- **LoadView(NULL) and BEAMCON0** — whether graphics resets BEAMCON0 on every monitor driver is unverified; skill says write it yourself.
- **Early-startup "original chipset" and ChipRevBits0** — unverified.
- **SetChipRev() result value** — no autodoc in the source set; unverified.
- **CD32 CPU (68EC020) and A4000/CD32 Kickstart 3.x** — not in the source set; unverified. A4000 CPU variants (030/040) come from Action's guide and RandyAGA.
- **Sprite-steal mechanism on AGA** — AmigaScope TOOLKIT.md says sprites are "DISABLED by AGA"; the HRM shows the same effect on OCS (DDFSTRT $0030 disables sprite 7); resolution: documented as chipset-independent, with the AGA measurements (sprite n at recorder hpos $19+4n/$1B+4n; fetch start $34 -> sprite 7 lost, $24 -> sprites 3-7 lost) marked "measured with AmigaScope's DMA profiler". The recorder hpos is not the DDFSTRT value; the mapping between them is not stated in the repo.

### AmigaScope repo findings (outside this skill)

- **copper_disasm.py BPLCON1 decode** — `PF1H = v & 0x3F`, `PF2H = (v>>4) & 0x3F` is not an AGA decode: for $8822 it prints "PF1H=34 PF2H=2", while the AA layout gives 136 steps (34 lores px) for both playfields; the PF1 "34" matches only by coincidence. The FMODE decode labels bits 1-0 "BPL32=". Status: fixed in AmigaScope (`copper_disasm.py` now decodes the AA layout, FMODE bits, BPLCON2-4, DIWHIGH and bank/LOCT colour loads).
- **TOOLKIT.md** — refers to `docs/AGA.md` ("Hardware sprite DMA steal (DDFSTRT)", §11a), which does not exist in the repo.

## Additions from the SWOS AGA port notes

- **FMODE=0 with 8 lores planes** — AA spec mode table: lores up to 8 planes needs 1x
  bandwidth (FMODE=0); SWOS AGA port on FS-UAE: an 8-plane lores display with a 352-pixel
  fetch window (DDFSTRT `$28`-`$D0`) intermittently lost planes 4-5 at FMODE=0 and was fixed
  by FMODE=1. Resolution: both stated in fmode-and-fetch.md; treat the FS-UAE result as
  possibly emulator- or window-specific (unverified on real hardware).
- **Sprite steal table** — the `$20` and `$30` rows were measured with AmigaScope's DMA
  profiler (fetch start = DDFSTRT + 4); the `$28` and `$38` rows are derived from the same
  rule and marked "(derived)". FMODE=3 as a way to move the fetch start past the sprite
  slots is a proposal from the same notes and has not been measured.

