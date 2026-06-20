# Book Processing Pipeline

A 3-step pipeline that turns coaching/training books into a structured, AI-ready
knowledge base for use in Claude Projects, Gemini, or ChatGPT.

```
Book (EPUB/PDF)  →  convert.py  →  Markdown  →  extract.py  →  KB.md  →  combine.py  →  Combined KB.md
```

This repo contains **only the scripts and manuals** (code, no books). Source books,
converted Markdown files, and extracted KBs are stored separately in Google Drive —
see [Where files live](#where-files-live) below.

---

## The 3 steps

### 1. `convert.py` — Book → Markdown

Converts a book file (EPUB, PDF, DOCX, etc.) into clean Markdown using **MarkItDown**
(local, free text extraction) plus **Gemini Vision** (image/table/chart extraction,
requires an API key).

Handles 4 source types automatically:
- Text-based EPUB (HTML chapters + embedded images)
- Image-based EPUB (fully scanned page images)
- Text-based PDF (digital text + embedded images)
- Scanned PDF (every page processed as an image)

**Requires:** `GEMINI_API_KEY` environment variable (only needed when the book has
images; plain text extraction works without it — see manual for fallback behavior).

```powershell
$env:GEMINI_API_KEY = "AIzaSy..."
python convert.py "book.epub"
python convert.py "book.epub" -o "output.md"
python convert.py "book.pdf" --model "gemini-2.5-pro"
```

Full details: [`manual_convertir.md`](./manual_convertir.md)

---

### 2. `extract.py` — Markdown → Knowledge Base

Sends the full converted book (single call, no chunking) to the Claude API and
extracts a structured 17-section knowledge base: philosophy, physiology, zones,
testing protocols, periodization, individual workouts, coaching heuristics,
nutrition, formulas, and more — split into TIER A (conceptual) and TIER B
(numeric/tabular) content. The extraction logic itself lives in
[`extraction_prompt.md`](./extraction_prompt.md), passed in via `--prompt`.

Two modes:
- **immediate** (default): result right away, full price.
- **batch**: ~24h turnaround, 50% cheaper — recommended for large libraries.

**Requires:** `ANTHROPIC_API_KEY` environment variable.

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Single book, immediate
python extract.py --prompt extraction_prompt.md --input "book.md" --output kb_out

# Single book, batch (cheaper, ~24h)
python extract.py --prompt extraction_prompt.md --input "book.md" --output kb_out --mode batch

# Whole folder of books, batch
python extract.py --prompt extraction_prompt.md --input books\ --output kb_out --mode batch

# Check / download a batch once ready
python extract.py --check msgbatch_abc123 --output kb_out
```

Full details: [`manual_extraccion_kb.md`](./manual_extraccion_kb.md)

---

### 3. `combine.py` — Multiple KBs → One Combined File

Merges several KB markdown files (typically all books by the same author) into a
single file: YAML metadata header, table of contents, and each book in its own
clearly marked block with auto-generated abbreviations (e.g. `HMM2e`, `RLRF`) used
to prefix section headings so identical section numbers never collide.

No external dependencies — pure Python standard library.

```powershell
# Minimum
python combine.py --input ./kb_files --output kb_final.md

# Recommended — explicit order
python combine.py --input ./kb_files --output kb_final.md --order "book1.md,book2.md,book3.md"
```

Full details: [`combine_kb_manual.md`](./combine_kb_manual.md)

---

## Where files live

This pipeline intentionally splits **code** from **content**:

| | Location | Why |
|---|---|---|
| Scripts (`.py`) + manuals (`.md`) | **This GitHub repo** (private) | Text, lightweight, benefits from version history |
| Source books (`.epub`, `.pdf`) | Google Drive only | Copyrighted — never committed to Git |
| Converted books, extracted KBs, combined KBs | Google Drive only | Derived from copyrighted material |
| API keys | Windows environment variables (per machine) | Never in code, never in Git |

Google Drive structure used alongside this repo:

```
00_Anthropic/
├── Library/
│   └── <book-slug>/
│       ├── 00_original/    ← source .epub / .pdf
│       ├── 01_converted/   ← output of convert.py
│       └── 02_kb/          ← output of extract.py
└── combinados/             ← output of combine.py
```

---

## Setup

```powershell
pip install markitdown google-genai Pillow pymupdf anthropic
```

Environment variables needed (set per machine, persisted as permanent Windows
user/system variables — not committed anywhere):

```powershell
$env:GEMINI_API_KEY = "AIzaSy..."        # required by convert.py for image extraction
$env:ANTHROPIC_API_KEY = "sk-ant-..."    # required by extract.py
```

---

## Security

This repo's `.gitignore` blocks API keys, `.env` files, books (`.epub`/`.pdf`), and
spreadsheets (`.xlsx`/`.xls`) from ever being committed. Source books and personal
athlete data must never be placed inside this repo folder.
