@echo off
chcp 65001 >nul
REM ===================================================================
REM  Book Pipeline - arma el programa de escritorio
REM  Resultado: dist\BookPipeline.exe  + acceso directo en el Escritorio
REM  Correr desde la carpeta del repo (doble clic o:  .\build.bat)
REM ===================================================================

cd /d "%~dp0"
echo.
echo ==========================================
echo   Book Pipeline - armando el .exe
echo ==========================================
echo.

if not exist "app\ventana.py" (
    echo [ERROR] No encuentro app\ventana.py. Corre este archivo desde la carpeta del repo.
    pause
    exit /b 1
)
if not exist "BookPipeline.spec" (
    echo [ERROR] No encuentro BookPipeline.spec.
    pause
    exit /b 1
)

echo [1/4] Instalando/actualizando librerias...
python -m pip install --upgrade pip >nul
python -m pip install --upgrade -r requirements.txt pyinstaller
if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de librerias.
    pause
    exit /b 1
)

echo [2/4] Borrando el armado anterior...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo [3/4] Armando el ejecutable (tarda de 2 a 5 minutos)...
python -m PyInstaller BookPipeline.spec --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] Fallo el armado. Revisa los mensajes de arriba.
    pause
    exit /b 1
)

echo [4/4] Creando el acceso directo en el Escritorio...
powershell -NoProfile -Command "$e=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $e 'Book Pipeline.lnk')); $s.TargetPath='%~dp0dist\BookPipeline.exe'; $s.WorkingDirectory='%~dp0dist'; $s.IconLocation='%~dp0dist\BookPipeline.exe,0'; $s.Save()"

echo.
echo ==========================================
echo   LISTO
echo ==========================================
echo   Programa:  %~dp0dist\BookPipeline.exe
echo   Acceso directo: "Book Pipeline" en tu Escritorio
echo ==========================================
echo.
pause
