# dos.library: loading code

LoadSeg() reads an AmigaDOS load file (hunk format, `dos/doshunks.h`), allocates and relocates
each hunk and returns a **seglist**: a BPTR to the first segment. Each segment begins with a
BPTR to the next one (0 ends the chain) and the hunk contents follow that longword; the longword
before it holds the segment size (see the fake seglist under
[CreateProc](processes.md#createproc)). Execution starts at the first hunk, i.e. at
`BADDR(seglist) + 4`. Run a seglist with [RunCommand](processes.md#runcommand) or
[CreateNewProc](processes.md#createnewproc) (`NP_Seglist`), free it with UnLoadSeg(). The resident
list (AddSegment/FindSegment/RemSegment) shares loaded seglists by name, e.g. shell `Resident`.

```text
seglist BPTR x4 --> +-----------------------+
                    | BPTR next segment / 0 |  BADDR(seglist)
                    | hunk 0 code/data ...  |  BADDR(seglist)+4 = entry point
                    +-----------------------+
```

## LoadSeg
`BPTR LoadSeg(CONST_STRPTR name)` — LVO -150 (-$96)
Registers: name=D1; result in D0

Load and relocate an executable (hunk) file into memory and return its seglist.

- **name** — path of the load file.
- **Result** — BPTR seglist, or 0 on failure (IoErr() has the reason; anything partly loaded is
  freed). The seglist is also returned in D1 (kept for old overlay code).

Hunks are loaded into the memory type their header asks for (`HUNKF_CHIP` bit 30, `HUNKF_FAST`
bit 31 on the hunk size), so chip-RAM sections of an executable land in chip RAM. Unused parts of
code/data hunks and BSS hunks are cleared.

### Example
```asm
        include "lvo/dos_lib.i"

        move.l  DOSBase,a6
        move.l  #cmdname,d1
        jsr     _LVOLoadSeg(a6)
        move.l  d0,d7                   ; seglist BPTR (d2-d7 survive calls)
        beq.s   .fail                   ; IoErr() has the reason
        move.l  d7,d1                   ; seg
        move.l  #8192,d2                ; stack for the command, bytes
        move.l  #args,d3
        moveq   #argsend-args,d4        ; length incl. newline, excl. NUL
        jsr     _LVORunCommand(a6)
        move.l  d0,d6                   ; command's return code
        move.l  d7,d1
        jsr     _LVOUnLoadSeg(a6)
        ...
cmdname dc.b    "C:List",0
args    dc.b    "RAM:",10
argsend dc.b    0
        even
```
```c
/* Your own plugin whose first hunk starts with the entry function */
BPTR seg = LoadSeg("PROGDIR:fx.plugin");
if (seg) {
    LONG (*entry)(void) = (LONG (*)(void))((ULONG)BADDR(seg) + 4);
    LONG r = entry();
    UnLoadSeg(seg);
}
```

### Gotchas
- The result is a BPTR, not an address: BADDR() it before touching memory.
- Loading does not start anything and sets up no CLI context: calling a normal C program's entry
  directly skips what RunCommand/CreateNewProc provide.
- Never free hunks yourself; UnLoadSeg() the whole list (unless DOS owns it, see UnLoadSeg).
- Hunks with `HUNKF_ADVISORY` (bit 29) are only skipped by V39+ dos; older dos fails with a bad
  hunk. Load files using `HUNK_RELOC32SHORT` must use hunk id 1015 to load on V37 (doshunks.h).

**See also:** [UnLoadSeg](#unloadseg), [NewLoadSeg](#newloadseg), [InternalLoadSeg](#internalloadseg),
[RunCommand](processes.md#runcommand), [CreateNewProc](processes.md#createnewproc),
[CreateProc](processes.md#createproc)

## UnLoadSeg
`VOID UnLoadSeg(BPTR seglist)` — LVO -156 (-$9C)
Registers: seglist=D1; no result

Free a seglist loaded by LoadSeg(), closing overlay files if needed.

- **seglist** — seglist BPTR; 0 is allowed.
- **Result** — none per the NDK prototype. The autodoc documents D0 = 0 for a 0 seglist or a
  failed overlay close (random before V36); do not depend on it.

### Gotchas
- Never unload code that is still running or referenced (a child process, an interrupt server,
  a hook, a patched vector).
- Do not UnLoadSeg a seglist given to CreateNewProc with `NP_FreeSeglist` TRUE (the default), or
  one added to the resident list (RemSegment unloads it).
- Seglists from InternalLoadSeg() with your own allocator go to InternalUnLoadSeg().

**See also:** [LoadSeg](#loadseg), [InternalUnLoadSeg](#internalunloadseg), [RemSegment](#remsegment)

## NewLoadSeg
`BPTR NewLoadSeg(CONST_STRPTR file, CONST struct TagItem *tags)` — LVO -768 (-$300)
Registers: file=D1, tags=D2; result in D0

LoadSeg() with a tag list for extra options (no tags are defined).

- **file** — path of the load file.
- **tags** — TagItem array; pass NULL (dostags.h defines no NewLoadSeg tags).
- **Result** — seglist BPTR or 0. Unlike LoadSeg, NOT duplicated in D1.

`NewLoadSegTagList` is the same LVO; `NewLoadSegTags(file, ..., TAG_END)` is the varargs form.

Since V36.

**See also:** [LoadSeg](#loadseg), [UnLoadSeg](#unloadseg), [InternalLoadSeg](#internalloadseg)

## InternalLoadSeg
`BPTR InternalLoadSeg(BPTR fh, BPTR table, CONST LONG *funcarray, LONG *stack)` — LVO -756 (-$2F4)
Registers: fh=D0, table=A0, funcarray=A1, stack=A2; result in D0

Load a hunk file from an open handle using caller-supplied read, alloc and free functions.

- **fh** — open file handle (in D0!). It is not closed; its seek position afterwards is anywhere
  past the last hunk.
- **table** — overlay table when loading an overlay; otherwise 0.
- **funcarray** — pointer to three function pointers, each called with these registers:

| Index | Function | Inputs | Output |
|---|---|---|---|
| 0 | ReadFunc | D1 = handle, D2 = buffer, D3 = length, A6 = DOSBase | D0 = bytes read |
| 1 | AllocFunc | D0 = size, D1 = flags, A6 = ExecBase | D0 = memory |
| 2 | FreeFunc | A1 = memory, D0 = size, A6 = ExecBase | -- |

  These match Read(), exec AllocMem() and exec FreeMem() exactly.
- **stack** — pointer to a LONG preset to your default stack size; overwritten only if the file
  encodes a stack size.
- **Result** — seglist BPTR; `-(seglist)` (negative) for an overlaid file; 0 on failure. Not
  returned in D1.

Unused parts of code/data hunks and BSS hunks are cleared.

Since V36.

### Example
```asm
        include "lvo/exec_lib.i"
        include "lvo/dos_lib.i"

        move.l  DOSBase,a6
        move.l  filehandle,d0           ; BPTR from Open(), in D0
        sub.l   a0,a0                   ; no overlay table
        lea     functab(pc),a1
        lea     stacksize,a2            ; preset default, may be overwritten
        jsr     _LVOInternalLoadSeg(a6)
        move.l  d0,d7
        ble.s   .fail                   ; 0 = error, <0 = overlay (not handled)
        ...
        move.l  d7,d1                   ; later: free with the matching FreeFunc
        lea     fr_mem(pc),a1
        jsr     _LVOInternalUnLoadSeg(a6)
        ...
functab dc.l    rd_file,al_mem,fr_mem
rd_file jmp     _LVORead(a6)            ; A6 = DOSBase when called
al_mem  jmp     _LVOAllocMem(a6)        ; A6 = ExecBase when called
fr_mem  jmp     _LVOFreeMem(a6)         ; A6 = ExecBase when called

        section data,data
stacksize dc.l  4096
```

### Gotchas
- Unusual registers: fh=D0, table=A0, funcarray=A1, stack=A2.
- Replace ReadFunc to load from memory or a packed stream; the handle passed in D1 is presumably
  the `fh` value you gave (unverified).
- Free with InternalUnLoadSeg() and a FreeFunc matching your AllocFunc.

**See also:** [InternalUnLoadSeg](#internalunloadseg), [LoadSeg](#loadseg), [NewLoadSeg](#newloadseg),
[Read](files.md#read), exec.library AllocMem, FreeMem

## InternalUnLoadSeg
`BOOL InternalUnLoadSeg(BPTR seglist, VOID (*CONST freefunc)())` — LVO -762 (-$2FA)
Registers: seglist=D1, freefunc=A1; result in D0

Free a seglist from InternalLoadSeg() using a caller-supplied free function.

- **seglist** — seglist to free (D1).
- **freefunc** — free routine (A1), called like InternalLoadSeg's FreeFunc: A1 = memory,
  D0 = size, A6 = ExecBase.
- **Result** — TRUE if all went well; FALSE for a 0 seglist or if closing an overlay file failed.

Closes the file of an overlaid seglist.

Since V36.

**See also:** [InternalLoadSeg](#internalloadseg), [UnLoadSeg](#unloadseg), [Close](files.md#close)

## AddSegment
`LONG AddSegment(CONST_STRPTR name, BPTR seg, LONG system)` — LVO -774 (-$306)
Registers: name=D1, seg=D2, system=D3; result in D0

Add a seglist to the DOS resident list under a name.

- **name** — name to register (what FindSegment and the shell look up).
- **seg** — seglist BPTR.
- **system** — initial use count `seg_UC`, normally 0. Negative values are the system's (see
  [FindSegment](#findsegment)).
- **Result** — non-zero on success.

Since V36.

### Gotchas
- Never build `struct Segment` yourself.
- Once added, the list owns the seglist: remove it with RemSegment() (which unloads it), not
  UnLoadSeg().
- Several processes may run the same resident code at once, so it must be re-entrant (pure).
- Unused type values may make future dos read D4 and up as extra arguments: pass 0.

**See also:** [FindSegment](#findsegment), [RemSegment](#remsegment), [LoadSeg](#loadseg)

## FindSegment
`struct Segment * FindSegment(CONST_STRPTR name, CONST struct Segment *seg, LONG system)` — LVO -780 (-$30C)
Registers: name=D1, seg=D2, system=D3; result in D0

Search the DOS resident list for a named segment; call it under Forbid().

- **name** — segment name.
- **seg** — search starts AFTER this segment; NULL = from the start of the list.
- **system** — 0: only normal segments (`seg_UC` >= 0); non-zero: search system segments
  (negative `seg_UC`).
- **Result** — `struct Segment *` or NULL.

`struct Segment` (dosextens.h): `seg_Next` (BPTR), `seg_UC` (LONG use count), `seg_Seg` (BPTR
seglist), `seg_Name[4]` (start of the BSTR name). Special `seg_UC` values:

| Name | Value | Meaning |
|---|---|---|
| `CMD_SYSTEM` | -1 | system module, e.g. a filesystem or the shell |
| `CMD_INTERNAL` | -2 | resident shell (internal) command |
| `CMD_DISABLED` | -999 | disabled internal command, ignore |

Since V36.

### Example
```c
struct Segment *s;
BPTR seglist = 0;
LONG rc = -1;

Forbid();
s = FindSegment("MyTool", NULL, FALSE);
if (s && s->seg_UC >= 0) {
    s->seg_UC++;                    /* pin it: RemSegment now fails */
    seglist = s->seg_Seg;
}
Permit();

if (seglist) {
    rc = RunCommand(seglist, 8192, "\n", 1);
    Forbid();
    s->seg_UC--;                    /* always under Forbid */
    Permit();
}
```

### Gotchas
- Does no locking and does not touch `seg_UC`: Forbid() around the search, bump `seg_UC` before
  Permit(), decrement under Forbid() when done.
- Never modify a negative `seg_UC`; all values from -1 to -32767 are reserved to DOS.

**See also:** [AddSegment](#addsegment), [RemSegment](#remsegment), [RunCommand](processes.md#runcommand),
exec.library Forbid

## RemSegment
`LONG RemSegment(struct Segment *seg)` — LVO -786 (-$312)
Registers: seg=D1; result in D0

Remove a resident segment from the DOS resident list and unload it.

- **seg** — segment from FindSegment().
- **Result** — non-zero on success; fails unless `seg_UC` is 0.

Since V36.

### Gotchas
- Find and remove inside one Forbid()/Permit() pair so nobody starts using it in between.
- On success the Segment and its seglist are gone: do not touch either afterwards.

**See also:** [FindSegment](#findsegment), [AddSegment](#addsegment)
