# FMODE, fetch width and DMA slots

FMODE ($DFF1FC) sets how many bits Alice/Lisa fetch per plane per DMA cycle. Wider fetches
give the bandwidth deep hires/superhires displays need, but they change alignment, the
data-fetch window, modulos and scroll range, and an early fetch start costs hardware
sprites. Register: [FMODE](../registers/aga.md#fmode).

## The fetch modes

| FMODE bits 1-0 | Bitplane fetch per plane | Bus | Bandwidth |
|---|---|---|---|
| 00 | 16 bits (2 bytes) | 16-bit, normal CAS | 1x (OCS) |
| 01 BPL32 | 32 bits (4 bytes) | 32-bit, normal CAS | 2x |
| 10 BPAGEM | 32 bits (4 bytes) | 16-bit, double CAS (page mode) | 2x |
| 11 | 64 bits (8 bytes) | 32-bit, double CAS | 4x |

Bits 3-2 (SPAGEM, SPR32) do the same for sprite data. Bits 15/14 (SSCAN2/BSCAN2) are scan
doubling, not fetch width.

- Which displays need what: lores up to 8 planes 1x; hires 5-8 planes 2x; superhires 3-4
  planes 2x, 5-8 planes 4x (AA mode tables; full table in
  [bitplanes and modes](bitplanes-and-modes.md)).
- Whether the machine can do it: the A1200 has a 32-bit chip bus and page-mode capable
  chip RAM (4x per the functional spec). Under the OS, `GfxBase->MemType` holds
  `BUS_32` (1) / `DBL_CAS` (2) -- the same bit values as FMODE bits 1-0 -- and the display
  database marks modes the memory cannot support (see [OS level](os-level.md)).
- For 2x pick the variant the machine supports (`MemType`); the SWOS AGA build measured
  below runs 8-plane lores at FMODE `$0001` (BPL32).
- howtocode (quoted in RandyAGA): with a fetch mode above 0 the copper list runs faster and
  leaves more time for the CPU and blitter; the blitter itself is not faster.

## Alignment and bitmap widths

- Every plane row must be a whole number of fetch units: 2, 4 or 8 bytes. A 320-pixel row
  (40 bytes) is fine for all three; a 2-byte scroll margin is not -- make it 8 bytes.
- Plane data must start on a 16/32/64-bit boundary for 1x/2x/4x (RandyAGA, quoting
  Commodore). Otherwise "the picture appears cut".
  - Assembler data: `CNOP 0,8` before `incbin` of planes and sprites.
  - OS: `AllocBitMap(..., BMF_DISPLAYABLE, ...)` (V39) allocates displayable, aligned planes.
  - exec rounds allocations to `MEM_BLOCKSIZE` (8, exec/memory.i), so `AllocMem` blocks are
    normally 8-byte aligned; RandyAGA still recommends AllocBitMap or allocating +8 bytes
    and skipping to the next 8-byte boundary.
- Separate allocations per plane keep each plane aligned; one big block needs a plane size
  that is a multiple of 8 bytes.

## DDFSTRT, DDFSTOP and modulos

The fetch window is still DDFSTRT/DDFSTOP, but data now arrives in larger units, so the
first unit has to be fetched further ahead of the first visible pixel:

- Yragael & Junkie (via RandyAGA), hires, with STARTX = the DIW horizontal start:
  16-bit fetch `DDFSTRT = (STARTX-9)/2`; 32-bit ("long burst") fetch
  `DDFSTRT = (STARTX-17)/2`. Reason: a hires word takes 4 colour clocks to fetch, a long
  8, plus half a clock.
- The same reasoning gives (derived, unverified -- check on the target):

| Fetch | lores | hires | superhires |
|---|---|---|---|
| 16-bit | (STARTX-17)/2 (the OCS formula) | (STARTX-9)/2 | (STARTX-5)/2 |
| 32-bit | (STARTX-33)/2 | (STARTX-17)/2 | (STARTX-9)/2 |
| 64-bit | (STARTX-65)/2 | (STARTX-33)/2 | (STARTX-17)/2 |

- Modulo = bitmap bytes per row - bytes fetched per line. RandyAGA's rule of thumb when
  keeping the 1x DDF values: modulo is 4 less with FMODE `$0002`, 8 less with `$0003`
  (normal 0 becomes -4 / -8), because the wide fetch reads one extra unit per line.
  Unverified in general: measure it.
- A measured working setup (AmigaScope `copper_disasm.py` on SWOS AGA): BPLCON0 `$0210`
  (8 planes lores), FMODE `$0001`, DDFSTRT `$0030`, DIWSTRT `$2471`, BPLCON1 `$8822`
  (34 lores pixels of fine scroll).
- Verify, do not guess: decode the live copper list and the displayed buffer with the
  AmigaScope tools (see the amigascope-workflow skill: `copper_disasm.py`,
  `fb_capture.py`), and the fetch start with `dma_profile.py`.

## Measured: 8-plane lores scrolling at FMODE=1

Facts established on cycle-exact FS-UAE with the AmigaScope tools while porting SWOS to
AGA (8 interleaved planes, 320-pixel lores playfield in a 352/384-pixel buffer). They are
emulator measurements, not checked on real hardware.

- **Plane pointers must be 32-pixel (4-byte) aligned at FMODE=1.** Moving a pointer by one
  2-byte word scrambled the whole display. Coarse scroll therefore moves in 32-pixel steps
  (`offset & ~3`) and everything below that goes into BPLCON1.
- **DDFSTRT must be aligned to 16 colour clocks at FMODE=1.** `$30` and `$20` work; the OCS
  fine-scroll value `$28` is invalid.
- **Longs fetched per line = (DDFSTOP - DDFSTRT) / 16 + 1:** `$30`-`$D0` fetched 11 longs
  (352 px), `$20`-`$D0` 12 longs (384 px).
- **Modulo = bytes from one line of a plane to the next line of the same plane, minus the
  bytes fetched.** With 44-byte planes interleaved 8 deep (352 bytes per line) and 44 bytes
  fetched: 308. It is razor-sharp: +-4 garbled the whole picture.
- **Fine scroll needs one extra long on the left.** A 32-bit fetch reads its first long
  early (RandyAGA's "long burst"), so a BPLCON1 delay shows pixels from before the pointer.
  The working set-up fetched 12 longs from DDFSTRT `$20`, pulled the pointer back one long
  (-4 bytes) and kept DDFSTRT/DDFSTOP constant; with a 32-pixel-aligned pointer and delay
  D in 16..31 lores px, screen x=0 showed pointer + (32 - D). Without the extra long the
  leftmost column showed pre-fetch colour-0 pixels.
- **BPLCON1 encoding for a lores delay D (0-63):** `lo = D & $F; h6 = (D>>4)&1;
  h7 = (D>>5)&1; BPLCON1 = lo | lo<<4 | h6<<10 | h6<<14 | h7<<11 | h7<<15` (both playfields;
  the AA bit layout in [BPLCON1](../registers/aga.md#bplcon1)). D = 34 gives `$8822`.
- **Incremental scroll must write whole fetch units.** Writing new tile columns on a
  16-pixel grid left half of each 32-pixel block stale, and the display showed it as a
  jump back at every block boundary. Update the full 4-byte block (both 16-pixel columns).
- **Whatever you put near a plane boundary is read twice.** An interleaved 44-byte plane
  row fetched 48 bytes at a time over-reads the first 4 bytes of the next plane's row. A
  scroll margin placed there serves two purposes at once; check both before writing it.
- **FMODE is global.** Every display on screen at the same time (split screens, menus
  shown between game frames) must use the same fetch mode, or switch it in the copper
  list in lock-step with the matching DDF/modulo/pointer values. The OCS 4-plane build
  kept FMODE=0.
- **FMODE=0 with 8 lores planes over a 352-pixel window intermittently lost planes 4-5**
  on FS-UAE (white lines turned blue); FMODE=1 fixed it. The AA spec says lores 8 planes
  needs only 1x bandwidth, so this may be emulator- or window-specific (see `errata.md`).

## Scroll range

BPLCON1 holds 0-255 in 35ns steps per playfield, but only one fetch unit is usable:

| Fetch | lores screen | hires screen | superhires screen |
|---|---|---|---|
| 1x (16-bit) | 0-15 lores px (0-63 steps) | 0-7 lores px (0-31) | 0-3 lores px (0-15) |
| 2x (32-bit) | 0-31 (0-127) | 0-15 (0-63) | 0-7 (0-31) |
| 4x (64-bit) | 0-63 (0-255) | 0-31 (0-127) | 0-15 (0-63) |

(AA spec table, ranges in lores pixels and in 35ns steps: exactly one fetch unit.) Scroll
further by moving the plane pointers a whole fetch unit and resetting BPLCON1.

## What breaks

- **OCS copper list, FMODE left non-zero by the OS** (after superhires, productivity,
  DblPAL screens): planes consume 4/8 bytes per fetch -> sheared, doubled or cut picture,
  wrong sprite data. Fix: `dc.w fmode,0` in every list.
- **FMODE set, data not aligned or rows not a multiple of the unit**: cut or shifted picture.
- **BSCAN2 left set**: BPL1MOD/BPL2MOD alternate by line instead of odd/even planes; dual
  playfield and per-playfield modulos break.
- **SSCAN2 left set**: SH10 is no longer a position bit; sprites past that position are
  misplaced and some are scan-doubled.
- **Wide sprite fetch left set** (SPR32/SPAGEM): sprite lists written as 16-bit words are
  read as longs; unused sprite pointers must point at enough zero data (RandyAGA: four
  zero longwords on a 64-bit boundary).

## Bitplane DMA vs sprite DMA: the sprite steal

Each hardware sprite's data is fetched in fixed DMA slots near the start of every line.
If the bitplane fetch has already started when a sprite's slot comes round, that sprite
gets no DMA and is not displayed. The HRM gives the OCS case: `DDFSTRT = $0030` (one word
early, for scrolling) disables sprite 7.

Measured with AmigaScope's DMA profiler (SWOS, AGA 8-plane lores, FMODE `$0001`):

| Sprite | DMA slots (recorder hpos) |
|---|---|
| n | $19+4n and $1B+4n |
| 0 | $19 / $1B |
| 3 | $25 / $27 |
| 6 | $31 / $33 |
| 7 | $35 / $37 |

- First bitplane DMA cycle on display lines at hpos **$34** -> sprite 7 lost (sprites 0-6 fine).
- First bitplane DMA cycle at hpos **$24** -> sprites 3, 4, 5, 6, 7 lost.
- Rule: a sprite is lost when either of its slots is at or after the fetch start.
- The first bitplane DMA cycle was measured at hpos **DDFSTRT + 4**, which gives:

| DDFSTRT | First fetch hpos | Sprites lost | Sprites 0-3 |
|---|---|---|---|
| `$20` | `$24` | 3-7 | sprite 3 lost (breaks a 2/3 attached pair) |
| `$28` | `$2C` | 4-7 (derived) | safe |
| `$30` | `$34` | 7 | safe |
| `$38` (standard lores) | `$3C` | none (derived) | safe |

- A wider fetch needs fewer DMA cycles per line, so its window can start later for the
  same number of planes. Moving 8 lores planes to FMODE=3 (64-bit, 4x) so that DDFSTRT can
  sit after the sprite slots is the proposed fix for the `$20` case above; it has not been
  measured.

What to do:

- Start the fetch as late as the display allows. Every extra unit of early fetch (wide
  FMODE, fine scroll margin, overscan) moves the start left over more sprite slots.
- Use sprites from 0 upwards; they are lost from 7 downwards.
- If the fetch must start early, draw those objects as bobs.
- Check it: `dma_profile.py parse` prints the fetch start, the slot map and a `STEAL` line
  naming the lost sprites; `dma_profile.py map` draws it (see the amigascope-workflow skill).
  Frames with active hardware sprites can stall the cycle-exact recorder; profile an
  equivalent frame without them (the slots are at fixed hpos).

## Blitter DMA on display lines

Also measured with the profiler (SWOS AGA pitch scroll): large blits (16x1024) that ran
past the vertical blank were still active on 59 display lines, and the live frame showed
a half-written column. Small blits that finished in the blank were clean.

- An 8-plane lores fetch uses almost all chip-bus DMA capacity during the visible lines;
  on that display only about 32-40 lines of blanking were available before the display
  started, while one frame's scroll maintenance needed about 90 lines of blitting. Budget
  blits against the blank, not the whole frame.
- DMACON BLTPRI ("blitter nasty") is not a fix: with it the blitter starved the bitplane
  fetch; without it the slow blit was still unfinished when the buffers were swapped.
- Finish big blits inside the vertical blank, split them over frames, or draw to a
  back buffer and swap plane pointers in the copper list.
- Signature to remember: the buffer decoded while halted is clean and a re-composited
  screenshot is clean, but the live frame shows the fault -> a real-time DMA/timing bug.
  Profile it; do not keep taking screenshots.
- Proof and regression test: `dma_profile.py` reports `CONTENTION` (blitter cells on
  display lines) and `blits` lists each blit's raster span with `OVERRUNS DISPLAY`.

## Common mistakes

- Turning on 2x/4x fetch "for speed" without aligning data and adjusting DDFSTRT/modulo.
- Forgetting `fmode,0` in OCS-style copper lists on AGA.
- Scrolling more than one fetch unit with BPLCON1 alone.
- Early DDFSTRT plus hardware sprites 4-7, then wondering where the sprites went.

**See also:** [FMODE](../registers/aga.md#fmode), [BPLCON1](../registers/aga.md#bplcon1), [sprites](sprites.md), [bitplanes and modes](bitplanes-and-modes.md)
