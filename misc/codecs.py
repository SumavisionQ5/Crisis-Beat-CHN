#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""codecs.py: Crisis Beat pak 压缩格式完整复刻 (基于 SLPS_014.exe 逆向)
顶层: 0x8001E0F0 逻辑 - 连续块流, 每块输出到 dst+8192*n
块头 1 字节 tag 分发 (0x8001DC8C):
  0x14 字典nibble  0x20 LZSS变体  0x30 RLE8  0x31 RLE16  0x40 RLE单次
  0x70 位选择RLE  0x71 经典RLE  0x72 平面拆分(内嵌73/74)  0x73 LZSS  0x74 LZSS+映射表
  0xFF 原样拷贝  0x00 结束
"""

TIM4 = b"\x10\x00\x00\x00\x08\x00\x00\x00"
TIM8 = b"\x10\x00\x00\x00\x09\x00\x00\x00"


class CodecError(Exception):
    pass


def dec_ff(src, p, out):
    """0xFF: 原样拷贝 [FF][len_lo][len_hi][data...] (0x8001DDEC)"""
    if p + 3 > len(src):
        raise CodecError("ff overrun")
    ln = src[p + 1] | src[p + 2] << 8
    if ln == 0:
        return 3, bytearray()
    if p + 3 + ln > len(src):
        raise CodecError("ff data overrun")
    return 3 + ln, bytearray(src[p + 3:p + 3 + ln])


def dec_70(src, p, out):
    """0x70 位选择RLE (0x8001D4E0)
    [n16 组数][每组: fill字节 + 4B小端LE32标志 + 按位MSB先(1=fill,0=字面量) x32]
    尾部: 单个 count 字节 + count 个字面量 (仅一轮, 非循环)"""
    start = p
    p += 1
    n_groups = src[p] | src[p + 1] << 8
    p += 2
    if n_groups:
        for g in range(n_groups):
            if p + 5 > len(src):
                raise CodecError("70 overrun")
            fill = src[p]; p += 1
            flags = src[p] | src[p + 1] << 8 | src[p + 2] << 16 | src[p + 3] << 24
            p += 4
            for i in range(32):
                if flags & (0x80000000 >> i):
                    out.append(fill)
                else:
                    if p >= len(src):
                        raise CodecError("70 lit overrun")
                    out.append(src[p]); p += 1
    # 尾部: 单个 count (引擎 0x8001D590: 读一个字节, count=0 结束, 非循环)
    if p >= len(src):
        raise CodecError("70 tail overrun")
    n = src[p]; p += 1
    if n:
        if p + n > len(src):
            raise CodecError("70 tail lit overrun")
        out.extend(src[p:p + n]); p += n
    return p - start


def dec_71(src, p, out):
    """0x71 经典RLE (0x8001D5D4)
    控制字节 c: 0=结束; c&0x80 → [ch]x(c&0x7F); 否则 c 个字面量"""
    start = p
    p += 1
    while True:
        if p >= len(src):
            raise CodecError("71 overrun")
        c = src[p]; p += 1
        if c == 0:
            break
        if c & 0x80:
            n = c & 0x7F
            if p >= len(src):
                raise CodecError("71 ch overrun")
            ch = src[p]; p += 1
            if n:
                out.extend([ch] * n)
        else:
            if p + c > len(src):
                raise CodecError("71 lit overrun")
            out.extend(src[p:p + c]); p += c
    return p - start


def _lzss_body(src, q, out, out_start, getbyte=None):
    """0x73/74 共用 LZSS 主体 (0x8001D9C4 起的无字典路径 / 0x74 经 getbyte)
    返回结束位置 q"""
    while True:
        if q >= len(src):
            raise CodecError("lz overrun")
        if getbyte is None:
            c = src[q]; q += 1
        else:
            c = getbyte()
        if c == 0:
            break
        if c == 127:
            if getbyte is None:
                if q + 3 >= len(src) + 1:
                    raise CodecError("lz127 overrun")
                L = src[q] | src[q + 1] << 8
                ch = src[q + 2]
                q += 3
            else:
                L = getbyte() | getbyte() << 8
                ch = getbyte()
            out.extend([ch] * L)
        elif c == 126:
            if getbyte is None:
                n = src[q]; ch = src[q + 1]; q += 2
            else:
                n = getbyte(); ch = getbyte()
            out.extend([ch] * (n + 4))
        elif c & 0x80:
            if getbyte is None:
                if q + 1 >= len(src):
                    raise CodecError("lzmatch overrun")
                off = ((c & 7) << 8) | src[q]; q += 1
            else:
                off = ((c & 7) << 8) | getbyte()
            dist = off + 1
            ln = ((c >> 3) & 0xF) + 3
            cur = len(out)
            for i in range(ln):
                # 引擎: 若 s3 < dst_start+2048 且 (cur-out_start)<dist → 0
                if (cur - out_start) < dist:
                    out.append(0)
                else:
                    out.append(out[-dist])
                cur += 1
        else:
            n = c & 0x7F
            if getbyte is None:
                if q + n > len(src):
                    raise CodecError("lzlit overrun")
                out.extend(src[q:q + n]); q += n
            else:
                for i in range(n):
                    out.append(getbyte())
    return q


def dec_73(src, p, out, out_start):
    """0x73 LZSS 直接字节 (0x8001D6F8 的 0x73 路径)
    注意: 引擎从 tag+1 开始读控制字节, 结尾再消费终止符"""
    start = p
    q = p + 1
    if q >= len(src):
        raise CodecError("73 empty")
    # 0x8001D9B4: 先读 src[tag+1], 为 0 直接结束 (ptr=tag+2)
    if src[q] == 0:
        return q + 1 - start
    q = _lzss_body(src, q, out, out_start, None)
    # 0x8001DB8C: 结束时 ptr++ (越过 0)
    return q - start


def dec_74(src, p, out, out_start):
    """0x74 LZSS + 字节映射表 (0x8001D6F8 的 0x74 路径)
    [74][n][n字节字典][n个LE16半字][LZSS流(经getbyte映射)]
    引擎用固定 RAM 区: dict@0x8005A618 halves@0x8005A628 table@0x8005A658
    (基址 0x8005A618 → MEM 偏移: dict=0x100 halves=0x110 table=0x140)
    三个区相互重叠: n>0x10 halves 覆盖 dict 尾部; n>0x40 建表覆盖 dict;
    n>24 halves 覆盖 table。用 MEM 数组忠实模拟引擎行为(含重叠副作用)。"""
    start = p
    q = p
    tag = src[q]
    if tag != 0x74:
        raise CodecError("not 74")
    n = src[q + 1]
    q += 2
    raw_dict = src[q:q + n]; q += n
    if len(raw_dict) < n:
        raise CodecError("74 dict overrun")

    MEM = bytearray(0x240)
    # 1) 读入字典 (引擎 0x8001D758-0x8001D784)
    MEM[0x100:0x100 + n] = raw_dict
    # 2) 建表 (引擎 0x8001D788-0x8001D7E0): 先清 table[v]=0, 再找首次出现
    for v in range(256):
        MEM[0x140 + v] = 0
        for k in range(1, n + 1):
            if MEM[0x100 + k - 1] == v:
                MEM[0x140 + v] = k
                break
    # 3) 读入 halves (引擎 0x8001D7E4-0x8001D820, sh 小端半字)
    halves_raw = src[q:q + 2 * n]; q += 2 * n
    if len(halves_raw) < 2 * n:
        raise CodecError("74 halves overrun")
    for k in range(n):
        MEM[0x110 + 2 * k] = halves_raw[2 * k]
        MEM[0x110 + 2 * k + 1] = halves_raw[2 * k + 1]

    state = {"pending": False, "q": q}

    def getbyte():
        if state["pending"]:
            state["pending"] = False
            return state["hi"]
        b = src[state["q"]]
        k = MEM[0x140 + b]
        if k == 0:
            state["q"] += 1
            return b
        h = MEM[0x110 + 2 * (k - 1)] | MEM[0x110 + 2 * (k - 1) + 1] << 8
        state["hi"] = h >> 8
        state["pending"] = True
        state["q"] += 1
        return h & 0xFF

    # 引擎循环后 ptr = getbyte 真实推进位置 (终止符直读已含消费; _lzss_body
    # 的 getbyte 分支不动局部 q, 不能用其返回值 — 实测块0@条目1/0x7D4FC 验证)
    _lzss_body(src, state["q"], out, out_start, getbyte)
    return state["q"] - start


def dec_72(src, p, out, out_start):
    """0x72 平面拆分 (0x8001DBC4)
    [72][len16][内嵌0x73/74流] → 解压到临时, 前半→偶数位, 后半→奇数位
    引擎返回值 = 内嵌流消耗 + 3 (0x8001DC10: a0 = v0+3)"""
    start = p
    ln = src[p + 1] | src[p + 2] << 8
    tmp = bytearray()
    inner = src[p + 3]
    if inner == 0x74:
        used = dec_74(src, p + 3, tmp, 0)
    elif inner == 0x73:
        used = dec_73(src, p + 3, tmp, 0)
    else:
        raise CodecError("72 inner tag %02X" % inner)
    s0 = (ln + 1) >> 1
    s1 = ln >> 1
    if len(tmp) < s0 + s1:
        raise CodecError("72 tmp short %d < %d" % (len(tmp), s0 + s1))
    res = bytearray(ln)
    res[0::2] = tmp[:s0]
    res[1::2] = tmp[s0:s0 + s1]
    out.extend(res)
    return 3 + used  # 引擎 0x8001DC6C: 返回 a0 = 内嵌消耗 + 3


def dec_14(src, p, out):
    """0x14 字典nibble (0x8001DE38)
    [14][n16][16字节字典][n个控制字节, 每个→2输出: 低nibble索引, 高nibble索引]"""
    start = p
    p += 1
    n = src[p] | src[p + 1] << 8
    p += 2
    dic = src[p:p + 16]
    p += 16
    if len(dic) < 16:
        raise CodecError("14 dict overrun")
    for i in range(n):
        if p + i >= len(src):
            raise CodecError("14 ctrl overrun")
        b = src[p + i]
        out.append(dic[b & 0xF])
        out.append(dic[b >> 4])
    return 19 + (n >> 1)  # 引擎返回值 (疑点: 真实读取 19+n)


def dec_30(src, p, out):
    """0x30 RLE-8 (0x8001DEBC) [count][ch] 序列, count=0 结束"""
    start = p
    p += 1
    pairs = 0
    while True:
        if p >= len(src):
            raise CodecError("30 overrun")
        c = src[p]; p += 1
        if c == 0:
            break
        if p >= len(src):
            raise CodecError("30 ch overrun")
        ch = src[p]; p += 1
        out.extend([ch] * c)
        pairs += 1
    return 2 + 2 * pairs


def dec_31(src, p, out):
    """0x31 RLE-16 (0x8001DF1C) [count16][ch] 序列, count=0 结束"""
    start = p
    p += 1
    total = 0
    while True:
        if p + 1 >= len(src):
            raise CodecError("31 overrun")
        c = src[p] | src[p + 1] << 8
        p += 2
        if c == 0:
            break
        if p >= len(src):
            raise CodecError("31 ch overrun")
        ch = src[p]; p += 1
        out.extend([ch] * c)
        total += 3
    return total + 3


def dec_40(src, p, out):
    """0x40 单次RLE (0x8001DF84) [40][ch][count16]"""
    if p + 3 >= len(src):
        raise CodecError("40 overrun")
    ch = src[p + 1]
    n = src[p + 2] | src[p + 3] << 8
    out.extend([ch] * n)
    return 4


def dec_20(src, p, out, out_start):
    """0x20 LZSS变体 (0x8001DFD0)
    c=0 结束; c<0x80 字面量c个; 0x80<=c<0xC0 长匹配(len=(c&3F)+3, off16绝对);
    c>=0xC0 短匹配(len=(c&3F)+3, off8相对, dist=off8+1)"""
    start = p
    p += 1
    consumed = 1  # t2 初值 1 (含 tag)
    while True:
        if p >= len(src):
            raise CodecError("20 overrun")
        c = src[p]; p += 1
        if c == 0:
            break
        if c < 0x80:
            if p + c > len(src):
                raise CodecError("20 lit overrun")
            out.extend(src[p:p + c]); p += c
            consumed += 1 + c
        elif c < 0xC0:
            if p + 1 >= len(src):
                raise CodecError("20 off16 overrun")
            off = src[p] | src[p + 1] << 8
            p += 2
            n = (c & 0x3F) + 3
            base = out_start + off
            for i in range(n):
                out.append(out[base + i])
            consumed += 3
        else:
            if p >= len(src):
                raise CodecError("20 off8 overrun")
            off = src[p] + 1
            p += 1
            n = (c & 0x3F) + 3
            cur = len(out)
            for i in range(n):
                out.append(out[cur - off + i])
            consumed += 2
    return consumed + 1  # +1 = 终止符


def decode_block(src, p, out, out_start):
    """解码一个块 (0x8001DC8C). 返回 (consumed, ok)"""
    tag = src[p]
    if tag == 0x70:
        return dec_70(src, p, out)
    if tag == 0x71:
        return dec_71(src, p, out)
    if tag == 0x73:
        return dec_73(src, p, out, out_start)
    if tag == 0x74:
        return dec_74(src, p, out, out_start)
    if tag == 0x72:
        return dec_72(src, p, out, out_start)
    if tag == 0x14:
        return dec_14(src, p, out)
    if tag == 0x30:
        return dec_30(src, p, out)
    if tag == 0x31:
        return dec_31(src, p, out)
    if tag == 0x40:
        return dec_40(src, p, out)
    if tag == 0x20:
        return dec_20(src, p, out, out_start)
    if tag == 0xFF:
        return dec_ff(src, p, out)[0]
    raise CodecError("unknown tag %02X @%d" % (tag, p))


def unpack_stream(src, p=0, max_blocks=4096):
    """顶层 0x8001E0F0: 连续块流; 每块输出占用独立 8192 字节槽位
    (引擎 0x8001E14C 延迟槽: addiu s1, s1, 8192)
    返回 (输出bytes, 终止位置, 块数, 是否正常结束)"""
    out = bytearray()
    blocks = 0
    ok = True
    try:
        while p < len(src) and blocks < max_blocks:
            tag = src[p]
            if tag == 0:
                break
            block_start = len(out)
            consumed = decode_block(src, p, out, block_start)
            if consumed is None or consumed <= 0 or consumed >= 0x2004:
                ok = False
                break
            p += consumed
            # 8192 槽位: 输出超长截断, 不足补零
            end = block_start + 8192
            if len(out) > end:
                del out[end:]
            else:
                out.extend(b"\x00" * (end - len(out)))
            blocks += 1
    except CodecError:
        ok = False
    except (IndexError, ValueError, OverflowError):
        ok = False
    return bytes(out), p, blocks, ok
