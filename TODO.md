# AmigaScope — TODO

These tools were extracted from a Sensible World of Soccer Amiga port, so a few
project-specific assumptions are still baked in. Turning them into first-class,
documented config is the main work to make AmigaScope truly general.

## Generalization (de-SWOS-ify)

- [ ] **`cpu_flamegraph.py`** — default ELF path (`SWOS_ELF`) and `.text` VMA
      (`0x100000`) are SWOS-specific. Promote to required `--elf` arg; auto-read the
      `.text` VMA/size from the ELF instead of the hard-coded fallback.
- [ ] **`dma_profile.py`** — the display window (`DISPLAY_VLO/VHI = 36..307`), sprite
      slot map, and pitch geometry are the SWOS AGA lores mode. Make the vertical
      window + fetch/sprite geometry configurable (or derive from the copper list).
- [ ] **`amiga_gdb.sh`** — launch defaults (`KICKSTART`, `DH0`, hard drives, `:SWOS2`
      trigger) are SWOS. Move to a `.env` / config file with documented keys.
- [ ] Rename `SWOS_ELF` → `AMIGASCOPE_ELF` (keep the old name as a fallback alias).

## Packaging

- [ ] Decide a home for the scripts (flat root vs `bin/`) and a `pyproject.toml` /
      console-scripts entry so `pip install -e .` gives `amigascope-dma` etc.
- [x] FlameGraph renderer bundled as a submodule in `third_party/FlameGraph` (keeps its
      own upstream license).
- [x] `LICENSE` — MIT.

## Features

- [ ] Full hierarchical stacks depend on a DWARF `.debug_frame` unwind table; document
      the `capture` flow and fall back gracefully (flat profile) when unavailable.
- [ ] Band-path (active hardware-sprite) frames stall the cycle-exact recorder — a
      possible FS-UAE-side fix (the recorder never completes the frame). Until then,
      profile the equivalent bob/no-sprite frame; the sprite DMA slots are hpos-fixed
      so the fetch-vs-slot overlap is still fully visible.
- [ ] A single `amigascope` front-end command that dispatches to the sub-tools.
