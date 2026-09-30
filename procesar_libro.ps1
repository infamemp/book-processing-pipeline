<#
.SYNOPSIS
    Procesa un libro completo: EPUB/PDF -> Markdown -> KB (core + biblioteca).

.DESCRIPTION
    Un solo comando por libro. Se puede correr varias veces: lo que ya se hizo
    no se repite ni se vuelve a pagar. Antes de gastar muestra el costo estimado
    y pide confirmacion.

    Los resultados se guardan en:  <Google Drive>\00_Anthropic\Library\<libro>\
    (si no encuentra Google Drive, en una carpeta "kb_<libro>" junto al libro).

.EXAMPLE
    .\procesar_libro.ps1 -Libro "E:\Descargas\libro.epub"
    .\procesar_libro.ps1 -Libro "E:\Descargas\libro.epub" -Lote
    .\procesar_libro.ps1 -Libro "E:\Descargas\libro.epub" -Unidades "U05,U08"   (prueba barata)
#>
param(
    [Parameter(Mandatory = $true)][string]$Libro,
    [switch]$Lote,          # ~50% mas barato; Anthropic tarda minutos u horas
    [string]$Unidades = "", # solo para pruebas, ej. "U05,U08"
    [string]$Salida = ""    # carpeta de salida (opcional)
)

$ErrorActionPreference = "Stop"
$aqui = Split-Path -Parent $MyInvocation.MyCommand.Path

function Buscar-Drive {
    foreach ($d in (Get-PSDrive -PSProvider FileSystem).Root) {
        foreach ($n in @("Mi unidad", "Mi Unidad", "My Drive")) {
            $c = Join-Path $d $n
            if (Test-Path (Join-Path $c "00_Anthropic")) { return (Join-Path $c "00_Anthropic") }
            $u = Join-Path $d "Users"
            if (Test-Path $u) {
                foreach ($p in (Get-ChildItem $u -Directory -ErrorAction SilentlyContinue)) {
                    $c2 = Join-Path $p.FullName $n
                    if (Test-Path (Join-Path $c2 "00_Anthropic")) { return (Join-Path $c2 "00_Anthropic") }
                }
            }
        }
    }
    return $null
}

if (-not (Test-Path $Libro)) { Write-Host "No encuentro el libro: $Libro" -ForegroundColor Red; exit 1 }
$Libro = (Resolve-Path $Libro).Path
foreach ($v in @("ANTHROPIC_API_KEY", "GEMINI_API_KEY")) {
    if (-not [Environment]::GetEnvironmentVariable($v)) {
        Write-Host "Falta la variable de entorno $v (ver README)." -ForegroundColor Red; exit 1
    }
}

$nombre = [IO.Path]::GetFileNameWithoutExtension($Libro)
$slug = ($nombre.ToLower() -replace "[^a-z0-9]+", "-").Trim("-")

if (-not $Salida) {
    $drive = Buscar-Drive
    if ($drive) { $Salida = Join-Path $drive "Library\$slug" }
    else { $Salida = Join-Path (Split-Path -Parent $Libro) "kb_$slug" }
}
New-Item -ItemType Directory -Path $Salida -Force | Out-Null
Write-Host "Libro  : $Libro"
Write-Host "Salida : $Salida" -ForegroundColor Cyan

# Paso 1: convertir (si ya existe libro.md, se reutiliza)
$md = Join-Path $Salida "libro.md"
if (Test-Path $md) {
    Write-Host "[1/2] Conversion ya hecha, se reutiliza: libro.md" -ForegroundColor Yellow
} else {
    Write-Host "[1/2] Convirtiendo el libro a Markdown..." -ForegroundColor Cyan
    python (Join-Path $aqui "convert.py") $Libro -o $md
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $md)) { Write-Host "Fallo la conversion." -ForegroundColor Red; exit 1 }
}

# Paso 2: extraer el KB
Write-Host "[2/2] Extrayendo el KB..." -ForegroundColor Cyan
$args2 = @((Join-Path $aqui "extract.py"), "--input", $md, "--output", $Salida)
if ($Lote) { $args2 += "--batch" }
if ($Unidades) { $args2 += @("--units", $Unidades) }
python @args2
if ($LASTEXITCODE -ne 0) { Write-Host "La extraccion se detuvo. Corre el mismo comando otra vez para continuar." -ForegroundColor Yellow; exit 1 }
