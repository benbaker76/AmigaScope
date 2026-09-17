# exec.library: system, caches and diagnostics

Odds and ends every program eventually needs: RawDoFmt (the ROM's printf engine), Alert and
Debug for crash reporting, the CPU cache calls that must follow self-modifying or hand-loaded
code on 68020+ machines, and ColdReboot. The cache functions are absent on Kickstart 1.x
(check `SysBase->LibNode.lib_Version` first). The last section lists the private LVO slots so
disassembly and patch code can be recognised.

## RawDoFmt
`APTR RawDoFmt(CONST_STRPTR formatString, CONST APTR dataStream, VOID (*CONST putChProc)(), APTR putChData)` — LVO -522 (-$20A)
Registers: formatString=A0, dataStream=A1, putChProc=A2, putChData=A3; result in D0

Format a data stream with a printf-like string, emitting one character at a time.

- **formatString** — NUL-terminated format. `%%` prints a percent sign. Conversions are
  `%[flags][width.limit][length]type`:
  - flags: `-` left-justifies; a width starting with `0` pads with zeros.
  - `.limit` — maximum characters taken from a `%s` string (only valid for `%s`).
  - length: `l` = 32-bit argument. WITHOUT `l`, `d`, `x` and `c` read a 16-bit WORD.
  - types: `d` signed decimal, `u` unsigned decimal (V37), `x` hex, `c` character, `s`
    32-bit pointer to a C string (NULL prints as empty from V36), `b` 32-bit BPTR to a BCPL
    string (V36; NULL BPTR prints as empty).
- **dataStream** — packed arguments, read in order: WORD for plain `%d/%x/%c`, LONG for
  `%ld/%lx/%lu`, `%s`, `%b`. No alignment padding between them.
- **putChProc** — routine called for every output character with the character in D0 (low
  byte) and putChData in A3; called once more with a NUL at the end. From V45.1 it may be
  NULL, which selects a built-in `move.b d0,(a3)+` style copy into putChData.
- **putChData** — passed to putChProc in A3; putChProc may change A3 and the new value is
  kept for the next character (so `(a3)+` walks a buffer).
- **Result** — pointer just past the last argument consumed (V36+; garbage before V36), for
  multi-pass formatting.

### Example
```asm
        include "lvo/exec_lib.i"

        movem.l a2-a3/a6,-(sp)
        move.l  4.w,a6
        move.l  score,fmtargs           ; fill the data stream at run time
        move.w  lives,fmtargs+4
        lea     fmtstr,a0
        lea     fmtargs,a1
        lea     putch(pc),a2
        lea     textbuf,a3              ; output pointer, advanced by putch
        jsr     _LVORawDoFmt(a6)
        movem.l (sp)+,a2-a3/a6
        rts

putch:  move.b  d0,(a3)+                ; copies the final NUL too
        rts

fmtstr:  dc.b   "Score %06ld  Lives %d",0
        even
fmtargs: dc.l   0                       ; %06ld: LONG
        dc.w    0                       ; %d: WORD
textbuf: ds.b   40
```

```c
/* move.b d0,(a3)+ ; rts -- a two-word PutChProc usable from C */
static const UWORD stuffChar[] = { 0x16c0, 0x4e75 };

void FormatScore(char *buf, ULONG score, ULONG lives)   /* buf >= 32 bytes */
{
    ULONG args[2];

    args[0] = score;
    args[1] = lives;
    RawDoFmt((CONST_STRPTR)"Score %06ld  Lives %ld", (APTR)args,
             (VOID (*)())stuffChar, (APTR)buf);
}
```

### Gotchas
- The WORD default is the classic bug: with 32-bit ints (GCC) every numeric conversion needs
  `l` (`%ld`, `%lx`, `%lu`, even `%lc`). The Bartman template's KPrintF also passes its
  varargs straight to RawDoFmt, so the same rule applies there.
- No length limit on output: size the buffer for the worst case.
- Do not rely on the NULL putChProc shortcut unless exec is V45 or newer (Kickstart 3.1 is V40).
- `%u` needs V37 and `%b` V36; older ROMs print them wrongly.

**See also:** [Debug](system.md#debug), dos.library VFPrintf, amiga.lib sprintf

## Alert
`VOID Alert(ULONG alertNum)` — LVO -108 (-$6C)
Registers: alertNum=D7; no result

Stop the machine with a guru/alert display, or show a recoverable alert and continue.

- **alertNum** — 32-bit code in D7 (exec/alerts.h). -1 is not allowed. Layout:
  - bit 31 — `AT_DeadEnd` (0x80000000): fatal, never returns; `AT_Recovery` (0): may return.
  - bits 30-24 — subsystem: e.g. `AN_ExecLib` 0x01000000, `AN_GraphicsLib` 0x02000000,
    `AN_Intuition` 0x04000000, `AN_DOSLib` 0x07000000.
  - bits 23-16 — general error: `AG_NoMemory` 0x00010000, `AG_MakeLib` 0x00020000,
    `AG_OpenLib` 0x00030000, `AG_OpenDev` 0x00040000, `AG_OpenRes` 0x00050000,
    `AG_IOError` 0x00060000, `AG_NoSignal` 0x00070000, `AG_BadParm` 0x00080000, ...
  - bits 15-0 — object or specific code: `AO_ExecLib` 0x00008001, `AO_GraphicsLib`
    0x00008002, `AO_Intuition` 0x00008004, `AO_DOSLib` 0x00008007, ...
  - CPU exceptions use `ACPU_` codes, e.g. `ACPU_BusErr` 0x80000002, `ACPU_AddressErr`
    0x80000003, `ACPU_DivZero` 0x80000005.

Interrupts are disabled while the alert is shown. If it cannot be displayed the machine
resets and Exec posts it after the reboot. A recoverable alert may return to the caller.

From V39 the display times out after the number of frames in `LastAlert[3]` (ExecBase,
`LastAlert` = $202); the value survives warm reboots and 0 suppresses the display. Leave it to
the user: it exists for unattended machines.

### Example
```c
#include <exec/alerts.h>

DOSBase = (struct DosLibrary *)OpenLibrary((CONST_STRPTR)"dos.library", 0);
if (DOSBase == NULL) {
    Alert(AG_OpenLib | AO_DOSLib);           /* recoverable: returns */
    return 20;
}
```

### Gotchas
- The argument goes in D7, not D0. The asm `ALERT` / `DEADALERT` macros in exec/alerts.i
  load D7 (and an optional parameter pointer into A5) and fetch ExecBase from address 4.
- Only dead-end alerts may be raised from interrupt code.
- Post-mortem: before a reset the power LED blinks; a terminal on the built-in serial port
  (9600 baud, 8N1) can press DEL during the blinking to enter the ROM debugger.
- alerts.h defines `AN_MemCorrupt` as 0x81000005 (dead-end) while the memory autodocs quote
  $01000005.

**See also:** [Debug](system.md#debug), [ColdReboot](system.md#coldreboot)

## Debug
`VOID Debug(ULONG flags)` — LVO -114 (-$72)
Registers: flags=D0; no result

Enter the system debugger: SAD from V39, ROM-WACK before that.

- **flags** — pass 0 (reserved for future use).

Third-party debuggers take over this entry with SetFunction so a program's Debug() call lands
in them.

### Gotchas
- With nothing attached, SAD waits on the serial port and only resumes after its heartbeat
  timeout (10 prompts at 2 s intervals, roughly 20 s): not a "break if debugger present".
- A SetFunction patch must cope with being called in a bad system state, possibly in
  supervisor mode, and with the different exception stack frames of 68000/010/020/030/040.
- ROM-WACK (pre-V39) trashed A5 and the user stack pointer when entered from supervisor mode.
- Pre-V40 SAD numbers its commands off by one; see the SAD protocol page.

**See also:** [SAD protocol](sad-debugger.md), [SetFunction](libraries-devices-resources.md#setfunction),
[Alert](system.md#alert)

## CacheClearU
`VOID CacheClearU(VOID)` — LVO -636 (-$27C)
Registers: none; no result

Flush the CPU instruction and data caches, writing back dirty copyback data first.

Call it after anything that places or changes code behind the CPU's back: self-modifying
code, filling in jump tables or JMP instructions, run-time patches, relocating or loading
code yourself (for example decrunching an executable into memory). LoadSeg, MakeLibrary and
SetFunction already do it.

Since V37.

### Example
```asm
        include "exec/libraries.i"
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        cmp.w   #37,LIB_VERSION(a6)
        bcs.s   .nocache                ; LVO not present on 1.x
        jsr     _LVOCacheClearU(a6)
.nocache:
        jmp     (a2)                    ; now safe to run the new code
```

### Gotchas
- On a 68020+ with caches on, jumping into freshly written code without this call can run
  stale instructions. A 68000 has no caches to flush.
- Guard with a version check: calling LVO -636 on Kickstart 1.x crashes.

**See also:** [CacheClearE](system.md#cachecleare), [CacheControl](system.md#cachecontrol)

## CacheClearE
`VOID CacheClearE(APTR address, ULONG length, ULONG caches)` — LVO -642 (-$282)
Registers: address=A0, length=D0, caches=D1; no result

Flush selected caches for an address range, pushing dirty copyback data first.

- **address** — start of the area; may be rounded to the cache granularity.
- **length** — bytes, or `$FFFFFFFF` for the whole address space.
- **caches** — `CACRF_ClearI` ($8) for the instruction cache, `CACRF_ClearD` ($800) for the
  data cache; other bits reserved.

Since V37.

### Gotchas
- The range is only a hint: the call may flush the entire cache (likely on a 68030).
- Chip RAM on all Amiga models runs with instruction caching on and data caching off, and the
  custom chip registers are marked non-cacheable, so blitter/DMA writes to chip RAM do not need
  a data-cache flush.

**See also:** [CacheClearU](system.md#cacheclearu), [CacheControl](system.md#cachecontrol)

## CacheControl
`ULONG CacheControl(ULONG cacheBits, ULONG cacheMask)` — LVO -648 (-$288)
Registers: cacheBits=D0, cacheMask=D1; result in D0

Read or change the global CPU cache settings, returning the previous settings.

- **cacheBits** — new values for the bits selected by cacheMask.
- **cacheMask** — which bits to change; 0 only reads.
- **Result** — all previous settings.

Bits follow the 68030 CACR layout (exec/execbase.h / execbase.i): `CACRF_EnableI` $1,
`CACRF_FreezeI` $2, `CACRF_ClearI` $8, `CACRF_IBE` $10, `CACRF_EnableD` $100, `CACRF_FreezeD`
$200, `CACRF_ClearD` $800, `CACRF_DBE` $1000, `CACRF_WriteAllocate` $2000, `CACRF_EnableE`
$40000000 (external caches), `CACRF_CopyBack` $80000000. Other CPUs and cache boards map them
as closely as possible.

### Example
```c
#define MY_CACHES (CACRF_EnableI | CACRF_EnableD)

ULONG old = CacheControl(0, MY_CACHES);     /* caches off, remember state */
RunTimingSensitiveCode();
CacheControl(old, MY_CACHES);               /* restore exactly */
```

### Gotchas
- Settings are global, not per task: always restore the old bits.
- Every call also flushes all caches.
- Leave `CACRF_WriteAllocate` set (the include marks it "must always be set" for the 68030).
- Not in Kickstart 1.x (clib/exec_protos.h lists it with the V36 functions).

**See also:** [CacheClearU](system.md#cacheclearu), [CacheClearE](system.md#cachecleare)

## CachePreDMA
`APTR CachePreDMA(CONST APTR address, ULONG *length, ULONG flags)` — LVO -762 (-$2FA)
Registers: address=A0, length=A1, flags=D0; result in D0

Prepare a memory range for a DMA transfer and get its physical address.

- **address** — virtual start address of the buffer.
- **length** — pointer to a ULONG holding the wanted length; updated to the contiguous
  physical length available at the result, which may be shorter.
- **flags** — `DMA_Continue` ($2) when continuing a range that was split by an earlier call;
  `DMA_ReadFromRAM` ($8) when data flows from RAM to the device (e.g. a disk write). Asm
  names from execbase.i: `DMAF_Continue`, `DMAF_ReadFromRAM`.
- **Result** — physical address for the DMA controller.

For DMA device-driver writers. On 68000-68030 it does nothing; on a 68040 it writes matching
dirty cache lines back to memory; MMU/VM or cache-board software may patch it. To cover a
buffer that comes back shorter, call again for the remainder with `DMA_Continue`.

Since V37.

### Gotchas
- Every CachePreDMA needs a matching CachePostDMA; `DMA_ReadFromRAM` must be used on both or
  neither.
- The NDK prototype uses `ULONG *length`; the autodoc says `LONG *`.

**See also:** [CachePostDMA](system.md#cachepostdma), [CacheClearE](system.md#cachecleare)

## CachePostDMA
`VOID CachePostDMA(CONST APTR address, ULONG *length, ULONG flags)` — LVO -768 (-$300)
Registers: address=A0, length=A1, flags=D0; no result

Finish a DMA transfer started with CachePreDMA.

- **address** — the same address given to CachePreDMA.
- **length** — the same length pointer given to CachePreDMA.
- **flags** — `DMA_NoModify` ($4) if the transfer did not change memory (no flush needed);
  `DMA_ReadFromRAM` ($8) if it was used on the CachePreDMA call. Asm: `DMAF_NoModify`,
  `DMAF_ReadFromRAM`.

Does nothing on 68000-68020, flushes the data cache on a 68030 and the matching parts of it on
a 68040.

Since V37.

**See also:** [CachePreDMA](system.md#cachepredma), [CacheClearU](system.md#cacheclearu)

## ColdReboot
`VOID ColdReboot(VOID)` — LVO -726 (-$2D6)
Registers: none; no result

Reset the whole machine, expansion boards included, as if power-cycled.

Never returns. External memory and peripherals are reset and the power-up diagnostics run.

Since V36.

### Example
```asm
        move.l  4.w,a6
        cmp.w   #36,LIB_VERSION(a6)
        bcs.s   .noreboot               ; not in Kickstart 1.x
        jsr     _LVOColdReboot(a6)      ; does not return
.noreboot:
```

### Gotchas
- LVO -726 does not exist before V36.
- Exec V45 made it more reliable on 68040/68060 machines and with a moved VBR (exec release
  notes).

**See also:** [Alert](system.md#alert)

## Private and reserved LVOs

Exec jump-table slots that are private or reserved: never call them from portable code.

Offsets counted from the NDK 3.9 `fd/exec_lib.fd` (bias 30, 6 bytes per slot):

| LVO | fd name | Notes |
|---|---|---|
| -36 .. -66 | execPrivate1-6 | "special patchable hooks to internal exec activity" |
| -504 | execPrivate7 | commonly called RawIOInit (unverified) |
| -510 | execPrivate8 | commonly called RawMayGetChar (unverified) |
| -516 | execPrivate9 | commonly called RawPutChar (unverified): character in D0 to the serial port |
| -738 .. -756 | execPrivate10-13 | named ChildFree, ChildOrphan, ChildStatus, ChildWait in `include_i/exec/exec_lib.i` |
| -792 .. -822 | execPrivate14-19 | `exec_lib.i` names them execPrivate10-15 |
| -834 .. -846 | execPrivate20-22 | `exec_lib.i` names them ExecReserved10-12 |
| -912 .. -966 | (10 reserved slots) | fd ends with `##bias 972` |

- The fd group around -504..-516 is headed "private diagnostic support". The Bartman
  template's KPrintF fallback does `jsr -$204(a6)` (-516) with the character in D0 to send
  debug text to the serial port; that routine is fine for your own debug builds, not for
  released code.
- Bartman's `lvo/exec_lib.i` defines no `_LVO` symbols for these slots (the NDK
  `exec/exec_lib.i` FUNCDEF list does name them), so disassemblies show bare offsets.

**See also:** [Debug](system.md#debug), [RawDoFmt](system.md#rawdofmt),
[calling convention](../topics/calling-convention.md)
