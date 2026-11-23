---
name: paper-bilingual-translator
description: Extract two-column academic PDFs with normalized paragraph bounding boxes and perform high-precision three-stage translation into Taiwan academic Traditional Chinese Markdown (.md) compatible with BilingualReader.html.
---

# Academic Paper Bilingual Translator (`paper-bilingual-translator`)

This skill converts an English academic journal PDF into a Taiwan-standard Traditional Chinese Markdown (`.md`) file with embedded paragraph coordinate markers (`<!-- sync: ... -->`) for synchronized side-by-side reading in `BilingualReader.html`.

## Prerequisites

- Python 3 with `PyMuPDF` (`fitz`) installed (`pip install pymupdf`).
- Bundled extraction script: `scripts/extract_blocks.py`.

## Google Drive Source Scope (When Reading from `Paper_Translate`)

When instructed to read PDFs from the Google Drive `Paper_Translate` folder:
- **Non-recursive only**: List and process **only** `.pdf` files directly inside `Paper_Translate` (`gdrive readonly ls <FOLDER_ID>`).
- **Ignore subfolders**: Do **not** recurse into or process any nested subfolders inside `Paper_Translate`.

## Step 0: Extract PDF Text Blocks & Coordinates

Run `scripts/extract_blocks.py` on the target PDF to extract text blocks in two-column reading order with normalized `0.0–1.0` bounding boxes:

```bash
python3 scripts/extract_blocks.py /path/to/paper.pdf --format md -o /tmp/paper_extracted.md
```

Each extracted block has the format:

```markdown
<!-- sync: {"id": "p1_b1", "page": 1, "bbox": [0.08, 0.12, 0.92, 0.18]} -->
Original English paragraph text...
```

## Three-Stage Translation Workflow (Mandatory)

You MUST follow all three passes in order. Never do literal sentence-by-sentence machine translation, and never omit or merge `<!-- sync: ... -->` markers.

### Pass 1: Global Context & Glossary Extraction

1. Read the **Title**, **Abstract**, **Section Headings**, and **Conclusions** from the extracted blocks.
2. Summarize the paper's core thesis, methodology, and domain.
3. Build an **English–Traditional Chinese Glossary** for all key technical terms, acronyms, and domain-specific phrases.
   - Use **Taiwan academic & engineering terminology** (台灣慣用學術與工程詞彙):
     - `laser` → 雷射 (NOT 激光)
     - `information` → 資訊 (NOT 信息)
     - `robustness` → 強健性 / 穩健性 (NOT 魯棒性)
     - `support / carrier` → 擔體 (NOT 載體, in catalysis/chemistry)
     - `simulation` → 模擬 (NOT 仿真)
     - `algorithm` → 演算法 (NOT 算法)
     - `optimization` → 最佳化 (NOT 優化)
     - `network` → 網路 (NOT 網絡)
     - `data` → 資料 (NOT 數據, except when referring to numerical values/measurements)
     - `software / hardware` → 軟體 / 硬體 (NOT 軟件 / 硬件)
     - `interface` → 介面 (NOT 接口)
     - `video / audio` → 視訊 / 音訊 (NOT 視頻 / 音頻)
     - `quality` → 品質 (NOT 質量, except physical mass)
     - `default` → 預設 (NOT 默認)
     - `module` → 模組 (NOT 模塊)
     - `vector` → 向量 (NOT 矢量)
     - `matrix` → 矩陣

### Pass 2: Structured Section-by-Section Precision Translation

Translate all blocks in section order:

1. **Preserve every sync marker verbatim**: Every translated paragraph MUST be immediately preceded by its exact `<!-- sync: {"id": "...", "page": ..., "bbox": [...]} -->` HTML comment on its own line. Do NOT alter `id`, `page`, or `bbox` values, and do NOT merge or split blocks with different `id`s.
2. **First-occurrence term annotation**: On the first appearance of a key technical term in the body text, format it as `繁體中文（English Term）`, e.g., `電化學二氧化碳還原反應（electrochemical $\text{CO}_2$ reduction reaction, $\text{CO}_2\text{RR}$）`. Subsequent occurrences use the Traditional Chinese term or acronym consistently.
3. **Markdown structure**: Format titles (`#`), section headings (`##`, `###`), figure/table captions (`**圖 1：**` / `**表 1：**`), and bullet lists cleanly using Markdown syntax right below their corresponding `<!-- sync: ... -->` comment.

### Pass 3: Taiwan Academic Polishing & Formula Locking

Review the entire translated Markdown before writing the final output:

1. **LaTeX Formula Locking**:
   - Ensure all mathematical and chemical formulas are wrapped in valid LaTeX (`$...$` for inline, `$$...$$` for display), e.g. `$\text{CO}_2$`, `$\Delta H$`, `$\eta = 92.4\%$`.
   - Verify that NO formula syntax, subscripts, superscripts, units, or numerical values were altered or corrupted during translation.
2. **Citation Locking**:
   - Preserve all literature citation numbers and formats exactly as in the source, e.g., `[12, 13]`, `(Smith et al., 2024)`.
3. **Fluency & Tone**:
   - Eliminate "translationese" (機翻感): restructure long English passive clauses into natural, concise Taiwan academic prose.
   - Ensure zero Mainland China terminology remains.

## Output

Save the final translated Markdown in the same directory as the original PDF, using the exact same base filename with `.md` extension:

- Input: `/path/to/paper.pdf`
- Output: `/path/to/paper.md`
