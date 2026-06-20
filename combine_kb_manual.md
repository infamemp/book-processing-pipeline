# combine_kb.py — Instruction Manual

**Version:** 2.0  
**Script:** `combine_kb.py`  
**Purpose:** Combine multiple KB markdown files into a single file ready to use in Claude Projects, Gemini GEM, ChatGPT, or any other AI platform.

---

## Table of Contents

1. [What does this script do?](#1-what-does-this-script-do)
2. [Requirements](#2-requirements)
3. [Input file format](#3-input-file-format)
4. [How to run it](#4-how-to-run-it)
5. [All available options](#5-all-available-options)
6. [Output file structure](#6-output-file-structure)
7. [Automatic book abbreviations](#7-automatic-book-abbreviations)
8. [Warnings and what they mean](#8-warnings-and-what-they-mean)
9. [Complete usage examples](#9-complete-usage-examples)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. What does this script do?

Takes two or more KB markdown files (one per book) and combines them into a single clean file with:

- A YAML header with metadata about all books (optimized for Claude Projects)
- A table of contents
- Each book in its own clearly marked block with a visible START and END banner
- Section headings prefixed with the book abbreviation so identical section numbers never collide
- Automatic normalization of line endings (Windows vs. Unix)
- Automatic detection and handling of YAML frontmatter in any input file
- A summary at the end showing file size, estimated token count, and the abbreviations used

---

## 2. Requirements

- **Python 3.8 or higher**
- No external packages required — uses only Python's standard library
- Works on Windows, macOS, and Linux

To check your Python version:
```
python --version
```

---

## 3. Input file format

The script is designed for KB files extracted from books using the standard KB extraction pipeline. The expected format is:

```
# KB — Author Name — Book Title (Edition)
Source format: MD via markitdown
Extraction date: YYYY-MM-DD
...

---

## 1. Author & Source Registry
...

## 2. Philosophy & Training Principles (TIER A)
...
```

**Key expectations:**
- The file begins with a `# ` heading (H1) that contains the book title
- Sections use `## N.` headings (H2 with a number)
- The H1 follows the pattern: `KB — Author(s) — Book Title`

**Accepted variations:**
- Files with or without YAML frontmatter (`--- ... ---` at the top)
- Files with Windows line endings (CRLF) or Unix line endings (LF)
- Files where the H1 does not follow the standard pattern (a warning is issued and the filename is used as fallback title)
- Files from different authors or different method systems — abbreviations are auto-generated from whatever title is found

---

## 4. How to run it

Open a terminal (PowerShell on Windows, Terminal on macOS/Linux), navigate to the folder containing the script, and run:

### Minimum required command
```
python combine_kb.py --input ./kb_files --output kb_final.md
```

### Recommended command (with explicit file order)
```
python combine_kb.py \
  --input ./kb_files \
  --output kb_final.md \
  --order "book1.md,book2.md,book3.md"
```

On Windows (PowerShell), use backtick `` ` `` instead of `\` for line continuation, or write it on a single line:
```
python combine_kb.py --input .\kb_files --output kb_final.md --order "book1.md,book2.md,book3.md"
```

---

## 5. All available options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--input` | Yes | — | Folder containing the .md files to combine |
| `--output` | Yes | — | Path and name of the combined output file |
| `--order` | No | Auto sort | Comma-separated list of filenames in the exact order you want them combined |
| `--pattern` | No | All .md files | Only include files whose names start with this prefix |
| `--no-prefix` | No | Off (prefixes ON) | Disable the `[ABBR]` prefix on section headings |
| `--no-toc` | No | Off (TOC ON) | Skip generating the table of contents |

### Option details

#### `--input`
The folder that contains your KB markdown files. Use a relative or absolute path.

```
--input ./kb_files
--input C:\Users\YourName\kb_files
```

#### `--output`
The name and location of the combined file that will be created. If the folder does not exist, the script creates it automatically.

```
--output kb_final.md
--output ./output/hansons_combined.md
```

#### `--order` *(strongly recommended)*
When your filenames are not numerically ordered (e.g., `kb_001.md`, `kb_002.md`), you must specify the order explicitly. This is the most important option for ensuring books appear in the correct logical sequence.

```
--order "KB_Hansons_Marathon_Method_2nd_Edition.md,KB_Hansons_First_Marathon.md,KB_Hansons_Half-Marathon_Method.md"
```

If `--order` is omitted, the script sorts files alphabetically by filename and shows a warning. Always verify the sequence when omitting this option.

#### `--pattern`
If your input folder contains files you do not want to combine, use this to filter by filename prefix.

```
--pattern "KB_Hansons_"
```
This would only combine files whose names start with `KB_Hansons_`.

#### `--no-prefix`
By default, every `## N.` section heading gets the book abbreviation added:

```
## [HMM2e] 5. Intensity & Zone Systems
```

Use `--no-prefix` to keep the original headings unchanged. This is not recommended when combining books with the same section structure (§1–§17), because the headings become identical and indistinguishable.

#### `--no-toc`
Skip the table of contents. Useful if you only need the raw combined content without the index at the top.

---

## 6. Output file structure

The combined file is structured as follows, from top to bottom:

### Section 1 — YAML frontmatter (Claude-optimized)
```yaml
---
kb_title: "Combined Knowledge Base"
generated: "2026-06-18 13:54 UTC"
source_count: 4
books:
  - abbr: "HMM2e"
    title: "KB — Luke Humphrey — Hansons Marathon Method (2nd Edition)"
    authors: "Luke Humphrey (with Keith & Kevin Hanson)"
    file: "KB_Hansons_Marathon_Method_2nd_Edition.md"
  - abbr: "RLRF"
    ...
prefix_headings: true
---
```

Claude Projects reads this header to understand the structure of the KB. Other platforms see it as plain text (it does not interfere with usability).

### Section 2 — Table of contents

A navigable index of all sections from all books, grouped by book. Each section links to its heading in the document.

```
## Table of Contents

### [HMM2e]  Hansons Marathon Method (2nd Edition)  ·  Luke Humphrey
  - [HMM2e] 1. Author & Source Registry
  - [HMM2e] 2. Philosophy & Training Principles (TIER A)
  ...

### [RLRF]  Runner's World Run Less Run Faster  ·  Bill Pierce & Scott Murr
  - [RLRF] 1. Author & Source Registry
  ...
```

### Section 3 — Book blocks

Each book occupies its own block, surrounded by unmistakable START and END banners:

```
################################################################################
##  BOOK 1 / 4  —  START
##  [HMM2e]  KB — Luke Humphrey — Hansons Marathon Method (2nd Edition)
##  Authors: Luke Humphrey (with Keith & Kevin Hanson)
##  File: KB_Hansons_Marathon_Method_2nd_Edition.md  |  1,505 lines  |  125.3 KB
################################################################################

[... full book content ...]

################################################################################
##  BOOK 1 / 4  —  END  —  [HMM2e]
################################################################################
```

If the original file had YAML frontmatter, it is preserved inside the block as an HTML comment (not active, not rendered, but available for reference):

```html
<!--
ORIGINAL FRONTMATTER (KB_Hansons_Half-Marathon_Method.md):
kb_title: "Hansons Half-Marathon Method — Structured Knowledge Base"
...
-->
```

---

## 7. Automatic book abbreviations

The script reads the `# ` title (H1) inside each file and generates a short label automatically. No manual input is needed.

### How the logic works

1. **Isolates the book title** from the H1, ignoring the `KB —` prefix and the author segment.
2. **Detects edition number.** If the title contains `(2nd Edition)` with no year, the suffix `2e` is added. If it contains `(3rd Edition, 2021)` (with a year), the edition suffix is ignored to keep the abbreviation clean.
3. **Removes parenthetical content** from the title (years, edition notes).
4. **Takes the first letter of each significant word**, uppercase. Stop words (a, the, of, for, with, and, etc.) are skipped.
5. **If more than 5 significant words**, only the last 4 are used. This handles series names like "Runner's World" that appear at the front of a title.
6. **Caps total length at 8 characters.**

### Examples with your files

| H1 title found in file | Abbreviation generated |
|---|---|
| `KB — ... — Hansons Marathon Method (2nd Edition)` | `HMM2e` |
| `KB — ... — Hansons First Marathon` | `HFM` |
| `KNOWLEDGE BASE — HANSONS HALF-MARATHON METHOD` | `HHM` |
| `KB — Bill Pierce & Scott Murr — Runner's World Run Less Run Faster (3rd Edition, 2021)` | `RLRF` |

### Conflict resolution

If two books accidentally generate the same abbreviation, the script automatically renames the second one by adding a number (`HMM` → `HMM2`) and shows a warning. No manual intervention is needed.

---

## 8. Warnings and what they mean

Warnings are printed in the terminal during execution. They do not stop the script — the output file is always generated. They inform you of automatic corrections made.

| Warning | What happened | Action needed? |
|---|---|---|
| `CRLF line endings detected in: filename.md (normalized to LF)` | The file had Windows line endings. They were silently converted to Unix format in the output. | None |
| `YAML frontmatter found in: filename.md (preserved as HTML comment inside its block)` | The file had a YAML block at the top. It was moved inside the book block as an HTML comment, so it does not interfere with the combined file's own YAML header. | None |
| `No H1 heading found in: filename.md (filename used as fallback title)` | The file does not have a `# ` heading. The filename is used as the book title in banners and TOC. | Review the source file — the H1 heading may be missing or malformed. |
| `Abbreviation conflict: [ABC] used by multiple books. Renamed to [ABC2] for: filename.md` | Two books generated the same abbreviation. The second one was renamed automatically. | None — but verify the auto-assigned abbreviation makes sense. |
| `WARNING: no --order specified. Using automatic (natural) sort.` | No `--order` was provided. Files are sorted alphabetically by filename. | Verify the book sequence in the output is the intended one. Use `--order` to fix it if not. |

---

## 9. Complete usage examples

### Example 1 — Hansons trilogy (3 books, same author)
```
python combine_kb.py \
  --input ./hansons_kb \
  --output ./output/hansons_combined.md \
  --order "KB_Hansons_Marathon_Method_2nd_Edition.md,KB_Hansons_First_Marathon.md,KB_Hansons_Half-Marathon_Method.md"
```

### Example 2 — Mixed authors (4 books)
```
python combine_kb.py \
  --input ./running_kb \
  --output ./output/running_methods_combined.md \
  --order "KB_Hansons_Marathon_Method_2nd_Edition.md,KB_Hansons_First_Marathon.md,KB_Hansons_Half-Marathon_Method.md,run-less-run-faster_kb.md"
```

### Example 3 — Combine only files with a specific prefix
```
python combine_kb.py \
  --input ./all_kb_files \
  --output ./output/hansons_only.md \
  --pattern "KB_Hansons_" \
  --order "KB_Hansons_Marathon_Method_2nd_Edition.md,KB_Hansons_First_Marathon.md,KB_Hansons_Half-Marathon_Method.md"
```

### Example 4 — Generate without TOC (lean version)
```
python combine_kb.py \
  --input ./kb_files \
  --output kb_final_no_toc.md \
  --order "file1.md,file2.md" \
  --no-toc
```

### Example 5 — Keep original section headings (no prefix)
```
python combine_kb.py \
  --input ./kb_files \
  --output kb_final_no_prefix.md \
  --order "file1.md,file2.md" \
  --no-prefix
```
> **Not recommended** when combining books with the same §1–§17 structure.

---

## 10. Troubleshooting

### "ERROR: folder '...' does not exist."
The path in `--input` does not exist or is misspelled. Check the path and try again. On Windows, make sure to use `.\` or a full path.

### "ERROR: the following files were not found in '...':"
One or more filenames in `--order` do not match files in the `--input` folder. Common causes:
- Typo in the filename
- The file is in a different folder
- The filename has a different extension (e.g., `.MD` vs `.md` on case-sensitive systems)

### The abbreviations look wrong
If the auto-generated abbreviation is not what you expected, check the H1 heading inside the file. The abbreviation is derived from the book title portion of the H1. If the H1 does not follow the `KB — Author — Title` pattern, the result may differ.

### The section headings are not prefixed
Make sure you did not accidentally use `--no-prefix`. Prefixes are ON by default — you only need to do something if you want to turn them OFF.

### Token estimate seems too high for Claude Projects
Claude Projects (Pro plan) has a context window large enough for typical combined KBs of 3–5 books. If the estimated token count is very high (e.g., above 150,000), consider splitting the KB into two separate combined files by topic or author.

### Output file has unexpected content at the top
If you see raw YAML text at the very beginning that is not formatted as a code block, this is the YAML frontmatter — it is intentional and optimized for Claude Projects. Other platforms will see it as plain text, which does not affect functionality.

---

*End of manual.*
