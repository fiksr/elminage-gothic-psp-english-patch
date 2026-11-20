"""Column-safe ETC.BIN CSV merger: preserves all PSP columns, numeric rows, and Shift-JIS formatting."""
import csv
import io
from pathlib import Path
import struct
import zlib

from iso_patcher import patch_iso_file
from mps2 import pack_mps2, unpack_mps2

ISO_ORIG = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\elminage\Elminage Gothic - Ulm Zakir to Yami no Gishiki (Japan).iso")
ISO_TEST = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\elminage\Elminage_Gothic_Test.iso")
STEAM_S00 = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Elminage Gothic\S00.bra")

USR_ETC_LBA = 159472
USR_ETC_SZ = 1888256


def clean_en(s: str) -> str:
    return (
        s.replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2026", "...")
        .replace("\xa0", " ")
        .replace("\x85", "...")
        .replace("\x91", "'")
        .replace("\x92", "'")
        .replace("\x93", '"')
        .replace("\x94", '"')
        .replace("\x96", "-")
        .replace("\x97", "-")
    )


def is_valid_en(s: str) -> bool:
    st = s.strip()
    if not st or "??" in st or "\ufffd" in st:
        return False
    return any("a" <= ch.lower() <= "z" for ch in st)


def parse_csv(b: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(b.decode("cp932", errors="replace"))))


def dump_csv(rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerows(rows)
    return buf.getvalue().encode("cp932", errors="replace")


def parse_int(s: str) -> int | None:
    st = s.strip()
    if st.isdigit():
        return int(st)
    return None


def index_rows_by_col(rows: list[list[str]], id_col: int, start_row: int = 0) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for r in rows[start_row:]:
        if id_col < len(r):
            rid = parse_int(r[id_col])
            if rid is not None and rid not in out:
                out[rid] = r
    return out


def merge_by_id(
    psp_rows: list[list[str]],
    stm_rows: list[list[str]],
    psp_id_col: int,
    stm_id_col: int,
    col_map: list[tuple[int, int]],
    start_row: int = 1,
    append_suffix: dict[int, str] | None = None,
    overrides: dict[int, dict[int, str]] | None = None,
) -> int:
    stm_by_id = index_rows_by_col(stm_rows, stm_id_col)
    replaced = 0
    for r in psp_rows[start_row:]:
        if psp_id_col >= len(r):
            continue
        rid = parse_int(r[psp_id_col])
        if rid is None:
            continue
        sr = stm_by_id.get(rid)
        if not sr:
            continue
        row_ovr = overrides.get(rid, {}) if overrides else {}
        for pc, sc in col_map:
            if pc >= len(r) or sc >= len(sr):
                continue
            val = row_ovr.get(pc)
            if val is None:
                cand = clean_en(sr[sc])
                if not is_valid_en(cand):
                    continue
                val = cand
                if append_suffix and pc in append_suffix:
                    val = val.rstrip() + append_suffix[pc]
            r[pc] = val
            replaced += 1
    return replaced


def merge_transposed_matrix(
    psp_rows: list[list[str]], stm_rows: list[list[str]], id_row: int, target_rows: list[int]
) -> int:
    if len(psp_rows) <= max(target_rows) or len(stm_rows) <= max(target_rows):
        return 0
    # Build Steam col map by horizontal ID in id_row (fallback to same column index)
    stm_col_by_id: dict[int, int] = {}
    for c, v in enumerate(stm_rows[id_row]):
        if c >= 4:
            vid = parse_int(v)
            if vid is not None:
                stm_col_by_id[vid] = c

    replaced = 0
    for pc in range(4, len(psp_rows[id_row])):
        pid = parse_int(psp_rows[id_row][pc])
        sc = stm_col_by_id.get(pid) if pid is not None else None
        if sc is None and pc < len(stm_rows[id_row]):
            sc = pc
        if sc is None:
            continue
        for rr in target_rows:
            if pc < len(psp_rows[rr]) and sc < len(stm_rows[rr]):
                cand = clean_en(stm_rows[rr][sc])
                if is_valid_en(cand):
                    psp_rows[rr][pc] = cand
                    replaced += 1
    return replaced


def load_steam_csvs() -> dict[str, bytes]:
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


def merge_csv(name_up: str, p_blob: bytes, s_blob: bytes) -> tuple[bytes, int]:
    """Return (merged_csv_bytes, replaced_cell_count)."""
    pr = parse_csv(p_blob)
    sr = parse_csv(s_blob)
    cnt = 0

    if name_up == "HELP_TEXT.CSV":
        cnt = merge_by_id(
            pr, sr, psp_id_col=8, stm_id_col=7,
            col_map=[(10, 9)], start_row=4,
            append_suffix={10: "   "},
        )
    elif name_up == "PLACE_NM.CSV":
        cnt = merge_by_id(
            pr, sr, psp_id_col=0, stm_id_col=0,
            col_map=[(2, 2)], start_row=4,
            overrides={1: {2: "Ishmag Kingdom"}},
        )
    elif name_up == "ITEM.CSV":
        cnt = merge_by_id(pr, sr, psp_id_col=0, stm_id_col=0, col_map=[(4, 4), (5, 5)], start_row=7)
    elif name_up == "ITEM_HELP.CSV":
        cnt = merge_by_id(pr, sr, psp_id_col=0, stm_id_col=0, col_map=[(1, 1), (3, 3)], start_row=5)
    elif name_up == "ITEM_PRIZ.CSV":
        cnt = merge_by_id(pr, sr, psp_id_col=1, stm_id_col=0, col_map=[(3, 2), (4, 3)], start_row=4)
    elif name_up == "SPELL.CSV":
        for p_ri, s_ri in zip(range(1, 6), range(0, 5)):
            if len(pr[p_ri]) > 4 and len(sr[s_ri]) > 4 and is_valid_en(sr[s_ri][4]):
                pr[p_ri][4] = clean_en(sr[s_ri][4])
                cnt += 1
        cnt += merge_by_id(
            pr, sr, psp_id_col=0, stm_id_col=0,
            col_map=[(1, 1), (3, 3), (4, 4), (5, 5)], start_row=9,
        )
    elif name_up == "SPELL_TEXT.CSV":
        cnt = merge_by_id(pr, sr, psp_id_col=0, stm_id_col=0, col_map=[(1, 1), (3, 3), (4, 4)], start_row=5)
    elif name_up == "SP_TEXT.CSV":
        cnt = merge_by_id(pr, sr, psp_id_col=0, stm_id_col=0, col_map=[(1, 1), (2, 2), (3, 3), (4, 4)], start_row=4)
    elif name_up == "EVENT_TEXT.CSV":
        cnt = merge_by_id(pr, sr, psp_id_col=0, stm_id_col=0, col_map=[(2, 2), (6, 6), (7, 7), (8, 8)], start_row=1)
    elif name_up == "JOB_EX.CSV":
        cnt = merge_by_id(pr, sr, psp_id_col=1, stm_id_col=0, col_map=[(2, 1), (3, 2)], start_row=4)
    elif name_up == "TRAP.CSV":
        cnt = merge_by_id(pr, sr, psp_id_col=1, stm_id_col=0, col_map=[(2, 1), (3, 2), (4, 3)], start_row=4)
    elif name_up == "RACE.CSV":
        cnt = merge_by_id(pr, sr, psp_id_col=0, stm_id_col=0, col_map=[(1, 1)], start_row=4)
    elif name_up == "DGN_NAME.CSV":
        cnt = merge_by_id(pr, sr, psp_id_col=0, stm_id_col=0, col_map=[(1, 1), (2, 2), (4, 4)], start_row=3)
    elif name_up == "DGN_SET.CSV":
        cnt = merge_by_id(pr, sr, psp_id_col=0, stm_id_col=0, col_map=[(1, 1)], start_row=3)
    elif name_up == "BGM_NAME.CSV":
        cnt = merge_by_id(pr, sr, psp_id_col=0, stm_id_col=0, col_map=[(2, 2), (4, 4)], start_row=4)
    elif name_up == "TAROT_TEXT.CSV":
        cnt = merge_by_id(pr, sr, psp_id_col=0, stm_id_col=0, col_map=[(1, 1), (2, 2), (3, 3)], start_row=4)
    elif name_up == "RENKIN_TXT.CSV":
        cnt = merge_by_id(pr, sr, psp_id_col=0, stm_id_col=0, col_map=[(1, 1), (3, 3)], start_row=1)
    elif name_up == "MSP_TEXT.CSV":
        cnt = merge_by_id(pr, sr, psp_id_col=0, stm_id_col=0, col_map=[(1, 1), (2, 2)], start_row=4)
    elif name_up in ("MONSTER1.CSV", "MONSTER2.CSV", "MONSTER3.CSV"):
        cnt = merge_transposed_matrix(pr, sr, id_row=5, target_rows=[6, 7, 8])
    elif name_up == "PLAYER.CSV":
        cnt = merge_transposed_matrix(pr, sr, id_row=5, target_rows=[6, 7, 8])
    else:
        return p_blob, 0

    return dump_csv(pr), cnt


def main() -> None:
    steam_csvs = load_steam_csvs()
    with ISO_ORIG.open("rb") as f:
        f.seek(USR_ETC_LBA * 2048)
        orig_etc = f.read(USR_ETC_SZ)

    w4, psp_entries = unpack_mps2(orig_etc)
    new_entries: list[tuple[str, bytes]] = []
    total_cells = 0
    merged_files = 0
    for name, p_blob in psp_entries:
        u = name.upper()
        if u in steam_csvs:
            out_blob, cnt = merge_csv(u, p_blob, steam_csvs[u])
            new_entries.append((name, out_blob))
            if cnt > 0:
                merged_files += 1
                total_cells += cnt
                print(f"  {name:16s}: merged {cnt:4d} EN cells (PSP cols/rows preserved)")
        else:
            new_entries.append((name, p_blob))

    new_etc = pack_mps2(new_entries, w4=w4)
    print(f"Repacked ETC.BIN: {merged_files} CSVs merged ({total_cells} cells), size={len(new_etc)}/{USR_ETC_SZ}")
    patch_iso_file(ISO_TEST, "PSP_GAME/USRDIR/ETC.BIN", new_etc)


if __name__ == "__main__":
    main()
