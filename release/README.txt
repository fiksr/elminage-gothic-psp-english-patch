Elminage Gothic PSP (ULJM06091) - English Patch (xdelta3)
=========================================================

Files in this release folder:
  - Elminage_Gothic_PSP_EN.xdelta   (3.84 MB binary patch)
  - apply_patch.bat                 (Windows drag-and-drop patcher)
  - xdelta3.exe                     (xdelta3 v3.1.0 x64)

Required Source ISO (unmodified Japanese UMD dump):
  - Title : Elminage Gothic - Ulm Zakir to Yami no Gishiki (Japan) [ULJM06091]
  - Size  : 610,828,288 bytes
  - MD5   : 287A287DC6FFA4BFD4FCC482842A08BD
  - SHA-1 : 746BA98F3E4D0D47D925D373F04258092E0D3CE1

How to Patch (Windows):
  1. Drag and drop your clean Japanese ISO onto apply_patch.bat.
  2. It will create "<ISO name> [EN].iso" next to your original ISO.
  3. Boot the patched ISO in PPSSPP or on PSP / PS Vita (Adrenaline).

How to Play on Real PSP / PS Vita (Adrenaline):
  - Requires Custom Firmware (ARK-4, PRO-C, or LME) on PSP, or Adrenaline on Vita.
  - PSP: Copy patched ISO to ms0:/ISO/Elminage_Gothic_EN.iso
  - PS Vita (Adrenaline): Copy patched ISO to ux0:pspemu/ISO/Elminage_Gothic_EN.iso
  - Launch from Game -> Memory Stick on the XMB.
  - If needed, set UMD ISO MODE to Inferno in the VSH menu (SELECT on XMB).

Important Notes:
  - Data Install: Select NO if prompted for Data Install. The optional
    INSDIR/*.BIN install archives are PGD-encrypted and untouched; keeping
    Data Install off ensures the game loads all patched USRDIR files.
  - PPSSPP Sharpness: Setting Rendering Resolution to 4x PSP only upscales
    3D geometry edges. To sharpen dungeon wall textures, enable
    Graphics -> Texture scaling (e.g. xBRZ 2x-4x) and Anisotropic Filtering.

Translation Source Breakdown:
  - Event dialogue (4,169 lines in Scenario.bin): 100% Official Ghostlight PC
    (Steam) localization.
  - Game data tables (5,800 cells across 22 CSVs in ETC.BIN): 100% Official
    Ghostlight PC (Steam) localization.
  - UI graphics (14 EL0*.GIM atlases): Official Steam PC UI artwork adapted to
    PSP UVs, plus PSP-only labels (Options, Automap Legend, Monster Alert,
    Character Status headers) rendered to match Steam terminology.
  - Executable (EBOOT.BIN: 1,111 .rodata strings + 81 stack-built prompts):
    Official Steam PC strings where present (~500 verbatim matches), plus
    33 PSP-hardware-exclusive strings (Memory Stick / UMD / Data Install /
    PSP buttons) and ~658 short UI/combat/system strings adapted/translated
    for PSP screen constraints.
