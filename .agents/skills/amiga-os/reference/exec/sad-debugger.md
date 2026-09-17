# exec.library: SAD remote debugger protocol

SAD ("Simple Amiga Debugging kernel") is a tiny debugger in the V39+ Kickstart ROM that a
remote host drives over the built-in serial port. Everything on this page is a SERIAL BYTE
PROTOCOL spoken by an external machine -- none of it is an exec.library function, and there
are no LVOs. On the Amiga side SAD is entered through [Debug](system.md#debug) (or an NMI /
crash hook); the host then reads and writes memory, reads the saved register frame and calls
code. Pre-V39 ROMs have ROM-WACK instead.

## Protocol overview

Framing, prompts, timeouts and version quirks shared by all SAD commands.

```text
Host -> Amiga   $AF <cmd> [data bytes]         all multi-byte values big-endian
Amiga -> Host   $00 <cmd>                       ACK (command received)
Amiga -> Host   $1F <cmd> [result bytes]        DONE (command finished)

Prompt / heartbeat (Amiga -> Host, "SAD" + state byte):
  $53 $41 $44 $BF   entered via NMI hook: full Disable + Forbid
  $53 $41 $44 $3F   entered via Debug(): Forbid only (running "as a task")
  $53 $41 $44 $21   dead-end crash
```

- Serial: SAD sets 9600 baud every time it is entered. The host may speed things up by
  writing SERPER with WRITE_WORD; that rate lasts until SAD is left or SERPER changes again.
- Heartbeat: with no command, the prompt is re-sent about every 2 seconds. After 10
  unanswered heartbeats SAD returns to the system (RTS or RTE) so the machine cannot hang;
  send NOP to keep it waiting.
- Every byte of a command must follow the previous one within 2 seconds or SAD drops back to
  the prompt.
- After any write, SAD calls CacheClearU before sending DONE.
- `$BF` state (NMI): system lists may be half-updated (an NMI can land inside AllocMem or a
  task switch); follow pointers defensively. `$3F` state (Debug()): only Forbid is in effect,
  the system is between operations, and the host may Disable itself if needed.
- The host is responsible for legal access: WORD/LONG addresses must be even on a 68000, and
  touching unmapped memory can bus-error.
- V39 bug: WRITE_BYTE was not wired in, so command numbers are off by one in V39 SAD
  (READ_WORD, $05 in V40, is $04 there; presumably every command above WRITE_BYTE shifts the
  same way) while the ACK still names the command actually run.
  V39 READ_WORD also returns wrong data. Probe first:

```text
Send  $AF $05 $00 $F8 $00 $00      READ_WORD at $F80000 (start of ROM)
Recv  $00 $05 ...                   V40 SAD: a READ_WORD, 2 data bytes follow the DONE header
Recv  $00 $06 ...                   V39 SAD: ran READ_LONG, 4 data bytes follow
```

## NOP

Keep SAD waiting without doing anything.

```text
Send  $AF $00
(no ACK, no DONE -- only restarts the timeout)
```

## WRITE_BYTE

Write one byte to memory (V40 SAD only).

```text
Send  $AF $01 aa aa aa aa bb         aa = address, bb = byte
ACK   $00 $01
DONE  $1F $01
```

- Missing in V39 SAD (see overview): emulate with WRITE_ARRAY and a length of 1.

## WRITE_WORD

Write a 16-bit value to memory.

```text
Send  $AF $02 aa aa aa aa ww ww      aa = address, ww = word
ACK   $00 $02
DONE  $1F $02
```

- Address must be even on a 68000. Writing SERPER ($DFF032) changes SAD's baud rate.

## WRITE_LONG

Write a 32-bit value to memory.

```text
Send  $AF $03 aa aa aa aa ll ll ll ll
ACK   $00 $03
DONE  $1F $03
```

## READ_BYTE

Read one byte from memory.

```text
Send  $AF $04 aa aa aa aa
ACK   $00 $04
DONE  $1F $04 bb
```

## READ_WORD

Read a 16-bit value from memory (correct only in V40 SAD).

```text
Send  $AF $05 aa aa aa aa
ACK   $00 $05
DONE  $1F $05 ww ww
```

- Pre-V40 exec returns wrong values; use this command as the V39/V40 probe (overview).

## READ_LONG

Read a 32-bit value from memory.

```text
Send  $AF $06 aa aa aa aa
ACK   $00 $06
DONE  $1F $06 ll ll ll ll
```

## CALL_ADDRESS

JSR to code on the Amiga, with the saved context frame still in place.

```text
Send  $AF $07 aa aa aa aa            aa = routine address
ACK   $00 $07                         sent as soon as the command is received
DONE  $1F $07                         after the routine returns
```

- Registers are not loaded from the frame; normal rules apply: the routine may use
  D0/D1/A0/A1 and must preserve the rest, ending in RTS.
- Combine with WRITE_ARRAY to upload helper code, then call it.

## RETURN_TO_SYSTEM

Leave SAD and resume whatever entered it.

```text
Send  $AF $08 $00 $00 $00 $00        four zero bytes are a mandatory safety check
ACK   $00 $08                         no DONE: SAD has given up control
```

- Registers are restored from the context frame (see GET_CONTEXT_FRAME), so edits made there
  take effect on return.

## GET_CONTEXT_FRAME

Return the address of the saved register frame.

```text
Send  $AF $09
ACK   $00 $09
DONE  $1F $09 ff ff ff ff            ff = address of the SAD_FRAME structure
```

| Offset | Field | Size | Meaning |
|---|---|---|---|
| $00 | SAD_VBR | ULONG | vector base register (0 on a 68000), read-only |
| $04 | SAD_AttnFlags | ULONG | copy of ExecBase AttnFlags (upper word 0), read-only |
| $08 | SAD_ExecBase | ULONG | ExecBase, read-only |
| $0C | SAD_USP | ULONG | user stack pointer (valid only if SR was not supervisor) |
| $10-$2C | SAD_D0 .. SAD_D7 | ULONG each | data registers |
| $30-$48 | SAD_A0 .. SAD_A6 | ULONG each | address registers |
| $4C | SAD_PROMPT | ULONG | SAD's current prompt, internal (writing has no effect) |
| $50 | SAD_SR | UWORD | status register, start of the exception frame |
| $52 | SAD_PC | ULONG | return address |

- Offsets computed from the documented field order ($56 bytes to the end of SAD_PC); the
  rest of the CPU exception frame follows and differs between 680x0 models.
- Write the register fields with WRITE_LONG/WRITE_WORD to change what the interrupted code
  sees after RETURN_TO_SYSTEM.

## ALLOCATE_MEMORY

Allocate memory on the Amiga via AllocVec.

```text
Send  $AF $0A ss ss ss ss tt tt tt tt   ss = size in bytes, tt = MEMF_ attributes
ACK   $00 $0A
DONE  $1F $0A aa aa aa aa               aa = address, 0 if the allocation failed
```

- Only safe in `$3F` (Debug()) state, and even then only if the system is healthy.
- The block stays allocated until FREE_MEMORY.

## FREE_MEMORY

Free a block obtained with ALLOCATE_MEMORY (FreeVec on the Amiga).

```text
Send  $AF $0B aa aa aa aa
ACK   $00 $0B
DONE  $1F $0B
```

- Same restrictions as ALLOCATE_MEMORY.

## TURN_ON_SINGLE

Switch on trace-mode single stepping.

```text
Send  $AF $0C
ACK   $00 $0C
DONE  $1F $0C vv vv vv vv            vv = previous TRACE exception vector: keep it
```

- SAD takes over the TRACE vector while stepping. Enabling it from the `$BF` state executes
  the step and SAD then continues in `$3F` (non-NMI) mode.

## TURN_OFF_SINGLE

Switch single stepping off again.

```text
Send  $AF $0D vv vv vv vv            vv = value returned by TURN_ON_SINGLE
ACK   $00 $0D
DONE  $1F $0D
```

## WRITE_ARRAY

Write a block of bytes to memory.

```text
Send  $AF $0E aa aa aa aa nn nn nn nn   aa = address, nn = byte count
ACK   $00 $0E
Send  <nn data bytes>                   only after the ACK
DONE  $1F $0E
```

## READ_ARRAY

Read a block of bytes from memory.

```text
Send  $AF $0F aa aa aa aa nn nn nn nn   aa = address, nn = byte count
ACK   $00 $0F
DONE  $1F $0F <nn data bytes>
```

## RESET

Reset the Amiga.

```text
Send  $AF $10 $FF $FF $FF $FF        four $FF bytes guard against accidental resets
ACK   $00 $10                         no DONE: the machine resets
```
