---
name: amiga-os
description: AmigaOS 3.x system reference - every public function of exec, dos, graphics, intuition, diskfont, utility, layers and lowlevel, the timer/input device functions and cia/potgo resources (LVO, registers, C prototype, version, pitfalls), plus timer.device, input.device and audio.device commands, calling conventions, tag lists, hooks, structures and memory rules. Use whenever writing, reviewing or debugging Amiga C (m68k-amiga-elf-gcc + NDK) or assembler that calls the OS - memory, tasks, messages, interrupts, files, screens, windows, IDCMP, bitmaps, blits, copper lists, colours, fonts, layers, joysticks/CD32 pads, keyboard input handlers, timers, audio channels, CIA timers - or when decoding a jsr -offset(a6). Never guess an LVO, register, command or flag - look it up.
---

# AmigaOS libraries, devices and resources

Function entries are distilled from the NDK 3.9 autodocs (cross-checked with the V37
autodocs). The first three lines of every entry - heading, C prototype + LVO, register
assignment - are GENERATED from the NDK 3.9 SFD files and clib prototypes and validated by
`tools/skills/amiga_skill_data.py check`: trust them over memory.

## Hard rules

- **Calling convention:** A6 = library base before every call; arguments in exactly the
  registers the entry lists; result in D0; D0/D1/A0/A1 and the flags are trashed - test D0
  yourself (`tst.l d0`). SysBase is at address 4 (`move.l 4.w,a6`) and is never opened.
  Some calls use unusual registers (dos.library D1-D4, LockLayerRom's Layer in A5,
  FindColor's ColorMap in A3): always read the `Registers:` line.
- **Open with a real minimum version** and check the result: V36+ for tags, AllocVec,
  CreateMsgPort/CreateIORequest; V37 for most intuition/dos tag calls; V39 for pools,
  AllocBitMap, RGB32 colours, pens, ScreenBuffers; V40 WriteChunkyPixels; V45 (OS 3.5+)
  for NewMinList/AVL. Kickstart 3.1 is exec V40. Never pass version 0.
- **Bartman gcc (m68k-amiga-elf-gcc 15 + NDK):** base globals must be named `SysBase`,
  `DOSBase`, `GfxBase`, `IntuitionBase`, `DiskfontBase`; library function names are macros
  (don't reuse them for your own functions); in `...Tags()`/`Printf`/`EasyRequest` varargs
  cast every pointer to `(ULONG)`/`(LONG)` and use `%ld`/`%lx`/`%lu` (RawDoFmt reads `%d`
  as 16-bit); a few inline macros with `**` parameters (AllocRemember, NextTagItem,
  AVL_AddNode...) need `-Wno-error=incompatible-pointer-types`. No amiga.lib: use
  `<inline/alib.h>` for NewList/BeginIO only.
- **Asm names:** `include "lvo/<lib>_lib.i"` and `jsr _LVOName(a6)`. The NDK STRUCTURE
  macros define labels such as `GfxBase`, `RastPort`, `BitMap`, `View`: name your base
  variables `_GfxBase` etc. in vasm sources.
- **Memory:** anything the custom chips touch needs `MEMF_CHIP`; use `MEMF_ANY` (not
  `MEMF_FAST`) for CPU data. Free with the matching call and size (AllocMem/FreeMem,
  AllocVec/FreeVec, AllocPooled/FreePooled) only after the hardware has stopped using it.
- **Lists and ports:** a zeroed List is corrupt, not empty - initialise it (NewList). Empty
  test: `lh_TailPred == (struct Node *)list`. After a port signal loop GetMsg until NULL;
  ReplyMsg everything you receive; copy IntuiMessage fields before replying.
- **Forbid/Disable are broken by any Wait** (DOS I/O, WaitPort, device I/O, semaphores).
  Only Signal, ReplyMsg, Cause, Disable/Enable are interrupt-safe; never AllocMem, Wait,
  OpenLibrary or dos from an interrupt. VERTB servers return with Z set.
- **dos.library:** only Processes may call it (not plain Tasks, interrupts, or code under
  Disable); load files BEFORE a bare-metal takeover. BPTR = address >> 2; FileInfoBlock
  and friends come from AllocDosObject; read IoErr() right after a failure. Return
  conventions differ per call (Read/Write/Seek use -1; PutStr, MatchFirst and SystemTagList
  return 0 on success): check the entry.
- **Devices:** OpenDevice returns 0 on SUCCESS (unlike OpenLibrary). After AbortIO still
  WaitIO; collect every SendIO reply before CloseDevice.
- **graphics:** the blitter runs asynchronously - WaitBlit before reading blitted planes or
  freeing bitmaps. Display takeover: save `GfxBase->ActiView`, `LoadView(NULL)` +
  `WaitTOF` x2, OwnBlitter; on exit write `GfxBase->copinit` to COP1LC, LoadView(old) +
  WaitTOF x2, DisownBlitter. RGB32 components are left-justified (`c8 * $01010101`);
  LoadRGB32 tables are `count<<16|first`, triplets, 0 terminator. On shared screens use
  ObtainBestPen, never SetRGB a shared pen. Mode IDs compare with `INVALID_ID`
  (LORES_KEY is 0).
- **intuition:** tags need V37; cleanup order ClearMenuStrip -> CloseWindow -> CloseScreen
  (check TRUE) -> CloseFont -> CloseLibrary; draw inside `BorderLeft/BorderTop`; never
  call dos while VERIFY IDCMP classes are enabled; window move/size calls are deferred.
- **Fonts:** graphics OpenFont only finds fonts already in memory; disk fonts need
  diskfont OpenDiskFont (a Process). Release both with CloseFont.
- **utility:** V36+. Hooks are called with A0 = hook, A2 = object, A1 = message (not C
  order) and need an asm stub for C code; with gcc 15 cast `(HOOKFUNC)(void (*)(void))fn`.
  Never walk tag arrays with `ti++` - use NextTagItem; the math calls return the remainder
  or high half in D1.
- **layers:** never move/size/depth/delete a window's layer yourself (use intuition);
  `InstallClipRegion(l, NULL)` before DeleteLayer/CloseWindow/DisposeRegion; the classic
  calls take an unused dummy in A0 and the layer in A1.
- **lowlevel (V40):** test `ReadJoyPort` results with `JP_TYPE_MASK` before reading bits;
  SetJoyPortAttrsA needs revision 40.27; interrupt routines return D0 = 0 and must be
  removed before exit.
- **input.device handlers** get the event list in A0 and return it in D0; write them in
  asm, never block, remove with IND_REMHANDLER before freeing. Its settings are global.
- **timer.device:** TimerBase = `io_Device` of an open timer request; one request = one
  pending wait (`if (!CheckIO(r)) AbortIO(r); WaitIO(r);`); reload `tr_time` each time;
  CmpTime(a, b) is -1 when `a` is LATER. Use absolute E-clock deadlines for periodic ticks.
- **audio.device:** commands only; allocate channels at OpenDevice with a mask array and
  precedence, pass the allocation key with every command, send CMD_WRITE with
  `ADIOF_PERVOL` through BeginIO (DoIO/SendIO wipe `io_Flags`). Direct Paula pokes on
  channels the device owns are the classic conflict.
- **Resources:** `OpenResource("ciaa.resource")`/`"ciab.resource"`/`"potgo.resource"` -
  never OpenLibrary. Claim a CIA timer with AddICRVector (non-zero result = someone owns
  it); with the OS running, POTGO bits must come from AllocPotBits.
- **Never invent.** If a function, flag or tag is not in `reference/`, say so. Claims
  marked `(unverified)` could not be checked against the autodocs, includes or a compile.

## How to look things up

- Any function or device command: `reference/index.md` (all functions alphabetically with
  library, LVO and entry link, plus the device commands), or the per-library table at the
  end of `reference/<lib>/index.md`.
  Machine-readable LVO/register tables: `reference/data/<lib>.tsv`.
- Library intros (opening, version landmarks, register quirks) and group files:
  `reference/exec/`, `reference/dos/`, `reference/graphics/`, `reference/intuition/`,
  `reference/diskfont/`, `reference/utility/` (tags, hooks, math, dates, namespaces),
  `reference/layers/` (plus `concepts.md`), `reference/lowlevel/` (ReadJoyPort, keyboard,
  interrupts, SystemControl).
- Devices: `reference/timer/` (units, functions, commands, `timing-recipes.md`),
  `reference/input/` (handler chain, InputEvent, IND_ commands), `reference/audio/`
  (channel allocation, commands, `playing-samples.md`). Resources: `reference/cia/`
  (claiming CIA timers), `reference/potgo/` (extra fire buttons, CD32 pads). Concepts per library: `dos/concepts.md` (BPTR/BSTR, locks vs
  handles, processes), `graphics/concepts.md` (GfxBase fields, View/ViewPort/RastPort,
  mode IDs, bitmaps), `intuition/concepts.md` (IDCMP loop, SA_/WA_ tags, public screens).
- Cross-library guides: `reference/topics/calling-convention.md`,
  `opening-libraries.md`, `taglists.md`, `structures.md` (field-exact exec structures with
  asm offsets), `memory-rules.md`. The SAD serial debugger protocol:
  `reference/exec/sad-debugger.md`.
- Autodoc vs include discrepancies, toolchain traps and unverified items:
  `reference/errata.md`; sources: `reference/SOURCE.md`.
- Register-level hardware: the amiga-hardware and amiga-aga skills. Instruction and
  directive details: the m68k-asm skill. AHI audio: the amiga-ahi skill. Debugging a live
  program: the amigascope-workflow skill.
