# amiga-os errata

Discrepancies found while distilling the exec, dos, graphics, intuition and diskfont reference: disagreements between sources,
OCR ambiguities, toolchain behaviour that contradicts documentation, and statements that
could not be verified locally (these are marked "(unverified)" in the entries). Each item
records the resolution used in the reference. When sources conflict, the NDK 3.9 includes
and SFD files win for names, offsets and registers; the Commodore documentation wins for
behaviour unless a test with the bundled toolchain showed otherwise.

## exec.library and shared topics

### Prototype / type mismatches (autodoc vs NDK 3.9 includes)

- **CheckIO result** — V37 autodoc (prb28) says `BOOL CheckIO()`; NDK 3.9 autodoc, clib and SFD say `struct IORequest *`; resolution: documented as a request pointer or NULL (the 3.9 autodoc BUGS section itself calls BOOL wrong).
- **Procure / Vacate** — include: `ULONG Procure(struct SignalSemaphore *, struct SemaphoreMessage *)`; 3.9 autodoc: `VOID Procure(...)`; V37 autodoc: `BYTE Procure(struct Semaphore *, struct Message *)` and a one-argument `Vacate(struct Semaphore *)`; resolution: follow the include fact block, and state that only the V39+ SignalSemaphore semantics work.
- **AllocSignal / FreeSignal argument** — autodoc and SFD say `BYTE signalNum`; clib/fact block say `LONG signalNum`; resolution: follow the fact block. The result is still a BYTE (test with `tst.b` in asm).
- **AttemptSemaphore result** — autodoc `LONG`; include `ULONG`; resolution: include.
- **MakeFunctions result** — autodoc documents `ULONG tableSize` in D0; clib/SFD prototype is `VOID`; resolution: fact block kept as VOID, and the entry mentions the documented D0 size (read it from asm if needed).
- **CreatePool result register** — autodoc SYNOPSIS labels the result `a0`; fd/SFD/inline use D0; resolution: D0.
- **AVL_AddNode prototype line** — the autodoc SYNOPSIS C line is mislabeled `AVL_FindNextNodeByKey(...)`; resolution: use clib `AVL_AddNode(struct AVLNode **root, struct AVLNode *node, APTR func)`.
- **AddIntServer intNum type** — autodoc `ULONG`; include `LONG`; autodoc register note `D0-0:4` (low 4 bits); resolution: include type, low-4-bits note kept.
- **GetCC result type** — autodoc `UWORD`; include/fact block `ULONG`; resolution: include; the entry only says "condition codes".
- **FreeTrap argument type** — autodoc `ULONG`; include `LONG`; resolution: include.
- **CachePreDMA / CachePostDMA length** — autodoc `LONG *`; include `ULONG *`; resolution: include.
- **AllocTrap vector range** — autodoc says exception vectors 32..47 correspond to "Trap #1...Trap #15"; 32..47 is 16 vectors = TRAP #0..#15; resolution: documented as TRAP #0-#15.

### Constants / structure definitions

- **AN_MemCorrupt value** — AllocMem/FreeMem/AllocAbs/Allocate autodocs print `$01000005`; exec/alerts.h defines `AN_MemCorrupt 0x81000005` (dead-end bit set); resolution: quote both, include value authoritative.
- **AN_BadFreeAddr** — not mentioned in the autodocs; alerts.h defines `0x0100000F` ("memory header not located"); resolution: cited from alerts.h in FreeMem.
- **alerts.h example comment** — comment computes AN_TimerDev|AG_OpenLib|AO_MathLib as 0x05038015 but the defines OR to 0x15038005; resolution: follow the defines; example not reproduced.
- **AFB_68060 / AFF_68060** — present in exec/execbase.h (bit 7) and Bartman's copy; absent from execbase.i (both NDK 3.9 and Bartman); resolution: asm code uses bit 7 literally, noted in structures.md.
- **Task offset $22** — tasks.h: `UWORD tc_TrapAlloc; UWORD tc_TrapAble;`; tasks.i: `APTR tc_ETask`; resolution: documented as private, headers disagree.
- **LIBF_EXP0CNT** — `BITDEF LIB,EXP0CNT,4` only in libraries.i; libraries.h lacks it; resolution: noted as asm-only.
- **DMA flag names** — execbase.h: `DMA_Continue`, `DMA_NoModify`, `DMA_ReadFromRAM` (masks 2/4/8); execbase.i BITDEF gives `DMAF_Continue`/`DMAB_Continue` etc.; the autodoc uses the C names; resolution: give both spellings.
- **ExecBase ChkSum** — `WORD ChkSum` in execbase.i, `UWORD ChkSum` in execbase.h; resolution: irrelevant (private), not documented.
- **Task UserData label** — asm label is `TC_Userdata`, C field `tc_UserData`; resolution: both spellings shown.
- **MemList size** — asm `ML_SIZE` ($10) excludes MemEntry structs; C `sizeof(struct MemList)` (24) includes the first; resolution: warned in structures.md and AllocEntry.
- **SM_SHARED / SM_EXCLUSIVE** — defined only in semaphores.h; semaphores.i has no equivalent; resolution: asm writes 1/0.
- **exec/avl.i** — no asm include for AVLNode/AVLKey (neither NDK 3.9 nor Bartman); resolution: asm defines its own 16-byte node offsets.
- **Cause node type** — autodoc writes `NT_UNKOWN`; the constant is `NT_UNKNOWN` (0); resolution: include spelling.
- **ables.i macros vs Disable autodoc** — the autodoc says never use a macro for Disable; exec/ables.i still ships DISABLE/ENABLE/FORBID/PERMIT macros (needing an external `_intena`); resolution: macros mentioned, real calls recommended.

### Versions

- **Cache functions / pools version grouping** — clib/SFD place CacheClearU/CacheClearE/CacheControl and the pool LVOs under "V36 or higher"; autodocs say CacheClearU/CacheClearE/CachePreDMA/CachePostDMA are V37 and pools V39; CacheControl has no version in its autodoc; resolution: autodoc versions used; CacheControl gets no "Since" line.
- **NewMinList** — no autodoc; clib comment places it under "functions in V45 or higher"; resolution: "Since V45" with the Source line.
- **V45 exec availability** — exec_relnotes describe V45 as the start of a RAM-loadable exec; the clib comments tie V40 to Release 3.1, and exec V40 in Kickstart 3.1 ROMs is standard knowledge; resolution: every V45 entry tells the reader to check `lib_Version >= 45`.
- **Version-to-release mapping** — no autodoc gives it, but the NDK 3.9 clib headers' section comments do: V31 = 1.1, V33 = 1.2, V34 = 1.3, V36 = 2.0, V37 = 2.04, V38 = 2.1, V39 = 3, V40 = 3.1, V44 = 3.5, V45 = 3.9; resolution: used as given (index.md, opening-libraries.md).
- **MEMF_TOTAL version** — memory.h/.i define bit 19 with no version; AvailMem autodoc does not mention it; resolution: marked "V39+, unverified".

### Private LVOs

- **Private slot names** — fd/exec_lib.fd: execPrivate1-22 (-36..-66, -504..-516, -738..-756, -792..-822, -834..-846); include_i/exec/exec_lib.i names -738..-756 ChildFree/ChildOrphan/ChildStatus/ChildWait, -792..-822 execPrivate10-15 and -834..-846 ExecReserved10-12; resolution: table in system.md shows both.
- **RawIOInit / RawMayGetChar / RawPutChar** — no local source names LVOs -504/-510/-516 (fd: execPrivate7-9, "private diagnostic support"); Bartman's template KPutCharX does `jsr -0x204(a6)` with the char in D0, confirming -516 as serial char output; resolution: names marked (unverified).

### Unverified claims kept (open items)

- **MEMF_CLEAR on pools** — CreatePool autodoc only says "memory flags as taken by AllocMem"; AllocPooled returning zeroed memory marked (unverified).
- **FreeMem/FreeVec/pool calls from interrupts** — only AllocMem's autodoc forbids interrupts; same restriction applied to the others, marked (unverified).
- **Low-memory handler / AVL callback / soft interrupt registers** — autodocs give only entry registers; "preserve D2-D7/A2-A6" and "A1 = is_Data for Cause'd code" marked (unverified).
- **Who clears INTREQ for server chains** — AddIntServer autodoc silent (SetIntVector says handlers clear their own); claim that exec clears it for chains marked (unverified).
- **Interrupt handler owners** — TBE/RBF = serial.device, DSKBLK/DSKSYNC = disk, AUD0-3 = audio.device is standard knowledge, not in local sources.
- **Memory list lock** — no source says which lock guards ExecBase MemList; Forbid marked (unverified). Task queues need Disable (FindTask autodoc: name search disables interrupts).
- **ss_QueueCount** — "-1 when free" is standard knowledge, marked (unverified) in structures.md.
- **RemSemaphore removal pattern** — Forbid, RemSemaphore, Obtain/Release, Permit before freeing; not in local sources, marked (unverified).
- **OpenDevice parallel requests** — no local source describes cloning an opened request (copying `io_Device`/`io_Unit`) for parallel I/O; marked (unverified) in OpenDevice.
- **ROM vs disk libraries** — which libraries are in ROM on each Kickstart is not in the local sources; marked (unverified) in opening-libraries.md, FindResident given as the runtime check.
- **SAD V39 command numbering** — autodoc only gives the READ_WORD example of the off-by-one; "all commands above WRITE_BYTE shift" is written as presumably.

### Toolchain findings (verified with Bartman m68k-amiga-elf-gcc 15.1.0 / vasm)

- **Varargs `...Tags` stubs** — inline macros build a `ULONG` array; a pointer argument without `(ULONG)` cast is a hard error (-Wint-conversion) in GCC 15; resolution: every example casts.
- **Inline NextTagItem / AVL_AddNode / AVL_RemNodeByAddress / AVL_RemNodeByKey** — the LP macros declare `register volatile t1` giving `volatile struct X **`, which GCC 15 rejects (-Wincompatible-pointer-types); resolution: taglists.md gives a hand-written walker or `-Wno-error=incompatible-pointer-types`; avl.md uses a `#pragma GCC diagnostic` workaround.
- **Inline macros shadow names** — `inline/exec.h` defines every function name (Insert, Remove, Wait, ...) as a function-like macro; a user function with the same name fails to compile; resolution: gotcha added.
- **Bartman template is -nostdlib** — amiga.lib (CreatePort, CreateTask, CreateExtIO, LibCreatePool, sprintf, ...) is not linked. Bartman's `proto/alib.h` still declares every amiga.lib prototype, but only `BeginIO()` and `NewList()` are real inline macros (inline/alib.h); resolution: entries show amiga.lib-free code and mention the two inline macros.
- **C vs asm offsets** — Bartman GCC `offsetof` equals vasm-resolved NDK .i offsets for Node, List, Library, Task, MsgPort, Message, Interrupt, IORequest, IOStdReq, MemHeader, MemList, SignalSemaphore, ExecBase and Process; no discrepancy.
- **clib/*_protos.h encoding** — files are ISO-8859 (copyright byte); plain `grep` treats them as binary and silently prints nothing; use `grep -a`.

## dos.library

Sources compared: NDK 3.9 autodocs (NDK 3.9 autodocs (dos.doc) ), NDK 3.9 prototypes/sfd (fact blocks), NDK 3.9 include_h/include_i, V37 prb28 autodocs, NDK 3.9 release notes (ffs_relnotes), Bartman GCC inline headers (test compiles).

### concepts.md, index.md, errors.md, arguments.md, variables.md, time.md, notification-and-locking.md, objects.md

- **FindArg argument order** — NDK 3.9 autodoc (and V37 prb28): `index = FindArg(template, keyword)` with template=D1, keyword=D2, and BUGS says earlier autodocs had them backwards; NDK 3.9 sfd/prototype/Bartman inline: `FindArg(CONST_STRPTR keyword, CONST_STRPTR arg_template)` (d1,d2); resolution: fact block unchanged, entry tells callers to follow the autodoc (template in D1 / first C argument). Which order the ROM really uses cannot be checked locally (open item).
- **FindArg index base** — autodoc says "argument number" / "number of entry in template" without saying whether the first item is 0; resolution: documented as 0-based (same as the ReadArgs array index), marked (unverified).
- **Fault return** — NDK 3.9 autodoc: `LONG Fault(...)` returns the length, BUGS says older docs wrongly showed BOOL; V37 prb28 autodoc and NDK 3.9 prototype/sfd: `BOOL Fault(...)`; resolution: fact block kept, entry says D0 is a character count.
- **ErrorReport REPORT_FH** — autodoc lists request type `REPORT_FH`; dosextens.h/.i define only `REPORT_STREAM` (0), `REPORT_TASK` (1), `REPORT_LOCK` (2), `REPORT_VOLUME` (3), `REPORT_INSERT` (4); resolution: entry uses `REPORT_STREAM`.
- **ErrorReport DOS_TRUE / return type** — autodoc says it returns `DOS_TRUE` and prototype-types it BOOL; dos.h only defines `DOSTRUE` (-1); NDK prototype returns LONG; resolution: entry says DOSTRUE, test for zero (= Retry).
- **LockRecord return type** — V37 prb28 autodoc: `ULONG LockRecord(...)`; NDK 3.9 autodoc and prototype: `BOOL`; resolution: BOOL, test non-zero.
- **Delay argument** — autodoc: `void Delay(ULONG)` with input `ticks`; NDK prototype: `VOID Delay(LONG timeout)`; resolution: fact block kept, bullet says ticks (unsigned per autodoc).
- **DateToStr / StrToDate return type** — autodocs: BOOL; NDK prototypes: LONG; resolution: test non-zero.
- **FORMAT_INT layout** — datetime.h and datetime.i comments: `yy-mm-dd`; DateToStr/StrToDate autodocs: `yy-mmm-dd`; resolution: table shows the header form and notes the autodoc form (not verified which the ROM prints).
- **FORMAT_DEF in asm** — datetime.h defines `FORMAT_DEF` (4, locale default); datetime.i has no FORMAT_DEF (only FORMAT_DOS..FORMAT_CDN and FORMAT_MAX); resolution: noted in time.md; asm users write 4.
- **DateStamp resolution** — autodoc says DateStamp "only returns even multiples of 50 ticks. Therefore the time you get is always an even number of ticks" (the second sentence does not follow from the first); resolution: documented as whole-second resolution (multiples of 50 ticks), not verified for V39+ ROMs.
- **GVF_SAVE_VAR comment** — var.h and var.i say "only with GVF_GLOBAL_VAR"; no GVF_GLOBAL_VAR exists; resolution: read as GVF_GLOBAL_ONLY. var.h mentions only SetVar for this flag; DeleteVar behaviour with it is undocumented (not claimed).
- **SetVar default** — autodoc: "The default is to set a local environment variable" (mixing "local" and "environment", the term used for globals); resolution: documented as local by default, advise passing GVF_GLOBAL_ONLY explicitly.
- **ReadArgs `?` help** — rdargs.h says RDA_ExtHelp is shown "if the user is prompted for input" and RDAF_NOPROMPT disables reprompting, but no local source says typing `?` triggers the prompt; resolution: stated with (unverified).
- **ReadItem terminator** — autodoc FUNCTION says ReadItem always unreads the terminator (UnGetC(fh,-1)); its BUGS says it does not actually unread it; resolution: entry tells callers not to rely on it.
- **ReadItem parameter names** — autodoc: `ReadItem(buffer, maxchars, input)`; NDK prototype names the buffer `name` and the CSource `cSource`; resolution: fact block kept, bullets explain.
- **StrToLong sign** — autodoc only describes decimal digits and leading blanks; handling of a leading `-` is not documented; resolution: not claimed.
- **FreeDosObject pre-V39 DOS_CLI workaround** — autodoc says to `FreeVec()` cli_SetName, cli_CommandFile, cli_CommandName and cli_Prompt; dosextens.h types these fields as BSTR (BPTRs), so FreeVec on the raw field value would be wrong; resolution: entry says the address is presumably BADDR(field), marked (unverified).
- **AllocDosObject from tasks** — autodoc allows tasks to call AllocDosObject for V37 types/tags; FreeDosObject's autodoc says nothing about tasks; resolution: concepts.md lists only AllocDosObject as task-callable.
- **NotifyRequest flags NRF_WAIT_REPLY / NRF_NOTIFY_INITIAL** — defined in notify.h with no comment; neither the StartNotify autodoc nor any local source describes them; resolution: behaviour given in notification-and-locking.md is marked (unverified).
- **Record-lock error codes** — dos.h defines ERROR_RECORD_NOT_LOCKED 240 .. ERROR_UNLOCK_ERROR 243 but no autodoc says which record call returns which; resolution: listed as "related codes" only.
- **ERROR_ table meanings** — dos.h has no comments on most ERROR_ constants; meanings in errors.md are paraphrased from the names, plus callers where an autodoc names the code (ExNext/ExAll/MatchFirst/GetDeviceProc -> 232, GetVar -> 205/115, NameFromLock -> 120, Get*Name -> 212, MatchPattern -> 217, Format -> 202, ReadLink -> 233, rdargs.h MAX_MULTIARGS -> 120); resolution: no Fault() message text is quoted.
- **Workbench start: no streams / no CLI** — the only local support is the Execute autodoc ("programs running under the Workbench do not normally have a current window"); concepts.md and errors.md (PrintFault) state that Input()/Output() are normally 0 and Cli() is NULL for Workbench starts; resolution: marked (unverified) where stated in my files.
- **CON: window specification** — Open autodoc only says "CON: or RAW: followed by window parameters"; the `CON:x/y/width/height/title` form is not in any local source; resolution: marked (unverified) in concepts.md.
- **Seek and files over 2 GB** — no dos autodoc mentions it; the NDK 3.9 ffs_relnotes (FFS V43) say files may now be 0..4GB-2 bytes and software must check for exactly -1 because positions are unsigned; resolution: concepts.md, index.md and the files.md Seek entry say to compare with -1 exactly (files.md FileSize example changed from `< 0` to `== -1`).
- **cli_Result2 and the shell** — dosextens.h comments cli_Result2 "Value of IoErr from last command"; that the Why command reports it is background knowledge; resolution: SetIoErr/Standard-output notes mention "a meaningful Why" without detail.
- **pr_WindowPtr = -1** — ErrorReport and NameFromLock autodocs state that -1 suppresses the requesters; advising callers to restore the old value before exit is practice, not a sourced rule; resolution: kept as advice.

### files.md

- **Seek result** — NDK 3.9 autodoc FUNCTION text says the result is "the current absolute position"; its SYNOPSIS names it `oldPosition` (same in V37 prb28); resolution: documented as the position before the seek (the standard `Seek(fh,0,OFFSET_END); size = Seek(fh,0,OFFSET_BEGINNING);` idiom depends on it).
- **Seek V36/V37 error return** — V37 prb28 BUGS says the ROM FS returns the current position instead of -1 with no fix noted; NDK 3.9 autodoc adds "fixed in the V39 filesystem"; resolution: documented as fixed in V39 with the IoErr() workaround for 2.x.
- **NameFromFH error code** — NDK 3.9 autodoc says old filesystems fail with `ERROR_ACTION_NOT_SUPPORTED`; no such constant exists in dos/dos.h (the name is `ERROR_ACTION_NOT_KNOWN`, 209); resolution: entry points at `ERROR_ACTION_NOT_KNOWN` and notes the autodoc name. Same code assumed for ExamineFH on old filesystems (unverified).
- **ChangeMode newmode for CHANGE_FH** — autodoc only says "the new mode you want" with a shared->exclusive lock example; no include documents the value expected for file handles; resolution: entry recommends `SHARED_LOCK`/`EXCLUSIVE_LOCK` and marks the CHANGE_FH case (unverified).
- **ChangeMode parameter name** — autodoc calls the 2nd argument `object` (lock or filehandle); NDK 3.9 prototype names it `fh`; resolution: fact block kept, bullet explains it takes either.
- **SetOwner version** — autodoc NAME says (V39) but text says the entry point exists from V37 and returns FALSE there; not present in V37 prb28 set; resolution: "Since V39." plus gotcha about V37/V38 returning FALSE.
- **Close / DeleteFile / Rename / SetProtection / SetComment / IsInteractive / WaitForChar / SetMode return types** — autodocs say BOOL; NDK 3.9 prototypes say LONG; resolution: fact blocks keep LONG, text treats them as boolean (non-zero = success).
- **Close(0)** — no source states whether Close(0) is harmless (UnLock(0) is documented harmless); resolution: entry advises not to pass 0.
- **Input()/Output() from Workbench** — stated that Workbench-started programs normally have 0 streams / no console; only indirect local support (Execute autodoc: "programs running under the Workbench do not normally have a current window"); standard knowledge, (unverified) against a local source.
- **FileHandle 2nd field** — C dos/dosextens.h names it `fh_Port` ("reply port for the packet"); asm dos/dosextens.i names it `fh_Interactive` ("TRUE if interactive handle"); resolution: not used in entries (use IsInteractive()).
- **SetProtection bit description** — V37 prb28 lists bits 4-0 in prose (bit 4 "1 = file has not changed"); NDK 3.9 autodoc drops the list and points to dos/dos.h; resolution: table built from dos/dos.h `FIBB_`/`FIBF_` definitions.

### buffered-io.md

- **SetVBuf version** — V37 prb28 autodoc NAME says (V36) and BUGS "Not implemented yet, always returns 0"; NDK 3.9 autodoc says (V39) and "Not implemented until after V39. From V36 up to V39, always returned 0"; resolution: "Since V39." with gotcha that it is only functional after V39 (entry point exists since V36).
- **SetVBuf small size** — V37 prb28: sizes under 208 bytes "will be ignored"; NDK 3.9: rounded up to 208; resolution: NDK 3.9 wording.
- **SetVBuf size -1** — V37 prb28: "If buff is NULL and size is -1, only the mode changes"; NDK 3.9: "If size is -1, then only the buffering mode will be changed" (buff not required NULL); resolution: NDK 3.9 wording.
- **FPuts result** — V37 prb28 FUNCTION says "the length actually written is returned"; its RESULT and the NDK 3.9 autodoc say 0 normally, -1 on error; resolution: 0/-1 (inverted).
- **FPutC argument type** — V37 prb28 prototype `LONG FPutC(BPTR, UBYTE)`; NDK 3.9 autodoc and prototype use LONG and BUGS says pass a LONG 0-255; resolution: LONG.
- **VFWritef result** — autodoc SYNOPSIS `LONG VFWritef(...)` with "count - Number of bytes written or -1"; BUGS and the NDK 3.9 prototype say VOID (no valid return as of V37); resolution: VOID.
- **VFWritef width digit** — autodoc says "x is in base 36" and also "'x' above is actually the character value - '0'" (these disagree for letters); V37 prb28 same text; resolution: entry recommends digits 0-9 only.
- **VFWritef description** — V37 prb28 says it writes to "the default output" (and lacks the fh input); NDK 3.9 says "the specified file"; resolution: NDK 3.9.
- **FGets V36/V37 overflow bug** — present in NDK 3.9 BUGS, absent from V37 prb28 doc; resolution: documented (pass size-1 on 2.x).
- **Flush V36/V37 never-buffered-handle bug** — present in NDK 3.9 BUGS only; resolution: documented with the FGetC/UnGetC/Flush workaround.
- **FWrite blocks input** — V37 prb28 says "number of blocks to read" for FWrite (copy/paste typo); NDK 3.9 says "to write"; resolution: NDK 3.9.
- **RawDoFmt %u default size** — exec RawDoFmt autodoc lists WORD default only for d, x and c, and adds u in V37 exec without stating its default; resolution: entries recommend `%lu` (unverified whether plain `%u` is 16-bit).
- **Printf/FPrintf pointer arguments** — autodoc BUGS says the old prototype forces a cast of the first vararg to LONG; with Bartman's GCC 15.1 inline macros (`_sfdc_vararg` = ULONG) an uncast pointer argument is a hard error (-Wint-conversion), verified by test compile; resolution: examples cast pointers to (LONG).
- **VPrintf/VFPrintf return types** — autodoc and prototype agree (LONG); `CONST APTR argarray` in the 3.9 prototype vs `LONG *` in the autodoc; resolution: fact block kept.

### locks-and-directories.md

- **ExAll buffer type** — NDK 3.9 autodoc and V37 prb28 synopsis give `BOOL ExAll(BPTR,STRPTR,LONG,LONG,struct ExAllControl *)`; NDK 3.9 prototype/sfd gives `LONG ExAll(BPTR lock, struct ExAllData *buffer, ...)`; resolution: fact block uses the prototype; entry documents the buffer as an ExAllData chain (same bytes).
- **ExAll ED_OWNER** — V37 prb28 autodoc lists types only up to ED_COMMENT ("ED_COMMENT gives everything"); NDK 3.9 autodoc and exall.h add ED_OWNER 7 (V39) plus the V37 ROM-filesystem BSTR-comment and ED_OWNER-trashing bugs; resolution: documented ED_OWNER as V39 with the pre-V39 fallback to ED_COMMENT.
- **ExAll field names** — NDK 3.9 autodoc text says "ead_Next" and names control fields Entries/LastKey/MatchString/MatchFunc; exall.h names them `ed_Next`, `eac_Entries`, `eac_LastKey`, `eac_MatchString`, `eac_MatchFunc`; resolution: header names used.
- **ExAllEnd** — present in NDK 3.9 autodoc (V39) and sfd; absent from the V37 prb28 set; resolution: documented as V39 only.
- **FileInfoBlock date field** — dos.h names it `fib_Date`; asm dos.i names the same field `fib_DateStamp`; resolution: both names given in the Examine field table.
- **fib_DirEntryType test** — ExNext autodoc: positive = directory, negative = file; dosextens.h comment: use `<0` and `>=0` for file/directory checks; resolution: entries tell readers to test files with `< 0`.
- **Examine/ExNext/Info/NameFromLock return type** — autodocs say BOOL; NDK 3.9 prototypes say LONG; resolution: prototype in fact block, documented as boolean (non-zero = success).
- **SameDevice version** — autodoc NAME says V37 but notes the entry existed in V36 returning 0; resolution: "Since V37" with a gotcha about V36.
- **MakeLink hard-link lock ownership** — no local source says whether the `dest` lock of a hard link is consumed; entry states it stays with the caller, marked (unverified); open item.
- **Stack-allocated FileInfoBlock/InfoData alignment** — autodocs only say "must be longword aligned"; entries add that a C local variable is not guaranteed to be longword aligned by 68k compilers (standard knowledge, consistent with the autodoc advice to use AllocDosObject); no local source states the compiler rule.

### paths-and-names.md

- **ParsePattern buffer size** — ParsePattern autodoc says Dest must be "2 times as large as Source plus bytes" (number missing) and later "twice as large as source + 2 bytes"; ParsePatternNoCase autodoc says "plus 2 bytes"; resolution: `2 * strlen(pattern) + 2`.
- **ParsePattern/ParsePatternNoCase BUGS** — NDK 3.9 autodocs add "Fixed in V39" for the V37 IoErr() bug and the V37 character-class upper-casing bug (utility.library ToUpper workaround); V37 prb28 text lacks the fix version and the ToUpper workaround; resolution: 3.9 text used.
- **SplitName BUGS** — NDK 3.9 autodoc documents a V36/V37 last-character-loss bug (fixed V39) with a size workaround; V37 prb28 autodoc has no BUGS section; resolution: 3.9 text used.
- **SplitName types** — autodoc prototype `WORD SplitName(STRPTR, UBYTE, STRPTR, WORD, LONG)`; NDK 3.9 prototype `WORD SplitName(CONST_STRPTR, ULONG separator, STRPTR, LONG oldpos, LONG size)`; resolution: fact block uses the NDK prototype; result kept as a 16-bit WORD (asm: `ext.l d0` before comparing with -1 -- derived from the WORD type, not stated by the autodoc).
- **`*` wildcard switch** — ParsePattern autodoc says `*` is off by default in 2.0 and "can be turned on" without saying how; dosextens.h defines `RNB_WILDSTAR`/`RNF_WILDSTAR` in RootNode `rn_Flags` with no comment; resolution: entry says not to rely on `*`; the RNF_WILDSTAR link is not documented (open item, unverified).
- **Quote escape in patterns** — the `'` escape character commonly used in AmigaDOS patterns is not described in any local source (autodoc token table and dosasl.h P_ tokens omit it); resolution: omitted from the pattern table (open item).
- **`^` token** — dosasl.h defines `P_NOTCLASS 0x87 /* Token for '^' */`, but the ParsePattern autodoc documents negated classes as `[~bc]` only; resolution: only `[~...]` documented.
- **MatchFirst/MatchNext recursion idiom** — the APF_DODIR / APF_DIDDIR enter-and-clear loop is derived from the dosasl.h bit comments ("Application can RESET this bit ... to AVOID entering a dir", "SET for an expired dir node"); no local source gives the full idiom; resolution: documented as a short snippet consistent with the header comments.
- **AnchorPath ap_Buf** — dosasl.h declares `UBYTE ap_Buf[1]` while dosasl.i declares `LABEL ap_Buf` (no storage); resolution: entry says to allocate `sizeof(struct AnchorPath) + buffer` and set `ap_Strlen` to the buffer size.

### processes.md

- **CheckSignal name** — V37 prb28 autodoc prototype line reads `ULONG CheckSignals(ULONG)`; NDK 3.9 autodoc and sfd say `CheckSignal`; resolution: `CheckSignal` (prb28 typo).
- **CheckSignal types** — NDK 3.9 autodoc: `ULONG CheckSignal(ULONG)`; NDK sfd/prototype: `LONG CheckSignal(LONG mask)`; resolution: fact block from sfd; documented as a signal bit mask (type irrelevant to register use).
- **FindCliProc argument type** — V37 prb28: `FindCliProc(LONG)`; NDK 3.9 autodoc and sfd: `ULONG num`; resolution: ULONG, range 1..MaxCli().
- **MaxCli return type** — NDK 3.9 autodoc: `LONG MaxCli(void)`; sfd: `ULONG MaxCli()`; resolution: fact block (ULONG); value is always a small positive number.
- **SetArgStr return** — NDK 3.9 and V37 autodocs: returns `STRPTR oldptr`; NDK sfd/prototype: `BOOL SetArgStr(CONST_STRPTR)`; resolution: entry says D0 holds the old string pointer despite the BOOL prototype (cast when saving it).
- **Execute return type** — autodoc: `BOOL Execute(STRPTR, BPTR, BPTR)`; sfd: `LONG Execute(...)`; resolution: treat as boolean success.
- **CliInitRun autodoc wording** — the CliInitRun autodoc says the packet "will have already been returned by CliInitNewcli()"; it is the CliInitRun text (copy/paste from CliInitNewcli); resolution: read as CliInitRun().
- **NP_ExitData comment** — dostags.h/dostags.i describe NP_ExitData as the "optional argument for NP_EndCode rtn"; no NP_EndCode tag exists; resolution: it is the argument for NP_ExitCode.
- **SystemTagList V37 vs 3.9 text** — V37 prb28 autodoc lacks the "never pass the same handle for SYS_Input and SYS_Output" rule, the list of filtered NP_ tags and the "-1 only if the shell could not be created / not found -> RETURN_ERROR" note; resolution: 3.9 text used.
- **NP_ tag hex values** — computed from dostags.h (`NP_Dummy` = `TAG_USER`+1000, `TAG_USER` = 1<<31 from utility/tagitem.h) and `SYS_Dummy` = `TAG_USER`+32; not listed numerically in any source; resolution: derived values given in tables.
- **NP_Entry process termination (unverified background knowledge)** — no local source states that returning from an NP_Entry function ends the process, nor the "Forbid(); Signal(parent)" exit idiom; standard practice; resolution: used in the CreateNewProc example without marking, listed here as open.
- **Workbench-started process state (unverified)** — sources only say Workbench programs "do not normally have a current window" (Execute autodoc) and Cli() may return NULL; statements that pr_ConsoleTask is NULL for Workbench starts (GetConsoleTask gotcha) are background knowledge; marked (unverified) in text.
- **SetProgramDir lock ownership (unverified)** — autodoc does not say who unlocks a lock installed with SetProgramDir(); resolution: entry advises restoring the old lock and unlocking your own, marked (unverified).
- **pr_Flags meaning** — dosextens.h only defines PRF_FREESEGLIST ... PRF_FREEARGS with the comment "flags telling dos about process"; the entry's reading that they record what DOS frees at exit is inferred from the names; resolution: kept as a one-line note.
- **RunCommand paramlen** — autodoc says argsize is "its length" of a null-terminated string that must end in a newline; entry states the newline counts and the NUL does not (inference from "length" of a C string); resolution: kept, consistent with the asm/C examples.
- **GetProgramName truncation** — V37 prb28 text is garbled (sentence about truncation merges into the no-CLI sentence); 3.9 autodoc: truncates on a small buffer and fails only when no CLI; resolution: 3.9 wording.

### loading.md

- **UnLoadSeg return** — NDK 3.9 and V37 autodocs: `BOOL UnLoadSeg(BPTR)` returning 0 for a NULL seglist or failed overlay close; NDK sfd/prototype: `VOID UnLoadSeg(BPTR seglist)`; resolution: fact block VOID, entry mentions the autodoc D0 value but says not to depend on it.
- **InternalLoadSeg ReadFunc registers** — V37 prb28 register row under ReadFunc reads "D0 D1 A0 D0 A6"; NDK 3.9 autodoc: readhandle=D1, buffer=D2, length=D3, A6=DOSBase; resolution: 3.9 (matches Read()).
- **InternalLoadSeg readhandle (unverified)** — autodoc names the ReadFunc first argument `readhandle` without saying it equals the `fh` passed in D0; entry says "presumably" and marks (unverified).
- **InternalUnLoadSeg SEE ALSO** — NDK 3.9 and V37 autodocs list `NewUnLoadSeg()`; no such function exists in the NDK 3.9 sfd/LVO table; resolution: ignored.
- **AddSegment prototype** — autodoc: `BOOL AddSegment(STRPTR, BPTR, LONG)` with third input named `type` (initial use count); sfd: `LONG AddSegment(CONST_STRPTR name, BPTR seg, LONG system)`; resolution: fact block names, entry explains it is the initial seg_UC.
- **RemSegment return type** — autodoc `BOOL`; sfd `LONG`; resolution: boolean success.
- **FindSegment `system` input** — autodoc: "true for system segment, false for normal segments" but FUNCTION only defines the FALSE case (seg_UC >= 0); resolution: entry says non-zero searches system (negative seg_UC) segments without claiming whether normal ones are included.
- **LoadSeg memory flags (background knowledge)** — doshunks.h defines HUNKF_CHIP/HUNKF_FAST but no local autodoc states LoadSeg honours them; standard, universally relied on; resolution: stated in the LoadSeg entry, listed here as open.
- **Seglist layout / entry at BADDR(seglist)+4** — derived from LoadSeg ("BPTRs on their first words"), CreateProc (fake seglist: length longword, next BPTR, code) autodocs; resolution: stated in loading.md intro.
- **HUNK_RELOC32SHORT id** — doshunks.h note: V37 LoadSeg uses 1015 (HUNK_DREL32) by mistake, future versions accept 1015 and 1020; resolution: gotcha tells producers to use 1015 for V37 compatibility.

### dos-list.md

- **AssignLock / AddBuffers / Inhibit / Relabel / RemAssignList return type** — NDK 3.9 autodocs give `BOOL`; the NDK 3.9 prototypes (sfd/fact blocks) give `LONG` (AssignLock, AddBuffers, Inhibit, Relabel, RemAssignList); resolution: fact blocks kept as prototypes, entries describe the result as "non-zero on success" (AddBuffers: see its count quirk).
- **AttemptLockDosList failure value** — V37 prb28 autodoc has no BUGS section; NDK 3.9 autodoc adds that V36 through dos V39.23 returned NULL or 1 on failure (fixed V39.24); resolution: entry tells callers to test for both 0 and 1.
- **RemAssignList first entry** — V37 prb28 autodoc silent; NDK 3.9 autodoc BUGS says V36 through dos V39.23 could not remove the first lock of an assign (fixed V39.24); resolution: documented as a gotcha.
- **LockDosList autodoc example** — NDK 3.9 example uses `...->di_DeviceList` for the pre-V36 walk; dosextens.h `struct DosInfo` has no such field (the device list BPTR is `di_DevInfo`); resolution: entry names `di_DevInfo`.
- **LockDosList example unlock** — V37 prb28 example calls `UnLockDosList()` with no argument; NDK 3.9 example passes `LDF_VOLUMES|LDF_READ`; resolution: flags are mandatory (UnLockDosList autodoc).
- **AssignPath node type** — AssignPath autodoc says it uses "DLT_ASSIGNPATH, or some such"; no such constant exists; dosextens.h has `DLT_NONBINDING` (4) and dosextens.i comments it "non-binding assign (AssignPath)"; resolution: DLT_NONBINDING.
- **LDF_DELETE** — defined in dosextens.h/.i (bit 6, $40) with no comment or autodoc description; resolution: listed as "no public description", not recommended.
- **FindDosEntry start point** — autodoc says the search "starts with the entry dlist", yet its own loop `while (dl = FindDosEntry(dl, name, LDF_VOLUMES))` only terminates if the search begins after dlist (and the LockDosList cookie is not a valid node); resolution: entry describes the start/continue idiom without claiming inclusive/exclusive semantics.
- **GetDeviceProc end of multi-assign** — autodoc says re-calling returns a modified DevProc or NULL with ERROR_NO_MORE_ENTRIES, but not whether the passed-in DevProc is released when NULL comes back; resolution: example relies only on documented `FreeDeviceProc(NULL)` being safe after the loop (open item: confirm no leak).
- **Relabel argument** — autodoc SYNOPSIS names args (volumename,name), INPUTS say volumename is the "Full name of device to rename (with ':')"; prototype names them (drive,newname); unclear whether a volume name ("Work:") is also accepted; resolution: documented as device name with colon, per autodoc.
- **MakeDosEntry example (dol_Task preset)** — filehandler.h says a device node's task field, if NULL on access, causes a handler to be started; that a DLT_DEVICE node with only `dol_Task` set (other fields 0) is a complete working device is inferred, not stated; resolution: example kept minimal, claim is (unverified) for fields beyond dol_Task.
- **Format dostype values** — Format autodoc only says "Type of format"; the `ID_DOS_DISK`/`ID_FFS_DISK`/... values are the dos.h disk-type codes, matching filehandler.h `de_DosType` comments ($444F5300 old FS, $444F5301 FFS); resolution: ID_ constants documented as dostype values.

### packets.md

- **Packet argument layouts** — NDK 3.9 autodocs/includes give ACTION_ names and values but no dp_Arg layouts (except: ACTION_SERIALIZE_DISK takes no arguments, dosextens.h; Format autodoc warns printed ACTION_FORMAT docs are wrong); resolution: action table lists names/values/notes only; examples use ACTION_SERIALIZE_DISK or generic helpers.
- **DoPkt example Res1 test** — treating `DoPkt0(port, ACTION_SERIALIZE_DISK) == 0` as failure assumes the usual DOSTRUE/DOSFALSE Res1 convention, not stated in local sources; resolution: marked (unverified) in the code comment.
- **ReplyPkt example reply values** — replying `DOSFALSE` to ACTION_IS_FILESYSTEM from a stream handler and `DOSFALSE, ERROR_ACTION_NOT_KNOWN` to unknown actions is common handler practice (port-handler/queue-handler autodocs only list ACTION_IS_FILESYSTEM as supported); resolution: marked (unverified).
- **Async packets on pr_MsgPort** — DoPkt autodoc says it uses pr_MsgPort for replies; that every ordinary dos call does the same (so a pending SendPkt reply can collide with synchronous DOS I/O) is standard knowledge, not in local sources; resolution: gotcha marked (unverified), advises a private reply port.
- **Standard packet initialisation** — dosextens.h says "see the function init_std_pkt for initializing this structure", which is not a dos.library function in the NDK 3.9 sfd; AllocDosObject autodoc says DOS_STDPKT returns a pointer to sp_Pkt of an initialised object; resolution: entries use AllocDosObject(DOS_STDPKT)/FreeDosObject.
- **fh_Type as handler port** — dosextens.h comments `fh_Type` as "Port to do PutMsg() to / Address is negative if a plain file" (the second half is unexplained); resolution: fh_Type listed as a port source without relying on the sign remark.
- **SendPkt and dp_Port** — dosextens.h says dp_Port "Must be filled in each send"; SendPkt autodoc says the packet returns to `replyport` but not explicitly that it writes dp_Port; resolution: intro says SendPkt takes the reply port as `replyport` (inferred that it sets dp_Port).
- **DoPkt secondary result** — autodoc returns result2 in D1 as well as IoErr(); C prototypes only expose D0; resolution: documented — C callers use IoErr(), asm callers may read D1.
- **ACTION_READ / ACTION_WRITE values** — dosextens.h defines them as character constants 'R'/'W'; resolution: table gives both forms, 82 and 87.

### Review edits (applied after the group files were written)

- **FGetC EOF vs error** — the FGets autodoc says IoErr() is 0 for a NULL return at EOF, but the FGetC autodoc only says -1 means "EOF or an error"; resolution: the FGetC entry now tells callers to SetIoErr(0) before reading and marks "IoErr() 0 = plain EOF" as (unverified).
- **SetComment empty string** — files.md claimed `""` removes a comment; no local source says so; resolution: sentence removed.
- **Seek failure test** — files.md FileSize example tested `Seek(...) < 0`; per ffs_relnotes (V43 FFS, files up to 4GB-2 bytes, "checks for -1 as error code exactly") it now tests `== -1` and has a gotcha.

## graphics.library

Sources compared: NDK 3.9 autodocs (split per function), V37 prb28 autodoc pages, NDK 3.9
include_h/include_i/SFD/fd, Bartman amiga-debug 1.8.2 sys-include and project template. Items
marked "unverified" in the reference files are listed here as open items.

### General, GfxBase, colours, bitmaps, blitter (bitmaps-and-blits.md, colors-and-pens.md, blitter-and-timing.md, concepts.md)

- **BltBitMapRastPort result** — NDK 3.9 autodoc: `BOOL`, "RESULT TRUE"; NDK 3.9 SFD/clib: `VOID`; resolution: entry says do not rely on D0.
- **BltBitMap / FindColor / ObtainPen result types** — autodocs: `ULONG BltBitMap`, `ULONG FindColor`, `LONG ObtainPen`; SFD/clib: `LONG BltBitMap`, `LONG FindColor`, `ULONG ObtainPen`; resolution: fact blocks follow the SFD, ObtainPen entry tells C callers to compare with `(ULONG)-1` / store in a LONG.
- **SetRGB32CM synopsis** — NDK 3.9 autodoc synopsis line reads `void SetRGB4CM( struct ColorMap *, ULONG, ULONG, ULONG , ULONG);` under SetRGB32CM; resolution: typo, noted in the entry.
- **GetRGB32 NAME line** — autodoc NAME says "Set a series of color registers"; the function reads them into the table; resolution: noted in the entry.
- **LoadRGB32 autodoc example** — `ULONG table[]={1l<<16+0,...}` only works because `+0` binds tighter than `<<`; resolution: entries write `(count << 16) | first` and warn.
- **LoadRGB32/SetRGB32 from interrupts** — LoadRGB4/SetRGB4 autodocs say not interrupt-safe under V36+; the 32-bit calls say nothing; resolution: entries advise not calling them from interrupts (unverified for the RGB32 calls).
- **WaitBlit preserved registers** — autodoc says "do/d1/a0/a1 are preserved" (letter o for zero); resolution: D0/D1/A0/A1 preserved, condition codes may change.
- **BltClear row limit** — autodoc text "rows must be <- 1024" (typo); resolution: read as `<= 1024`.
- **BltMaskBitMapRastPort minterms** — autodoc gives symbolic `(ABC|ABNC|ANBC)` and `(ANBC)`; hex values $E0 / $20 computed from hardware/blit.h (`ABC` $80, `ABNC` $40, `ANBC` $20); resolution: both forms given.
- **BltBitMap minterms** — autodoc: `$0C0` copy, `$030` inverted source, `$050` invert destination; resolution: entry uses $C0/$30/$50; `$C0` = `ABC|ABNC` from blit.h.
- **QBlit/QBSBlit callback registers** — autodocs do not state how `bltnode.function` is called; entry says A0 = custom base, A1 = bltnode, D0 = 0 when done / non-zero to be called again, marked (unverified, RKM convention). Open item.
- **gb_Modes comment** — gfxbase.h: "copy of current first bplcon0"; gfxbase.i: "copy of bltcon0"; resolution: bplcon0 used in concepts.md, discrepancy mentioned.
- **GFXB_BIG_BLITS** — gfxbase.h/.i define `GFXB_BIG_BLITS` and `GFXB_HR_AGNUS` both as bit 0; resolution: documented as aliases.
- **GfxBase / STRUCTURE label clash (asm)** — `STRUCTURE GfxBase,LIB_SIZE` in gfxbase.i defines the symbol `GfxBase` (exec/types.i STRUCTURE macro: `\1 EQU 0`); a user variable `GfxBase:` fails with vasm "label <GfxBase> redefined" (verified); resolution: all asm examples use `_GfxBase`, noted in index.md and concepts.md.
- **GfxBase offsets** — computed with m68k-amiga-elf-gcc `offsetof` on NDK 3.9 gfxbase.h and assembled with vasm on gfxbase.i: `gb_ActiView` $22, `gb_copinit` $26, `gb_LOFlist` $32, `gb_SHFlist` $36, `gb_DisplayFlags` $CE, `gb_NormalDisplayRows` $D8, `gb_ChipRevBits0` $EC, `gb_ChunkyToPlanarPtr` $1FC; both agree.
- **Bartman gfxbase.h** — Bartman sys-include gfxbase.h adds `#ifdef __KICK13__ ULONG reserved[23]` variant; field offsets unchanged otherwise; resolution: none needed.
- **gfxmacros.h `custom` macros** — ON_DISPLAY/OFF_DISPLAY/ON_SPRITE/OFF_SPRITE/ON_VBLANK/OFF_VBLANK reference an object `custom` that hardware/custom.h never declares (comment only); Bartman template defines `struct Custom *custom` (pointer), so they do not compile there; ON_VBLANK needs hardware/intbits.h which gfxmacros.h does not include; resolution: documented in blitter-and-timing.md.
- **C-only / asm-only constants** — `SPRITE_ATTACHED`, `CLEANUP`, `DBLPALLORESDPFFF_KEY`, `DBLPALLORESDPF2FF_KEY`, `DBLPALHIRESDPFFF_KEY`, `DBLPALHIRESDPF2FF_KEY` exist only in the C headers; asm uses `CLEANME` for CLEANUP; renamed asm names (`MUST_FLAGS` for SPECIAL_FLAGS, `RP_JAM1`, `V_HIRES`, `RPF_AREAOUTLINE`, `rp_AOLPen`, `BORDER_SPRITES`, `VPXF_VP_LAST`, `VSF_*`, `BF_*`); resolution: table in concepts.md.
- **AllocRaster argument width** — V37 prb28 autodoc: `AllocRaster(UWORD,UWORD)` d0:16/d1:16; NDK 3.9 autodoc/SFD: ULONG/UWORD in D0/D1; resolution: follow NDK 3.9.
- **FreeColorMap(NULL)** — NDK 3.9 autodoc: NULL acceptable from V39; V37 page silent; resolution: entry says test the pointer on V37.
- **InitBitMap BytesPerRow rounding** — autodoc does not give the formula; entry states width rounded up to 16 bits in bytes, consistent with the `RASSIZE` macro in gfx.h (standard knowledge).
- **GetColorMap entry counts** — 32 (OCS/ECS) / 256 (AGA) not stated in the autodoc; standard knowledge.

### RastPort attributes and area fill (rastport-attrs.md, area-fill.md)

- **GetOutlinePen / GetOPen macro** — NDK 3.9 include_h/graphics/gfxmacros.h (39.3) says `#define GetOutlinePen(rp) GetOPen(rp)` but no GetOPen prototype/LVO exists; Bartman sys-include gfxmacros.h says `#define GetOPen(rp) GetOutlinePen(rp)`; resolution: verified with m68k-amiga-elf-gcc (pure NDK 3.9 headers -> implicit declaration of GetOPen; `#undef GetOutlinePen` after gfxmacros.h fixes it); documented as gotcha, LVO name is GetOutlinePen.
- **GetOPen autodoc** — NDK 3.9 autodoc for LVO -876 is filed as GetOPen; SFD/protos/lvo name it GetOutlinePen; resolution: entry uses GetOutlinePen, GetOPen gets a macro entry.
- **GetRPAttrA / SetRPAttrA** — NDK 3.9 autodoc names; SFD, clib protos and lvo/graphics_lib.i use GetRPAttrsA/SetRPAttrsA (varargs GetRPAttrs/SetRPAttrs); resolution: real names used, doc spellings kept as stub entries.
- **RPTAG_SoftStyle** — Get/SetRPAttrA autodocs list RPTAG_SoftStyle; not defined in NDK 3.9 graphics/rpattr.h or rpattr.i (nor Bartman's copies; the gap is value $80000001); resolution: documented as missing, pointed to SetSoftStyle.
- **SetRPAttrsA/GetRPAttrsA version** — autodoc NAME gives no (Vnn); SFD lists them under `==version 39`; resolution: stated V39+ in Gotchas citing the SFD, no "Since" line.
- **InitTmpRas result** — autodoc synopsis `void InitTmpRas(...)`; NDK 3.9 SFD/protos `struct TmpRas *InitTmpRas(...)`; resolution: told readers not to rely on the result.
- **Flood result** — SFD `BOOL Flood`, autodoc calls it "error" without defining values; resolution: documented as undefined meaning.
- **AreaDraw result type** — autodoc `ULONG AreaDraw`, SFD `LONG`; returns 0/-1; resolution: follow SFD (LONG).
- **Negative AreaPtSz (multicolour area pattern)** — not described in NDK 3.9 includes/autodocs; resolution: mentioned with (unverified).
- **AreaPtrn chip RAM** — no source says whether area patterns must be chip RAM; resolution: advice "keep in chip RAM if in doubt" marked (unverified).
- **TmpRas size for area fills** — AreaEnd/InitTmpRas autodocs give no size (only Flood: as large as the RastPort); resolution: "one plane covering the filled area" marked (unverified), full-BitMap RASSIZE recommended.
- **AreaEnd without TmpRas** — behaviour undocumented; resolution: said so, advise attaching one and checking -1.

### Drawing (drawing.md)

- **ReadPixel return type** — NDK 3.9 SFD/clib prototype says `ULONG ReadPixel(...)`; the NDK 3.9 autodoc synopsis says `LONG` and documents -1 on failure; resolution: entry keeps the SFD fact block and tells callers to cast to LONG before testing for -1.
- **DrawEllipse radii wording** — NDK 3.9 autodoc NAME line says "vertical and horizontal radii of a,b respectively"; its INPUTS section says a = horizontal, b = vertical; resolution: followed INPUTS (a horizontal, b vertical), consistent with the prototype's parameter order.
- **ReadPixelArray8/WritePixelArray8 array row layout** — autodoc only gives the buffer size `((((width+15)>>4)<<4)*(ystop-ystart+1))`, not the row stride; resolution: entries state rows are `width` bytes apart and the rounding is working space, marked (unverified). Open item.
- **WritePixelArray8 temprp wording** — autodoc for ReadPixelArray8/ReadPixelLine8 writes `temprp->BytesPerRow`, WritePixelArray8/WritePixelLine8 write `temprp->BitMap BytesPerRow`; BytesPerRow is a BitMap field (gfx.h), resolution: documented as the temp BitMap's BytesPerRow.
- **gfxmacros.h DrawCircle** — the OLD_GRAPHICS_GFXMACROS_H variant appends a `;` to the DrawEllipse expansion, the default variant does not; resolution: documented the default expansion.
- **BltTemplate chip RAM / srcMod parity** — autodoc does not state that the template must be in chip RAM or that srcMod is even; both follow from the blitter reading word-aligned data (standard knowledge); resolution: stated as a requirement for chip RAM and "normally even" for srcMod.
- **Bartman gcc chip data** — `__chip` keyword is not supported by m68k-amiga-elf-gcc (compile error); Bartman's template uses `__attribute__((section(".INCBIN.MEMF_CHIP")))` (template/support/gcc8_c_support.h); resolution: example copies data to AllocMem(MEMF_CHIP) instead.
- **RectFill COMPLEMENT / write-mask advice** — autodoc BUGS only says RectFill COMPLEMENT complements all bitplanes; restricting planes via the write mask is inference from RastPort Mask semantics; resolution: phrased as optional advice.

### Text, fonts, regions, layer locks (text-and-fonts.md, layers-regions-clipping.md)

- **Text / SetFont return type** — NDK 3.9 SFD/clib prototypes return `LONG`; NDK 3.9 and V37 autodocs document `void`; resolution: documented as "do not rely on D0".
- **TextExtent return type** — SFD says `WORD TextExtent(...)`; autodoc synopsis has no result (and misspells it `textExtent`); resolution: entry says use the filled structure only.
- **TextExtent te_Extent.MaxX** — autodoc describes MaxX as "the offset of the left side of the rectangle"; MinX is the left side, so MaxX must be the right edge; resolution: written as right edge.
- **ClearEOL / ClearScreen BgPen** — autodocs say BgPen is used "if the DrawMode is 2"; rastport.h has JAM2 = 1, COMPLEMENT = 2; resolution: entries say BgPen with JAM2, marked (unverified).
- **Text count width** — skeleton prototype `ULONG count`; autodoc register line `D0-0:16` / `WORD`; resolution: only the low 16 bits are used.
- **WeighTAMatch** — public in graphics.library V36-V37 (prb28 V37 page); OpenFont NDK 3.9 autodoc says system PRIVATE as of V39; NDK 3.9 fd lists the slot as `graphicsPrivate6`, no prototype, no `_LVO`; resolution: no-fact entry, no LVO number given.
- **LockLayerRom vs layers LockLayer** — graphics autodoc says layers LockLayer is "identical"; NDK 3.9 layers SFD shows `LockLayer(LONG dummy, struct Layer *layer) (a0,a1)` and `UnlockLayer(layer)(a0)` while the graphics versions take the layer in A5; resolution: described as "same effect", registers differ.
- **Rectangle Max inclusive for regions** — no local source states that Region/RegionRectangle MaxX/MaxY are inclusive (RectFill/EraseRect autodocs do give lower-right corner coordinates); resolution: marked (unverified).
- **InstallClipRegion dispose order** — first written without the layers.library autodoc and marked (unverified); resolved when layers.library was added: its NDK 3.9 autodoc requires `InstallClipRegion(l, NULL)` before DeleteLayer or CloseWindow, and the entry now says so. The SFD confirms it returns `struct Region *` (the previous region).
- **CloseFont then freed memory** — autodoc only says unused fonts stop consuming resources; "remove it from RastPorts first" is a conservative inference.
- **Bartman string.h** — the Bartman sys-include `string.h` declares only memcpy/memmove/memset (no strlen), and CONST_STRPTR is `const unsigned char *`; resolution: C examples compute string lengths by hand (worth a SKILL.md note for C examples).

### Views, viewports, copper lists (views-and-viewports.md, user-copper-lists.md, copper-macros.md)

- **MakeVPort / MrgCop return type** — V37 prb28 autodocs: `void`; NDK 3.9 autodoc + SFD: `ULONG` error (`MVP_*` 0-5, `MCOP_*` 0-2, view.h) from V39; resolution: documented as V39+, test only when lib_Version >= 39.
- **VideoControl return type** — autodoc: `ULONG error` (0 = OK); NDK 3.9 SFD/proto: `BOOL`; resolution: documented "0 = success, test non-zero"; videocontrol.h comment says V39 tags return error -3 on older versions (value not repeated in entry).
- **GfxNew / GfxLookUp return type** — autodoc: `struct ExtendedNode *`; SFD: `APTR`; resolution: SFD kept in fact block, noted in Gotchas.
- **GfxLookUP spelling** — NDK 3.9 autodoc file/heading `GfxLookUP`; NAME line, SFD, LVO include: `GfxLookUp`; resolution: single entry GfxLookUp mentioning the spelling (same anchor, no separate heading).
- **InitVPort synopsis** — autodoc prototype line reads `void InitViewPort(struct ViewPort *)`; SFD/LVO: `InitVPort`; resolution: autodoc typo noted in Gotchas.
- **CINIT autodoc** — calls the function `UCopListInit` and types n as `UWORD`; SFD: `UCopperListInit(struct UCopList *, WORD n)`, proto `LONG n`; resolution: real name used.
- **CMove prototype** — autodoc `void CMove(struct UCopList *, void *, WORD)`; SFD `APTR destination, WORD data`, proto `LONG data`; resolution: fact block from skeleton; data documented as 16-bit.
- **`custom` object** — hardware/custom.h (NDK 3.9 and Bartman) only mentions `extern struct Custom custom;` in a comment, no declaration; Bartman's amiga-debug template/main.c defines `volatile struct Custom *custom` (pointer) set to $DFF000, so the autodoc/macro form `CMOVE(c, custom.color[0], v)` does not compile there; resolution: entries show `(APTR)&custom->color[0]` or a cast address. Whether any gcc lib links a `custom` object at $DFF000 is unverified.
- **Bartman custom.h volatile fields** — Bartman sys-include hardware/custom.h declares register fields `volatile`, NDK 3.9 does not; passing `&custom->color[0]` to CMove without a cast gives -Wdiscarded-qualifiers; resolution: examples cast to APTR (verified with gcc).
- **EXTEND_VSTRUCT for custom Views** — view.h defines `EXTEND_VSTRUCT 0x1000` ("unused bit in Modes field of View") but no local source states MrgCop/LoadView require it with a ViewExtra; resolution: used in example (RKM-style), marked (unverified).
- **VTAG_ATTACH_CM_SET sets vp->ColorMap?** — not stated in autodoc; resolution: example also sets `vp.ColorMap = cm` explicitly, no claim made.
- **User copper list freed by intuition CloseScreen / removal via FreeVPortCopLists+RemakeDisplay** — CINIT autodoc only says FreeVPortCopLists deallocates it; resolution: CloseScreen behaviour and the removal recipe marked (unverified).
- **Two WaitTOF after LoadView** — not in autodoc; confirmed by Bartman's amiga-debug template (TakeSystem/FreeSystem: `LoadView(0); WaitTOF(); WaitTOF();`, restores cop1lc from GfxBase->copinit); resolution: stated as usual practice citing the template.
- **VTAG_DEFSPRITERESN_SET/GET** — present in videocontrol.h/.i ($8000003B/$8000003C) but only mentioned in autodoc NOTES, not in the tag list; resolution: listed in table without version.
- **ScrollVPort speed** — autodoc BUGS: V37 visible hashing, rewritten V39 "~10 times faster"; resolution: kept.
- **VPXB_LAST / VPXF_LAST (C) vs VPXB_VP_LAST / VPXF_VP_LAST (asm)** — private ViewPortExtra flags differ in name between view.h and view.i; resolution: not used in entries.

### GELs, sprites, display database (gels.md, sprites.md, display-database.md)

- **RemBob (asm macro)** — gels.i `RemBob MACRO` expands to `OR.W #BF_BOBSAWAY,b_BobFlags+\1`, but the Bob structure label is `bob_BobFlags`; vasm fails ("illegal relocation"); resolution: documented the direct `or.w #BF_BOBSAWAY,bob_BobFlags(a0)` instead (verified by assembling).
- **AnimOb accelerations (asm)** — gels.h: `WORD YAccel, XAccel;`; gels.i: `ao_XAccel` then `ao_YAccel` (commented "!!! backwards !!!"); resolution: told asm users to lay data out in C order; which order the ROM reads is unverified (assumed C).
- **dBufPacket** — gels.i has an extra `dbp_BufPlanes` field not present in C `struct DBufPacket`; resolution: noted only as asm/C difference, not used in entries.
- **InitGels storage** — autodoc says head/tail are assigned "in GfxBase"; rastport.h shows `GelsInfo.gelHead/gelTail`; resolution: entry says they go into the GelsInfo.
- **collide.h** — comment mentions `BNDRY_HIT` and `GEL_HIT` but only `BORDERHIT` 0 and `TOPHIT`/`BOTTOMHIT`/`LEFTHIT`/`RIGHTHIT` (1/2/4/8) are defined; there is no collide.i; gels.h does not include collide.h; resolution: entries use the defined names and say to include graphics/collide.h.
- **Gel-to-gel collision dispatch** — which routine (lowest common HitMask/MeMask bit?) is called when several bits match is not stated in autodoc/headers; marked unverified.
- **Collision routine calling convention** — stack arguments (C-style) for SetCollision routines is RKM practice, not stated in the NDK 3.9 sources; marked unverified.
- **GelsInfo.sprRsrvd** — header only says "flag of which sprites to reserve from vsprite system"; bit polarity/meaning not further documented; entry quotes the header wording.
- **VSprite SprColors / RINGTRIGGER ring motion** — per-VSprite colour loading and ring translation behaviour come from RKM knowledge, not NDK 3.9 text; marked unverified.
- **VSprite/Bob asm field names** — asm `vs_VSFlags`, `vs_Oldy/vs_Oldx`, `bob_BobFlags`, `ac_CompFlags` vs C `Flags`, `OldY/OldX`; STRUCTURE names `VS`, `BOB`, `AC`, `AO`, `DBP` (label clash risk); resolution: noted in gels.md intro.
- **AllocSpriteDataA V39 attach bug** — autodoc "bit 7 of the second word" (3rd for 32-bit, 5th for 64-bit) does not say which buffer the words are counted in; entry assumes the ExtSprite's posctl data; unverified.
- **ChangeExtSpriteA oldsprite NULL** — example passes NULL for the first image; not documented in the autodoc; unverified.
- **GSTAG_SOFTSPRITE / SPRITEA_OldDataFormat / IGNORE_MCOMPAT** — present in NDK 3.9 headers (sprite.h, coerce.h) but not in the autodocs; described as header-only.
- **FreeSprite then free image** — how many frames until the copper stops using the old image is undocumented; example waits two WaitTOF; unverified.
- **Sprite 0 / Intuition pointer** — "sprite 0 is normally the pointer" is standard knowledge, not in the graphics autodocs.
- **BestModeIDA autodoc typos** — `BIDTAG_Greenits`, `BIDTAG_MustHave`, `DIFP_IS_LACE` in the autodoc; modeid.h has `BIDTAG_GreenBits`, `BIDTAG_DIPFMustHave`, `DIPF_IS_LACE`; resolution: header names used.
- **SPECIAL_FLAGS vs MUST_FLAGS** — modeid.h `SPECIAL_FLAGS`, modeid.i names the same mask `MUST_FLAGS`; documented both.
- **DisplayInfo colour bits (asm)** — displayinfo.i declares `RedBits`/`GreenBits`/`BlueBits` without the `dis_` prefix (all other fields have it); verified by assembling.
- **CloseMonitor** — SFD/protos `BOOL`, NDK 3.9 autodoc `LONG`; TRUE = failure; NDK 3.9 autodoc allows NULL, V37 prb28 page does not mention NULL; resolution: documented both.
- **GetDisplayInfoData displayID** — autodoc shows `[ID]` optional in D2; SFD prototype has 5 required args; resolution: always pass INVALID_ID/ID.
- **ModeNotAvailable** — autodoc ULONG vs SFD LONG; INVALID_ID return for unknown IDs only in the NDK 3.9 autodoc (not in V37 page).
- **MoveSprite BUGS** — NDK 3.9 autodoc limits the one-pixel-left bug to SimpleSprites (not ExtSprites); V37 page has no such restriction.
- **VGA70 monitor names** — monitor.h marks VGA70 definitions obsolete (never implemented); monitor.i has no `*_MONITOR_NAME` strings; resolution: VGA70 not recommended.
- **AGA modes on ECS -> DI_AVAIL_NOCHIPS** — plausible but not stated in sources; marked unverified.

## intuition.library and diskfont.library

Sources compared: NDK 3.9 autodocs (NDK 3.9 autodocs (intuition.doc) , diskfont), clib protos / fact blocks, SFD files, NDK 3.9 C and asm includes, V37 prb28 autodocs, Bartman inline headers.

### screens.md

- **CloseScreen result** — V37 prb28 doc shows `[D0] [BOOL]` optional; NDK 3.9 autodoc: no result before V36, BOOL from V36; proto BOOL; resolution: documented as BOOL (V36+), meaningless on V34.
- **MakeScreen / RethinkDisplay / RemakeDisplay result** — V37 prb28 docs: `VOID`; NDK 3.9 autodoc + proto: `LONG` (0 = success) from V39, garbage before V39; resolution: documented LONG with "invalid before V39".
- **GetScreenData types** — NDK 3.9 autodoc: `BOOL GetScreenData(APTR, UWORD, UWORD, struct Screen *)`; proto/fact block: `LONG ... (APTR, ULONG size, ULONG type, CONST struct Screen *)`; resolution: fact block kept; described as non-zero = success.
- **SA_ErrorCode data type** — OpenScreen autodoc: "points to a ULONG"; screens.h comment: "points to LONG error code"; resolution: `LONG *` (screens.h), values 1-9 are positive either way.
- **OSERR_NOTAVAILABLE** — screens.h defines `OSERR_NOTAVAILABLE (9)`; OpenScreen autodoc lists only codes 1-8; resolution: listed as "screens.h only".
- **SA_Overscan "STDSCREEN"** — OpenScreen autodoc says "Width and Height dimensions STDSCREENWIDTH and STDSCREEN"; no `STDSCREEN` constant exists (screens.h has `STDSCREENHEIGHT`); resolution: autodoc typo, used STDSCREENWIDTH/STDSCREENHEIGHT.
- **GetDefaultPubScreen return** — proto/fact block and autodoc synopsis: `VOID`; autodoc NOTES/BUGS: D0 actually holds the default public Screen pointer (0 if none set); resolution: documented as hidden D0 result, identity comparison only.
- **GetDefaultPubScreen buffer size** — autodoc: buffer of MAXPUBSCREENNAME; NextPubScreen autodoc BUGS + screens.h comment: MAXPUBSCREENNAME+1 needed (NextPubScreen); resolution: recommend +1 for both.
- **LockIBase parameter** — proto names it `dontknow` (ULONG in D0); autodoc: LockNumber, must be 0; resolution: fact block kept, text says pass 0.
- **UnlockIBase register** — proto/SFD: ibLock in A0 (ULONG); autodoc confirms "passed in A0, not D0, for historical reasons"; resolution: noted in entry (no conflict, just a trap).
- **QueryOverscan argument types/registers** — autodoc: `LONG QueryOverscan(ULONG, struct Rectangle *, WORD)`; proto: `LONG oScanType`; displayID travels in A0 (both agree); autodoc BUGS mentions a V36.A17 parameter change; resolution: fact block kept, A0 noted.
- **QueryOverscan OSCAN list** — autodoc says "three types of system overscan values" then lists four (TEXT, STANDARD, MAX, VIDEO); screens.h defines 1-4; resolution: four documented.
- **MoveScreen delta types** — autodoc: `WORD, WORD`; proto: `LONG dx, LONG dy`; resolution: fact block kept (values are small signed pixel deltas).
- **ShowTitle / PubScreenStatus / SetPubScreenModes types** — autodoc: `BOOL ShowIt`, `UWORD StatusFlags`, `UWORD Modes`; proto: `LONG showIt`, `ULONG statusFlags`, `ULONG modes`; resolution: fact blocks kept; only low bits are meaningful.
- **UnlockPubScreen / LockPubScreen name type** — autodoc `UBYTE *`; proto `CONST_STRPTR`; resolution: cosmetic, fact block kept.
- **SA_Draggable before V39** — not stated in any local source what V36-V38 do with V39-only `SA_` tags; example comment "ignored before V39" relies on the general rule that unknown tags are skipped (intuition.h states it for V39 `WA_` tags); resolution: left as is, low risk (unverified for SA_ tags specifically).
- **ChangeScreenBuffer DBufInfo** — intuition autodoc does not say whose `sb_DBufInfo` (new or old ScreenBuffer) is passed to graphics ChangeVPBitMap; resolution: example sets `dbi_SafeMessage.mn_ReplyPort` on every buffer so the message arrives either way (stated in the entry).
- **SA_Exclusive with attached screens** — OpenScreen autodoc: "Starting with V40, attached screens may be SA_Exclusive"; screens.h comment: "Starting with 3.01"; resolution: 3.01 is V40 Kickstart, consistent; not repeated in the table.

### windows.md

- **ActivateWindow result** — V37 prb28 autodoc shows `[D0] [LONG] ActivateWindow()`; NDK 3.9 autodoc and proto declare VOID and BUGS says there never was a meaningful result; resolution: documented as no result.
- **ChangeWindowBox / MoveWindow / SizeWindow argument types** — NDK 3.9 autodoc gives WORD; clib proto (fact block) gives LONG; resolution: fact block kept, values are pixel counts in WORD range.
- **EndRefresh complete** — autodoc BOOL; proto LONG; resolution: fact block kept, documented as TRUE/FALSE.
- **SetMouseQueue queueLength** — autodoc UWORD; proto ULONG; resolution: fact block kept.
- **WindowLimits types** — autodoc WORD/WORD/UWORD/UWORD; proto LONG/LONG/ULONG/ULONG; resolution: fact block kept.
- **ScrollWindowRaster types** — SFD declares WORD dx..yMax; clib proto LONG; window in A1 in both; resolution: fact block kept, A1 called out in the entry.
- **ReportMouse1 alias** — NDK clib proto and pragma declare `ReportMouse1(struct Window *window, LONG flag)` with window in A0 and flag in D0 (pragma `ea 0802`, correct ROM interface); the SFD declares `ReportMouse1(struct Window * flag, BOOL window) (d0,a0)` and the sfdc-generated GCC inline header therefore passes the window in D0 and the flag in A0 (wrong); resolution: entry tells readers to use ReportMouse(flag, window) and avoid ReportMouse1.
- **WA_Flags** — intuition.i comments `WA_Flags ; not implemented at present`; OpenWindow autodoc documents it as the initial Flags value applied before the boolean tags; intuition.h has no such remark; resolution: documented per autodoc.
- **Tag definitions location** — OpenWindow autodoc says TagItems are "defined in intuition/tagitem.h"; the header is utility/tagitem.h; resolution: not repeated.
- **IDCMP_MENUHELP version** — intuition.h/intuition.i comment "new for V36"; ModifyIDCMP autodoc says new for V37 and WA_MenuHelp is "(V37)" (ignored by V36), autodoc also notes MENUHELP availability in V36 is not controllable; resolution: documented as V37.
- **WA_PointerDelay comment** — intuition.h says the delayed change is called off by "NewSetPointer()" (no such function); autodoc says clearing or setting another pointer cancels it; resolution: autodoc wording used.
- **WA_HelpGroup ID source** — intuition.h comment says "Use GetGroupID()"; OpenWindow/HelpControl autodocs say utility.library GetUniqueID(); resolution: GetUniqueID (the function that exists in utility.library).
- **NewWindow Min/Max comment** — intuition.h NewWindow comment says the limits matter only with WFLG_SIZEGADGET and can be changed with "SetWindowLimits()"; the 3.9 autodoc urges always filling them and the function is WindowLimits(); resolution: autodoc advice used.
- **SetPointer chip RAM** — no local source states that SetPointer data must be in chip RAM (standard RKM rule for pre-V39 sprite pointers; V39+ may copy it into a pointer object); resolution: entry recommends chip RAM and marks the V39 behaviour (unverified).
- **IDCMP_IDCMPUPDATE IAddress** — icclass.h only says an "attribute list" is sent with the message; the IAddress-points-to-tag-list statement is standard BOOPSI knowledge; resolution: stated, consistent with icclass.h wording.

### menus.md

- **OnMenu/OffMenu menuNumber** — autodoc and SFD give UWORD; clib proto (fact block) ULONG; resolution: fact block kept.
- **OnMenu/OffMenu NOITEM/NOSUB meaning** — local autodocs only say the packed number selects a sub-item, item or whole menu "as described in the Intuition Reference Manual"; the rule that item field NOITEM means the whole menu and sub field NOSUB means the item is from the RKM; resolution: stated and marked (unverified).
- **ResetMenuStrip enable flag** — autodoc says "change the ITEMENABLED flag to enable/disable some MenuItem or Menu structures"; intuition.h uses MENUENABLED (0x0001) for struct Menu and ITEMENABLED (0x0010) for struct MenuItem; resolution: both flags named per structure.
- **Menu number macros** — MENUNUM/ITEMNUM/SUBNUM/SHIFTxxx in intuition.h do not parenthesize their argument; resolution: gotcha added (pass a plain variable).
- **Multi-select methods** — intuition.h NextSelect comment mentions only drag-select; MENUHELP notes mention extend-select; resolution: "drag-select or extended selection", no mouse-button specifics.

### gadgets.md

- **AddGadget position type** — NDK 3.9 autodoc and SFD say `UWORD position`; clib proto (fact block) says `ULONG position`; resolution: fact block kept, entry says the position is treated as a UWORD (so `(UWORD)~0` appends).
- **AddGList position/numGad types** — autodoc `UWORD, WORD`; proto `ULONG, LONG`; resolution: fact block kept, no behaviour change documented.
- **OnGadget INPUTS wording** — NDK 3.9 autodoc OnGadget INPUTS says "gadget that you want disabled" (copied from OffGadget); resolution: entry says "gadget to enable".
- **RemoveGadget/RemoveGList failure value** — autodoc says -1 is returned but the prototype returns UWORD; resolution: entry documents -1 as `$FFFF` and tells C code to compare with `(UWORD)~0`.
- **RefreshGadgets FUNCTION text** — autodoc says "The Pointer argument points to a Window structure", a leftover sentence with no matching parameter; resolution: ignored.
- **ActivateGadget parameter name** — fact block names the first argument `gadgets`, autodoc names it `Gadget` (one gadget); resolution: fact block kept, bullet explains it is a single gadget.
- **ModifyProp/NewModifyProp types** — autodoc `UWORD` flags/pots/bodies and `WORD NumGad`; proto `ULONG`/`LONG`; resolution: fact block kept; values are 16-bit (MAXPOT/MAXBODY = 0xFFFF).
- **DoGadgetMethodA on pre-V39** — autodoc says it is "same as DoMethod() of amiga.lib" plus GadgetInfo; the entry's advice to use amiga.lib DoMethodA on V36-V38 is inferred, not stated; resolution: kept as advice.

### boopsi.md

- **GadgetMouse prototype** — NDK 3.9 autodoc and V37 prb28 doc synopsis give `VOID GadgetMouse( struct GadgetInfo *, WORD * )` (2 args) while the register line lists Gadget/GInfo/MousePoint in A0/A1/A2; clib proto and SFD have 3 args (gadget=A0, gInfo=A1, mousePoint=A2); resolution: 3-argument fact block.
- **MakeClass instanceSize type** — autodoc and SFD `UWORD`; clib proto `ULONG`; resolution: fact block kept (cl_InstSize is a UWORD in classes.h, so keep sizes < 65536).
- **MakeClass autodoc example** — contains `cl-cl_UserData = ...` (missing `>`); resolution: not reproduced.
- **NewObjectA autodoc file name** — NDK 3.9 split autodoc is filed as `NewObject.txt` (NAME lists NewObjectA and the varargs NewObject); resolution: single `## NewObjectA` entry mentioning `NewObject`.
- **NextObject autodoc example** — uses `DoMethodA( member, msg )` with an undeclared `member` vs `member_object`; resolution: fresh example.
- **amiga.lib availability with Bartman gcc** — Bartman sys-include has `clib/alib_protos.h` (DoMethodA, DoSuperMethodA, HookEntry prototypes) but no linkable amiga.lib was found in the toolchain dir; the NDK `Include/linker_libs/amiga.lib` is hunk format; resolution: stated as (unverified) in MakeClass, asm example performs the superclass call inline (`cl_Super` -> `h_Entry`).
- **propgclass notification attributes** — no local source documents which attributes propgclass sends through ICA_TARGET (PGA_Top assumed, per RKM); resolution: marked (unverified) in NewObjectA.
- **IDCMP_IDCMPUPDATE IAddress** — not documented in intuition.h; NDK example `Examples/DataTypes/Memory/testdt.c` reads the tag list from `IAddress` before ReplyMsg; resolution: used as source.
- **Gadget method task context** — "dispatcher runs on the input task" inferred from SetGadgetAttrsA BUGS ("calls that Intuition's input task makes to the gadgets"); resolution: stated as gotcha.

### drawing.md

- **Image data in chip RAM** — no local source (NDK 3.9 autodocs, includes, prb28) states that `Image.ImageData` must be chip RAM; RKM Libraries rule from background knowledge; resolution: stated with (unverified).
- **DrawImageState/EraseImage INPUTS** — autodoc lists "LeftOffset,RightOffset" but the second offset is the top offset (D1, `topOffset` in proto); resolution: named leftOffset/topOffset.
- **PointInImage** — autodoc says the box test uses "LeftEdge/RightEdge/Width/Height" (means TopEdge) and passes `struct Point` by value; proto/fact block takes `ULONG point` in D0; resolution: entry documents manual packing `(x << 16) | y`.
- **DrawBorder/DrawImage/EraseImage/PrintIText offsets** — autodoc and SFD `WORD`; clib proto `LONG`; resolution: fact block kept.
- **IntuiText position semantics** — "top-left of text, not baseline" not stated in local sources; resolution: marked (unverified) in PrintIText.
- **PrintIText and disk fonts** — only OpenScreen autodoc says Intuition never calls OpenDiskFont; applied to ITextFont by analogy; resolution: marked (unverified).
- **IDS_SELECTEDDISABLED** — present in imageclass.h (value 8) but absent from the DrawImageState autodoc list; resolution: listed from the header.

### requesters-and-alerts.md, input-and-prefs.md, concepts.md, index.md, diskfont/

- **DisplayAlert height type** — V37 prb28 doc `WORD`; NDK 3.9 autodoc and SFD `UWORD`; clib proto (fact block) `ULONG`; resolution: fact block kept, documented as a line count. TimedDisplayAlert has the same UWORD/ULONG split.
- **AutoRequest / BuildSysRequest width, height** — autodoc `WORD`; proto `ULONG`; resolution: fact block kept. Both are ignored from V36 anyway.
- **BuildSysRequest result on failure** — FUNCTION text says V36 always returns FALSE when it cannot post; RESULT text still describes the pre-V36 DisplayAlert fallback returning TRUE/FALSE; resolution: documented as FALSE on V36+, TRUE/FALSE from the alert on older versions.
- **BuildEasyRequestArgs failure** — RESULT says a recoverable alert "may be substituted"; BUGS says "Does not put up alternative alert"; resolution: no fallback alert is documented, and the 0/1 return values are kept.
- **SysReqHandler** — RESULT text refers to "UDCMP_ptr" (typo for IDCMPFlagsPtr); autodoc `BOOL WaitInput` vs proto `LONG waitInput`; resolution: proto names used.
- **EasyStruct size label (asm)** — intuition.h uses `sizeof(struct EasyStruct)`; intuition.i label is `EasyStruct_SIZEOF` (renamed from `es_SIZEOF` because of a clash with graphics ExtSprite); resolution: asm example uses `EasyStruct_SIZEOF`.
- **Bartman inline varargs guards** — `inline/intuition.h` guards EasyRequest/BuildEasyRequest with `NO_INLINE_VARARGS` but the tag-list macros (OpenWindowTags, NewObject, ...) with `NO_INLINE_STDARG`; the EasyRequest macro needs at least one variadic argument; resolution: documented in concepts.md and the EasyRequestArgs entry.
- **DisplayAlert string layout in asm** — the autodoc gives the byte layout (16-bit X, 8-bit Y, text, NUL, continuation byte). Advice to write X as two `dc.b` because a Devpac-compatible assembler may auto-align `dc.w` is from background knowledge about assemblers (unverified for vasm defaults); resolution: kept, since the `dc.b` form is correct either way.
- **TimedDisplayAlert time unit** — autodoc says "number of video frames"; the 50/s PAL and 60/s NTSC rates are background knowledge; resolution: stated.
- **GetPrefs / GetDefPrefs size** — autodoc and SFD `WORD`; proto `LONG`; resolution: fact block kept.
- **SetPrefs / FreeRemember BOOL arguments** — autodoc `BOOL Inform` / `BOOL ReallyForget`; proto `LONG`; resolution: fact block kept, TRUE/FALSE documented.
- **OpenIntuition / Intuition** — no autodoc; clib/intuition_protos.h says "Public functions OpenIntuition() and Intuition() are intentionally not documented"; SFD has `VOID OpenIntuition() ()` and `VOID Intuition(struct InputEvent * iEvent) (a0)`; resolution: short "internal, never call" entries. That Intuition() is Intuition's input-event entry is (unverified).
- **FreeRemember key reset** — the autodoc does not say whether FreeRemember sets `*rememberKey` to NULL; resolution: not claimed.
- **IDCMP_IDCMPUPDATE tag list lifetime** — no local source says whether the `IAddress` tag list stays valid after ReplyMsg; resolution: concepts.md says to read it before replying and marks its validity afterwards (unverified).
- **Unknown tags ignored by older Intuition** — only stated by intuition.h comments for specific tags ("ignored by V36", "ignored by V37 and earlier"); resolution: generalised in concepts.md (low risk).
- **V33 function group** — the autodocs give no version for AddGList, RemoveGList, RefreshGList, NewModifyProp, ActivateWindow, ActivateGadget, RefreshWindowFrame or GetScreenData; the SFD `==version 33` marker precedes exactly these; resolution: listed as V33 in the index.md version table only (no "Since" lines).
- **AvailFonts buffer / flags types** — NDK 3.9 autodoc `struct AvailFontsHeader *buffer`, `ULONG flags`, and its synopsis is missing a comma after `bufBytes` (the V37 prb28 copy has it); SFD/proto `STRPTR buffer`, `LONG flags`; resolution: fact block kept, entry says to cast the buffer.
- **NewScaledDiskFont types** — autodoc returns `struct DiskFontHeader *` and takes `struct TTextAttr *`; SFD/proto return `struct DiskFont *` (a struct defined nowhere in the NDK 3.9 includes) and take `struct TextAttr *`; resolution: fact block kept, entry says the result is a DiskFontHeader (cast it).
- **NewScaledDiskFont freeing** — autodoc: StripFont() the font, then UnLoadSeg() "the segment" (in DiskFontHeader); `dfh_Segment` is declared `LONG` with comment "the segment address when loaded"; using it directly as the BPTR for UnLoadSeg is (unverified).
- **DFCTRL_SYMSET value** — diskfont/diskfonttag.h defines both `DFCTRL_YDOTP` and `DFCTRL_SYMSET` as `DFCTRL_BASE + 4`; the autodocs list them as separate tags; resolution: gotcha that they collide. No asm `DFCTRL_` equates exist in include_i/diskfont/diskfonttag.i.
- **Get/SetDiskFontCtrl version** — autodoc NAME lines and clib/diskfont_protos.h say V45; diskfont_lib.sfd lists them after `==version 36` with no later marker; resolution: V45.
- **SetDiskFontCtrlA naming** — autodoc NAME line is "SetDiskFontCtrl" (the file is SetDiskFontCtrlA.txt); GetDiskFontCtrl autodoc prototype names the argument `tagitem`, SYNOPSIS/proto say `tagid`; resolution: proto names.
- **NewFontContents / DisposeFontContents** — autodoc `char *fontName`; proto `STRPTR`; DisposeFontContents takes its argument in A1 (all sources agree); resolution: A1 called out in the entry and index.
- **diskfont background facts** — "diskfont.library is disk-based (LIBS:), not in ROM", "TTextAttr is V36+", "OpenDiskFont/AvailFonts need a process because they do DOS I/O" are standard knowledge not stated in the local autodocs; resolution: stated without the unverified mark. The DOS-in-VERIFY warning follows the ModifyIDCMP autodoc.
- **AllocRemember / FreeRemember with Bartman gcc 15** — `inline/macros.h` LPn macros declare `register volatile t1 _n1 = _v1;`. For t1 = `struct Remember **` this becomes `volatile struct Remember **`, and GCC 15 rejects the initialisation as incompatible-pointer-types (an error by default; verified by compiling a snippet). The same macro pattern affects other `**` parameters (inline/exec.h LVO -852/-858/-864, inline/graphics.h LVO -156/-162; the exec AVL and graphics entries carry the same gotcha). Resolution: gotcha in both entries (`-Wno-error=incompatible-pointer-types` or avoid the calls).

## utility.library and layers.library

Sources compared: NDK 3.9 autodocs (split per function), NDK 3.9 include_h/include_i/SFD, Bartman
amiga-debug 1.8.2 sys-include (clib/inline/proto/lvo) and project template, and as a later
cross-check only the NDK 3.2R4 autodocs and release notes. No V37 prb28 pages exist for these two
libraries. Structure offsets were verified with gcc `offsetof` and vasm `printv`. Items marked
"unverified" in the reference files are listed as open items.

### utility.library

- **SMult64/UMult64 result registers** — NDK 3.9 autodoc: result `D0:D1`, no statement which half is
  where; NDK 3.2R4 utility-RelNotes (release 45.1, AmigaOS 3.1.4): "the 68000 version now returns the
  results in proper order, low 32 bits in d0 and high 32 bits in d1", implying older 68000 builds
  returned them swapped; resolution: entries document low=D0/high=D1, warn about old 68000 builds and
  show a runtime order check. Which V39/V40 ROMs are affected: open item.
- **SMult64/UMult64/SDivMod32/UDivMod32 C prototypes** — SFD/clib return a single LONG/ULONG; the
  second half (D1) is unreachable through the inline macros; resolution: math.md says so and
  recommends C operators (template supplies `__mulsi3`, `__divsi3`, `__udivsi3`, `__modsi3`,
  `__umodsi3`).
- **Math routines on 68020+** — whether utility.library uses native 32/64-bit instructions on
  68020+ is not stated in the NDK 3.9 docs (NDK 3.2 notes mention a retired 68020-only build and
  060 variants); resolution: marked unverified. Division by zero behaviour undocumented.
- **ToUpper/ToLower argument type** — autodoc and SFD: `UBYTE ToUpper(UBYTE)`; clib (fact block):
  `ULONG character`; Bartman inline: UBYTE; resolution: fact block kept, entries say only the low
  byte matters for argument and result.
- **ToUpper SEE ALSO** — autodoc lists `ToUpper(), locale.library/ConvToLower()` (copied from
  ToLower); resolution: entry links ToLower and locale ConvToUpper (exists in locale_lib.sfd).
- **PackBoolTags autodoc example** — says the result from initial 0x800002 is `0x80005`; worked out it
  is 0x800005 (also the comment ends with `/*`); resolution: typo noted in the entry.
- **FilterTagItems autodoc** — FUNCTION text calls the array `tagArray`, INPUTS/SFD call it
  `filterArray`; resolution: `filterArray` used.
- **Control-tag handling of FindTagItem/GetTagData/PackBoolTags/Filter/Map/Apply** — only NextTagItem's
  autodoc states TAG_MORE/TAG_IGNORE/TAG_SKIP handling; the others imply it (CloneTagItems/
  PackStructureTags wording); resolution: stated once in tags.md intro, marked unverified.
- **AllocateTagItems** — autodoc does not say whether slots are zeroed or whether `numTags` includes
  the terminator, and warns the library may insert TAG_MORE/TAG_IGNORE; resolution: entry advises
  counting the TAG_DONE slot and writing it explicitly (unverified).
- **FindNamedObject case sensitivity** — autodoc: comparison is always caseless via locale;
  utility/name.h: `NSF_CASE` "Name space is case sensitive"; resolution: both stated, open item.
- **AllocNamedObjectA name ownership** — autodoc does not say whether the name string is copied
  (NamedObjectName says the name goes away with the object); resolution: entry advises keeping the
  string valid (unverified).
- **AttemptRemNamedObject FALSE result** — autodoc does not say whether the caller's use count is
  consumed on failure; resolution: marked unverified. Example assumes the allocation's initial use
  counts as the "found" use required by the autodoc.
- **ClockData ranges** — neither utility/date.h/.i (NDK 3.9 or 3.2) nor the autodocs give field ranges;
  resolution: usual convention (month 1-12, wday 0-6 with 0 = Sunday, full year) marked unverified.
- **utility/date.i labels** — the structure uses unprefixed labels `sec`, `min`, `hour`, `mday`,
  `month`, `year`, `wday` (plus `CD_SIZE`), which can clash with program symbols; noted in dates.md.
- **utility/pack.i** — asm include only has `PSTB_/PSTF_` bits; the `PKCTRL_*` values and `PACK_*`
  macros exist only in pack.h; noted in tags.md.
- **Bartman GCC 15 and hooks** — gcc 15 defaults to C23, so `ULONG (*h_Entry)()` in utility/hooks.h
  means `(void)`: assigning a function with parameters without a cast and calling
  `hook->h_SubEntry(a,b,c)` are compile errors (verified). `(HOOKFUNC)(void (*)(void))fn` compiles
  clean with -Wextra.
- **NextTagItem inline macro** — GCC 15 error `initialization of 'volatile struct TagItem **'`
  (verified, also with an explicit cast); workarounds verified: a typedef'd `LP1(0x30, ...)` macro, or
  `#pragma GCC diagnostic ignored "-Wincompatible-pointer-types"`.

### layers.library

- **SortLayerCR** — no autodoc in NDK 3.9; SFD: `(struct Layer *, WORD dx, WORD dy)` (a0,d0,d1) under
  `==version 39`; clib/fact block: LONG dx, dy; NDK 3.2R4 autodoc: V39, "for scroll raster",
  "Layers/Graphics internal use only", layer must be locked; resolution: entry from the includes with
  the Source line, NDK 3.2 wording cited as a later source.
- **MoveSizeLayer autodoc INPUTS** — lists `dummy`, `l` and "dw,dy" while SYNOPSIS/SFD are
  `(layer, dx, dy, dw, dh)` (a0,d0-d3); resolution: SFD, noted in the entry.
- **EndUpdate flag type** — autodoc and SFD: `UWORD`; clib (fact block): `ULONG`; resolution: fact block
  kept; pass 0/1.
- **WhichLayer x, y type** — autodoc and SFD: `WORD`; clib (fact block): `LONG`; resolution: entry says
  pass sign-extended longs.
- **Create*Layer autodoc prototypes** — declare the SuperBitMap as a trailing `...` ("[,bm2]"); SFD
  requires `bm2` in A2 always; resolution: always pass NULL or a BitMap.
- **DisposeLayerInfo autodoc example** — calls `DeleteLayer(li, layer)`, passing the Layer_Info as the
  unused dummy; harmless, entries pass 0.
- **clip.i vs clip.h names** — asm `lr_SuperSaverClipRects` vs C `SuperSaveClipRects`; asm `cr_SIZEOF`
  = 40 includes `cr_Flags`, C `struct ClipRect` is 36 bytes unless `NEWCLIPRECTS_1_1`; layers.i has
  `ALERTLAYERSNOMEM` $83010000 not present in layers.h; the first two are noted in concepts.md.
- **Graphics errata item "InstallClipRegion dispose order"** — the layers autodoc IS now in the source
  set: InstallClipRegion requires `InstallClipRegion(l, NULL)` before DeleteLayer / Intuition
  CloseWindow. Uninstalling before DisposeRegion remains standard practice only. Resolution:
  graphics/layers-regions-clipping.md and the graphics errata line were updated to match.
- **Clip region / DoHookClipRects rectangle coordinates** — autodocs do not say whether they are
  layer-relative; resolution: layer-relative stated as unverified.
- **Backfill hook bounds** — autodoc text does not state the coordinate space; its asm example uses
  `ra_MinX..` directly with BltBitMap on `rp_BitMap(a2)`, i.e. BitMap coordinates; resolution: stated
  from the example.
- **Layer.Window field** — clip.h: "reserved for user interface use"; that Intuition stores the owning
  Window there is common knowledge, unverified.
- **WFLG_* refresh flags -> LAYER* types**, **LAYERUPDATING / LAYERIREFRESH / LAYERIREFRESH2 meaning**,
  **whether a newly created layer is backfilled** — not documented in the NDK 3.9 sources; marked
  unverified.
- **LockIBase vs layer locks** — intuition LockIBase autodoc forbids LockIBase while holding layer or
  LayerInfo locks AND forbids layers calls while holding the IBase lock; locking.md follows it.

## lowlevel.library, input.device, cia.resource and potgo.resource

### Prototype / type mismatches (autodoc vs SFD vs clib)

- **SetJoyPortAttrs varargs synopsis** — autodoc: `BOOL SetJoyPortAttrs(Tag, ...)` (no port); SFD/clib: `SetJoyPortAttrs(ULONG portNumber, Tag, ...)`; resolution: documented with the port argument (Bartman inline macro also takes it).
- **QueryKeys arraySize** — autodoc and SFD: `UBYTE`; clib/fact block: `ULONG`; Bartman inline passes UBYTE; resolution: fact block kept, entry says at most 255 entries.
- **StartTimerInt continuous** — autodoc and SFD: `BOOL`; clib/fact block: `LONG`; resolution: fact block kept, entry says pass 0/1 in D1.
- **GetLanguageSelection result** — autodoc SYNOPSIS: `ULONG`; SFD/clib: `UBYTE`; resolution: UBYTE, test the low byte only.
- **cia.resource iCRBit / mask** — autodoc and SFD: `WORD`; clib/fact block: `LONG`; resolution: fact block kept.
- **potgo.resource bits / word / mask** — autodoc and SFD: `UWORD`; clib/fact block: `ULONG`; result of AllocPotBits is UWORD everywhere.

### Autodoc text errors

- **AddTimerInt** — FUNCTION text says `StartIntTimer()`; the function is StartTimerInt; resolution: noted in the entry.
- **AddKBInt INPUTS** — describes intRoutine as "the routine to invoke every vblank" (copied from AddVBlankInt); resolution: documented as the keyboard routine.
- **SetJoyPortAttrsA SJA_Type** — says the default type is `SJA_AUTOSENSE`; lowlevel.h defines `SJA_TYPE_AUTOSENSE` (0); resolution: include name.
- **GetKey** — NAME says "currently pressed" key, RESULT says "last non-qualifier key pressed" and "FF" when none; resolution: documented as the last key pressed, low word $00FF = none (whether a released key still reports is unverified).
- **SystemControlA SCON_KillReq** — the headings "reasons for NOT disabling system requesters" / "When requesters should not be disabled" introduce lists that actually describe when disabling is safe; resolution: documented as the safe conditions.
- **ElapsedTime range** — autodoc says the 16-bit whole-seconds part covers "about 16 hours"; 65535 s is about 18.2 hours. The autodoc gives the resolution as "approximately 20 microseconds", while one step of the 16-bit fraction is 15.26 us; resolution: both quoted.
- **IND_SETMTRIG** — `gpt_YDelta` described as "a distance in x"; io_Length written `sizeof(gameportTrigger)`; the include struct is `struct GamePortTrigger` (8 bytes); `gpt_Timeout` "(60/sec)" while the include says vertical-blank units (50/s on PAL); resolution: Y axis, include struct name, vertical blanks.
- **potgo AllocPotBits** — text says "FreePotgoBits"; the function is FreePotBits.
- **IND_WRITEEVENT** — V34-and-earlier docs allowed chaining via ie_NextEvent; the 3.9 autodoc states it never worked; resolution: one event per request.

### Include oddities

- **resources/cia.h guard** — the C header guard is `DEVICES_CIA_H` and cia.i uses `DEVICES_CIA_I` although the files live in `resources/`; `resources/ciabase.i` uses `RESOURCES_CIA_I`. Harmless, noted only here.
- **IECLASS_ANSI** — inputevent.h/.i have a comment block of `IECODE_C0_*`..`IECODE_LATIN1_*` codes "for IECLASS_ANSI" but define no `IECLASS_ANSI`; `IECLASS` value $05 is not defined either.
- **SCON_TakeOverSys = SCON_Dummy** — `SCON_TakeOverSys` is `SCON_Dummy+0` ($80C00000); fine as a tag, but it equals the dummy base.
- **SCON_AddCreateKeys raw key codes** — `RAWKEY_PORT0_*` are $72-$7C, overlapping `IECODE_COMM_CODE_FIRST..LAST` ($78-$7F); port 1-3 codes are $172.. $37C (above a byte); the include defines PORT2/PORT3 codes although the tag accepts only units 0 and 1.
- **KeyQuery** — C `BOOL kq_Pressed` (16-bit short) vs asm `UWORD kq_Pressed`: same size (KeyQuery_SIZEOF 4, verified with vasm and GCC).
- **POTGO bits** — no NDK constants exist for START/DATxx/OUTxx (hardware/custom.h only has the `potgo` field); names come from the potgo.resource autodoc and HRM table 8-4.

### HRM (OCR) notes

- **CIA-B serial register** — HRM Appendix F address map calls CIA-B `sdr` "unused", while the pin list shows CIA-B `SP..BUSY` and `CNT..POUT` (parallel port lines); resolution: both stated (register unused by the OS, pins shared with parallel BUSY/POUT).
- **CIA-B FLAG** — the Appendix F pin list is truncated by OCR for CIA-B; chapter 8 states the disk INDEX pulse is the 8520 FLAG input at level 6, i.e. CIA-B; CIA-A FLAG = `ack*` (parallel).

### Unverified claims (open items)

- Intuition's input handler priority is 50 (not in the NDK 3.9 autodocs/includes).
- Input handlers run on input.device's task (not in an interrupt) and must preserve D2-D7/A2-A6.
- Which CIA timers the OS owns: entries say CIA-A timers are used by the system and CIA-B timers are usually free; CIA-A TOD alarm used by OS timekeeping, CIA-B TOD by graphics. The local sources only say timer.device UNIT_MICROHZ uses "the 8520 timers".
- cia.resource handler registers (A1 = is_Data, exec-server scratch set) and that the resource reads/acknowledges the ICR itself.
- lowlevel.library is disk-based (LIBS:) on computers and in ROM on the CD32.
- AddKBInt routine is also called for key releases (codes with bit 7 set).
- The V40 lowlevel.library cannot read a CD32 pad in port 0 (claimed only by the third-party V45 release notes in the NDK).
- `SCON_AddCreateKeys` codes reach windows as IDCMP_RAWKEY.
- IND_SETMTYPE `GPCT_NOCONTROLLER` makes input.device release the mouse port.
- input.device holds the potgo bits of the mouse port's right button.
- CD32 pad serial protocol summary (pin 5 low = shift mode, pin 6 clock via CIA-A DDRA, data on pin 9 through POTINP).
- potgo.resource allocations are not released when the allocating task exits.

## timer.device and audio.device

### timer.device

- **TR_SETSYSTIME request table** — the NDK 3.9 autodoc's TIMER REQUEST block for TR_SETSYSTIME lists `io_Command TR_GETSYSTIME`; devices/timer.h defines `TR_SETSYSTIME` = `CMD_NONSTD+2` (11); resolution: the entry uses TR_SETSYSTIME (11) and notes the typo.
- **AbortIO result** — timer autodoc: `LONG AbortIO(struct timerequest *)`, D0 = 0 if aborted (io_Error = IOERR_ABORTED), -1 otherwise; NDK 3.9 exec autodoc, clib and SFD: `VOID AbortIO(struct IORequest *)` (Bartman inline is LP1NR); resolution: the D0 result is documented for asm; C code tests io_Error after WaitIO.
- **CmpTime sign** — 3.9 autodoc: -1 when dest has more time than src, +1 when less; its BUGS section says older documents had the sense reversed (the code never changed); resolution: follow the 3.9 autodoc and flag the inversion in index.md and the entry.
- **TR_ADDREQUEST tr_time on return** — autodoc: zeroed; NOTES: before 2.0 documented as junk; resolution: "zeroed from 2.0, reload before every send".
- **TR_ADDREQUEST SEE ALSO `timer.device/TimeDelay()`** — no TimeDelay in timer_lib.sfd / clib/timer_protos.h (it is presumably an amiga.lib function, unverified); resolution: not referenced.
- **Unit versions** — `--background--` describes all five units without versions; resolution: `UNIT_ECLOCK`, `UNIT_WAITUNTIL`, `UNIT_WAITECLOCK` stated as V36 (unverified). AddTime/SubTime/CmpTime and the three commands stated as 1.x (unverified). GetSysTime and ReadEClock are V36 per their autodocs.
- **UNIT_VBLANK time source** — autodoc: power-supply strobe, or the E-clock on machines without one, resolution one vertical blank; resolution: documented as a stable 50/60 Hz base that is NOT display-synchronous (use WaitTOF for display sync).
- **E-clock frequency values** — not in the timer autodoc; HRM appendix F (8520 table) gives 0.709379 MHz PAL / 0.715909 MHz NTSC; resolution: quoted from the HRM with "use ReadEClock's return value".
- **System time epoch** — autodocs only say system time starts at 0 at power-on unless set; 1-Jan-1978 comes from utility Amiga2Date/Date2Amiga; that boot code sets it from the battery clock in those units is unverified; resolution: marked (unverified).
- **TR_GETSYSTIME unit** — autodoc names no unit; "any opened unit works" marked (unverified).
- **Parallel timers by copying a request** (`*tr2 = *tr1`) — common practice, not stated in the timer autodocs; marked (unverified). (The audio autodocs do explicitly allow copying io_Device/ioa_AllocKey.)
- **TR_SETSYSTIME and the battery clock** — that it does not write the battery-backed clock is not in the local sources; marked (unverified).
- **Bartman sys-include devices/timer.h differs from NDK 3.9** — Bartman's `struct timeval` wraps `tv_secs`/`tv_micro` in anonymous unions with `tv_sec`/`tv_usec` (guard `_TIMEVAL_DEFINED`); consequence verified by compile: `struct timeval t = { 1, 0 };` warns `-Wmissing-braces` under -Wall; resolution: docs use tv_secs/tv_micro assigned by name.
- **64-bit maths in Bartman builds** — verified by linking against the amiga-debug template (`-nostdlib`, support/gcc8_a_support.s provides only __mulsi3/__udivsi3/__divsi3/__modsi3/__umodsi3): `unsigned long long` multiply/divide leaves `__muldi3` and `__udivdi3` undefined; resolution: recipes use 32-bit arithmetic only.
- **lvo/timer_lib.i** — not present in `NDK_3.9/Include/include_i/lvo/`, but present in Bartman's `sys-include/lvo/timer_lib.i` (_LVOAddTime -42 ... _LVOGetSysTime -66, matching the SFD); resolution: docs say `include "lvo/timer_lib.i"` (assembled OK with vasm against Bartman's sys-include).

### audio.device

- **ADCMD_ALLOCATE error/flag names** — autodoc FUNCTION text says `IOERR_ALLOCFAILED` and "IOERR_NOALLOCATION", and INPUTS mention `ADIOF_QUICK`; devices/audio.h has `ADIOERR_ALLOCFAILED` (-11), `ADIOERR_NOALLOCATION` (-10) and no ADIOF_QUICK (exec `IOF_QUICK` = 1); resolution: include names used, typo noted in the entry.
- **ADCMD_WAITCYCLE command name** — autodoc INPUTS: "command number for CMD_WAITCYCLE"; include: `ADCMD_WAITCYCLE` = CMD_NONSTD+5 (14); resolution: include name.
- **CMD_START typo** — autodoc text says "CMP_START"; resolution: CMD_START (7).
- **Period range** — CMD_WRITE/ADCMD_PERVOL autodocs: 124 thru 65536; `ioa_Period` is UWORD (max 65535); HRM ch.5: minimum 124 NTSC, 123 PAL; resolution: 124..65535.
- **ADCMD_ALLOCATE value** — `ADCMD_ALLOCATE` is 32, not CMD_NONSTD-based (the other ADCMD_ are 9..14); verified with gcc `_Static_assert` and vasm.
- **IOAudio offsets** — verified with gcc offsetof and vasm (audio.i): ioa_AllocKey $20, ioa_Data $22, ioa_Length $26, ioa_Period $2A, ioa_Volume $2C, ioa_Cycles $2E, ioa_WriteMsg $30, ioa_SIZEOF $44; `sizeof(struct timerequest)` $28.
- **AUDIONAME asm macro** — audio.i `AUDIONAME` emits the string without `DS.W 0` (timer.i TIMERNAME has it); vasm warns "instruction has been auto-aligned" when code follows; resolution: example adds `even`.
- **Stereo side of channels** — HRM ch.5: channels 1/2 left, 0/3 right; common tracker convention: 0/3 left; resolution: masks documented by pairs (0/3 vs 1/2) with the dispute stated, pointing to the amiga-hardware skill.
- **Precedence guideline table** (127 unstealable ... -128 silence) — from RKM Devices, not in the local sources; marked (unverified).
- **ADCMD_FINISH details** — autodoc does not give the io_Error of the finished write or say whether queued writes start next; marked (unverified).
- **CMD_FLUSH aborted requests' io_Error** — autodoc says "aborts"; that the value is IOERR_ABORTED is assumed from CMD_WRITE's AbortIO wording; marked (unverified).
- **ADCMD_LOCK after ADIOERR_CHANNELSTOLEN** — ALLOCATE replies the lock with CHANNELSTOLEN; FREE replies the lock "if it has no channel bits set"; whether the device avoids a second reply after a steal notice is not stated; resolution: example collects the lock once, after ADCMD_FREE (unverified edge case).
- **OpenDevice failure** — audio autodoc: io_Device = -1 on failure and the device is closed again when allocation fails; resolution: "do not send commands or CloseDevice on that request".
- **REALLY_PAL for the audio clock** — gfxbase.h: `REALLY_PAL` (V39) = actual crystal frequency vs boot-menu mode; HRM: clock constant derives from the system clock; recommending REALLY_PAL on V39+ is an inference (unverified on hardware).
- **Versions** — the audio autodocs state no versions (audio.h 36.3); "all commands are the original 1.x set" marked (unverified).
