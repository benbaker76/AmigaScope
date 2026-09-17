# amiga-hardware errata

Discrepancies found while distilling the Custom chip and CIA reference (registers/ and topics/): disagreements between sources,
OCR ambiguities, toolchain behaviour that contradicts documentation, and statements that
could not be verified locally (these are marked "(unverified)" in the entries). Each item
records the resolution used in the reference. When sources conflict, the NDK 3.9 includes
and SFD files win for names, offsets and registers; the Commodore documentation wins for
behaviour unless a test with the bundled toolchain showed otherwise.

## Registers (registers/)

### prb28 register pages / registers.tsv copy-paste errors
- **SERDATR ($DFF018)** — prb28 title "Pot pin data read"; HRM App A: serial port data and status read; resolution: HRM.
- **BLTCON0L ($DFF05A)** — prb28 title "Pot pin data read"; HRM App C: blitter control 0 lower 8 bits (minterms); resolution: HRM.
- **BLTCON1 ($DFF042)** — prb28 title is the BLTCON0L description ("Blitter control register 0 (lower 8 bits)"); HRM: blitter control register 1; resolution: HRM.
- **CIAB PRB ($BFD100)** — prb28 title "CIAB Peripheral Data Register A"; HRM App F: port B (disk control); resolution: HRM.
- **POTINP at $DFF09A** — registers.tsv/prb28 (DFF09A_POTINP.md) lists POTINP at the INTENA address with INTENA text; HRM + custom.i: POTINP/POTGOR is $DFF016; resolution: treated as bogus row, noted in the POTGOR entry.
- **DKSDAT ($DFF026)** — prb28 file name typo; custom.i `dskdat`; resolution: DSKDAT.
- **BLTHSTRT ($DFF1D4)** — prb28 file name typo and description "UHRES bit plane vertical stop" (also in Solo's AGA PDF); custom.i `bplhstrt`, PDF body text "controls the line when the data fetch starts"; resolution: BPLHSTRT, start line.
- **VSSTOP ($DFF1CA)** — prb28 page repeats the VTOTAL text; Solo PDF calls it "VSYNC start"; HRM App B/C: VSYNC stop; resolution: HRM.
- **HSSTRT ($DFF1DE)** — prb28 and Solo PDF title "HSYNC stop"; HRM App C and PDF body: sync start; resolution: start.
- **STREQU / STRVBL / STRHOR ($DFF038-$03C)** — prb28 pages all carry the STRLONG description; Solo PDF gives STRVBL the address 038; HRM App A/B: $03A and separate meanings; resolution: HRM.
- **STRLONG slot** — prb28/PDF: "first refresh time slot"; HRM App A: STRLONG uses the second refresh slot of every other line (first slot carries STREQU/STRVBL/STRHOR); resolution: HRM.
- **Null RGA address** — HRM App A says unused refresh slots carry "(FF)"; prb28/PDF say $1FE; HRM App B lists $1FE as NO-OP (NULL); resolution: $1FE.
- **BPLHDAT ($DFF07A)** — prb28 and PDF copy the BPLHMOD description; PDF BPLHPTH text: identifier placed on the RGA bus when the pointer is valid; resolution: identifier.
- **VTOTAL** — prb28 title "VERBEAMEN"; resolution: VARBEAMEN.
- **POT0DAT/POT1DAT symbol column** — prb28 lists "RIGHT Y RX"; resolution: RY.
- **POTGO/POTGOR Paula pin numbers** — HRM App A: OUTRY pin 36, OUTRX 35, OUTLY 33, OUTLX 32 (pot table: RY 36, RX 35, LY 33, LX 32); prb28/PDF swap left and right (RY 33, RX 32, LY 36, LX 35); resolution: entries give port/connector pin (HRM ch8 Table 8-4) and omit Paula pins.
- **CLXCON bit names** — prb28 and Solo PDF name bits 11-0 "ENSPx"; HRM App A, ch7 and prb28 hardware_manual_guide: ENBP6-ENBP1 / MVBP6-MVBP1; resolution: HRM.
- **CLXDAT bit 0** — Solo PDF "Playfield 2 to Playfield 2"; HRM/prb28: playfield 1 to playfield 2; resolution: HRM.
- **JOYxDAT serial bit table** — prb28/PDF list M1V/M1VQ twice for JOY1DAT (horizontal should be M1H/M1HQ); only relevant to Lisa's serial mouse bus; not reproduced.
- **JOYTEST** — prb28 table shows Y1-Y0/X1-X0 as written; HRM App A and PDF: bits 9-8 and 1-0 are "xx"; resolution: HRM.
- **BLTCON0/BLTCON1 tables** — prb28/PDF "ASA0" (ASH0) and line-mode "DPFF" (DOFF) typos; resolution: ASH0, DOFF.
- **ADKCON note** — prb28 "UDxVOL" typo for AUDxVOL.

### HRM internal contradictions / OCR
- **COPCON write ranges** — HRM ch2 (MOVE section): Copper may write $20 and up, $10-$20 with CDANG, never below $10; HRM ch2 (control register section): $00-$3E never, $40-$7E only with CDANG; HRM App C: with CDANG clear the ECS Copper "can access $03E-$07E"; Solo PDF: CDANG=0 -> above $7E, CDANG=1 -> all (ECS/AGA) or above $3E (old chips); resolution: table in COPCON uses the ch2 control-register text for OCS and the PDF for ECS/AGA.
- **COPINS MOVE word 1 bits 15-9** — HRM App A "x", prb28 "0", HRM ch2 "not used, should be set to 0"; resolution: 0.
- **CIA-B DDRA** — HRM App F address table: "set to $FF"; same appendix's pin list: DTR/RTS outputs, CD/CTS/DSR and printer SEL/POUT/BUSY inputs; resolution: entry gives bits 7-6 out, 5-0 in and warns against writing $FF; actual OS value not verified.
- **CIAA PRA fire button order** — HRM App E OCR reads "PRA0 bit 7 ... left controller port, bit 6 ... right"; cia.i: `CIAB_GAMEPORT1` = bit 7, `CIAB_GAMEPORT0` = bit 6; HRM ch8: bits 6 and 7 for ports 0 and 1; resolution: NDK (bit 6 = port 0/left/mouse).
- **CRA bit 7** — cia.i defines `CIACRAB_TODIN` (6526 name); HRM App F: unused on the 8520; resolution: both stated.
- **DIWHIGH bits 2-0** — HRM App C OCR labels them "Vertical stop"; they are the start bits (PDF, prb28); bit 6 OCR garbage; resolution: start.
- **DDFSTRT/DDFSTOP bit naming** — HRM (ch3, App A): bits 7-2 = H8-H3, bits 1-0 unused; prb28/PDF (AGA renumbering) name bits 7-1 H8-H2 and prb28 places H2 in bit 1; resolution: OCS naming.
- **DIWSTRT/DIWSTOP horizontal naming** — HRM H7-H0; prb28/PDF H9-H2 (AGA renaming, H0 = 35 ns); resolution: OCS naming.
- **Blitter line mode BLTAPTL** — HRM App A: "(2Y-X)"; HRM ch6 register summary: 4*dy - 2*dx; resolution: ch6.
- **BLTCON1 line-mode bit 5** — HRM App A "0 (reserved)"; PDF OVF; blit.i `OVFLAG` = $20; resolution: OVF, write 0.
- **Octant numbering** — HRM ch6 Table 6-3 numbers octants 0-7 (code 110 = octant 0 ... 100 = octant 7); blit.i `OCTANT1`-`OCTANT8` use the same codes in reverse (`OCTANTn` = HRM octant 8-n); resolution: NDK constants given with the mapping.
- **Sprite horizontal coordinates** — HRM ch4 says its example window spans pixels 64-383 and adds 64 to X, while the same chapter's example sprite (H = 128) encodes HSTART $C0 on a $2C81 window; resolution: only the verified vertical relation is stated; "HSTART = DIWSTRT H - 1 aligns with the window edge" is marked unverified.
- **AUDxPER minimum** — HRM App A: 124; HRM ch5: 124 NTSC, 123 PAL; resolution: both.
- **Pointer widths** — HRM App A: "18-bit" pointers (3 high + 15 low bits); prb28/PDF: "20-bit" (5 high bits); resolution: entries say "3 address bits OCS, 5 ECS" in the high word and avoid bit totals.
- **DSKBYTR bit 14 (DMAON)** — HRM App A: DSKLEN DMAEN AND DMACON DMAEN; PDF adds DMACON DSKEN; resolution: both enables listed.
- **HBSTRT/HBSTOP chip** — Solo PDF chip column "D" (Lisa fine bits); HRM App B/C "A(E)"; resolution: Agnus for ECS, AGA fine bits deferred to amiga-aga.

### ECS vs AGA bit ownership
- **BPLCON0 bits 5-4** — HRM App C (ECS) names them BPLHWRM / SPRHWRM; Solo PDF (AGA) names them BYPASS / BPU3 and puts BPLHWRM/SPRHWRM in bit 15 of BPLHSTOP/SPRHSTOP (prb28 agrees); resolution: "write 0 on OCS/ECS", AGA meanings deferred, WRM bits documented in BPLHSTOP/SPRHSTOP.
- **BPLCON0 bit 0 name** — HRM App C ENBPLCN3; PDF ECSENA; C custom.h `USE_BPLCON3`; resolution: all three names given.
- **BPLCON3 bits 2-0** — C custom.h (`ECS_SPECIFIC`): EXTBLNKEN (0), EXTBLKZD (1), ZDCLKEN (2); Solo PDF (AGA): EXTBLKEN (0), BRDSPRT (1), ZDCLKEN (2); HRM App C documents only bits 5-4 for ECS; C name `BPLCON3_BRDNBLNK` vs HRM BRDRBLNK; resolution: ECS entry documents bits 5-4 and lists the C names.
- **BEAMCON0 bit 3** — HRM App C: BLANKEN (C `CSBLANK`); Solo PDF: "(unused, formerly BLANKEN)"; resolution: ECS BLANKEN, unused on AGA.
- **BEAMCON0 C flags** — custom.h has no names for bits 14 (HARDDIS) and 13 (LPENDIS); VARVSYEN text in Solo PDF says "set vertically on HSSTRT" (prb28: VSSTRT); VBSTRT/VBSTOP text "BLAKEN" typo; resolution: VSSTRT.
- **KILLEHB (BPLCON2 bit 9)** — HRM App C lists it with the ECS genlock bits; not defined in custom.h ECS_SPECIFIC; resolution: documented as ECS per HRM.
- **VPOSR ID bits** — HRM App A (OCS) shows only LOF and V8; HRM App C and Solo PDF give I6-I0 values including OCS 8361/8367; resolution: ID table in VPOSR, LOL/V9/V10 marked ECS/AGA.

### Unverified claims (not in the local sources)
- **INTREQ double write** — "write INTREQ twice before RTE on 68020+ in fast RAM" is community knowledge; local sources only say acknowledge late, just before RTE (action-aga-fixing.txt). Marked (unverified).
- **68000 autovector addresses** ($64-$7C) — not stated in the HRM; resolved: vector numbers 25-31 confirmed by NDK `exec/alerts.i` (`ACPU_AutoVec1`-`7`).
- **CIA-A /LED switches the audio filter** — not in the local sources. Marked (unverified).
- **Keyboard handshake via CRA SPMODE** — HRM says pulse KDAT low >= 85 us; that setting SPMODE (output) is what drives KDAT low is not stated. Marked (unverified).
- **Sprite HSTART/window alignment** — see sprite coordinate item above. Marked (unverified).

## Topic guides (topics/)

### Source discrepancies

- **Copper write ranges (COPCON/CDANG)** -- HRM ch.2 MOVE section says the copper can write "address $20 or above", "$10-$20 with CDANG", "never below $10" (DA-index units, i.e. offsets $40/$20); HRM ch.2 Control Register section says offsets $80-$FF always, $40-$7E only with CDANG, $00-$3E never; HRM App C says OCS+CDANG reaches $03E-$07E and ECS reaches everything with CDANG and $03E-$07E without; prb28 COPCON says "if 0, access to RGA>$7E; old chips >$3E if CDANG". Resolution: guides state the conservative rule valid on all chipsets ($080+ always, $040-$07E only with CDANG, never below $040) and mention the ECS relaxation.
- **HAM enable bit** -- HRM Table 3-19 text says HAM is active "only if bit 10 of BPLCON0 = 1"; HRM BPLCON0 summary, NDK usage and prb28 give HOMOD = bit 11 (bit 10 is DBLPF). Resolution: bit 11.
- **Line-mode A shift** -- HRM ch.6 text says ASH = "x1 modulo 15"; the HRM SimpleLine example uses the low 4 bits of x1. Resolution: `x1 & 15`.
- **Line-mode set-up values** -- HRM App A says BLTAPTL = "2Y-X" and BLTBDAT "preloaded with FF"; HRM ch.6 register summary and the SimpleLine example use `4*dy-2*dx` and `$FFFF`. Resolution: ch.6 values.
- **Octant numbering** -- HRM Table 6-3 / App A number octants 0-7 (codes 110,001,011,111,101,010,000,100); NDK `blit.i` names OCTANT1-OCTANT8 with values 16,0,8,20,28,12,4,24 (HRM octant n == NDK OCTANT(8-n)). Resolution: guides use the NDK names; dx/dy/major-axis meaning derived from the HRM SimpleLine example (SUD = x major, SUL = minor step negative, AUL = major step negative).
- **DMACONR bit 13** -- NDK names it `DMAF_BLTNZERO` ("not zero"); HRM ch.7 (BZERO) and ch.6 say the bit stays 1 when the blit output was all zero. Resolution: guide follows the HRM (1 = all zero) and notes the confusing NDK name.
- **FILL_CARRYIN bit** -- HRM ch.6 text says "FILL_CARRYIN or bit 3" (same number as FILL_OR); NDK `FILL_CARRYIN equ $4` and HRM App A (FCI = bit 2). Resolution: bit 2.
- **BLTCON0L address** -- HRM App C and prb28 list BLTCON0L at `$05A`; NDK `custom.i` defines `bltcon0l EQU $05B` "byte access only". Resolution: use the NDK label with a byte write.
- **Audio stereo layout** -- HRM ch.5: channels 1 and 2 left, 0 and 3 right; common tracker/emulator convention treats 0 and 3 as left. Resolution: both stated in audio.md, marked unverified.
- **Minimum audio period** -- HRM ch.5: 124 NTSC, 123 PAL; HRM App A: 124. Resolution: 124.
- **Vertical blank length** -- HRM ch.7: minimum vertical blank 20 lines NTSC / 25 PAL; HRM ch.3 Table 3-13: vertical blank stop $15 (21) NTSC / $1D (29) PAL. Resolution: both quoted, line $2C recommended as first display line.
- **DDFSTRT minimum** -- HRM ch.3: hardware limit $18; HRM App A DDFSTRT table: "extra wide (max)" = H8-H4 00101 = $28. Resolution: $18 (ch.3).
- **ROM range** -- `Amiga System Memory Map.htm` lists `$F00000-$FBFFFF` as "256K System ROM (Kickstart 2.0)" (range is 768K); HRM A3000 map: `$F00000-$F7FFFF` diagnostic ROM, `$F80000-$FFFFFF` 512K ROM. Resolution: HRM.
- **Zorro III area** -- HRM A3000 map: Zorro III expansion `$10000000-$7FFFFFFF`; NDK `configregs.i`: `EZ3_CONFIGAREA $40000000`-`$7FFFFFFF`. Resolution: both given.
- **Sprite horizontal offset** -- HRM ch.4 uses a window "from pixel 64 to 383" and example H=128+64=192 (HSTART $C0) while ch.3 puts the window at DIWSTRT HSTART $81 (lores pixels); internally inconsistent. Resolution: guide gives `HSTART = $80 + x` for a `$2C81` window, marked unverified.
- **Disk port name** -- HRM ch.8 says the PB disk bits are "in CIAAPRB ($BFD100)"; `$BFD100` is CIA-B PRB (App F, NDK `CIAB_DSK*` under "ciab port B"). Resolution: CIA-B PRB.
- **Controller port numbering** -- HRM ch.8 calls JOY0DAT "port 1" and JOY1DAT "port 2", then says fire buttons for "ports 0 and 1" are PRA bits 6 and 7. Resolution: guides use NDK gameport 0/1 (`CIAB_GAMEPORT0` = bit 6 = JOY0DAT = mouse port).
- **DSKSIDE polarity** -- HRM ch.8: "zero indicates the upper head"; HRM App H: SIDEB- "low for side 1". Resolution: consistent if the upper head is side 1; guide says 0 = upper head (side 1).
- **BEAMCON0 bit 3** -- HRM App C: BLANKEN; NDK `custom.h`: `CSBLANK $0008`; prb28: "unused, formerly BLANKEN". Resolution: NDK name, both shown.
- **BPLCON3 bit 5 name** -- HRM/prb28: BRDRBLNK; NDK C `BPLCON3_BRDNBLNK` (comment duplicates "border is opaque" from bit 4). Resolution: bit 5 = border blank.
- **BPLCON0 bit 0 name** -- HRM App C: ENBPLCN3; prb28: ECSENA; NDK C: `USE_BPLCON3 1`. Resolution: same bit, names listed.
- **DIWHIGH** -- HRM App C labels the start bits 2-0 "Vertical stop" (copy error) and numbers horizontal bits H8; prb28 renames them H10/H1/H0 (AGA numbering). Resolution: bits 2-0 = start V10-V8, bit 5 = start H8, bit 13 = stop H8, bits 10-8 = stop V10-V8.
- **Bus cycle parity** -- HRM ch.2 / App A: copper uses odd cycles, display/audio/disk/refresh/sprites use even cycles; HRM ch.6: the 68000 uses even cycles and odd cycles go to other devices. Resolution: guides only say the copper uses odd cycles and the CPU normally gets alternate cycles.
- **Interlace copper restart** -- HRM ch.2 says COP1LC is "automatically reset to point to the original list" during vertical blank; the hardware only restarts from COP1LC -- the reset is done by graphics.library's VBL server. Resolution: guide switches lists in the VERTB handler (LOF=1 long list, per HRM ch.3 example).
- **VPOSR contents** -- HRM App A lists only LOF and V8; HRM App C adds Agnus ID bits 14-8; prb28 adds LOL (bit 7) and V9/V10. Resolution: all listed where relevant.
- **Dual playfield plane numbering** -- HRM ch.3 says "Bits from PLANE 0 have the lowest significance" for playfield 1. Resolution: plane 1 (planes are numbered 1-6).
- **CIA-B DDRA default** -- HRM App F OCR says CIA-B DDRA is "set to 0xFF", although PRA bits 5-0 are inputs (CD, CTS, DSR, SEL, POUT, BUSY). Resolution: no default stated for CIA-B DDRA.
- **Keyboard handshake length** -- HRM ch.8/App G: at least 85 us (keyboards detect >= 1 us); `action-aga-fixing.txt`: "handshake min 75 us". Resolution: 85 us, example waits >= 2 full lines.
- **CIA-A TOD source** -- HRM App F: "50/60 Hz event counter (VSync or line tick)". Resolution: guide says 50/60 Hz tick, model dependent.

### Unverified claims (open items)

- Gary as A500/A2000 glue chip: not described in the HRM or other local sources.
- Slow RAM at `$C00000` being added to the free list as fast-type memory.
- ROM overlay polarity (CIA-A PRA bit 0 = 1 maps ROM at `$0`).
- Standard 68k vector assignments `$08`-`$2C` (only the autovector levels come from the INTENA table; `$6C`/`$80` also appear in RandyAGA).
- Writing INTREQ twice when acknowledging (common practice, no HRM statement).
- Exec's server-chain dispatcher acknowledging INTREQ for AddIntServer servers.
- Non-interlaced displays keeping LOF = 1 (long field every frame).
- Horizontal scroll recipe showing stored column `sx+1` at the window edge (derived from HRM ch.3 rules).
- HAM: the "pixel to the left" of the first pixel on a line is the background colour.
- Sprite loss vs DDFSTRT beyond the HRM's `$30` -> sprite 7 (derived from AmigaScope `dma_profile.py` AGA slot map `$19+4n` with a fetch start of DDFSTRT+4).
- Sprite HSTART offset `$80 + x` for a `$2C81` window (see discrepancy above).
- Keyboard handshake via CRA SPMODE (HRM only specifies pulling KDAT low).
- Parallel BUSY polarity (1 = busy).
- `FindConfigDev` wildcard -1 (no expansion autodoc in the local sources).
- Whether `LoadView(oldView)` reprograms BEAMCON0 after a PAL/NTSC switch.
- Fill-outline vertex handling (first pixel of each edge) for blitter area fill.
