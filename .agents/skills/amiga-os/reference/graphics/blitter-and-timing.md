# graphics.library: blitter access and display timing

The blitter is shared by every task and by graphics.library itself. To drive its registers
yourself either lock it with [OwnBlitter](#ownblitter) -> [WaitBlit](#waitblit) -> poke ->
[WaitBlit](#waitblit) -> [DisownBlitter](#disownblitter), or queue a callback with
[QBlit](#qblit)/[QBSBlit](#qbsblit) that runs when the blitter is free. Frame timing:
[WaitTOF](#waittof) sleeps until the next vertical blank (the normal once-per-frame sync),
[WaitBOVP](#waitbovp) busy-waits until the beam has passed a ViewPort, [VBeamPos](#vbeampos)
reads the beam line. [SetChipRev](#setchiprev) enables post-OCS chip features. See
[blitter ownership](concepts.md#blitter-ownership) and
[taking over the display](concepts.md#taking-over-the-display).

## OwnBlitter
`VOID OwnBlitter(VOID)` — LVO -456 (-$1C8)
Registers: none; no result

Get exclusive use of the blitter, sleeping until it is available.

When it returns you own the blitter, but the previous owner's last blit may still be running:
call [WaitBlit](#waitblit) before writing any blitter register.

### Example
```c
/* exclusive blitter section: clear 40 words at a chip RAM address */
void hw_clear(UWORD *chipmem)
{
    struct Custom *hw = (struct Custom *)0xDFF000;

    OwnBlitter();
    WaitBlit();                       /* previous owner may still be blitting */
    hw->bltcon0 = DEST;               /* only D enabled, minterm 0 -> clear */
    hw->bltcon1 = 0;
    hw->bltdpt  = (APTR)chipmem;
    hw->bltdmod = 0;
    hw->bltsize = (1 << HSIZEBITS) | 40;   /* 1 row, 40 words */
    WaitBlit();                       /* let it finish before anyone else uses it */
    DisownBlitter();
}
```

```asm
        include "hardware/custom.i"
        include "hardware/blit.i"
; own the blitter around direct register access (a5 = $dff000)
BlitSection:
        movem.l a5-a6,-(sp)
        move.l  _GfxBase,a6
        lea     $dff000,a5
        jsr     _LVOOwnBlitter(a6)
        jsr     _LVOWaitBlit(a6)        ; old blit may still run
        ; ... write bltcon0/bltapt/.../bltsize(a5) here ...
        jsr     _LVOWaitBlit(a6)
        jsr     _LVODisownBlitter(a6)
        movem.l (sp)+,a5-a6
        rts
```

### Gotchas
- Calls do not nest: calling OwnBlitter twice -- or calling a graphics function that uses the
  blitter (BltBitMap, Text, RectFill, AreaEnd, BltClear, ...) while you own it -- deadlocks.
- It may sleep, so never call it from an interrupt; under Forbid the wait breaks the Forbid.
- Keep the section short: all system rendering stops while you own the blitter.
- Also the lock for direct use of `GfxBase->ChunkyToPlanarPtr` hardware (V40).

**See also:** [DisownBlitter](#disownblitter), [WaitBlit](#waitblit), [QBlit](#qblit)

## DisownBlitter
`VOID DisownBlitter(VOID)` — LVO -462 (-$1CE)
Registers: none; no result

Release the blitter obtained with OwnBlitter.

### Gotchas
- Call [WaitBlit](#waitblit) first if you started a blit, so the next owner does not find it busy
  mid-operation.
- Only the task that called [OwnBlitter](#ownblitter) may release it, once.

**See also:** [OwnBlitter](#ownblitter), [WaitBlit](#waitblit)

## WaitBlit
`VOID WaitBlit(VOID)` — LVO -228 (-$E4)
Registers: none; no result

Wait until the blitter has finished its current operation.

Unusually, it preserves D0/D1/A0/A1 (the condition codes may change).

### Example
```asm
; make sure the blitter is idle before the CPU reads a blitted plane
SafeRead:
        move.l  a6,-(sp)
        move.l  _GfxBase,a6
        jsr     _LVOWaitBlit(a6)        ; d0/d1/a0/a1 survive
        move.l  (sp)+,a6
        rts
```

### Gotchas
- Needed after any rendering call before the CPU reads the result, before freeing memory the
  blitter uses, and before writing blitter registers yourself: graphics calls return while the
  blit is still running.
- Does not wait for blits still queued with [QBlit](#qblit)/[QBSBlit](#qbsblit).
- Works around the old Agnus BUSY-bit timing bugs (early start and early stop) by testing the
  bit repeatedly -- another reason to prefer it over a hand-written `btst #DMAB_BLTDONE` loop.

**See also:** [OwnBlitter](#ownblitter), [DisownBlitter](#disownblitter)

## QBlit
`VOID QBlit(struct bltnode *blit)` — LVO -276 (-$114)
Registers: blit=A1; no result

Queue a routine to be called when the blitter is free for you.

- **blit** — `struct bltnode` (hardware/blit.h; asm blit.i): `n` / `bn_n` (link, system),
  `function` / `bn_function` (your routine), `stat` / `bn_stat` (set `CLEANUP` $40 --
  asm `CLEANME` -- to have `cleanup` called), `blitsize` / `bn_blitsize`, `beamsync` /
  `bn_beamsync` (used by [QBSBlit](#qbsblit)), `cleanup` / `bn_cleanup` (routine called when
  the node is done).

When `function` runs the blitter is yours: load the registers and start the blit. Queued
requests go ahead of tasks waiting in [OwnBlitter](#ownblitter). The routine is called with the
custom chip base in A0 and the bltnode in A1, and returns 0 in D0 when finished or non-zero to
be called again after the next blit completes (unverified -- not in the autodoc; RKM
convention).

### Gotchas
- `function` and `cleanup` run from the blitter interrupt / queue handler: no Wait, no memory
  allocation or FreeMem, no DOS; set a flag or `Signal()` a task. The cleanup routine is the only
  safe way to learn the node has finished.
- Code must work in supervisor or user mode.
- The bltnode and everything it references must stay valid until cleanup has run.
- For small blits the queue overhead is higher than Own/DisownBlitter.
- Rewritten in V39 (FIFO order, fairer to OwnBlitter users); older versions had ordering bugs.

**See also:** [QBSBlit](#qbsblit), [OwnBlitter](#ownblitter), [WaitBlit](#waitblit)

## QBSBlit
`VOID QBSBlit(struct bltnode *blit)` — LVO -294 (-$126)
Registers: blit=A1; no result

Queue a blitter routine to run only when the video beam reaches a given position.

- **blit** — `struct bltnode` as for [QBlit](#qblit); `beamsync` holds the beam position to wait
  for.

Use it to blit into a visible area while the beam is elsewhere, avoiding half-old/half-new
frames. If the beam has already wrapped past pending positions, the remaining nodes are run as
fast as possible.

### Gotchas
- Same interrupt-context rules as [QBlit](#qblit) for `function` and `cleanup`.
- Before V39 beam-synced blits used a separate queue with priority over QBlit and had ordering
  bugs; from V39 both share one FIFO queue.

**See also:** [QBlit](#qblit), [VBeamPos](#vbeampos)

## WaitTOF
`VOID WaitTOF(VOID)` — LVO -270 (-$10E)
Registers: none; no result

Sleep until the next vertical blank has been processed (once-per-frame synchronisation).

The task is put on the TOF wait queue and signalled after the vertical blank interrupt servers
ran, i.e. about 50 times a second on PAL, 60 on NTSC.

### Example
```c
/* simple frame loop: move something once per frame */
void run_frames(struct ViewPort *vp, WORD frames)
{
    WORD i;
    for (i = 0; i < frames; i++) {
        WaitTOF();                          /* start of frame */
        vp->RasInfo->RxOffset = i & 0xFF;   /* e.g. scroll a hand-built ViewPort */
        ScrollVPort(vp);
    }
}
```

```asm
; wait two frames (e.g. after LoadView)
Wait2Frames:
        move.l  a6,-(sp)
        move.l  _GfxBase,a6
        jsr     _LVOWaitTOF(a6)
        jsr     _LVOWaitTOF(a6)
        move.l  (sp)+,a6
        rts
```

### Gotchas
- Task context only (it Waits for a signal); never from an interrupt. It relies on the vertical
  blank interrupt, so it never returns while `INTF_VERTB` is disabled.
- Not a precise beam position: a lower-priority or busy system wakes you late. For exact beam
  timing use a copper interrupt or a VERTB server.
- After `LoadView()` wait twice so both fields of an interlaced View have been replaced (the
  pattern used by startup code such as Bartman's amiga-debug template).

**See also:** [WaitBOVP](#waitbovp), [VBeamPos](#vbeampos), [LoadView](views-and-viewports.md#loadview)

## WaitBOVP
`VOID WaitBOVP(struct ViewPort *vp)` — LVO -402 (-$192)
Registers: vp=A0; no result

Busy-wait until the video beam is below the bottom of the given ViewPort.

- **vp** — the ViewPort.

### Gotchas
- It busy-waits (autodoc BUGS): the CPU is burned and other tasks of the same or lower priority
  starve until it returns. Prefer [WaitTOF](#waittof) unless you really need "below this
  ViewPort".
- Returns some time after the beam passes; on a loaded system the beam may be well past.

**See also:** [WaitTOF](#waittof), [VBeamPos](#vbeampos)

## VBeamPos
`LONG VBeamPos(VOID)` — LVO -384 (-$180)
Registers: none; result in D0

Return the current vertical beam position read from the hardware.

- **Result** — line number, 0-511.

### Gotchas
- With multitasking the value may be stale by the time you use it; it is only close (within a
  line) if you are the highest-priority ready task.

**See also:** [WaitBOVP](#waitbovp), [WaitTOF](#waittof)

## SetChipRev
`ULONG SetChipRev(ULONG want)` — LVO -888 (-$378)
Registers: want=D0; result in D0

Enable the features of a newer chip set if present and update the display database.

- **want** — one of `SETCHIPREV_A` (`GFXF_HR_AGNUS`), `SETCHIPREV_ECS`
  (`GFXF_HR_AGNUS|GFXF_HR_DENISE`), `SETCHIPREV_AA` (`GFXF_AA_ALICE|GFXF_AA_LISA|SETCHIPREV_ECS`),
  `SETCHIPREV_BEST` (`$FFFFFFFF`).
- **Result** — the bits now set in `GfxBase->ChipRevBits0`.

Since V39.

### Example
```asm
; bootblock/trackmo: enable AGA if present, then test for it
EnableAGA:
        move.l  a6,-(sp)
        move.l  _GfxBase,a6
        cmp.w   #39,LIB_VERSION(a6)
        blo.s   .noaga
        moveq   #-1,d0                  ; SETCHIPREV_BEST
        jsr     _LVOSetChipRev(a6)
        btst    #GFXB_AA_ALICE,gb_ChipRevBits0(a6)
        beq.s   .noaga
        moveq   #1,d0                   ; AGA present
        bra.s   .out
.noaga: moveq   #0,d0
.out:   move.l  (sp)+,a6
        rts
```

### Gotchas
- Normally done by the system during startup-sequence; call it only once, e.g. from bootblock
  code that runs before the startup-sequence would have.
- Check `lib_Version >= 39` first; the call does not exist on older ROMs.
- To merely detect AGA, test `GFXF_AA_ALICE` in `GfxBase->ChipRevBits0` (V39+) without
  calling SetChipRev. See [GfxBase fields](concepts.md#gfxbase-fields).

**See also:** [GfxBase fields](concepts.md#gfxbase-fields)

## ON_DISPLAY, OFF_DISPLAY

Macro (graphics/gfxmacros.h) — not a library call; expands to a custom.dmacon write.

`ON_DISPLAY` expands to `custom.dmacon = BITSET|DMAF_RASTER`, `OFF_DISPLAY` to
`custom.dmacon = BITCLR|DMAF_RASTER` (`BITSET` $8000 / `BITCLR` 0 from graphics/gfx.h).

### Gotchas
- They need an object `custom` of type `struct Custom` at $DFF000; hardware/custom.h only
  contains a comment suggesting `extern struct Custom custom;` (the symbol traditionally comes
  from amiga.lib). Bartman's amiga-debug template instead defines `struct Custom *custom` (a
  pointer), so these macros do not compile there: write `custom->dmacon = 0x8100` directly.
- Bypasses graphics.library: Intuition/graphics do not know the raster was switched off.

**See also:** [ON_SPRITE, OFF_SPRITE](#on_sprite-off_sprite), [LoadView](views-and-viewports.md#loadview)

## ON_SPRITE, OFF_SPRITE

Macro (graphics/gfxmacros.h) — not a library call; expands to a custom.dmacon write.

`ON_SPRITE` = `custom.dmacon = BITSET|DMAF_SPRITE`, `OFF_SPRITE` =
`custom.dmacon = BITCLR|DMAF_SPRITE`.

### Gotchas
- The LoadView autodoc points out that sprites (the mouse pointer) stay visible after
  `LoadView(NULL)` until sprite DMA is switched off like this.
- Same `custom` object requirement as [ON_DISPLAY](#on_display-off_display).

**See also:** [ON_DISPLAY, OFF_DISPLAY](#on_display-off_display), [LoadView](views-and-viewports.md#loadview)

## ON_VBLANK, OFF_VBLANK

Macro (graphics/gfxmacros.h) — not a library call; expands to a custom.intena write.

`ON_VBLANK` = `custom.intena = BITSET|INTF_VERTB`, `OFF_VBLANK` =
`custom.intena = BITCLR|INTF_VERTB`.

### Gotchas
- `INTF_VERTB` comes from hardware/intbits.h, which gfxmacros.h does not include: include it
  yourself.
- Turning off the vertical blank interrupt stops WaitTOF wake-ups, system timing and the
  mouse pointer update; restore it before calling the OS again.
- Same `custom` object requirement as [ON_DISPLAY](#on_display-off_display).

**See also:** [WaitTOF](#waittof)
