# Windows kurulum paketini yerelde üretir (GitHub Actions'taki "Windows paketi" iş akışıyla aynı adımlar).
#
# Gereksinimler: Python 3.13 (py başlatıcısıyla), NSIS 3 (makensis PATH'te ya da varsayılan klasörde).
# NSIS yoksa:  winget install NSIS.NSIS   ya da   choco install nsis
#
# Kullanım (PowerShell, proje klasöründe):
#   .\scripts\build_windows.ps1              # paketle, dene, kurulum dosyasını üret
#   .\scripts\build_windows.ps1 -SkipSmoke   # paketlenmiş programı denemeden
#
# Çıktı: dist\EnglishMaster\ (taşınabilir klasör) ve dist\EnglishMaster-Setup-<sürüm>.exe
# Bu betik ayrı bir sanal ortam (.venv-build) kullanır; geliştirme ortamına dokunmaz.
param([switch]$SkipSmoke)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path ".venv-build")) { py -3.13 -m venv .venv-build }
$python = ".\.venv-build\Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt -r packaging\requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Bağımlılıklar kurulamadı" }

$version = & $python -c "import app; print(app.__version__)"
Write-Host "`n== English Master $version paketleniyor"

& $python scripts\build_content.py
if ($LASTEXITCODE -ne 0) { throw "İçerik doğrulanamadı" }
& $python scripts\build_audio.py --check
& $python packaging\collect_licenses.py
& $python -m PyInstaller packaging\english_master.spec --noconfirm --distpath dist --workpath build\pyi
if ($LASTEXITCODE -ne 0) { throw "PyInstaller başarısız" }

if (-not $SkipSmoke) {
  Write-Host "`n== Paketlenmiş program deneniyor"
  & $python packaging\smoke_test.py dist\EnglishMaster\EnglishMaster.exe
  if ($LASTEXITCODE -ne 0) { throw "Paketlenmiş program denemesi başarısız" }
}

$makensis = Get-Command makensis -ErrorAction SilentlyContinue
if (-not $makensis) {
  foreach ($dir in @("${env:ProgramFiles(x86)}\NSIS", "$env:ProgramFiles\NSIS")) {
    if (Test-Path "$dir\makensis.exe") { $makensis = "$dir\makensis.exe" }
  }
}
if (-not $makensis) {
  Write-Warning "NSIS bulunamadı; kurulum dosyası üretilmedi. Taşınabilir klasör: dist\EnglishMaster"
  exit 0
}
& $makensis /V3 /DVERSION=$version packaging\installer.nsi
if ($LASTEXITCODE -ne 0) { throw "makensis başarısız" }
$setup = "dist\EnglishMaster-Setup-$version.exe"
$hash = (Get-FileHash $setup -Algorithm SHA256).Hash.ToLower()
"$hash  EnglishMaster-Setup-$version.exe" | Out-File "$setup.sha256" -Encoding ascii
Write-Host "`nHazır: $setup"
Write-Host "SHA-256: $hash"
