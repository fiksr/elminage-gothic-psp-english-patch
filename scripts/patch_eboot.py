"""Patch decrypted PSP ULJM06091_EBOOT.BIN strings with in-place + PT_MIPS_PSPREL PHDR[1] relocation,
universal Yes/No dialog patch, and MIPS32 Scenario.bin runtime hook."""
import json
from pathlib import Path
import struct
import zlib

from iso_patcher import patch_iso_file

ORIG_EBOOT = Path(r"C:\Users\Nikola\Desktop\ppsspp_win\memstick\PSP\SYSTEM\DUMP\ULJM06091_EBOOT.BIN")
TRANS_JSON = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\elminage\work\eboot_translations.json")
OUT_EBOOT = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\elminage\work\EBOOT_patched.BIN")
STEAM_S00 = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Elminage Gothic\S00.bra")
ISO_TEST = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\elminage\Elminage_Gothic_Test.iso")

CAVE_START = 0x784E8
CAVE_END = 0x787B0
ORIG_DECODE_VA = 0xB8A90
SCENARIO_MAX_LINE_BYTES = 56

SCENARIO_OVERRIDES: dict[bytes, bytes] = {
    "日経過しました".encode("cp932"): b" day(s) passed.",
}

INLINE_PROMPT_TRANSLATIONS: dict[str, str] = {
    # 0x3B240 confirmation prompts (33)
    "確認用メッセージが用意されていません\n": "Confirmation message not ready.\n",
    "冒険を中断します。よろしいですか？": "This will interrupt your adventure.\nIs this OK?",
    "どこにセーブしますか？": "Where would you like to save?",
    "現在の状況をセーブしてもよろしいですか？": "OK to save your current status?",
    "セーブをやり直しますか？": "Restart save?",
    "すべてのオプション設定を元に戻しますか？": "Return all option settings back to default?",
    "秘められた力を解放しますか？": "Unleash hidden power?",
    "本当に捨てますか？": "Do you really want to get rid of this?",
    "フェイムを消費し、光を宿しますか？": "Consume Fame to harbor a light?",
    "この相談、解決してやれよ！\u3000なっ！？": "This advice will solve your problem! Right?!",
    "ヒントを購入しますか？": "Purchase the hint?",
    "性格コメントを入力しますか？": "Do you want to add an alignment comment?",
    "このキャラクターを登録しますか？": "Register this character?",
    "所持金を投資してキャラクターを鍛えますか？": "Invest money to train this character?",
    "このキャラクターを削除しますか？": "Delete this character?",
    "この職業に転職しますか？": "Change to this class?",
    "性格コメントを変更しますか？": "Do you want to change the alignment comment?",
    "エクストラスキルを変更しますか？": "Do you want to change extra skills?",
    "アイコン画像とスタイル画像の変更をしますか？": "Do you want to change character images?",
    "購入します。よろしいですか？": "OK to buy this?",
    "売却します。よろしいですか？": "OK to sell this?",
    "取引します。よろしいですか？": "OK to trade this?",
    "鑑定を依頼しますか？": "Request identification?",
    "アイテムを売ります。よろしいですか？": "OK to sell this item?",
    "解呪・修理しますか？": "Repair or remove curse?",
    "再開しますか？": "Resume?",
    "データインストールしますか？": "Do you want to install data?",
    "利用しますか？": "Use this?",
    "宿屋に戻りますか？": "Return to the Inn?",
    "これでよろしいですか？": "Is this OK?",
    "分解します。よろしいですか？": "Disassembling. Is this OK?",
    "本当に削除してもよろしいですか？": "Are you sure you want to delete?",
    "削除してもよろしいですか？": "Do you want to delete?",
    # 0x3C040 info/status prompts + strcat combinations (20)
    "捨てました": "Threw away.",
    "購入しました": "Purchased.",
    "訓練しました。": "Training complete.",
    "売却しました。": "Sold.",
    "解呪・修理しました。": "Item repaired or curse removed.",
    "データインストールをすると、\nゲームのロード速度があがります。": (
        "Installing data speeds up\ngame loading times."
    ),
    "データインストールをすると、\nゲームのロード速度があがります。\n※既存のインストールデータは削除されます。": (
        "Installing data speeds up game loading.\n*Existing install data will be deleted."
    ),
    "データインストールをすると、\nゲームのロード速度があがります。\n*Existing install data will be deleted.": (
        "Installing data speeds up game loading.\n*Existing install data will be deleted."
    ),
    "データインストールをすると、\nゲームのロード速度があがります。\n※メモリースティック│が差さっていません": (
        "Installing data speeds up game loading.\n*No Memory Stick inserted."
    ),
    "データインストールをすると、\nゲームのロード速度があがります。\n*No Memory Stick inserted.": (
        "Installing data speeds up game loading.\n*No Memory Stick inserted."
    ),
    "インストールに失敗しました。\nインストールを中断します。": (
        "Installation failed.\nAborting installation."
    ),
    "錬金しました\n･･････奇妙な煙が出ている！！": "Transmuted!\n...Strange smoke is rising!!",
    "爆発してしまった！！": "It exploded!!",
    "爆発した錬金倉庫から何かをみつけた。": "Found something in the exploded Warehouse.",
    "寄付しました": "Donated.",
    "ロードするセーブデータを選んでください": "Please select the save data to load.",
    "ロードするセーブデータを選んでください\n△ボタンでこのデータを削除します": (
        "Select save data to load.\nPress Triangle to delete this data."
    ),
    "ロードするセーブデータを選んでください\nPress Triangle to delete this data.": (
        "Select save data to load.\nPress Triangle to delete this data."
    ),
    "セーブデータをロードしました": "Save data loaded.",
    "新規ゲームを開始します": "Starting a new game.",
    # 0x4B040..0x4C340 help-bar prompts via 0x4C340 (jal 0x311d0) (17)
    "全滅したパーティーです。再開できません。": "The party was annihilated. You can't resume.",
    "変更したい天気を選んでください\u3000": "Select the weather to change to.",
    "入れ替えるキャラクターを選んでください。": "Select a character to swap with.",
    "入れ替えました": "Swapped.",
    "職業を選んでください": "Select a class.",
    "呪文名を変更してください。": "Change player spell names.",
    "確認する人を選んで下さい。": "Select a character to check.",
    "どのアイテムに唱えますか？": "Which item will you cast this on?",
    "唱えました": "Spell cast.",
    "階層を選んでください": "Select a floor.",
    "場所を選んでください": "Select a location.",
    "アイテムを選択して下さい": "Please choose an item.",
    "装備しました": "Equipped.",
    "△ボタンで特殊発動・抵抗\u3000×ボタンで戻る": "Tri: Special Move/Resist  X: Back",
    "△ボタンで抵抗＆倍打\u3000×ボタンで戻る": "Tri: Resist & Slayer  X: Back",
    "△ボタンで装備制限＆自動効果\u3000×ボタンで戻る": "Tri: Equip Limits & Auto-Effect  X: Back",
    "使う相手を選んでください": "Select a character to use.",
    # Other stack-built prompts (Shop, Herb Pouch, Icon Select, Alchemy Warehouse, Corrupted Save) (11)
    "品切れ中": "Sold Out",
    "現在ＨＰが最大ＨＰの": "Current HP is less than",
    "％より低い": "% of max HP.",
    "使用するアイコンを選んでください": "Select an icon to use.",
    "職業アイコン": "Class Icon",
    "顔アイコン": "Face Icon",
    "＊\u3000錬金倉庫の利用\u3000＊": "* Alchemy Warehouse *",
    "鍛冶、錬金、分解と倉庫": "Forge, Transmute, Disassemble, Store",
    "壊れたセーブデータを削除しています\nメモリースティック│を抜かないで下さい": (
        "Deleting corrupted save data.\nDo not remove Memory Stick."
    ),
    "インストールされたデータが壊れているため、\n削除します": (
        "Installed data is corrupted.\nDeleting..."
    ),
    "壊れたインストールデータを削除しています\nメモリースティック│を抜かないで下さい": (
        "Deleting corrupted install data.\nDo not remove Memory Stick."
    ),
}


def _pack_lookup_blob(pairs: dict[bytes, bytes]) -> tuple[bytes, int]:
    """Pack {raw_jp_bytes: raw_en_bytes} into a sorted, position-independent lookup blob."""
    items = sorted(pairs.items(), key=lambda kv: kv[0])
    n = len(items)
    table_end = 4 + n * 8
    pool = bytearray()
    index = bytearray()
    for jp, en in items:
        jp_off = table_end + len(pool)
        pool.extend(jp + b"\x00")
        en_off = table_end + len(pool)
        pool.extend(en + b"\x00")
        index.extend(struct.pack("<II", jp_off, en_off))
    return struct.pack("<I", n) + bytes(index) + bytes(pool), n


def _wrap_scenario_bytes(en: bytes, max_len: int = SCENARIO_MAX_LINE_BYTES) -> bytes:
    """Word-wrap ultra-long (>56B) Scenario.bin lines on spaces using 0x01 0x04 page-clear
    so wrapped lines never push a 3-line dialogue box past the bottom of the 272px screen."""
    if len(en) <= max_len:
        return en
    lines: list[bytes] = []
    cur = bytearray()
    for word in en.split(b" "):
        while len(word) > max_len:
            if cur:
                lines.append(bytes(cur))
                cur.clear()
            lines.append(word[:max_len])
            word = word[max_len:]
        if not cur:
            cur.extend(word)
        elif len(cur) + 1 + len(word) <= max_len:
            cur.append(0x20)
            cur.extend(word)
        else:
            lines.append(bytes(cur))
            cur = bytearray(word)
    if cur or not lines:
        lines.append(bytes(cur))
    return b"\x01\x04".join(lines)


def build_prompt_blob(prompts: dict[str, str] = INLINE_PROMPT_TRANSLATIONS) -> tuple[bytes, int]:
    """Encode inline stack-built prompt translations into a sorted CP932 lookup blob."""
    pairs = {jp.encode("cp932"): en.encode("cp932") for jp, en in prompts.items()}
    return _pack_lookup_blob(pairs)


def load_scenario_blob(steam_s00: Path = STEAM_S00) -> tuple[bytes, int]:
    """Load Steam S00.bra -> Scenario.bin and pack a sorted, position-independent lookup blob."""
    with steam_s00.open("rb") as f:
        _, _, toc_off, count = struct.unpack("<4sIII", f.read(16))
        f.seek(toc_off)
        toc = f.read()
        pos = 0
        data = None
        for _ in range(count):
            _, _, csz, usz, nlen, _, off = struct.unpack_from("<IIIIHHI", toc, pos)
            name = toc[pos + 24 : pos + 24 + nlen].split(b"\x00")[0].decode("ascii", "replace")
            pos += 24 + nlen
            if name.lower() == "scenario.bin":
                f.seek(off)
                raw = f.read(csz)
                data = zlib.decompress(raw[16:], -15) if csz != usz else raw[16:]
                break
    if data is None:
        raise FileNotFoundError(f"Scenario.bin not found in {steam_s00}")

    n_pairs = struct.unpack_from("<I", data, 0)[0]
    offs = struct.unpack_from(f"<{2 * n_pairs}I", data, 4)
    pairs: dict[bytes, bytes] = {}
    for k in range(n_pairs):
        jo, eo = offs[2 * k], offs[2 * k + 1]
        jp = data[jo : data.index(b"\x00", jo)]
        en = data[eo : data.index(b"\x00", eo)]
        if not jp or not en:
            continue
        if any(b < 0x20 for b in jp) or any(b < 0x20 for b in en):
            raise ValueError(f"Unexpected <0x20 control byte in Scenario.bin pair {k}")
        if jp not in pairs:
            en_val = SCENARIO_OVERRIDES.get(jp, en)
            # Prepend space on dynamic-prefix particle suffixes (e.g., "<Name>は水を飲んだ。")
            jps = jp.decode("cp932", "ignore")
            if (
                jps
                and jps[0] in ("は", "が", "を", "に", "で", "の", "も", "と")
                and en_val
                and en_val[0] not in (0x20, ord(","), ord("."), ord("!"), ord("?"), ord("'"))
                and en_val[0:1].islower()
            ):
                en_val = b" " + en_val
            pairs[jp] = _wrap_scenario_bytes(en_val)

    return _pack_lookup_blob(pairs)


class _MipsAsm:
    REGS = {
        "$zero": 0, "$at": 1, "$v0": 2, "$v1": 3,
        "$a0": 4, "$a1": 5, "$a2": 6, "$a3": 7,
        "$t0": 8, "$t1": 9, "$t2": 10, "$t3": 11,
        "$t4": 12, "$t5": 13, "$t6": 14, "$t7": 15,
        "$s0": 16, "$s1": 17, "$s2": 18, "$s3": 19,
        "$s4": 20, "$s5": 21, "$s6": 22, "$s7": 23,
        "$t8": 24, "$t9": 25, "$gp": 28, "$sp": 29,
        "$fp": 30, "$ra": 31,
    }

    def __init__(self, base_va: int) -> None:
        self.base_va = base_va
        self.ops: list[tuple[str, tuple]] = []
        self.labels: dict[str, int] = {}

    def label(self, name: str) -> None:
        if name in self.labels:
            raise ValueError(f"Duplicate label {name}")
        self.labels[name] = len(self.ops)

    def va_of(self, name: str) -> int:
        return self.base_va + self.labels[name] * 4

    def emit(self, op: str, *args) -> None:
        self.ops.append((op, args))

    def _r(self, name: str) -> int:
        return self.REGS[name]

    def assemble(self) -> bytes:
        out = bytearray()
        for idx, (op, args) in enumerate(self.ops):
            if op == "nop":
                w = 0
            elif op == "addiu":
                rt, rs, imm = self._r(args[0]), self._r(args[1]), args[2]
                w = (0x09 << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)
            elif op == "sltiu":
                rt, rs, imm = self._r(args[0]), self._r(args[1]), args[2]
                w = (0x0B << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)
            elif op == "lui":
                rt, imm = self._r(args[0]), args[1]
                w = (0x0F << 26) | (rt << 16) | (imm & 0xFFFF)
            elif op in ("lw", "lbu", "sb", "sw"):
                opc = {"lw": 0x23, "lbu": 0x24, "sb": 0x28, "sw": 0x2B}[op]
                rt, imm, rs = self._r(args[0]), args[1], self._r(args[2])
                w = (opc << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)
            elif op in ("beq", "bne"):
                opc = 0x04 if op == "beq" else 0x05
                rs, rt, lbl = self._r(args[0]), self._r(args[1]), args[2]
                rel = self.labels[lbl] - (idx + 1)
                w = (opc << 26) | (rs << 21) | (rt << 16) | (rel & 0xFFFF)
            elif op == "b":
                rel = self.labels[args[0]] - (idx + 1)
                w = (0x04 << 26) | (rel & 0xFFFF)
            elif op == "j":
                w = (0x02 << 26) | ((args[0] >> 2) & 0x03FFFFFF)
            elif op == "jal":
                w = (0x03 << 26) | ((args[0] >> 2) & 0x03FFFFFF)
            elif op in ("sll", "srl"):
                funct = 0x00 if op == "sll" else 0x02
                rd, rt, sa = self._r(args[0]), self._r(args[1]), args[2]
                w = (rt << 16) | (rd << 11) | ((sa & 0x1F) << 6) | funct
            elif op == "jr":
                rs = self._r(args[0])
                w = (rs << 21) | 0x08
            elif op in ("addu", "slt", "sltu"):
                funct = {"addu": 0x21, "slt": 0x2A, "sltu": 0x2B}[op]
                rd, rs, rt = self._r(args[0]), self._r(args[1]), self._r(args[2])
                w = (rs << 21) | (rt << 16) | (rd << 11) | funct
            else:
                raise ValueError(f"Unsupported op {op}")
            out.extend(struct.pack("<I", w))
        return bytes(out)


def assemble_cave_hooks(
    cave_va: int,
    scenario_seg1_off: int,
    prompt_seg1_off: int,
) -> tuple[bytes, dict[str, int]]:
    """Assemble hook_b8a90 + prompt_lookup + hook_3b180_call + hook_7b264_call into cave."""
    scen_hi16 = ((scenario_seg1_off + 0x8000) >> 16) & 0xFFFF
    scen_lo16 = scenario_seg1_off & 0xFFFF
    prompt_hi16 = ((prompt_seg1_off + 0x8000) >> 16) & 0xFFFF
    prompt_lo16 = prompt_seg1_off & 0xFFFF

    a = _MipsAsm(cave_va)
    a.emit("addiu", "$sp", "$sp", -0x440)
    for idx, reg in enumerate(("$s0", "$s1", "$s2", "$s3", "$s4", "$s5", "$s6", "$ra")):
        a.emit("sw", reg, 0x420 + idx * 4, "$sp")
    a.emit("addu", "$s0", "$a1", "$zero")
    a.label("jal_orig")
    a.emit("jal", ORIG_DECODE_VA)
    a.emit("nop")
    a.emit("addu", "$s1", "$v0", "$zero")
    a.emit("beq", "$s0", "$zero", "epilogue")
    a.emit("nop")
    a.label("lui_scen")
    a.emit("lui", "$s5", scen_hi16)
    a.label("addiu_scen")
    a.emit("addiu", "$s5", "$s5", scen_lo16)
    a.emit("addu", "$s2", "$s0", "$zero")
    a.emit("addiu", "$s3", "$sp", 0x20)
    a.emit("addiu", "$s6", "$sp", 0x418)

    a.label("outer")
    a.emit("lbu", "$t0", 0, "$s2")
    a.emit("beq", "$t0", "$zero", "copy_back")
    a.emit("sltiu", "$t1", "$t0", 0x80)
    a.emit("beq", "$t1", "$zero", "scan_seg")
    a.emit("nop")
    a.emit("sltu", "$t1", "$s3", "$s6")
    a.emit("beq", "$t1", "$zero", "ctrl_next")
    a.emit("nop")
    a.emit("sb", "$t0", 0, "$s3")
    a.emit("addiu", "$s3", "$s3", 1)
    a.label("ctrl_next")
    a.emit("b", "outer")
    a.emit("addiu", "$s2", "$s2", 1)

    a.label("scan_seg")
    a.emit("addu", "$s4", "$s2", "$zero")
    a.label("scan_loop")
    a.emit("lbu", "$t0", 0, "$s4")
    a.emit("sltiu", "$t1", "$t0", 0x20)
    a.emit("bne", "$t1", "$zero", "scan_done")
    a.emit("nop")
    a.emit("b", "scan_loop")
    a.emit("addiu", "$s4", "$s4", 1)

    a.label("scan_done")
    a.emit("addu", "$t2", "$zero", "$zero")
    a.emit("lw", "$t3", 0, "$s5")
    a.emit("addiu", "$t3", "$t3", -1)

    a.label("bsearch_loop")
    a.emit("slt", "$t0", "$t3", "$t2")
    a.emit("bne", "$t0", "$zero", "not_found")
    a.emit("addu", "$t4", "$t2", "$t3")
    a.emit("srl", "$t4", "$t4", 1)
    a.emit("sll", "$t5", "$t4", 3)
    a.emit("addu", "$t5", "$t5", "$s5")
    a.emit("lw", "$t6", 4, "$t5")
    a.emit("addu", "$t6", "$t6", "$s5")
    a.emit("addu", "$t7", "$s2", "$zero")
    a.emit("addu", "$t8", "$t6", "$zero")

    a.label("cmp_loop")
    a.emit("beq", "$t7", "$s4", "cmp_end_seg")
    a.emit("lbu", "$a1", 0, "$t8")
    a.emit("lbu", "$a0", 0, "$t7")
    a.emit("beq", "$a0", "$a1", "cmp_eq")
    a.emit("sltu", "$a2", "$a0", "$a1")
    a.emit("bne", "$a2", "$zero", "go_left")
    a.emit("nop")
    a.emit("b", "bsearch_loop")
    a.emit("addiu", "$t2", "$t4", 1)

    a.label("cmp_eq")
    a.emit("addiu", "$t7", "$t7", 1)
    a.emit("b", "cmp_loop")
    a.emit("addiu", "$t8", "$t8", 1)

    a.label("cmp_end_seg")
    a.emit("bne", "$a1", "$zero", "go_left")
    a.emit("nop")
    a.emit("lw", "$t6", 8, "$t5")
    a.emit("addu", "$t6", "$t6", "$s5")

    a.label("copy_en")
    a.emit("lbu", "$t0", 0, "$t6")
    a.emit("beq", "$t0", "$zero", "seg_done")
    a.emit("nop")
    a.emit("sltu", "$t1", "$s3", "$s6")
    a.emit("beq", "$t1", "$zero", "seg_done")
    a.emit("nop")
    a.emit("sb", "$t0", 0, "$s3")
    a.emit("addiu", "$s3", "$s3", 1)
    a.emit("b", "copy_en")
    a.emit("addiu", "$t6", "$t6", 1)

    a.label("go_left")
    a.emit("b", "bsearch_loop")
    a.emit("addiu", "$t3", "$t4", -1)

    a.label("not_found")
    a.emit("addu", "$t6", "$s2", "$zero")
    a.label("copy_orig")
    a.emit("beq", "$t6", "$s4", "seg_done")
    a.emit("nop")
    a.emit("sltu", "$t1", "$s3", "$s6")
    a.emit("beq", "$t1", "$zero", "seg_done")
    a.emit("nop")
    a.emit("lbu", "$t0", 0, "$t6")
    a.emit("sb", "$t0", 0, "$s3")
    a.emit("addiu", "$s3", "$s3", 1)
    a.emit("b", "copy_orig")
    a.emit("addiu", "$t6", "$t6", 1)

    a.label("seg_done")
    a.emit("b", "outer")
    a.emit("addu", "$s2", "$s4", "$zero")

    a.label("copy_back")
    a.emit("sb", "$zero", 0, "$s3")
    a.emit("addiu", "$t6", "$sp", 0x20)
    a.emit("addu", "$t7", "$s0", "$zero")
    a.label("cb_loop")
    a.emit("lbu", "$t0", 0, "$t6")
    a.emit("sb", "$t0", 0, "$t7")
    a.emit("beq", "$t0", "$zero", "epilogue")
    a.emit("addiu", "$t6", "$t6", 1)
    a.emit("b", "cb_loop")
    a.emit("addiu", "$t7", "$t7", 1)

    a.label("epilogue")
    a.emit("addu", "$v0", "$s1", "$zero")
    for idx, reg in enumerate(("$s0", "$s1", "$s2", "$s3", "$s4", "$s5", "$s6", "$ra")):
        a.emit("lw", reg, 0x420 + idx * 4, "$sp")
    a.emit("jr", "$ra")
    a.emit("addiu", "$sp", "$sp", 0x440)

    # prompt_lookup($v1 -> $v0): binary-search sorted CP932 inline prompt table; clobbers ONLY $v0, $t3..$t9
    a.label("prompt_lookup")
    a.emit("beq", "$v1", "$zero", "pl_miss")
    a.emit("addu", "$v0", "$v1", "$zero")
    a.label("lui_prompt")
    a.emit("lui", "$t9", prompt_hi16)
    a.label("addiu_prompt")
    a.emit("addiu", "$t9", "$t9", prompt_lo16)
    a.emit("addu", "$t3", "$zero", "$zero")
    a.emit("lw", "$t4", 0, "$t9")
    a.emit("addiu", "$t4", "$t4", -1)

    a.label("pl_bsearch")
    a.emit("slt", "$t5", "$t4", "$t3")
    a.emit("bne", "$t5", "$zero", "pl_miss")
    a.emit("addu", "$t5", "$t3", "$t4")
    a.emit("srl", "$t5", "$t5", 1)
    a.emit("sll", "$t6", "$t5", 3)
    a.emit("addu", "$t6", "$t6", "$t9")
    a.emit("lw", "$t7", 4, "$t6")
    a.emit("addu", "$t7", "$t7", "$t9")
    a.emit("addu", "$t8", "$v1", "$zero")

    a.label("pl_cmp")
    a.emit("lbu", "$v0", 0, "$t8")
    a.emit("lbu", "$t6", 0, "$t7")
    a.emit("bne", "$v0", "$t6", "pl_diff")
    a.emit("sltu", "$t6", "$v0", "$t6")
    a.emit("beq", "$v0", "$zero", "pl_found")
    a.emit("addiu", "$t8", "$t8", 1)
    a.emit("b", "pl_cmp")
    a.emit("addiu", "$t7", "$t7", 1)

    a.label("pl_diff")
    a.emit("bne", "$t6", "$zero", "pl_go_left")
    a.emit("nop")
    a.emit("b", "pl_bsearch")
    a.emit("addiu", "$t3", "$t5", 1)

    a.label("pl_go_left")
    a.emit("b", "pl_bsearch")
    a.emit("addiu", "$t4", "$t5", -1)

    a.label("pl_found")
    a.emit("sll", "$t6", "$t5", 3)
    a.emit("addu", "$t6", "$t6", "$t9")
    a.emit("lw", "$v0", 8, "$t6")
    a.emit("jr", "$ra")
    a.emit("addu", "$v0", "$v0", "$t9")

    a.label("pl_miss")
    a.emit("jr", "$ra")
    a.emit("addu", "$v0", "$v1", "$zero")

    prompt_lookup_va = a.va_of("prompt_lookup")

    a.label("hook_3b180_call")
    a.emit("addiu", "$sp", "$sp", -0x10)
    a.emit("sw", "$ra", 0, "$sp")
    a.label("jal_pl_3b180")
    a.emit("jal", prompt_lookup_va)
    a.emit("addu", "$v1", "$a0", "$zero")
    a.emit("addu", "$a0", "$v0", "$zero")
    a.emit("lw", "$ra", 0, "$sp")
    a.label("j_3b180")
    a.emit("j", 0x3B180)
    a.emit("addiu", "$sp", "$sp", 0x10)

    a.label("hook_7b264_call")
    a.emit("addiu", "$sp", "$sp", -0x10)
    a.emit("sw", "$ra", 0, "$sp")
    a.label("jal_pl_7b264")
    a.emit("jal", prompt_lookup_va)
    a.emit("addu", "$v1", "$a1", "$zero")
    a.emit("addu", "$a1", "$v0", "$zero")
    a.emit("lw", "$ra", 0, "$sp")
    a.label("j_7b264")
    a.emit("j", 0x7B264)
    a.emit("addiu", "$sp", "$sp", 0x10)

    a.label("hook_311d0_call")
    a.emit("addiu", "$sp", "$sp", -0x10)
    a.emit("sw", "$ra", 0, "$sp")
    a.label("jal_pl_311d0")
    a.emit("jal", prompt_lookup_va)
    a.emit("addu", "$v1", "$a0", "$zero")
    a.emit("addu", "$a0", "$v0", "$zero")
    a.emit("lw", "$ra", 0, "$sp")
    a.label("j_311d0")
    a.emit("j", 0x311D0)
    a.emit("addiu", "$sp", "$sp", 0x10)

    code = a.assemble()
    if len(code) > CAVE_END - CAVE_START:
        raise ValueError(f"Hook too large for cave: {len(code)} > {CAVE_END - CAVE_START}")
    label_vas = {
        k: a.va_of(k)
        for k in (
            "jal_orig",
            "lui_scen",
            "addiu_scen",
            "lui_prompt",
            "addiu_prompt",
            "hook_3b180_call",
            "jal_pl_3b180",
            "j_3b180",
            "hook_7b264_call",
            "jal_pl_7b264",
            "j_7b264",
            "hook_311d0_call",
            "jal_pl_311d0",
            "j_311d0",
        )
    }
    return code, label_vas


def build_patched_eboot(
    translations: dict[str, str],
    extra_payload: bytes = b"",
    prompt_payload: bytes = b"",
    install_scenario_hook: bool = False,
) -> tuple[bytes, int]:
    """
    Patch ULJM06091_EBOOT.BIN with {hex_vaddr_or_jp: en_str} translations,
    plus optional .rodata sweep, universal Yes/No patch, and Scenario.bin runtime hook.
    Returns (patched_eboot_bytes, extra_payload_seg1_vaddr).
    """
    elf = bytearray(ORIG_EBOOT.read_bytes())

    e_phoff = struct.unpack_from("<I", elf, 28)[0]
    e_shoff = struct.unpack_from("<I", elf, 32)[0]
    e_shentsize, e_shnum = struct.unpack_from("<HH", elf, 46)

    p0_off = struct.unpack_from("<I", elf, e_phoff + 0 * 32 + 4)[0]
    p1_type, p1_off, p1_vaddr, p1_paddr, p1_filesz, p1_memsz, p1_flags, p1_align = struct.unpack_from(
        "<8I", elf, e_phoff + 1 * 32
    )
    p2_off, _, _, p2_filesz = struct.unpack_from("<4I", elf, e_phoff + 2 * 32 + 4)

    # 1. Scan PT_MIPS_PSPREL to build exact reference map: target_vaddr -> reloc list
    #    For HI16/LO16, pair each LO16 with its immediately preceding HI16 on the same register.
    u32_refs: dict[int, list[tuple[int, int]]] = {}  # target -> [(rela_off, r_off)]
    hi_to_los: dict[int, list[tuple[int, int, int]]] = {}  # hi_rela_off -> [(lo_rela_off, lo_r_off, target)]
    hi_meta: dict[int, tuple[int, int]] = {}  # hi_rela_off -> (hi_r_off, hi_rt)
    active_hi: dict[int, tuple[int, int]] = {}  # reg -> (hi_rela_off, hi16)

    for roff in range(p2_off, p2_off + p2_filesz, 8):
        r_off, r_info = struct.unpack_from("<II", elf, roff)
        rtype = r_info & 0xFF
        symseg = (r_info >> 8) & 0xFF
        datseg = (r_info >> 16) & 0xFF
        if datseg != 0 or symseg != 0:
            continue
        if rtype == 2:  # R_MIPS_32
            val = struct.unpack_from("<I", elf, p0_off + r_off)[0]
            if 0x14CE80 <= val < 0x16CB18:
                u32_refs.setdefault(val, []).append((roff, r_off))
        elif rtype == 5:  # R_MIPS_HI16
            w = struct.unpack_from("<I", elf, p0_off + r_off)[0]
            rt = (w >> 16) & 0x1F
            hi16 = w & 0xFFFF
            active_hi[rt] = (roff, hi16)
            hi_meta[roff] = (r_off, rt)
        elif rtype == 6:  # R_MIPS_LO16
            w = struct.unpack_from("<I", elf, p0_off + r_off)[0]
            rs = (w >> 21) & 0x1F
            lo_s = struct.unpack("<h", struct.pack("<H", w & 0xFFFF))[0]
            if rs in active_hi:
                hi_roff, hi16 = active_hi[rs]
                val = ((hi16 << 16) + lo_s) & 0xFFFFFFFF
                hi_to_los.setdefault(hi_roff, []).append((roff, r_off, val))

    # Build safe HI16/LO16 groups: only repoint a HI16 if ALL its paired LO16s share the same target vaddr
    hilo_refs: dict[int, list[tuple[int, int, list[tuple[int, int]]]]] = {}
    unsafe_vaddrs: set[int] = set()
    for hi_roff, los in hi_to_los.items():
        targets = {t for _, _, t in los}
        if len(targets) == 1:
            t = next(iter(targets))
            if 0x14CE80 <= t < 0x16CB18:
                hi_r_off, _ = hi_meta[hi_roff]
                hilo_refs.setdefault(t, []).append((hi_roff, hi_r_off, [(lr, lo) for lr, lo, _ in los]))
        else:
            for t in targets:
                if 0x14CE80 <= t < 0x16CB18:
                    unsafe_vaddrs.add(t)

    # 2. Prepare PHDR[1] extra block (after .bss)
    bss_pad_len = p1_memsz - p1_filesz
    base_seg1_off = (p1_memsz + 15) & ~15
    pre_align = base_seg1_off - p1_memsz
    extra_block = bytearray(bss_pad_len + pre_align)

    def _measure_avail(foff: int, raw_len: int, end: int) -> int:
        # Count available bytes including trailing 0-padding up to next 4-byte boundary (keeping >=1 NUL)
        z = end
        while z < len(elf) and elf[z] == 0 and (z - foff) < raw_len + 4:
            z += 1
        return max(raw_len, z - foff - 1)

    inplace_cnt = 0
    repoint_cnt = 0
    truncated_cnt = 0
    sweep_cnt = 0

    all_ref_vaddrs = set(u32_refs.keys()) | set(hilo_refs.keys()) | unsafe_vaddrs
    orig_elf = bytes(elf)
    for va in sorted(all_ref_vaddrs):
        foff = p0_off + va
        end = orig_elf.find(b"\x00", foff)
        if end <= foff:
            continue
        raw = orig_elf[foff:end]
        try:
            jp = raw.decode("cp932")
        except UnicodeDecodeError:
            continue

        en = translations.get(hex(va)) or translations.get(jp)
        if not en:
            continue
        en_b = en.encode("cp932", errors="replace")
        avail = _measure_avail(foff, len(raw), end)
        has_interior_ref = any(
            va < other_va < (end - p0_off) for other_va in all_ref_vaddrs
        )

        if len(en_b) <= avail and not has_interior_ref:
            elf[foff : foff + len(en_b)] = en_b
            elf[foff + len(en_b) : foff + avail + 1] = b"\x00" * (avail + 1 - len(en_b))
            inplace_cnt += 1
        elif va not in unsafe_vaddrs and (va in u32_refs or va in hilo_refs):
            seg1_off = base_seg1_off + (len(extra_block) - bss_pad_len - pre_align)
            extra_block.extend(en_b + b"\x00")
            while len(extra_block) % 4 != 0:
                extra_block.append(0)

            for rela_off, r_off in u32_refs.get(va, []):
                struct.pack_into("<I", elf, p0_off + r_off, seg1_off)
                r_info = struct.unpack_from("<I", elf, rela_off + 4)[0]
                struct.pack_into("<I", elf, rela_off + 4, (r_info & 0xFFFF) | (1 << 16))

            hi16 = ((seg1_off + 0x8000) >> 16) & 0xFFFF
            lo16 = seg1_off & 0xFFFF
            for hi_roff, hi_r_off, los in hilo_refs.get(va, []):
                w_hi = struct.unpack_from("<I", elf, p0_off + hi_r_off)[0]
                struct.pack_into("<I", elf, p0_off + hi_r_off, (w_hi & 0xFFFF0000) | hi16)
                ri_hi = struct.unpack_from("<I", elf, hi_roff + 4)[0]
                struct.pack_into("<I", elf, hi_roff + 4, (ri_hi & 0xFFFF) | (1 << 16))
                for lo_roff, lo_r_off in los:
                    w_lo = struct.unpack_from("<I", elf, p0_off + lo_r_off)[0]
                    struct.pack_into("<I", elf, p0_off + lo_r_off, (w_lo & 0xFFFF0000) | lo16)
                    ri_lo = struct.unpack_from("<I", elf, lo_roff + 4)[0]
                    struct.pack_into("<I", elf, lo_roff + 4, (ri_lo & 0xFFFF) | (1 << 16))
            repoint_cnt += 1
        else:
            # Shared HI16 fallback: trim safely to fit in-place
            trimmed = en_b[:avail]
            elf[foff : foff + len(trimmed)] = trimmed
            elf[foff + len(trimmed) : foff + avail + 1] = b"\x00" * (avail + 1 - len(trimmed))
            truncated_cnt += 1

    # 2b. Safe .rodata in-place sweep for unreferenced exact Shift-JIS strings
    va = 0x14CE80
    rodata_end = 0x16CB18
    while va < rodata_end:
        foff = p0_off + va
        if elf[foff] == 0:
            va += 1
            continue
        end = elf.find(b"\x00", foff, p0_off + rodata_end)
        if end == -1:
            break
        if elf[foff - 1] == 0 and va not in all_ref_vaddrs and (end - foff) >= 2:
            raw = bytes(elf[foff:end])
            if any(b >= 0x80 for b in raw):
                try:
                    jp = raw.decode("cp932")
                except UnicodeDecodeError:
                    jp = ""
                if jp:
                    en = translations.get(hex(va)) or translations.get(jp)
                    if en:
                        en_b = en.encode("cp932", errors="replace")
                        avail = _measure_avail(foff, len(raw), end)
                        if len(en_b) <= avail:
                            elf[foff : foff + len(en_b)] = en_b
                            elf[foff + len(en_b) : foff + avail + 1] = b"\x00" * (avail + 1 - len(en_b))
                            sweep_cnt += 1
        va = (end - p0_off) + 1

    # 2c. Patch universal inline Yes/No prompt at 0x3b180 and 7px half-width advance at 0x7B53C
    word_patches = [
        (0x3B1C0, 0x3C04A283, 0x3C040073),  # lui $a0, 0x0073
        (0x3B1C4, 0x2484CD82, 0x34846559),  # ori $a0, $a0, 0x6559 -> "Yes\0"
        (0x3B1F4, 0x3C04A283, 0x34046F4E),  # ori $a0, $zero, 0x6F4E -> "No\0\0"
        (0x3B1F8, 0x2484A282, 0x00000000),  # nop
        (0x3B1FC, 0x3405A682, 0x00002821),  # addu $a1, $zero, $zero
        (0x7B53C, 0x340A000A, 0x340A0007),  # ori $t2, $zero, 7 (half_w=7px)
    ]
    for patch_va, exp_word, new_word in word_patches:
        got = struct.unpack_from("<I", elf, p0_off + patch_va)[0]
        if got != exp_word:
            raise ValueError(f"Unexpected instruction at {patch_va:#x}: {got:#010x} != {exp_word:#010x}")
        struct.pack_into("<I", elf, p0_off + patch_va, new_word)

    extra_payload_seg1_off = base_seg1_off + (len(extra_block) - bss_pad_len - pre_align)
    if extra_payload:
        extra_block.extend(extra_payload)
        while len(extra_block) % 16 != 0:
            extra_block.append(0)

    prompt_seg1_off = base_seg1_off + (len(extra_block) - bss_pad_len - pre_align)
    if prompt_payload:
        extra_block.extend(prompt_payload)
        while len(extra_block) % 16 != 0:
            extra_block.append(0)

    # 2d. Install cave hooks, redirect prompt callers, & patch PHDR[2] cave relocs BEFORE splicing extra_block
    hook_bytes = 0
    patched_callers = 0
    cave_slots_cnt = 0
    if extra_payload and install_scenario_hook:
        if not prompt_payload:
            raise ValueError("prompt_payload must be provided when install_scenario_hook=True")
        hook_code, cave_vas = assemble_cave_hooks(
            CAVE_START, extra_payload_seg1_off, prompt_seg1_off
        )
        hook_bytes = len(hook_code)
        elf[p0_off + CAVE_START : p0_off + CAVE_START + hook_bytes] = hook_code
        elf[p0_off + CAVE_START + hook_bytes : p0_off + CAVE_END] = b"\x00" * (
            (CAVE_END - CAVE_START) - hook_bytes
        )

        orig_jal_word = (0x03 << 26) | (ORIG_DECODE_VA >> 2)
        hook_jal_word = (0x03 << 26) | (CAVE_START >> 2)
        for cva in range(0, 0x14C000, 4):
            if CAVE_START <= cva < CAVE_END:
                continue
            if struct.unpack_from("<I", elf, p0_off + cva)[0] == orig_jal_word:
                struct.pack_into("<I", elf, p0_off + cva, hook_jal_word)
                patched_callers += 1
        if patched_callers != 23:
            raise ValueError(f"Expected 23 callers of jal {ORIG_DECODE_VA:#x}, patched {patched_callers}")

        r26_relocs = {
            struct.unpack_from("<II", elf, roff)[0]
            for roff in range(p2_off, p2_off + p2_filesz, 8)
            if struct.unpack_from("<II", elf, roff)[1] == 4
        }
        hook_7b264_jal = (0x03 << 26) | (cave_vas["hook_7b264_call"] >> 2)
        prompt_call_patches = [
            (0x3C02C, 0x0C00EC60, (0x03 << 26) | (cave_vas["hook_3b180_call"] >> 2)),
            (0x3C71C, 0x0C01EC99, hook_7b264_jal),
            (0x3C744, 0x0C01EC99, hook_7b264_jal),
            (0x4C340, 0x0C00C474, (0x03 << 26) | (cave_vas["hook_311d0_call"] >> 2)),
            (0x39CE0, 0x0C01EC99, hook_7b264_jal),
            (0x3CAD8, 0x0C01EC99, hook_7b264_jal),
            (0x3CB50, 0x0C01EC99, hook_7b264_jal),
            (0x5DCD4, 0x0C01EC99, hook_7b264_jal),
            (0x5DD10, 0x0C01EC99, hook_7b264_jal),
            (0x5DD50, 0x0C01EC99, hook_7b264_jal),
            (0x73858, 0x0C01EC99, hook_7b264_jal),
            (0x738BC, 0x0C01EC99, hook_7b264_jal),
        ]
        for call_va, exp_word, new_word in prompt_call_patches:
            if call_va not in r26_relocs:
                raise ValueError(f"Missing R_MIPS_26 relocation at {call_va:#x}")
            got = struct.unpack_from("<I", elf, p0_off + call_va)[0]
            if got != exp_word:
                raise ValueError(f"Unexpected call word at {call_va:#x}: {got:#010x} != {exp_word:#010x}")
            struct.pack_into("<I", elf, p0_off + call_va, new_word)

        cave_slots: list[int] = []
        for roff in range(p2_off, p2_off + p2_filesz, 8):
            r_off, r_info = struct.unpack_from("<II", elf, roff)
            if ((r_info >> 8) & 0xFF) == 0 and CAVE_START <= r_off < CAVE_END:
                cave_slots.append(roff)
        cave_slots_cnt = len(cave_slots)
        if cave_slots_cnt != 41:
            raise ValueError(f"Expected 41 cave relocs, found {cave_slots_cnt}")
        if cave_slots[-1] - cave_slots[0] != 40 * 8:
            raise ValueError("Cave relocation slots are not contiguous in PHDR[2]")

        cave_reloc_entries = [
            (cave_vas["jal_orig"], 4),
            (cave_vas["lui_scen"], 5 | (1 << 16)),
            (cave_vas["addiu_scen"], 6 | (1 << 16)),
            (cave_vas["lui_prompt"], 5 | (1 << 16)),
            (cave_vas["addiu_prompt"], 6 | (1 << 16)),
            (cave_vas["jal_pl_3b180"], 4),
            (cave_vas["j_3b180"], 4),
            (cave_vas["jal_pl_7b264"], 4),
            (cave_vas["j_7b264"], 4),
            (cave_vas["jal_pl_311d0"], 4),
            (cave_vas["j_311d0"], 4),
        ]
        for idx, (r_off, r_info) in enumerate(cave_reloc_entries):
            struct.pack_into("<II", elf, cave_slots[idx], r_off, r_info)
        for slot in cave_slots[len(cave_reloc_entries) :]:
            struct.pack_into("<II", elf, slot, 0, 0)

    # 3. Splice extra_block at end of PHDR[1] (p1_off + p1_filesz) and shift PHDR[2] + section headers
    if repoint_cnt > 0 or extra_payload or prompt_payload:
        insert_pos = p1_off + p1_filesz
        delta = len(extra_block)
        new_elf = bytearray(elf[:insert_pos]) + extra_block + bytearray(elf[insert_pos:])

        new_p1_filesz = p1_filesz + delta
        struct.pack_into("<II", new_elf, e_phoff + 1 * 32 + 16, new_p1_filesz, new_p1_filesz)
        struct.pack_into("<I", new_elf, e_phoff + 2 * 32 + 4, p2_off + delta)

        new_e_shoff = e_shoff + delta if e_shoff >= insert_pos else e_shoff
        struct.pack_into("<I", new_elf, 32, new_e_shoff)
        for i in range(e_shnum):
            sh_pos = new_e_shoff + i * e_shentsize
            sh_off = struct.unpack_from("<I", new_elf, sh_pos + 16)[0]
            if sh_off >= insert_pos:
                struct.pack_into("<I", new_elf, sh_pos + 16, sh_off + delta)
    else:
        new_elf = elf

    print(
        f"EBOOT patched: inplace={inplace_cnt}, repointed={repoint_cnt}, trimmed={truncated_cnt}, "
        f"sweep={sweep_cnt}, hook_bytes={hook_bytes}, callers={patched_callers}, cave_relocs={cave_slots_cnt}, "
        f"out_size={len(new_elf)}"
    )
    return bytes(new_elf), p1_vaddr + extra_payload_seg1_off


def main() -> None:
    if not TRANS_JSON.exists():
        raise FileNotFoundError(f"Missing {TRANS_JSON}")
    trans = json.loads(TRANS_JSON.read_text(encoding="utf-8"))
    scenario_blob, n_scen = load_scenario_blob(STEAM_S00)
    prompt_blob, n_prompts = build_prompt_blob()
    print(f"Scenario.bin: {n_scen} unique entries, blob={len(scenario_blob)} bytes")
    print(f"Inline prompts: {n_prompts} entries, blob={len(prompt_blob)} bytes")
    patched, scen_va = build_patched_eboot(
        trans,
        extra_payload=scenario_blob,
        prompt_payload=prompt_blob,
        install_scenario_hook=True,
    )
    print(f"Scenario blob PHDR[1] vaddr: {scen_va:#x}")
    OUT_EBOOT.write_bytes(patched)
    print(f"Wrote {OUT_EBOOT}")
    patch_iso_file(ISO_TEST, "PSP_GAME/SYSDIR/EBOOT.BIN", patched)


if __name__ == "__main__":
    main()
