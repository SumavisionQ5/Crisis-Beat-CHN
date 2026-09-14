---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '578713a3-b4bf-4522-bb71-b4b3a655ff8d'
  PropagateID: '578713a3-b4bf-4522-bb71-b4b3a655ff8d'
  ReservedCode1: '59420928-4e9f-4b7b-a899-17db90dbff9f'
  ReservedCode2: '59420928-4e9f-4b7b-a899-17db90dbff9f'
---

# Crisis Beat (PS1, Japan) 逆向工程综合文档

> 版本：2026-09-13 · 适用范围：日版镜像 `Crisis Beat (Japan).bin`（SLPS-01490）
> 本文档汇总对**原始日版**的逆向研究结论，供后续研究者参考。
> 不含任何修改镜像/补丁的 hack 成果；补丁相关历史与问题见 `docs/TEXT_RENDER_ENGINE_NOTES_0913.md` 第四节。

---

## 1. 总览

| 子系统 | 结论 | 证据 |
|--------|------|------|
| 光盘数据组织 | DATA.0 条目表 @ LBA 1184，实测 **513 条**（旧文档称 2037 项，以解析器为准） | `tools/extract_entries.py` |
| 场景包压缩 | 自研 pak 块流（tag 分发） | `misc/codecs.py`（逆向 0x8001E0F0） |
| 文本编码 | 1B 码 0x01-0xEF + `FF xx`/`FE xx` 扩展 | `docs/TEXT_FORMAT_DOC.md` |
| 文本位置 | **33 个内容文本段**（每段双份拷贝，镜像副本 +0x02400000） | `tools/decode_text.py` `TEXT_SEGS` |
| 日文码表 | kana_00_7F + kanjiA_80_EF + FF 映射 | `assets/codetable_master.json` |
| 字库装载 | 14 处数据区窗（F2 2072B + FB 7264B） | `docs/FONT_LOAD_DOC.md` |
| VRAM 映射 | slot73/74 + TSB5/29/31 | `docs/FONT_LOAD_DOC.md` |
| 文本渲染 | 解码器/渲染引擎/字体上传反汇编 | `docs/TEXT_RENDER_ENGINE_NOTES_0913.md` |

---

## 2. 光盘与 DATA.0

### 2.1 物理与逻辑

- 镜像为 MODE2/2352 扇区；每扇区用户数据 2048B，偏移 `lba*2352 + 24`。
- 数据轨起始 LBA 1184（逻辑 0x250000，相对 DATA.0 0x290000 的说法来自早期文档，两者对应同一位置）。
- 条目表位于 DATA.0 开头 4 个扇区，每项 u32 LE。实测解析出 **513 条**（旧文档称 2037 项，实际以解析器结果为准；末条 `0x89a80c64` 为表尾越界读出的哨兵/垃圾值，真实条目止于 `0x65bc000`）。

### 2.2 读取方式

```python
file_off = lba * 2352 + 24          # 物理偏移
logical   = lba * 2048 + 偏移        # 逻辑坐标 (跨扇区)
```

文本块逻辑坐标 = `DATA_BASE(0x250000) + 相对偏移`。

---

## 3. 场景包压缩格式（pak）

顶层 `unpack_stream`（逆向自 0x8001E0F0）：

```
while src[p] != 0x00:
    块 = decode_block(src, p, out, block_start)
    p += consumed
    out 写入 dst + 8192*块号
```

块头 1 字节 tag 分发：

| tag | 含义 | 说明 |
|-----|------|------|
| 0x14 | 字典 nibble | `[14][n16][16B字典][n控制字节]` |
| 0x20 | LZSS 变体 | 字面量/绝对匹配/相对匹配 |
| 0x30 | RLE8 | `[count][ch]` |
| 0x31 | RLE16 | `[count16][ch]` |
| 0x40 | RLE 单次 | `[40][ch][count16]` |
| 0x70 | 位选择 RLE | 标志位 |
| 0x71 | 经典 RLE | 控制字节 |
| 0x72 | 平面拆分 | 内嵌 0x73/0x74 → 奇偶平面 |
| 0x73 | LZSS | 直接字节 |
| 0x74 | LZSS + 映射表 | 建表+半字映射 |
| 0xFF | 原样拷贝 | `[FF][len_lo][len_hi][data]` |
| 0x00 | 结束 | |

完整实现见 `misc/codecs.py`（含 0x74 的 RAM 区重叠副作用模拟）。

---

## 4. 文本系统

### 4.1 编码规则

| 码 | 含义 |
|----|------|
| 0x01-0xEF | 单字节（假名/汉字） |
| 0xF0 | 转义 |
| 0xF1 | 句中停顿/翻页（译文以 ∥ 表示） |
| 0xF2/F3 | 块标记 |
| 0xF4/F5 | 清屏/滚屏 |
| 0xF6 | 块尾/换行 |
| `FF xx` | 码 0xF0-0x1AF（xx = 码-0xF0） |
| `FE xx` | 码 0x1E0-0x2DF（xx = 码-0x1E0） |
| 0x00 | 全角空格/终止 |

- 每帧：`[说话人标记] F3 [正文] F6`。
- 每帧文本码数 ≤ 20。
- **FF 双字节解码**：按码表键 `FFxx` 直接查表（`ff_low_map` 覆盖 00-0F，`bankB_FF10_BF` 覆盖 10-BF），不是线性 `code-0xF0` 映射（后者仅适用于汉化码表 codetable_v3）。

### 4.2 块结构

```
[token]* [00 00] [零填充...]
```

### 4.3 文本块位置

全部 **33 个内容文本段**（地址见 `tools/decode_text.py` 的 `TEXT_SEGS`），每段在镜像中有双份拷贝（镜像副本地址 +0x02400000）。早期文档中的 "30 ENTRY / 62 块 / ABS 字典" 说法为历史过程记录，最终以 `TEXT_SEGS` 实测清单为准。

---

## 5. 码表

### 5.1 日文原表（`assets/codetable_master.json`）

- `kana_00_7F`：128 项（假名/符号）
- `kanjiA_80_EF`：112 项（汉字）
- `bankB_FF10_BF`：扩展
- FF 映射：`xx>=0x80` → VRAM code=xx；`xx<0x80` → code=xx+0x3A

> 注意：汉化版新码表（codetable_v3 等）**不属于**原始日版研究资料，本仓库不收录。

---

## 6. 字库装载

### 6.1 装载器

- F2_VA=0x800A9D3C（F2' 流），FB_VA=0x800AA560（FB' 流），FB_END=0x800AC1C0。
- 数据区 14 处窗口（F2 窗 2072B + FB 窗 7264B），位置见 `docs/FONT_LOAD_DOC.md` 2.3。
- 每窗口解压：F2 → 8192B（TIM2'），FB → 24576B（bankB 等）。
- 槽 73/74 在 entry 1/3/5/7/9/11/12/13/14/15 各加载 10 处。

### 6.2 VRAM 映射

```
码 < 0x100  → TSB5
码 < 0x200  → TSB29
码 >= 0x200 → TSB31
字形 U = (码 & 0xF) << 4
字形 V = 码 & 0xF0
```

> 补充（09-13 反汇编）：渲染引擎实际只处理 TPAGE 5 与 TPAGE 29，**无 TPAGE 31 渲染路径**；码 >= 0x200 的字符依赖槽位 74 的 TSB31 字形区，但引擎用 `andi` 将字符码截断为 8 位参与 UV 计算，详见 `docs/TEXT_RENDER_ENGINE_NOTES_0913.md`。

---

## 7. 参考文件

- `docs/TEXT_FORMAT_DOC.md` — 文本格式细节
- `docs/FONT_LOAD_DOC.md` — 字库装载细节
- `docs/TEXT_RENDER_ENGINE_NOTES_0913.md` — 09-13 反汇编补充（解码器/渲染引擎/字体上传）
- `docs/text_extraction_report_zh.md` — 提取/翻译阶段报告
- `docs/progress_0904.md` — 码表建立进展
- `docs/SESSION_NOTES_0904.md` — 阶段结题纪要
- `misc/codecs.py` — 压缩解压完整实现
- `misc/engine137b_templates.py` — 文本块模板（历史脚本，含过时地址，仅参考）
- `misc/disc_lzss.py` — DATA.0 条目 LZSS 探测（历史脚本，仅参考）

> AI生成