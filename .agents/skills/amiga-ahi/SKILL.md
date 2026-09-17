---
name: amiga-ahi
description: AHI (Audio Hardware Interface) retargetable audio for AmigaOS - opening ahi.device, the low-level AHI_ library calls (AllocAudio, LoadSound, SetSound/SetFreq/SetVol, ControlAudio, hooks), the device I/O interface (CMD_WRITE/CMD_READ), tags, audio modes, effects, recording, and AHI driver basics. Use ONLY when the program targets AHI (ahi.device installed); direct Paula register access or audio.device is not AHI.
---

# AHI audio

## GATE - read first

AHI is an OS-level sound system (`DEVS:ahi.device` plus audio mode drivers). Use this
skill only when the program is meant to play or record through AHI. Code that hits Paula's
registers directly belongs to the amiga-hardware skill. AHI needs the OS running: no
system takeover (Forbid/Disable, interrupts off) while it plays. AHI 6 needs a 68020+;
68000 machines use AHI 4.

## Hard rules

- **There is no OpenLibrary for AHI.** `CreateIORequest(port, sizeof(struct AHIRequest))`,
  set `ahir_Version` (4, or 6 for V6 features) BEFORE `OpenDevice(AHINAME, AHI_NO_UNIT,
  req, 0)`, then `AHIBase = req->ahir_Std.io_Device`. Device-API programs open unit
  `AHI_DEFAULT_UNIT` (0) instead. Asm: `jsr _LVOAHI_xxx(a6)` with the base in A6; the
  AudioCtrl argument is always A2; D0/D1/A0/A1 are scratch.
- **Interrupt/hook context:** only AHI_SetVol, AHI_SetFreq, AHI_SetSound and
  AHI_ControlAudioA (without `AHIC_Play`/`AHIC_Record`) may be called from
  SoundFunc/PlayerFunc/RecordFunc or interrupts. Never AHI_SetEffect, AHI_LoadSound or
  AHI_FreeAudio there.
- **`AHISF_IMM`:** must be 0 inside SoundFunc, may be either inside PlayerFunc, must be set
  everywhere else. A one-shot from task code is AHI_PlayA with `AHIP_LoopSound,
  AHI_NOSOUND`.
- **Fixed point everywhere:** volume `0x10000` = 1.0; pan `0` left, `0x8000` centre,
  `0x10000` right; `AHIA_PlayerFreq` = `hz<<16`, always with `AHIA_MinPlayerFreq` and
  `AHIA_MaxPlayerFreq`. Paula volume 0-64 -> `vol<<10`; a ProTracker period ->
  `3546895/period` Hz.
- **A note needs all three calls:** nothing plays until AHI_SetSound AND AHI_SetFreq, it is
  silent without AHI_SetVol, and nothing is heard before `AHIC_Play, TRUE`. Started sounds
  loop until changed.
- **Units differ:** the library API counts sample FRAMES (`ahisi_Length`, Offset, Length);
  the device API's `io_Length` counts BYTES. Convert with AHI_SampleFrameSize.
- **Hooks** are called with A0 = hook, A2 = AHIAudioCtrl, A1 = message and must preserve
  D2-D7/A2-A6; RecordFunc returns 0. With m68k-amiga-elf-gcc point `h_Entry` at a small
  asm stub that pushes A1/A2/A0 and calls `h_SubEntry`. In varargs tag calls cast every
  pointer to `(ULONG)`.
- **Memory and teardown:** samples need `MEMF_PUBLIC`, not chip RAM; `AHIST_SAMPLE` data is
  read-only once loaded. Tear down in this order: `AHIC_Play, FALSE` -> cancel every effect
  (`AHIET_CANCEL`) -> AHI_FreeAudio (unloads sounds) -> free sample memory -> CloseDevice ->
  DeleteIORequest -> DeleteMsgPort.
- **Modes:** use `AHI_DEFAULT_ID`/`AHI_DEFAULT_FREQ` or a user-chosen ID
  (AHI_AudioRequestA); never hard-code mode IDs. Read the real mixing rate with
  `AHIC_MixFreq_Query`. AHI_BestAudioIDA booleans are strict (FALSE excludes). Time music
  from PlayerFunc, not VBlank or CIA timers, so non-realtime modes work.
- **Device API:** duplicate the opened request (AllocVec + CopyMem, free with FreeVec) for
  each extra simultaneous sound or for double buffering via `ahir_Link`; after completion
  every field except io_Device/io_Unit/io_Command is trashed; applications never send
  CMD_FLUSH/CMD_RESET, and CMD_STOP/CMD_START affect every program.
- **The `OPENAHI`/`CLOSEAHI` macros in `devices/ahi.i` are unsafe on failure paths** - use
  hand-written open/close code (see `reference/device-interface.md`).
- **Never invent.** Four functions (AHI_SetVol/SetFreq/SetSound/SetEffect) have no entry in
  the 6.0 SDK autodoc and were written from the AHI source; anything else not in
  `reference/` should be treated as unknown.

## How to look things up

- A function: `reference/index.md`, then `reference/functions.md` (every public call with
  its LVO and registers). Machine-readable: `reference/data/ahi.tsv`.
- The device I/O interface (AHIRequest, commands, double buffering, examples):
  `reference/device-interface.md`.
- Tags, flags, sample types, error codes, effect structures with offsets:
  `reference/tags.md`.
- How-to guides: `reference/topics/overview.md`, `low-level-playback.md` (complete C and
  vasm programs, ProTracker mapping), `audio-modes.md`, `effects.md`, `recording.md`,
  and `drivers.md` (only for writing AHI drivers; `data/ahi_sub.tsv`).
- Doc bugs and header mismatches: `reference/errata.md`; sources: `reference/SOURCE.md`.
- exec/dos calls used around AHI (CreateMsgPort, OpenDevice, AllocVec...): the amiga-os
  skill. Paula hardware: the amiga-hardware skill.
