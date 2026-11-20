"""Port Steam UI sprite atlases cleanly into PSP USRDIR/ANIME.BIN using exact PSP UV rectangles."""
import io
from pathlib import Path
import struct
import zlib
from PIL import Image, ImageDraw, ImageFont

from iso_patcher import _find_iso_entry
from mps2 import _xor_entry_payload, get_key_table

ISO_ORIG = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\elminage\Elminage Gothic - Ulm Zakir to Yami no Gishiki (Japan).iso")
STEAM_S00 = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Elminage Gothic\S00.bra")
ISO_TEST = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\elminage\Elminage_Gothic_Test.iso")
VERIFY_DIR = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\elminage\work\verify_gim")

FONT_NARROW = Path(r"C:\Windows\Fonts\ARIALN.TTF")
FONT_NARROW_B = Path(r"C:\Windows\Fonts\ARIALNB.TTF")

BEIGE = (255, 224, 201, 255)
WHITE = (245, 245, 245, 255)


def load_steam_el0_dds() -> dict[str, bytes]:
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
            up = name.upper()
            if up.startswith("EL0") and up.endswith(".DDS"):
                f.seek(off)
                out[up.replace(".DDS", ".GIM")] = zlib.decompress(f.read(csz)[16:], -15)
    return out


def parse_gim_info(gim: bytes) -> tuple[int, int, int, int, int, int]:
    """Return (pal_off, gfmt, gorder, gw, gh, img_data_off)."""
    pal_off = -1
    img_info = None
    p = 0x30
    while p + 16 < len(gim):
        cid, _, cnext, _ = struct.unpack_from("<HHII", gim, p)
        if cid == 5:
            pal_off = p + 0x10 + struct.unpack_from("<I", gim, p + 0x2C)[0]
        elif cid == 4:
            gfmt, gorder, gw, gh = struct.unpack_from("<HHHH", gim, p + 0x14)
            img_data_off = p + 0x10 + struct.unpack_from("<I", gim, p + 0x2C)[0]
            img_info = (gfmt, gorder, gw, gh, img_data_off)
            break
        if cnext == 0:
            break
        p += cnext
    if pal_off == -1 or img_info is None:
        raise ValueError("Missing GIM PALETTE or IMAGE chunk")
    return (pal_off, *img_info)


def encode_rgba_to_gim(gim: bytearray, rgba_img: Image.Image) -> None:
    """Quantize RGBA image to 256-color RGBA8888 palette + INDEX8 pixels inside GIM buffer."""
    pal_off, gfmt, gorder, gw, gh, img_data_off = parse_gim_info(gim)
    if gfmt != 5:
        raise ValueError(f"Expected INDEX8 gfmt=5, got {gfmt}")

    resized = rgba_img.resize((gw, gh), Image.Resampling.LANCZOS) if rgba_img.size != (gw, gh) else rgba_img
    q = resized.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    pal_rgba = bytes(q.getpalette("RGBA"))
    if len(pal_rgba) < 1024:
        pal_rgba = pal_rgba + b"\x00" * (1024 - len(pal_rgba))
    gim[pal_off : pal_off + 1024] = pal_rgba[:1024]

    indices = q.tobytes()
    if gorder == 0:
        end = img_data_off + gw * gh
        gim[img_data_off:end] = indices
    elif gorder == 1:
        pitch = (gw + 15) & ~15
        rows = []
        for y in range(gh):
            row = indices[y * gw : (y + 1) * gw]
            if pitch > gw:
                row += b"\x00" * (pitch - gw)
            rows.append(row)
        out_pix = bytearray()
        for ty in range(gh // 8):
            for tx in range(pitch // 16):
                x0 = tx * 16
                for y in range(8):
                    r = rows[ty * 8 + y]
                    out_pix.extend(r[x0 : x0 + 16])
        gim[img_data_off : img_data_off + len(out_pix)] = out_pix
    else:
        raise ValueError(f"Unsupported GIM image_order={gorder}")


def decode_gim_to_rgba(gim: bytes) -> Image.Image:
    """Decode decrypted GIM (gfmt=5 INDEX8) back to an RGBA Image for verification."""
    pal_off, gfmt, gorder, gw, gh, doff = parse_gim_info(gim)
    if gfmt != 5:
        raise ValueError(f"Expected gfmt=5, got {gfmt}")
    pal = [tuple(gim[pal_off + i * 4 : pal_off + i * 4 + 4]) for i in range(256)]
    pix = bytearray(gw * gh * 4)
    if gorder == 0:
        for i in range(gw * gh):
            pix[i * 4 : i * 4 + 4] = bytes(pal[gim[doff + i]])
    else:
        pitch = (gw + 15) & ~15
        src = doff
        for ty in range(gh // 8):
            for tx in range(pitch // 16):
                for y in range(8):
                    for x in range(16):
                        px = tx * 16 + x
                        py = ty * 8 + y
                        idx = gim[src]
                        src += 1
                        if px < gw and py < gh:
                            o = (py * gw + px) * 4
                            pix[o : o + 4] = bytes(pal[idx])
    return Image.frombytes("RGBA", (gw, gh), bytes(pix))


def _clear_box(img: Image.Image, box: tuple[int, int, int, int], mode: str, pad_x: int = 2, pad_y: int = 1) -> None:
    x0, y0, x1, y1 = box
    px = img.load()
    if mode == "clear":
        for y in range(y0, y1):
            for x in range(x0, x1):
                px[x, y] = (0, 0, 0, 0)
    elif mode == "strip":
        samples = [
            px[x, y]
            for y in range(y0, y1)
            for x in range(x0, x1)
            if min(px[x, y][1], px[x, y][2]) < 75 and px[x, y][3] > 20
        ]
        bg = samples[len(samples) // 2] if samples else (38, 38, 38, 128)
        for y in range(y0, y1):
            for x in range(x0, x1):
                px[x, y] = bg
    elif mode == "bar":
        # Preserve capsule/button borders at top/bottom/left/right; sample dark/red background per scanline
        ix0 = min(x1 - 1, x0 + pad_x)
        ix1 = max(ix0 + 1, x1 - pad_x)
        iy0 = min(y1 - 1, y0 + pad_y)
        iy1 = max(iy0 + 1, y1 - pad_y)
        for y in range(iy0, iy1):
            row_bg = [
                px[x, y]
                for x in range(ix0, ix1)
                if min(px[x, y][1], px[x, y][2]) < 85 and px[x, y][3] > 180
            ]
            if row_bg:
                row_bg.sort(key=lambda c: c[0] + c[1] + c[2])
                fill = row_bg[len(row_bg) // 2]
            else:
                fill = (20, 20, 20, 255)
            for x in range(ix0, ix1):
                px[x, y] = fill


def _draw_label(
    img: Image.Image,
    uvwh: tuple[int, int, int, int],
    text: str,
    fg: tuple[int, int, int, int] = BEIGE,
    mode: str = "clear",
    max_pt: int = 10,
    bold: bool = False,
    pad_x: int = 1,
    pad_y: int = 1,
    align: str = "center",
    shadow: bool | None = None,
) -> None:
    if shadow is None:
        shadow = mode == "bar"
    u, v, w, h = uvwh
    box = (u, v, u + w, v + h)
    _clear_box(img, box, mode, pad_x=pad_x if mode == "bar" else 0, pad_y=pad_y if mode == "bar" else 0)
    avail_w = max(4, w - pad_x * 2)
    avail_h = max(6, h - (2 if mode == "bar" else 0))

    fpath = str(FONT_NARROW_B if bold else FONT_NARROW)
    chosen_font = None
    tw = th = 0
    for pt in range(max_pt, 6, -1):
        f = ImageFont.truetype(fpath, pt)
        bb = f.getbbox(text, anchor="lt")
        if (bb[2] - bb[0]) <= avail_w and (bb[3] - bb[1]) <= avail_h + 1:
            chosen_font = f
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            break

    if chosen_font is None:
        chosen_font = ImageFont.truetype(fpath, 7)
        # Render slightly wider then compress horizontally so nothing ever spills outside UV box
        tmp_w = max(avail_w, int(chosen_font.getlength(text)) + 6)
        tmp = Image.new("RGBA", (tmp_w, h * 2), (0, 0, 0, 0))
        td = ImageDraw.Draw(tmp)
        td.text((tmp_w // 2, h), text, font=chosen_font, fill=fg, anchor="mm")
        bb = tmp.getbbox()
        if bb:
            crop = tmp.crop(bb)
            nw = min(avail_w, crop.width)
            nh = min(avail_h, crop.height)
            res = crop.resize((nw, nh), Image.Resampling.LANCZOS)
            dx = u + (w - nw) // 2 if align == "center" else u + pad_x
            dy = v + (h - nh) // 2
            if shadow:
                sh = Image.new("RGBA", res.size, (0, 0, 0, 0))
                sp = sh.load(); rp = res.load()
                for yy in range(nh):
                    for xx in range(nw):
                        if rp[xx, yy][3] > 60:
                            sp[xx, yy] = (0, 0, 0, min(200, rp[xx, yy][3]))
                img.alpha_composite(sh, (dx + 1, dy + 1))
            img.alpha_composite(res, (dx, dy))
        return

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    cx = w // 2 if align == "center" else pad_x
    anch = "mm" if align == "center" else "lm"
    cy = h // 2
    if shadow:
        od.text((cx + 1, cy + 1), text, font=chosen_font, fill=(0, 0, 0, 210), anchor=anch)
    od.text((cx, cy), text, font=chosen_font, fill=fg, anchor=anch)
    img.alpha_composite(overlay, (u, v))


def patch_el01_000(orig_psp: Image.Image, steam_img: Image.Image) -> Image.Image:
    out = steam_img.resize(orig_psp.size, Image.Resampling.LANCZOS).convert("RGBA")
    # Restore crisp PSP NAME / STYLE LOAD / FACE LOAD (y=247..280) so Steam's taller FACE LOAD never slices y>=280
    # and Steam's SPELL RESIST / DEFENSE ATT (y=236..246) stay untouched.
    crop_ctrl = orig_psp.crop((384, 247, 512, 280))
    out.paste(crop_ctrl, (384, 247))

    # Top-right equipment / combat / alignment labels
    rects = [
        ((342, 120, 48, 12), "Acts", "clear", 10),
        ((390, 120, 48, 12), "WpnBrk", "clear", 10),
        ((438, 120, 48, 12), "ArmBrk", "clear", 10),
        ((342, 132, 48, 12), "Breath", "clear", 10),
        ((390, 132, 32, 12), "Rng:", "clear", 10),  # keep ∞ icon at 422..438!
        ((438, 132, 48, 12), "Flee", "clear", 10),
        ((342, 144, 48, 12), "Summon", "clear", 10),
        ((390, 144, 36, 12), "Main", "clear", 10),
        ((426, 144, 36, 12), "Sub", "clear", 10),
        ((462, 144, 36, 12), "Head", "clear", 10),
        ((342, 156, 36, 12), "Body", "clear", 10),
        ((378, 156, 36, 12), "Hand", "clear", 10),
        ((414, 156, 36, 12), "Foot", "clear", 10),
        ((450, 156, 36, 12), "Acc1", "clear", 10),
        ((342, 168, 36, 12), "Acc2", "clear", 10),
        ((378, 168, 24, 12), "Type", "clear", 10),
        ((402, 168, 48, 12), "AC Mod", "clear", 10),
        ((450, 168, 48, 12), "Range", "clear", 10),
        ((342, 180, 48, 12), "Accuracy", "clear", 10),
        ((390, 180, 48, 12), "Damage", "clear", 10),
        ((450, 180, 50, 12), "Hits", "clear", 10),
        ((390, 194, 17, 15), "G", "clear", 10),
        ((407, 194, 27, 15), "N", "clear", 10),
        ((434, 194, 17, 15), "E", "clear", 10),
        ((382, 267, 26, 12), "Title", "clear", 10),
        # Character sheet labels y=280..438 (exact .ANM UV rects!)
        ((312, 280, 72, 12), "Nickname", "clear", 10),
        ((384, 280, 24, 12), "Race", "clear", 10),
        ((408, 280, 24, 12), "Sex", "clear", 10),
        ((432, 280, 24, 12), "Age", "clear", 10),
        ((456, 280, 24, 12), "Aln", "clear", 10),
        ((480, 280, 24, 12), "Job", "clear", 10),
        ((336, 292, 24, 12), "STR", "clear", 10),
        ((384, 292, 24, 12), "Stat", "clear", 10),
        ((408, 292, 24, 12), "Dead", "clear", 10),
        ((480, 292, 24, 12), "STR", "clear", 10),
        ((288, 304, 24, 12), "INT", "clear", 10),
        ((312, 304, 24, 12), "PIE", "clear", 10),
        ((336, 304, 24, 12), "VIT", "clear", 10),
        ((360, 304, 24, 12), "AGI", "clear", 10),
        ((384, 304, 24, 12), "LUK", "clear", 10),
        ((408, 304, 68, 12), "Recovery %", "clear", 10),
        ((476, 304, 12, 12), "x", "clear", 10),
        ((488, 304, 24, 12), "Kill", "clear", 10),
        ((288, 316, 44, 12), "Mage", "clear", 10),
        ((332, 316, 44, 12), "Priest", "clear", 10),
        ((376, 316, 44, 12), "Alchem", "clear", 10),
        ((420, 316, 44, 12), "Summ", "clear", 10),
        ((288, 328, 32, 16), "Add", "bar", 10),
        ((320, 328, 32, 16), "Back", "bar", 10),
        ((352, 328, 68, 12), "Regen", "clear", 10),  # keep % at 420..432
        ((432, 328, 28, 12), "Main", "clear", 10),
        ((460, 328, 28, 12), "Sub", "clear", 10),
        ((288, 344, 144, 12), "HP Item Condition", "clear", 10),
        ((466, 338, 42, 12), "Breath", "clear", 10),
        ((288, 356, 48, 12), "SplRes", "clear", 10),
        ((336, 356, 48, 12), "ElmAtk", "clear", 10),
        ((384, 356, 48, 12), "ElmDef", "clear", 10),
        ((432, 356, 34, 12), "Slay", "clear", 10),
        ((288, 368, 12, 12), "Fr", "clear", 9),
        ((300, 368, 12, 12), "Ic", "clear", 9),
        ((312, 368, 12, 12), "Lg", "clear", 9),
        ((324, 368, 24, 12), "Hol", "clear", 9),
        ((348, 368, 24, 12), "Drk", "clear", 9),
        ((372, 368, 24, 12), "Mag", "clear", 9),
        ((396, 368, 24, 12), "Pri", "clear", 9),
        ((420, 368, 24, 12), "Alc", "clear", 9),
        ((444, 368, 24, 12), "Sum", "clear", 9),
        ((468, 368, 30, 12), "Name", "clear", 10),
        # 2-line race/class slayer grid (288..512, 380..428)
        ((290, 380, 15, 24), "Mg", "clear", 9),
        ((305, 380, 16, 24), "Un", "clear", 9),
        ((321, 380, 16, 24), "Sp", "clear", 9),
        ((337, 380, 16, 24), "In", "clear", 9),
        ((353, 380, 16, 24), "An", "clear", 9),
        ((369, 380, 16, 24), "My", "clear", 9),
        ((385, 380, 16, 24), "Dm", "clear", 9),
        ((401, 380, 16, 24), "Dg", "clear", 9),
        ((417, 380, 16, 24), "Fg", "clear", 9),
        ((433, 380, 16, 24), "Mz", "clear", 9),
        ((449, 380, 16, 24), "Pr", "clear", 9),
        ((465, 380, 16, 24), "Th", "clear", 9),
        ((481, 380, 16, 24), "Bs", "clear", 9),
        ((497, 380, 14, 24), "Gn", "clear", 9),
        ((290, 404, 16, 24), "Gt", "clear", 9),
        ((306, 404, 16, 24), "Gd", "clear", 9),
        ((322, 404, 46, 12), "Main", "clear", 9),
        ((370, 404, 54, 12), "Sub", "clear", 9),
        ((426, 404, 40, 12), "Res", "clear", 9),
        ((466, 404, 44, 12), "Drain", "clear", 9),
        ((322, 417, 24, 12), "Slp", "clear", 9),
        ((346, 417, 24, 12), "Psn", "clear", 9),
        ((370, 417, 24, 12), "Par", "clear", 9),
        ((394, 417, 24, 12), "Sil", "clear", 9),
        ((418, 417, 24, 12), "Cnf", "clear", 9),
        ((442, 417, 24, 12), "Chm", "clear", 9),
        ((466, 417, 24, 12), "Pet", "clear", 9),
        ((288, 428, 36, 12), "Behead", "clear", 9),
    ]
    for rect, txt, mode, pt in rects:
        fg = WHITE if mode == "bar" else BEIGE
        _draw_label(out, rect, txt, fg=fg, mode=mode, max_pt=pt)
    return out


def patch_el02_000(orig_psp: Image.Image) -> Image.Image:
    # Keep PSP base so every header capsule matches exact PSP UVs and high-contrast white-on-black styling!
    out = orig_psp.copy().convert("RGBA")
    rects = [
        # Remaining JP black capsule headers
        ((384, 30, 53, 12), "ACTIVATE", "bar", 9),
        ((387, 60, 53, 12), "UNLOCK", "bar", 9),
        ((352, 156, 64, 12), "MONSTER", "bar", 9),
        ((402, 140, 62, 12), "ADVENTURER", "bar", 9),
        ((278, 216, 192, 10), "SPELL LIST", "bar", 9),
        # Ore labels top right
        ((438, 30, 42, 12), "Ore2", "clear", 10),
        ((438, 42, 42, 12), "Ore1", "clear", 10),
        # Beige labels y=80..180
        ((0, 80, 200, 12), "Proc / Resist Rate (%)", "clear", 10),
        ((200, 80, 28, 12), "Max", "clear", 10),
        ((228, 80, 26, 12), "Main", "clear", 10),
        ((254, 80, 24, 12), "Sub", "clear", 10),
        ((278, 80, 24, 12), "Rng", "clear", 10),
        ((302, 80, 28, 12), "Curse", "clear", 10),
        ((332, 80, 72, 12), "All AC Mod", "clear", 10),
        ((404, 80, 48, 12), "Spl Res", "clear", 10),
        ((0, 92, 36, 12), "Invest", "clear", 10),
        ((36, 92, 36, 12), "Exp EP", "clear", 10),
        ((72, 92, 48, 12), "Unident.", "clear", 10),
        ((120, 92, 60, 12), "AC Lower", "clear", 10),
        ((180, 92, 48, 12), "Stat Unlock", "clear", 10),
        ((228, 92, 26, 12), "Sex", "clear", 10),
        ((254, 92, 28, 12), "Race", "clear", 10),
        ((282, 92, 30, 12), "Align", "clear", 10),
        ((312, 92, 72, 12), "Atk +1", "clear", 10),
        ((384, 92, 58, 12), "Spd Mod", "clear", 10),  # keep % at 444..456
        ((0, 104, 60, 12), "Spd Bonus", "clear", 10),
        ((60, 104, 60, 12), "Base Wpn", "clear", 10),
        ((120, 104, 24, 12), "Refine", "clear", 10),
        ((144, 104, 24, 12), "Ore", "clear", 10),
        ((186, 104, 140, 12), "Proc / Resist (%)", "bar", 10),
        ((326, 104, 72, 12), "DrainBarrier", "clear", 10),
        ((398, 104, 46, 12), "Release", "clear", 10),
        ((0, 116, 48, 12), "Res1", "clear", 10),
        ((48, 116, 24, 12), "Res2", "clear", 10),
        ((72, 116, 24, 12), "Atk", "clear", 10),
        ((96, 116, 24, 12), "AC", "clear", 10),
        ((120, 116, 24, 12), "HP", "clear", 10),
        ((144, 116, 24, 12), "Atk", "clear", 10),
        ((168, 116, 24, 12), "AC", "clear", 10),
        ((192, 116, 24, 12), "HP", "clear", 10),
        ((216, 116, 48, 12), "Age Inp", "clear", 10),
        ((276, 116, 48, 12), "Bonus", "clear", 10),
        ((324, 116, 72, 12), "BreathBarrier", "clear", 10),
        ((396, 116, 48, 12), "Draw Rate", "clear", 10),
        ((0, 128, 72, 12), "Whs Usage", "clear", 10),
        ((72, 128, 36, 12), "Stored", "clear", 10),
        ((108, 128, 48, 12), "Sex Sel", "clear", 10),
        ((156, 128, 48, 12), "AlignSel", "clear", 10),
        ((216, 128, 40, 12), "Mage", "clear", 10),
        ((260, 128, 40, 12), "Priest", "clear", 10),
        ((300, 128, 44, 12), "Alchem", "clear", 10),
        ((350, 128, 38, 12), "Summ", "clear", 10),
        ((392, 128, 64, 12), "Hits Left", "clear", 10),
        ((130, 140, 62, 16), "Sell / Buy", "clear", 11),
        ((160, 156, 48, 12), "Bonus", "clear", 10),
        ((208, 156, 48, 12), "Rec Rate", "clear", 10),
        ((256, 156, 48, 12), "Regen", "clear", 10),
        ((304, 156, 48, 12), "Resist", "clear", 10),
        ((418, 156, 46, 12), "Gold", "clear", 10),
        ((160, 168, 48, 12), "Expect.", "clear", 10),
        ((208, 168, 101, 12), "Tri: Sort Asc.", "clear", 9),
        ((309, 168, 101, 12), "Sq: Sort Desc.", "clear", 9),
        ((372, 191, 78, 13), "Skill Uses", "clear", 10),
        ((372, 203, 80, 13), "SP / Cost Cur", "clear", 10),
        # Face icon + Face Load (116..162, 230..278)
        ((116, 230, 46, 24), "Face Icon", "bar", 9),
        ((116, 254, 46, 24), "Face Load", "bar", 9),
    ]
    for rect, txt, mode, pt in rects:
        fg = WHITE if mode == "bar" else BEIGE
        _draw_label(out, rect, txt, fg=fg, mode=mode, max_pt=pt)

    # 16-col Monster Type short codes at x=160..384, y=232..256 (each col 14px)
    mtypes = ["Mg", "Un", "Sp", "In", "An", "My", "Gh", "Dm", "Dg", "Fg", "Ma", "Pr", "Th", "Bs", "Gt", "Gd"]
    for i, mt in enumerate(mtypes):
        _draw_label(out, (160 + i * 14, 232, 14, 24), mt, fg=BEIGE, mode="strip", max_pt=9)
    return out


def patch_el03_000(orig_psp: Image.Image) -> Image.Image:
    out = orig_psp.copy().convert("RGBA")

    # 1. Save / Record / Rare / Roster headers + Party Panel + Options screen (left side x=0..336)
    bars = [
        ((416, 10, 72, 12), "OFF", "bar", 10),
        # Save/Load screen top row (y=30)
        ((0, 30, 118, 12), "CURRENT DATA", "bar", 9),
        ((118, 30, 53, 12), "SAVE DATA", "bar", 9),
        ((184, 30, 72, 12), "RARE RATE UP", "bar", 9),
        ((256, 30, 47, 12), "ROSTER", "bar", 9),
        ((303, 30, 61, 12), "PLAY TIME", "bar", 9),
        ((364, 30, 72, 12), "ITEMS FOUND", "bar", 9),
        ((436, 30, 72, 12), "FOES MET", "bar", 9),
        ((0, 42, 72, 12), "EVENTS DONE:", "clear", 9),
        ((90, 42, 24, 12), "Run", "clear", 9),
        ((170, 42, 24, 12), "Stat", "clear", 9),
        ((0, 54, 288, 12), "PARTY PANEL SETTINGS", "bar", 9),
        # World Map Monster Alert (text sits at x=12..116, y=332..348; keep gauge x=116..202)
        ((12, 331, 104, 17), "MONSTER ALERT", "bar", 10),
        # Lower-right Settings Labels
        ((349, 279, 120, 12), "STYLE LOAD IMPORT", "bar", 9),
        ((349, 292, 120, 12), "AUTO-HEAL INJURED", "bar", 9),
        ((120, 306, 288, 12), "STYLE DISPLAY SETTINGS", "bar", 9),
        ((16, 370, 120, 12), "FACE LOAD IMPORT", "bar", 9),
        ((318, 386, 120, 12), "TOWN FACILITY", "bar", 9),
        ((280, 398, 120, 12), "STATUS DISPLAY", "clear", 9),
        ((280, 410, 120, 12), "COMBAT", "clear", 9),
        ((276, 422, 56, 14), "FAME", "clear", 9),
        ((333, 422, 120, 12), "PASSWORD", "bar", 9),
        ((333, 434, 120, 12), "NEXT ERA'S BOOK", "bar", 9),
        ((350, 446, 72, 12), "INPUT", "bar", 9),
        ((276, 449, 62, 14), "SEARCH", "bar", 9),
    ]
    for rect, txt, mode, pt in bars:
        _draw_label(out, rect, txt, fg=WHITE, mode=mode, max_pt=pt)

    # 2. Options Table Left Labels (0, 66..318, 120, 12) + Right Toggle Buttons (120..336, 66..318)
    opt_labels = [
        (66, "Nickname Display"), (78, "BGM Volume"), (90, "SE Volume"),
        (102, "Help Msg Anim"), (114, "Dialogue Speed"), (126, "Remember Cursor"),
        (138, "KO Voice"), (150, "Ally Side SE"), (162, "Enemy Side SE"),
        (174, "Battle Effects"), (186, "Backup Display"), (198, "Combat Msg Speed"),
        (210, "Rename Spells"), (222, "Enemy Spells Too"), (234, "Combat Log Style"),
        (246, "Combat Log Name"), (258, "D-Pad Down Action"), (270, "Move Animation"),
        (282, "Clock Display"), (294, "Party Panel"), (306, "Minimap Facing"),
        (318, "Minimap Size"),
    ]
    for y, lbl in opt_labels:
        _draw_label(out, (0, y, 120, 12), lbl, fg=WHITE, mode="bar", max_pt=9)

    opt_toggles = [
        ((120, 66, 120, 12), "HP/AC Display"), ((240, 66, 72, 12), "ON"),
        ((240, 78, 72, 12), "ON"),
        ((120, 90, 72, 12), "YES"), ((192, 90, 72, 12), "NO"), ((264, 90, 48, 12), "LARGE"),
        ((120, 102, 72, 12), "REMEMBER ALL"), ((192, 102, 72, 12), "DEFAULT"), ((264, 102, 48, 12), "LARGE"),
        ((120, 114, 120, 12), "HP/AC Display"), ((264, 114, 48, 12), "SMALL"),
        ((264, 126, 48, 12), "SMALL"),
        ((120, 138, 72, 12), "YES"), ((192, 138, 72, 12), "NO"), ((264, 138, 48, 12), "NONE"),
        ((120, 150, 72, 12), "REMEMBER ALL"), ((192, 150, 72, 12), "DEFAULT"), ((264, 150, 48, 12), "NONE"),
        ((120, 162, 72, 12), "CHANGE"), ((192, 162, 72, 12), "NO CHANGE"), ((264, 162, 72, 12), "OFF"),
        ((120, 174, 72, 12), "CURTAIN"), ((192, 174, 72, 12), "WINDOW"),
        ((120, 186, 72, 12), "REAL NAME"), ((192, 186, 72, 12), "NICKNAME"),
        ((120, 198, 72, 12), "CHANGE"), ((192, 198, 72, 12), "NO CHANGE"),
        ((120, 210, 72, 12), "CURTAIN"), ((192, 210, 72, 12), "WINDOW"),
        ((120, 222, 72, 12), "REAL NAME"), ((192, 222, 72, 12), "NICKNAME"),
        ((192, 234, 72, 12), "KEEP"), ((264, 234, 72, 12), "NO BLUE"), ((336, 234, 72, 12), "NORTH UP"),
        ((192, 246, 72, 12), "KEEP"), ((264, 246, 72, 12), "NO BLUE"), ((336, 246, 72, 12), "DIR. UP"),
        ((120, 258, 72, 12), "TURN BACK"), ((192, 258, 72, 12), "STEP BACK"),
        ((120, 270, 72, 12), "NORTH UP"), ((192, 270, 72, 12), "DIR. UP"),
        ((192, 282, 72, 12), "MAX"),
        ((120, 294, 72, 12), "TURN BACK"), ((192, 294, 72, 12), "STEP BACK"),
        ((192, 318, 72, 12), "MAX"),
    ]
    for rect, txt in opt_toggles:
        _draw_label(out, rect, txt, fg=WHITE, mode="bar", max_pt=9)

    # 3. Automap Legend (note keep left 12px icon inside each box, replace text part only!)
    legend_l = [
        (62, "Position"), (74, "Entrance"), (86, "Event"), (98, "Spring"),
        (110, "Door"), (122, "Locked Door"), (134, "Event Door"), (146, "Monster"),
        (158, "Stone Wall"), (170, "Dark Zone"), (182, "Water/Slide"),
        (194, "Anti-Magic"), (206, "Dead Party"), (218, "No Teleport"),
    ]
    for idx, (y, lbl) in enumerate(legend_l):
        bw = 152 if y >= 182 else 82
        _draw_label(out, (358, y, bw, 12), lbl, fg=WHITE, mode="bar", max_pt=9, pad_x=2, align="left")

    legend_r = [
        (62, "Stairs Up"), (74, "Stairs Down"), (86, "Conveyor"), (98, "Spinner"),
        (110, "Damage Floor"), (122, "Chute"), (134, "Pit"), (146, "Warp"),
        (158, "Escape Warp"), (170, "Floor Master"),
    ]
    for y, lbl in legend_r:
        _draw_label(out, (455, y, 57, 12), lbl, fg=WHITE, mode="bar", max_pt=8, pad_x=2, align="left")

    return out


def patch_small_steam_extras(up: str, orig_psp: Image.Image, steam_img: Image.Image) -> Image.Image:
    out = steam_img.resize(orig_psp.size, Image.Resampling.LANCZOS).convert("RGBA")
    if up == "EL01_002.GIM":
        for rect, txt in [
            ((402, 0, 94, 15), "Tarot Eff."),
            ((402, 15, 58, 16), "Weather"),
            ((402, 31, 46, 16), "Fire"),
            ((402, 47, 46, 16), "Ice"),
            ((402, 63, 46, 16), "Lgt"),
        ]:
            _draw_label(out, rect, txt, fg=BEIGE, mode="clear", max_pt=10, align="left")
    elif up == "EL02_004.GIM":
        # Replace Display / Translucent / Hide toggle pills (black and red rows)
        for y in (154, 166):
            _draw_label(out, (120, y, 48, 12), "Show", fg=WHITE, mode="bar", max_pt=9)
            _draw_label(out, (168, y, 48, 12), "Trans.", fg=WHITE, mode="bar", max_pt=9)
            _draw_label(out, (216, y, 48, 12), "Hide", fg=WHITE, mode="bar", max_pt=9)
    elif up == "EL03_003.GIM":
        _draw_label(out, (340, 316, 64, 14), "Fame", fg=BEIGE, mode="clear", max_pt=10, align="left")
    return out


def main() -> None:
    steam_dds = load_steam_el0_dds()
    print(f"Loaded {len(steam_dds)} EL0*.dds files from S00.bra")
    key_tbl = get_key_table()

    # Load clean original PSP EL0* GIMs from ISO_ORIG
    orig_gims: dict[str, bytes] = {}
    with ISO_ORIG.open("rb") as f:
        _, orig_lba, _ = _find_iso_entry(f, "PSP_GAME/USRDIR/ANIME.BIN")
        f.seek(orig_lba * 2048)
        d = f.read(65536)
        cnt = struct.unpack_from("<I", d, 4)[0]
        hdr_sz = 0x18 + cnt * 24
        if hdr_sz > len(d):
            f.seek(orig_lba * 2048)
            d = f.read(hdr_sz)
        hdr = bytearray(d[:hdr_sz])
        for i in range(6, hdr_sz // 4):
            struct.pack_into("<I", hdr, i * 4, struct.unpack_from("<I", hdr, i * 4)[0] ^ key_tbl[0xFF - (i & 0xFF)])
        for i in range(cnt):
            off, sz, rn = struct.unpack_from("<II16s", hdr, 0x18 + i * 24)
            name = rn.split(b"\x00")[0].decode("ascii", "replace")
            up = name.upper()
            if up.startswith("EL0") and up.endswith(".GIM"):
                f.seek(orig_lba * 2048 + off)
                buf = bytearray(f.read(sz))
                _xor_entry_payload(buf, off, sz, name)
                orig_gims[up] = bytes(buf)

    with ISO_TEST.open("r+b") as f:
        _, anime_lba, _ = _find_iso_entry(f, "PSP_GAME/USRDIR/ANIME.BIN")
        f.seek(anime_lba * 2048)
        d = f.read(65536)
        cnt = struct.unpack_from("<I", d, 4)[0]
        hdr_sz = 0x18 + cnt * 24
        if hdr_sz > len(d):
            f.seek(anime_lba * 2048)
            d = f.read(hdr_sz)
        hdr = bytearray(d[:hdr_sz])
        for i in range(6, hdr_sz // 4):
            w = struct.unpack_from("<I", hdr, i * 4)[0] ^ key_tbl[0xFF - (i & 0xFF)]
            struct.pack_into("<I", hdr, i * 4, w)

        VERIFY_DIR.mkdir(parents=True, exist_ok=True)
        patched = 0
        verify_targets: list[tuple[str, int, int]] = []
        for i in range(cnt):
            off, sz, rn = struct.unpack_from("<II16s", hdr, 0x18 + i * 24)
            name = rn.split(b"\x00")[0].decode("ascii", "replace")
            up = name.upper()
            if up not in orig_gims:
                continue

            gim = bytearray(orig_gims[up])
            orig_im = decode_gim_to_rgba(gim)

            if up in ("EL03_001.GIM", "EL03_002.GIM"):
                # Keep original PSP graphics untouched (automap icons & exact match)
                rgba_out = orig_im
            elif up == "EL01_000.GIM":
                stm_im = Image.open(io.BytesIO(steam_dds[up])).convert("RGBA")
                rgba_out = patch_el01_000(orig_im, stm_im)
            elif up == "EL02_000.GIM":
                rgba_out = patch_el02_000(orig_im)
            elif up == "EL03_000.GIM":
                rgba_out = patch_el03_000(orig_im)
            else:
                stm_im = Image.open(io.BytesIO(steam_dds[up])).convert("RGBA")
                rgba_out = patch_small_steam_extras(up, orig_im, stm_im)

            if up not in ("EL03_001.GIM", "EL03_002.GIM"):
                encode_rgba_to_gim(gim, rgba_out)

            _xor_entry_payload(gim, off, sz, name)
            f.seek(anime_lba * 2048 + off)
            f.write(gim)
            patched += 1
            if up in ("EL01_000.GIM", "EL01_002.GIM", "EL02_000.GIM", "EL02_004.GIM", "EL03_000.GIM", "EL03_001.GIM", "EL03_003.GIM"):
                verify_targets.append((name, off, sz))
        print(f"Patched/restored {patched}/14 EL0*.GIM atlases in USRDIR/ANIME.BIN (lba={anime_lba})")

        for name, off, sz in verify_targets:
            f.seek(anime_lba * 2048 + off)
            gim = bytearray(f.read(sz))
            _xor_entry_payload(gim, off, sz, name)
            im = decode_gim_to_rgba(gim)
            out_png = VERIFY_DIR / f"patched_{name}.png"
            im.save(out_png)
            print(f"Verified read-back {name} ({im.size}) -> {out_png}")


if __name__ == "__main__":
    main()
