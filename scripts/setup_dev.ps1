# Windows'ta geliştirme ortamını kurar ve testleri çalıştırır.
# Kullanım (PowerShell, proje klasöründe):  .\scripts\setup_dev.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path ".venv")) { py -3.13 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
& .\.venv\Scripts\python.exe scripts\build_content.py
& .\.venv\Scripts\python.exe -m pytest -rs
Write-Host "`nHazır. Programı başlatmak için:  .\.venv\Scripts\python.exe -m app"
