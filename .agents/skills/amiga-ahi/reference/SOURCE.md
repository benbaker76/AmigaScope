# Sources (not redistributed)

The entries and guides were distilled (rewritten, not copied) from the documents below. AHI
is free software (LGPL/GPL, Martin Blom), but the same rewrite policy as the other skills
was applied; no source documents are included.

- **AHI 6.0 developer archive** (`m68k-amigaos-ahidev.lha`): `Docs/ahi.doc` and
  `ahi_sub.doc` (autodocs), `ahidev.guide` (developer guide), `Include/C/devices/ahi.h`,
  `libraries/ahi_sub.h`, `Include/Asm/devices/ahi.i`, `Include/SFD/ahi_lib.sfd` and
  `ahi_sub_lib.sfd`, `Examples/` (Device, Low-level, Extras), `Drivers/` sources.
- **AHI 6.0 user archive** (`m68k-amigaos-ahiusr.lha`): `ahiusr.guide`.
- **AHI 4 source** (`ahisrc.tar.gz`, 1999) - autodoc comments in `Device/sound.c` for
  AHI_SetVol, AHI_SetFreq, AHI_SetSound and AHI_SetEffect, which the 6.0 autodoc omits.
- **"Aros/Developer/AHIDrivers"** (Wikibooks page capture) - application-side AHI usage
  notes.

The fact blocks and `data/ahi.tsv` / `data/ahi_sub.tsv` are generated from the SFD files by
`tools/skills/amiga_skill_data.py` and match the archive's `lvo/*.i` headers. Example code
was not compiled against the AHI headers.
