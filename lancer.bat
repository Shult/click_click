@echo off
chcp 65001 >nul
title ClickClick

echo.
echo  === ClickClick ===
echo.

:: Vérifier si uv est installé
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo  Installing uv ^(Python toolchain^)...
    powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"

    :: Recharger le PATH
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"

    where uv >nul 2>&1
    if %errorlevel% neq 0 (
        echo.
        echo  ERROR: uv installation failed.
        echo  Try running this file as administrator.
        pause
        exit /b 1
    )
    echo  uv installed successfully.
    echo.
)

:: Installer les dépendances si besoin
if not exist ".venv" (
    echo  Preparing the environment ^(first run only^)...
    uv sync
    echo.
)

:: Lancer l'application
uv run python mouse_recorder.py
