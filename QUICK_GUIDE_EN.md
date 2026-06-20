# Quick Reference Guide

For the full, detailed guide, see [`HOW_TO_USE_EN.md`](./HOW_TO_USE_EN.md).
This is just a quick cheat sheet for when you already know the process.

---

## 0. Open the right terminal (always the same one)

Open File Explorer → go to the repository folder → right-click inside it →
**Open in Terminal**

```
C:\Dev\Github\book-processing-pipeline
```
or
```
E:\Dev\github\book-processing-pipeline
```

---

## 1. Convert a new book

1. Put the file in `00_Anthropic\_source_intake\`
2. Run:
   ```powershell
   .\step1_convert.ps1 -BookName "book-name" -SourceFile "Exact Name.epub"
   ```
3. Result in: `Library\book-name\01_converted\`

---

## 2. Extract the KB

```powershell
# Immediate (result right away, more expensive)
.\step2_extract.ps1 -BookName "book-name" -Mode immediate

# Batch (up to 24h, 50% cheaper)
.\step2_extract.ps1 -BookName "book-name" -Mode batch

# Check a pending batch
.\step2_extract.ps1 -BookName "book-name" -Check "msgbatch_xxxxx"
```

Result in: `Library\book-name\02_kb\`

---

## 3. Combine multiple books

1. Copy the `.md` files you want to combine into `combinados\_staging\`
2. Rename them with a numeric prefix to set the order: `01_`, `02_`, `03_`...
3. Run:
   ```powershell
   .\step3_combine.ps1 -OutputName "final_name.md"
   ```
4. Result in: `combinados\final_name.md` (and `_staging` empties itself)

---

## Folder structure (Google Drive)

```
00_Anthropic\
├── _source_intake\          ← new unprocessed books
├── Library\
│   └── <book-name>\
│       ├── 00_original\     ← .epub / .pdf
│       ├── 01_converted\    ← Step 1 output
│       └── 02_kb\           ← Step 2 output
└── combinados\
    ├── _staging\            ← files to combine (with 01_/02_/03_ prefix)
    └── <final file>         ← Step 3 output
```

---

## Most common errors

| Error | Solution |
|---|---|
| `File not found in _source_intake` | Check that the file name matches exactly (capitalization, spaces, extension) |
| `convert.py not found` / `extract.py not found` / `combine.py not found` | Make sure you opened the terminal inside the repository folder |
| `Could not find the '00_Anthropic' folder` | Google Drive isn't synced, open it and wait |
| `No .md file found in 01_converted` | Run Step 1 first for that book |
| `Found more than one .md file` | Leave only one file in that folder, move or delete the rest |
| Mentions `GEMINI_API_KEY` or `ANTHROPIC_API_KEY` | That variable isn't configured — see the full guide, API keys section |

---

## Reminder for working across 2 computers

Before working → **Fetch origin + Pull** in GitHub Desktop
After working → **Commit + Push** in GitHub Desktop
