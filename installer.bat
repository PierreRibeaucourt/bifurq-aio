@echo off
setlocal
cd /d "%~dp0"

rem Retire la marque "provient d'Internet" des fichiers de l'outil, au cas ou seul
rem installer.bat a ete debloque et pas le ZIP : sinon Windows peut restreindre les
rem scripts PowerShell de notification et de tache planifiee.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -Recurse -File | Unblock-File" >nul 2>nul

set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    where python >nul 2>nul
    if not errorlevel 1 set "PY=python"
)
if not defined PY (
    echo Python n'est pas installe sur cet ordinateur.
    echo La page de telechargement va s'ouvrir.
    start https://www.python.org/downloads/
    echo Pendant l'installation, cochez bien la case "Add python.exe to PATH".
    echo Ensuite, relancez ce fichier installer.bat.
    pause
    exit /b 1
)

if not exist "config\venv\Scripts\pythonw.exe" (
    echo Preparation de l'outil, une seule fois...
    %PY% -m venv config\venv
)

"config\venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt >nul 2>nul
"config\venv\Scripts\python.exe" -m veille_ia.raccourci
start "" "config\venv\Scripts\pythonw.exe" -m veille_ia.installer.server

echo.
echo C'est pret. L'outil s'ouvre dans votre navigateur.
echo Pour y revenir plus tard : raccourci "Veille des adresses inventees" sur votre bureau.
echo Cette fenetre va se fermer toute seule.
timeout /t 8 >nul
