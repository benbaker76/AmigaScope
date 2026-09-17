# m68k-asm errata

Discrepancies found while distilling the 68k instruction and vasm reference: disagreements between sources,
OCR ambiguities, toolchain behaviour that contradicts documentation, and statements that
could not be verified locally (these are marked "(unverified)" in the entries). Each item
records the resolution used in the reference. When sources conflict, the NDK 3.9 includes
and SFD files win for names, offsets and registers; the Commodore documentation wins for
behaviour unless a test with the bundled toolchain showed otherwise.

## Instructions and CPU topics

Verification used besides the listed sources: every ```asm example (116 blocks) was assembled
with the repo toolchain's vasm 1.9 (`vasmm68k_mot`, CPU option per entry, 0 warnings/errors);
opcode encodings were read back with m68k-amiga-elf-objdump; selected semantics were run in a
scratch unicorn 2.1.4 (QEMU m68k) emulator (flags captured through Scc because unicorn's SR
readback is unreliable).

### Source discrepancies

- **TST operand modes** — prb28 tst.md marks (d,PC)/(d,PC,Xi) as allowed with no CPU note; refmanual: An (W/L), #imm and PC-relative only on 68020+ ("do not apply to MC68000, MC68008, or MC68010"); vasm -m68000 rejects `tst.w (4,pc)`. Resolution: refmanual.
- **CMPI destination modes** — prb28 cmpi.md allows PC-relative; refmanual footnote: not on 68000/68008/68010; vasm -m68000 rejects. Resolution: 68020+ only.
- **CHK source modes** — prb28 chk.md table excludes (d,PC), (d,PC,Xi), #imm, yet its own example is `CHK #max_bound,D0`; refmanual: data modes (includes them); vasm accepts `chk #10,d0`. Resolution: data modes.
- **BTST destination** — prb28 btst.md excludes #imm; refmanual allows #imm for the dynamic `BTST Dn,<ea>` form only. Resolution: refmanual.
- **Bcc 8-bit range** — prb28 bcc.md says "-126 to +128 bytes"; refmanual: two's-complement displacement relative to the branch address + 2. Resolution: -128..+127 from address+2.
- **ASL/LSL wording** — prb28 asl_asr.md: "ASL is almost identical to the corresponding logical shift, LSR". Resolution: LSL (typo).
- **ABCD example comment** — prb28 abcd.md/68000.md: `MOVE #$04,CCR ;Clear X-bit and Z-bit`; $04 sets Z and clears X (which is what a chain needs). Resolution: comment is wrong, code right.
- **ADDX example** — prb28 addx.md starts the chain with `MOVE #$00,CCR`, which clears Z, so the chain's final Z is meaningless. Resolution: start with `move #$04,ccr` (X=0, Z=1).
- **DIVU overflow condition** — refmanual DIVU word-form NOTE says overflow when "quotient is larger than a 16-bit signed integer"; prb28 divs_divu.md mixes that with "upper word of dividend >= divisor". Resolution: DIVU overflows when the quotient > $FFFF (= high word of dividend >= divisor), DIVS when outside -32768..32767; emulation: $18000/2 via DIVU gives $C000 with V=0, via DIVS sets V.
- **DIVS/MULS word source modes** — refmanual text says "data alterable", its tables list all data modes including #imm and PC-relative. Resolution: data modes (vasm accepts `divs #2,d0`).
- **MOVE from SR privilege** — prb28 move.md: privileged on 68010/020/030; refmanual section 6 lists MC68EC000, 68010, 020, 030, 040, CPU32; exec GetCC autodoc and HRM: privileged on 68010+. Resolution: 68010+ and 68EC000.
- **STOP with S clear in the data** — prb28 stop.md says it causes a privilege violation; refmanual STOP entry does not say so (only the CPU32 LPSTOP text does). Resolution: entry only advises keeping S set; claim not repeated.
- **MOVEM "overshoot" access** — prb28 movem.md/68000.md describe an extra bus access past the last register; not in refmanual. Resolution: omitted.
- **NOT operation line** — prb28 not.md shows `[destination] <- [destination]` (complement bar lost). Resolution: cosmetic, ignored.
- **FSINCOS syntax** — refmanual.md OCR shows `FSINCOS.X FPm,FPc,FPs`; vasm accepts `fsincos fp0,fp1:fp2`. Resolution: colon form `FPc:FPs`.
- **32-bit addressing on the 68EC020** — HRM intro: "The 68020, 68030, and 68040 use all 32 bits for addressing"; A1200FuncSpec: A1200 68EC020 has a 24-bit address space; AGA-fixing guide: 68000 and 68EC020 use 24 bits. Resolution: EC020 = 24-bit, full 020/030/040/060 = 32-bit.
- **refmanual.md coverage** — the brief says it contains the addressing-mode chapter and exception processing; the file only has sections 4-7 (integer, FPU, supervisor, CPU32 instructions). Resolution: mode/register encodings taken from the per-instruction EA tables (and vasm encodings), vector numbers from NDK `exec/alerts.i` ACPU_ codes (low byte = vector number), stack-frame layout from the AGA-fixing guide (src/aga/action-aga-fixing.txt).

### Unverified or indirectly verified claims (open items)

- **68060 details** — refmanual predates the 68060. Unverified: MOVEC PCR = $808 and BUSCR = $008 (taken from vasm 1.9's register table, `movec pcr,d0` -> $4E7A $0808); software emulation of CAS/CAS2, CHK2/CMP2, PACK/UNPK, 64-bit MULx.L/DIVx.L; presence of MOVE16/CINV/CPUSH and on-chip FPU (not LC/EC). Only "68060 lacks MOVEP" has a source (AGA-fixing guide).
- **68040.library / 68060.library** — names of the Amiga CPU support libraries are not in any listed source.
- **SR bits T0 (14) and M (12)** on 68020+ — only "T0 = 1, T1 = 0" appears (refmanual STOP); layout marked unverified.
- **Bit-field offset direction** — refmanual text only says "starting bit"; offset 0 = MSB is consistent with the BFFFO description and confirmed in emulation (`bfextu d0{4:4}` of $0F000000 = $F; BFINS/BFFFO results).
- **A7 byte push/pop steps 2** — not in the available Motorola text; confirmed only in emulation (SP $8000 -> $7FFE after `move.b #$12,-(sp)`).
- **68000 multiply/divide/shift timing** (MULU 38+2n up to 70 clocks, DIVU up to ~140, shift 6+2n) — no timing tables in the sources; tagged (unverified) in optimisation.md.
- **FPU condition predicates** — refmanual refers to Table 3-23, not included. Codes $00-$1F taken from vasm encodings (fbeq=$01, fbogt=$02 ... fbst=$1F); "the $10-$1F group are the IEEE non-aware (BSUN-setting) tests" tagged unverified.
- **Machines** — A500+/A600 = 68000, CD32 = 68EC020, A4000/030 32-bit decoding: not in sources, tagged unverified. Sourced: A1000/A500/A2000 68000 and A3000 68030 (HRM), A1200 68EC020 14 MHz (A1200FuncSpec), A4000/030 and /040 variants (AGA-fixing guide).
- **CAS on Chip RAM** — HRM only states TAS's read-modify-write cycle is unsupported on the Amiga; the CAS gotcha applies the same reasoning (CAS uses a locked/read-modify-write sequence per refmanual).
- **Emulator caveats** — unicorn/QEMU reported NEG.B $80 with C=0 via SR readback (Scc capture shows the refmanual's C=1) and does not implement CMP2 and PACK/UNPK; those instructions rest on the refmanual alone.

### Tool behaviour recorded (vasm 1.9, verified by assembling)

- `moveq #200,d0` / `moveq #$ff,d0`: warning 2028, assembles -56 / -1. `addq #9`, `lsl.l #9`, `trap #16`: errors. `btst #9,(a0)` and `bset #33,d0`: accepted silently (modulo applied by the CPU).
- `$8000.w`: error "absolute short address out of range"; unsized absolute values in $0000-$7FFF / $FFFF8000-$FFFFFFFF become abs.W with optimisation on.
- `(8,a0,d0)` defaults to a word index; with `-m68020` an out-of-range 8-bit index displacement is silently promoted to a full-format (68020-only) extension.
- Default optimiser rewrites: `clr.l Dn`/`move.l #0,Dn` -> moveq; `move.l #200,Dn` -> `moveq #100` + `add.w` (X/C change); `move.l #$20000,Dn` -> moveq + swap; addi/subi 1..8 -> addq/subq; `adda.l #1000,An` -> lea; `lea 0(An),An` removed; `cmp #0`/`or.l #0` -> tst; `asl.l #1` -> `add.l`; in-range jsr/jmp -> bsr/bra; `bra.s` to the next instruction -> 2-byte no-op with warning 2058. Not rewritten: `move.w #0,<mem>` (no CLR), single-register MOVEM, MULU by powers of two.
- `cpusha dc/ic` is accepted with a "trailing garbage" warning and only flushes the data cache; vasm's both-caches operand is `bc` ($F4F8).
- vasm assembles MOVEP with `-m68060` without complaint.

## Directives, vasm/vlink and program structure

Verification method: every directive and option claim was checked against the vasm manual
(`vasm manual`, 2025 edition), the vlink manual, the NDK 3.9 asm includes and by
assembling test files with the two bundled binaries: vasm 1.9 (mot 3.15d) from
bartmanabyss.amiga-debug-1.8.2 and vasm 1.8k (mot 3.15a) + vlink 0.16h from
prb28.amiga-assembly-1.8.13. "Tested" in the skill text means this.

### Source discrepancies

- **FO order** — prb28 `fo.md` and vasm manual §4.4: label gets the counter, THEN it is decremented; vasm 1.8k and 1.9: decrement first, then assign (`clrfo` / `a fo.l 1` gives a = -4); resolution: documented observed behaviour with a warning in structures.md#fo.
- **Hex symbol insertion in macros** — prb28 `macro.md`: `\$<symbolname>`; manual §4.4: `\<$symbolname>`; test: prb28 form fails ("identifier expected"), manual form prints hex on both builds; resolution: manual form documented, prb28 spelling flagged.
- **TTL** — prb28 `ttl.md`: equivalent to IDNT; manual 2025: sets listing page title; test: 1.8k and 1.9 write it as the HUNK_UNIT name (= IDNT); resolution: documented both, advise not to rely on it.
- **NREF** — prb28 and manual: only in PhxAss mode; test: vasm 1.9 accepts it in default mode, rejects it with `-devpac`; resolution: documented observed behaviour.
- **CODE/DATA/BSS/CSEG/TEXT section names** — prb28/manual: `section code,code` etc.; test: 1.9 emits `.text`, `.data`, `.bss`, `code.MEMF_CHIP`, `data.MEMF_CHIP`; 1.8k emits `CODE`, `CODE_C`, `DATA`, `BSS`; resolution: documented, advise explicit `section name,type` when vlink must merge by name.
- **DS contents** — prb28 `ds.md`: "content undefined"; manual: equivalent to `dcb ...,0`; test: zeros (fill changeable with `-uspc`); resolution: zero-filled.
- **CNOP offset in code sections** — manual: add `<offset>` padding bytes; test (1.8k and 1.9, default mode, code section): offset filled with `offset` NOP WORDS (2x bytes); data sections and `-devpac` correct; resolution: gotcha "use only cnop 0,n in code".
- **IFMACROD/IFMACROND** — prb28/manual: "assemble the following line"; test: opens a normal block closed by `endc`; resolution: documented as block.
- **ELSEIF** — brief listed ELSEIF as if it were else-if; manual: "Same as else, for compatibility!"; test confirms operand ignored (`if M=1 / elseif M=2 / else` assembles both if- and else-blocks when M=1); resolution: entry with loud gotcha.
- **Manual features missing from the bundled builds** — manual 2025 lists `elif`, `assert`, `local`, `rseven`, `rept <n>,<sym>`, `=.s/.d/.x/.p`, `equ.s/...`, `.sdreg`, `-opt-<devpac option>`; tests: unknown mnemonic / unknown option on 1.8k and 1.9 (`elif` is silently skipped inside a false block); resolution: entries marked "not available in vasm 1.8k/1.9".
- **SHOWOFFSET, FEQUR, FREG/FEQURL** — manual lists them; test: work in 1.9, errors in 1.8k (2045/2067, unknown mnemonic); resolution: marked "vasm 1.9".
- **Size `.p` for RS/SO/FO** — prb28/manual allow `b w l q s d x p`; test: 1.9 rejects `.p` (error 1002); resolution: documented.
- **Float constants** — manual: IEEE encoding; test: amiga-debug vasm 1.9 emits zeros for `dc.s/dc.d/dc.x` and `fequ` values; 1.8k correct, but 1.8k rejects `dc.p`; resolution: gotcha "verify or write IEEE hex". Likely a build without float support; open item for whoever ships the toolchain.
- **GLOBAL** — not in prb28 or manual §4.4; test: accepted by 1.8k/1.9 in default mode (like XDEF), rejected by `-devpac`; resolution: mentioned inside XDEF only.
- **DR syntax** — prb28: `dr.[bwlbx]`; manual: `dr.b/.w/.l` only; resolution: b/w/l documented (per-element PC confirmed by test).
- **Include search order** — prb28 `include.md`: current dir, then -I/incdir; manual §2.5: work dir, compile (main-source) dir, -I, incdir; test: nested include is NOT searched relative to the including file; resolution: manual order + test note.
- **Data alignment** — prb28 silent; manual §24.3: data not auto-aligned without `-align`/`-devpac`; tests also show `ds.w 0` does not align in native mode (NDK `exec/macros.i` PRINTF relies on it) and that a label on its own line before an auto-aligned instruction keeps the odd address; resolution: documented in data.md intro/EVEN/DS.
- **-kick1hunks** — manual CPU chapter: prevents JMP/JSR -> 32-bit BRA/BSR; manual hunk chapter: no 16-bit relocation offsets in executables, rejects 32-bit PC-relative relocs; test: `-Fhunkexe` default writes HUNK_DREL32 ($3F7, short reloc), with `-kick1hunks` HUNK_RELOC32 ($3EC), and cross-hunk `dr.l` becomes error 3005; resolution: both effects documented.
- **Cross-hunk 32-bit PC-relative** — none of the sources say what vasm emits; test: `-Fhunkexe` and vlink both write HUNK_RELRELOC32 ($3FD), which NDK `dos/doshunks.i` marks "New for V39"; resolution: documented with V39 note (no OS-version name attached).
- **Label collisions with NDK includes** — not in sources; tests: `STRUCTURE GfxBase` makes `GfxBase` EQU 0 (label `GfxBase:` = error 75, `move.l GfxBase,a6` assembles as `movea.l $0.w,a6`); `ra_SIZEOF` already defined by `graphics/gfx.i`; `dos/dos_lib.i` + `lvo/dos_lib.i` = error 68; `exec/exec_lib.i` needs a user FUNCDEF; resolution: gotchas in library-calls.md / macros-and-structures.md / include-and-output.md.
- **NDK exec/macros.i PUSHM/POPM** — use `\*VALOF()`; vasm errors ") expected"; resolution: documented as unusable with vasm.
- **CALLEXEC / LIBCALL** — brief asked for CALLLIB/LINKLIB/LIBCALL-style macros; NDK 3.9 `exec/libraries.i` has only CALLLIB and LINKLIB, `exec/macros.i` has JSRLIB/JMPLIB; no CALLEXEC/CALLDOS/CALLGRAF/LIBCALL anywhere in sys-include (grep). The vscode example `gencop.s` mentions `CALLEXEC` only in a comment; resolution: documented absence.
- **elf2hunk chip sections** — no doc; elf2hunk binary strings show `.MEMF_CHIP`/`.MEMF_FAST`; tests: `.MEMF_CHIP`, `.gfx.MEMF_CHIP` -> chip hunk, `.MEMF_FAST` -> fast hunk, `.data.MEMF_CHIP` -> plain data (the ld default script folds `.data.*` into `.data`); resolution: documented naming rule.
- **fix_hunk_relocs.py version note** — docstring blames elf2hunk "bundled with Amiga Debug Extension 1.8.1"; installed extension is 1.8.2; whether 1.8.2's elf2hunk still has the bug was not tested (analyze_pc32.py text implies a partial fix exists upstream); open item.
- **analyze_pc32.py vs fix_hunk_relocs.py RELA unpack** — analyze uses `'>IiI'` (signed r_info, unsigned addend), fix uses `'>IIi'`; both mask `r_info & 0xff` for the type, so results agree; cosmetic only.

### Unverified statements left in the skill (standard knowledge, no local text found)

- **Program entry at the first byte of the first hunk** — standard AmigaDOS behaviour; consistent with vscode-amiga-assembly putting the entrypoint object first and vlink's "start of first code section"; marked "(standard behaviour...)" in vasm-vlink.md and amiga-program-structure.md.
- **Why Forbid before ReplyMsg(WBStartup)** — rule comes from the brief; the reason (Workbench unloads the segment after the reply) is marked "(unverified)".
- **pr_CLI == 0 means Workbench start** — from the brief and common practice; dosextens.i only says "pointer to CommandLineInterface".
- **First WBArg describes the program itself** — marked "(unverified)".
- **Preserving D2-D7/A2-A6 at program level** — stated as convention "(not stated in the local sources)".
- **No console from Workbench** — the skeleton skips PutStr when started from Workbench; the reason (Output() has no stream) is not in local sources.
- **Scratch registers D0/D1/A0/A1, preserved D2-D7/A2-A6 for library calls** — from STYLE.md spec; not re-derived from autodocs.
