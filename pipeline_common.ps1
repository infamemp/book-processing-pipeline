<#
.SYNOPSIS
    Shared helper: auto-detects the Google Drive "00_Anthropic" folder on this machine.

.DESCRIPTION
    Different computers may have Google Drive mounted on different drive letters
    (e.g. C:\Users\Michel\Mi unidad on one machine, E:\Mi Unidad on another).
    This script searches all available drive letters for a "00_Anthropic" folder
    sitting inside a "Mi unidad" / "Mi Unidad" folder, and returns the first match.

    This file is not meant to be run directly — it's loaded (dot-sourced) by
    step1_convert.ps1, step2_extract.ps1, and step3_combine.ps1.
#>

function Find-DriveRoot {
    # Common Google Drive folder name variants (capitalization differs by machine/locale)
    $driveFolderNames = @("Mi unidad", "Mi Unidad", "My Drive")

    # Check every drive letter that actually exists on this machine
    $availableDrives = Get-PSDrive -PSProvider FileSystem | Select-Object -ExpandProperty Root

    foreach ($drive in $availableDrives) {
        foreach ($folderName in $driveFolderNames) {

            # Case 1: Drive folder sits directly at the root of the disk
            #   e.g. E:\Mi Unidad\00_Anthropic
            $candidate = Join-Path $drive $folderName
            $candidate = Join-Path $candidate "00_Anthropic"
            if (Test-Path $candidate) {
                return $candidate
            }

            # Case 2: Drive folder sits inside a user's profile folder
            #   e.g. C:\Users\Michel\Mi unidad\00_Anthropic
            $usersPath = Join-Path $drive "Users"
            if (Test-Path $usersPath) {
                $userFolders = Get-ChildItem -Path $usersPath -Directory -ErrorAction SilentlyContinue
                foreach ($userFolder in $userFolders) {
                    $candidate = Join-Path $userFolder.FullName $folderName
                    $candidate = Join-Path $candidate "00_Anthropic"
                    if (Test-Path $candidate) {
                        return $candidate
                    }
                }
            }
        }
    }

    # Nothing found on any drive letter
    return $null
}

function Get-PipelinePaths {
    <#
        Returns a hashtable with all the standard pipeline folder paths,
        based on the auto-detected Drive root.
    #>
    $driveRoot = Find-DriveRoot

    if (-not $driveRoot) {
        Write-Host ""
        Write-Host "ERROR: Could not find the '00_Anthropic' folder on any drive letter." -ForegroundColor Red
        Write-Host "Checked all available drives looking for:" -ForegroundColor Red
        Write-Host "  <drive>:\Mi unidad\00_Anthropic"
        Write-Host "  <drive>:\Mi Unidad\00_Anthropic"
        Write-Host ""
        Write-Host "Make sure Google Drive is installed and synced on this machine." -ForegroundColor Yellow
        exit 1
    }

    return @{
        DriveRoot   = $driveRoot
        IntakeDir   = Join-Path $driveRoot "_source_intake"
        LibraryDir  = Join-Path $driveRoot "Library"
        CombinedDir = Join-Path $driveRoot "combinados"
    }
}
