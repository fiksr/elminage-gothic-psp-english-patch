"""ISO9660 in-place or append-with-directory-update patcher for PSP ISOs."""
from pathlib import Path
import struct


def _find_iso_entry(iso_file, target_path: str) -> tuple[int, int, int]:
    """Return (dir_record_file_off, lba, size) for target_path like 'PSP_GAME/SYSDIR/EBOOT.BIN'."""
    parts = [p.upper() for p in target_path.strip("/").split("/")]
    iso_file.seek(16 * 2048)
    pvd = iso_file.read(2048)
    cur_lba = struct.unpack_from("<I", pvd, 156 + 2)[0]
    cur_sz = struct.unpack_from("<I", pvd, 156 + 10)[0]

    for depth, part in enumerate(parts):
        iso_file.seek(cur_lba * 2048)
        data = iso_file.read(cur_sz)
        pos = 0
        found = None
        while pos < len(data):
            rec_len = data[pos]
            if rec_len == 0:
                pos = ((pos // 2048) + 1) * 2048
                continue
            elba = struct.unpack_from("<I", data, pos + 2)[0]
            esz = struct.unpack_from("<I", data, pos + 10)[0]
            nlen = data[pos + 32]
            name = data[pos + 33 : pos + 33 + nlen].decode("ascii", "replace").split(";")[0].upper()
            if name == part:
                found = (cur_lba * 2048 + pos, elba, esz)
                break
            pos += rec_len
        if found is None:
            raise FileNotFoundError(f"Path {target_path} not found in ISO (missing {part})")
        if depth == len(parts) - 1:
            return found
        cur_lba, cur_sz = found[1], found[2]
    raise RuntimeError("Unreachable")


def patch_iso_file(iso_path: Path, target_path: str, new_data: bytes) -> None:
    """Replace target_path in ISO9660 image (in-place if it fits, otherwise append & update dir record + PVD)."""
    with iso_path.open("r+b") as f:
        rec_off, orig_lba, orig_sz = _find_iso_entry(f, target_path)
        orig_sectors = (orig_sz + 2047) // 2048
        new_sz = len(new_data)
        new_sectors = (new_sz + 2047) // 2048

        if new_sectors <= orig_sectors:
            new_lba = orig_lba
            f.seek(new_lba * 2048)
            f.write(new_data)
            rem = orig_sectors * 2048 - new_sz
            if rem:
                f.write(b"\x00" * rem)
        else:
            f.seek(0, 2)
            end_off = f.tell()
            pad = (-end_off) % 2048
            if pad:
                f.write(b"\x00" * pad)
                end_off += pad
            new_lba = end_off // 2048
            f.write(new_data)
            pad2 = (-new_sz) % 2048
            if pad2:
                f.write(b"\x00" * pad2)
            # Update Primary Volume Descriptor Volume Space Size (offset 80: LE + BE u32)
            total_sectors = (f.tell()) // 2048
            f.seek(16 * 2048 + 80)
            f.write(struct.pack("<I", total_sectors))
            f.write(struct.pack(">I", total_sectors))

        # Update directory record LBA (LE+BE at +2, +6) and Size (LE+BE at +10, +14)
        f.seek(rec_off + 2)
        f.write(struct.pack("<I", new_lba))
        f.write(struct.pack(">I", new_lba))
        f.write(struct.pack("<I", new_sz))
        f.write(struct.pack(">I", new_sz))
        print(f"ISO patched {target_path}: lba {orig_lba}->{new_lba}, size {orig_sz}->{new_sz}")
