#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析 Crisis Beat DATA.0 条目表（只读，不写盘）。

用法:
    python extract_entries.py <Crisis Beat (Japan).bin> [max_entries]

- 解析 DATA.0 开头的条目表（u32 LE），打印条目数量、前几条与末尾。
- 可选参数 max_entries 限制打印数量。
"""
import struct, sys

DATA_LBA = 1184          # 数据轨起始扇区
SECTOR = 2352            # MODE2/2352
USER = 2048
HEADER = 24

def parse_entry_table(f, max_entries=None):
    f.seek(DATA_LBA * SECTOR + HEADER)
    raw = f.read(2048 * 64)
    entries = []
    prev = -1
    for i in range(0, len(raw) - 4, 4):
        v = struct.unpack("<I", raw[i:i+4])[0]
        if v < prev:
            break
        entries.append(v)
        prev = v
        if max_entries and len(entries) >= max_entries:
            break
    return entries

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    path = sys.argv[1]
    max_entries = int(sys.argv[2]) if len(sys.argv) >= 3 else None
    with open(path, "rb") as f:
        entries = parse_entry_table(f, max_entries)
    print("条目数: %d" % len(entries))
    print("前 5: %s" % [hex(e) for e in entries[:5]])
    print("末 3: %s" % [hex(e) for e in entries[-3:]])

if __name__ == "__main__":
    main()