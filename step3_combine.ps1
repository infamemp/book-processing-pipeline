<#
.SYNOPSIS
    Step 3 of the book processing pipeline: Combine staged KB files into one file.

.DESCRIPTION
    Workflow:
      1. You manually copy the .md KB files you want to combine into:
           combinados\_staging\
      2. You manually rename them with a numeric prefix (01_, 02_, 03_...) to
         set the order they should appear in the combined file.
      3. You run this script with the desired output file name.

    The script then:
      - Runs combine.py on whatever is sitting inside _staging (natural sort,
        so the 01_/02_/03_ prefixes you set are respected automatically).
      - Saves the result into combinados\<OutputName>.
      - Empties _staging afterwards, ready for the next combination.

    Works on any computer automatically — it detects where Google Drive's
    "00_Anthropic" folder lives on this machine (no path to edit by hand).

    This script must be run from the GitHub repo folder (where combine.py lives).

.PARAMETER OutputName
    The file name for the combined result, e.g. "hansons_combined.md".

.EXAMPLE
    .\step3_combine.ps1 -OutputName "hansons_combined.md"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$OutputName
)

# ──────────────────────────────────────────────────────────────────────────
# Load shared helpers (auto-detects Google Drive location on this machine)
# ──────────────────────────────────────────────────────────────────────────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir "pipeline_common.ps1")

$paths       = Get-PipelinePaths
$CombinedDir = $paths.CombinedDir
$StagingDir  = Join-Path $CombinedDir "_staging"

# Path to combine.py — assumes this script lives in the same repo folder
$CombinePy = Join-Path $ScriptDir "combine.py"

Write-Host ""
Write-Host "=== STEP 3: COMBINE ===" -ForegroundColor Cyan
Write-Host "Output name : $OutputName"
Write-Host "Drive root  : $($paths.DriveRoot)" -ForegroundColor DarkGray
Write-Host ""

# ──────────────────────────────────────────────────────────────────────────
# 1. Verify combine.py exists where expected
# ──────────────────────────────────────────────────────────────────────────
if (-not (Test-Path $CombinePy)) {
    Write-Host "ERROR: combine.py not found at:" -ForegroundColor Red
    Write-Host "  $CombinePy"
    Write-Host "Make sure this script lives in the same folder as combine.py (the GitHub repo folder)."
    exit 1
}

# ──────────────────────────────────────────────────────────────────────────
# 2. Make sure _staging exists (create it if this is the first time)
# ──────────────────────────────────────────────────────────────────────────
if (-not (Test-Path $StagingDir)) {
    New-Item -ItemType Directory -Path $StagingDir -Force | Out-Null
    Write-Host "[OK] Created staging folder (first time):" -ForegroundColor Green
    Write-Host "  $StagingDir"
    Write-Host ""
    Write-Host "Nothing to combine yet. Copy your KB .md files into that folder," -ForegroundColor Yellow
    Write-Host "rename them with 01_ / 02_ / 03_ prefixes for ordering, then run this script again."
    exit 0
}

# ──────────────────────────────────────────────────────────────────────────
# 3. Check that _staging actually has .md files in it
# ──────────────────────────────────────────────────────────────────────────
$stagedFiles = Get-ChildItem -Path $StagingDir -Filter "*.md" -File

if ($stagedFiles.Count -eq 0) {
    Write-Host "ERROR: No .md files found in staging folder:" -ForegroundColor Red
    Write-Host "  $StagingDir"
    Write-Host ""
    Write-Host "Copy the KB files you want to combine into that folder first" -ForegroundColor Yellow
    Write-Host "(with 01_ / 02_ / 03_ prefixes to set the order), then run this script again."
    exit 1
}

Write-Host "[OK] Found $($stagedFiles.Count) file(s) in staging:" -ForegroundColor Green
foreach ($f in ($stagedFiles | Sort-Object Name)) {
    Write-Host "  - $($f.Name)"
}
Write-Host ""

# ──────────────────────────────────────────────────────────────────────────
# 4. Run combine.py
#    No --order is passed: combine.py's natural sort already respects the
#    01_/02_/03_ prefixes you set manually on the staged files.
# ──────────────────────────────────────────────────────────────────────────
if (-not (Test-Path $CombinedDir)) {
    New-Item -ItemType Directory -Path $CombinedDir -Force | Out-Null
}
$outputPath = Join-Path $CombinedDir $OutputName

Write-Host "Running combine.py..." -ForegroundColor Cyan
Write-Host ""

python "$CombinePy" --input "$StagingDir" --output "$outputPath"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: combine.py exited with an error. See output above." -ForegroundColor Red
    Write-Host "Staging folder was NOT cleared, so you can retry without re-copying files."
    exit 1
}

# ──────────────────────────────────────────────────────────────────────────
# 5. Empty _staging, ready for next time
# ──────────────────────────────────────────────────────────────────────────
Get-ChildItem -Path $StagingDir -File | Remove-Item -Force

Write-Host ""
Write-Host "=== DONE ===" -ForegroundColor Cyan
Write-Host "Combined file saved at:"
Write-Host "  $outputPath"
Write-Host ""
Write-Host "Staging folder has been emptied and is ready for the next combination." -ForegroundColor Gray
