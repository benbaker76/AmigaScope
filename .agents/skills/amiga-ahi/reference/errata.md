# amiga-ahi errata

Discrepancies found while distilling the AHI reference: disagreements between sources,
OCR ambiguities, toolchain behaviour that contradicts documentation, and statements that
could not be verified locally (these are marked "(unverified)" in the entries). Each item
records the resolution used in the reference. When sources conflict, the NDK 3.9 includes
and SFD files win for names, offsets and registers; the Commodore documentation wins for
behaviour unless a test with the bundled toolchain showed otherwise.

## AHI

- **AHI_SetVol / AHI_SetFreq / AHI_SetSound / AHI_SetEffect autodocs** — the AHI 6.0 SDK `Docs/ahi.doc` and `ahi.guide` have no entries for these four (TOC jumps from AHI_SampleFrameSize to AHI_UnloadSound); the SFD, `lvo/ahi_lib.i` and `inline/ahi.h` do define them. Resolution: entries written from the autodoc comments in `ahisrc/Device/sound.c` (AHI 4.x source, 1999) plus `ahidev.guide` 6.0 and `devices/ahi.h` 6.0 for V6 additions (`AHISF_NODELAY`, `AHISF_NONE`).
- **Source tree vs SDK version** — `ahisrc` is AHI 4 (`version.ver` 4, rev 507, 08.02.99); SDK includes/docs are 6.0. V4 AHI_LoadSound documents `AHIST_INPUT` ("not fully functional"), the V6 autodoc drops it; `AHIST_INPUT` is still in `ahi.h`. Resolution: listed with the V4 caveat.
- **AHI_MIXFREQ** — V4 AHI_SetFreq autodoc: only usable with `AHIST_INPUT` sounds; `ahi.h` 6.0 comment: "Special frequency for AHI_SetFreq()". Resolution: both stated.
- **ahiim_Type** — ahi.doc AHI_AllocAudioA (AHIA_RecordFunc) says "multiply by 4 if ahiim_Type is AHIST_S16S"; no such field, the header field is `ahirm_Type`. Resolution: `ahirm_Type`.
- **ahirm_Samples** — ahi_sub.doc AHIsub_Start (recording) fills `ahirm_Samples`; `ahi.h`/`ahi.i` name the field `ahirm_Length`. Resolution: `ahirm_Length`.
- **AHIDBB_STEREO** — ahi_sub.doc AHIsub_Start mentions `AHIDBB_STEREO`, which is defined nowhere; `ahi_sub.h` has `AHIACB_STEREO`/`AHIACF_STEREO` for `ahiac_Flags`. Resolution: header names.
- **AHIsub_Stop / AHIsub_Update return type** — ahi_sub.doc synopses say `void`; `ahi_sub_lib.sfd` (and the skeleton fact blocks) say `ULONG`. Resolution: fact blocks pasted unchanged, discrepancy noted in drivers.md.
- **AHI_AddAudioMode synopsis** — V4 source autodoc shows `ULONG AHI_AddAudioMode(struct TagItem *, UBYTE *, UBYTE *)` (3 args); SFD has one argument (A0). Resolution: SFD.
- **AHIDB_MixFreq** — `devices/ahi.i` defines `AHIDB_MixFreq EQU AHI_TagBase+128`; not in `ahi.h` or any autodoc. Resolution: listed as asm-only, advised not to use.
- **AHI_NOSOUND** — C `0xffffU`, asm `~0` (32-bit). The Sound argument is UWORD (D1:16), so both work. Resolution: both values given.
- **Asm vs C structure names** — `ahi.i` names effect fields `ahiemv_Effect`, `ahieob_Effect`, `ahiedm_Effect`, `ahiede_Effect`, `ahieci_Effect` (plus a generic `ahie_Effect EQU 0`); C uses `ahie_Effect`. Asm `ahiam_ObsoleteUserData0/1`, `ahir_Private1/2` vs C arrays. Resolution: both names in the tables.
- **OPENAHI / CLOSEAHI macros (ahi.i)** — reading the macro source: OPENAHI clears AHI_DEVICE to 0 (= "open succeeded") before trying; if CreateMsgPort or CreateIORequest fails, CLOSEAHI calls CloseDevice with a NULL request; if OpenDevice fails, CLOSEAHI skips DeleteIORequest (leak). Resolution: documented as caveats, hand-written open/close shown. Open item: not run-tested.
- **SimplePlay one-shot from task code** — the SDK example's V2 branch queues `AHI_SetSound(1, AHI_NOSOUND, 0, 0, actrl, 0)` from the main task; ahidev.guide says flags must be `AHISF_IMM` outside Sound/PlayerFunc. Resolution: follow the guide; one-shots from task code via AHI_PlayA.
- **Paula channel panning** — PT-AHIPlay uses pan 0,1,0,1 for channels 0-3; ahiusr.guide says paula.audio uses "right, left, left, right" and admits wide confusion. Resolution: no left/right assignment asserted; deferred to the amiga-hardware skill.
- **AHISF_NODELAY version** — `ahi.h` gives no version; ahidev.guide (rev 5.3, 2003) ties it to `AHIA_AntiClickSamples` (V6). Resolution: described as the V6 anti-click override.
- **V5** — autodocs mark no feature as V5; ChangeLog shows ahi.device 5.x releases (AHI 5.1 "for AmigaOS 3.9 CD", anti-click fixes in 5.4-5.6). Resolution: features labelled V6 as the includes/autodocs do; advise `ahir_Version` 6 for them.
- **AHI_GetAudioAttrsA with unknown ID** — autodoc only says "TRUE if everything went well"; V4 `modeinfo.c` returns FALSE when the ID has no database entry. Resolution: stated "per the V4 source".
- **devices/newstyle.h** — not in the NDK 3.9 include tree used here; `NSCMD_DEVICEQUERY` (0x4000) and `struct NSDeviceQueryResult` layout taken from `ahisrc/Device/device.h`. Resolution: layout given inline.
- **AROS wikibook "Aros/Developer/AHIDrivers"** — despite the title it covers application use (device/library API, sample code), not driver writing. Its claims "device interface has a fixed 20 ms latency" and "CMD_READ blocks AHI exclusively" have no support in the AHI docs (ahiusr readme only says `device.audio` can't serve apps needing < 20 ms). Resolution: latency marked "(community reports ~20 ms, unverified)"; exclusivity claim omitted.
- **C hook trampoline for m68k-amiga-elf-gcc** — the top-level `__asm__` stub (GAS syntax, `%` register prefix, `12(%a0)` = `h_SubEntry`) follows Bartman's template usage and `utility/hooks.h`; not build-tested. Open item (unverified).
- **GCC 14+ int-conversion** — statement that implicit pointer-to-ULONG in varargs tag arrays is an error is standard GCC 14 behaviour (toolchain here is GCC 15.1); not compiled in this session. Open item (unverified locally).
- **AHI_UnloadSound "stop channels first"** — not in the autodoc; taken from PT-AHIPlay `mt_end` (sets `AHI_NOSOUND` on all channels before unloading). Resolution: stated as practice.
- **CMD_WRITE buffers in chip RAM** — no autodoc statement for the device API; LoadSound's "no need for Chip memory" plus SDK examples (PlayTest uses BSS buffers) support "chip RAM not needed". Resolution: stated.
