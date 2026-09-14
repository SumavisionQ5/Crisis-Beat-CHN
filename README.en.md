---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '93c09a34-28d4-43e4-9b4f-92c9f6a0ec7b'
  PropagateID: '93c09a34-28d4-43e4-9b4f-92c9f6a0ec7b'
  ReservedCode1: 'bff0a037-d074-41ea-bb91-7e87853ed556'
  ReservedCode2: 'bff0a037-d074-41ea-bb91-7e87853ed556'
---

# Crisis Beat (PS1, Japan) — Original Japanese Research Assets

> This repository collects reverse-engineering research on the **original Japanese release** of *Crisis Beat* (PS1, SLPS-01490):
> text extraction, font format, disc-reading/VRAM-transfer pipeline, Japanese codetables, and complete bilingual research docs.
> **It contains NO game patches/hacks and NO game image** (copyright belongs to the original publisher; only research data is included).

---

## Contents

| Directory | What it holds |
|-----------|---------------|
| `text/` | Japanese original text (raw decode / cleaned / v3 re-decode), v331 full translation (237 lines), Chinese easy-read version, JP/CN per-frame comparison |
| `assets/` | Japanese original codetables (`codetable_master.json` etc.) |
| `docs/` | Research docs: text format, font loading, reverse-engineering, 09-13 disassembly addendum, phase reports |
| `misc/` | Compression research (`codecs.py` — pak codec), entry-table LZSS probing (`disc_lzss.py`), text block template analysis (`engine137b_templates.py`) |
| `tools/` | Read-only research tools: text decode, entry extraction, VRAM glyph mapping |

### File list

- **text/**
  - `dialogue_original_raw.txt` — raw extraction (contains early mis-decodes, research use)
  - `dialogue_original_final.txt` — corrected Japanese original
  - `dialogue_original_v3.txt` — authoritative JP text re-decoded with v3 codetable
  - `v331_translation_clean.txt` — v331 full translation (237 lines, with scene notes)
  - `dialogue_zh_easyread.txt` — Chinese full translation (easy-read)
  - `dialogue_zhja_compare.txt` — JP/CN per-frame comparison
- **assets/**
  - `codetable_master.json` — Japanese original codetable (kana/kanji/FF mapping)
  - `codetable_final.json` / `codetable_full.json` / `codetable_kana.json` / `codetable_kana2.json` — intermediate codetable research versions
- **docs/**
  - `FONT_LOAD_DOC.md` — font loading pipeline & codetable
  - `TEXT_FORMAT_DOC.md` — text compression & storage locations
  - `TEXT_RENDER_ENGINE_NOTES_0913.md` — 09-13 disassembly addendum (decoder/renderer/font upload)
  - `REVERSE_ENGINEERING_ZH.md` / `REVERSE_ENGINEERING_EN.md` — comprehensive reverse-engineering summary (CN/EN)
  - `text_extraction_report_zh.md` — extraction & translation phase report
  - `progress_0904.md`, `SESSION_NOTES_0904.md` — early phase notes
- **misc/**、**tools/** — see table above

---

## Quick start

### Requirements

- Python 3.8+ (stdlib only, no third-party deps)
- Original JP disc image `Crisis Beat (Japan).bin` (MODE2/2352, 676,665,696 bytes)
- Any PS1 emulator (ePSXe 1.7, PCSX-ReARMed, ...) for verification

### Decode text

```bash
python tools/decode_text.py "Crisis Beat (Japan).bin" --all   # decode all 33 content text segments
python tools/decode_text.py "Crisis Beat (Japan).bin" 0x024691E0 0x32  # decode a specific offset (first line)
```

> Note: `misc/disc_lzss.py` and `misc/engine137b_templates.py` are historical research scripts containing local absolute paths and outdated addresses (some differ from the final findings) — reference only, not directly runnable.

### Extract scenario entries

```bash
python tools/extract_entries.py "Crisis Beat (Japan).bin"
```

---

## Research summary

- **Disc organization**: DATA.0 entry table @ LBA 1184, **513 entries measured** (early docs said 2037; the parser result is authoritative; the trailing `0x89a80c64` is a garbage sentinel read past the table end — real entries end at `0x65bc000`)
- **Scenario compression**: custom pak block stream (tags 14/20/30/31/40/70/71/72/73/74/FF)
- **Text encoding**: 1-byte codes 0x01-0xEF + two-byte `FF xx` (codes 0xF0-0x1AF) / `FE xx` (0x1E0-0x2DF); control F1=line break, F3=segment end, F6=block end
- **Text locations**: 33 content text segments (each dual-copied, mirror copy at +0x02400000); full address list in `tools/decode_text.py` `TEXT_SEGS`. The early-doc "30 ENTRY / 62 blocks / ABS dict" phrasing is historical — `TEXT_SEGS` is authoritative.
- **Japanese codetable**: `kana_00_7F` + `kanjiA_80_EF` + `bankB_FF10_BF`; two-byte `FFxx` is decoded by direct codetable lookup (`ff_low_map` 00-0F, `bankB_FF10_BF` 10-BF), not linear `code-0xF0` (that applies only to the Chinese codetable)
- **Font loading**: 14 data-area windows (F2 2072B + FB 7264B) → loader decompress → RAM → VRAM (TSB5/29/31 + slots 73/74)
- **Glyph addressing**: `U=(code&0xF)<<4`, `V=code&0xF0`
- **Renderer** (09-13 disassembly): only TPAGE 5/29 supported, no TPAGE 31 render path; display buffer 15×15×2B without bounds check

---

## Status & scope

- This repository **only ships original-Japanese research assets**; no buggy patches/images are included.
- The Chinese patch effort went through multiple rounds (v17/v55-v59) but was never usable due to a "crash after font replacement at boot" issue; the investigation log is kept in `docs/TEXT_RENDER_ENGINE_NOTES_0913.md` §4 for future researchers.
- Game copyright belongs to the original authors; this repo contains only research documents and text data from a legitimately held Japanese image.

---

## License

- Assets released under **CC BY-NC-SA 4.0** (Attribution-NonCommercial-ShareAlike).
- The game itself is NOT included.

*Last updated: 2026-09-13*

> AI生成