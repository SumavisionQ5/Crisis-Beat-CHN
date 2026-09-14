---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '53b83e8d-cacf-4e6a-9d9b-bc362b0d8d28'
  PropagateID: '53b83e8d-cacf-4e6a-9d9b-bc362b0d8d28'
  ReservedCode1: 'ef850d6c-d9a7-4a3a-904e-1c94969e7ecd'
  ReservedCode2: 'ef850d6c-d9a7-4a3a-904e-1c94969e7ecd'
---

# Crisis Beat (PS1, Japan) — 原始日版逆向研究资料集

> 本仓库收录对 **《Crisis Beat》PS1 日版**（SLPS-01490）**原始镜像**的逆向研究资料：
> 文本提取、字库格式、光盘读取/VRAM 传输链路、日文原码表，以及完整的中英双语研究文档。
> **不含任何修改镜像/补丁等 hack 成果**，也不包含游戏本体（版权归原厂商所有）。

---

## 仓库内容

| 目录 | 内容 |
|------|------|
| `text/` | 日文原文（原始提取 / 修正 / v3 重解码）、v331 全量译文（237 条）、中文易读版、中日对照 |
| `assets/` | 日文原码表（`codetable_master.json` 等） |
| `docs/` | 研究文档：文本格式、字库装载、逆向综合、09-13 反汇编补充、阶段报告 |
| `misc/` | 压缩/解压格式研究（`codecs.py`）、条目表 LZSS 探测（`disc_lzss.py`）、文本块模板分析（`engine137b_templates.py`） |
| `tools/` | 只读研究工具：文本解码、条目提取、VRAM 字形映射 |

### 文件清单

- **text/**
  - `dialogue_original_raw.txt` — 原始提取（含早期错码，研究用）
  - `dialogue_original_final.txt` — 修正后日文原文
  - `dialogue_original_v3.txt` — 按 v3 码表重解码的权威日文原文
  - `v331_translation_clean.txt` — v331 全量翻译（237 条，含段落与场景说明）
  - `dialogue_zh_easyread.txt` — 中文全译文（易读版）
  - `dialogue_zhja_compare.txt` — 日文/中文逐框对照
- **assets/**
  - `codetable_master.json` — 日文原版码表（假名/汉字/FF 映射）
  - `codetable_final.json` / `codetable_full.json` / `codetable_kana.json` / `codetable_kana2.json` — 码表研究中间版本
- **docs/**
  - `FONT_LOAD_DOC.md` — 字库加载链路与码表
  - `TEXT_FORMAT_DOC.md` — 文本压缩与存储位置
  - `TEXT_RENDER_ENGINE_NOTES_0913.md` — 09-13 反汇编补充（解码器/渲染引擎/字体上传）
  - `REVERSE_ENGINEERING_ZH.md` / `REVERSE_ENGINEERING_EN.md` — 逆向综合文档（中/英）
  - `text_extraction_report_zh.md` — 提取/翻译阶段报告
  - `progress_0904.md`、`SESSION_NOTES_0904.md` — 早期阶段记录
- **misc/**、**tools/** — 见上表

---

## 快速上手

### 环境要求

- Python 3.8+（仅标准库，无第三方依赖）
- 原版日版镜像 `Crisis Beat (Japan).bin`（MODE2/2352，676,665,696 字节）
- 任意 PS1 模拟器（ePSXe 1.7、PCSX-ReARMed 等）用于验证

### 解码文本

```bash
python tools/decode_text.py "Crisis Beat (Japan).bin" --all   # 解码全部 33 个内容文本段
python tools/decode_text.py "Crisis Beat (Japan).bin" 0x0246915C 0x12  # 指定偏移（开场第一句）
```

### 提取场景包条目

```bash
python tools/extract_entries.py "Crisis Beat (Japan).bin"   # 按条目表提取场景包
```

### 验证压缩实现

```bash
python -c "import sys; sys.path.insert(0,'misc'); import codecs; print(codecs.__doc__)"
```

> 注：`misc/disc_lzss.py`、`misc/engine137b_templates.py` 是研究过程脚本，内部含本机绝对路径与历史地址数据（部分地址与最终实证有出入），仅作参考，不可直接运行。

---

## 主要研究结论（摘要）

- **光盘组织**：DATA.0 条目表 @ LBA 1184，实测 513 条（旧文档称 2037 项，实际解析器结果为 513；末条 `0x89a80c64` 为表尾越界读出的哨兵值）
- **场景包压缩**：自研 pak 块流（tag: 14/20/30/31/40/70/71/72/73/74/FF）
- **文本编码**：1B 码 0x01-0xEF + 双字节 `FF xx`（码 0xF0-0x1AF）/ `FE xx`（码 0x1E0-0x2DF）；控制符 F1=换行、F3=段尾、F6=块尾
- **文本位置**：33 个内容文本段（每段双份拷贝，镜像副本地址 +0x02400000）；段地址清单见 `tools/decode_text.py` 的 `TEXT_SEGS`
- **日文码表**：`kana_00_7F` + `kanjiA_80_EF` + `bankB_FF10_BF`，FF 映射 `xx>=0x80` 直映 / `<0x80` 偏移 +0x3A
- **字库加载**：14 处数据区窗（F2 2072B + FB 7264B）→ 装载器解压 → RAM → VRAM（TSB5/29/31 + 槽 73/74）
- **字形地址**：`U=(码&0xF)<<4`，`V=码&0xF0`
- **渲染引擎**（09-13 反汇编）：只支持 TPAGE 5/29，无 TPAGE 31 渲染路径；显示缓冲 15×15×2B 无边界检查

---

## 状态与边界

- 本仓库**只发布原始日版研究资料**，不发布任何修改镜像/补丁。
- 汉化补丁曾尝试多轮（v17/v55-v59），**因「字形替换后开场死机」问题未解决，全部不发布**；崩溃排查记录见 `docs/TEXT_RENDER_ENGINE_NOTES_0913.md` 第四节，供后续研究者参考。
- 游戏版权归原厂商所有；本仓库仅收录合法持有的日版镜像的**研究文档与文本数据**。

---

## 许可

- 资料遵循 **CC BY-NC-SA 4.0**（署名-非商业-相同方式共享）发布。
- 游戏本体不在本仓库中。

*文档最后更新：2026-09-13*

> AI生成