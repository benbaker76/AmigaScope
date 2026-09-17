# Structure offsets: NDK include macros and vasm counters

OS structures are described in the NDK asm includes with macros from `exec/types.i`;
your own structures can use the same macros or vasm's RS/SO/FO/OFFSET directives. Both
only compute offsets: nothing is emitted, nothing is aligned automatically. All values
below were printed with vasm `printv` from the NDK 3.9 includes.

## The exec/types.i macros

`exec/types.i` must be included before any other Amiga include (its own header). Its
structure macros keep a running offset in the global SET symbol `SOFFSET`.

| Macro | Advances SOFFSET by | Notes |
|---|---|---|
| `STRUCTURE Name,start` | sets it to `start` | also defines `Name EQU 0` |
| `BYTE x` / `UBYTE x` | 1 | |
| `WORD x` / `UWORD x` / `BOOL x` | 2 | `SHORT`, `USHORT` are obsolete aliases |
| `RPTR x` | 2 | 16-bit relative pointer |
| `LONG x` / `ULONG x` / `APTR x` / `FPTR x` / `FLOAT x` | 4 | `CPTR` obsolete alias of APTR |
| `DOUBLE x` | 8 | |
| `STRUCT x,size` | size | embedded structure or array |
| `LABEL x` | 0 | names the current offset, used for `..._SIZE`/`..._SIZEOF` |
| `ALIGNWORD` / `ALIGNLONG` | to even / to multiple of 4 | explicit alignment |
| `BPTR x` / `BSTR x` | 4 | defined in `dos/dos.i`, not in types.i |

Each field macro is `x EQU SOFFSET` followed by `SOFFSET SET SOFFSET+n`. Other macros in
the file:

- `ENUM [base]` / `EITEM label` — `label EQU` 0, 1, 2... (or from `base`).
- `BITDEF prefix,name,bit` — `prefixB_name EQU bit` and `prefixF_name EQU 1<<bit`
  (e.g. `BITDEF MEM,CHIP,1` gives `MEMB_CHIP` 1, `MEMF_CHIP` 2).
- `EXTERN_LIB name` — `XREF _LVOname`.
- `LIBRARY_MINIMUM EQU 33`, `INCLUDE_VERSION EQU 40` (the latter is not an OpenLibrary
  version).

## Worked example: where is gb_copinit?

`graphics/gfxbase.i` starts:

```asm
 STRUCTURE  GfxBase,LIB_SIZE
        APTR    gb_ActiView
        APTR    gb_copinit              ; ptr to copper start up list
        APTR    gb_cia
```

1. `LIB_SIZE` comes from `exec/libraries.i`: `STRUCTURE LIB,LN_SIZE` where `LN_SIZE` is 14
   (`exec/nodes.i`: `LN_SUCC` 0, `LN_PRED` 4, `LN_TYPE` 8, `LN_PRI` 9, `LN_NAME` 10). Then
   `LIB_FLAGS` 14, `LIB_pad` 15, `LIB_NEGSIZE` 16, `LIB_POSSIZE` 18, `LIB_VERSION` 20,
   `LIB_REVISION` 22, `LIB_IDSTRING` 24, `LIB_SUM` 28, `LIB_OPENCNT` 32, `LIB_SIZE` 34.
2. `STRUCTURE GfxBase,LIB_SIZE` sets SOFFSET to 34, so `gb_ActiView` = 34 and
   `gb_copinit` = 38 ($26), `gb_cia` = 42, `gb_blitter` = 46, `gb_LOFlist` = 50.
3. Check instead of counting by hand:

```asm
        include "exec/types.i"
        include "graphics/gfxbase.i"
        printv  gb_copinit              ; prints $26 38 ...

        section code,code
        move.l  _GfxBase,a6             ; your variable, from OpenLibrary
        move.l  gb_copinit(a6),$dff080  ; COP1LC = system copper list
```

The vscode-amiga-assembly example `gencop.s` reads the same field as the literal
`38(a1)`; using `gb_copinit(a1)` keeps the source readable and include-checked.

## Your own structure with the NDK macros

```asm
        include "exec/types.i"

 STRUCTURE Actor,0
        WORD    act_X                   ; 0
        WORD    act_Y                   ; 2
        UBYTE   act_Frame               ; 4
        ALIGNWORD                       ; pad to 6
        APTR    act_Image               ; 6
        STRUCT  act_Vel,2*2             ; 10: two words
        LONG    act_Score               ; 14
        LABEL   act_SIZEOF              ; 18

        BITDEF  ACT,VISIBLE,3           ; ACTB_VISIBLE 3, ACTF_VISIBLE 8
        ENUM
        EITEM   ST_IDLE                 ; 0
        EITEM   ST_RUN                  ; 1

        section code,code
        lea     actors,a0
        move.w  #10,act_X(a0)
        bset    #ACTB_VISIBLE,act_Frame(a0)
        lea     act_SIZEOF(a0),a0       ; next actor

        section vars,bss
actors: ds.b    act_SIZEOF*16
```

A leading blank before `STRUCTURE` is required (column 1 would make it a label).

## The same structure with vasm directives

```asm
        rsreset
obj_X     rs.w  1                       ; 0
obj_Y     rs.w  1                       ; 2
obj_Frame rs.b  1                       ; 4
          rs.b  1                       ; pad
obj_Image rs.l  1                       ; 6
obj_Vel   rs.w  2                       ; 10
obj_Score rs.l  1                       ; 14
obj_SIZEOF rs.b 0                       ; 18
```

| | NDK macros | vasm RS / SO / FO / OFFSET |
|---|---|---|
| Portability | any assembler that runs the NDK includes | vasm and Devpac-style assemblers |
| Counter | global `SOFFSET` (shared with every NDK include) | `__RS`, `__SO`, `__FO`, offset sections |
| Alignment | `ALIGNWORD`/`ALIGNLONG` | pad by hand (auto only with `-devpac`/`-align`) |
| Extras | `ENUM`/`EITEM`, `BITDEF` | FO counts downwards for LINK frames |

Extending an OS structure works with either: `STRUCTURE MyNode,LN_SIZE` or
`rsset LN_SIZE`.

## Common mistakes

- **Name collisions with the NDK.** `STRUCTURE GfxBase,...` makes `GfxBase` the constant
  0, so `GfxBase: ds.l 1` is "label redefined" and `move.l GfxBase,a6` reads address 0.
  NDK field names use short prefixes that collide easily: `ra_SIZEOF` is already defined
  by `graphics/gfx.i` (error 68 in a test that used a `ra_` prefix). Pick distinctive
  prefixes and assemble with `-x`.
- **Guessing the size label.** The NDK is inconsistent: `LN_SIZE`, `LIB_SIZE`, `MN_SIZE`,
  `TC_SIZE`, `gb_SIZE`, `pr_SIZEOF`, `sm_SIZEOF`. A wrong guess without `-x` becomes a
  silent external (value unknown until link). Look it up or `printv` it.
- **Missing padding** after an odd `UBYTE`/`rs.b` run: every later field is off by one
  compared with the C structure.
- **Using `SOFFSET` for your own purposes**: every NDK include rewrites it.
- **`BPTR` without `dos/dos.i`**: "unknown mnemonic BPTR" (tested).
- **Hard-coded offsets** (`38(a1)`): they compile, but nothing checks them.

**See also:** [RS](../directives/structures.md#rs), [SO](../directives/structures.md#so),
[FO](../directives/structures.md#fo), [OFFSET](../directives/sections.md#offset),
[MACRO](../directives/macros-repeat.md#macro), [library calls](library-calls.md)
