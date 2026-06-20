<#
.SYNOPSIS
    Step 1 of the book processing pipeline: Convert a source book/document to Markdown.

.DESCRIPTION
    This script automates the manual file-juggling around convert.py:
      1. Looks for the source file (by exact name) inside _source_intake.
      2. If the book's folder doesn't exist yet in Library, creates it
         (00_original, 01_converted, 02_kb).
      3. Moves the source file from _source_intake into the book's 00_original folder.
      4. Runs convert.py and saves the result into the book's 01_converted folder.

    Works on any computer automatically — it detects where Google Drive's
    "00_Anthropic" folder lives on this machine (no path to edit by hand).

    This script must be run from the GitHub repo folder (where convert.py lives).
    It only performs Step 1 — it does NOT call extract.py or combine.py.

.PARAMETER BookName
    The folder name to use/create under Library. Use lowercase-with-hyphens,
    e.g. "daniels-running-formula".

.PARAMETER SourceFile
    The exact file name (with extension) to look for inside _source_intake,
    e.g. "Daniels Running Formula.epub".

.EXAMPLE
    .\step1_convert.ps1 -BookName "daniels-running-formula" -SourceFile "Daniels Running Formula.epub"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$BookName,

    [Parameter(Mandatory = $true)]
    [string]$SourceFile
)

# ──────────────────────────────────────────────────────────────────────────
# Load shared helpers (auto-detects Google Drive location on this machine)
# ──────────────────────────────────────────────────────────────────────────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir "pipeline_common.ps1")

$paths      = Get-PipelinePaths
$IntakeDir  = $paths.IntakeDir
$LibraryDir = $paths.LibraryDir

# Path to convert.py — assumes this script lives in the same repo folder
$ConvertPy  = Join-Path $ScriptDir "convert.py"

Write-Host ""
Write-Host "=== STEP 1: CONVERT ===" -ForegroundColor Cyan
Write-Host "Book name   : $BookName"
Write-Host "Source file : $SourceFile"
Write-Host "Drive root  : $($paths.DriveRoot)" -ForegroundColor DarkGray
Write-Host ""

# ──────────────────────────────────────────────────────────────────────────
# 1. Verify convert.py exists where expected
# ──────────────────────────────────────────────────────────────────────────
if (-not (Test-Path $ConvertPy)) {
    Write-Host "ERROR: convert.py not found at:" -ForegroundColor Red
    Write-Host "  $ConvertPy"
    Write-Host "Make sure this script lives in the same folder as convert.py (the GitHub repo folder)."
    exit 1
}

# ──────────────────────────────────────────────────────────────────────────
# 2. Look for the source file inside _source_intake (and only there)
# ──────────────────────────────────────────────────────────────────────────
$sourcePath = Join-Path $IntakeDir $SourceFile

if (-not (Test-Path $sourcePath)) {
    Write-Host "ERROR: File not found in _source_intake:" -ForegroundColor Red
    Write-Host "  $sourcePath"
    Write-Host ""
    Write-Host "Make sure the file is sitting directly inside:"
    Write-Host "  $IntakeDir"
    Write-Host "and that the name (including extension) matches exactly."
    exit 1
}

Write-Host "[OK] Found source file in _source_intake." -ForegroundColor Green

# ──────────────────────────────────────────────────────────────────────────
# 3. Create the book's folder structure in Library if it doesn't exist yet
# ──────────────────────────────────────────────────────────────────────────
$bookDir      = Join-Path $LibraryDir $BookName
$originalDir  = Join-Path $bookDir "00_original"
$convertedDir = Join-Path $bookDir "01_converted"
$kbDir        = Join-Path $bookDir "02_kb"

$isNewBook = -not (Test-Path $bookDir)

if ($isNewBook) {
    New-Item -ItemType Directory -Path $originalDir  -Force | Out-Null
    New-Item -ItemType Directory -Path $convertedDir -Force | Out-Null
    New-Item -ItemType Directory -Path $kbDir         -Force | Out-Null
    Write-Host "[OK] Created new book folder in Library: $BookName" -ForegroundColor Green
} else {
    # Folder already exists — make sure all 3 subfolders are present too
    foreach ($dir in @($originalDir, $convertedDir, $kbDir)) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
    Write-Host "[OK] Book folder already exists, reusing it: $BookName" -ForegroundColor Yellow
}

# ──────────────────────────────────────────────────────────────────────────
# 4. Move the source file from _source_intake into 00_original
# ──────────────────────────────────────────────────────────────────────────
$destPath = Join-Path $originalDir $SourceFile

if (Test-Path $destPath) {
    Write-Host "[SKIP] File already exists in 00_original, not overwriting:" -ForegroundColor Yellow
    Write-Host "  $destPath"
} else {
    Move-Item -Path $sourcePath -Destination $destPath
    Write-Host "[OK] Moved file to:" -ForegroundColor Green
    Write-Host "  $destPath"
}

# ──────────────────────────────────────────────────────────────────────────
# 5. Run convert.py, saving the result into 01_converted
# ──────────────────────────────────────────────────────────────────────────
$outputName = [System.IO.Path]::GetFileNameWithoutExtension($SourceFile) + ".md"
$outputPath = Join-Path $convertedDir $outputName

Write-Host ""
Write-Host "Running convert.py..." -ForegroundColor Cyan
Write-Host ""

python "$ConvertPy" "$destPath" -o "$outputPath"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: convert.py exited with an error. See output above." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== DONE ===" -ForegroundColor Cyan
Write-Host "Converted file saved at:"
Write-Host "  $outputPath"
Write-Host ""
Write-Host "Next step (when you're ready): run step2_extract.ps1 on this file." -ForegroundColor Gray
