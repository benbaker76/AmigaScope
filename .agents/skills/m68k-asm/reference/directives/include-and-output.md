# vasm directives: include files and output naming

**Search order for INCLUDE and INCBIN (vasm manual, confirmed by tests):**
1. current work directory; 2. directory of the main source file ("compile directory",
disable with `-nocompdir`); 3. `-I` paths in command-line order; 4. `incdir` paths in
source order. Relative `-I`/`incdir` paths are tried below the work directory, then below
the compile directory. A file included from `inc/a.i` is NOT searched for in `inc/`.

## INCLUDE
`include <file>`

Insert another source file at this point.

- **file** — `"name"`, `'name'`, `<name>` or bare `name` all work (tested). An absolute
  path is used as is.

### Example
```asm
        include "exec/types.i"          ; NDK: always first
        include "exec/memory.i"
        include "hardware/custom.i"
        include "lvo/exec_lib.i"        ; _LVO... offsets
```
Assemble with `-I<NDK>/sys-include` (Bartman's toolchain path:
`.../bin/<os>/opt/m68k-amiga-elf/sys-include`).

### Gotchas
- NDK asm includes are guarded (`IFND EXEC_TYPES_I` / `EXEC_TYPES_I SET 1`), so double
  inclusion is harmless; give your own `.i` files the same guard. `-ignore-mult-inc`
  skips a repeated include of the same path.
- Use `lvo/<lib>_lib.i` for `_LVO` offsets. In this NDK `exec/exec_lib.i` is only
  `FUNCDEF` lines ("unknown mnemonic FUNCDEF" unless you define that macro), and
  `dos/dos_lib.i` defines the same `_LVO` names plus global `count`/`vsize`/`reserve`
  symbols; including it together with `lvo/dos_lib.i` is error 68 (tested).
- For Makefiles: `-depend=make` / `-dependall=make` plus `-depfile <file>` write
  dependencies while assembling (Bartman's template uses `-dependall=make -depfile`).

**See also:** [INCDIR](#incdir), [INCBIN](data.md#incbin), [IFND](conditional.md#ifnd),
[library calls topic](../topics/library-calls.md)

## INCDIR
`incdir <path>`

Add a directory to the include search list.

Paths added this way are searched after all `-I` paths, in the order the directives
appear. They also apply to INCBIN.

### Example
```asm
        incdir  "include"               ; vscode-amiga-assembly example workspace style
        include "hw.i"
```

**See also:** [INCLUDE](#include)

## OUTPUT
`output <name>`

Set the output file name when none was given with `-o`.

- A name starting with `.` while `-o` was given replaces the extension of the `-o` name
  (Devpac compatibility): `-o game.o` plus `output .exe` writes `game.exe` (tested).
- Without `-o` and without OUTPUT the file is `a.out`.

**See also:** [IDNT](#idnt), [vasm and vlink](../topics/vasm-vlink.md)

## IDNT
`idnt <name>`

Set the module name stored in the object file.

For `-Fhunk` this is the `HUNK_UNIT` name (tested); by default vasm uses the source file
name. It has no effect on the program itself.

**See also:** [TTL](#ttl)

## TTL
`ttl <name>`

Title directive whose meaning depends on the vasm version.

In the bundled vasm 1.8k and 1.9 it sets the `HUNK_UNIT` name like IDNT (tested); the
newer manual describes it as the listing page title. Do not rely on either.

**See also:** [IDNT](#idnt), [PAGE](listing-and-misc.md#page)

## END
`end`

Stop assembling; every following line is ignored.

A missing END is fine. Anything after END (test code, notes) is not even syntax-checked.

**See also:** [FAIL](listing-and-misc.md#fail), [REM](listing-and-misc.md#rem)
