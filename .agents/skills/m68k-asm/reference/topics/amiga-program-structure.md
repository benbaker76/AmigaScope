# Amiga program structure: hunks, startup and exit

How an assembled program looks to AmigaDOS, what the registers hold when it starts from
the Shell (CLI) or from Workbench, and a minimal startup/exit that is correct for both.
Offsets below were computed by assembling the NDK includes with vasm (`printv`).

## The executable: one hunk per section

Every `section` becomes a hunk. The loader (`LoadSeg`) allocates each hunk separately, in
the memory type the hunk header asks for, copies the contents, clears BSS hunks and patches
all relocations. The program is then entered at the first byte of the first hunk
(standard behaviour; vlink and vscode-amiga-assembly put the startup object first).

```asm
        section code,code               ; hunk 0: any RAM, execution starts here
start:  ...
        section vars,bss                ; hunk 1: zeroed, only the size is in the file
DOSBase: ds.l   1
        section gfx,data_c              ; hunk 2: forced into chip RAM
copper: dc.w    $0180,$0000,$ffff,$fffe
```

Start of the [skeleton below](#minimal-correct-startup-and-exit) as written by
`vasm -Fhunkexe` (tested, 32-bit words; same three-hunk layout):

```text
000003F3 00000000 00000003 00000000 00000002   HUNK_HEADER, no libs, 3 hunks, first 0, last 2
0000002B 00000004 40000002                     sizes in longs: code 43, bss 4, data 2 + CHIP bit
000003E9 0000002B 48E73F3E ...                 HUNK_CODE, 172 bytes, relocations, HUNK_END
```

- Memory flags (NDK `dos/doshunks.i`): `HUNKB_CHIP` = bit 30, `HUNKB_FAST` = bit 31 of the size.
- Pointers between hunks (`dc.l copper`, `move.l #Hello,d1`, `lea copper,a0`) are fine:
  they get relocations. PC-relative references between hunks are not (see
  [SECTION](../directives/sections.md#section)).
- Everything the custom chips touch (copper lists, bitplanes, sprites, audio samples,
  blitter buffers) must be in a `_c` section or in memory from `AllocMem` with
  `MEMF_CHIP` (`MEMF_CHIP` = 2, bit 1, `exec/memory.i`). Do not ask for `_f`: chip-only
  machines cannot load it.
- Kickstart 1.x cannot zero BSS hunks above 256K (vasm error 3019) and does not
  understand short or PC-relative relocation hunks: build with `-kick1hunks` / vlink
  `-kick1` for 1.3 targets ([vasm and vlink](vasm-vlink.md)).

## Entry from the Shell (CLI)

| Register | Contents |
|---|---|
| A0 | pointer to the argument string (dos `GetArgStr` autodoc) |
| D0 | length of that string (`dos/dostags.h`, NP_Arguments comment) |
| SP | the process stack; `(sp)` is the return address |
| A6, others | undefined: load ExecBase from `$4` yourself |

- The argument text is what follows the command name, zero-terminated (`GetArgStr`
  autodoc) and normally ending in a linefeed (`RunCommand` requires one). Save A0/D0
  before the first library call trashes them.
- Exit: put the return code in D0 and `rts` with the SAME stack pointer you were entered
  with (dos `Exit` autodoc). Codes from `dos/dos.i`: `RETURN_OK` 0, `RETURN_WARN` 5,
  `RETURN_ERROR` 10, `RETURN_FAIL` 20.
- Preserving D2-D7/A2-A6 across the program is the usual convention and costs one MOVEM
  (not stated in the local sources).

## Entry from Workbench

Workbench starts the program as a new process with no CLI and sends it a `WBStartup`
message on the process's own message port. The program must:

1. Find its Process (`FindTask(0)`; NULL name = current task, exec autodoc).
2. Test `pr_CLI` (BPTR, offset 172): zero means Workbench.
3. `WaitPort(&pr_MsgPort)` then `GetMsg(&pr_MsgPort)` (port embedded at offset 92) and keep
   the message, before doing anything else.
4. At exit: `Forbid()`, `ReplyMsg(msg)`, return. Do not call `Permit()`: the Forbid lasts
   until the process is gone, so Workbench cannot unload the code while it still runs
   (reason: standard practice, unverified in the local sources).

`WBStartup` (NDK `workbench/startup.i`): `sm_Message` 0 (MN_SIZE 20), `sm_Process` 20,
`sm_Segment` 24, `sm_NumArgs` 28, `sm_ToolWindow` 32, `sm_ArgList` 36, `sm_SIZEOF` 40.
Each `WBArg` is `wa_Lock` 0 (BPTR), `wa_Name` 4, `wa_SIZEOF` 8; the first one describes
the program itself (unverified).

A0/D0 carry no arguments in this case; ignore them.

## Minimal correct startup and exit

Assembles with vasm 1.9: `vasmm68k_mot -m68000 -x -Fhunkexe -I<NDK>/sys-include -o hello hello.s`
(tested).

```asm
        include "exec/types.i"
        include "exec/memory.i"
        include "dos/dos.i"
        include "dos/dosextens.i"
        include "lvo/exec_lib.i"
        include "lvo/dos_lib.i"

        section code,code
start:
        movem.l d2-d7/a2-a6,-(sp)
        move.l  a0,ArgPtr               ; CLI arguments (meaningless from Workbench)
        move.l  d0,ArgLen
        move.l  4.w,a6                  ; ExecBase
        suba.l  a1,a1
        jsr     _LVOFindTask(a6)        ; d0 = our Process
        move.l  d0,a4
        tst.l   pr_CLI(a4)
        bne.s   .fromcli
        lea     pr_MsgPort(a4),a0       ; Workbench: fetch WBStartup first
        jsr     _LVOWaitPort(a6)
        lea     pr_MsgPort(a4),a0
        jsr     _LVOGetMsg(a6)
        move.l  d0,WBMsg
.fromcli:
        moveq   #RETURN_FAIL,d7
        lea     DosName(pc),a1
        moveq   #36,d0                  ; PutStr needs V36
        jsr     _LVOOpenLibrary(a6)
        move.l  d0,DOSBase
        beq.s   .nodos

        bsr     Main                    ; returns the exit code in d0
        move.l  d0,d7

        move.l  4.w,a6
        move.l  DOSBase,a1
        jsr     _LVOCloseLibrary(a6)
.nodos:
        tst.l   WBMsg
        beq.s   .exit
        jsr     _LVOForbid(a6)          ; no Permit: exit ends the Forbid
        move.l  WBMsg,a1
        jsr     _LVOReplyMsg(a6)
.exit:
        move.l  d7,d0
        movem.l (sp)+,d2-d7/a2-a6
        rts

Main:
        tst.l   WBMsg                   ; no console when started from Workbench
        bne.s   .done
        move.l  DOSBase,a6
        move.l  #Hello,d1
        jsr     _LVOPutStr(a6)
.done:  moveq   #RETURN_OK,d0
        rts

DosName: dc.b   "dos.library",0
Hello:  dc.b    "Hello",10,0
        even

        section vars,bss
DOSBase: ds.l   1
WBMsg:  ds.l    1
ArgPtr: ds.l    1
ArgLen: ds.l    1

        section gfx,data_c              ; chip-RAM data lives in its own hunk
Copper: dc.w    $0180,$0000,$ffff,$fffe
```

Notes on the skeleton:
- All variables live in the BSS hunk and are addressed absolutely: code cannot reach
  them with `(pc)` because they are in another hunk.
- The Workbench message is taken before anything that could fail, and replied on every
  exit path.
- `Main` receives nothing in registers; add your own argument parsing from `ArgPtr`/`ArgLen`.
- For a bare-metal demo, take over the display and interrupts inside `Main` and restore
  them before returning (see the amiga-hardware skill); the startup and exit stay the same.

## Chip-RAM data in the executable

```asm
        section gfx,data_c
copperlist:
        dc.w    $0100,$0200             ; BPLCON0: no bitplanes
        dc.w    $0180,$0005             ; COLOR00
        dc.w    $ffff,$fffe             ; end of copper list
logo:   incbin  "gfx/logo.raw"          ; raw planar data
logo_end:
        even
module: incbin  "music/tune.mod"
        even

        section chipbuf,bss_c
screen: ds.b    320/8*256*5             ; 5 lores bitplanes, zeroed
```

- `data_c` / `bss_c` (or `section name,data,chip`) are the only in-file ways to get chip
  RAM; the alternative is `AllocMem(size,MEMF_CHIP)` at run time.
- In Bartman's ELF flow the section memory argument is ignored; use an ELF section named
  `.MEMF_CHIP` (details in [vasm and vlink](vasm-vlink.md)).

## Common mistakes

- **Chip data in a plain `data` section**: works on a chip-only A500, shows garbage or
  silence on any machine with fast RAM.
- **Not replying the WBStartup message**, or replying it without `Forbid()` first.
- **Reading A0/D0 as arguments after a Workbench start**.
- **Returning with a different SP** (unbalanced MOVEM or pushes on an error path): the
  RTS jumps into garbage.
- **Random D0 at exit**: the Shell reports it as the return code; always load a
  `RETURN_...` value.
- **`lea var(pc),a0` for a BSS variable**: cross-hunk PC-relative, rejected when linking.
- **Opening a library and exiting through an error path that skips `CloseLibrary`.**

**See also:** [SECTION](../directives/sections.md#section), [DATA_C](../directives/sections.md#data_c),
[library calls](library-calls.md), [vasm and vlink](vasm-vlink.md)
