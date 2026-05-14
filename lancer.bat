@echo off
chcp 65001 >nul
title Mouse Recorder

echo.
echo  === Mouse Recorder ===
echo.

:: Vérifier si uv est installé
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo  Installation de uv ^(gestionnaire Python^)...
    powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"

    :: Recharger le PATH
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"

    where uv >nul 2>&1
    if %errorlevel% neq 0 (
        echo.
        echo  ERREUR : l'installation de uv a echoue.
        echo  Relance ce fichier en tant qu'administrateur.
        pause
        exit /b 1
    )
    echo  uv installe avec succes.
    echo.
)

:: Installer les dépendances si besoin
if not exist ".venv" (
    echo  Preparation de l'environnement ^(premiere fois uniquement^)...
    uv sync
    echo.
)

:: Lancer l'application
uv run python mouse_recorder.py
