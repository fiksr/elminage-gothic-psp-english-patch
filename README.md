# Elminage Gothic PSP (ULJM06091) — English Translation Patch

An `xdelta3` binary English translation patch for the Japanese PSP release of **Elminage Gothic: Ulm Zakir to Yami no Gishiki** (`ULJM06091`), porting the official Ghostlight Steam PC English localization onto the PSP ISO.

## Download & How to Apply (Windows)

Everything needed to patch your own Japanese ISO is in the [`release/`](release/) folder:
- `release/Elminage_Gothic_PSP_EN.xdelta` (3.84 MB)
- `release/apply_patch.bat`
- `release/xdelta3.exe`

1. Obtain a clean, unmodified Japanese UMD dump of **Elminage Gothic (Japan) [ULJM06091]**:
   - **Size:** `610,828,288` bytes
   - **MD5:** `287A287DC6FFA4BFD4FCC482842A08BD`
   - **SHA-1:** `746BA98F3E4D0D47D925D373F04258092E0D3CE1`
2. Drag and drop your Japanese `.iso` onto `release/apply_patch.bat`.
3. It will create `<ISO name> [EN].iso` next to your original file.
4. Boot the patched ISO in PPSSPP or on real PSP / PS Vita (Adrenaline) hardware.

## Important Notes

- **Data Install:** Choose **No** when prompted for Data Install. The optional `INSDIR/*.BIN` install archives are PGD-encrypted and untouched; keeping Data Install disabled ensures the game loads all patched `USRDIR` files.
- **PPSSPP Sharpness:** Increasing Rendering Resolution (e.g. 4× PSP) only upscales 3D polygon edges. To sharpen low-resolution PSP dungeon wall textures, enable **Graphics → Texture scaling** (e.g. `xBRZ` 2×–4×) and **Anisotropic Filtering**.

## Translation Source Transparency

- **Story & Event Dialogue (`Scenario.bin`, 4,169 lines):** 100% official Ghostlight Steam PC localization (wrapped with native `0x01 0x04` page breaks for ultra-long lines and dynamic-prefix support for runtime numbers/character names).
- **Game Data Tables (`ETC.BIN`, 22 CSVs / 5,800 cells):** 100% official Ghostlight Steam PC localization (items, spells, monsters, races, classes, dungeons, epithets, help text, Tarot, traps).
- **UI Atlases (`ANIME.BIN`, 14 `EL0*.GIM` sheets + 7×16 narrow `FONT10_16.GIM`):** Steam PC UI artwork rebuilt to PSP `.ANM` UVs, plus PSP-only UI labels rendered to match Steam terminology.
- **Executable (`EBOOT.BIN`, 1,111 `.rodata` strings + 81 stack-built prompts):** ~500 verbatim Steam PC `Elminage.exe` strings, 33 PSP-hardware-exclusive strings (Memory Stick, UMD, Data Install, PSP buttons), and ~658 short UI/combat/system strings adapted/translated for PSP screen constraints.

## Build Scripts (`scripts/`)

All patching scripts used to generate the ISO from the clean Japanese dump and Steam PC installation are included in [`scripts/`](scripts/):
- `patch_font.py` — generates the `7×16` narrow ASCII `FONT10_16.GIM`
- `patch_ui_gim.py` — rebuilds all 14 `EL0*.GIM` UI sprite atlases in `ANIME.BIN`
- `patch_etc.py` — merges 22 Steam CSVs into `ETC.BIN`
- `generate_eboot_translations.py` + `eboot_translations_extra.py` — generates `eboot_translations.json` with printf specifier parity checks
- `patch_eboot.py` — patches `EBOOT.BIN` strings, `PT_MIPS_PSPREL` relocations, `half_w = 7` font width, universal `Yes`/`No`, and the MIPS32 runtime hooks for `Scenario.bin` and stack-built prompts
