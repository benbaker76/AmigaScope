# exec.library: interrupts

Exec owns the 680x0 autovectors and dispatches Paula (INTENA/INTREQ) sources. Each source
is either a **server chain** -- shared, many `struct Interrupt` nodes called in `ln_Pri`
order, managed with AddIntServer/RemIntServer -- or a single **handler** slot replaced
with SetIntVector. Cause queues software interrupts; ObtainQuickVector hands out a raw
Zorro-III vector. INTENA/INTREQ register details: the amiga-hardware skill.

| Bit | Name (hardware/intbits.i) | CPU level | Exec dispatch |
|---|---|---|---|
| 0 | `INTB_TBE` | 1 | handler (serial.device) |
| 1 | `INTB_DSKBLK` | 1 | handler (disk) |
| 2 | `INTB_SOFTINT` | 1 | exec's software interrupts -- use [Cause](#cause) |
| 3 | `INTB_PORTS` | 2 | server chain (INT2, CIA-A) |
| 4 | `INTB_COPER` | 3 | server chain |
| 5 | `INTB_VERTB` | 3 | server chain |
| 6 | `INTB_BLIT` | 3 | handler |
| 7-10 | `INTB_AUD0`..`INTB_AUD3` | 4 | handlers (audio.device) |
| 11 | `INTB_RBF` | 5 | handler (serial.device) |
| 12 | `INTB_DSKSYNC` | 5 | handler (disk) |
| 13 | `INTB_EXTER` | 6 | server chain (INT6, CIA-B) |
| 15 | `INTB_NMI` (exec/interrupts.i) | 7 | server chain |

Bit 14 is `INTB_INTEN`, the master enable, not a source. `struct Interrupt` = `is_Node`
(`ln_Type` = `NT_INTERRUPT`, `ln_Pri`, `ln_Name` pointing at a descriptive name),
`is_Data` (IS_DATA $0E) and `is_Code` (IS_CODE $12); size `IS_SIZE` $16. Keep the
structure and code in memory that is never freed or swapped while installed.

**Server calling convention:** D0, D1, A0, A5, A6 scratch; A1 = `is_Data`; every other
register must be preserved; return with RTS. The Z flag on return decides the chain: Z
set (e.g. `moveq #0,d0`) passes the interrupt on, Z clear ends the chain. **VERTB
servers must always return Z set.** Write servers in assembler (Bartman builds assemble
`*.asm` files with vasm): compiled C cannot promise the Z flag or the register rules.

## AddIntServer
`VOID AddIntServer(LONG intNumber, struct Interrupt *interrupt)` — LVO -168 (-$A8)
Registers: intNumber=D0, interrupt=A1; no result

Add an Interrupt node to a shared server chain, ordered by `ln_Pri`.

- **intNumber** — chain bit: `INTB_PORTS` (3), `INTB_COPER` (4), `INTB_VERTB` (5),
  `INTB_EXTER` (13) or `INTB_NMI` (15). Only the low 4 bits of D0 are used.
- **interrupt** — initialised `struct Interrupt`: `NT_INTERRUPT`, priority, name,
  `is_Data`, `is_Code`.

The first server added to a chain enables that interrupt in INTENA.

### Example
```asm
        include "exec/types.i"
        include "exec/nodes.i"
        include "exec/interrupts.i"
        include "hardware/intbits.i"
        include "lvo/exec_lib.i"

InstallVBL:
        move.l  4.w,a6
        moveq   #INTB_VERTB,d0
        lea     VBLInt(pc),a1
        jsr     _LVOAddIntServer(a6)
        rts

RemoveVBL:
        move.l  4.w,a6
        moveq   #INTB_VERTB,d0
        lea     VBLInt(pc),a1
        jsr     _LVORemIntServer(a6)
        rts

; called once per frame: a1 = is_Data
VBLServer:
        addq.l  #1,(a1)                 ; frame counter
        moveq   #0,d0                   ; Z set: let the other VERTB servers run
        rts

VBLInt:
        dc.l    0,0                     ; LN_SUCC, LN_PRED
        dc.b    NT_INTERRUPT,0          ; LN_TYPE, LN_PRI (keep below 10, see Gotchas)
        dc.l    VBLName                 ; LN_NAME
        dc.l    FrameCount              ; IS_DATA
        dc.l    VBLServer               ; IS_CODE

FrameCount:
        dc.l    0
VBLName:
        dc.b    "mygame vblank",0
        even
```

### Gotchas
- Return Z with care: `movem.l (sp)+,...` leaves the flags alone but a single-register
  `move.l (sp)+,d2` or similar sets them. Load D0 (`moveq #0,d0`) as the very last flag-
  changing instruction.
- VERTB: graphics.library's own VBlank server and some other code expect A0 = $DFF000 on
  the chain. A server at priority 10 or higher must leave A0 = $DFF000
  (`lea $dff000,a0` before `moveq #0,d0`).
- Servers run in interrupt context: no Wait, no memory allocation, no DOS; hand work
  to a task with [Signal](signals-and-messages.md#signal) or defer it with [Cause](#cause).
- Server code must not clear INTREQ for the chain itself; exec does it (unverified).
- Use [SetIntVector](#setintvector) for non-chain sources; AddIntServer only for the five
  chains above.

**See also:** [RemIntServer](#remintserver), [SetIntVector](#setintvector), [Cause](#cause)

## RemIntServer
`VOID RemIntServer(LONG intNumber, struct Interrupt *interrupt)` — LVO -174 (-$AE)
Registers: intNumber=D0, interrupt=A1; no result

Unlink an Interrupt node from a server chain.

- **intNumber** — the same chain bit used with AddIntServer.
- **interrupt** — the same `struct Interrupt` that was added.

Removing the last server of a chain disables that interrupt in INTENA (V36+; older ROMs
leave it enabled).

### Gotchas
- Always remove your servers before exit and before freeing their code or data.
- Pass the same chain number the node was added to.

**See also:** [AddIntServer](#addintserver)

## SetIntVector
`struct Interrupt * SetIntVector(LONG intNumber, CONST struct Interrupt *interrupt)` — LVO -162 (-$A2)
Registers: intNumber=D0, interrupt=A1; result in D0

Install the single handler for a non-chained Paula interrupt, returning the previous one.

- **intNumber** — source bit: `INTB_TBE`, `INTB_DSKBLK`, `INTB_BLIT`, `INTB_AUD0`..
  `INTB_AUD3`, `INTB_RBF`, `INTB_DSKSYNC`. Never a chain bit.
- **interrupt** — the new handler's `struct Interrupt`, or NULL to remove the current
  handler. Exec copies `is_Code`/`is_Data` privately at install time.
- **Result** — the previously installed `struct Interrupt *`; put it back when done.

Handler entry registers: D1 = INTENAR & INTREQR (the active sources), A0 = $DFF000,
A1 = `is_Data`, A5 = jump vector, A6 = SysBase. D0/D1/A0/A1/A5/A6 are scratch, all
others must be preserved; return with RTS. Unlike servers, the handler must acknowledge
(clear) its own INTREQ bit and manage its INTENA bit.

### Example
```asm
        include "exec/types.i"
        include "exec/nodes.i"
        include "exec/interrupts.i"
        include "hardware/intbits.i"
        include "hardware/custom.i"
        include "lvo/exec_lib.i"

InstallAud0:
        move.l  4.w,a6
        moveq   #INTB_AUD0,d0
        lea     Aud0Int(pc),a1
        jsr     _LVOSetIntVector(a6)
        move.l  d0,OldAud0              ; previous owner, restore on exit
        move.w  #INTF_SETCLR!INTF_AUD0,$dff000+intena
        rts

RestoreAud0:
        move.w  #INTF_AUD0,$dff000+intena       ; source off first
        move.l  4.w,a6
        moveq   #INTB_AUD0,d0
        move.l  OldAud0,a1
        jsr     _LVOSetIntVector(a6)
        rts

Aud0Code:                               ; a0 = $dff000, a1 = is_Data
        move.w  #INTF_AUD0,intreq(a0)   ; acknowledge
        addq.l  #1,(a1)                 ; count "block done"
        rts

Aud0Int:
        dc.l    0,0
        dc.b    NT_INTERRUPT,0
        dc.l    Aud0Name
        dc.l    Aud0Count
        dc.l    Aud0Code

OldAud0:        dc.l    0
Aud0Count:      dc.l    0
Aud0Name:       dc.b    "mygame aud0",0
        even
```

### Gotchas
- These vectors belong to system code (serial.device, audio.device, disk code) while it
  is active: take one only when that code is not using it, and restore the old
  Interrupt on exit.
- The previous code may have left the source enabled or with a pending request: disable
  and clear it before installing, enable after.
- Do not SetIntVector `INTB_SOFTINT` (exec's Cause mechanism) or the chain bits.
- Changing `is_Code`/`is_Data` after installation has no effect (they were copied).

**See also:** [AddIntServer](#addintserver), [Cause](#cause)

## Cause
`VOID Cause(struct Interrupt *interrupt)` — LVO -180 (-$B4)
Registers: interrupt=A1; no result

Queue a software interrupt; it runs as soon as no higher interrupt is being processed.

- **interrupt** — initialised `struct Interrupt`: `ln_Type` `NT_INTERRUPT` (or
  `NT_UNKNOWN`), `ln_Pri` one of -32, -16, 0, +16, +32, `is_Code`, `is_Data`.

If called from a task it pre-empts the task immediately. Typical use: a hardware
interrupt server Causes a soft interrupt to do the longer part of its work at a lower
level. Also used by message ports with `PA_SOFTINT`.

### Example
```asm
        include "exec/types.i"
        include "exec/nodes.i"
        include "exec/interrupts.i"
        include "lvo/exec_lib.i"

; inside a VERTB server: defer the heavy work
VBLServer:
        move.l  4.w,a6                  ; A6 is scratch in servers
        lea     WorkInt(pc),a1
        jsr     _LVOCause(a6)
        moveq   #0,d0                   ; Z set for the VERTB chain
        rts

WorkCode:                               ; soft interrupt: a1 = is_Data (unverified)
        ; ... music player, game logic ... (preserve A6!)
        rts

WorkInt:
        dc.l    0,0
        dc.b    NT_INTERRUPT,0          ; priority 0
        dc.l    WorkName
        dc.l    0                       ; IS_DATA
        dc.l    WorkCode                ; IS_CODE

WorkName:
        dc.b    "mygame work",0
        even
```

### Gotchas
- A soft interrupt is still interrupt code: same restrictions as servers (no Wait, no
  allocation, no DOS).
- Unlike other interrupt code, soft interrupt code must preserve A6.
- Priorities between the five legal values are truncated; outside -32..+32 is illegal.
- Causing an already pending soft interrupt does nothing (it runs once, no count). The
  node is `NT_SOFTINT` while pending and back to `NT_INTERRUPT` afterwards -- do not
  change or free it while pending.
- The autodoc spells the type NT_UNKOWN; the constant is `NT_UNKNOWN`.

**See also:** [AddIntServer](#addintserver), [PutMsg](signals-and-messages.md#putmsg)

## ObtainQuickVector
`ULONG ObtainQuickVector(APTR interruptCode)` — LVO -786 (-$312)
Registers: interruptCode=A0; result in D0

Allocate a Zorro-III quick interrupt vector and point it straight at your code.

- **interruptCode** — raw interrupt code, entered directly from the CPU vector.
- **Result** — the 8-bit vector number your board must supply, or 0 if none is free
  (fall back to a shared server chain, e.g. `INTB_EXTER`/`INTB_PORTS`).

Since V39.

### Gotchas
- Not an exec interrupt: no registers are set up or saved. Save and restore everything
  you touch (D0/D1/A0/A1 included) and end with RTE.
- Right after a Disable one last interrupt can still slip in. If the code touches system
  structures, check `INTB_INTEN` in INTENAR first and exit at once when it is clear.
- Not safe to call on V37 exec despite the LVO existing there; require V39.
- Only meaningful for Zorro-III expansion hardware; irrelevant for OCS/AGA chipset code.

**See also:** [AddIntServer](#addintserver)
