#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解码 Crisis Beat 文本块（只读，不写盘）。

用法:
    python decode_text.py <Crisis Beat (Japan).bin> [abs_offset_hex] [len_hex]
    python decode_text.py <Crisis Beat (Japan).bin> --all

- 不带偏移：从条目表中扫描所有含 FF xx 双字节 + 假名高密度的条目，解码并打印
  （注意：会把大字体/资源条目误判为文本，仅供快速浏览，结果需人工甄别）。
- 带偏移：直接解码该绝对偏移处的一个文本块（如 0x0246915C）。
- 可选长度（十六进制，默认 0x200）：限制读取字节数，避免跨段读出非文本数据。
- --all：解码全部 33 个已知内容文本段（地址来自逆向实证，见 docs/TEXT_RENDER_ENGINE_NOTES_0913.md）。
- 码表读取 assets/codetable_master.json（kana_00_7F / kanjiA_80_EF / ff_low_map / bankB_FF10_BF）。

偏移基准（与 docs/TEXT_FORMAT_DOC.md 一致）:
    段地址（如 0x0246915C）是"逻辑用户数据偏移"，
    磁盘文件偏移 = (u // 2048) * 2352 + 24 + (u % 2048)，
    即不额外加 DATA_LBA(1184)。DATA.0 的 LBA 只用于定位条目表；
    条目表中的偏移（0x2000 等）相对 DATA.0 起始，需加上 1184*2048 转为逻辑坐标。
"""
import json, os, struct, sys

# DATA.0 条目表参数（数据轨起始扇区）
DATA_LBA = 1184          # 数据轨起始扇区
SECTOR = 2352            # MODE2/2352
USER = 2048              # 每扇区用户数据
HEADER = 24              # 扇区头
# DATA.0 用户区 offset 0 对应"相对 LBA0 用户数据"的逻辑偏移 = 1184 * 2048
DATA_LOGICAL_BASE = DATA_LBA * USER

def load_codetable():
    """从 assets/codetable_master.json 读取日文原码表"""
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "assets", "codetable_master.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    kana = data["kana_00_7F"]          # "00".."7F"
    kanjiA = data["kanjiA_80_EF"]      # "80".."EF"
    ff_low = data["ff_low_map"]        # "FF00".."FF0F"
    bankB = data["bankB_FF10_BF"]      # "FF10".."FFBF"
    return kana, kanjiA, ff_low, bankB

def u2d(u):
    """逻辑用户数据偏移 -> 磁盘文件偏移（MODE2/2352, 2048B 用户数据/扇区）"""
    return (u // USER) * SECTOR + HEADER + (u % USER)

def read_logical(f, off, size):
    """按逻辑坐标读取（自动跨扇区）"""
    out = bytearray()
    cur = off
    end = off + size
    while cur < end:
        io_ = cur % USER
        take = min(USER - io_, end - cur)
        f.seek(u2d(cur))
        out += f.read(take)
        cur += take
    return bytes(out)

def parse_entry_table(f):
    """解析 DATA.0 条目表，返回条目偏移列表。

    表中的偏移（如 0x2000, 0x69000...）是相对 DATA.0 起始的偏移；
    返回时统一加上 DATA_LOGICAL_BASE 转成绝对逻辑坐标，便于 read_logical。
    """
    f.seek(DATA_LBA * SECTOR + HEADER)
    raw = f.read(USER * 64)
    entries = []
    prev = -1
    for i in range(0, len(raw) - 4, 4):
        v = struct.unpack("<I", raw[i:i+4])[0]
        if v < prev:
            break
        entries.append(v + DATA_LOGICAL_BASE)
        prev = v
    return entries

def decode_ff(low, ff_low, bankB):
    key = "FF%02X" % low
    if low <= 0x0F:
        return ff_low.get(key, "[FF%02X]" % low)
    ch = bankB.get(key)
    return ch if ch and ch != "\u25C7" else "[FF%02X]" % low

def decode_block(data, kana, kanjiA, ff_low, bankB, verbose=False):
    """解码一段文本字节流，返回字符串。

    控制符：F0 转义 / F1 句中停顿(∥) / F2-F3 块标记(段首说话人) / F4-F5 清屏 / F6 换行。
    单字节：0x00-0x7F 假名表；0x80-0xEF 汉字A表。
    双字节：FF xx -> ff_low(00-0F) / bankB(10-BF)；FE xx -> 页31码（原表未收录）。
    """
    out = []
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b == 0xF6:
            out.append("\n")
            i += 1
            continue
        if b == 0xF1:
            out.append("∥")
            i += 1
            continue
        if b == 0xFF and i + 1 < n:
            out.append(decode_ff(data[i + 1], ff_low, bankB))
            i += 2
            continue
        if b == 0xFE and i + 1 < n:
            out.append("〔FE%02X〕" % data[i + 1])
            i += 2
            continue
        if 0xF2 <= b <= 0xF5:
            if verbose:
                out.append("[F%X]" % (b - 0xF0))
            i += 1
            continue
        if b == 0x00:
            # 段尾 00 填充：若剩余全为 00 则截断
            if all(x == 0 for x in data[i:]):
                break
            out.append("〔00〕")
            i += 1
            continue
        if 0x80 <= b <= 0xEF:
            ch = kanjiA.get("%02X" % b)
            out.append(ch if ch else "〔%02X〕" % b)
            i += 1
            continue
        if b <= 0x7F:
            ch = kana.get("%02X" % b)
            if ch:
                out.append(ch)
                i += 1
                continue
        if verbose:
            out.append("[%02X]" % b)
        i += 1
    return "".join(out)

def is_text_like(data, kana):
    """判断 data 是否像文本区：FF 对 + 假名密度"""
    ff = 0
    ka = 0
    n = min(len(data), 256)
    i = 0
    while i < n:
        b = data[i]
        if b == 0xFF and i + 1 < n:
            ff += 1
            i += 2
        elif b <= 0x7F and ("%02X" % b) in kana:
            ka += 1
            i += 1
        else:
            i += 1
    return ff >= 3 and ka >= 20

# 33 个内容文本段（起始地址, 结束地址）——逆向实证，镜像内镜像副本地址 = +0x02400000
TEXT_SEGS = [
    (0x0246915C, 0x0246916E), (0x024691E0, 0x02469212),
    (0x0254B7F4, 0x0254B80D), (0x025ECFFF, 0x025ED061),
    (0x026587E8, 0x0265880E), (0x026CA6E8, 0x026CA775),
    (0x0277C9A0, 0x0277C9E5), (0x027E10DC, 0x027E1155),
    (0x0283FF00, 0x0283FF99), (0x028D4430, 0x028D456A),
    (0x0293B944, 0x0293B995), (0x0299D780, 0x0299D825),
    (0x029FA88C, 0x029FA8ED), (0x02A5C8CC, 0x02A5C98E),
    (0x02AE1718, 0x02AE1781), (0x02B87E20, 0x02B87EF5),
    (0x02C2BD5C, 0x02C2BEC5), (0x02C984D0, 0x02C985B9),
    (0x02D0E31C, 0x02D0E406), (0x02D81D3D, 0x02D81DCD),
    (0x02DED078, 0x02DED11A), (0x02E5A3AC, 0x02E5A549),
    (0x02EFB70C, 0x02EFB87D), (0x02F97768, 0x02F97879),
    (0x03007B1C, 0x03007B30), (0x03007B39, 0x03007B56),
    (0x03079D44, 0x03079D5D), (0x0311B854, 0x0311B959),
    (0x031893EC, 0x03189400), (0x03189409, 0x0318942A),
    (0x031F8550, 0x031F856E), (0x0329C624, 0x0329C6AA),
    (0x0332BBAC, 0x0332BC09),
]

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    path = sys.argv[1]
    kana, kanjiA, ff_low, bankB = load_codetable()
    with open(path, "rb") as f:
        if len(sys.argv) >= 3 and sys.argv[2] == "--all":
            for i, (a, b) in enumerate(TEXT_SEGS):
                data = read_logical(f, a, b - a)
                text = decode_block(data, kana, kanjiA, ff_low, bankB)
                print("\n----- TEXT[%02d] addr=0x%08X len=%d -----" % (i, a, len(data)))
                print(text)
            return
        entries = parse_entry_table(f)
        print("条目数: %d  前3: %s" % (len(entries), [hex(e) for e in entries[:3]]))
        if len(sys.argv) >= 3:
            # 指定绝对偏移解码
            off = int(sys.argv[2], 16)
            n = int(sys.argv[3], 16) if len(sys.argv) >= 4 else 0x200
            data = read_logical(f, off, n)
            print("\n=== 解码 @0x%X ===" % off)
            print(decode_block(data, kana, kanjiA, ff_low, bankB))
        else:
            # 扫描条目
            for i in range(len(entries) - 1):
                start, end = entries[i], entries[i + 1]
                size = end - start
                if size < 64 or size > 2 * 1024 * 1024:
                    continue
                data = read_logical(f, start, min(size, 4096))
                if is_text_like(data, kana):
                    text = decode_block(data, kana, kanjiA, ff_low, bankB)
                    first = "\n".join(text.split("\n")[:3])
                    print("\n条目[%5d] off=0x%08X size=%7d" % (i, start, size))
                    print(first)

if __name__ == "__main__":
    import sys
    main()