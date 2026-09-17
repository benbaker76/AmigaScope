# dos.library: command-line arguments

`ReadArgs()` parses a CLI command line against a template string and fills a LONG array, one
slot per template item; `FreeArgs()` releases what it allocated. `FindArg()` and `ReadItem()`
are the building blocks for custom parsers, `StrToLong()` converts decimal text. All of this
reads the command line from the process's buffered `Input()` unless you supply a `CSource`, so
it only makes sense for CLI-started programs (a Workbench start has no command line -- read
icon tool types instead).

## ReadArgs
`struct RDArgs * ReadArgs(CONST_STRPTR arg_template, LONG *array, struct RDArgs *args)` — LVO -798 (-$31E)
Registers: arg_template=D1, array=D2, args=D3; result in D0

Parse the command line (or a string) against a template into an array of LONGs.

- **arg_template** — comma-separated items, each `NAME` optionally preceded by aliases
  (`Q=QUIET`) and followed by modifiers:

  | Modifier | Meaning | Array slot receives |
  |---|---|---|
  | (none) | string (quotes stripped) | `STRPTR`, or unchanged if absent |
  | `/A` | required: error if not filled | per its type |
  | `/K` | keyword: only filled as `NAME=value` or `NAME value` | per its type |
  | `/S` | switch: set if the name appears | LONG, non-zero = given |
  | `/T` | toggle: like /S but flips the value in the slot | LONG boolean |
  | `/N` | decimal number (error if invalid) | `LONG *` to the value, NULL if absent |
  | `/M` | any number of strings (only one /M per template) | `STRPTR *`, NULL-terminated array |
  | `/F` | rest of the line, keywords included | `STRPTR` |

  Modifiers stack: `FROM/A/M`, `SIZE/K/N`. Leftover /M strings are taken from the END of the /M
  list to fill later /A items, which is how `FROM/A/M,TO/A` works.
- **array** — `LONG` array with one entry per template item, pre-set to 0 or your defaults.
- **args** — NULL (ReadArgs allocates the RDArgs), or your own `struct RDArgs` from
  `AllocDosObject(DOS_RDARGS, NULL)` to parse a string, supply a buffer or help text.
- **Result** — `struct RDArgs *` to pass to `FreeArgs()`, or NULL on failure with IoErr set
  (`ERROR_REQUIRED_ARG_MISSING`, `ERROR_BAD_NUMBER`, `ERROR_KEY_NEEDS_ARG`,
  `ERROR_TOO_MANY_ARGS`, `ERROR_BAD_TEMPLATE`, `ERROR_LINE_TOO_LONG`, ...).

`struct RDArgs` (`dos/rdargs.h`): `RDA_Source` (`struct CSource`: `CS_Buffer`, `CS_Length`,
`CS_CurChr`), `RDA_DAList` (private, must be NULL before first use), `RDA_Buffer`/`RDA_BufSiz`
(optional parse buffer), `RDA_ExtHelp` (shown instead of the template when prompting),
`RDA_Flags`: `RDAF_STDIN` (1), `RDAF_NOALLOC` (2), `RDAF_NOPROMPT` (4). Limits:
`MAX_TEMPLATE_ITEMS` 100, `MAX_MULTIARGS` 128.

Since V36.

### Example
```c
#include <proto/dos.h>
#include <dos/dos.h>
#include <dos/rdargs.h>

#define TEMPLATE "FILE/A,TO,Q=QUIET/S,BUF=BUFSIZE/K/N,EXTRA/M"
enum { OPT_FILE, OPT_TO, OPT_QUIET, OPT_BUFSIZE, OPT_EXTRA, OPT_COUNT };

int main(void)
{
    LONG opts[OPT_COUNT] = { 0 };
    struct RDArgs *rda = ReadArgs(TEMPLATE, opts, NULL);
    if (!rda) {
        PrintFault(IoErr(), "mytool");
        return RETURN_FAIL;
    }
    STRPTR file   = (STRPTR)opts[OPT_FILE];
    STRPTR to     = (STRPTR)opts[OPT_TO];            /* NULL if not given */
    BOOL   quiet  = opts[OPT_QUIET] != 0;
    LONG   bufsz  = opts[OPT_BUFSIZE] ? *(LONG *)opts[OPT_BUFSIZE] : 4096;
    STRPTR *extra = (STRPTR *)opts[OPT_EXTRA];       /* NULL or NULL-terminated */

    if (!quiet)                                      /* pointers need (LONG) casts */
        Printf("%s -> %s (%ld)\n", (LONG)file, (LONG)(to ? to : (STRPTR)"-"), bufsz);
    for (; extra && *extra; extra++) {
        PutStr(*extra);
        PutStr("\n");
    }

    FreeArgs(rda);            /* every string above is invalid from here on */
    return RETURN_OK;
}
```

Parsing a string instead of the command line:
```c
static char line[] = "work:data TO ram: QUIET\n";   /* keep the newline */
LONG opts[OPT_COUNT] = { 0 };
struct RDArgs *rda = AllocDosObject(DOS_RDARGS, NULL);
if (rda) {
    rda->RDA_Source.CS_Buffer = (UBYTE *)line;
    rda->RDA_Source.CS_Length = sizeof(line) - 1;
    rda->RDA_Source.CS_CurChr = 0;
    rda->RDA_Flags |= RDAF_NOPROMPT;
    if (ReadArgs(TEMPLATE, opts, rda)) {
        /* use opts[] */
        FreeArgs(rda);                        /* frees the parse data, not rda */
    }
    FreeDosObject(DOS_RDARGS, rda);
}
```

### Gotchas
- Every successful ReadArgs needs exactly one `FreeArgs()`; the strings/number pointers in the
  array point into memory FreeArgs releases -- copy what you keep.
- /N gives a POINTER to the number, not the number. /S and /T give a plain LONG.
- Clear the array (or set defaults) first: absent items are left untouched.
- Strings passed via `CSource` must end in `'\n'` (V37 and earlier require it).
- A caller-supplied RDArgs must come from `AllocDosObject(DOS_RDARGS, ...)`; reset
  `RDA_Buffer` before every new ReadArgs on it, and free it yourself after `FreeArgs()`.
- V36 bugs (fixed V37): /M/N returned strings, /T did nothing, /K before non-switch items made
  those items keyword-only.
- Uses a fair amount of stack (the header asks for "a lot"); do not call it on a tiny stack.
- Typing `?` makes ReadArgs print the template (or `RDA_ExtHelp`) and read a new line from the
  console (unverified); set `RDAF_NOPROMPT` when there is no console.

**See also:** [FreeArgs](#freeargs), [FindArg](#findarg), [ReadItem](#readitem),
[AllocDosObject](objects.md#allocdosobject), [RunCommand](processes.md#runcommand)

## FreeArgs
`VOID FreeArgs(struct RDArgs *args)` — LVO -858 (-$35A)
Registers: args=D1; no result

Free everything a successful ReadArgs() allocated.

- **args** — the value ReadArgs returned, or NULL (no-op). If ReadArgs allocated the RDArgs it
  is freed too; a caller-supplied RDArgs is only emptied.

Since V36.

**See also:** [ReadArgs](#readargs), [ReadItem](#readitem), [FindArg](#findarg)

## FindArg
`LONG FindArg(CONST_STRPTR keyword, CONST_STRPTR arg_template)` — LVO -804 (-$324)
Registers: keyword=D1, arg_template=D2; result in D0

Return the index of a keyword within a ReadArgs template, or -1.

- **keyword** / **arg_template** — see the register gotcha: per the autodoc D1 = template,
  D2 = keyword.
- **Result** — item number in the template (0 = first item, matching the ReadArgs array index;
  unverified), or -1 if the keyword is not in it.
  Abbreviations (`Q=QUIET`) are matched.

Since V36.

### Gotchas
- Argument order is a known trap. The NDK 3.9 autodoc gives `FindArg(template, keyword)` with
  template in D1 and says earlier autodocs had the two swapped; the NDK prototype still names
  the D1 parameter `keyword`. Follow the autodoc: in C pass the template FIRST
  (`FindArg("FROM/A,TO/A", "TO")` -> 1); in asm put the template in D1.

**See also:** [ReadArgs](#readargs), [ReadItem](#readitem), [FreeArgs](#freeargs)

## ReadItem
`LONG ReadItem(CONST_STRPTR name, LONG maxchars, struct CSource *cSource)` — LVO -810 (-$32A)
Registers: name=D1, maxchars=D2, cSource=D3; result in D0

Read one whitespace/quote/`=`-delimited word from Input() or a CSource.

- **name** — buffer that receives the word (NUL-terminated).
- **maxchars** — size of the buffer.
- **cSource** — `struct CSource` to read from, or NULL to read buffered `FGetC(Input())`.
- **Result** — `ITEM_EQUAL` (-2, an `=`), `ITEM_ERROR` (-1), `ITEM_NOTHING` (0: `*N`, `;` or
  end of stream, per the dos.h comment), `ITEM_UNQUOTED` (1), `ITEM_QUOTED` (2).

Handles quoting, and `*e`/`*n` escapes inside quotes only.

Since V36.

### Gotchas
- The autodoc claims the terminator is pushed back for the caller, but its BUGS section says it
  is not actually unread; do not rely on re-reading it.

**See also:** [ReadArgs](#readargs), [FindArg](#findarg), [UnGetC](buffered-io.md#ungetc),
[FGetC](buffered-io.md#fgetc)

## StrToLong
`LONG StrToLong(CONST_STRPTR string, LONG *value)` — LVO -816 (-$330)
Registers: string=D1, value=D2; result in D0

Convert leading decimal text to a LONG.

- **string** — text; leading spaces and tabs are skipped (and counted).
- **value** — where the number is stored; set to 0 if no digits were found.
- **Result** — characters consumed, or -1 if no decimal digits were found.

Since V36.

### Example
```c
LONG n;
if (StrToLong(text, &n) < 0) {
    PutStr("not a number\n");
}
```

### Gotchas
- Decimal only -- no `$`, `0x` or `%` prefixes.
- Before V39, "no digits" returned the number of skipped blanks instead of -1: check that the
  count is greater than the number of leading blanks if you must support V37.

**See also:** [ReadArgs](#readargs), [ReadItem](#readitem)
