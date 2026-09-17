# dos.library: DOS objects

`AllocDosObject()` allocates and initialises the DOS structures that have hidden size or
alignment requirements; `FreeDosObject()` releases them with the SAME type. Use it whenever
an autodoc says a structure "MUST be allocated by AllocDosObject" (ExAllControl), must be
longword aligned (FileInfoBlock), or is handed back to DOS (RDArgs, packets, CLI).

| Type (`dos/dos.h`) | Value | Returns | Typical use |
|---|---|---|---|
| `DOS_FILEHANDLE` | 0 | `struct FileHandle *` | handler writers only ("few people should use this") |
| `DOS_EXALLCONTROL` | 1 | `struct ExAllControl *` | required for [ExAll](locks-and-directories.md#exall) |
| `DOS_FIB` | 2 | `struct FileInfoBlock *` | [Examine](locks-and-directories.md#examine)/[ExNext](locks-and-directories.md#exnext)/[ExamineFH](files.md#examinefh) |
| `DOS_STDPKT` | 3 | `struct DosPacket *` (the `sp_Pkt` inside a StandardPacket) | [SendPkt](packets.md#sendpkt) |
| `DOS_CLI` | 4 | `struct CommandLineInterface *` | shell writers |
| `DOS_RDARGS` | 5 | `struct RDArgs *` | caller-supplied [ReadArgs](arguments.md#readargs) control |

Tags (`dos/dostags.h`, base `ADO_Dummy` = `TAG_USER + 2000`): `ADO_FH_Mode` (DOS_FILEHANDLE:
set the buffering up for this Open mode), and for DOS_CLI the buffer sizes `ADO_DirLen`,
`ADO_CommNameLen`, `ADO_CommFileLen`, `ADO_PromptLen` (also accepted by CreateNewProc).
Unspecified DOS_CLI fields are 0 except `cli_FailLevel` (10) and `cli_Background` (DOSTRUE).

## AllocDosObject
`APTR AllocDosObject(ULONG type, CONST struct TagItem *tags)` — LVO -228 (-$E4)
Registers: type=D1, tags=D2; result in D0

Allocate and initialise a DOS structure of the given type.

- **type** — `DOS_FILEHANDLE`, `DOS_EXALLCONTROL`, `DOS_FIB`, `DOS_STDPKT`, `DOS_CLI` or
  `DOS_RDARGS` (table above).
- **tags** — `TagItem` array (`ADO_*`), or NULL.
- **Result** — pointer to the object, or NULL on failure. For `DOS_STDPKT` it points at the
  DosPacket, not at the StandardPacket's Message.

Also callable as `AllocDosObjectTagList()` (same LVO) and, with varargs,
`AllocDosObjectTags(type, tag, ..., TAG_DONE)`.

Since V36.

### Example
```c
struct FileInfoBlock *fib = AllocDosObject(DOS_FIB, NULL);
if (fib) {
    BPTR lock = Lock("SYS:", ACCESS_READ);
    if (lock) {
        if (Examine(lock, fib))
            Printf("%s\n", (LONG)fib->fib_FileName);
        UnLock(lock);
    }
    FreeDosObject(DOS_FIB, fib);
}
```

```asm
        move.l  DOSBase,a6
        moveq   #DOS_FIB,d1
        moveq   #0,d2                   ; no tags
        jsr     _LVOAllocDosObject(a6)
        move.l  d0,d5                   ; d5 = FileInfoBlock (longword aligned)
        beq     .nomem
        ; ... Examine/ExNext with d2 = d5 ...
        moveq   #DOS_FIB,d1
        move.l  d5,d2
        jsr     _LVOFreeDosObject(a6)
```

### Gotchas
- A plain exec Task may call it for all V37 types and tags (`DOS_FILEHANDLE`..`DOS_RDARGS`,
  `ADO_FH_Mode`..`ADO_PromptLen`).
- `DOS_EXALLCONTROL` is mandatory for ExAll -- a static or stack ExAllControl is not allowed.
- Before V39 `FreeDosObject` cannot fully free a `DOS_CLI` object (see FreeDosObject).
- SetVBuf buffer-SIZE changes only affect file handles that came from AllocDosObject.

**See also:** [FreeDosObject](#freedosobject), [ExAll](locks-and-directories.md#exall),
[ReadArgs](arguments.md#readargs), [SendPkt](packets.md#sendpkt),
[SetVBuf](buffered-io.md#setvbuf)

## FreeDosObject
`VOID FreeDosObject(ULONG type, APTR ptr)` — LVO -234 (-$EA)
Registers: type=D1, ptr=D2; no result

Free an object obtained from AllocDosObject().

- **type** — the type it was allocated with.
- **ptr** — the pointer AllocDosObject returned (for `DOS_STDPKT` the DosPacket pointer).

Since V36.

### Gotchas
- Never pass memory from AllocMem/AllocVec or a stack structure, and never mismatch `type`.
- Before V39, freeing a `DOS_CLI` object leaks its strings: FreeDosObject frees only the
  CommandLineInterface. Pre-V39 workaround from the autodoc: `FreeVec()` `cli_SetName`,
  `cli_CommandName`, `cli_CommandFile` and `cli_Prompt`, then set them to 0. Those fields are
  BSTRs, so the address to free is presumably `BADDR(field)` (unverified). Do NOT do this on V39+.

**See also:** [AllocDosObject](#allocdosobject)
