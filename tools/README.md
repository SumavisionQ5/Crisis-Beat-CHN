---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '83ccd7ec-471d-4a97-9163-5c368e0680f4'
  PropagateID: '83ccd7ec-471d-4a97-9163-5c368e0680f4'
  ReservedCode1: 'c4d58370-4d5c-4c1a-8318-e01f6062a12c'
  ReservedCode2: 'c4d58370-4d5c-4c1a-8318-e01f6062a12c'
---

# tools/ — 只读研究工具

这些工具只读镜像、不修改任何文件，用于验证/复现逆向结论。

| 文件 | 作用 | 用法 |
|------|------|------|
| `decode_text.py` | 解码文本块（指定偏移 / 全段解码 / 扫描） | `python decode_text.py 镜像.bin [偏移hex] [长度hex]` |
| `extract_entries.py` | 解析 DATA.0 条目表 | `python extract_entries.py 镜像.bin [max_entries]` |

## 依赖

- Python 3.8+（仅标准库）
- 镜像 `Crisis Beat (Japan).bin`（MODE2/2352）

## 偏移基准

段地址（如 `0x0246915C`）是**逻辑用户数据偏移**：

```
磁盘文件偏移 = (u // 2048) * 2352 + 24 + (u % 2048)
```

即不额外加 DATA_LBA(1184)。DATA.0 的 LBA(1184) 只用于定位条目表；
条目表中的偏移（如 `0x2000`）相对 DATA.0 起始，需加上 `1184 * 2048` 转为逻辑坐标。

## 示例

```bash
# 解码开场第一句（TEXT[00]，武器确认）
python decode_text.py "Crisis Beat (Japan).bin" 0x0246915C 0x12

# 解码开场第一句（TEXT[01]）
python decode_text.py "Crisis Beat (Japan).bin" 0x024691E0 0x32

# 解码全部 33 个内容文本段
python decode_text.py "Crisis Beat (Japan).bin" --all

# 扫描条目表内疑似文本（结果含大量字体/资源误报，仅作快速浏览）
python decode_text.py "Crisis Beat (Japan).bin"

# 解析条目表（513 条）
python extract_entries.py "Crisis Beat (Japan).bin"
```

## 说明

- 码表读取 `assets/codetable_master.json`（日文原表），与 `docs/` 中描述一致。
- `extract_entries.py` 输出的末条 `0x89a80c64` 是表尾越界读出的垃圾值（真实条目止于 `0x65bc000`），属已知现象。
- 这些工具**不包含任何写盘能力**，只用于验证逆向结论。

> AI生成