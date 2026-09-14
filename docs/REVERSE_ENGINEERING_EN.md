---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '62db2705-5015-4078-bef6-e22a3dedf144'
  PropagateID: '62db2705-5015-4078-bef6-e22a3dedf144'
  ReservedCode1: '2328214d-e6c7-465a-b2cc-6260cdbc97fa'
  ReservedCode2: '2328214d-e6c7-465a-b2cc-6260cdbc97fa'
---

# Crisis Beat (PS1, Japan) Reverse-Engineering Summary

> Version: 2026-09-13 · Applies to: Japanese disc image `Crisis Beat (Japan).bin` (SLPS-01490)
> This document summarizes reverse-engineering findings about the **original Japanese release**, for reference by future researchers.
> It deliberately excludes any modified-image/patch ("hack") artifacts; see `docs/TEXT_RENDER_ENGINE_NOTES_0913.md` §4 for the patch history.

---

## 1. Overview

| Subsystem | Finding | Evidence |
|-----------|---------|----------|
| Disc data organization | DATA.0 entry table @ LBA 1184, **513 entries** (measured; early docs said 2037, actual parser yields 513) | `tools/extract_entries.py` |
| Scenario package compression | Custom pak block stream (tag dispatch) | `misc/codecs.py` (reverse-engineered from 0x8001E0F0) |
| Text encoding | 1-byte codes 0x01-0xEF + `FF xx`/`FE xx` extensions | `docs/TEXT_FORMAT_DOC.md` |
| Text location | 33 content text segments (each dual-copied, mirror at +0x02400000) | `tools/decode_text.py` `TEXT_SEGS` |
| Japanese codetable | kana_00_7F + kanjiA_80_EF + FF mapping | `assets/codetable_master.json` |
| Font loading | 14 data-area windows (F2 2072B + FB 7264B) | `docs/FONT_LOAD_DOC.md` |
| VRAM mapping | slot73/74 + TSB5/29/31 | `docs/FONT_LOAD_DOC.md` |
| Text rendering | disassembly of decoder/renderer/font upload | `docs/TEXT_RENDER_ENGINE_NOTES_0913.md` |

---

## 2. Disc & DATA.0

### 2.1 Physical / logical

- Image is MODE2/2352 sectors; 2048B user data per sector at `lba*2352 + 24`.
- Data track starts at LBA 1184 (logical 0x250000; the "0x290000 relative to DATA.0" phrasing in early docs refers to the same position).
- Entry table: first 4 sectors of DATA.0, u32 LE each. Measured **513 entries** (early docs said 2037; the parser result of 513 is authoritative). The trailing `0x89a80c64` is a sentinel/garbage value read past the table end — real entries end at `0x65bc000`.

### 2.2 Reading

```python
file_off = lba * 2352 + 24          # physical offset
logical   = lba * 2048 + offset      # logical coordinates (cross-sector)
```

Text block logical address = `DATA_BASE(0x250000) + relative offset`.

---

## 3. Scenario package compression (pak)

Top-level `unpack_stream` (reverse-engineered from 0x8001E0F0):

```
while src[p] != 0x00:
    block = decode_block(src, p, out, block_start)
    p += consumed
    out written to dst + 8192*block_no
```

1-byte tag dispatch:

| tag | meaning | notes |
|-----|---------|-------|
| 0x14 | dict nibble | `[14][n16][16B dict][n ctrl bytes]` |
| 0x20 | LZSS variant | literal/absolute-match/relative-match |
| 0x30 | RLE8 | `[count][ch]` |
| 0x31 | RLE16 | `[count16][ch]` |
| 0x40 | RLE single | `[40][ch][count16]` |
| 0x70 | bit-select RLE | flag bits |
| 0x71 | classic RLE | control byte |
| 0x72 | plane split | embedded 0x73/0x74 → odd/even planes |
| 0x73 | LZSS | direct bytes |
| 0x74 | LZSS + map table | build table + halfword map |
| 0xFF | raw copy | `[FF][len_lo][len_hi][data]` |
| 0x00 | end | |

Full implementation in `misc/codecs.py` (including 0x74's RAM overlap side effects).

---

## 4. Text system

### 4.1 Encoding rules

| code | meaning |
|------|---------|
| 0x01-0xEF | single byte (kana/kanji) |
| 0xF0 | escape |
| 0xF1 | mid-sentence pause / page turn (∥ in translations) |
| 0xF2/F3 | block markers |
| 0xF4/F5 | clear/scroll |
| 0xF6 | block end / newline |
| `FF xx` | code 0xF0-0x1AF (xx = code-0xF0) |
| `FE xx` | code 0x1E0-0x2DF (xx = code-0x1E0) |
| 0x00 | full-width space / terminator |

- Each frame: `[speaker marker] F3 [body] F6`.
- Frame body: ≤ 20 text codes.
- **FF two-byte decoding**: lookup by codetable key `FFxx` directly (`ff_low_map` covers 00-0F, `bankB_FF10_BF` covers 10-BF) — not the linear `code-0xF0` mapping (that applies only to the Chinese codetable codetable_v3).

### 4.2 Block layout

```
[token]* [00 00] [zero fill...]
```

### 4.3 Text block locations

All **33 content text segments** (addresses in `tools/decode_text.py`'s `TEXT_SEGS`), each dual-copied in the image (mirror copy at +0x02400000). The early-doc "30 ENTRY / 62 blocks / ABS dict" phrasing is historical; the authoritative list is `TEXT_SEGS`.

---

## 5. Codetables

### 5.1 Japanese original table (`assets/codetable_master.json`)

- `kana_00_7F`: 128 entries (kana/symbols)
- `kanjiA_80_EF`: 112 entries (kanji)
- `bankB_FF10_BF`: extension
- FF mapping: `xx>=0x80` → VRAM code=xx; `xx<0x80` → code=xx+0x3A

> Note: the Chinese-translation codetable (codetable_v3 etc.) is **not** part of the original-Japanese research assets and is excluded from this repository.

---

## 6. Font loading

### 6.1 Loader

- F2_VA=0x800A9D3C (F2' stream), FB_VA=0x800AA560 (FB' stream), FB_END=0x800AC1C0.
- 14 data-area windows (F2 2072B + FB 7264B), positions in `docs/FONT_LOAD_DOC.md` §2.3.
- Each window decompresses: F2 → 8192B (TIM2'), FB → 24576B (bankB etc.).
- Slots 73/74 are loaded 10 times in entries 1/3/5/7/9/11/12/13/14/15.

### 6.2 VRAM mapping

```
code < 0x100  → TSB5
code < 0x200  → TSB29
code >= 0x200 → TSB31
glyph U = (code & 0xF) << 4
glyph V = code & 0xF0
```

> Update (09-13 disassembly): the renderer only handles TPAGE 5 and TPAGE 29 — **there is no TPAGE 31 render path**. Codes >= 0x200 rely on the TSB31 glyph area of slot 74, but the engine `andi`-truncates the character code to 8 bits for UV math; see `docs/TEXT_RENDER_ENGINE_NOTES_0913.md`.

---

## 7. Reference files

- `docs/TEXT_FORMAT_DOC.md` — text format details
- `docs/FONT_LOAD_DOC.md` — font loading details
- `docs/TEXT_RENDER_ENGINE_NOTES_0913.md` — 09-13 disassembly addendum (decoder/renderer/font upload)
- `docs/text_extraction_report_zh.md` — extraction & translation phase report
- `docs/progress_0904.md` — codetable progress
- `docs/SESSION_NOTES_0904.md` — phase summary
- `misc/codecs.py` — complete compression implementation
- `misc/engine137b_templates.py` — text block template parser (historical script, outdated addresses, reference only)
- `misc/disc_lzss.py` — DATA.0 entry LZSS probing (historical script, reference only)

> AI生成