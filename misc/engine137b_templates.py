# -*- coding: utf-8 -*-
"""engine137b.py: 全部对话块模板解析 + 译文对照 + 容量预检 (只读不写)
输出: 每块 token 结构 / 帧模板 / 悬空标记 / 零区富余 / 与 T[entry] 帧数对照
"""
import struct
import sys
import json

P = r"C:\Users\Administrator\.local\share\TeleAgent\TeleAgent的工作空间\.temp\cb"
sys.path.insert(0, P)
import translation

ABS = {}
def add(e, a):
    ABS[e] = a
add(160, 0x221915C)
add(164, 0x22FB7F4)
add(166, 0x239CFFC)
add(168, 0x24087E8)
add(170, 0x247A6E8)
add(174, 0x252C9A0)
add(176, 0x25910DC)
add(178, 0x25EFF00)
add(180, 0x2684430)
add(182, 0x26EB944)
add(184, 0x274D780)
add(186, 0x27AA88C)
add(188, 0x280C8CC)
add(190, 0x2891718)
add(192, 0x2937E20)
add(194, 0x29DBD5C)
add(196, 0x2A484D0)
add(198, 0x2ABE31C)
add(200, 0x2B31D3C)
add(202, 0x2B9D078)
add(204, 0x2C0A3AC)
add(206, 0x2CAB70C)
add(208, 0x2D47768)
add(210, 0x2DB7B1C)
add(212, 0x2E29D44)
add(214, 0x2ECB854)
add(216, 0x2F393EC)
add(218, 0x2FA8550)
add(220, 0x304C624)
add(222, 0x30DBBAC)
for _e, _a in [
    (358, 0x483995C), (362, 0x4919FF4), (364, 0x49BB7FC), (366, 0x4A26FE8),
    (368, 0x4A98EE8), (372, 0x4B4B1A0), (374, 0x4BAF8DC), (376, 0x4C0E700),
    (378, 0x4CA2C30), (380, 0x4D0A144), (382, 0x4D6BF80), (384, 0x4DC908C),
    (386, 0x4E2B0CC), (388, 0x4EAFF18), (390, 0x4F56620), (392, 0x4FFA55C),
    (394, 0x5066CD0), (396, 0x50DCB1C), (398, 0x515053C), (400, 0x51BB878),
    (402, 0x5228BAC), (404, 0x52C9F0C), (406, 0x5365F68), (408, 0x53D631C),
    (410, 0x5448544), (412, 0x54EA054), (414, 0x5557BEC), (416, 0x55C6D50),
    (418, 0x566AE24), (420, 0x56FA3AC),
]:
    ABS[_e] = _a

# 块结构: entry -> [(块偏移键, 帧切片)]  E160/E358 是双块
BLOCKS = {}
for e in ABS:
    if e in (160, 358):
        BLOCKS[e] = [(ABS[e], slice(0, 1)), (ABS[e] + 0x84, slice(1, 4))]
    else:
        # 第二份拷贝的镜像 entry (358-420, 单块); 第一份 (162-222) 直接用本 entry
        src = e - 198 if e >= 358 else e
        BLOCKS[e] = [(ABS[e], slice(0, len(translation.T[src])))]

def read_bytes(f, u, n):
    """从打开的镜像文件读用户数据空间 (跨扇区)"""
    def u2d(x):
        return (x // 2048) * 2352 + 24 + (x % 2048)
    out = bytearray()
    cur, end = u, u + n
    while cur < end:
        io = cur % 2048
        take = min(2048 - io, end - cur)
        f.seek(u2d(cur))
        out += f.read(take)
        cur += take
    return bytes(out)

def u_data(datarel):
    return 1184 * 2048 + datarel

def parse_tokens(data):
    """解析 token 流: 返回 (tokens, end_idx)  end_idx=00 终止符位置"""
    toks = []
    i = 0
    while i < len(data):
        b = data[i]
        if b == 0x00:
            return toks, i
        if b == 0xFF:
            toks.append(("T", bytes([0xFF, data[i + 1]])))
            i += 2
            continue
        if b == 0xF1:
            toks.append(("F1",)); i += 1; continue
        if b == 0xF3:
            toks.append(("F3",)); i += 1; continue
        if b == 0xF6:
            toks.append(("F6",)); i += 1; continue
        if 0xF0 <= b <= 0xF5:
            toks.append(("??F%X" % (b - 0xF0),)); i += 1; continue
        toks.append(("T", bytes([b])))
        i += 1
    return toks, -1

def to_frameinfo(toks):
    """token 流 -> (frames, dangling)
    frames = [(kana_bytes|None, n_text_tokens, n_f1)], 悬空标记返回 dangling=(kana|None,)
    状态机: F3 前恰 1 个文本 token = 标记; F6 = 帧尾; 00 = 块尾。
    """
    frames = []
    pending = None          # 待归属标记
    texts = []              # 当前帧文本 token 累积
    dangling = None
    for t in toks:
        kind = t[0]
        if kind == "F3":
            if len(texts) == 1 and len(texts[0]) == 1:
                pending = texts[0]
            else:
                pending = b"?BAD?"
            texts = []
        elif kind == "F6":
            n_f1 = sum(1 for x in texts if x == "F1")
            frames.append((pending, len([x for x in texts if x != "F1"]), n_f1))
            pending = None
            texts = []
        elif kind == "F1":
            texts.append("F1")
        elif kind == "T":
            texts.append(t[1])
        else:
            texts.append(kind.encode())
    if pending is not None or texts:
        n_f1d = sum(1 for x in texts if x == "F1")
        dangling = (pending, len([x for x in texts if x != "F1"]), n_f1d)
    return frames, dangling

def zero_span(data, end_idx):
    """00 00 终止符后连续零区长度 (不含终止符), 返回 (span, next_nonzero_off)"""
    i = end_idx + 2
    while i < len(data) and data[i] == 0:
        i += 1
    return i - (end_idx + 2), i

if __name__ == "__main__":
    f = open(r"D:\游轮格斗汉化\Crisis Beat (Japan).bin", "rb")
    CT = json.load(open(P + r"\codetable_v3.json", encoding="utf-8"))["code_table"]
    k2c = {k: int(v, 16) for k, v in CT.items()}
    print("%-6s %-10s %-4s %-4s %-6s %-8s %s" % ("entry", "块@abs", "帧数", "T帧", "零区", "悬空", "帧明细 (kana,ntok,nf1)"))
    nbad = 0
    for e in sorted(ABS):
        if e in translation.T or (e - 198) in translation.T:
            src = e if e in translation.T else e - 198
        else:
            continue
        framesT = translation.T[src]
        for bi, (a, sl) in enumerate(BLOCKS[e]):
            u = u_data(a)
            d = read_bytes(f, u, 0x200)
            toks, endi = parse_tokens(d)
            if endi < 0:
                print("E%-4d blk%d @0x%X: 未找到 00 终止符 (前300B)!" % (e, bi, a))
                nbad += 1
                continue
            frames, dang = to_frameinfo(tooks := toks)
            zspan, nz = zero_span(d, endi)
            exp = framesT[sl]
            ok = "OK" if len(frames) == len(exp) else "!!帧数%d≠%d" % (len(frames), len(exp))
            if len(frames) != len(exp):
                nbad += 1
            detail = " ".join(
                "%s/%d/%d" % (x[0].hex() if x[0] else "--", x[1], x[2]) for x in frames)
            flag = ""
            if dang is not None:
                flag = "悬空=%s/ntok=%d" % (dang[0].hex() if dang[0] else "None", dang[1])
            print("E%-4d b%d @0x%07X end=+%03X %-6s %-8s %s %s | %s" %
                  (e, bi, a, endi, zspan, ok, flag, detail, "" if ok == "OK" else "T=" + str([t for t, _ in exp])[:40]))
    print("\n异常块数: %d" % nbad)
