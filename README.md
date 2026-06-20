# Book Processing Pipeline

A 3-step pipeline that turns coaching/training books into a structured, AI-ready
knowledge base for use in Claude Projects, Gemini, or ChatGPT.

```
Book (EPUB/PDF)  →  convert.py  →  Markdown  →  extract.py  →  KB.md  →  combine.py  →  Combined KB.md
```

This repo contains **only the scripts and manuals** (code, no books). Source books,
converted Markdown files, and extracted KBs are stored separately in Google Drive —
see [Where files live](#where-files-live) below.

For a fully detailed, step-by-step walkthrough with no assumed knowledge, see
[`HOW_TO_USE.md`](./HOW_TO_USE.md). This README is the technical reference.

---

## Two ways to run each step

Every step can be run two ways:

1. **The automation scripts** (`step1_convert.ps1`, `step2_extract.ps1`,
   `step3_combine.ps1`) — recommended. They auto-detect Google Drive's location on
   the current machine, create folders as needed, and call the underlying Python
   script with the right paths already filled in.
2. **The raw Python scripts directly** (`convert.py`, `extract.py`, `combine.py`)
   — useful for troubleshooting or one-off runs with custom options not exposed by
   the automation scripts.

---

## The 3 steps

### 1. Convert — Book → Markdown

**Automation script:**
```powershell
.\step1_convert.ps1 -BookName "daniels-running-formula" -SourceFile "Daniels Running Formula.epub"
```
Looks for `SourceFile` inside Google Drive's `_source_intake` folder, creates the
book's folder structure under `Library` if it doesn't exist yet
(`00_original` / `01_converted` / `02_kb`), moves the source file into
`00_original`, then runs `convert.py` and saves the result into `01_converted`.

**Underlying script — `convert.py`:**
Converts a book file (EPUB, PDF, DOCX, etc.) into clean Markdown using
**MarkItDown** (local, free text extraction) plus **Gemini Vision** (image/table/
chart extraction, requires an API key). Handles 4 source types automatically:
text-based EPUB, image-based EPUB, text-based PDF, and scanned PDF.

```powershell
python convert.py "book.epub"
python convert.py "book.epub" -o "output.md"
python convert.py "book.pdf" --model "gemini-2.5-pro"
```

**Requires:** `GEMINI_API_KEY` environment variable (only needed when the book has
images; plain text extraction works without it — see manual for fallback behavior).

Full manual details: [`manual_convertir.md`](./manual_convertir.md)

---

### 2. Extract — Markdown → Knowledge Base

**Automation script — Action 1, submit extraction:**
```powershell
.\step2_extract.ps1 -BookName "daniels-running-formula" -Mode immediate
.\step2_extract.ps1 -BookName "daniels-running-formula" -Mode batch
```
Looks for the single `.md` file inside `Library\<BookName>\01_converted\`, runs
`extract.py` against it, saves the resulting KB into
`Library\<BookName>\02_kb\`. If more than one `.md` file is found, it stops and
asks you to remove the extra one(s) — it never guesses which file to use.

**Automation script — Action 2, check a pending batch:**
```powershell
.\step2_extract.ps1 -BookName "daniels-running-formula" -Check "msgbatch_abc123"
```
Asks `extract.py` whether the batch is ready. If ready, downloads the result into
`02_kb`. If not, tells you to check again later.

**Underlying script — `extract.py`:**
Sends the full converted book (single call, no chunking) to the Claude API and
extracts a structured 17-section knowledge base — philosophy, physiology, zones,
testing protocols, periodization, individual workouts, coaching heuristics,
nutrition, formulas, and more — split into TIER A (conceptual) and TIER B
(numeric/tabular) content. The extraction logic lives in
[`extraction_prompt.md`](./extraction_prompt.md), passed in via `--prompt`.

Two modes:
- **immediate** (default): result right away, full price.
- **batch**: ~24h turnaround, 50% cheaper — recommended for large libraries.

```powershell
python extract.py --prompt extraction_prompt.md --input "book.md" --output kb_out
python extract.py --prompt extraction_prompt.md --input "book.md" --output kb_out --mode batch
python extract.py --check msgbatch_abc123 --output kb_out
```

**Requires:** `ANTHROPIC_API_KEY` environment variable.

Full manual details: [`manual_extraccion_kb.md`](./manual_extraccion_kb.md)

---

### 3. Combine — Multiple KBs → One Combined File

**Automation script:**
```powershell
.\step3_combine.ps1 -OutputName "hansons_combined.md"
```
Combines whatever `.md` files are sitting in `combinados\_staging\` at the moment
you run it. You control both *which* files get combined and the *order* they
appear in:

1. Manually copy the KB files you want to combine (from their respective
   `02_kb` folders) into `combinados\_staging\`.
2. Manually rename them with a numeric prefix — `01_`, `02_`, `03_`... — to set
   the order they should appear in.
3. Run the script. It picks up everything in `_staging`, runs `combine.py`
   (relying on natural sort, so your numeric prefixes are respected automatically
   without needing `--order`), saves the result into `combinados\<OutputName>`,
   and empties `_staging` afterwards.

The first time you run it (before `_staging` exists), it just creates the folder
and stops — telling you to add files and run it again.

**Underlying script — `combine.py`:**
Merges several KB markdown files into a single file: YAML metadata header, table
of contents, and each book in its own clearly marked block with auto-generated
abbreviations (e.g. `HMM2e`, `RLRF`) used to prefix section headings so identical
section numbers never collide. No external dependencies — pure Python standard
library.

```powershell
python combine.py --input ./kb_files --output kb_final.md
python combine.py --input ./kb_files --output kb_final.md --order "book1.md,book2.md,book3.md"
```

Full manual details: [`combine_kb_manual.md`](./combine_kb_manual.md)

---

## Where files live

This pipeline intentionally splits **code** from **content**:

| | Location | Why |
|---|---|---|
| Scripts (`.py`, `.ps1`) + manuals (`.md`) | **This GitHub repo** (private) | Text, lightweight, benefits from version history |
| Source books (`.epub`, `.pdf`) | Google Drive only | Copyrighted — never committed to Git |
| Converted books, extracted KBs, combined KBs | Google Drive only | Derived from copyrighted material |
| API keys | Windows environment variables (per machine) | Never in code, never in Git |

Google Drive structure used alongside this repo:

```
00_Anthropic/
├── _source_intake/         ← drop new source books/documents here before converting
├── Library/
│   └── <book-slug>/
│       ├── 00_original/    ← source .epub / .pdf (moved here by step1_convert.ps1)
│       ├── 01_converted/   ← output of convert.py
│       └── 02_kb/          ← output of extract.py
└── combinados/
    ├── _staging/           ← drop KB files here (with 01_/02_/03_ prefixes) before combining
    └── <combined files>    ← output of combine.py
```

The Drive location (which drive letter, exact folder name) is **auto-detected**
by `pipeline_common.ps1` on every machine — nothing to configure by hand when
moving between computers, as long as Google Drive is installed and synced.

---

## Multi-computer setup (GitHub Desktop)

This repo is meant to be synced between multiple machines via GitHub Desktop.
The drive letter and exact repo path can differ per machine (e.g.
`C:\Dev\Github\book-processing-pipeline` on one, `E:\Dev\github\book-processing-pipeline`
on another) — none of the scripts depend on a fixed path, so this just works.

Golden rule for every machine: **before working, `Fetch origin` + `Pull` in
GitHub Desktop; after working, `Commit` + `Push`.** This keeps both machines in
sync and avoids editing a stale copy of any script.

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
