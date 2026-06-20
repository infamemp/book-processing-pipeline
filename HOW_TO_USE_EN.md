# How to Use This Pipeline — Step-by-Step Guide

This guide assumes you don't remember how any of this works. Follow the steps in
order, without skipping any. Each step tells you exactly what to do, what to
type, and what you should see on screen.

---

## Before you start — What do you need ready?

- [ ] Google Drive installed and synced on this computer
- [ ] The repository folder downloaded on this computer (either
      `C:\Dev\Github\book-processing-pipeline` or
      `E:\Dev\github\book-processing-pipeline`, depending on the machine)
- [ ] The `GEMINI_API_KEY` environment variable configured (only needed if you're
      going to convert books that contain images)
- [ ] The `ANTHROPIC_API_KEY` environment variable configured (needed to extract
      the KB)

If you're not sure whether those variables are configured, go to the
[Checking that your API keys are configured](#checking-that-your-api-keys-are-configured)
section at the end of this document.

---

## PART 1 — How to open the right terminal

Everything you'll do in this guide runs from **a single folder**, always the
same one, no matter which step of the process you're on.

### Step 1.1 — Open Windows File Explorer

### Step 1.2 — Navigate to the repository folder

Go to whichever of these paths actually exists on your computer (only one will):
```
C:\Dev\Github\book-processing-pipeline
```
or
```
E:\Dev\github\book-processing-pipeline
```

### Step 1.3 — Open a terminal there

Inside that folder (without going into any subfolder), **right-click** on an
empty space (not on any file) and select:

> **Open in Terminal**

(On some versions of Windows it says "Open PowerShell window here.")

A black or dark-blue window with text will open. That's your terminal. Check
that the first line reads something like:
```
PS C:\Dev\Github\book-processing-pipeline>
```
If it shows that path, you're in the right place. **Leave this window open** —
you'll use it for every step in this guide.

---

## PART 2 — Converting a new book (Pipeline Step 1)

### Step 2.1 — Put the book file in the intake folder

Open Windows File Explorer and go to your Google Drive, to the folder:
```
00_Anthropic\_source_intake
```

Copy or drag the book file you want to process into that folder (`.epub` or `.pdf`).

**Write down the exact file name, exactly as it appears**, including
capitalization, spaces, and the extension. For example: `Daniels Running Formula.epub`

### Step 2.2 — Decide the name you'll give this book

You're going to make up a short name to identify this book in the folder
structure. Rules:
- All lowercase
- No spaces (use hyphens `-` instead)
- No accents or special characters

Example: if the book is "Daniels Running Formula", the name would be:
```
daniels-running-formula
```

### Step 2.3 — Go to the terminal you left open (Part 1)

Type the following command, **replacing** the two values in quotes with your own:

```powershell
.\step1_convert.ps1 -BookName "daniels-running-formula" -SourceFile "Daniels Running Formula.epub"
```

- `-BookName` → the short name you made up in Step 2.2
- `-SourceFile` → the exact file name, as you wrote it down in Step 2.1

Press **Enter**.

### Step 2.4 — What you'll see on screen

The script will print several lines of text. This is normal and expected:

```
=== STEP 1: CONVERT ===
Book name   : daniels-running-formula
Source file : Daniels Running Formula.epub
Drive root  : E:\Mi Unidad\00_Anthropic

[OK] Found source file in _source_intake.
[OK] Created new book folder in Library: daniels-running-formula
[OK] Moved file to:
  ...\00_original\Daniels Running Formula.epub

Running convert.py...

Gemini Vision active — model: gemini-2.5-flash
Converting 'Daniels Running Formula.epub'...
  ...
Saved as '...md' (284,531 characters)

=== DONE ===
Converted file saved at:
  ...\01_converted\Daniels Running Formula.md
```

This can take anywhere from a few seconds to 20-30 minutes, depending on how
many images the book has. **Don't close the terminal while it's working.**

### Step 2.5 — If you see an error instead of "DONE"

| If you see this... | It means... | What to do |
|---|---|---|
| `ERROR: File not found in _source_intake` | The name you typed in `-SourceFile` doesn't exactly match the file | Check capitalization, spaces, and the extension. Confirm the file is actually inside `_source_intake` |
| `ERROR: convert.py not found` | You're in the wrong folder | Repeat Part 1 — make sure you opened the terminal inside the repository folder |
| `ERROR: Could not find the '00_Anthropic' folder` | Google Drive isn't synced on this machine | Open the Google Drive app and wait for it to sync |
| Something mentions `GEMINI_API_KEY` | The Gemini API key isn't configured | Go to [Checking that your API keys are configured](#checking-that-your-api-keys-are-configured) |

### Step 2.6 — Verify the result

Go to your Google Drive, to:
```
00_Anthropic\Library\daniels-running-formula\01_converted\
```
There should be an `.md` file there containing the book's content. Open it and
take a quick look to confirm it looks right.

**You've finished Step 1 for this book.** You don't need to do anything else
right now — you can move on to Step 2 now, or close everything and come back
another day.

---

## PART 3 — Extracting the book's knowledge (Pipeline Step 2)

This step takes the `.md` file you generated in Part 2 and asks the AI to
extract the methodology, philosophy, and technical data from the book, in a
structured format.

### Step 3.1 — Go to the terminal (the same one as always)

If you closed it, repeat Part 1 to open a new one.

### Step 3.2 — Type the command

```powershell
.\step2_extract.ps1 -BookName "daniels-running-formula" -Mode immediate
```

- `-BookName` → the same short name you used in Part 2 (must be identical)
- `-Mode` → type `immediate` if you want the result right away (more expensive),
  or `batch` if you're not in a hurry and want to pay less (takes up to 24 hours)

Press **Enter**.

### Step 3.3 — What you'll see on screen (immediate mode)

```
=== STEP 2: EXTRACT KB ===
Book name  : daniels-running-formula
Drive root : E:\Mi Unidad\00_Anthropic

Action     : SUBMIT EXTRACTION
Mode       : immediate
Input file : Daniels Running Formula.md

[1/1] Daniels Running Formula
  Input ~45,000 tokens  |  Estimated cost ~$1.20
  Processing... done  180s  in=44,892  out=38,201  $1.15

=== DONE ===
KB file saved into:
  ...\02_kb\
```

This can take several minutes. Be patient and don't close the window.

### Step 3.4 — What you'll see on screen (batch mode)

```
=== STEP 2: EXTRACT KB ===
Action     : SUBMIT EXTRACTION
Mode       : batch
...
Batch ID  : msgbatch_abc123xyz
...
=== DONE ===
Batch submitted. Look above for the Batch ID, then check it later with:
  .\step2_extract.ps1 -BookName "daniels-running-formula" -Check "msgbatch_abc123xyz"
```

**Copy and save that Batch ID somewhere** (a Notepad file, for example). You'll
need it to check the result later.

### Step 3.5 — If you chose batch: how to check the result later

Wait at least a couple of hours (it can take up to 24h). Then, in the terminal:

```powershell
.\step2_extract.ps1 -BookName "daniels-running-formula" -Check "msgbatch_abc123xyz"
```
(use the real Batch ID you copied in Step 3.4)

If it's not ready yet, you'll see something like:
```
Status : in_progress
Not ready yet. Check again with: ...
```
That's normal — just wait longer and try again later.

If it's ready, the file downloads automatically and you'll see "DONE".

### Step 3.6 — If you see an error

| If you see this... | It means... | What to do |
|---|---|---|
| `ERROR: Book folder not found in Library` | The book name doesn't match any existing folder | Check that you typed the same `-BookName` you used in Part 2 |
| `ERROR: No .md file found in 01_converted` | You haven't completed Part 2 for this book | Go back to Part 2 and run `step1_convert.ps1` first |
| `ERROR: Found more than one .md file` | There's more than one `.md` file in that folder | Go into `01_converted` and leave only the correct file, move or delete the rest |
| Something mentions `ANTHROPIC_API_KEY` | That API key isn't configured | Go to [Checking that your API keys are configured](#checking-that-your-api-keys-are-configured) |

### Step 3.7 — Verify the result

Go to:
```
00_Anthropic\Library\daniels-running-formula\02_kb\
```
There should be an `.md` file with the knowledge extracted from the book,
organized into sections.

---

## PART 4 — Combining several books from the same author (Pipeline Step 3)

This step is optional — you only need it if you want to merge the knowledge
from several books (typically by the same author) into a single file.

### Step 4.1 — The first time: create the temporary staging folder

In the terminal, type:
```powershell
.\step3_combine.ps1 -OutputName "test.md"
```
(the name doesn't matter yet — this first run will only create a folder)

You'll see:
```
[OK] Created staging folder (first time): ...\combinados\_staging
Nothing to combine yet. Copy your KB .md files into that folder...
```

This is normal and expected the first time. The folder you need has now been created.

### Step 4.2 — Copy the files you want to combine into it

Go to Google Drive, to:
```
00_Anthropic\combinados\_staging\
```

Now go to the `02_kb` folders of each book you want to combine, and **copy**
(don't move) those `.md` files into `_staging`.

### Step 4.3 — Rename the files to set the order

Inside `_staging`, **rename** each file by adding a number at the beginning,
matching the order you want them to appear in the final result:

```
01_daniels-book-one_kb.md
02_daniels-book-two_kb.md
03_daniels-book-three_kb.md
```

The number determines the order — `01_` appears first, `02_` second, and so on.

### Step 4.4 — Run the combine script

In the terminal:
```powershell
.\step3_combine.ps1 -OutputName "daniels_combined.md"
```

Change `"daniels_combined.md"` to whatever name you want for the final file.

### Step 4.5 — What you'll see on screen

```
=== STEP 3: COMBINE ===
Output name : daniels_combined.md
...
[OK] Found 3 file(s) in staging:
  - 01_daniels-book-one_kb.md
  - 02_daniels-book-two_kb.md
  - 03_daniels-book-three_kb.md

Running combine.py...
...
=== DONE ===
Combined file saved at:
  ...\combinados\daniels_combined.md

Staging folder has been emptied and is ready for the next combination.
```

### Step 4.6 — Verify the result

Go to:
```
00_Anthropic\combinados\
```
Your combined file should be there, ready to upload to Claude Projects, Gemini,
or ChatGPT.

**Note:** after each successful combination, the `_staging` folder empties
itself automatically — so it's ready for next time without you having to clean
it up by hand.

### Step 4.7 — If you see an error

| If you see this... | It means... | What to do |
|---|---|---|
| `ERROR: No .md files found in staging folder` | You didn't copy any files into `_staging`, or it was already emptied from a previous run | Repeat Step 4.2 |

---

## Checking that your API keys are configured

API keys are configured as **permanent** Windows environment variables. If
you've already configured them before, they should keep working without you
doing anything.

### To check if they're already configured

In the terminal, type:
```powershell
echo $env:GEMINI_API_KEY
echo $env:ANTHROPIC_API_KEY
```

If each one shows a long string of text (something like `AIzaSy...` or
`sk-ant-...`), they're already configured correctly and you don't need to do
anything else.

If either one shows nothing (an empty line), you need to configure it:

### To permanently configure GEMINI_API_KEY

```powershell
[System.Environment]::SetEnvironmentVariable('GEMINI_API_KEY', 'AIzaSy...', 'User')
```
(replace `AIzaSy...` with your real key)

### To permanently configure ANTHROPIC_API_KEY

```powershell
[System.Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY', 'sk-ant-...', 'User')
```
(replace `sk-ant-...` with your real key)

**Important:** after configuring a new variable, you must **close the terminal
and open a new one** for the change to take effect. Terminals that were already
open won't update on their own.

---

## Command reference (quick summary)

```powershell
# Step 1 — Convert
.\step1_convert.ps1 -BookName "book-name" -SourceFile "Exact Name.epub"

# Step 2 — Extract KB (immediate)
.\step2_extract.ps1 -BookName "book-name" -Mode immediate

# Step 2 — Extract KB (cheaper, 24h)
.\step2_extract.ps1 -BookName "book-name" -Mode batch

# Step 2 — Check a pending batch
.\step2_extract.ps1 -BookName "book-name" -Check "msgbatch_xxxxx"

# Step 3 — Combine (after copying and renaming files into _staging)
.\step3_combine.ps1 -OutputName "final_name.md"
```
