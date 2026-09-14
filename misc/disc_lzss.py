#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""disc_lzss.py: 对 DATA.0 条目跑 LZSS 暴力解压, 找字库压缩流
判据(强到弱):
  S1: 输出含 TIM 头 10 00 00 00 08 00 00 00 (4bpp TIM)
  S2: 输出含 TIM 头 10 00 00 00 09 00 00 00 (8bpp TIM)
  S3: 输出含 9连 0x22 (字形空白)
  S4: 输出三值率(0x22/0x11/0x00/0x01/0x10/0x12/0x21 组合) > 85% 且含 22
范围: 全部 2037 条目, 尺寸>0x400 才试
参数: spos=0/1/2/4, lit_bit=0/1, msbf=T/F, ref=0-5
"""
import struct, sys

P = r"C:\Users\Administrator\.local\share\TeleAgent\TeleAgent的工作空间\.temp\cb"
BIN = r"D:\游轮格斗汉化\Crisis Beat (Japan).bin"
f = open(BIN, "rb")
DATA_LBA = 1184

def user_sector(lba):
    f.seek(lba * 2352 + 24)
    return f.read(2048)

def read_at_cross(off, size):
    out = bytearray()
    cur, remaining = off, size
    while remaining > 0:
        f.seek((DATA_LBA + cur // 2048) * 2352 + 24)
        chunk = f.read(2048)
        if not chunk: break
        io = cur % 2048
        take = min(2048 - io, remaining)
        out += chunk[io:io + take]
        cur += take; remaining -= take
    return bytes(out)

# 条目表
entries = []
for page in range(4):
    vals = struct.unpack("<512I", user_sector(DATA_LBA + page))
    prev = entries[-1] if entries else -1
    for v in vals:
        if v < prev: break
        if (v & 0xFF) != 0 and v > 0x2000: break
        entries.append(v); prev = v
entries.append(0x11900000)

TIM4 = b"\x10\x00\x00\x00\x08\x00\x00\x00"
TIM8 = b"\x10\x00\x00\x00\x09\x00\x00\x00"
RUN22 = b"\x22" * 9

def lzss(src, spos, max_out, lit_bit, msbf, ref):
    out = bytearray()
    sp = spos
    fb = 0; fn = 0
    n = len(src)
    while len(out) < max_out and sp < n:
        if fn == 0:
            if sp >= n: break
            fb = src[sp]; sp += 1
            fn = 8
        bit = (fb >> (7 if msbf else 0)) & 1
        if not msbf: fb >>= 1
        else: fb = (fb << 1) & 0xFF
        fn -= 1
        if bit == lit_bit:
            if sp >= n: break
            out.append(src[sp]); sp += 1
        else:
            if sp + 1 >= n: break
            b0, b1 = src[sp], src[sp + 1]
            sp += 2
            if ref == 0:   v = b0 | (b1 << 8); off = (v >> 4) & 0xFFF; ln = (v & 0xF) + 3
            elif ref == 1: v = b0 | (b1 << 8); off = v & 0xFFF; ln = (v >> 12) + 3
            elif ref == 2: v = (b0 << 8) | b1; off = (v >> 4) & 0xFFF; ln = (v & 0xF) + 3
            elif ref == 3: v = b0 | (b1 << 8); off = v & 0x1FFF; ln = (v >> 13) + 3
            elif ref == 4: v = b0 | (b1 << 8); off = (v >> 3) & 0x1FFF; ln = (v & 7) + 3
            else:          v = (b0 << 8) | b1; off = v & 0xFFF; ln = (v >> 12) + 3
            if off == 0: return None
            opos = len(out) - off
            if opos < 0: return None
            for i in range(ln):
                out.append(out[opos + i])
                if len(out) >= max_out: break
    return bytes(out)

