# dos.library: processes and the CLI

A Process is an exec Task followed by a `pr_MsgPort` and DOS state (current dir `pr_CurrentDir`,
I/O handles `pr_CIS`/`pr_COS`/`pr_CES`, IoErr value `pr_Result2`, `pr_CLI`, `pr_WindowPtr`,
`pr_HomeDir`, local variables) -- `struct Process` in `dos/dosextens.h`, node type `NT_PROCESS` (13).
Only processes may call DOS I/O; a plain task must start a process to do it
([processes vs tasks](concepts.md#processes-vs-tasks)). Shell-started programs also own a
`CommandLineInterface` (Cli() non-NULL); Workbench-started programs have none and get a WBStartup
message instead. CreateNewProc() starts code in memory as a new process, SystemTagList() and
Execute() run command lines through a shell, RunCommand() runs a loaded seglist on YOUR process.

## CreateNewProc
`struct Process * CreateNewProc(CONST struct TagItem *tags)` — LVO -498 (-$1F2)
Registers: tags=D1; result in D0

Create a new DOS process from a seglist or an entry point, configured by tags.

- **tags** — TagItem array ending in `TAG_END`. Exactly one of `NP_Seglist` / `NP_Entry` is
  required; everything else is optional (`dos/dostags.h`, `NP_Dummy` = `TAG_USER`+1000):

| Tag | Value | Data | Default |
|---|---|---|---|
| `NP_Seglist` | `$800003E9` | BPTR seglist (from LoadSeg) | -- |
| `NP_FreeSeglist` | `$800003EA` | BOOL: UnLoadSeg it at exit (NP_Seglist only) | TRUE |
| `NP_Entry` | `$800003EB` | APTR code to run (not with NP_Seglist) | -- |
| `NP_Input` | `$800003EC` | BPTR file handle | `Open("NIL:")` |
| `NP_Output` | `$800003ED` | BPTR file handle | `Open("NIL:")` |
| `NP_CloseInput` | `$800003EE` | BOOL: Close input at exit | TRUE |
| `NP_CloseOutput` | `$800003EF` | BOOL: Close output at exit | TRUE |
| `NP_Error` | `$800003F0` | BPTR error handle (`pr_CES`) | `Open("NIL:")` |
| `NP_CloseError` | `$800003F1` | BOOL: Close error handle at exit | TRUE |
| `NP_CurrentDir` | `$800003F2` | BPTR lock | copy of parent's current dir |
| `NP_StackSize` | `$800003F3` | stack in bytes | 4000 |
| `NP_Name` | `$800003F4` | STRPTR process name | "New Process" |
| `NP_Priority` | `$800003F5` | LONG -128..127 | parent's |
| `NP_ConsoleTask` | `$800003F6` | struct MsgPort * | parent's |
| `NP_WindowPtr` | `$800003F7` | struct Window * for requesters; -1 = none | parent's |
| `NP_HomeDir` | `$800003F8` | BPTR lock used for PROGDIR: | parent's home dir |
| `NP_CopyVars` | `$800003F9` | BOOL: copy local shell variables | TRUE |
| `NP_Cli` | `$800003FA` | BOOL: give it a CLI structure | FALSE |
| `NP_Path` | `$800003FB` | BPTR path list (CLI processes only) | copy of parent's path |
| `NP_CommandName` | `$800003FC` | STRPTR command name (CLI only) | -- |
| `NP_Arguments` | `$800003FD` | STRPTR args, copied; child gets string in A0, length in D0 | empty |
| `NP_NotifyOnDeath` | `$800003FE` | BOOL -- not functional | FALSE |
| `NP_Synchronous` | `$800003FF` | BOOL -- not functional | FALSE |
| `NP_ExitCode` | `$80000400` | function called when the process exits | -- |
| `NP_ExitData` | `$80000401` | LONG argument for NP_ExitCode | NULL |

  `ADO_DirLen`, `ADO_CommNameLen`, `ADO_CommFileLen`, `ADO_PromptLen` (buffer sizes of the CLI
  strings, see [AllocDosObject](objects.md#allocdosobject)) are also accepted.
- **Result** — `struct Process *` (a real Process, not its port), or NULL.

`CreateNewProcTagList` is the same LVO; `CreateNewProcTags(tag, data, ..., TAG_END)` is the varargs
form (amiga.lib / Bartman inline). `pr_Flags` bits `PRF_FREESEGLIST` (1), `PRF_FREECURRDIR` (2),
`PRF_FREECLI` (4), `PRF_CLOSEINPUT` (8), `PRF_CLOSEOUTPUT` (16), `PRF_FREEARGS` (32) record what the
system releases when the process ends.

Since V36.

### Example
```c
#include <proto/exec.h>
#include <proto/dos.h>
#include <dos/dostags.h>
#include <utility/tagitem.h>

static struct Task *parent;
static ULONG doneMask;

static void worker(void)            /* runs as its own process */
{
    PutStr("worker running\n");     /* goes to NP_Output */
    Delay(50);
    Forbid();                       /* stay atomic until this process is gone */
    Signal(parent, doneMask);
}                                   /* returning ends the process */

int main(void)
{
    struct Process *pr;
    LONG bit = AllocSignal(-1);

    if (bit == -1) return RETURN_FAIL;
    parent   = FindTask(NULL);
    doneMask = 1UL << bit;

    pr = CreateNewProcTags(NP_Entry,       (ULONG)worker,
                           NP_Name,        (ULONG)"myprog worker",
                           NP_StackSize,   8192,
                           NP_Output,      Output(),
                           NP_CloseOutput, FALSE,   /* Output() is not ours to close */
                           TAG_END);
    if (pr)
        Wait(doneMask);             /* worker's code lives in OUR seglist */
    else
        PutStr("CreateNewProc failed\n");
    FreeSignal(bit);
    return pr ? RETURN_OK : RETURN_FAIL;
}
```

### Gotchas
- NP_Input/NP_Output/NP_Error are CLOSED when the child ends unless you pass
  `NP_CloseInput`/`NP_CloseOutput`/`NP_CloseError` FALSE -- never hand over your own Input()/Output()
  without that.
- On a NULL result you still own everything you passed (NP_CurrentDir lock, handles, seglist) and
  must free it; on success the process owns it.
- NP_Entry code runs from the parent's seglist: the parent must not exit (its code is unloaded)
  before the child has finished. Signal the parent under Forbid() as above.
- With NP_Seglist and the default NP_FreeSeglist TRUE, DOS unloads the seglist at exit -- do not
  UnLoadSeg() it yourself.
- Default stack is 4000 bytes: far too small for most C code; always set NP_StackSize.
- NP_Arguments needs a non-NULL NP_Input (it modifies the input handle so ReadArgs works). It was
  broken in V36; works from V37.
- Callable from a plain task, but defaults that need DOS I/O (e.g. DupLock of the current dir)
  are then skipped.
- `NP_WindowPtr` -1 makes the child's DOS requesters (insert disk etc.) fail instead of opening.

**See also:** [CreateProc](#createproc), [RunCommand](#runcommand), [SystemTagList](#systemtaglist),
[LoadSeg](loading.md#loadseg), [ReadArgs](arguments.md#readargs), exec.library Signal, Wait

## CreateProc
`struct MsgPort * CreateProc(CONST_STRPTR name, LONG pri, BPTR segList, LONG stackSize)` — LVO -138 (-$8A)
Registers: name=D1, pri=D2, segList=D3, stackSize=D4; result in D0

Create a process from a seglist (1.x call); returns the new process's message port.

- **name** — process name.
- **pri** — priority, -128..127.
- **segList** — BPTR seglist; execution starts at its first hunk.
- **stackSize** — stack in bytes, must be a multiple of 4.
- **Result** — pointer to the new process's `pr_MsgPort`, 0 on failure. The Process is at
  `port - sizeof(struct Task)` (dosextens.h).

Obsolete from V36: use [CreateNewProc](#createnewproc).

### Example
```asm
        include "lvo/dos_lib.i"

        move.l  DOSBase,a6
        move.l  #procname,d1
        moveq   #0,d2                   ; priority
        move.l  #fakeseg+4,d3           ; address of the "next segment" longword
        lsr.l   #2,d3                   ; -> BPTR
        move.l  #4096,d4                ; stack, multiple of 4
        jsr     _LVOCreateProc(a6)
        tst.l   d0                      ; pr_MsgPort of the new process
        beq     .fail
        ...

        cnop    0,4                     ; a seglist must be longword aligned
fakeseg dc.l    16                      ; fake segment length
        dc.l    0                       ; BPTR next segment: none
        ; process code starts here
        ...
procname dc.b   "worker",0
```

### Gotchas
- The seglist is NOT freed when the process ends: the parent frees it, or the code unloads itself.
- A fake seglist like the one above must never be passed to UnLoadSeg().
- Returns a MsgPort pointer, not a `struct Process *` (unlike CreateNewProc).

**See also:** [CreateNewProc](#createnewproc), [LoadSeg](loading.md#loadseg),
[UnLoadSeg](loading.md#unloadseg)

## SystemTagList
`LONG SystemTagList(CONST_STRPTR command, CONST struct TagItem *tags)` — LVO -606 (-$25E)
Registers: command=D1, tags=D2; result in D0

Run a command line through a new shell process and return the command's return code.

- **command** — program name plus arguments; full shell parsing including `<`/`>` redirection.
  Your current directory and command path are inherited and used to find the program.
- **tags** — `SYS_` tags (`SYS_Dummy` = `TAG_USER`+32) plus any CreateNewProc tags except the
  filtered ones (`NP_Seglist`, `NP_FreeSeglist`, `NP_Entry`, `NP_Input`, `NP_Output`,
  `NP_CloseInput`, `NP_CloseOutput`, `NP_HomeDir`, `NP_Cli`):

| Tag | Value | Data | Default |
|---|---|---|---|
| `SYS_Input` | `$80000021` | BPTR input handle | your Input() |
| `SYS_Output` | `$80000022` | BPTR output handle | your Output() |
| `SYS_Asynch` | `$80000023` | BOOL: return at once; handles closed at exit | FALSE |
| `SYS_UserShell` | `$80000024` | BOOL: use the user shell, not the boot shell | FALSE |
| `SYS_CustomShell` | `$80000025` | STRPTR name of the shell to use | -- |

- **Result** — the command's return code (`RETURN_OK` 0, `RETURN_WARN` 5, `RETURN_ERROR` 10,
  `RETURN_FAIL` 20), or -1 only if DOS could not create the shell. A command that is not found
  gives an error code from the shell, normally `RETURN_ERROR`.

`System` is the same LVO; `SystemTags(command, tag, data, ..., TAG_END)` is the varargs form.

Since V36.

### Example
```c
#include <proto/dos.h>
#include <dos/dostags.h>
#include <utility/tagitem.h>

/* Run a command silently, logging its output to RAM:cmd.log. */
LONG run_logged(CONST_STRPTR cmd)
{
    BPTR in  = Open("NIL:", MODE_OLDFILE);
    BPTR out = Open("RAM:cmd.log", MODE_NEWFILE);
    LONG rc  = -1;

    if (in && out) {
        rc = SystemTags(cmd, SYS_Input, in, SYS_Output, out, TAG_END);
        if (rc == -1)
            PutStr("could not start a shell\n");
    }
    if (out) Close(out);            /* synchronous call: handles stay ours */
    if (in)  Close(in);
    return rc;
}
```

### Gotchas
- Synchronous: SYS_Input/SYS_Output are never closed for you -- close them after it returns.
- `SYS_Asynch` closes BOTH handles when the command ends, even if they were your Input()/Output():
  pass fresh handles and do not close them yourself (on a -1 result they are still yours).
- Never pass the same handle as SYS_Input and SYS_Output. For one CON: window, pass it as
  SYS_Input and SYS_Output NULL; the shell opens `*` on that window for output.
- The result is a return code, not a BOOL: 0 means success.
- Send text typed by the user with `SYS_UserShell` TRUE.
- V37+: an interactive or NIL: SYS_Input sets the new process's `pr_ConsoleTask` to that handler.

**See also:** [Execute](#execute), [CreateNewProc](#createnewproc), [Input](files.md#input),
[Output](files.md#output)

## Execute
`LONG Execute(CONST_STRPTR string, BPTR file, BPTR file2)` — LVO -222 (-$DE)
Registers: string=D1, file=D2, file2=D3; result in D0

Run a shell command line (optionally followed by commands read from a handle) and wait.

- **string** — command line; may contain `<`/`>` redirection; may be empty.
- **file** — input handle, normally 0. Non-zero: after `string`, further commands are read from
  this handle until EOF.
- **file2** — output handle for the commands; 0 means the current window (`*`), which
  Workbench-started programs normally do not have.
- **Result** — non-zero if the command could be found and started, 0 otherwise. NOT the
  command's return code.

### Example
```c
BPTR nil = Open("NIL:", MODE_NEWFILE);

if (nil) {
    if (!Execute("delete RAM:tmp#? QUIET", 0, nil))
        PutStr("Execute failed\n");
    Close(nil);                     /* Execute does not close it */
}
```

### Gotchas
- Use [SystemTagList](#systemtaglist) when you need the return code.
- Empty `string` plus an input handle on a new CON: window gives an interactive NewShell-style
  shell that only ends with EndCLI.
- Before V36 it needs `C:Run` on disk (1.3.2+ also checks the resident list for Run).
- V37+: an interactive or NIL: input handle sets the new process's `pr_ConsoleTask` to it.

**See also:** [SystemTagList](#systemtaglist), [RunCommand](#runcommand)

## RunCommand
`LONG RunCommand(BPTR seg, LONG stack, CONST_STRPTR paramptr, LONG paramlen)` — LVO -504 (-$1F8)
Registers: seg=D1, stack=D2, paramptr=D3, paramlen=D4; result in D0

Run a loaded seglist as a command on the calling process, with a newly allocated stack.

- **seg** — seglist of the command (any language, BCPL included).
- **stack** — stack size in bytes for the command.
- **paramptr** — NUL-terminated argument string; MUST end with a newline (`"\n"`).
- **paramlen** — length of the argument string in bytes (the newline counts, the NUL does not).
- **Result** — the command's return code (D0 at its exit), or -1 if the stack could not be
  allocated.

The command sees `paramptr` through GetArgStr() and can use ReadArgs() on Input(); RunCommand()
restores the input buffering and the GetArgStr() value afterwards (the handle setup is V37+).

Since V36.

### Example
```c
BPTR seg = LoadSeg("C:List");

if (seg) {
    UBYTE oldname[64];
    LONG rc;

    GetProgramName(oldname, sizeof(oldname));
    SetProgramName("List");                 /* the command sees its own name */
    rc = RunCommand(seg, 8192, "RAM:\n", 5);
    SetProgramName(oldname);
    UnLoadSeg(seg);
    Printf("List returned %ld\n", rc);
} else {
    PrintFault(IoErr(), "LoadSeg");
}
```

### Gotchas
- No trailing newline -> ReadArgs() in the command misparses or waits for input.
- It runs on YOUR process: same current dir, Input()/Output(), CLI structure. Only the input
  buffering and the argument string are documented as restored.
- RunCommand swaps the input handle's buffer without SetVBuf(), so a later
  [SetVBuf](buffered-io.md#setvbuf) on that handle fails.
- V36/V37: after SelectInput() of a fresh handle, Flush() misbehaves (fixed V39); see
  [Flush](buffered-io.md#flush).

**See also:** [LoadSeg](loading.md#loadseg), [CreateNewProc](#createnewproc),
[SystemTagList](#systemtaglist), [GetArgStr](#getargstr), [SetProgramName](#setprogramname),
[ReadArgs](arguments.md#readargs)

## Exit
`VOID Exit(LONG returnCode)` — LVO -144 (-$90)
Registers: returnCode=D1; no result

BCPL-style program exit; do NOT call it from C or assembler programs.

- **returnCode** — return code for the CLI.

Under a CLI it ends the command and returns to the shell; in a stand-alone process it deletes the
process and frees its stack, seglist and process structure. C programs return from main() or call
`exit()`; asm programs put the return code in D0 and `rts` with the stack pointer they started with.

### Gotchas
- It bypasses your cleanup (open libraries, memory, locks, C runtime).

**See also:** [CreateProc](#createproc), [CreateNewProc](#createnewproc)

## CheckSignal
`LONG CheckSignal(LONG mask)` — LVO -792 (-$318)
Registers: mask=D1; result in D0

Test and clear signals in a mask; the standard way to poll for Ctrl-C/D/E/F breaks.

- **mask** — signals to test: `SIGBREAKF_CTRL_C` (1<<12), `SIGBREAKF_CTRL_D` (1<<13),
  `SIGBREAKF_CTRL_E` (1<<14), `SIGBREAKF_CTRL_F` (1<<15), or any other signal bits.
- **Result** — the bits of `mask` that were set (0 = none). All bits in `mask` are cleared.

Since V36.

### Example
```c
while (!(CheckSignal(SIGBREAKF_CTRL_C) & SIGBREAKF_CTRL_C)) {
    /* one unit of work */
}
PutStr("***Break\n");
```
```asm
        include "dos/dos.i"
        include "lvo/dos_lib.i"

.loop   bsr     do_work
        move.l  DOSBase,a6
        move.l  #SIGBREAKF_CTRL_C,d1
        jsr     _LVOCheckSignal(a6)
        tst.l   d0
        beq.s   .loop                   ; no break yet
        ; Ctrl-C pressed: clean up and exit
```

### Gotchas
- Reading clears the bits: test the result once and remember it.
- Poll it in every long loop of a CLI program; users expect Ctrl-C to work.
- Pre-V36: use exec `SetSignal(0, SIGBREAKF_CTRL_C)` and test the returned bits.

**See also:** exec.library SetSignal, Wait

## Cli
`struct CommandLineInterface * Cli(VOID)` — LVO -492 (-$1EC)
Registers: none; result in D0

Return the calling process's CommandLineInterface structure, or NULL if it has none.

- **Result** — `struct CommandLineInterface *` (already converted from the `pr_CLI` BPTR), or NULL
  for non-CLI processes (Workbench start, CreateNewProc without `NP_Cli`).

| Field | Type | Meaning |
|---|---|---|
| `cli_Result2` | LONG | IoErr value of the last command |
| `cli_SetName` | BSTR | current directory name |
| `cli_CommandDir` | BPTR | head of the command path lock list |
| `cli_ReturnCode` | LONG | return code of the last command |
| `cli_CommandName` | BSTR | name of the current command |
| `cli_FailLevel` | LONG | FAILAT level |
| `cli_Prompt` | BSTR | prompt string |
| `cli_StandardInput` / `cli_StandardOutput` | BPTR | default (terminal) handles |
| `cli_CurrentInput` / `cli_CurrentOutput` | BPTR | current handles |
| `cli_CommandFile` | BSTR | name of the Execute script |
| `cli_Interactive` | LONG | TRUE if prompts are shown |
| `cli_Background` | LONG | TRUE if created by RUN |
| `cli_DefaultStack` | LONG | stack size in LONGWORDS (x4 for bytes) |
| `cli_Module` | BPTR | seglist of the current command |

Since V36.

### Example
```c
struct CommandLineInterface *cli = Cli();

if (cli == NULL) {
    /* no CLI: Workbench start or a plain child process */
} else {
    /* RawDoFmt %b prints a BSTR given as a BPTR */
    Printf("I am %b, default stack %ld bytes\n",
           cli->cli_CommandName, cli->cli_DefaultStack * 4);
}
```

### Gotchas
- String fields are BSTRs (BPTR to a length byte + chars, not reliably NUL-terminated): use
  BADDR(), `%b`, or GetProgramName()/GetPrompt()/GetCurrentDirName() instead.
- `cli_DefaultStack` is in longwords, not bytes.
- Change the strings only through SetProgramName()/SetPrompt()/SetCurrentDirName().

**See also:** [GetProgramName](#getprogramname), [MaxCli](#maxcli), [FindCliProc](#findcliproc),
[BPTR and BSTR](concepts.md#bptr-and-bstr)

## MaxCli
`ULONG MaxCli(VOID)` — LVO -552 (-$228)
Registers: none; result in D0

Return the highest CLI number that may currently be in use.

- **Result** — highest possible CLI number. Numbers are reused and kept small; scan 1..MaxCli()
  with FindCliProc() to find all shells. The value can change at any moment.

Since V36.

**See also:** [FindCliProc](#findcliproc), [Cli](#cli)

## FindCliProc
`struct Process * FindCliProc(ULONG num)` — LVO -546 (-$222)
Registers: num=D1; result in D0

Return the Process for a CLI number, or NULL if that number is not an active CLI.

- **num** — CLI number, 1..MaxCli().
- **Result** — `struct Process *` or NULL.

Since V36.

### Example
```c
ULONG n;

Forbid();
for (n = 1; n <= MaxCli(); n++) {
    struct Process *pr = FindCliProc(n);
    if (pr) {
        /* copy what you need from pr here; it may vanish after Permit() */
    }
}
Permit();
```

### Gotchas
- Call it inside Forbid(): the process can exit at any time otherwise.
- A process's own CLI number is `pr_TaskNum` (0 = not a CLI).

**See also:** [MaxCli](#maxcli), [Cli](#cli), exec.library Forbid

## GetArgStr
`STRPTR GetArgStr(VOID)` — LVO -534 (-$216)
Registers: none; result in D0

Return the argument string the current program was started with.

- **Result** — NUL-terminated argument string: the same string a CLI command receives in A0 at
  startup (length in D0).

Since V36.

### Gotchas
- Shell argument lines end with a newline (RunCommand requires one); strip it before using the
  string raw, or parse with [ReadArgs](arguments.md#readargs).
- Read-only: do not modify it; use SetArgStr() to replace it temporarily.

**See also:** [SetArgStr](#setargstr), [RunCommand](#runcommand)

## SetArgStr
`BOOL SetArgStr(CONST_STRPTR string)` — LVO -540 (-$21C)
Registers: string=D1; result in D0

Replace the argument string returned by GetArgStr(); restore the old one before exit.

- **string** — new argument string.
- **Result** — the previous argument string pointer (the NDK prototype says BOOL; D0 holds the
  old STRPTR).

Since V36.

### Gotchas
- The original pointer MUST be put back before the process exits.

**See also:** [GetArgStr](#getargstr), [RunCommand](#runcommand)

## GetProgramName
`BOOL GetProgramName(STRPTR buf, LONG len)` — LVO -576 (-$240)
Registers: buf=D1, len=D2; result in D0

Copy the current command name from the CLI structure into a buffer.

- **buf** — destination buffer.
- **len** — buffer size in bytes; a longer name is truncated.
- **Result** — non-zero on success. Without a CLI structure: FALSE, empty string in `buf`, IoErr()
  = `ERROR_OBJECT_WRONG_TYPE`.

Since V36.

### Gotchas
- Workbench-started programs get an empty string: take the name from the WBStartup message there.

**See also:** [SetProgramName](#setprogramname), [Cli](#cli)

## SetProgramName
`BOOL SetProgramName(CONST_STRPTR name)` — LVO -570 (-$23A)
Registers: name=D1; result in D0

Set the command name stored in the CLI structure.

- **name** — new name.
- **Result** — non-zero on success; FALSE if the name does not fit (old value kept). Safe to call
  without a CLI structure.

Since V36.

### Gotchas
- The name is clipped to a fixed, 1.3-compatible buffer size.
- Set it before RunCommand() so the command sees its own name; restore yours afterwards.

**See also:** [GetProgramName](#getprogramname), [RunCommand](#runcommand)

## GetProgramDir
`BPTR GetProgramDir(VOID)` — LVO -600 (-$258)
Registers: none; result in D0

Return a shared lock on the directory the running program was loaded from (PROGDIR:).

- **Result** — BPTR lock, or 0 (e.g. the program came from the resident list). The lock belongs
  to the system: never UnLock() it.

Since V36.

### Example
```c
/* Simplest: paths relative to the PROGDIR: assign */
BPTR fh = Open("PROGDIR:data/level1.dat", MODE_OLDFILE);

/* Or make the program directory current for plain relative names */
BPTR home = GetProgramDir();
if (home) {
    BPTR old = CurrentDir(home);
    BPTR cfg = Open("game.cfg", MODE_OLDFILE);
    CurrentDir(old);                /* restore; never UnLock(home) */
    if (cfg) { /* ... */ Close(cfg); }
}
```

### Gotchas
- Test for 0: `CurrentDir(0)` means the root of the boot volume, not "here".
- Ideal for games/demos that load data files stored next to the executable.

**See also:** [SetProgramDir](#setprogramdir), [CurrentDir](locks-and-directories.md#currentdir),
[Open](files.md#open)

## SetProgramDir
`BPTR SetProgramDir(BPTR lock)` — LVO -594 (-$252)
Registers: lock=D1; result in D0

Set the lock returned by GetProgramDir() and used to resolve PROGDIR:.

- **lock** — shared lock on a directory, or 0.
- **Result** — the previous program directory lock.

Since V36.

### Gotchas
- Put the previous lock back before your program ends. Ownership of the lock you set is not
  documented: keep it and UnLock() it yourself after restoring (unverified).

**See also:** [GetProgramDir](#getprogramdir)

## GetCurrentDirName
`BOOL GetCurrentDirName(STRPTR buf, LONG len)` — LVO -564 (-$234)
Registers: buf=D1, len=D2; result in D0

Copy the current directory name kept in the CLI structure into a buffer.

- **buf** — destination buffer.
- **len** — buffer size in bytes.
- **Result** — non-zero on success; FALSE if truncated, or if there is no CLI structure (empty
  string, IoErr() = `ERROR_OBJECT_WRONG_TYPE`).

Since V36.

### Gotchas
- This is the shell's stored name string, not derived from `pr_CurrentDir`; for the real path use
  [NameFromLock](locks-and-directories.md#namefromlock) on the current directory lock.
- V36 mishandled 0-length buffers.

**See also:** [SetCurrentDirName](#setcurrentdirname), [CurrentDir](locks-and-directories.md#currentdir)

## SetCurrentDirName
`BOOL SetCurrentDirName(CONST_STRPTR name)` — LVO -558 (-$22E)
Registers: name=D1; result in D0

Set the directory name kept in the CLI structure (does not change the current directory).

- **name** — directory name to store.
- **Result** — non-zero on success; FALSE if too long (old value kept). Safe without a CLI.

Since V36.

### Gotchas
- Only [CurrentDir](locks-and-directories.md#currentdir) changes the directory; a shell-like
  program calls both.
- Clipped to a fixed, 1.3-compatible size.

**See also:** [GetCurrentDirName](#getcurrentdirname)

## GetPrompt
`BOOL GetPrompt(STRPTR buf, LONG len)` — LVO -588 (-$24C)
Registers: buf=D1, len=D2; result in D0

Copy the shell prompt string from the CLI structure into a buffer.

- **buf** — destination buffer.
- **len** — buffer size in bytes.
- **Result** — non-zero on success; FALSE if truncated, or no CLI structure (empty string, IoErr()
  = `ERROR_OBJECT_WRONG_TYPE`).

Since V36.

**See also:** [SetPrompt](#setprompt)

## SetPrompt
`BOOL SetPrompt(CONST_STRPTR name)` — LVO -582 (-$246)
Registers: name=D1; result in D0

Set the shell prompt string in the CLI structure.

- **name** — new prompt text.
- **Result** — non-zero on success; FALSE if too long (old value kept). Safe without a CLI.

Since V36.

### Gotchas
- Clipped to a fixed, 1.3-compatible size.

**See also:** [GetPrompt](#getprompt)

## GetConsoleTask
`struct MsgPort * GetConsoleTask(VOID)` — LVO -510 (-$1FE)
Registers: none; result in D0

Return the process's default console handler port (`pr_ConsoleTask`).

- **Result** — `pr_MsgPort` of the console handler for the process's window, or NULL. Opening `*`
  (current window) goes to this handler.

Since V36.

### Gotchas
- NULL when the process has no console window (typical for Workbench starts), so `*` cannot be
  opened (unverified).

**See also:** [SetConsoleTask](#setconsoletask), [Open](files.md#open)

## SetConsoleTask
`struct MsgPort * SetConsoleTask(CONST struct MsgPort *task)` — LVO -516 (-$204)
Registers: task=D1; result in D0

Set the process's default console handler port (`pr_ConsoleTask`).

- **task** — `pr_MsgPort` of the console handler to use, e.g. `fh_Type` of a CON: handle
  (`((struct FileHandle *)BADDR(fh))->fh_Type`).
- **Result** — the previous value.

Since V36.

### Gotchas
- Restore the previous value before the handler you set goes away (e.g. before closing that
  window).

**See also:** [GetConsoleTask](#getconsoletask), [Open](files.md#open)

## GetFileSysTask
`struct MsgPort * GetFileSysTask(VOID)` — LVO -522 (-$20A)
Registers: none; result in D0

Return the process's default filesystem handler port (`pr_FileSystemTask`).

- **Result** — `pr_MsgPort` of the default filesystem, or NULL.

Since V36.

**See also:** [SetFileSysTask](#setfilesystask), [DoPkt](packets.md#dopkt)

## SetFileSysTask
`struct MsgPort * SetFileSysTask(CONST struct MsgPort *task)` — LVO -528 (-$210)
Registers: task=D1; result in D0

Set the process's default filesystem handler port (`pr_FileSystemTask`).

- **task** — `pr_MsgPort` of the filesystem to use.
- **Result** — the previous value.

Since V36.

**See also:** [GetFileSysTask](#getfilesystask)

## CliInitNewcli
`LONG CliInitNewcli(struct DosPacket *dp)` — LVO -930 (-$3A2)
Registers: dp=A0; result in D0

Shell writers only: set up a new shell process from its NewShell/NewCLI startup packet.

- **dp** — the initial packet received on your `pr_MsgPort` (passed in A0; its format is private).
- **Result** — flags, valid only when bit 31 is set:

| Bit | Meaning when set |
|---|---|
| 31 | flags are valid |
| 3 | asynchronous System() call |
| 2 | this is a System() call |
| 1 | caller supplied the input stream |
| 0 | RUN supplied the output stream |

Sets up the process and CLI structure (current dir, path, input streams). If bit 31 is clear,
check IoErr(): if it equals your own Process pointer an error occurred, the packet was already
replied -- clean up and exit; otherwise reply the packet immediately with
[ReplyPkt](packets.md#replypkt).

### Gotchas
- Argument in A0, not D1.
- Reply rules differ from [CliInitRun](#cliinitrun).
- `dos/dosextens.h` defines `RUN_EXECUTE` (-1), `RUN_SYSTEM` (-2), `RUN_SYSTEM_ASYNCH` (-3) as
  initial-packet types for shells.

**See also:** [CliInitRun](#cliinitrun), [ReplyPkt](packets.md#replypkt),
[WaitPkt](packets.md#waitpkt), [IoErr](errors.md#ioerr)

## CliInitRun
`LONG CliInitRun(struct DosPacket *dp)` — LVO -936 (-$3A8)
Registers: dp=A0; result in D0

Shell writers only: set up a shell process from a Run/System()/Execute() startup packet.

- **dp** — initial packet from your `pr_MsgPort` (in A0; private format).
- **Result** — flags with the same bits as [CliInitNewcli](#cliinitnewcli).

Packet reply rules:
- Bit 31 clear and IoErr() == your Process: error, packet already replied; clean up and exit.
- Bit 31 clear otherwise: reply only after loading the first command (or at exit) -- avoids disk
  thrashing with Run.
- Bit 31 set: bit 3 set (asynchronous System) -> ReplyPkt() at once; else reply when the shell
  exits (synchronous System, Execute).

### Gotchas
- Argument in A0, not D1.

**See also:** [CliInitNewcli](#cliinitnewcli), [ReplyPkt](packets.md#replypkt),
[WaitPkt](packets.md#waitpkt), [SystemTagList](#systemtaglist), [Execute](#execute)
