"""Minimal round-trip test: port Steam S00.bra English CSVs into PSP ETC.BIN and build a test ISO for PPSSPP."""
from pathlib import Path
import shutil
import struct
import zlib
from mps2 import unpack_mps2, pack_mps2

ISO_ORIG = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\elminage\Elminage Gothic - Ulm Zakir to Yami no Gishiki (Japan).iso")
ISO_TEST = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\elminage\Elminage_Gothic_Test.iso")
STEAM_S00 = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Elminage Gothic\S00.bra")

# ISO9660 locations from our verified scan
USR_ETC_LBA = 159472
USR_ETC_SZ = 1888256


def load_steam_s00_csvs() -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    with STEAM_S00.open("rb") as f:
        _, _, toc_off, count = struct.unpack("<4sIII", f.read(16))
        f.seek(toc_off)
        toc = f.read()
        pos = 0
        for _ in range(count):
            _, _, csz, _, nlen, _, off = struct.unpack_from("<IIIIHHI", toc, pos)
            name = toc[pos + 24 : pos + 24 + nlen].split(b"\x00")[0].decode("ascii", "replace")
            pos += 24 + nlen
            if name.upper().endswith(".CSV"):
                f.seek(off)
                out[name.upper()] = zlib.decompress(f.read(csz)[16:], -15)
    return out


def main() -> None:
    steam_csvs = load_steam_s00_csvs()
    with ISO_ORIG.open("rb") as f:
        f.seek(USR_ETC_LBA * 2048)
        orig_etc = f.read(USR_ETC_SZ)

    w4, psp_entries = unpack_mps2(orig_etc)
    new_entries: list[tuple[str, bytes]] = []
    replaced = 0
    for name, p_blob in psp_entries:
        u = name.upper()
        if u in steam_csvs:
            # Use Steam's English CSV directly for this minimal round-trip test
            new_entries.append((name, steam_csvs[u]))
            replaced += 1
        else:
            new_entries.append((name, p_blob))

    new_etc = pack_mps2(new_entries, w4=w4)
    print(f"Repacked ETC.BIN: replaced={replaced}/47 CSVs, orig_sz={len(orig_etc)}, new_sz={len(new_etc)}")
    if len(new_etc) > USR_ETC_SZ:
        raise RuntimeError(f"new_etc ({len(new_etc)}) exceeds original slot ({USR_ETC_SZ})")

    print(f"Creating test ISO: {ISO_TEST} ...")
    shutil.copy2(ISO_ORIG, ISO_TEST)
    with ISO_TEST.open("r+b") as f:
        f.seek(USR_ETC_LBA * 2048)
        f.write(new_etc)
        if len(new_etc) < USR_ETC_SZ:
            f.write(b"\x00" * (USR_ETC_SZ - len(new_etc)))
    print("Done! Ready to test in PPSSPP.")


if __name__ == "__main__":
    main()
