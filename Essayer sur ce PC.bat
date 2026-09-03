@echo off
REM Double-cliquez sur ce fichier pour ouvrir l'application sur ce PC.
REM Donnees isolees dans _local\, aucun Pi n'est touche.
title Traceability 2.0 - essai sur PC
cd /d "%~dp0"

python tools\run_pc.py
if errorlevel 1 goto essai2
goto fin

:essai2
echo.
echo Python n'a pas repondu, nouvel essai avec le lanceur "py"...
echo.
py tools\run_pc.py
if errorlevel 1 (
    echo.
    echo -------------------------------------------------------------
    echo  L'application n'a pas pu demarrer.
    echo  Verifiez que Python est installe : https://www.python.org
    echo  Puis, dans ce dossier, installez les modules necessaires :
    echo     pip install opencv-python-headless pillow reportlab bleak tinytuya
    echo -------------------------------------------------------------
    echo.
    pause
)

:fin
