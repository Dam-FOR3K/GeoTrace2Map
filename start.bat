@echo off
title GeoTrace2Map (GT2M) - Plateforme Forensique de Géolocalisation et Cartographie
color 0A

echo ========================================================
echo   Lancement de GeoTrace2Map (GT2M)
echo   Forensic Mobile Geolocation and Mapping Platform
echo   Developpe par Dam-FOR3K
echo ========================================================
echo.

:: Verifier Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Erreur : Python n'est pas installe ou n'est pas dans le PATH.
    echo Veuillez installer Python 3.9+ : https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Installer les dependances
echo [i] Verification des dependances Python...
pip install -r requirements.txt --quiet --disable-pip-version-check

echo [i] Demarrage du serveur et ouverture du navigateur...
python run.py

pause
