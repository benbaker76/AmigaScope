# AHI overview

AHI is the retargetable audio system for AmigaOS (author Martin Blom, LGPL device,
GPL tools). A program talks to `ahi.device`; the user decides in the AHI prefs which
driver and mode actually make the sound: Paula, a Zorro/PCI card, or a file
renderer. Use this skill only when the program targets AHI. Programs that poke
Paula (`AUDxLC`, `AUDxPER`, `DMACON`...) or use `audio.device` belong to the
amiga-hardware skill.

## The pieces on disk

What must be installed for an AHI program to run, and what each part does.

| Path | What |
|---|---|
| `DEVS:ahi.device` | The device + library API every program opens |
| `DEVS:AHI/<name>.audio` | Hardware drivers; really libraries (`paula.audio`, `toccata.audio`, `filesave.audio`, `device.audio`...) |
| `DEVS:AudioModes/<NAME>` | IFF-AHIM mode descriptor files, one per driver; loaded into the mode database on first OpenDevice |
| `SYS:Prefs/AHI` | Prefs editor; writes `ENV:Sys/ahi.prefs` (per-unit mode/rate/channels + global options) |
| `C:AddAudioModes` | Rebuild/flush the mode database (install scripts) |
| `L:AHI-Handler` (`AUDIO:`) | DOS device: `copy sample.aiff AUDIO:` plays, reading records |

If `OpenDevice("ahi.device", ...)` fails, AHI is not installed (or older than
`ahir_Version`): fall back to your Paula code or quit with a message.

## Two APIs

AHI has a shared device interface and an exclusive library interface; pick by need.

| | Device interface (high level) | Library interface (low level) |
|---|---|---|
| Open | `OpenDevice(AHINAME, unit 0-3, req)` | `OpenDevice(AHINAME, AHI_NO_UNIT, req)`, `AHIBase = io_Device` |
| Calls | `CMD_WRITE` / `CMD_READ` I/O requests | `AHI_AllocAudioA`, `AHI_LoadSound`, `AHI_SetSound`... |
| Sharing | Many programs at once, AHI mixes them | One owner of the card (unless the user maps the Music unit to `device.audio`, V6) |
| Units | 0-3 configured in prefs | Mode ID you choose (default = prefs "Music unit") |
| Timing | Buffered streams, latency not yours to control | PlayerFunc hook at your rate; Set* calls take effect within about 10 ms in realtime modes |
| Features | Volume, pan, precedence, sync via CMD_STOP/START | Channels, sample IDs, loops, SoundFunc (Paula-style), effects (echo, master volume, scopes), recording hook, hardware controls |
| Lengths | Bytes | Sample frames |
| Good for | Sample players, system sounds, MP3/stream output, simple recording | Games, module players, trackers, realtime effects, quality recording |

Reference: [device-interface.md](../device-interface.md), [functions.md](../functions.md),
[low-level-playback topic](low-level-playback.md).

## Audio modes and the database

How AHI names hardware configurations and where the defaults come from.

- A mode is a driver plus a configuration (mono/stereo, panning, bits, HiFi,
  realtime, record...). It has a 32-bit **audio ID**, like a screenmode ID: upper word
  = hardware ID, lower word = mode (bits 0-4), converter (8-11), card number (12-15).
- `AHI_DEFAULT_ID` (0) = whatever the user set for the Music unit; `AHI_DEFAULT_FREQ`
  (0) = its rate. `AHI_INVALID_ID` (`~0`) = none. Never hardcode real IDs.
- The database is built from `DEVS:AudioModes` and is private: read it with
  AHI_NextAudioID, AHI_GetAudioAttrsA, AHI_BestAudioIDA, or let the user pick with
  AHI_AudioRequestA ([audio-modes topic](audio-modes.md)).
- Typical mode families per driver: *Mono*, *Stereo* (channels hard left/right),
  *Stereo++* (free panning), *Fast* variants (tables / coarse volume, cheaper CPU,
  more RAM), *HiFi* variants (32-bit mixing with interpolation, much slower), *HiFi 7.1*.
- Paula driver specials: 8-bit and 14-bit modes, and a "DMA 8 bit stereo" mode that
  uses Paula's 4 hardware channels directly (4 channels, no panning, fixed rate).
- Prefs units: 0-3 serve device-interface programs; the "Music unit" (`AHI_NO_UNIT`)
  gives the default for library programs. Channels per unit are a user setting.

## Version history

Features by ahi.device version, as marked in the V6 autodocs, includes and readmes.

- **V1, V3** — obsolete.
- **V2** — library API only. Adds hardware controls: `AHIC_InputGain`,
  `AHIC_OutputVolume`, `AHIC_Input`, `AHIC_Output` (+ `_Query`) and `AHIDB_Min/Max*`,
  `AHIDB_Inputs/Outputs`, `AHIDB_Input/Output` names. `ahiac_BuffType` for drivers.
- **V3** — (autodoc bug note) string attributes are NUL-terminated on overflow from V3 on.
- **V4** — the device interface: `CMD_WRITE`, `CMD_READ`, `CMD_START/STOP`,
  `CMD_FLUSH`, `CMD_RESET`, `NSCMD_DEVICEQUERY`, the V4 `AHIRequest` fields; lowest
  version for the device API. Library: AHI_PlayA, AHI_SampleFrameSize, stereo sample
  types `AHIST_S8S`/`AHIST_S16S`, effects `AHIET_DSPMASK`/`DSPECHO`/`CHANNELINFO`,
  negative volume (invert) and pan (surround), `AHIB_Dizzy`, `AHIR_DoDefaultMode`,
  `AHI_DEFAULT_ID` accepted by AHI_GetAudioAttrsA, one-shots/one loop without a
  SoundFunc. AHI_SetEffect returns real error codes. The last release for 68000 CPUs.
- **V5** — ahi.device 5.x development releases (5.1 shipped for the OS 3.9 CD per
  the ChangeLog). The autodocs mark no feature as V5; test for V6 features with 6.
- **V6** (release 6.0, 2005) — 32-bit samples `AHIST_M32S`/`AHIST_S32S`, 7.1
  (`AHIST_L7_1`, `AHIDB_MultiChannel`), anti-click (`AHIA_AntiClickSamples`,
  `AHISF_NODELAY`), `AHISF_NONE`, `AHIR_UserData`/`ahiam_UserData`, `io_Actual` valid on
  aborted requests, AHI_SampleFrameSize returns 0 for bad types, full-volume default
  scaling with clipping, the `device.audio` driver, PowerPC/AROS ports. **Needs a
  68020+**: 68000 machines must use V4.

Set `ahir_Version` to the lowest version whose features you use (4 is the usual
choice for 68000-compatible programs).

## When to use which

Decision guide for picking the right audio path.

| You are writing | Use |
|---|---|
| OS-friendly game/music with module or sfx playback | Library API, PlayerFunc timing |
| Tool playing a WAV/AIFF/MP3 stream | Device API, double-buffered CMD_WRITE |
| "Beep"/UI sounds | Device API, one CMD_WRITE per sound |
| Recorder | Library API + RecordFunc (quality, monitoring) or CMD_READ (simple) |
| Scope/VU on your own output | Library API + `AHIET_OUTPUTBUFFER` |
| Trackmo/bare-metal demo that disables multitasking or takes over the chips | NOT AHI: drive Paula directly (amiga-hardware skill) |

## Building with m68k-amiga-elf-gcc

Toolchain notes for C programs using AHI.

- Add the AHI SDK `Include/C` directory to the include path: `devices/ahi.h`,
  `proto/ahi.h`, `inline/ahi.h`, `clib/ahi_protos.h`. `inline/ahi.h` uses the same
  `LPx` macros as the NDK's `inline/macros.h`.
- Define `struct Library *AHIBase;` yourself and set it from `io_Device`.
- Varargs tag calls build a ULONG array: cast every pointer, `(ULONG)&hook`
  (GCC 14+ makes the implicit conversion an error).
- Hooks are entered with arguments in A0/A2/A1; GCC cannot receive register
  arguments, so point `h_Entry` at a small asm stub that calls `h_SubEntry`
  ([low-level-playback topic](low-level-playback.md#hooks)).
- Asm: add SDK `Include/Asm` for `devices/ahi.i`, `lvo/ahi_lib.i`,
  `libraries/ahi_sub.i`.

## Common mistakes

Frequent errors when first using AHI.

- Treating `ahi.device` as a library (`OpenLibrary`). Open the device, take `io_Device`.
- Not setting `ahir_Version` before OpenDevice.
- Disabling multitasking (Forbid/Disable, killing interrupts) while AHI plays: most
  drivers need tasks and interrupts running.
- Passing integers where AHI wants Fixed: volume 64 instead of `0x10000`, PlayerFreq
  50 instead of `50<<16`.
- Mixing frame and byte counts between the two APIs.
- Hardcoding an audio ID copied from your own machine.
- Expecting chip RAM rules: AHI sample data only needs to be non-swappable
  (`MEMF_PUBLIC`); AHI mixes it into the driver's own output buffers.
