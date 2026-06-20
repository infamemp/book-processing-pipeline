<#
.SYNOPSIS
    Step 2 of the book processing pipeline: Extract a structured KB from a converted book.

.DESCRIPTION
    Has two separate actions:

    ACTION 1 — Submit extraction (immediate or batch):
        .\step2_extract.ps1 -BookName "daniels-running-formula" -Mode immediate
        .\step2_extract.ps1 -BookName "daniels-running-formula" -Mode batch

        Looks for the converted .md file inside:
          Library\<BookName>\01_converted\
        and runs extract.py, saving the KB into:
          Library\<BookName>\02_kb\

        If -Mode is "batch", extract.py won't return a result right away.
        It prints a Batch ID — save it, you'll need it for Action 2.

    ACTION 2 — Check / download a pending batch:
        .\step2_extract.ps1 -BookName "daniels-running-formula" -Check "msgbatch_abc123"

        Asks extract.py whether the batch is ready. If it is, downloads the
        result into Library\<BookName>\02_kb\. If not, tells you to check again later.

    Works on any computer automatically — it detects where Google Drive's
    "00_Anthropic" folder lives on this machine (no path to edit by hand).

    This script must be run from the GitHub repo folder (where extract.py and
    extraction_prompt.md live).

.PARAMETER BookName
    The book's folder name under Library, e.g. "daniels-running-formula".

.PARAMETER Mode
    "immediate" (default, result right away) or "batch" (24h turnaround, 50% cheaper).
    Used only for Action 1 (submitting a new extraction).

.PARAMETER Check
    A Batch ID to check/download (Action 2). When provided, -Mode is ignored.

.EXAMPLE
    .\step2_extract.ps1 -BookName "daniels-running-formula" -Mode immediate

.EXAMPLE
    .\step2_extract.ps1 -BookName "daniels-running-formula" -Mode batch

.EXAMPLE
    .\step2_extract.ps1 -BookName "daniels-running-formula" -Check "msgbatch_abc123"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$BookName,

    [ValidateSet("immediate", "batch")]
    [string]$Mode = "immediate",

    [string]$Check
)

# ──────────────────────────────────────────────────────────────────────────
# Load shared helpers (auto-detects Google Drive location on this machine)
# ──────────────────────────────────────────────────────────────────────────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir "pipeline_common.ps1")

$paths      = Get-PipelinePaths
$LibraryDir = $paths.LibraryDir

# Paths to extract.py and the extraction prompt — assumed to live in this repo folder
$ExtractPy = Join-Path $ScriptDir "extract.py"
$PromptMd  = Join-Path $ScriptDir "extraction_prompt.md"

$bookDir      = Join-Path $LibraryDir $BookName
$convertedDir = Join-Path $bookDir "01_converted"
$kbDir        = Join-Path $bookDir "02_kb"

Write-Host ""
Write-Host "=== STEP 2: EXTRACT KB ===" -ForegroundColor Cyan
Write-Host "Book name  : $BookName"
Write-Host "Drive root : $($paths.DriveRoot)" -ForegroundColor DarkGray
Write-Host ""

# ──────────────────────────────────────────────────────────────────────────
# 1. Verify extract.py exists where expected
# ──────────────────────────────────────────────────────────────────────────
if (-not (Test-Path $ExtractPy)) {
    Write-Host "ERROR: extract.py not found at:" -ForegroundColor Red
    Write-Host "  $ExtractPy"
    Write-Host "Make sure this script lives in the same folder as extract.py (the GitHub repo folder)."
    exit 1
}

# ──────────────────────────────────────────────────────────────────────────
# 2. Verify the book folder exists
# ──────────────────────────────────────────────────────────────────────────
if (-not (Test-Path $bookDir)) {
    Write-Host "ERROR: Book folder not found in Library:" -ForegroundColor Red
    Write-Host "  $bookDir"
    Write-Host ""
    Write-Host "Run step1_convert.ps1 first to create it and convert the book."
    exit 1
}

if (-not (Test-Path $kbDir)) {
    New-Item -ItemType Directory -Path $kbDir -Force | Out-Null
}

# ══════════════════════════════════════════════════════════════════════════
# ACTION 2 — Check / download a pending batch
# ══════════════════════════════════════════════════════════════════════════
if ($Check) {
    Write-Host "Action: CHECK BATCH" -ForegroundColor Cyan
    Write-Host "Batch ID : $Check"
    Write-Host ""

    python "$ExtractPy" --check "$Check" --output "$kbDir"

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: extract.py exited with an error. See output above." -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "=== DONE (check complete) ===" -ForegroundColor Cyan
    Write-Host "If the batch was ready, the KB file was saved into:"
    Write-Host "  $kbDir"
    exit 0
}

# ══════════════════════════════════════════════════════════════════════════
# ACTION 1 — Submit a new extraction (immediate or batch)
# ══════════════════════════════════════════════════════════════════════════

# Verify the extraction prompt exists
if (-not (Test-Path $PromptMd)) {
    Write-Host "ERROR: extraction_prompt.md not found at:" -ForegroundColor Red
    Write-Host "  $PromptMd"
    exit 1
}

# Find the converted .md file inside 01_converted
if (-not (Test-Path $convertedDir)) {
    Write-Host "ERROR: 01_converted folder not found:" -ForegroundColor Red
    Write-Host "  $convertedDir"
    Write-Host "Run step1_convert.ps1 first."
    exit 1
}

$mdFiles = Get-ChildItem -Path $convertedDir -Filter "*.md" -File

if ($mdFiles.Count -eq 0) {
    Write-Host "ERROR: No .md file found in:" -ForegroundColor Red
    Write-Host "  $convertedDir"
    Write-Host "Run step1_convert.ps1 first to generate it."
    exit 1
}

if ($mdFiles.Count -gt 1) {
    Write-Host "ERROR: Found more than one .md file in 01_converted:" -ForegroundColor Red
    foreach ($f in $mdFiles) { Write-Host "  - $($f.Name)" }
    Write-Host ""
    Write-Host "This script expects exactly one converted file per book. Remove the extra file(s) and try again." -ForegroundColor Yellow
    exit 1
}

$inputMd = $mdFiles[0].FullName

Write-Host "Action     : SUBMIT EXTRACTION"
Write-Host "Mode       : $Mode"
Write-Host "Input file : $($mdFiles[0].Name)"
Write-Host ""

python "$ExtractPy" --prompt "$PromptMd" --input "$inputMd" --output "$kbDir" --mode $Mode

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: extract.py exited with an error. See output above." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== DONE ===" -ForegroundColor Cyan
if ($Mode -eq "batch") {
    Write-Host "Batch submitted. Look above for the Batch ID, then check it later with:" -ForegroundColor Yellow
    Write-Host "  .\step2_extract.ps1 -BookName `"$BookName`" -Check `"<batch_id>`""
} else {
    Write-Host "KB file saved into:"
    Write-Host "  $kbDir"
}
