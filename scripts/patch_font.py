"""Generate a crisp 7x16 narrow ASCII + half-width kana FONT10_16.GIM and patch ANIME.BIN in Elminage_Gothic_Test.iso."""
from pathlib import Path
import struct
from PIL import Image, ImageDraw, ImageFont

from iso_patcher import _find_iso_entry
from mps2 import _xor_entry_payload, get_key_table
from patch_ui_gim import parse_gim_info

ISO_ORIG = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\elminage\Elminage Gothic - Ulm Zakir to Yami no Gishiki (Japan).iso")
ISO_TEST = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\elminage\Elminage_Gothic_Test.iso")
VERIFY_DIR = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\elminage\work\verify_gim")

FONT_PATH = Path(r"C:\Windows\Fonts\ARIALN.TTF")
NEW_HALF_W = 7
HALF_H = 16


def _unswizzle_index4(data: bytes, gw: int, gh: int) -> list[list[int]]:
    row_bytes = gw // 2
    unsw = bytearray(row_bytes * gh)
    idx = 0
    for ty in range(gh // 8):
        for tx in range(row_bytes // 16):
            for y in range(8):
                dst = (ty * 8 + y) * row_bytes + tx * 16
                unsw[dst : dst + 16] = data[idx : idx + 16]
                idx += 16
    pix = [[0] * gw for _ in range(gh)]
    for y in range(gh):
        for xb in range(row_bytes):
            b = unsw[y * row_bytes + xb]
            pix[y][xb * 2] = b & 0xF
            pix[y][xb * 2 + 1] = (b >> 4) & 0xF
    return pix


def _swizzle_index4(pix: list[list[int]], gw: int, gh: int) -> bytes:
    row_bytes = gw // 2
    linear = bytearray(row_bytes * gh)
    for y in range(gh):
        row = pix[y]
        for xb in range(row_bytes):
            linear[y * row_bytes + xb] = (row[xb * 2] & 0xF) | ((row[xb * 2 + 1] & 0xF) << 4)
    out = bytearray(row_bytes * gh)
    idx = 0
    for ty in range(gh // 8):
        for tx in range(row_bytes // 16):
            for y in range(8):
                src = (ty * 8 + y) * row_bytes + tx * 16
                out[idx : idx + 16] = linear[src : src + 16]
                idx += 16
    return bytes(out)


def _render_ascii_glyph_7x16(ch: str, font: ImageFont.FreeTypeFont, baseline_y: int = 13) -> list[list[int]]:
    """Render a printable ASCII char into a 7x16 4-bit alpha grid aligned to baseline_y=13."""
    if ch == " ":
        return [[0] * NEW_HALF_W for _ in range(HALF_H)]

    # Render using anchor='ls' (left baseline) at x=8, y=baseline_y on a clean canvas
    cw, ch_h = 28, 20
    img = Image.new("L", (cw, ch_h), 0)
    draw = ImageDraw.Draw(img)
    draw.text((8, baseline_y), ch, fill=255, font=font, anchor="ls")

    bbox = img.getbbox()
    if not bbox:
        return [[0] * NEW_HALF_W for _ in range(HALF_H)]

    gx0, gy0, gx1, gy1 = bbox
    g_w = gx1 - gx0
    # Crop vertically to [0..16) around baseline_y, horizontally tightly to [gx0..gx1)
    crop = img.crop((gx0, 0, gx1, HALF_H))

    max_w = NEW_HALF_W - 1  # keep column dx=6 completely blank so glyphs never touch
    if g_w > max_w:
        crop = crop.resize((max_w, HALF_H), Image.Resampling.LANCZOS)
        g_w = max_w

    # Boost midtones slightly so thin 1px strokes remain solid after 4-bit quantization
    cell = [[0] * NEW_HALF_W for _ in range(HALF_H)]
    x_pad = (max_w - g_w) // 2
    px = crop.load()
    for y in range(HALF_H):
        for dx in range(g_w):
            a = px[dx, y]
            if a > 24:
                boosted = int(min(255, ((a - 24) / 231.0) ** 0.58 * 255.0))
                lvl = min(15, max(2, (boosted + 8) // 17))
                cell[y][x_pad + dx] = lvl
    return cell


def build_font10_16(orig_gim: bytes) -> tuple[bytes, list[list[int]]]:
    pal_off, gfmt, gorder, gw, gh, img_off = parse_gim_info(orig_gim)
    if gfmt != 4 or gorder != 1 or (gw, gh) != (256, 128):
        raise ValueError(f"Unexpected FONT10_16 format: gfmt={gfmt}, gorder={gorder}, size={gw}x{gh}")

    orig_pix = _unswizzle_index4(orig_gim[img_off : img_off + (gw // 2) * gh], gw, gh)
    new_pix = [[0] * gw for _ in range(gh)]

    font = ImageFont.truetype(str(FONT_PATH), 15)
    old_cols = gw // 10
    new_cols = gw // NEW_HALF_W  # 256 // 7 = 36

    # 1. Render crisp 7x16 ASCII glyphs for slots 0..94 (0x20..0x7E)
    for slot in range(0x7F - 0x20):
        ch = chr(0x20 + slot)
        glyph = _render_ascii_glyph_7x16(ch, font, baseline_y=13)
        nx = (slot % new_cols) * NEW_HALF_W
        ny = (slot // new_cols) * HALF_H
        for dy in range(HALF_H):
            new_pix[ny + dy][nx : nx + NEW_HALF_W] = glyph[dy]

    # 2. Preserve slots >= 95 (half-width katakana etc.) scaled cleanly from 10x16 to 7x16
    for slot in range(0x7F - 0x20, 192):
        ox = (slot % old_cols) * 10
        oy = (slot // old_cols) * HALF_H
        g_img = Image.new("L", (10, HALF_H), 0)
        gp = g_img.load()
        for dy in range(HALF_H):
            for dx in range(10):
                gp[dx, dy] = orig_pix[oy + dy][ox + dx] * 17
        g_res = g_img.resize((NEW_HALF_W, HALF_H), Image.Resampling.LANCZOS)
        grp = g_res.load()
        nx = (slot % new_cols) * NEW_HALF_W
        ny = (slot // new_cols) * HALF_H
        for dy in range(HALF_H):
            for dx in range(NEW_HALF_W):
                a = grp[dx, dy]
                new_pix[ny + dy][nx + dx] = min(15, (a + 8) // 17)

    swizzled = _swizzle_index4(new_pix, gw, gh)
    out_gim = bytearray(orig_gim)
    out_gim[img_off : img_off + len(swizzled)] = swizzled
    return bytes(out_gim), new_pix


def _save_preview_images(new_pix: list[list[int]]) -> None:
    VERIFY_DIR.mkdir(parents=True, exist_ok=True)
    # 1. Full 2x zoomed sheet on dark background
    sheet = Image.new("RGBA", (256, 128), (24, 16, 32, 255))
    sp = sheet.load()
    for y in range(128):
        for x in range(256):
            v = new_pix[y][x]
            if v > 0:
                a = v * 17
                c = 40 + (v * 215) // 15
                sp[x, y] = (c, c, c, 255)
    sheet.resize((512, 256), Image.Resampling.NEAREST).save(VERIFY_DIR / "patched_FONT10_16.png")

    # 2. Simulated 480px PSP dialogue box preview (380px inner box -> 54 chars at 7px)
    prev = Image.new("RGBA", (420, 100), (12, 12, 16, 255))
    pp = prev.load()
    new_cols = 256 // NEW_HALF_W

    def draw_str(s: str, x0: int, y0: int) -> None:
        x = x0
        for ch in s:
            slot = ord(ch) - 0x20
            if 0 <= slot < 95:
                gx = (slot % new_cols) * NEW_HALF_W
                gy = (slot // new_cols) * HALF_H
                for dy in range(HALF_H):
                    for dx in range(NEW_HALF_W):
                        v = new_pix[gy + dy][gx + dx]
                        if v > 0:
                            cur = pp[x + dx, y0 + dy]
                            w = v / 15.0
                            r = int(cur[0] * (1 - w) + 253 * w)
                            g = int(cur[1] * (1 - w) + 244 * w)
                            b = int(cur[2] * (1 - w) + 244 * w)
                            pp[x + dx, y0 + dy] = (r, g, b, 255)
            x += NEW_HALF_W

    # Draw 396px marker box border
    for x in range(10, 406):
        pp[x, 6] = (90, 80, 60, 255)
        pp[x, 92] = (90, 80, 60, 255)
    for y in range(6, 93):
        pp[10, y] = (90, 80, 60, 255)
        pp[405, y] = (90, 80, 60, 255)

    draw_str("To the east of the continent was the Kingdom of Ishmag.", 14, 12)
    draw_str("Ishmag Kingdom  |  Caves of Tsun-Kurn  |  LV 4 Bishop", 14, 32)
    draw_str("0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ !?\"'-:.,/()", 14, 52)
    draw_str("abcdefghijklmnopqrstuvwxyz  @%$&*()[]+=<>", 14, 72)
    prev.resize((840, 200), Image.Resampling.NEAREST).save(VERIFY_DIR / "patched_FONT10_16_preview.png")


def main() -> None:
    with ISO_ORIG.open("rb") as f:
        _, orig_lba, orig_sz = _find_iso_entry(f, "PSP_GAME/USRDIR/ANIME.BIN")
        f.seek(orig_lba * 2048)
        key_tbl = get_key_table()
        d = f.read(65536)
        cnt = struct.unpack_from("<I", d, 4)[0]
        hdr_sz = 0x18 + cnt * 24
        if hdr_sz > len(d):
            f.seek(orig_lba * 2048)
            d = f.read(hdr_sz)
        hdr = bytearray(d[:hdr_sz])
        for i in range(6, hdr_sz // 4):
            struct.pack_into("<I", hdr, i * 4, struct.unpack_from("<I", hdr, i * 4)[0] ^ key_tbl[0xFF - (i & 0xFF)])
        orig_font = None
        for i in range(cnt):
            off, sz, rn = struct.unpack_from("<II16s", hdr, 0x18 + i * 24)
            name = rn.split(b"\x00")[0].decode("ascii", "replace")
            if name.upper() == "FONT10_16.GIM":
                f.seek(orig_lba * 2048 + off)
                buf = bytearray(f.read(sz))
                _xor_entry_payload(buf, off, sz, name)
                orig_font = bytes(buf)
                break
    if orig_font is None:
        raise FileNotFoundError("FONT10_16.GIM not found in ISO_ORIG")

    patched_font, new_pix = build_font10_16(orig_font)
    _save_preview_images(new_pix)

    with ISO_TEST.open("r+b") as f:
        _, test_lba, _ = _find_iso_entry(f, "PSP_GAME/USRDIR/ANIME.BIN")
        f.seek(test_lba * 2048)
        d = f.read(65536)
        cnt = struct.unpack_from("<I", d, 4)[0]
        hdr_sz = 0x18 + cnt * 24
        if hdr_sz > len(d):
            f.seek(test_lba * 2048)
            d = f.read(hdr_sz)
        hdr = bytearray(d[:hdr_sz])
        for i in range(6, hdr_sz // 4):
            struct.pack_into("<I", hdr, i * 4, struct.unpack_from("<I", hdr, i * 4)[0] ^ key_tbl[0xFF - (i & 0xFF)])
        wrote = False
        for i in range(cnt):
            off, sz, rn = struct.unpack_from("<II16s", hdr, 0x18 + i * 24)
            name = rn.split(b"\x00")[0].decode("ascii", "replace")
            if name.upper() == "FONT10_16.GIM":
                if sz != len(patched_font):
                    raise ValueError(f"Size mismatch: {sz} != {len(patched_font)}")
                buf = bytearray(patched_font)
                _xor_entry_payload(buf, off, sz, name)
                f.seek(test_lba * 2048 + off)
                f.write(buf)
                wrote = True
                break
        if not wrote:
            raise FileNotFoundError("FONT10_16.GIM not found in ISO_TEST")

    print(f"Patched FONT10_16.GIM ({len(patched_font)} bytes, 7x16 cell) in USRDIR/ANIME.BIN")


if __name__ == "__main__":
    main()
