"""Starfish PSP Mps2 archive unpacker & repacker (Elminage Gothic ULJM06091)."""
from pathlib import Path
import struct

EBOOT_PATH = Path(r"C:\Users\Nikola\Desktop\ppsspp_win\memstick\PSP\SYSTEM\DUMP\ULJM06091_EBOOT.BIN")
_KEY_TBL_CACHE: tuple[int, ...] | None = None


def get_key_table() -> tuple[int, ...]:
    global _KEY_TBL_CACHE
    if _KEY_TBL_CACHE is None:
        eboot = EBOOT_PATH.read_bytes()
        _KEY_TBL_CACHE = struct.unpack_from("<256I", eboot, 0x16CC68 + 0xC0)
    return _KEY_TBL_CACHE


def _xor_entry_payload(blob: bytearray, off: int, sz: int, name: str) -> None:
    """Apply symmetric Mps2 entry XOR (first 32 bytes + filename-indexed bytes)."""
    key = ((~off & 0xFFFFFFFF) + sz) & 0xFFFFFFFF
    for k in range(min(8, sz // 4)):
        w = struct.unpack_from("<I", blob, k * 4)[0] ^ key
        struct.pack_into("<I", blob, k * 4, w)
        key = (key - 0x3E5) & 0xFFFFFFFF

    for ch in name.upper():
        c = ord(ch)
        pos = 0x20 + c * 7
        if pos < sz:
            blob[pos] ^= (~c) & 0xFF


def unpack_mps2(data: bytes) -> tuple[int, list[tuple[str, bytes]]]:
    """Return (header_w4, [(name, decrypted_payload), ...])."""
    if data[:4] != b"Mps2":
        raise ValueError(f"Expected Mps2 magic, got {data[:4]!r}")
    key_tbl = get_key_table()
    cnt = struct.unpack_from("<I", data, 4)[0]
    w4 = struct.unpack_from("<I", data, 16)[0]
    hdr_sz = 0x18 + cnt * 24
    hdr = bytearray(data[:hdr_sz])
    for i in range(6, hdr_sz // 4):
        w = struct.unpack_from("<I", hdr, i * 4)[0] ^ key_tbl[0xFF - (i & 0xFF)]
        struct.pack_into("<I", hdr, i * 4, w)

    entries: list[tuple[str, bytes]] = []
    for i in range(cnt):
        off, sz, raw_name = struct.unpack_from("<II16s", hdr, 0x18 + i * 24)
        name = raw_name.split(b"\x00")[0].decode("ascii")
        blob = bytearray(data[off : off + sz])
        _xor_entry_payload(blob, off, sz, name)
        entries.append((name, bytes(blob)))
    return w4, entries


def pack_mps2(entries: list[tuple[str, bytes]], w4: int = 0) -> bytes:
    """Pack [(name, plain_payload), ...] into a 2048-byte sector-aligned Mps2 archive."""
    key_tbl = get_key_table()
    cnt = len(entries)
    hdr_sz = 0x18 + cnt * 24
    first_data_off = ((hdr_sz + 2047) // 2048) * 2048

    hdr = bytearray(hdr_sz)
    struct.pack_into("<4s5I", hdr, 0, b"Mps2", cnt, 0, 0, w4, 0)

    out = bytearray(first_data_off)
    for i, (name, plain) in enumerate(entries):
        off = len(out)
        sz = len(plain)
        name_b = name.encode("ascii")[:16].ljust(16, b"\x00")
        struct.pack_into("<II16s", hdr, 0x18 + i * 24, off, sz, name_b)

        enc = bytearray(plain)
        _xor_entry_payload(enc, off, sz, name)
        out.extend(enc)
        pad = (-len(out)) % 2048
        if pad:
            out.extend(b"\x00" * pad)

    # Encrypt Mps2 header table
    for i in range(6, hdr_sz // 4):
        w = struct.unpack_from("<I", hdr, i * 4)[0] ^ key_tbl[0xFF - (i & 0xFF)]
        struct.pack_into("<I", hdr, i * 4, w)

    out[:hdr_sz] = hdr
    return bytes(out)
